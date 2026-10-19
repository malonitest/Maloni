#!/usr/bin/env python3
"""Local G1 walking simulation, with the policy active from the first step."""
import argparse
import json
import subprocess
import time
import unicodedata
from collections import deque
from pathlib import Path
from threading import Lock

from buddha_task import BuddhaTask

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def camera_world_position(camera):
    az, el = np.radians([camera.azimuth, camera.elevation])
    return camera.lookat + camera.distance*np.array([
        -np.cos(el)*np.cos(az), -np.cos(el)*np.sin(az), -np.sin(el)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--bpm', type=float, default=220, help='Tempo tance (120–260 BPM)')
    parser.add_argument('--dance', action='store_true', help='Spustit taneční režim')
    parser.add_argument('--duration', type=float, default=None)
    parser.add_argument('--task', choices=['buddha', 'none'], default=None)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--forward-speed', type=float, default=0)
    parser.add_argument('--sideways-speed', type=float, default=0)
    parser.add_argument('--turn-speed', type=float, default=0)
    parser.add_argument('--scene', choices=['lab', 'classic'], default='lab')
    args = parser.parse_args()
    if not 120 <= args.bpm <= 260:
        parser.error('--bpm musí být mezi 120 a 260')
    if args.task == 'buddha' and (args.scene != 'lab' or args.dance):
        parser.error('Úkol Buddha vyžaduje laboratoř a vypnutý --dance.')
    task_enabled = args.task == 'buddha' or (args.task is None and args.scene == 'lab' and not args.dance)
    if args.duration is None:
        args.duration = 180 if task_enabled else 10
    cfg = json.loads((HERE / 'policy_config.json').read_text())
    scene_file = ('scene_lab_task.xml' if task_enabled else 'scene_lab.xml') if args.scene == 'lab' else 'scene_29dof.xml'
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'unitree_mujoco/unitree_robots/g1' / scene_file))
    data = mujoco.MjData(model)
    ids = np.array(cfg['joint_ids_map'], dtype=int)
    default = np.array(cfg['default_joint_pos'])
    joint_names = [f'{side}_{part}' for side in ['left','right'] for part in
                   ['hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll']]
    joint_names += ['waist_yaw','waist_roll','waist_pitch']
    joint_names += [f'{side}_{part}' for side in ['left','right'] for part in
                    ['shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw']]
    actuator_ids = np.array([model.actuator(name).id for name in joint_names])
    qadr = model.jnt_qposadr[model.actuator_trnid[actuator_ids, 0]]
    vadr = model.jnt_dofadr[model.actuator_trnid[actuator_ids, 0]]
    stiffness = np.array(cfg['stiffness'])
    damping = np.array(cfg['damping'])
    history = [deque(maxlen=5) for _ in range(6)]
    last_action = np.zeros(29)
    command = np.zeros(3)
    lock = Lock()
    control_requests = deque()
    reset_requested = False
    task = None
    follow_camera = True
    dancing = args.dance
    dance_start = 3.0 if args.dance else 0.0
    mappings = {ord('W'): (.5, 0, 0), ord('S'): (-.3, 0, 0),
                ord('A'): (0, .3, 0), ord('D'): (0, -.3, 0),
                ord('Q'): (0, 0, .6), ord('E'): (0, 0, -.8),
                265: (.5, 0, 0), 264: (-.3, 0, 0),
                263: (0, 0, .6), 262: (0, 0, -.8), 32: (0, 0, 0)}

    def reset():
        nonlocal last_action
        mujoco.mj_resetData(model, data)
        data.qpos[qadr[ids]] = default
        mujoco.mj_forward(model, data)
        for buffer in history:
            buffer.clear()
        last_action = np.zeros(29)

    def on_key(key):
        nonlocal reset_requested, follow_camera, dancing, dance_start
        with lock:
            if task is not None and key == 32:
                control_requests.append("pause")
            elif task is not None and key == ord('B'):
                control_requests.append("resume")
            elif key in mappings and task is None:
                dancing = False
                command[:] = mappings[key]
                print(f'Příkaz: vpřed={command[0]:.2f}, do strany={command[1]:.2f}, otáčení={command[2]:.2f}', flush=True)
            elif key == ord('T') and task is None:
                dancing = not dancing
                dance_start = data.time
                command[:] = 0
                print('Tanec: ' + ('zapnutý' if dancing else 'vypnutý'), flush=True)
            elif key == ord('F'):
                follow_camera = not follow_camera
                print('Sledování robota: ' + ('zapnuto' if follow_camera else 'vypnuto'), flush=True)
            elif key == ord('R'):
                reset_requested = True
                dancing = False
                command[:] = 0

    policy = ROOT / 'unitree_rl_lab/deploy/robots/g1_29dof/config/policy/velocity/v0/exported/policy.onnx'
    process = subprocess.Popen([str(HERE / 'policy_runner'), str(policy)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    viewer = None
    reset()
    if task_enabled:
        default_actuator = np.empty(29)
        default_actuator[ids] = default
        task = BuddhaTask(model, data, actuator_ids, default_actuator, args.seed)
    start_x = float(data.qpos[0])
    start_y = float(data.qpos[1])
    yaw_total = 0.0
    last_yaw = 0.0
    min_height = float(data.qpos[2])
    flight_time = 0.0
    longest_flight = 0.0
    jumps = 0
    foot_bodies = {model.body(name).id for name in (
        "left_ankle_roll_link", "right_ankle_roll_link")}
    print('G1 připraven. Klikni do okna MuJoCo.', flush=True)
    print('Prostředí: ' + ('MALONI Robotics Laboratory' if args.scene == 'lab' else 'klasická scéna') + '. F přepíná sledování robota.', flush=True)
    if task is not None:
        print('Úkol Buddha: mezerník PAUZA, B pokračovat, R nový úkol. Ruční ovládání: --task none.', flush=True)
    else:
        print('W/S pohyb, A/D do stran, Q/E otočení, mezerník STOP, R nový postoj, T tanec.', flush=True)
        print('Pohyb pokračuje do mezerníku nebo dalšího příkazu. Zavřením okna skončíš.', flush=True)
    try:
        if not args.headless:
            from mujoco import viewer as viewer_module
            print('Otevírám grafické okno MuJoCo…', flush=True)
            viewer = viewer_module.launch_passive(model, data, key_callback=on_key, show_left_ui=False, show_right_ui=False)
            print('Grafické okno je připraveno.', flush=True)
            with viewer.lock():
                viewer.cam.distance = 4.4 if task is not None else (4.0 if args.dance else 6.2)
                viewer.cam.azimuth = 55
                viewer.cam.elevation = -12
                viewer.cam.lookat[:] = (0, 0, 1.4)
        deadline = time.monotonic()
        while (data.time < args.duration if args.headless else viewer.is_running()):
            with lock:
                if reset_requested:
                    reset()
                    if task is not None:
                        task.reset()
                        control_requests.clear()
                    reset_requested = False
                while control_requests:
                    request = control_requests.popleft()
                    if task is not None:
                        task.pause() if request == "pause" else task.resume()
                current_command = command.copy()
                camera_following = follow_camera
                dance_time = data.time - dance_start
                dance_active = dancing and dance_time >= 0
            if args.headless and data.time >= 3:
                current_command[:] = (args.forward_speed, args.sideways_speed, args.turn_speed)
            if dance_active:
                musical_beat = dance_time * args.bpm / 60
                phrase = musical_beat % 16
                jump_time = phrase * 60 / args.bpm
                # Rock step, alternating chassés, then a turning flourish.
                step = np.tanh(3 * np.sin(np.pi * musical_beat))
                if phrase < 4:
                    current_command[:] = (.4 * step, 0, 0)
                elif phrase < 10:
                    current_command[:] = (.12, .3 * np.tanh(3 * np.sin(np.pi * musical_beat / 2)), 0)
                else:
                    current_command[:] = (.15, 0, .65 if int(musical_beat / 16) % 2 == 0 else -.8)
                if phrase >= 13.5 or (musical_beat >= 16 and jump_time < .95):
                    current_command[:] = 0
            task_target = None
            if task is not None:
                camera_position = np.array([4., -6., 3.])
                if viewer:
                    with viewer.lock():
                        camera_position = camera_world_position(viewer.cam)
                prior_target = np.empty(29)
                prior_target[ids] = default + .25*last_action
                with lock:
                    current_command, task_target = task.update(prior_target, camera_position)
            rotation = np.empty(9)
            mujoco.mju_quat2Mat(rotation, data.sensor('imu_quat').data)
            joint_offsets = data.qpos[qadr[ids]] - default
            joint_speeds = data.qvel[vadr[ids]] * .05
            observed_action = last_action.copy()
            if task is not None:
                # The walking policy was not trained on the manipulation arm poses.
                # Keep its arm observation at the nominal walking configuration;
                # measured IMU and leg feedback still close the locomotion loop.
                arm_mask = ids >= 15
                joint_offsets[arm_mask] = 0
                joint_speeds[arm_mask] = 0
                observed_action[arm_mask] = 0
            observations = [data.sensor('imu_gyro').data * .2,
                            rotation.reshape(3, 3).T @ np.array([0, 0, -1]),
                            current_command, joint_offsets, joint_speeds, observed_action]
            for buffer, value in zip(history, observations):
                if not buffer:
                    for _ in range(5):
                        buffer.append(value.copy())
                else:
                    buffer.append(value.copy())
            flat = np.concatenate([np.concatenate(buffer) for buffer in history])
            process.stdin.write(' '.join(map(str, flat)) + '\n')
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise RuntimeError('Řadič ONNX se ukončil.')
            last_action = np.fromstring(line, sep=' ')
            if last_action.size != 29 or not np.isfinite(last_action).all():
                raise RuntimeError('Řadič vrátil neplatný příkaz kloubů.')
            target = np.empty(29)
            target[ids] = default + .25 * last_action
            if task_target is not None:
                if task.support_pose is not None or task.paused:
                    target = task_target
                elif task.state in {'carry','table_align','retreat'}:
                    target[15:] = task_target[15:]
                elif task.state in {'search','celebrate'}:
                    target += task_target-prior_target
            if dance_active:
                blend = min(dance_time / 2, 1.0)
                beat = np.sin(np.pi * musical_beat)
                # Opposite arm swings, elbow pumps and shoulder twists on the beat.
                target[[15, 22]] += blend * np.array([.65 * beat - .15, -.65 * beat - .15])
                target[[16, 23]] += blend * np.array([.35 + .12 * beat, -.35 + .12 * beat])
                target[[17, 24]] += blend * np.array([.2 * beat, -.2 * beat])
                target[[18, 25]] += blend * np.array([.35 * (1 + beat), .35 * (1 - beat)])
                target[12] += blend * .16 * beat
                # Alternating knee lifts accent the chassé section.
                if 4 <= phrase < 10:
                    lift = .12 * np.sin(np.pi * (musical_beat % 1)) ** 2 * blend
                    leg = 0 if int(musical_beat) % 2 == 0 else 6
                    target[leg] -= lift
                    target[leg + 3] += 1.4 * lift
                # Keep the physical takeoff timing independent of musical tempo.
                crouch = 0.0
                if musical_beat >= 16:
                    if jump_time < .2625:
                        crouch = .45 * np.sin(np.pi * jump_time / .525)
                    elif jump_time < .375:
                        crouch = -.25
                if musical_beat >= 16 and jump_time < .45:
                    resting = np.empty(29)
                    resting[ids] = default
                    target[:12] = resting[:12]
                target[[0, 6]] -= crouch / 2
                target[[3, 9]] += crouch
                target[[4, 10]] -= crouch / 2
            for _ in range(round(cfg['step_dt'] / model.opt.timestep)):
                gains = stiffness.copy()
                current_damping = damping.copy()
                if task is not None and (task.attached or task.support_pose is not None):
                    gains[15:] = 100
                    current_damping[15:] = 3
                    for wrist in [19,20,21,26,27,28]:
                        gains[wrist] = 25
                        current_damping[wrist] = .4
                data.ctrl[actuator_ids] = gains * (target - data.qpos[qadr]) - current_damping * data.qvel[vadr]
                if task is not None and task.support_pose is not None:
                    data.ctrl[actuator_ids] += data.qfrc_bias[vadr]
                if task is not None:
                    task.support()
                mujoco.mj_step(model, data)
                if dance_active:
                    grounded = any(
                        model.geom_bodyid[c.geom1] in foot_bodies or
                        model.geom_bodyid[c.geom2] in foot_bodies
                        for c in data.contact)
                    if not grounded:
                        flight_time += model.opt.timestep
                    else:
                        if flight_time >= .04:
                            jumps += 1
                        longest_flight = max(longest_flight, flight_time)
                        flight_time = 0.0
            w, x, y, z = data.qpos[3:7]
            yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
            yaw_total += np.arctan2(np.sin(yaw - last_yaw), np.cos(yaw - last_yaw))
            last_yaw = yaw
            min_height = min(min_height, float(data.qpos[2]))
            if args.headless and task is None and data.qpos[2] < .35:
                raise RuntimeError(f'Robot spadl v čase {data.time:.2f} s.')
            if viewer:
                if camera_following:
                    with viewer.lock():
                        viewer.cam.lookat[:] = (data.qpos[0], data.qpos[1], .9 if task is not None else 1.4)
                if task is not None:
                    status = unicodedata.normalize('NFKD', task.status).encode('ascii','ignore').decode()
                    # Installed viewer.set_texts blocks in its native mutex.
                    # A camera-attached standard label uses the supported user
                    # scene instead, keeping the status in the top-left area.
                    with viewer.lock():
                        eye = camera_world_position(viewer.cam)
                        forward = viewer.cam.lookat-eye
                        forward /= np.linalg.norm(forward)
                        right = np.cross(forward, [0.,0.,1.])
                        right /= max(np.linalg.norm(right),1e-8)
                        up = np.cross(right,forward)
                        position = eye+.6*forward-.20*right+.20*up
                        scene = viewer.user_scn
                        mujoco.mjv_initGeom(scene.geoms[0],mujoco.mjtGeom.mjGEOM_LABEL,
                                           np.zeros(3),position,np.eye(3).ravel(),
                                           np.ones(4,dtype=np.float32))
                        scene.geoms[0].label = status
                        scene.ngeom = 1
                viewer.sync()
                deadline += cfg['step_dt']
                delay = deadline - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -.2:
                    deadline = time.monotonic()
            if args.headless and task is not None and task.state in {'done','failed'}:
                break
        if args.headless:
            if task is not None and not task.success:
                raise RuntimeError(task.failure or 'Úkol nebyl dokončen v daném čase.')
            distance = float(data.qpos[0]) - start_x
            if args.forward_speed > 0 and args.turn_speed == 0 and args.duration > 5 and distance < .5:
                raise RuntimeError('Robot nedosáhl očekávaného posunu vpřed.')
            if args.duration > 5 and args.turn_speed == 0 and args.sideways_speed != 0:
                sideways_distance = float(data.qpos[1]) - start_y
                if np.sign(args.sideways_speed) * sideways_distance < .3:
                    raise RuntimeError('Robot nedosáhl očekávaného posunu do strany.')
            if args.duration > 5 and args.turn_speed != 0:
                if np.sign(args.turn_speed) * yaw_total < np.radians(20):
                    raise RuntimeError('Robot nedosáhl očekávaného otočení.')
            if args.dance:
                if args.duration >= 15 and jumps == 0:
                    raise RuntimeError('Tanec neobsahoval ověřený skok.')
                print(f'Rock’n’roll {args.bpm:g} BPM: skoky {jumps}, nejdelší let {longest_flight:.3f} s')
            print(f'PASS: {data.time:.2f} s, vpřed {distance:.2f} m, do strany {data.qpos[1] - start_y:.2f} m, otočení {np.degrees(yaw_total):.1f}°, minimální výška {min_height:.3f} m')
    finally:
        if viewer:
            viewer.close()
        process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
