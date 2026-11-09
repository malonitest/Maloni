import * as T from 'three';
import { createConcierge } from './concierge';
import { appearance as look, atmospheres, type Ambience } from './appearance';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import './style.css';
import { lightGallery, bakeVehicleReflections, createPresentationPipeline } from './lighting';
import { createCameraRig } from './camera';
import { createInterior } from './interior';
import {MotionBuffer,type SimulationState} from './motion';
const status = document.querySelector<HTMLParagraphElement>('#status')!;
const fail = (message: string) => { status.textContent = message + ' Use the Simulation camera button.'; };
document.querySelector('#fallback')!.addEventListener('click', () => { if (parent === window)
    location.href = '/';
else
    parent.postMessage({ type: 'showroom-camera' }, location.origin); });
async function main() {
    const renderer = new T.WebGLRenderer({ antialias: true });
    renderer.outputColorSpace = T.SRGBColorSpace;
    renderer.toneMapping = T.NeutralToneMapping;
    renderer.toneMappingExposure = look.exposure;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = T.PCFShadowMap;
    renderer.shadowMap.autoUpdate = false;
    renderer.shadowMap.needsUpdate = true;
    document.querySelector('#viewport')!.append(renderer.domElement);
    let lost = false;
    renderer.domElement.addEventListener('webglcontextlost', e => { e.preventDefault(); lost = true; fail('The graphics context was lost.'); });
    renderer.domElement.addEventListener('webglcontextrestored', () => location.reload());
    const scene = new T.Scene();
    scene.background = new T.Color('#bac7cd');
    scene.fog = new T.Fog('#bac7cd', 25, 65);
    const camera = new T.PerspectiveCamera(42, 1, .1, 100);
    const controls = new OrbitControls(camera, renderer.domElement);
    let renderNeeded = true;
    controls.addEventListener('change', () => { renderNeeded = true; });
    controls.enableDamping = false;
    controls.minDistance = 2;
    controls.maxDistance = 26;
    controls.maxPolarAngle = Math.PI / 2 - .035;
    controls.enablePan = false;
    // All project geometry is authored in MuJoCo Z-up. One root maps it to Three Y-up.
    const root = new T.Group();
    root.rotation.x = -Math.PI / 2;
    scene.add(root);
    const layout = await fetch('/graphics/layout.json').then(r => { if (!r.ok)
        throw Error('The layout is unavailable'); return r.json(); });
    const [cx, cy] = layout.car.position;
    const interior = await createInterior(root, layout.vehicles, layout.scene);
    const lighting = lightGallery(scene), key = lighting.sun;
    let ambience: Ambience = 'day';
    renderer.domElement.dataset.ambience = ambience;
    renderer.domElement.dataset.humanoid = JSON.stringify(interior.robot ? new T.Box3().setFromObject(interior.robot).applyMatrix4(root.matrixWorld.clone().invert()) : null);
    renderer.domElement.dataset.receptionFacing = JSON.stringify({ customer: new T.Vector3(0, -1, 0).transformDirection(interior.customer.matrixWorld).toArray(), humanoid: interior.robot ? new T.Vector3(1, 0, 0).transformDirection(interior.robot.matrixWorld).toArray() : null });
    renderer.domElement.dataset.customer = JSON.stringify(interior.customerEvidence);
    renderer.domElement.dataset.humanoidDetails = JSON.stringify(interior.humanoidDetails);
    renderer.domElement.dataset.floor = JSON.stringify(interior.floorEvidence);
    renderer.domElement.dataset.materials = JSON.stringify({});
    const pmrem = new T.PMREMGenerator(renderer);
    const hdr = await new HDRLoader().loadAsync('/graphics/daylight.hdr');
    const env = pmrem.fromEquirectangular(hdr);
    scene.environment = env.texture;
    scene.environmentIntensity = look.environment;
    scene.background = hdr; scene.backgroundBlurriness = .065; scene.backgroundIntensity = .7;
    pmrem.dispose();
    type Vehicle = {id: string; name: string; url: string; position: number[]; length: number; yaw?: number};
    const vehicles: Vehicle[] = layout.vehicles.map((v: Vehicle) => ({...v, url: v.id === 'tiggo8' ? '/graphics/chery.glb' : v.url}));
    const carModels: T.Object3D[] = [];
    // Load sequentially to limit peak decoder/normal-rebuild memory on integrated graphics.
    for (const vehicle of vehicles) {
        const [cx, cy] = vehicle.position;
    const gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(vehicle.url);
    const car = gltf.scene;
    car.updateMatrixWorld(true);
    const bounds = new T.Box3().setFromObject(car), extent = bounds.getSize(new T.Vector3());
    const rotation = extent.z > extent.x ? new T.Matrix4().set(0, 0, -1, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1) : new T.Matrix4().makeRotationX(Math.PI / 2);
    car.applyMatrix4(rotation);
    car.updateMatrixWorld(true);
    const aligned = new T.Box3().setFromObject(car), center = aligned.getCenter(new T.Vector3());
    center.z = aligned.min.z;
    const scale = vehicle.length / Math.max(extent.x, extent.y, extent.z);
    car.scale.multiplyScalar(scale);
    car.position.set(cx - center.x * scale, cy - center.y * scale, .005 - center.z * scale);
    const placement=new T.Group();placement.position.set(cx,cy,.005);placement.rotation.z=vehicle.yaw||0;
    car.position.sub(placement.position);placement.add(car);root.add(placement);carModels.push(placement);placement.name='scene:'+vehicle.id;interior.sharedObjects[vehicle.id]=placement;
    root.updateMatrixWorld(true);
    const toProject = root.matrixWorld.clone().invert();
    car.traverse(o => {
        if (!(o instanceof T.Mesh))
            return;
        o.castShadow = true;
        o.receiveShadow = true;
        // Match the existing converter's face-color surface classifier in project coordinates.
        let geo = o.geometry.clone();
        if (geo.index)
            geo = geo.toNonIndexed();
        geo = toCreasedNormals(geo, Math.PI / 4);
        const colors = geo.getAttribute('color'), positions = geo.getAttribute('position');
        const roles = ['trim', 'chrome', 'paint', 'rubber', 'glass'];
        const materials = [new T.MeshStandardMaterial({ color: '#30383c', ...look.trim }), new T.MeshStandardMaterial({ color: '#bec7cc', ...look.chrome }), new T.MeshPhysicalMaterial({ color: vehicle.id === 'tiggo4' ? '#722734' : vehicle.id === 'tiggo7' ? '#a4b1b7' : '#264e61', ...look.paint }), new T.MeshStandardMaterial({ color: '#191b1c', ...look.rubber }), new T.MeshPhysicalMaterial({ color: '#202b30', ...look.glass })];
        materials.forEach((material, index) => { material.userData.surfaceRole = roles[index]; });
        if (colors) {
            geo.clearGroups();
            const buckets: number[][] = roles.map(() => []);
            for (let i = 0; i < positions.count; i += 3) {
                const c = [0, 0, 0], p = new T.Vector3();
                for (let j = 0; j < 3; j++) {
                    c[0] += colors.getX(i + j) * 255 / 3;
                    c[1] += colors.getY(i + j) * 255 / 3;
                    c[2] += colors.getZ(i + j) * 255 / 3;
                    p.add(new T.Vector3().fromBufferAttribute(positions, i + j).applyMatrix4(o.matrixWorld).applyMatrix4(toProject));
                }
                p.divideScalar(3);
                let role = 'trim';
                if (Math.max(...c) - Math.min(...c) < 12 && (c[0] + c[1] + c[2]) / 3 > 105)
                    role = 'chrome';
                if (c[2] > c[0] * 1.4 && c[2] > 55)
                    role = 'paint';
                if (Math.max(...c) < 30)
                    role = p.z > .97 && Math.abs(p.y - cy) < .94 ? 'glass' : 'rubber';
                buckets[roles.indexOf(role)].push(i, i + 1, i + 2);
            }
            const indices: number[] = [];
            buckets.forEach((bucket, role) => { geo.addGroup(indices.length, bucket.length, role); for (const index of bucket)
                indices.push(index); });
            geo.setIndex(indices);
            geo.deleteAttribute('color');
            o.geometry = geo;
            o.material = materials;
        } else {
            o.geometry = geo;
            // Some source GLBs use unlit materials; convert them so showroom light affects them.
            const physical = (original: T.Material): T.Material => {
                if (!(original instanceof T.MeshBasicMaterial || original instanceof T.MeshStandardMaterial)) return original;
                // BMW's source has separate named glass/metal surfaces; preserve that separation.
                const paint = original.color.r > .4 && original.color.g < .08 && original.color.b < .1;
                const glass = original.name === 'Material_8';
                const metal = ['Material_1', 'Material_5', 'Material_7', 'Material_15'].includes(original.name);
                const rubber = ['Material_4', 'Material_18'].includes(original.name);
                const role = paint ? 'paint' : glass ? 'glass' : metal ? 'chrome' : rubber ? 'rubber' : 'trim';
                const material = new T.MeshPhysicalMaterial({
                    color: paint ? '#722734' : glass ? '#202b30' : original.color, map: original.map,
                    ...look[role], transparent: false, opacity: 1,
                    alphaTest: original.alphaTest, side: original.side,
                });
                material.name = original.name; material.userData.surfaceRole = role;
                return material;
            };
            o.material = Array.isArray(o.material) ? o.material.map(physical) : physical(o.material);
        }
    });
    }
    const materialEvidence: Record<string, Record<string, number>> = {};
    carModels.forEach((car, index) => {
        const counts: Record<string, number> = {};
        car.traverse(node => { if (node instanceof T.Mesh) {
            const materials = Array.isArray(node.material) ? node.material : [node.material];
            for (const group of node.geometry.groups.length ? node.geometry.groups : [{ count: node.geometry.index?.count || node.geometry.getAttribute('position').count, materialIndex: 0 }]) {
                const material = materials[group.materialIndex || 0];
                const role = material.userData.surfaceRole || 'source'; counts[role] = (counts[role] || 0) + group.count / 3;
            }
        } });
        materialEvidence[vehicles[index].id] = counts;
    });
    renderer.domElement.dataset.materials = JSON.stringify(materialEvidence);
    status.textContent = 'Preparing showroom reflections…';
    root.updateMatrixWorld(true);
    renderer.domElement.dataset.sharedScene=JSON.stringify(Object.fromEntries(Object.entries(interior.sharedObjects).map(([id,node])=>[id,{position:root.worldToLocal(node.getWorldPosition(new T.Vector3())).toArray(),yaw:node.rotation.z}])));
    const reflectionModels = interior.robot ? [...carModels, interior.robot] : carModels;
    const reflectionPositions = interior.robot ? [...vehicles.map(v => v.position), [-2.2, -1.48]] : vehicles.map(v => v.position);
    const reflectionHeights = interior.robot ? [...vehicles.map(() => look.reflection.height), 1.5] : [];
    let reflections: T.WebGLRenderTarget[] = [];
    let reflectionGeneration = 0;
    interior.floorMaterial.envMapIntensity = look.reflection.floorIntensity;
    function refreshReflections() {
        const background = scene.background;
        // A cutaway's flat presentation backdrop must never leak into the indoor probes.
        scene.background = hdr;
        interior.floorMaterial.envMap = null; interior.floorMaterial.needsUpdate = true;
        try {
            const next = bakeVehicleReflections(renderer, scene, reflectionModels, reflectionPositions, reflectionHeights);
            interior.floorMaterial.envMap = next[1].texture;
            reflections.forEach(target => target.dispose()); reflections = next;
            renderer.domElement.dataset.reflectionGeneration = String(++reflectionGeneration);
        } finally {
            scene.background = background;
            renderer.shadowMap.needsUpdate = true;
        }
    }
    refreshReflections();
    const pipeline = createPresentationPipeline(renderer, scene, camera);
    const rig = createCameraRig(camera, controls, value => {
        interior.setCutaway(value);
        scene.background = value ? new T.Color(atmospheres[ambience].cutaway) : hdr;
        renderer.domElement.dataset.facadeVisible = String(interior.facade.visible);
        renderer.domElement.dataset.ceilingVisible = String(interior.ceiling.visible);
    }, renderer.domElement, () => { renderNeeded = true; });
    const selector = document.querySelector<HTMLSelectElement>('#vehicle')!;
    for (const vehicle of vehicles) selector.add(new Option(vehicle.name, vehicle.id));
    selector.value = 'tiggo8';
    selector.addEventListener('change', () => {
        const vehicle = vehicles.find(v => v.id === selector.value)!;
        rig.select(vehicle.position[0], vehicle.position[1]); resize();

    });
    let simulationCamera = false, lastSimulationCamera = '';
    controls.addEventListener('start', () => { simulationCamera = false; });
    let latestSimulation: SimulationState | null = null,renderedSimulation: SimulationState | null = null;
    const motion=new MotionBuffer();let directPoseMode=false;
    const applyCamera = () => {
        if (!simulationCamera || !latestSimulation) return;
        const view = latestSimulation.camera_view || 'showroom_overview';
        lastSimulationCamera = view;
        const native = renderedSimulation?.camera_pose || latestSimulation.camera_pose;
        if (native && (view === 'robot' || view === 'cinematic')) {
            let position = new T.Vector3(...native.position as [number,number,number]).applyMatrix4(root.matrixWorld);
            const q = new T.Quaternion(native.quaternion[1],native.quaternion[2],native.quaternion[3],native.quaternion[0]);
            const target = new T.Vector3(0,0,-1).applyQuaternion(q).add(new T.Vector3(...native.position as [number,number,number])).applyMatrix4(root.matrixWorld);
            if (view === 'robot' && interior.robot) {
                const head = interior.robot.getObjectByName('head_link_visual');
                if (head) { const direction = target.clone().sub(position).normalize(); position = new T.Box3().setFromObject(head).getCenter(new T.Vector3()).addScaledVector(direction,.15); target.copy(position).add(direction); }
            }
            rig.follow(position,target);
        } else {
            const views: Record<string,string> = { showroom_overview:'salon', overview:'overview', entrance_view:'entrance', entrance:'entrance', reception_view:'reception', vehicle_demo_view:'whole', detail_view:'front', furniture_detail:'lounge', customer:'staff' };
            const car = layout.vehicles.find((vehicle: {id: string}) => vehicle.id === (view.startsWith('hero_') ? view.slice(5) : latestSimulation?.selected));
            if (car) { selector.value = car.id; rig.select(car.position[0],car.position[1]); }
            rig.show(view.startsWith('hero_') ? 'front' : views[view] || 'whole');
        }
        renderNeeded = true;
    };
    window.addEventListener('message', event => {
        if (event.source !== parent || event.origin !== location.origin || !event.data || typeof event.data !== 'object') return;
        if (event.data.type === 'showroom-state' && event.data.simulation) {
            const packet={...event.data.simulation,run_id:event.data.runId};
            if (!motion.push(packet,performance.now())) return;
            if(latestSimulation?.run_id!==packet.run_id)renderedSimulation=null;
            latestSimulation=packet;
            // Offscreen iframes may have no animation frames. Consume authoritative poses without drawing.
            if(!sceneVisible()){directPoseMode=true;interior.applySimulation(packet);interior.customerGait.animate(performance.now());renderer.domElement.dataset.customerGait=JSON.stringify(interior.customerGait.evidence());renderNeeded=true;}
            if (simulationCamera && latestSimulation?.camera_view !== lastSimulationCamera) applyCamera();
            renderer.domElement.dataset.backend = event.data.simulation.backend || '';
        }
        if (event.data.type === 'showroom-camera-view') { simulationCamera = true; applyCamera(); }
        if (event.data.type === 'showroom-explore') simulationCamera = false;
    });
    document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { simulationCamera = false; }));
    const concierge = createConcierge(() => selector.value, interior.react, !!interior.robot);
    document.querySelector<HTMLButtonElement>('button[data-view=humanoid]')!.disabled = !interior.robot;
    document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.onclick = () => { rig.show(b.dataset.view!); if (b.dataset.view === 'humanoid') concierge.open(); resize(); });
    rig.show('salon', true);
    function quality() { const high = (document.querySelector('#quality') as HTMLSelectElement).value === 'high'; renderer.setPixelRatio(Math.min(devicePixelRatio, high ? 1.5 : 1)); key.shadow.mapSize.setScalar(high ? 2048 : 1024); key.shadow.radius = high ? 4 : 2; pipeline.configure(high); renderer.domElement.dataset.ambientOcclusion = String(high); key.shadow.map?.dispose(); key.shadow.map = null; renderer.shadowMap.needsUpdate = true; resize(); }
    function resize() {
        const w = innerWidth, h = innerHeight;
        const reserved = Math.min(h * .42, document.querySelector('nav')!.getBoundingClientRect().height + 22);
        const sceneHeight = Math.max(120, Math.floor(h - reserved));
        document.querySelector<HTMLDivElement>('#viewport')!.style.height = sceneHeight + 'px';
        renderer.setSize(w, sceneHeight); pipeline.resize(w, sceneHeight);
        camera.aspect = w / sceneHeight;
        const baseFov = rig.current() === 'salon' ? 54 : rig.current() === 'entrance' ? 49 : 37;
        camera.fov = ['staff', 'humanoid'].includes(rig.current()) ? 37 : Math.min(86, T.MathUtils.radToDeg(2 * Math.atan(Math.tan(T.MathUtils.degToRad(baseFov) / 2) * Math.max(1, 1.75 / camera.aspect))));
        camera.updateProjectionMatrix(); renderNeeded = true;
    }
    window.addEventListener('resize', resize);
    document.querySelector('#quality')!.addEventListener('change', quality);
    document.querySelector<HTMLSelectElement>('#ambience')!.addEventListener('change', event => {
        const measuring = bench;
        cancelMeasurement(); rig.stopKeyboard();
        const next = (event.target as HTMLSelectElement).value as Ambience;
        if (!(next in atmospheres) || next === ambience || lost) return;
        try {
            ambience = next; const settings = atmospheres[ambience];
            lighting.setAmbience(ambience); renderer.toneMappingExposure = settings.exposure;
            scene.backgroundIntensity = settings.background;
            (scene.fog as T.Fog).color.set(settings.fog);
            scene.background = renderer.domElement.dataset.cutaway === 'true' ? new T.Color(settings.cutaway) : hdr;
            refreshReflections();
            renderer.domElement.dataset.ambience = ambience;
            renderNeeded = true;
            status.textContent = (measuring ? 'Benchmark cancelled after a lighting change. ' : '') + readyStatus();
        } catch (error) { console.error(error); fail('Could not prepare the lighting.'); }
    });
    quality();
    new ResizeObserver(resize).observe(document.querySelector('nav')!);
    let visible = true;
    function sceneVisible(){return visible&&!document.hidden&&renderer.domElement.getClientRects().length>0;}
    const rebaseMotion=()=>{motion.clear();if(latestSimulation)motion.push(latestSimulation,performance.now());};
    new IntersectionObserver(e => { const next=e[0].isIntersecting;if(next!==visible)rebaseMotion();visible=next;if(!visible)rig.stopKeyboard(); }).observe(renderer.domElement);
    document.addEventListener('visibilitychange',rebaseMotion);
    let start = 0, frames = 0, last = 0;
    const samples: number[] = [];
    let bench = false;
    let benchmarkMotion = false;
    function cancelMeasurement() {
        if (bench) { bench = false; status.textContent = 'Benchmark cancelled after a view or settings change.'; }
    }
    controls.addEventListener('start', cancelMeasurement);
    document.querySelectorAll('[data-view], #vehicle, #quality, #benchmarkMode').forEach(element => {
        element.addEventListener('click', cancelMeasurement);
        element.addEventListener('change', cancelMeasurement);
    });
    document.querySelector<HTMLButtonElement>('#benchmark')!.onclick = () => { benchmarkMotion = (document.querySelector('#benchmarkMode') as HTMLSelectElement).value === 'motion'; rig.show(rig.current(), true); bench = true; start = performance.now() + 3000; frames = 0; last = 0; samples.length = 0; status.textContent = 'Benchmark: 3 s warm-up and 60 s rendering. Keep the view open.'; };
    function readyStatus() { return interior.robot ? 'Ready · ' + (ambience === 'day' ? 'daylight.' : 'evening gallery.') : 'Ready · The humanoid model is unavailable. You can still explore the showroom.'; }
    status.textContent = readyStatus();
    let renderSamples=0,renderTotal=0,renderReported=0;
    renderer.setAnimationLoop(now => {
        if(lost||!sceneVisible()){rig.stopKeyboard();if(bench){bench=false;fail('Benchmark cancelled because the view was hidden.');}return;}
        if(directPoseMode){rebaseMotion();directPoseMode=false;}
        const frame=motion.sample(now);
        if(frame){renderedSimulation=frame;if(interior.applySimulation(frame))renderNeeded=true;if(simulationCamera&&['robot','cinematic'].includes(frame.camera_view||''))applyCamera();}
        if(interior.customerGait.animate(now))renderNeeded=true;
        renderer.domElement.dataset.customerGait=JSON.stringify(interior.customerGait.evidence());
    if (bench && benchmarkMotion) rig.orbit(now - start); else rig.update(now); if (interior.animateRobot(now)) renderNeeded = true;if (renderNeeded || bench) { const renderStart=performance.now();pipeline.render();renderTotal+=performance.now()-renderStart;renderSamples++;if(now-renderReported>1000){parent.postMessage({type:'showroom-render-metrics',render_ms:renderTotal/renderSamples},location.origin);renderReported=now;renderTotal=0;renderSamples=0;} renderNeeded = false; } if (bench && now >= start) {
        frames++;
        if (last)
            samples.push(now - last);
        last = now;
        if (now - start >= 60000) {
            bench = false;
            if (samples.length < 2) { status.textContent = 'Not enough frames were recorded. Try again in Economy mode.'; return; }
            samples.sort((a, b) => a - b);
            const result = { cameraView: rig.current(), motion: benchmarkMotion, vehicle: selector.value, ambience, fps: frames * 1000 / (now - start), p95FrameMs: samples[Math.floor(samples.length * .95)], viewport: [innerWidth, innerHeight], pixelRatio: renderer.getPixelRatio(), userAgent: navigator.userAgent, quality: (document.querySelector('#quality') as HTMLSelectElement).value };
            status.textContent = `Result: ${result.fps.toFixed(1)} FPS · p95 ${result.p95FrameMs.toFixed(1)} ms`;
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
            a.download = 'showroom-benchmark.json';
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        }
    } });
}
main().catch(e => { console.error(e); fail('Could not load the 3D view: ' + String(e.message || e)); });
