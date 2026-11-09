import * as T from 'three';
import {worldObject,type SharedScene} from './shared_scene';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createConsultation } from './consultation';

type Point = [number, number, number];
type Box = (parent: T.Group, size: Point, pos: Point, material: T.Material, radius?: number) => T.Mesh;
type Context = { definition: SharedScene; building: T.Group; furnishings: T.Group; ceiling: T.Group; facade: T.Group;
    wood: T.Material; metal: T.Material; brass: T.Material; charcoal: T.Material; box: Box; foliage: T.Object3D;
    contact: (x: number, y: number, w: number, d: number, alpha?: number) => void };

/** Deterministic woven fibres. Repeated map stays local and uses no external textures. */
export function wovenRug(base: [number, number, number] = [145, 151, 138]) {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    const ctx = canvas.getContext('2d')!;
    const image = ctx.createImageData(256, 256);
    for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
        const fibre = ((x % 8 < 4) === (y % 8 < 4) ? 7 : -7) + ((x * 71 + y * 53) % 9) - 4;
        const index = (y * 256 + x) * 4;
        image.data.set([...base.map(color => color + fibre), 255], index);
    }
    ctx.putImageData(image, 0, 0);
    const map = new T.CanvasTexture(canvas); map.colorSpace = T.SRGBColorSpace;
    map.wrapS = map.wrapT = T.RepeatWrapping; map.repeat.set(10, 6); map.anisotropy = 4;
    const bumpMap = map.clone(); bumpMap.colorSpace = T.NoColorSpace; bumpMap.needsUpdate = true;
    return new T.MeshStandardMaterial({ map, bumpMap, bumpScale: .0015, roughness: 1 });
}

