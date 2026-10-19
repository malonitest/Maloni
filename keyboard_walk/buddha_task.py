"""Assisted MuJoCo pick-and-place demo: ground-truth navigation and point grip.

Manipulation and the finale use a six-dimensional base support. Navigation
uses the walking policy with upright assistance while carrying; arms use
damped least-squares inverse kinematics.
"""
import heapq
import math
import secrets

import mujoco
import numpy as np


def angle_error(target, actual):
    return math.atan2(math.sin(target - actual), math.cos(target - actual))


def yaw_of(quat):
    w, x, y, z = quat
    return math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z))


def quat_pose(yaw, pitch=0):
    return np.array([math.cos(yaw/2)*math.cos(pitch/2),
                     -math.sin(yaw/2)*math.sin(pitch/2),
                     math.cos(yaw/2)*math.sin(pitch/2),
                     math.sin(yaw/2)*math.cos(pitch/2)])


def smooth(t):
    t = np.clip(t, 0, 1)
    return t*t*(3-2*t)


class FloorPlanner:
    """A* over static colliders, with a conservative circular robot footprint."""
    step = .2
    radius = .39

    def __init__(self, model, data):
        self.model = model
        self.obstacles = []
        for g in range(model.ngeom):
            if model.geom_bodyid[g] != 0 or not (model.geom_contype[g] or model.geom_conaffinity[g]):
                continue
            if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_PLANE:
                continue
            pos = data.geom_xpos[g]
            half = np.abs(data.geom_xmat[g].reshape(3, 3)) @ model.geom_size[g]
            if pos[2] - half[2] > 1.8 or pos[2] + half[2] < .05:
                continue
            self.obstacles.append((pos[:2] - half[:2], pos[:2] + half[:2]))
        self.lows = np.array([o[0] for o in self.obstacles])
        self.highs = np.array([o[1] for o in self.obstacles])
        self.cell_cache = {}

    def clear(self, xy, radius=None):
        radius = self.radius if radius is None else radius
        x, y = xy
        if not (-7.5+radius < x < 7.5-radius and -5.5+radius < y < 5.65-radius):
            return False
        delta = np.maximum(np.maximum(self.lows-np.asarray(xy),np.asarray(xy)-self.highs),0)
        return not np.any(np.sum(delta*delta,axis=1) < radius*radius)

    def cell_clear(self, cell):
        if cell not in self.cell_cache:
            self.cell_cache[cell] = self.clear(np.array(cell)*self.step)
        return self.cell_cache[cell]

    def cell(self, xy):
        return tuple(np.rint(np.asarray(xy)/self.step).astype(int))

    def line_clear(self, start, goal):
        count = max(2,int(np.ceil(np.linalg.norm(np.asarray(goal)-start)/.05))+1)
        return all(self.clear(point) for point in np.linspace(start,goal,count))

    def path(self, start, goal):
        start, goal = np.asarray(start), np.asarray(goal)
        if not self.clear(start) or not self.clear(goal):
            raise ValueError('Cíl nebo výchozí bod není přístupný.')
        if self.line_clear(start,goal):
            return [start.copy(),goal.copy()]
        first, last = self.cell(start), self.cell(goal)
        todo = [(0., first)]
        cost = {first: 0.}
        parent = {}
        while todo:
            _, cell = heapq.heappop(todo)
            if cell == last:
                cells = [cell]
                while cell in parent:
                    cell = parent[cell]
                    cells.append(cell)
                points = [np.array(c)*self.step for c in cells[::-1]]
                points[0], points[-1] = start.copy(), goal.copy()
                # Keep only corners, retaining collision-checked grid edges.
                result = [points[0]]
                for i in range(1, len(points)-1):
                    a, b = points[i]-points[i-1], points[i+1]-points[i]
                    if abs(a[0]*b[1]-a[1]*b[0]) > 1e-6:
                        result.append(points[i])
                result.append(points[-1])
                shortened = [result[0]]
                index = 0
                while index < len(result)-1:
                    nxt = len(result)-1
                    while nxt > index+1 and not self.line_clear(result[index],result[nxt]):
                        nxt -= 1
                    shortened.append(result[nxt])
                    index = nxt
                return shortened
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nxt = (cell[0]+dx, cell[1]+dy)
                if not self.cell_clear(nxt):
                    continue
                if dx and dy and (not self.cell_clear((cell[0]+dx, cell[1]))
                                  or not self.cell_clear((cell[0], cell[1]+dy))):
                    continue
                value = cost[cell] + math.hypot(dx, dy)
                if value < cost.get(nxt, float('inf')):
                    cost[nxt] = value
                    parent[nxt] = cell
                    heapq.heappush(todo, (value+math.dist(nxt,last), nxt))
        raise ValueError('Nenalezena průchozí trasa.')


