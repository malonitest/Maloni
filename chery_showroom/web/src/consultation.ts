import * as T from 'three';
import {worldObject,type SharedScene} from './shared_scene';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

type Point = [number, number, number];
type Context = {
    definition: SharedScene; building: T.Group; furnishings: T.Group; facade: T.Group;
    wood: T.Material; brass: T.Material; charcoal: T.Material; fabric: T.Material; stone: T.Material;
    glow: T.Material; foliage: T.Object3D;
    box: (parent: T.Group, size: Point, position: Point, material: T.Material, radius?: number) => T.Mesh;
    contact: (x: number, y: number, w: number, d: number, alpha?: number) => void;
};

/** A wall-side consultation alcove; coordinates stay in project metres, Z-up. */
export function createConsultation(c: Context) {
    const { building, furnishings, wood, brass, charcoal, box } = c;
    const alcove = new T.Group(); alcove.name = 'scene:consultation_bench'; furnishings.add(alcove);
    const bench=worldObject(c.definition,'consultation_bench');
    alcove.position.fromArray(bench.position);alcove.rotation.z=bench.yaw;
    function merged(parent: T.Group, parts: T.BufferGeometry[], material: T.Material) {
        const mesh = new T.Mesh(mergeGeometries(parts)!, material);
        parts.forEach(part => part.dispose()); mesh.receiveShadow = true; mesh.castShadow = true;
        parent.add(mesh); return mesh;
    }
    // Acoustic felt behind slender walnut battens, merged into one draw call.
    box(building, [.04, 6.3, 2.9], [-8.881, -2.1, 1.9], charcoal, .012);
    const battens: T.BufferGeometry[] = [];
    for (let i = 0; i < 64; i++) {
        battens.push(new T.BoxGeometry(.065, .043, 2.88).translate(-8.827, -5.2 + i * .0984, 1.9));
    }
    merged(building, battens, wood);
    for (const y of [-5.26, 1.06]) box(building, [.07, .016, 2.94], [-8.825, y, 1.9], brass, .003);

    // Three separate cushions and four real feet anchor the bench at a 49 cm seat height.
    box(alcove, [.64, 4.8, .04], [-8.43, -2.1, .33], wood, .015);
    for (const x of [-8.66, -8.2]) for (const y of [-3.9, -.3]) box(alcove, [.035, .035, .31], [x, y, .16], brass, .008);
    for (const y of [-3.69, -2.1, -.51]) {
        box(alcove, [.67, 1.56, .14], [-8.43, y, .42], c.fabric, .055);
        box(alcove, [.105, 1.56, .43], [-8.76, y, .735], c.fabric, .045);
        const seam = new T.Mesh(new T.TubeGeometry(new T.LineCurve3(
            new T.Vector3(-8.095, y - .71, .43), new T.Vector3(-8.095, y + .71, .43)), 1, .0018, 6, false), charcoal);
        alcove.add(seam);
    }
    for (const y of [-3.9, -.3]) box(alcove, [.025, .035, .65], [-8.8, y, .55], brass, .006);
    c.contact(-8.43, -2.1, .9, 4.95, .26);

    // Sculptural side tables: weighted bronze base, slender stem, stone top and ceramic pot.
    const base = new T.CylinderGeometry(.21, .23, .016, 32);
    const stem = new T.CylinderGeometry(.016, .022, .46, 20);
    const top = new T.CylinderGeometry(.28, .275, .035, 48);
    const pottery = new T.MeshStandardMaterial({ color: '#d3ccba', roughness: .52 });
    const pot = new T.LatheGeometry([
        new T.Vector2(.045, 0), new T.Vector2(.055, .008), new T.Vector2(.066, .12),
        new T.Vector2(.066, .13), new T.Vector2(.059, .133), new T.Vector2(.048, .014),
    ], 32);
    for (const y of [-4.88, .69]) {
        for (const [geometry, z, material] of [[base, .008, brass], [stem, .235, brass], [top, .4825, c.stone]] as const) {
            const mesh = new T.Mesh(geometry, material); mesh.rotation.x = Math.PI / 2;
            mesh.position.set(-8.43, y, z); mesh.castShadow = true; mesh.receiveShadow = true; alcove.add(mesh);
        }
        const vase = new T.Mesh(pot, pottery); vase.rotation.x = Math.PI / 2; vase.position.set(-8.43, y, .5); alcove.add(vase);
        const leaves = c.foliage.clone(true), bounds = new T.Box3().setFromObject(leaves);
        const center = bounds.getCenter(new T.Vector3()); leaves.position.sub(new T.Vector3(center.x, bounds.min.y, center.z));
        const axis = new T.Group(); axis.rotation.x = Math.PI / 2; axis.scale.setScalar(.35); axis.add(leaves);
        axis.position.set(-8.43, y, .625); alcove.add(axis);
        c.contact(-8.43, y, .65, .65, .25);
    }

    // Original graphic studies complement the central automotive drawing.
    for (const [index, y] of [-4.3, .1].entries()) {
        const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 768;
        const ink = canvas.getContext('2d')!; ink.fillStyle = '#e5e3d8'; ink.fillRect(0, 0, 512, 768);
        ink.fillStyle = '#b5a377'; ink.font = '52px serif'; ink.fillText(`0${index + 1}`, 46, 85);
        ink.fillStyle = '#334b3e'; ink.font = '500 31px sans-serif'; ink.fillText(index ? 'MATERIAL' : 'DESIGN', 46, 140);
        ink.strokeStyle = '#526b5a'; ink.lineWidth = 2;
        for (let line = 0; line < 13; line++) {
            ink.beginPath();
            for (let x = 0; x <= 380; x += 4) {
                const yy = index ? 295 + line * 15 + Math.sin(x / 74 + line * .13) * 27
                    : 447 - Math.sin(x / 380 * Math.PI) * (105 + line * 6) + line * 8;
                if (x) ink.lineTo(65 + x, yy); else ink.moveTo(65 + x, yy);
            }
            ink.stroke();
        }
        ink.fillStyle = '#657367'; ink.font = '20px sans-serif'; ink.fillText('MALONI / AUTOMOTIVE GALLERY', 46, 694);
        const map = new T.CanvasTexture(canvas); map.colorSpace = T.SRGBColorSpace;
        box(building, [.055, 1.1, 1.6], [-8.77, y, 2.25], brass, .008);
        const print = new T.Mesh(new T.PlaneGeometry(1.045, 1.545), new T.MeshBasicMaterial({ map }));
        print.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(
            new T.Vector3(0, 1, 0), new T.Vector3(0, 0, 1), new T.Vector3(1, 0, 0)));
        print.position.set(-8.74, y, 2.25); building.add(print);
    }

    // Wall-attached cornices stay visible in the architectural cutaway.
    const profiles = [new T.BoxGeometry(17.7, .2, .16).translate(0, 6.25, 4.27)];
    const reveals = [new T.BoxGeometry(17.5, .008, .012).translate(0, 6.145, 4.19)];
    for (const x of [-8.8, 8.8]) {
        profiles.push(new T.BoxGeometry(.2, 12.5, .16).translate(x, 0, 4.27));
        reveals.push(new T.BoxGeometry(.008, 12.35, .012).translate(x > 0 ? 8.695 : -8.695, 0, 4.19));
    }
    merged(building, profiles, new T.MeshStandardMaterial({ color: '#dfded6', roughness: .88 }));
    merged(building, reveals, c.glow).castShadow = false;

    // Silkscreen safety dots on the glazing: one instanced mesh, no transmission/shadow pass.
    const dotGeometry = new T.CircleGeometry(.012, 8);
    const dotMaterial = new T.MeshBasicMaterial({ color: '#faf9ed', transparent: true, opacity: .46, depthWrite: false, side: T.DoubleSide });
    const dots = new T.InstancedMesh(dotGeometry, dotMaterial, 300);
    const transform = new T.Object3D(); transform.rotation.x = Math.PI / 2; let dot = 0;
    for (const z of [1.18, 1.48]) for (let i = 0; i < 150; i++) {
        const x = -8.94 + i * .12;
        if ([-9, -6, -3, -1.2, 0, 1.2, 3, 6, 9].some(frame => Math.abs(frame - x) < .055)) continue;
        transform.position.set(x, -6.419, z); transform.updateMatrix(); dots.setMatrixAt(dot++, transform.matrix);
    }
    dots.count = dot; dots.name = 'glazing-safety-dots'; c.facade.add(dots);
    for(const part of alcove.children)part.position.sub(new T.Vector3(-8.43,-2.1,0));

}