/** Architectural detailing in the same metre-based Z-up coordinates as the showroom. */
export function createAtelier(c: Context) {
    const { building, furnishings, ceiling, facade, wood, brass, charcoal, metal, box } = c;
    const details = new T.Group(); details.name = 'atelier-details'; furnishings.add(details);
    const cream = new T.MeshStandardMaterial({ color: '#dedbd0', roughness: .8 });
    const seam = new T.MeshStandardMaterial({ color: '#474e48', roughness: .65 });
    const glow = new T.MeshBasicMaterial({ color: new T.Color(1.65, 1.42, 1.08), toneMapped: true });
    const paleGlow = new T.MeshBasicMaterial({ color: new T.Color(1.5, 1.52, 1.42), toneMapped: true });
    function cylinder(parent: T.Group, radius: number, height: number, pos: Point, material: T.Material, top = radius) {
        const mesh = new T.Mesh(new T.CylinderGeometry(top, radius, height, 24), material);
        mesh.rotation.x = Math.PI / 2; mesh.position.set(...pos); mesh.castShadow = true; mesh.receiveShadow = true;
        parent.add(mesh); return mesh;
    }
    function coffeeCup(radius: number, height: number, pos: Point) {
        const body = new T.Mesh(new T.CylinderGeometry(radius, radius * .8, height, 24, 1, true), cream);
        body.rotation.x = Math.PI / 2; body.position.set(...pos); details.add(body);
        const rim = new T.Mesh(new T.TorusGeometry(radius, .002, 6, 24), cream);
        rim.position.set(pos[0], pos[1], pos[2] + height / 2); details.add(rim);
        const coffee = new T.Mesh(new T.CircleGeometry(radius - .002, 24),
            new T.MeshStandardMaterial({ color: '#3c2314', roughness: .23 }));
        coffee.position.copy(rim.position); coffee.position.z -= .005; details.add(coffee);
        const handle = new T.Mesh(new T.TorusGeometry(radius * .55, .003, 6, 20), cream);
        handle.rotation.y = Math.PI / 2; handle.position.set(pos[0], pos[1] + radius * 1.2, pos[2]); details.add(handle);
    }
    function sign(title: string, subtitle: string, width: number, height: number, pos: Point, rightWall = false, dark = false) {
        const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 512;
        const ctx = canvas.getContext('2d')!;
        ctx.fillStyle = dark ? '#263831' : '#ebe9de'; ctx.fillRect(0, 0, 1024, 512);
        ctx.strokeStyle = dark ? '#a6b399' : '#8e997f'; ctx.lineWidth = 2; ctx.strokeRect(30, 30, 964, 452);
        ctx.textAlign = 'center'; ctx.fillStyle = dark ? '#eee9d6' : '#334538';
        ctx.font = '500 56px sans-serif'; ctx.fillText(title, 512, 190);
        ctx.fillStyle = dark ? '#bfccb8' : '#65715f'; ctx.font = '28px sans-serif'; ctx.fillText(subtitle, 512, 260);
        ctx.fillStyle = '#b29c66'; ctx.fillRect(452, 310, 120, 3);
        ctx.font = '20px sans-serif'; ctx.fillText('M A L O N I   /   A U T O M O T I V E', 512, 393);
        const map = new T.CanvasTexture(canvas); map.colorSpace = T.SRGBColorSpace;
        const mesh = new T.Mesh(new T.PlaneGeometry(width, height), new T.MeshBasicMaterial({ map }));
        mesh.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(
            rightWall ? new T.Vector3(0, -1, 0) : new T.Vector3(1, 0, 0), new T.Vector3(0, 0, 1),
            rightWall ? new T.Vector3(-1, 0, 0) : new T.Vector3(0, -1, 0)));
        mesh.position.set(...pos); details.add(mesh); return mesh;
    }
    // Reception plinth, floating brass reveal and a working tablet/payment terminal.
    box(details, [2.66, .015, .012], [-2.2, -3.189, .143], glow, .004).castShadow = false;
    box(details, [2.75, .7, .025], [-2.2, -2.7, .035], charcoal, .01);
    const tablet = new T.Group(); tablet.position.set(-1.14, -2.91, 1.125); tablet.rotation.x = -.22; details.add(tablet);
    box(details, [.12, .07, .014], [-1.14, -2.91, 1.103], charcoal, .006);
    box(tablet, [.19, .13, .018], [0, 0, 0], charcoal, .014);
    const display = new T.Mesh(new T.PlaneGeometry(.166, .106), new T.MeshBasicMaterial({ color: '#284b50' }));
    display.position.z = .0095; tablet.add(display);
    for (const y of [-.026, 0, .026]) box(tablet, [.105, .003, .001], [-.01, y, .0105], metal);
    cylinder(details, .012, .13, [-2.76, -2.87, 1.163], brass);
    box(details, [.045, .075, .007], [-2.76, -2.87, 1.1], charcoal, .006);
    // A real keyboard silhouette with shared instanced key geometry, not dozens of draw calls.
    const keys = new T.InstancedMesh(new RoundedBoxGeometry(.020, .018, .004, 1, .002), charcoal, 48);
    keys.name = 'reception-keyboard'; const matrix = new T.Matrix4(); let index = 0;
    for (let row = 0; row < 4; row++) for (let col = 0; col < 12; col++) {
        matrix.makeTranslation(-1.48 + col * .023, -2.25 + row * .025, .887); keys.setMatrixAt(index++, matrix);
    }
    details.add(keys);
    box(details, [.034, .06, .022], [-1.03, -2.17, .879], charcoal, .012);
    const cable = new T.CatmullRomCurve3([new T.Vector3(-1.35, -2.47, 1.1), new T.Vector3(-1.46, -2.37, 1.08),
        new T.Vector3(-1.55, -2.22, .88)]);
    details.add(new T.Mesh(new T.TubeGeometry(cable, 12, .002, 6, false), seam));
    // An acoustic timber island above reception. Merge the battens into one mesh.
    const battens: T.BufferGeometry[] = [];
    for (let i = 0; i < 19; i++) battens.push(new T.BoxGeometry(.045, 3.7, .12).translate(-3.72 + i * .17, -2.65, 4.31));
    const timber = new T.Mesh(mergeGeometries(battens)!, wood); timber.castShadow = true; ceiling.add(timber);
    battens.forEach(geometry => geometry.dispose());
    for (const x of [-3.9, -.5]) box(ceiling, [.025, 3.9, .06], [x, -2.65, 4.39], brass, .004);
    // Thin suspended annular luminaire, with visible cables and no extra shadow lights.
    const ring = new T.Mesh(new T.TorusGeometry(.82, .025, 8, 80), charcoal);
    ring.position.set(3.3, -3.3, 3.1); ceiling.add(ring);
    const diffuser = new T.Mesh(new T.TorusGeometry(.82, .012, 8, 80), paleGlow);
    diffuser.position.set(3.3, -3.3, 3.078); ceiling.add(diffuser);
    for (const angle of [0, Math.PI * 2 / 3, Math.PI * 4 / 3]) {
        const x = 3.3 + Math.cos(angle) * .78, y = -3.3 + Math.sin(angle) * .78;
        cylinder(ceiling, .002, 1.67, [x, y, 3.945], charcoal);
    }
    // Hospitality joinery on the right wall: a coffee machine, cups, storage and a tray.
    box(details, [.5, 2.8, .88], [8.58, -.55, .46], wood, .025);
    box(details, [.55, 2.9, .045], [8.56, -.55, .923], cream, .015);
    box(details, [.03, 2.68, .035], [8.316, -.55, .16], charcoal, .006);
    for (const y of [-1.45, -.55, .35]) {
        box(details, [.006, .005, .66], [8.325, y, .48], seam);
        box(details, [.018, .14, .014], [8.312, y + .14, .65], brass, .006);
    }
    box(details, [.27, .42, .38], [8.48, -.4, 1.14], charcoal, .025);
    box(details, [.008, .29, .13], [8.34, -.4, 1.19], metal, .008);
    box(details, [.004, .16, .038], [8.333, -.4, 1.224], charcoal, .004);
    box(details, [.005, .06, .004], [8.33, -.4, 1.224], paleGlow).castShadow = false;
    box(details, [.095, .27, .012], [8.29, -.4, .956], metal, .006);
    for (const y of [-.48, -.32]) {
        cylinder(details, .009, .055, [8.30, y, 1.095], metal);
        coffeeCup(.026, .06, [8.30, y, .993]);
    }
    box(details, [.29, .52, .02], [8.52, -1.25, .96], charcoal, .012);
    for (const y of [-1.35, -1.14]) {
        cylinder(details, .046, .006, [8.51, y, .975], cream);
        coffeeCup(.032, .065, [8.51, y, 1.01]);
    }
    c.contact(8.58, -.55, .7, 3.0, .24);
    // Long wall niche, floating shelves and warm concealed LED strips.
    box(building, [.055, 3.35, 2.05], [8.875, -.55, 2.03], wood, .015);
    for (const z of [1.36, 2.64]) {
        box(details, [.3, 3.2, .035], [8.69, -.55, z], charcoal, .008);
        box(details, [.008, 3.08, .008], [8.548, -.55, z - .016], glow).castShadow = false;
    }
    sign('THE CUSTOMER LOUNGE', 'Coffee  /  conversation  /  a new journey', 2.75, .9, [8.835, -.55, 2.06], true, true);
    // Real curved paint samples. This wall is a design display, with no unverified product specs.
    box(building, [.055, 2.15, 1.8], [8.875, -4.0, 2.15], charcoal, .018);
    sign('MATERIAL ATELIER', 'Colour. Finish. Your choice.', 1.9, .65, [8.838, -4.0, 2.66], true, true);
    const paintColors = ['#893542', '#d1d2c9', '#315f71', '#34433c', '#a49b88', '#303438'];
    for (let i = 0; i < paintColors.length; i++) {
        const sample = new T.Mesh(new T.SphereGeometry(.115, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2),
            new T.MeshPhysicalMaterial({ color: paintColors[i], metalness: .38, roughness: .23, clearcoat: 1, clearcoatRoughness: .1 }));
        sample.scale.set(1, .38, 1);
        // Hemisphere pole starts on +Y: orient its convex cap towards the room (-X).
        sample.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(-1, 0, 0));
        sample.position.set(8.82, -4.6 + (i % 3) * .6, 2.04 - Math.floor(i / 3) * .44);
        details.add(sample);
        const mount = new T.Mesh(new T.CylinderGeometry(.13, .13, .012, 32), metal);
        mount.rotation.z = Math.PI / 2; mount.position.copy(sample.position); mount.position.x += .006; details.add(mount);
    }
    // Slim framed artwork on the left wall with an original line drawing made in canvas.
    const drawing = document.createElement('canvas'); drawing.width = 1024; drawing.height = 768;
    const pen = drawing.getContext('2d')!; pen.fillStyle = '#e7e6dc'; pen.fillRect(0, 0, 1024, 768);
    pen.strokeStyle = '#3d5148'; pen.lineWidth = 4; pen.beginPath();
    pen.moveTo(130, 435); pen.lineTo(158, 371); pen.lineTo(315, 341); pen.lineTo(411, 252); pen.lineTo(674, 252);
    pen.lineTo(772, 338); pen.lineTo(866, 362); pen.lineTo(891, 434); pen.lineTo(130, 435); pen.stroke();
    for (const x of [285, 751]) { pen.beginPath(); pen.arc(x, 437, 58, 0, Math.PI*2); pen.stroke(); pen.beginPath(); pen.arc(x,437,31,0,Math.PI*2);pen.stroke(); }
    pen.strokeStyle='#a79c7b';pen.lineWidth=2;pen.beginPath();pen.moveTo(160,555);pen.lineTo(865,555);pen.stroke();
    pen.font='500 36px sans-serif';pen.fillStyle='#3d5148';pen.fillText('FORM FOLLOWS THE JOURNEY',130,651);
    const artMap = new T.CanvasTexture(drawing); artMap.colorSpace = T.SRGBColorSpace;
    box(building, [.055, 2.36, 1.8], [-8.77, -2.1, 2.25], brass, .01);
    const art = new T.Mesh(new T.PlaneGeometry(2.28, 1.71), new T.MeshBasicMaterial({ map: artMap }));
    art.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(new T.Vector3(0,1,0),new T.Vector3(0,0,1),new T.Vector3(1,0,0)));
    art.position.set(-8.74,-2.1,2.25); details.add(art);
    createConsultation({ ...c, fabric: wovenRug([184, 177, 160]), stone: cream, glow });
    // Printed journal cover rests on the existing lounge book, without coplanar overlap.
    const cover = document.createElement('canvas'); cover.width = 256; cover.height = 512;
    const ink = cover.getContext('2d')!; ink.fillStyle = '#34473d'; ink.fillRect(0, 0, 256, 512);
    ink.strokeStyle = '#b6a372'; ink.lineWidth = 3; ink.strokeRect(17, 17, 222, 478);
    ink.fillStyle = '#e9e4d1'; ink.textAlign = 'center'; ink.font = '28px serif'; ink.fillText('MALONI', 128, 85);
    ink.font = '16px sans-serif'; ink.fillText('DESIGN JOURNAL', 128, 122);
    ink.strokeStyle = '#b6a372'; ink.lineWidth = 2; ink.beginPath(); ink.arc(128, 290, 68, 0, Math.PI * 2); ink.stroke();
    const coverMap = new T.CanvasTexture(cover); coverMap.colorSpace = T.SRGBColorSpace;
    const journal = new T.Mesh(new T.PlaneGeometry(.174, .244), new T.MeshStandardMaterial({ map: coverMap, roughness: .83 }));
    const tablePose=worldObject(c.definition,'coffee_table');journal.position.set(tablePose.position[0],tablePose.position[1],tablePose.position[2]+.0362); details.add(journal);
    // Approach terrace: a paved central path, planted margins and low architectural bollards.
    const pavers: T.BufferGeometry[] = [];
    for(let row=0;row<4;row++)for(let col=0;col<12;col++)pavers.push(new T.BoxGeometry(.985,.985,.025).translate(-5.5+col,-7.1-row,-.006));
    const paving = new T.Mesh(mergeGeometries(pavers)!, new T.MeshStandardMaterial({ color:'#babdb4',roughness:.9 }));
    pavers.forEach(geometry => geometry.dispose());
    paving.receiveShadow=true;facade.add(paving);
    for(const x of [-4.7,4.7]){
        box(facade,[2.4,.62,.45],[x,-8.25,.19],charcoal,.04);
        box(facade,[2.27,.5,.025],[x,-8.25,.428],new T.MeshStandardMaterial({color:'#31352a',roughness:1}));
        for (let i = 0; i < 3; i++) {
            // Reuse the licensed plant's textured leaves; source geometry/material stay shared.
            const leaves = c.foliage.clone(true);
            const bounds = new T.Box3().setFromObject(leaves), center = bounds.getCenter(new T.Vector3());
            leaves.position.sub(new T.Vector3(center.x, bounds.min.y, center.z));
            const axis = new T.Group(); axis.rotation.x = Math.PI / 2; axis.add(leaves);
            const planting = new T.Group(); planting.rotation.z = i * 1.9 + x;
            planting.position.set(x - .76 + i * .76, -8.25, .442); planting.add(axis); facade.add(planting);
        }
    }
    for(const x of [-2.1,2.1]){
        cylinder(facade,.045,.58,[x,-8.15,.27],charcoal);
        cylinder(facade,.047,.035,[x,-8.15,.54],paleGlow);
    }
}