class BuddhaTask:
    labels = {'settle':'Ustálení sošky', 'search':'Rozhlížím se',
              'approach':'Jdu k Buddhovi', 'align':'Připravuji uchopení',
              'reach':'Skláním se pro Buddhu', 'lift':'Zvedám Buddhu',
              'carry':'Nesu Buddhu na stůl', 'table_align':'Připravuji položení',
              'place':'Pokládám Buddhu', 'release':'Pouštím a odtahuji ruce',
              'verify':'Kontroluji položení', 'retreat':'Ustupuji od stolu',
              'face':'Otáčím se ke kameře', 'celebrate':'Hotovo! Oslavuji!',
              'done':'Úkol dokončen', 'failed':'Úkol zastaven'}
    manipulation = {'reach','lift','table_align','place','release','verify'}

    def __init__(self, model, data, actuator_ids, default_actuator, seed=None):
        self.m, self.d = model, data
        self.act = np.asarray(actuator_ids)
        self.joints = model.actuator_trnid[self.act, 0]
        self.qa = model.jnt_qposadr[self.joints]
        self.va = model.jnt_dofadr[self.joints]
        self.default = default_actuator.copy()
        self.body = model.body('buddha').id
        self.base = model.body('pelvis').id
        self.obj_q = model.jnt_qposadr[model.joint('buddha_free').id]
        self.obj_v = model.jnt_dofadr[model.joint('buddha_free').id]
        self.weld = model.equality('buddha_grasp').id
        self.support_weld = model.equality('task_base_support').id
        self.mocap = model.body('task_support').mocapid[0]
        self.palms = [model.site(s+'_palm').id for s in ['left','right']]
        self.ikdata = mujoco.MjData(model)
        self.drop = model.site('buddha_drop').pos.copy()
        self.planner = FloorPlanner(model, data)
        self.rng = np.random.default_rng(seed)
        self.reset(seed)

    @property
    def attached(self):
        return bool(self.d.eq_active[self.weld])

    @property
    def status(self):
        return ('POZASTAVENO — B pokračovat: ' if self.paused else '') + self.labels[self.state]

    def reset(self, seed=None):
        self.seed = int(seed) if seed is not None else secrets.randbits(32)
        self.rng = np.random.default_rng(self.seed)
        self.d.eq_active[self.weld] = 0
        self.d.eq_active[self.support_weld] = 0
        self.paused = False
        self.pause_time = None
        self.state = 'settle'
        self.since = self.d.time
        self.started = self.d.time
        self.failure = ''
        self.success = False
        self.path = []
        self.anchor = self.d.qpos[:3].copy()
        self.heading = yaw_of(self.d.qpos[3:7])
        self.support_pose = None
        self.ik_solution = None
        self.stable_since = None
        for _ in range(1000):
            xy = self.rng.uniform([-2.8,-2.4],[2.8,2.0])
            approach = xy-np.array([.43,0])
            if np.linalg.norm(xy-self.d.qpos[:2]) < 1.1 or not self.planner.clear(xy, .7):
                continue
            try:
                self.planner.path(self.d.qpos[:2], approach)
                self.planner.path(approach, [5.7,3.55])
            except ValueError:
                continue
            self.spawn = xy.copy()
            self.approach = approach
            break
        else:
            raise RuntimeError('Nelze najít volné místo pro Buddhu.')
        q = self.obj_q
        self.d.qpos[q:q+7] = [*self.spawn, .001, 1,0,0,0]
        self.d.qvel[self.obj_v:self.obj_v+6] = 0
        mujoco.mj_forward(self.m,self.d)
        print(f'Buddha: seed={self.seed}, místo={self.spawn.round(3).tolist()}', flush=True)

    def transition(self, state):
        self.state = state
        self.ik_solution = None
        self.since = self.d.time
        self.anchor = self.d.qpos[:3].copy()
        self.heading = yaw_of(self.d.qpos[3:7])
        self.entry_q = self.d.qpos[self.qa].copy()
        self.entry_obj = self.d.xpos[self.body].copy()
        self.entry_hands = np.array([self.d.site_xpos[s].copy() for s in self.palms])
        print(f'Buddha [{self.d.time:.2f} s]: {self.labels[state]}', flush=True)

    def fail(self, reason):
        self.failure = reason
        self.transition('failed')
        print('Buddha FAIL: '+reason, flush=True)

    def pause(self):
        if not self.paused:
            self.paused = True
            self.pause_time = self.d.time
            self.pause_anchor = self.d.qpos[:3].copy()
            self.pause_quat = self.d.qpos[3:7].copy()
            self.pause_target = self.d.qpos[self.qa].copy()

    def resume(self):
        if self.paused:
            delta = self.d.time-self.pause_time
            self.since += delta
            self.started += delta
            if self.stable_since is not None:
                self.stable_since += delta
            self.paused = False

    def route(self, goal):
        try:
            self.path = self.planner.path(self.d.qpos[:2], goal)[1:]
        except ValueError as exc:
            self.fail(str(exc))

    def navigate(self, speed):
        while self.path and np.linalg.norm(self.path[0]-self.d.qpos[:2]) < .20:
            self.path.pop(0)
        if not self.path:
            return np.zeros(3), True
        delta = self.path[0]-self.d.qpos[:2]
        error = angle_error(math.atan2(delta[1],delta[0]), yaw_of(self.d.qpos[3:7]))
        # This policy has a yaw dead zone at small commands, especially
        # with raised arms. Turn in place first, then walk the straight segment.
        if abs(error) > .18:
            turn = .65 if error > 0 else -.8
            forward = 0.
        else:
            turn = 0.
            forward = speed
        return np.array([forward,0,turn]), False

    def turn_to(self, heading):
        error = angle_error(heading,yaw_of(self.d.qpos[3:7]))
        if abs(error) < .10:
            return np.zeros(3), True
        return np.array([0,0,.6 if error > 0 else -.8]), False

    def attach(self):
        obj = self.d.xpos[self.body]
        errors = [np.linalg.norm(self.d.site_xpos[s]-(obj+np.array([0,side*.065,.075])))
                  for s,side in zip(self.palms,[1,-1])]
        if max(errors) > .065:
            return False
        hand = self.m.body('left_wrist_yaw_link').id
        point = self.d.site_xpos[self.palms[0]].copy()
        self.m.eq_data[self.weld,:3] = self.d.xmat[hand].reshape(3,3).T@(point-self.d.xpos[hand])
        self.m.eq_data[self.weld,3:6] = self.d.xmat[self.body].reshape(3,3).T@(point-obj)
        self.d.eq_active[self.weld] = 1
        self.grasp_offset = self.d.site_xpos[self.palms[0]]-obj
        return True

    def ik(self, target, hands=None, feet=None, base_pose=None):
        """Damped least-squares position IK in a separate, non-stepped MjData."""
        work = self.ikdata
        work.qpos[:] = self.d.qpos
        work.qpos[self.qa] = target
        work.qpos[self.qa[12:15]] = self.d.qpos[self.qa[12:15]]
        arm_indices = np.arange(15,29)
        selected = arm_indices if feet is None else np.r_[np.arange(12),arm_indices]
        dofs = self.va[selected]
        if self.ik_solution is not None:
            work.qpos[self.qa[selected]] = self.ik_solution[selected]
        jp = np.zeros((3,self.m.nv))
        jr = np.zeros_like(jp)
        for _ in range(10):
            mujoco.mj_kinematics(self.m,work)
            mujoco.mj_comPos(self.m,work)
            jac, error = [], []
            if hands is not None:
                for site,goal in zip(self.palms,hands):
                    mujoco.mj_jacSite(self.m,work,jp,jr,site)
                    jac.append(jp[:,dofs].copy())
                    error.append(goal-work.site_xpos[site])
            if feet is not None:
                for side,goal in zip(['left','right'],feet):
                    body = self.m.body(side+'_ankle_roll_link').id
                    mujoco.mj_jacBody(self.m,work,jp,jr,body)
                    jac.append(jp[:,dofs].copy()*2)
                    error.append((goal-work.xpos[body])*2)
            matrix, err = np.vstack(jac), np.concatenate(error)
            if np.linalg.norm(err) < .003:
                break
            dq = matrix.T@np.linalg.solve(matrix@matrix.T+.0001*np.eye(len(err)),err)
            dq *= min(1., .10 / max(np.max(np.abs(dq)), 1e-9))
            work.qpos[self.qa[selected]] += dq
            for i in selected:
                joint = self.joints[i]
                if self.m.jnt_limited[joint]:
                    work.qpos[self.qa[i]] = np.clip(work.qpos[self.qa[i]],*self.m.jnt_range[joint])
        self.ik_solution = work.qpos[self.qa].copy()
        self.ik_solution[12:15] = target[12:15]
        return self.ik_solution.copy()

    def hands_for(self, obj, heading=0):
        lateral = np.array([-math.sin(heading),math.cos(heading),0])
        hands = np.array([obj+lateral*.065+np.array([0,0,.075]),
                          obj-lateral*.065+np.array([0,0,.075])])
        if self.attached and hasattr(self, 'grasp_offset'):
            c, s = math.cos(heading), math.sin(heading)
            rotation = np.array([[c,-s,0],[s,c,0],[0,0,1]])
            hands[0] = obj+rotation@self.grasp_offset
        return hands

    def update(self, policy_target, camera_position):
        """Return policy command and joint target override for the current state."""
        target = policy_target.copy()
        cmd = np.zeros(3)
        self.support_pose = None
        if self.paused:
            self.support_pose = (self.pause_anchor,self.pause_quat)
            return cmd,self.pause_target.copy()
        t = self.d.time-self.since
        if self.state not in {'done','failed'} and self.d.time-self.started > 180:
            self.fail('Časový limit 180 s.')
        if self.state not in {'done','failed'} and (self.d.qpos[2] < (.18 if self.state in self.manipulation else .35) or not np.isfinite(self.d.qpos).all()):
            self.fail('Robot spadl nebo simulace není konečná.')
        if self.state in {'carry','table_align','place'} and (not self.attached or self.d.xpos[self.body,2] < .20):
            self.fail('Soška byla upuštěna.')
        if self.state == 'settle':
            if t > 2:
                self.transition('search')
        elif self.state == 'search':
            target[12] += .22*math.sin(math.pi*t)
            if t > 2:
                self.transition('approach')
                self.route(self.approach)
        elif self.state == 'approach':
            cmd, arrived = self.navigate(.45)
            if arrived:
                self.transition('align')
        elif self.state == 'align':
            cmd, aligned = self.turn_to(0)
            if aligned and t > 1:
                self.feet = np.array([self.d.xpos[self.m.body(s+'_ankle_roll_link').id].copy()
                                      for s in ['left','right']])
                self.transition('reach')
        elif self.state == 'reach':
            a = smooth(t/4)
            base = self.anchor.copy()
            base[:2] = (1-a)*self.anchor[:2]+a*self.approach
            base[2] = (1-a)*self.anchor[2]+a*.25
            pose = (base,quat_pose(self.heading,.85*a))
            self.support_pose = pose
            obj = self.d.xpos[self.body].copy()
            hands = (1-a)*self.entry_hands+a*self.hands_for(obj)
            posture = self.entry_q.copy()
            crouched = self.default.copy()
            crouched[[0,6]] = -1.8
            crouched[[3,9]] = 2.3
            crouched[[4,10]] = -.5
            posture[:15] = (1-a)*self.entry_q[:15]+a*crouched[:15]
            target = self.ik(posture,hands)
            if t > 4.5 and self.attach():
                self.transition('lift')
            elif t > 9:
                print('Dosah rukou:', np.round(self.d.site_xpos[self.palms]-hands,3).tolist(), flush=True)
                self.fail('Ruce nedosáhly k sošce.')
        elif self.state == 'lift':
            a = smooth(t/4)
            base = self.anchor.copy()
            base[2] = (1-a)*self.anchor[2]+a*.79
            pose = (base,quat_pose(self.heading,.85*(1-a)))
            self.support_pose = pose
            carry_obj = np.array([base[0]+.32,base[1],.91])
            obj = (1-a)*self.entry_obj+a*carry_obj
            hands = self.hands_for(obj)
            posture = self.entry_q.copy()
            posture[:15] = (1-a)*self.entry_q[:15]+a*self.default[:15]
            target = self.ik(posture,hands)
            if t > 4:
                target[:15] = (1-smooth((t-4)/2))*target[:15]+smooth((t-4)/2)*self.default[:15]
            if t > 7:
                self.transition('carry')
                self.route([5.7,3.55])
        elif self.state == 'carry':
            cmd, arrived = self.navigate(.4)
            if int(t/10) != getattr(self,'report_bucket',-1):
                self.report_bucket = int(t/10)
                print('Přenášení:',round(self.d.time,1),self.d.qpos[:3].round(2).tolist(), 'cíl', self.path[0].round(2).tolist() if self.path else None, 'příkaz',cmd.round(2).tolist(),flush=True)
            heading = yaw_of(self.d.qpos[3:7])
            obj = self.d.qpos[:3]+np.array([.32*math.cos(heading),.32*math.sin(heading),.12])
            target = self.ik(target,self.hands_for(obj,heading))
            if arrived:
                self.transition('table_align')
        elif self.state == 'table_align':
            cmd,aligned = self.turn_to(math.pi/2)
            heading = yaw_of(self.d.qpos[3:7])
            obj = self.d.qpos[:3]+np.array([.32*math.cos(heading),.32*math.sin(heading),.12])
            target = self.ik(target,self.hands_for(obj,heading))
            if aligned and t > 1:
                self.transition('place')
        elif self.state in {'place','release','verify'}:
            base = self.anchor.copy()
            if self.state == 'place':
                a = smooth((t-2)/3)
                base[:2] = (1-a)*self.anchor[:2]+a*np.array([self.drop[0], self.drop[1]-.40])
            pose = (base,quat_pose(self.heading))
            self.support_pose = pose
            if self.state == 'place':
                # Lift above the edge before extending across the desktop.
                if t < 2:
                    obj = self.entry_obj.copy()
                    obj[2] += smooth(t/2)*(1.14-obj[2])
                elif t < 5:
                    obj = (1-smooth((t-2)/3))*np.r_[self.entry_obj[:2],1.14]+smooth((t-2)/3)*(self.drop+np.array([0,0,.10]))
                else:
                    obj = self.drop+np.array([0,0,.10*(1-smooth((t-5)/2))+.003])
                target = self.ik(self.entry_q,self.hands_for(obj,self.heading))
                if t > 8:
                    actual = self.d.xpos[self.body]
                    if np.linalg.norm(actual[:2]-self.drop[:2]) < .12 and -.01 < actual[2]-self.drop[2] < .08:
                        self.d.eq_active[self.weld] = 0
                        self.transition('release')
                    elif t > 12:
                        print('Položení: skutečnost/cíl',actual,self.drop,flush=True)
                        self.fail('Soška nedosáhla odkládací plochy.')
            elif self.state == 'release':
                hands = self.entry_hands.copy()
                lateral = np.array([-math.sin(self.heading),math.cos(self.heading),0])
                a = smooth(t/2)
                hands[0] += a*(.12*lateral+np.array([0,0,.10]))
                hands[1] += a*(-.12*lateral+np.array([0,0,.10]))
                target = self.ik(self.entry_q,hands)
                if t > 2:
                    self.transition('verify')
                    self.stable_since = None
            else:
                target = self.entry_q.copy()
                pos = self.d.xpos[self.body]
                table = self.m.geom('lab_bench_top_1').id
                supported = any((c.geom1 == table and self.m.geom_bodyid[c.geom2] == self.body)
                                or (c.geom2 == table and self.m.geom_bodyid[c.geom1] == self.body)
                                for c in self.d.contact)
                stable = (not self.attached and supported and np.linalg.norm(pos[:2]-self.drop[:2]) < .16
                          and abs(pos[2]-self.drop[2]) < .025
                          and np.linalg.norm(self.d.qvel[self.obj_v:self.obj_v+6]) < .06)
                if stable:
                    if self.stable_since is None:
                        self.stable_since = self.d.time
                    if self.d.time-self.stable_since >= 1:
                        self.transition('retreat')
                else:
                    self.stable_since = None
                if t > 8:
                    self.fail('Soška nespočívá stabilně na stole.')
        elif self.state == 'retreat':
            cmd[0] = -.35
            base = self.anchor.copy()
            base[:2] -= .5*smooth(t/3)*np.array([math.cos(self.heading),math.sin(self.heading)])
            self.support_pose = (base,quat_pose(self.heading))
            target = (1-smooth(t/2))*self.entry_q+smooth(t/2)*target
            if t > 3:
                self.face_heading = math.atan2(camera_position[1]-self.d.qpos[1],camera_position[0]-self.d.qpos[0])
                self.transition('face')
        elif self.state == 'face':
            self.face_heading = math.atan2(camera_position[1]-self.d.qpos[1],camera_position[0]-self.d.qpos[0])
            cmd, aligned = self.turn_to(self.face_heading)
            desired_yaw = self.heading+smooth(t/4)*angle_error(self.face_heading,self.heading)
            self.support_pose = (self.anchor,quat_pose(desired_yaw))
            target[15:] = self.default[15:]
            if t > 4 and aligned:
                self.transition('celebrate')
        elif self.state == 'celebrate':
            a = min(smooth(t),smooth((6-t)))
            base = self.anchor.copy()
            base[2] -= a*.025*(1+math.sin(6*t))
            self.support_pose = (base,quat_pose(self.heading))
            target[[15,22]] -= a*1.4
            target[[16,23]] += a*np.array([.55,-.55])
            target[[18,25]] += a*np.array([.3+.2*math.sin(6*t),.3-.2*math.sin(6*t)])
            bounce = a*.08*(1+math.sin(6*t))
            target[[0,6]] -= bounce/2
            target[[3,9]] += bounce
            target[[4,10]] -= bounce/2
            if t > 6:
                self.success = True
                self.transition('done')
                print(f'Buddha PASS seed={self.seed}: položeno, otočeno ke kameře, oslava dokončena.',flush=True)
        return cmd,target

    def support(self):
        """Apply the explicit support and upright assistance used by this demo."""
        self.d.xfrc_applied[self.base] = 0
        self.d.xfrc_applied[self.body] = 0
        if self.attached:
            # The demonstration grip holds the statue upright while allowing
            # the fixed palm to rotate naturally around its attachment point.
            error = np.empty(3)
            desired = quat_pose(yaw_of(self.d.qpos[3:7]))
            mujoco.mju_subQuat(error,desired,self.d.xquat[self.body])
            rotation = self.d.xmat[self.body].reshape(3,3)
            torque = rotation@(2*error-.04*self.d.qvel[self.obj_v+3:self.obj_v+6])
            gravity = np.array([0,0,-self.m.body_mass[self.body]*9.81])
            grip = self.d.site_xpos[self.palms[0]]
            torque -= np.cross(self.d.xipos[self.body]-grip,gravity)
            self.d.xfrc_applied[self.body,3:] = np.clip(torque,-1,1)
        self.d.eq_active[self.support_weld] = self.support_pose is not None
        if self.support_pose is None and (self.attached or self.state in {'retreat','face','celebrate'}):
            # Modest upright assistance for the arm configuration absent from
            # walking-policy training; locomotion still comes from leg torques.
            error = np.empty(3)
            mujoco.mju_subQuat(error,quat_pose(yaw_of(self.d.qpos[3:7])),self.d.qpos[3:7])
            local = 160*error-18*self.d.qvel[3:6]
            world = self.d.xmat[self.base].reshape(3,3)@local
            world[2] = 0
            self.d.xfrc_applied[self.base,3:] = np.clip(world,-100,100)
        if self.support_pose is not None:
            position, quat = self.support_pose
            self.d.mocap_pos[self.mocap] = position
            self.d.mocap_quat[self.mocap] = quat
