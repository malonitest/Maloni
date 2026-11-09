import * as T from 'three';
import {createCustomerGait,type CustomerFrame} from './customer_gait';
import {worldObject,type SharedScene,type Point} from './shared_scene';
import { createMaloni120 } from './maloni120';
import { refineHumanoid } from './humanoid';
import { createAtelier, wovenRug } from './atelier';
import { appearance as look } from './appearance';
import { architecturalFinish, informationScreen, conciergeScreen } from './finishes';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';

type Vehicle = { id: string; name: string; position: number[]; length: number };

/** Scene coordinates remain metre-based Z-up, shared with the simulation layout. */
export async function createInterior(root: T.Group, vehicles: Vehicle[], definition: SharedScene) {
    const building = new T.Group(), facade = new T.Group(), ceiling = new T.Group(), furnishings = new T.Group();
    building.name = 'building'; facade.name = 'facade'; ceiling.name = 'ceiling'; furnishings.name = 'furnishings';
    root.add(building, facade, ceiling, furnishings);
    const loader = new T.TextureLoader();
    async function photographic(name: string, repeat: [number, number]) {
        const textures = await Promise.all(['color', 'normal', 'roughness'].map(role => loader.loadAsync(`/graphics/materials/${name}-${role}.jpg`)));
        textures.forEach(t => { t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(...repeat); t.anisotropy = 4; });
        textures[0].colorSpace = T.SRGBColorSpace;
        return { map: textures[0], normalMap: textures[1], roughnessMap: textures[2] };
    }
    const [stoneMaps, woodMaps] = await Promise.all([photographic('limestone-floor', [1, 1]), photographic('walnut', [1, 1])]);
    const stone = new T.MeshPhysicalMaterial({ ...stoneMaps, normalScale: new T.Vector2(look.stone.normal, look.stone.normal), roughness: look.stone.roughness, metalness: 0, clearcoat: look.stone.clearcoat, clearcoatRoughness: .4 });
    const wood = new T.MeshStandardMaterial({ ...woodMaps, normalScale: new T.Vector2(look.wood.normal, look.wood.normal), roughness: look.wood.roughness });
    function woodSurface(width: number, height: number, rotation = 0) {
        const material = wood.clone();
        for (const key of ['map', 'normalMap', 'roughnessMap'] as const) {
            const texture = woodMaps[key].clone(); texture.center.set(.5, .5);
            texture.repeat.set(width / 1.6, height / 1.6); texture.rotation = rotation; texture.needsUpdate = true;
            material[key] = texture;
        }
        return material;
    }
    const plaster = new T.MeshStandardMaterial({ ...architecturalFinish('plaster'), roughness: .97, bumpScale: .0012 });
    const counterStone = new T.MeshPhysicalMaterial({ ...architecturalFinish('basalt'), roughness: .5,
        bumpScale: .001, clearcoat: .18, clearcoatRoughness: .35 });
    const charcoal = new T.MeshStandardMaterial({ color: '#242d2d', roughness: .48, metalness: .18 });
    const metal = new T.MeshStandardMaterial({ color: '#a5adb0', roughness: .32, metalness: .85 });
    const brass = new T.MeshStandardMaterial({ color: '#a8946d', roughness: .34, metalness: .85 });
    const porcelain = new T.MeshStandardMaterial({ color: '#eee9dd', roughness: .26 });
    const emitter = new T.MeshBasicMaterial({ color: new T.Color(2.6, 2.45, 2.2), toneMapped: true });
    const glazing = new T.MeshPhysicalMaterial({ color: '#e2eef1', roughness: .09, metalness: .06,
        transparent: true, opacity: .1, clearcoat: .7, depthWrite: false, side: T.DoubleSide, transmission: 0 });
    const box = (parent: T.Group, size: [number, number, number], pos: [number, number, number], material: T.Material, radius = 0) => {
        const geometry = radius ? new RoundedBoxGeometry(...size, 3, radius) : new T.BoxGeometry(...size);
        const mesh = new T.Mesh(geometry, material); mesh.position.set(...pos); mesh.receiveShadow = true;
        // Opaque architecture casts sunlight, glass never becomes a solid shadow blocker.
        mesh.castShadow = !material.transparent; parent.add(mesh); return mesh;
    };
    const object = (id: string) => worldObject(definition,id);
    const sharedObjects: Record<string,T.Object3D> = {};
    function objectBox(parent: T.Group,id: string,material: T.Material,radius=0) {
        const value=object(id),mesh=box(parent,value.size!,value.position,material,radius);
        mesh.rotation.z=value.yaw;mesh.name='scene:'+id;sharedObjects[id]=mesh;return mesh;
    }
    function objectGroup(parent: T.Group,id: string) {
        const value=object(id),group=new T.Group();group.name='scene:'+id;
        group.position.fromArray(value.position);group.rotation.z=value.yaw;parent.add(group);sharedObjects[id]=group;return group;
    }
    function label(parent: T.Group, title: string, subtitle: string, w: number, h: number, pos: [number, number, number], dark = false, ink?: string) {
        const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 256;
        const ctx = canvas.getContext('2d')!;
        if (dark) { ctx.fillStyle = '#242d2d'; ctx.fillRect(0, 0, 1024, 256); }
        ctx.textAlign = 'center'; ctx.fillStyle = ink || (dark ? '#f7f4ea' : '#303b38');
        ctx.font = '500 62px sans-serif'; ctx.fillText(title, 512, 112);
        ctx.fillStyle = ink || (dark ? '#becac5' : '#737e77'); ctx.font = '29px sans-serif'; ctx.fillText(subtitle, 512, 181);
        const map = new T.CanvasTexture(canvas); map.colorSpace = T.SRGBColorSpace;
        const mesh = new T.Mesh(new T.PlaneGeometry(w, h), new T.MeshBasicMaterial({ map, transparent: !dark, depthWrite: false }));
        mesh.rotation.x = Math.PI / 2; mesh.position.set(...pos); parent.add(mesh); return mesh;
    }
    const floorAO = document.createElement('canvas'); floorAO.width = 1024; floorAO.height = 740;
    const floorCtx = floorAO.getContext('2d')!; const pixels = floorCtx.createImageData(1024, 740);
    for (let py = 0; py < 740; py++) for (let px = 0; px < 1024; px++) {
        const x = px / 1024 * 18 - 9, y = 6.5 - py / 740 * 13;
        const distance = Math.min(9 - Math.abs(x), 6.5 - y);
        const value = 255 * (1 - .19 * Math.exp(-Math.max(0, distance) / .22));
        const index = (py * 1024 + px) * 4; pixels.data.set([value, value, value, 255], index);
    }
    floorCtx.putImageData(pixels, 0, 0);
    function floorContact(x: number, y: number, w: number, d: number, alpha = .24) {
        floorCtx.save(); floorCtx.translate((x + 9) / 18 * 1024, (6.5 - y) / 13 * 740);
        floorCtx.scale(w / 18 * 1024 / 2, d / 13 * 740 / 2);
        const gradient = floorCtx.createRadialGradient(0, 0, .1, 0, 0, 1);
        gradient.addColorStop(0, `rgba(0,0,0,${alpha})`); gradient.addColorStop(.65, `rgba(0,0,0,${alpha * .6})`); gradient.addColorStop(1, 'rgba(0,0,0,0)');
        floorCtx.fillStyle = gradient; floorCtx.fillRect(-1, -1, 2, 2); floorCtx.restore();
    }
    const floorMap = new T.CanvasTexture(floorAO); floorMap.colorSpace = T.NoColorSpace; floorMap.channel = 1;
    stone.aoMap = floorMap; stone.aoMapIntensity = .35;
    // One mesh/draw call for all 234 metre-square slabs. UV1 keeps contact AO in world space.
    const positions: number[] = [], normals: number[] = [], uv: number[] = [], uv1: number[] = [];
    for (let row = 0; row < 13; row++) for (let col = 0; col < 18; col++) {
        const variant = ((col * 73856093) ^ (row * 19349663)) >>> 0;
        const index = variant % 16, rotation = (variant >>> 4) % 4;
        const corners = [[0, 0], [1, 0], [1, 1], [0, 1]];
        for (const corner of [0, 1, 2, 0, 2, 3]) {
            const [dx, dy] = corners[corner], [u, v] = corners[(corner + rotation) % 4];
            const x = -9 + col + .0015 + dx * .997, y = -6.5 + row + .0015 + dy * .997;
            positions.push(x, y, 0); normals.push(0, 0, 1);
            uv.push((index % 4) / 4 + (2 + u * 508) / 2048, (3 - Math.floor(index / 4)) / 4 + (2 + v * 508) / 2048);
            uv1.push((x + 9) / 18, (y + 6.5) / 13);
        }
    }
    const floorGeometry = new T.BufferGeometry();
    floorGeometry.setAttribute('position', new T.Float32BufferAttribute(positions, 3));
    floorGeometry.setAttribute('normal', new T.Float32BufferAttribute(normals, 3));
    floorGeometry.setAttribute('uv', new T.Float32BufferAttribute(uv, 2));
    floorGeometry.setAttribute('uv1', new T.Float32BufferAttribute(uv1, 2));
    const floor = new T.Mesh(floorGeometry, stone); floor.name = 'metre-slab-floor'; floor.receiveShadow = true; building.add(floor);
    const grout = new T.Mesh(new T.PlaneGeometry(18, 13), new T.MeshStandardMaterial({ color: '#aaa9a1', roughness: 1 }));
    grout.position.z = -.002; grout.receiveShadow = true; building.add(grout);
    const wallAO = document.createElement('canvas'); wallAO.width = 64; wallAO.height = 256;
    const wallCtx = wallAO.getContext('2d')!; const wallGradient = wallCtx.createLinearGradient(0, 0, 0, 256);
    wallGradient.addColorStop(0, '#e5e5e5'); wallGradient.addColorStop(.08, '#ffffff'); wallGradient.addColorStop(.85, '#ffffff'); wallGradient.addColorStop(1, '#b7b7b7');
    wallCtx.fillStyle = wallGradient; wallCtx.fillRect(0, 0, 64, 256);
    const wallMap = new T.CanvasTexture(wallAO); const wallMat = plaster.clone(); wallMat.aoMap = wallMap;
    function wall(width: number, pos: T.Vector3, horizontal: T.Vector3, normal: T.Vector3) {
        const finish = wallMat.clone();
        for (const key of ['map', 'bumpMap', 'roughnessMap'] as const) {
            finish[key] = plaster[key]!.clone(); finish[key]!.repeat.set(width / 2, 2.5); finish[key]!.needsUpdate = true;
        }
        const mesh = new T.Mesh(new T.PlaneGeometry(width, 5), finish);
        mesh.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(horizontal, new T.Vector3(0, 0, 1), normal));
        mesh.position.copy(pos); mesh.receiveShadow = true; building.add(mesh);
    }
    objectBox(building,'back_wall',plaster);
    wall(18, new T.Vector3(0, 6.415, 2.5), new T.Vector3(1, 0, 0), new T.Vector3(0, -1, 0));
    for (const id of ['left_wall','right_wall']) {
        const x=object(id).position[0];objectBox(building,id,plaster);
        wall(13, new T.Vector3(x > 0 ? 8.915 : -8.915, 0, 2.5), new T.Vector3(0, x > 0 ? -1 : 1, 0), new T.Vector3(x > 0 ? -1 : 1, 0, 0));
        box(building, [.045, 13, .09], [x > 0 ? 8.86 : -8.86, 0, .045], charcoal);
    }
    box(building, [18, .045, .09], [0, 6.36, .045], charcoal);
    const font = await new FontLoader().loadAsync('/graphics/signage-font.json');
    const lettering = new TextGeometry('MALONI', { font, size: .31, depth: .018, curveSegments: 6, bevelEnabled: true, bevelSize: .002, bevelThickness: .002, bevelSegments: 1 });
    lettering.computeBoundingBox(); const textWidth = lettering.boundingBox!.max.x - lettering.boundingBox!.min.x;
    const logo = new T.Mesh(lettering, brass); logo.rotation.x = Math.PI / 2; logo.position.set(-textWidth / 2, 6.29, 3.7); logo.castShadow = true; building.add(logo);
    label(building, '', 'AUTOMOTIVE / SHOWROOM', 2.7, .5, [0, 6.30, 3.48]);
    const panelMaps = await photographic('limestone-wall', [4.6 / 1.4, 2.8 / 1.4]);
    const wallStone = new T.MeshStandardMaterial({ ...panelMaps, roughness: .9, normalScale: new T.Vector2(.025, .025) });
    const joint = new T.MeshStandardMaterial({ color: '#a7a89f', roughness: .94 });
    const inlay = new T.MeshStandardMaterial({ color: '#b2a080', roughness: .5, metalness: .72 });
    const roundedOutline = (w: number, h: number, r: number) => {
        const shape = new T.Shape();
        shape.moveTo(-w / 2 + r, -h / 2); shape.lineTo(w / 2 - r, -h / 2);
        shape.absarc(w / 2 - r, -h / 2 + r, r, -Math.PI / 2, 0, false);
        shape.lineTo(w / 2, h / 2 - r); shape.absarc(w / 2 - r, h / 2 - r, r, 0, Math.PI / 2, false);
        shape.lineTo(-w / 2 + r, h / 2); shape.absarc(-w / 2 + r, h / 2 - r, r, Math.PI / 2, Math.PI, false);
        shape.lineTo(-w / 2, -h / 2 + r); shape.absarc(-w / 2 + r, -h / 2 + r, r, Math.PI, Math.PI * 1.5, false);
        shape.closePath(); return shape;
    };
    for (const [vehicleIndex, vehicle] of vehicles.entries()) {
        const [x, y] = vehicle.position;
        // A flush 9 mm brass inlay identifies each bay without raising the car or floor.
        const outline = roundedOutline(vehicle.length + .25, 2.65, .2);
        outline.holes.push(new T.Path(roundedOutline(vehicle.length + .232, 2.632, .191).getPoints(8).reverse()));
        const bay = new T.Mesh(new T.ShapeGeometry(outline, 8), inlay);
        bay.position.set(x, y, .002); bay.receiveShadow = true; building.add(bay);
        box(building, [4.6, .1, 2.8], [x + .2, 6.32, 1.75], wallStone, .012);
        for (const dx of [-.77, .77]) box(building, [.004, .003, 2.77], [x + .2 + dx, 6.264, 1.75], joint).castShadow = false;
        box(building, [4.57, .003, .004], [x + .2, 6.264, 1.75], joint).castShadow = false;
        box(building, [4.4, .04, .025], [x + .2, 6.24, .3], charcoal);
        box(building, [4.4, .02, .012], [x + .2, 6.22, .34], emitter);
        for (let dx = -2.55; dx < -1.9; dx += .095) box(building, [.055, .085, 3.0], [x + dx, 6.22, 1.7], wood, .004);
        label(building, vehicle.name.replace(/ 20\d\d$/, '').toUpperCase(), 'COLLECTION / ' + vehicle.name.slice(-4), 2.8, .65, [x + .4, 6.245, 2.76]);
        floorContact(x, y, vehicle.length + .15, 2.35, look.contacts.vehicle);
        for (const dx of [-vehicle.length * .3, vehicle.length * .3]) for (const dy of [-.77, .77]) floorContact(x + dx, y + dy, .46, .35, look.contacts.wheel);
        const sx = x + (x > 3 ? -2.65 : 2.65), sy = y + .9;
        box(furnishings, [.52, .42, .04], [sx, sy, .022], charcoal, .015);
        box(furnishings, [.035, .055, .93], [sx, sy, .5], metal, .008);
        const sign = new T.Group(); sign.position.set(sx, sy, 1.1); sign.rotation.x = -.17; furnishings.add(sign);
        box(sign, [.66, .045, .44], [0, 0, 0], charcoal, .02);
        const brochure = informationScreen(vehicle.name, vehicleIndex);
        const face = new T.Mesh(new T.PlaneGeometry(.615, .395), new T.MeshStandardMaterial({
            map: brochure, roughness: .42, emissive: '#ffffff', emissiveMap: brochure, emissiveIntensity: .22,
        }));
        face.rotation.x = Math.PI / 2; face.position.y = -.023; sign.add(face);
        floorContact(sx, sy, .7, .6, .2);
    }
    // Closed roof around a glazed central atrium; all visible lamps belong to actual fixtures.
    box(ceiling, [18, 3.2, .15], [0, -4.9, 4.94], plaster);
    box(ceiling, [18, 2, .15], [0, 5.5, 4.94], plaster);
    for (const x of [-6.5, 6.5]) box(ceiling, [5, 7.8, .15], [x, .6, 4.94], plaster);
    for (const x of [-4, -2, 0, 2, 4]) box(ceiling, [.065, 7.8, .12], [x, .6, 4.88], metal);
    for (const y of [-3.3, -1.35, .6, 2.55, 4.5]) box(ceiling, [8, .065, .12], [0, y, 4.88], metal);
    box(ceiling, [8, 7.8, .015], [0, .6, 4.96], glazing);
    for (const vehicle of vehicles) for (const dx of [-1.25, 1.25]) {
        box(ceiling, [.72, 3.5, .075], [vehicle.position[0] + dx, vehicle.position[1], 4.7], charcoal, .015);
        box(ceiling, [.64, 3.42, .025], [vehicle.position[0] + dx, vehicle.position[1], look.fixtures.vehicle.height + .04], emitter, .01);
    }
    box(ceiling, [3.5, 1.6, .07], [-2.2, -2.2, 4.65], charcoal, .025);
    box(ceiling, [3.4, 1.5, .02], [-2.2, -2.2, 4.6], emitter, .02);
    for (const y of [-5.2, -.8, 4.5]) box(ceiling, [18, .09, .15], [0, y, 4.8], charcoal);
    // Slim structural columns, low-iron glazing and real door hardware.
    for (const x of [-9, -6, -3, -1.2, 1.2, 3, 6, 9]) {
        box(facade, [.065, .14, 4.8], [x, -6.43, 2.4], charcoal, .006);
        box(facade, [.09, .17, .055], [x, -6.43, .0275], metal, .004);
        box(facade, [.09, .17, .055], [x, -6.43, 4.77], metal, .004);
    }
    box(facade, [2.4, .25, .016], [0, -6.4, .008], metal, .004);
    for (const z of [.07, 3, 4.8]) box(facade, [18, .14, .065], [0, -6.43, z], charcoal);
    for (const id of Object.keys(definition.objects).filter(id=>id.startsWith('front_panel_'))) objectBox(facade,id,glazing);
    objectBox(facade,'front_upper',glazing);
    for (const id of ['front_door_0','front_door_1']) {
        const x=object(id).position[0];objectBox(facade,id,glazing);
        box(facade, [.035, .12, 2.88], [x < 0 ? -.022 : .022, -6.43, 1.53], metal);
        box(facade, [.027, .055, .55], [x < 0 ? -.15 : .15, -6.32, 1.35], metal, .012);
    }
    box(facade, [24, 4.3, .1], [0, -8.65, -.06], new T.MeshStandardMaterial({ color: '#a7aaa5', roughness: .85 }));
    const counter=object('reception_counter'),reception=objectGroup(furnishings,'reception_counter');
    function piece(id: string,material: T.Material,radius: number) {
        const item=counter.parts![id],size: Point=item.size || [counter.size![0],counter.size![1],item.height!];
        return box(reception,size,item.offset,material,radius);
    }
    // Reception: separate concierge counter and lower staff work surface.
    piece('body',porcelain,.12);
    piece('front',woodSurface(2.67,.77,Math.PI/2),.025);
    piece('trim',brass,.008);
    piece('top',counterStone,.09);
    objectBox(furnishings,'staff_desk',woodSurface(2.65,.45),.025);
    label(reception, 'MALONI', 'WELCOME', 1.1, .3, [0.0, -0.497, 0.07], false, '#e7dec3');
    floorContact(counter.position[0],counter.position[1],3.15,1.28,.3);
    const monitor = box(reception, [.48, .045, .3], [0.85, 0.23, 0.72], charcoal, .018);
    box(reception, [.035, .1, .18], [0.85, 0.23, 0.54], metal, .01);
    box(reception, [.23, .15, .015], [0.85, 0.23, 0.55], metal, .01);
    const screen = label(reception, 'MALONI', 'CONCIERGE', .43, .25, [0.85, 0.256, 0.72], true);
    const placeholderMap = (screen.material as T.MeshBasicMaterial).map;
    (screen.material as T.MeshBasicMaterial).map = conciergeScreen(); placeholderMap?.dispose();
    screen.rotation.x = -Math.PI / 2;
    box(reception, [.4, .16, .014], [0.85, 0.5, 0.326], charcoal, .01);
    box(reception, [.18, .25, .008], [-0.75, 0.0, 0.55], porcelain);
    box(reception, [.16, .22, .005], [-0.75, 0.0, 0.557], new T.MeshStandardMaterial({ color: '#bfc3bd', roughness: .9 }));
    const cup = new T.Mesh(new T.CylinderGeometry(.037, .033, .085, 24, 1, true), porcelain);
    cup.rotation.x = Math.PI / 2; cup.position.set(-1.05,.15,.59); cup.castShadow = true; reception.add(cup);
    const coffee = new T.Mesh(new T.CircleGeometry(.032, 24), new T.MeshStandardMaterial({ color: '#24160e', roughness: .16 }));
    coffee.position.set(-1.05,.15,.627); reception.add(coffee);
    const handle = new T.Mesh(new T.TorusGeometry(.024, .006, 8, 20), porcelain);
    handle.rotation.x = Math.PI / 2; handle.position.set(-.997,.15,.59); reception.add(handle);
    // Leather consultation seating sits on a woven rug rather than floating in empty floor space.
    const rugMaterial = wovenRug();
    box(furnishings, [3.65, 2.25, .012], [3.3, -3.3, .006], rugMaterial, .005);
    const table=objectGroup(furnishings,'coffee_table');
    box(table, object('coffee_table').size!, [0,0,0], woodSurface(.97, .74), .07);
    box(table, [.07, .07, .47], [-0.3, -0.2, -0.265], charcoal, .01);
    box(table, [.07, .07, .47], [0.3, 0.2, -0.265], charcoal, .01);
    box(table, [.18, .25, .012], [0.0, 0.0, 0.03], porcelain);
    const gltf = new GLTFLoader();
    const [chair, plant, employee, humanoid] = await Promise.all([
        gltf.loadAsync('/graphics/furniture/modern_arm_chair_01.glb'),
        gltf.loadAsync('/graphics/furniture/potted_plant_02.glb'),
        gltf.loadAsync('/graphics/staff/receptionist.glb'),
        gltf.loadAsync('/web/models/g1-reception.glb').catch(() => null),
    ]);
    function place(source: T.Group, x: number, y: number, yaw: number, height?: number, lift = 0) {
        const instance = source.clone(true); const bounds = new T.Box3().setFromObject(instance);
        const center = bounds.getCenter(new T.Vector3()); const size = bounds.getSize(new T.Vector3());
        const scale = height ? height / size.y : 1;
        instance.scale.multiplyScalar(scale); instance.position.set(-center.x * scale, -bounds.min.y * scale, -center.z * scale);
        instance.traverse(node => { if (node instanceof T.Mesh) { node.receiveShadow = true; node.castShadow = true; } });
        const axis = new T.Group(); axis.rotation.x = Math.PI / 2; axis.add(instance);
        const placement = new T.Group(); placement.rotation.z = yaw; placement.position.set(x, y, lift); placement.add(axis); furnishings.add(placement);
        floorContact(x, y, size.x * scale * 1.15, size.z * scale * 1.15, look.contacts.furnishing);
        return placement;
    }
    for (const id of ['left_lounge_chair','right_lounge_chair','reception_chair']) {
        const value=object(id),model=place(chair.scene,value.position[0],value.position[1],value.yaw,undefined,value.position[2]);
        model.name='scene:'+id;sharedObjects[id]=model;
    }
    for (const vehicle of vehicles) for (const dx of [-2.55, 2.1]) place(plant.scene, T.MathUtils.clamp(vehicle.position[0] + dx, -8.35, 8.35), 5.72, dx);
    place(plant.scene, -7.45, -5.4, .35, 1.1);
    place(plant.scene, 7.6, -5.25, -.35, 1.1);
    // The supplied MakeHuman eye mesh has a corneal shell mapped to the atlas' blue
    // utility corner. Treat that shell as transparent rather than an opaque blue eye.
    employee.scene.traverse(node => {
        if (!(node instanceof T.Mesh) || Array.isArray(node.material) || node.material.name !== 'receptionist eyes') return;
        const original = node.material as T.MeshStandardMaterial;
        const iris = original.clone(); iris.roughness = .32; iris.envMapIntensity = .25;
        const cornea = new T.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .035,
            depthWrite: false, roughness: .2, metalness: 0, clearcoat: 1, envMapIntensity: .25 });
        const geometry = node.geometry.index ? node.geometry.toNonIndexed() : node.geometry.clone();
        const uv = geometry.getAttribute('uv'); const buckets: number[][] = [[], []];
        for (let i = 0; i < uv.count; i += 3) {
            const u = (uv.getX(i) + uv.getX(i+1) + uv.getX(i+2))/3;
            const v = (uv.getY(i) + uv.getY(i+1) + uv.getY(i+2))/3;
            buckets[u > .85 && v > .85 ? 1 : 0].push(i, i+1, i+2);
        }
        geometry.clearGroups(); const indices: number[] = [];
        buckets.forEach((bucket, material) => { geometry.addGroup(indices.length, bucket.length, material); for (const index of bucket) indices.push(index); });
        geometry.setIndex(indices); node.geometry = geometry; node.material = [iris, cornea];
    });
    const customerPose=object('customer_reception');
    const customer = place(employee.scene,customerPose.position[0],customerPose.position[1],customerPose.yaw,1.68);
    const customerGait=createCustomerGait(customer);
    const maloni = createMaloni120();
    const humanoidDetails = maloni.evidence;
    const robotPose=object('robot_reception');
    if (humanoid) refineHumanoid(humanoid.scene);
    const g1 = humanoid ? place(humanoid.scene,robotPose.position[0],robotPose.position[1],robotPose.yaw,1.68) : null;
    if (g1) {g1.name='g1-reception-assistant';g1.visible=false;}
    let robot = maloni.robot;
    furnishings.add(robot);
    maloni.update(robotPose.position[0],robotPose.position[1],robotPose.yaw);
    const torso = robot?.getObjectByName('torso_link');
    const restTorso = torso?.quaternion.clone();
    let reactingUntil = 0;
    let nativeState = false;
    const customerRestPosition = customer.position.clone(), customerRestQuaternion = customer.quaternion.clone();
    const applySimulation = (state: CustomerFrame & { robot_transforms?: Record<string, number[]>; sim_time?: number; robot_model?: string; robot_joints?: Record<string,number>; wheel_angles?: number[] }) => {
        if(state.customer&&!state.customer.hidden){customer.position.x=state.customer.position[0];customer.position.y=state.customer.position[1];customer.rotation.z=state.customer.heading+Math.PI/2;}
        else{customer.position.copy(customerRestPosition);customer.quaternion.copy(customerRestQuaternion);}
        customerGait.update(state);
        const poses = state.robot_transforms;
        if (!robot || !poses?.pelvis) return !!state.customer;
        nativeState = true;
        const useG1=state.robot_model==='g1' && !!g1;
        maloni.robot.visible=!useG1;
        if(g1)g1.visible=useG1;
        robot=useG1?g1!:maloni.robot;
        const base = poses.pelvis;
        const yaw = Math.atan2(2*(base[3]*base[6]+base[4]*base[5]),1-2*(base[5]**2+base[6]**2));
        // Existing navigation supplies planar position only; G1 leg poses never deform this wheeled concept.
        if(!useG1)maloni.update(base[0],base[1],yaw,state.sim_time,state.robot_joints,state.wheel_angles);
        else {
            robot.position.x=base[0];robot.position.y=base[1];robot.rotation.z=yaw;
            const inverseYaw=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,0,1),-yaw);
            for(const [name,pose] of Object.entries(poses)) {
                const node=robot.getObjectByName(name);if(!node)continue;
                const q=new T.Quaternion(pose[4],pose[5],pose[6],pose[3]);
                if(name==='pelvis'){node.position.set(0,0,pose[2]);node.quaternion.copy(inverseYaw).multiply(q);}
                else {
                    const parent=poses[node.parent?.name||''];if(!parent)continue;
                    const inverse=new T.Quaternion(parent[4],parent[5],parent[6],parent[3]).invert();
                    node.position.set(pose[0]-parent[0],pose[1]-parent[1],pose[2]-parent[2]).applyQuaternion(inverse);
                    node.quaternion.copy(inverse).multiply(q);
                }
            }
        }
        robot.updateMatrixWorld(true); customer.updateMatrixWorld(true);
        return true;
    };
    const react = () => { reactingUntil = performance.now() + 3200; };
    const animateRobot = (now: number) => {
        if (nativeState || !torso || !restTorso) return false;
        if (reactingUntil) {
            const remaining = reactingUntil - now;
            const amount = remaining > 0 ? Math.sin((3200 - remaining) / 220) * .025 * Math.min(1, remaining / 400) : 0;
            torso.quaternion.copy(restTorso).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), amount));
            if (remaining <= 0) reactingUntil = 0;
            return true;
        }
        return false;
    };
    customer.name = 'showroom-customer';
    customer.userData = { role: 'customer', source: 'Innerscene / MakeHuman CC0', height: 1.68, position: [-2.2, -4.05, 0] };
    createAtelier({ definition, building, furnishings, ceiling, facade, wood, metal, brass, charcoal, box,
        foliage: plant.scene.getObjectByName('potted_plant_02_leaves')!, contact: floorContact });
    const benchObject=furnishings.getObjectByName('scene:consultation_bench');if(benchObject)sharedObjects.consultation_bench=benchObject;
    floorMap.needsUpdate = true;
    // AO only darkens indirect light. A cached translucent contact mask also anchors
    // tyres in sunlit areas without another shadow light or per-frame render pass.
    const contactCanvas = document.createElement('canvas'); contactCanvas.width = 1024; contactCanvas.height = 740;
    const contactContext = contactCanvas.getContext('2d')!;
    const contacts = floorCtx.getImageData(0, 0, 1024, 740);
    for (let i = 0; i < contacts.data.length; i += 4) {
        const alpha = 255 - contacts.data[i]; contacts.data.set([0, 0, 0, alpha], i);
    }
    contactContext.putImageData(contacts, 0, 0);
    const contactTexture = new T.CanvasTexture(contactCanvas);
    const contactPlane = new T.Mesh(new T.PlaneGeometry(18, 13), new T.MeshBasicMaterial({
        map: contactTexture, transparent: true, depthWrite: false, toneMapped: false,
        polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
    }));
    contactPlane.name = 'static-contact-shadows'; contactPlane.position.z = .0006; building.add(contactPlane);
    root.updateMatrixWorld(true);
    // Publish measured geometry bounds, not a manually asserted visibility flag.
    const customerBounds = new T.Box3().setFromObject(customer).applyMatrix4(root.matrixWorld.clone().invert());
    const customerEvidence = { bounds: [customerBounds.min.toArray(), customerBounds.max.toArray()], role: customer.userData.role,
        meshCount: 0, texturedMeshes: 0, triangles: 0 };
    customer.traverse(node => { if (node instanceof T.Mesh) {
        customerEvidence.meshCount++;
        const materials = Array.isArray(node.material) ? node.material : [node.material];
        if (materials.some(m => m instanceof T.MeshStandardMaterial && m.map)) customerEvidence.texturedMeshes++;
        customerEvidence.triangles += (node.geometry.index?.count || node.geometry.getAttribute('position').count) / 3;
    } });
    return { sharedObjects, building, facade, ceiling, furnishings, customer, customerEvidence, customerGait, humanoidDetails, get robot(){return robot;}, react, animateRobot, applySimulation, floorMaterial: stone, floorEvidence: { slabs: 234, size: 1, grout: .003, drawCalls: 1 },
        setCutaway: (value: boolean) => { facade.visible = !value; ceiling.visible = !value; } };
}
