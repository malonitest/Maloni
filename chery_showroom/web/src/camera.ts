import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export function createCameraRig(camera: T.PerspectiveCamera, controls: OrbitControls,
    setCutaway: (value: boolean) => void, canvas: HTMLCanvasElement, dirty: () => void) {
    const held = new Set<string>();
    const cameraKeys = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyS', 'KeyA', 'KeyD']);
    let previousFrame = 0;
    const stopKeyboard = () => { held.clear(); previousFrame = 0; };
    canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', '3D showroom — camera controls');
    canvas.setAttribute('aria-describedby', 'camera-help');
    canvas.addEventListener('pointerdown', () => canvas.focus({ preventScroll: true }));
    canvas.addEventListener('keydown', event => {
        if (event.target !== canvas || !cameraKeys.has(event.code) || event.ctrlKey || event.metaKey || event.altKey) return;
        event.preventDefault();
        if (!held.has(event.code)) {
            if (!held.size) previousFrame = performance.now();
            // Reuse manual-input cancellation for preset transitions and benchmarks.
            controls.dispatchEvent({ type: 'start' });
            held.add(event.code); dirty();
        }
    });
    window.addEventListener('keyup', event => { held.delete(event.code); });
    canvas.addEventListener('blur', stopKeyboard);
    window.addEventListener('blur', stopKeyboard);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stopKeyboard(); });
    canvas.addEventListener('webglcontextlost', stopKeyboard);
    let selected = new T.Vector3(6.3, .95, -3.6);
    let active = 'whole';
    let cutaway = false;
    let transition: { start: number; from: T.Vector3; to: T.Vector3; fromTarget: T.Vector3; toTarget: T.Vector3 } | null = null;
    const publish = () => {
        canvas.dataset.view = active;
        canvas.dataset.transitioning = String(transition !== null);
        canvas.dataset.cutaway = String(cutaway);
        canvas.dataset.position = JSON.stringify(camera.position.toArray());
        canvas.dataset.direction = JSON.stringify(camera.getWorldDirection(new T.Vector3()).toArray());
    };
    function clamp() {
        if (!cutaway) {
            camera.position.x = T.MathUtils.clamp(camera.position.x, -8.65, 8.65);
            camera.position.z = T.MathUtils.clamp(camera.position.z, -6.1, 6.1);
            camera.position.y = T.MathUtils.clamp(camera.position.y, .4, 4.45);
        } else camera.position.y = Math.max(.4, camera.position.y);
    }
    function architecture(value: boolean) { cutaway = value; setCutaway(value); }
    function pose(name: string) {
        if (name === 'overview') return { position: new T.Vector3(0, 9.8, 16.3), target: new T.Vector3(0, 1.3, -.8) };
        if (name === 'salon') return { position: new T.Vector3(7.5, 2.6, 5.8), target: new T.Vector3(-.5, 1.5, -3.4) };
        if (name === 'entrance') return { position: new T.Vector3(0, 1.7, 5.7), target: new T.Vector3(0, 1.2, -3.2) };
        if (name === 'reception') return { position: new T.Vector3(-5.8, 1.75, 2.765), target: new T.Vector3(-2.2, .96, 2.765) };
        if (name === 'lounge') return { position: new T.Vector3(3.5, 1.7, 2.3), target: new T.Vector3(8.65, 1.5, 2.3) };
        if (name === 'humanoid') return { position: new T.Vector3(-3.6, 1.65, 3.8), target: new T.Vector3(-2.2, 1.38, 1.48) };
        if (name === 'staff') return { position: new T.Vector3(-2.7, 1.62, 2.0), target: new T.Vector3(-2.2, 1.33, 4.05) };
        // End bays need a diagonal from the aisle, otherwise wall clamping crops the car.
        const aisle = selected.x < -3 ? 1 : -1;
        const offsets: Record<string, number[]> = { whole: [aisle * 5.4, 1.55, 6.0], front: [-4.4, 1.05, 3.0], side: [0, .65, 6.5] };
        const target = selected.clone();
        const position = target.clone().add(new T.Vector3(...(offsets[name] || offsets.whole) as [number, number, number]));
        position.x = T.MathUtils.clamp(position.x, -8.5, 8.5);
        position.z = T.MathUtils.clamp(position.z, -5.9, 5.9);
        return { position, target };
    }
    function show(name: string, immediate = false) {
        stopKeyboard();
        active = name;
        const next = pose(name);
        if (immediate) {
            transition = null; architecture(name === 'overview');
            camera.position.copy(next.position); controls.target.copy(next.target);
            clamp(); controls.update();
        } else {
            // Keep the facade open while crossing between the exterior overview and interior.
            architecture(cutaway || name === 'overview');
            transition = { start: performance.now(), from: camera.position.clone(), to: next.position,
                fromTarget: controls.target.clone(), toTarget: next.target };
        }
        publish(); dirty();
    }
    controls.addEventListener('start', () => {
        transition = null;
        architecture(active === 'overview'); clamp(); controls.update(); publish(); dirty();
    });
    function update(now: number) {
        const dt = previousFrame ? Math.min(.05, Math.max(0, (now - previousFrame) / 1000)) : 0;
        previousFrame = now;
        if (transition) {
            const t = Math.min(1, Math.max(0, (now - transition.start) / 800));
            const eased = t*t*(3-2*t);
            camera.position.lerpVectors(transition.from, transition.to, eased);
            controls.target.lerpVectors(transition.fromTarget, transition.toTarget, eased);
            if (t === 1) { transition = null; architecture(active === 'overview'); }
            dirty();
        }
        if (held.size) {
            // Turn in place around vertical; retain pitch and distance to the orbit target.
            const yaw = Number(held.has('KeyA')) - Number(held.has('KeyD'));
            if (yaw && dt) {
                const heading = controls.target.clone().sub(camera.position);
                heading.applyAxisAngle(new T.Vector3(0, 1, 0), yaw * Math.PI / 3 * dt);
                controls.target.copy(camera.position).add(heading);
                controls.update(); dirty();
            }
            const right = new T.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
            const forward = camera.getWorldDirection(new T.Vector3());
            const movement = new T.Vector3();
            movement.addScaledVector(right, Number(held.has('ArrowRight')) - Number(held.has('ArrowLeft')));
            movement.y += Number(held.has('ArrowUp')) - Number(held.has('ArrowDown'));
            movement.addScaledVector(forward, Number(held.has('KeyW')) - Number(held.has('KeyS')));
            if (movement.lengthSq()) {
                movement.normalize().multiplyScalar(2 * dt);
                const origin = camera.position.clone();
                camera.position.add(movement); clamp();
                // Move target by the accepted displacement so hitting a wall never turns the view.
                controls.target.add(camera.position.clone().sub(origin));
                if (!origin.equals(camera.position)) dirty();
            }
        }
        const before = camera.position.clone();
        clamp();
        if (!before.equals(camera.position)) dirty();
        // Damping is disabled: exact interpolation and immediate pointer cancellation are predictable.
        controls.update(); publish();
    }
    function orbit(now: number) {
        transition = null;
        const base = pose(active);
        controls.target.copy(base.target);
        const delta = base.position.sub(base.target);
        delta.applyAxisAngle(new T.Vector3(0, 1, 0), .22*Math.sin(now/5000));
        camera.position.copy(base.target).add(delta);
        clamp(); controls.update(); publish(); dirty();
    }
    function follow(position: T.Vector3, target: T.Vector3) {
        transition = null; stopKeyboard(); active = 'robot'; architecture(false);
        camera.position.copy(position); controls.target.copy(target); clamp(); controls.update(); publish(); dirty();
    }
    return { show, update, orbit, follow, select: (x: number, y: number) => { selected.set(x, .95, -y); show('whole'); },
        stopKeyboard, current: () => active, moving: () => transition !== null };
}
