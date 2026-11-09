import * as T from 'three';

/** Refine the supplied G1 geometry; optical details follow the original head/torso nodes. */
export function refineHumanoid(model: T.Group) {
    const grain = document.createElement('canvas'); grain.width = grain.height = 128;
    const ctx = grain.getContext('2d')!, image = ctx.createImageData(128, 128);
    for (let y = 0; y < 128; y++) for (let x = 0; x < 128; x++) {
        const v = 192 + ((y * 73 + x * 17) % 19) - 9;
        image.data.set([v, v, v, 255], (y * 128 + x) * 4);
    }
    ctx.putImageData(image, 0, 0);
    const roughnessMap = new T.CanvasTexture(grain); roughnessMap.wrapS = roughnessMap.wrapT = T.RepeatWrapping;
    roughnessMap.repeat.set(4, 4);
    const shell = new T.MeshPhysicalMaterial({ color: '#c8cdd0', metalness: .6, roughness: .48,
        roughnessMap, clearcoat: .28, clearcoatRoughness: .25, envMapIntensity: .85 });
    const joint = new T.MeshStandardMaterial({ color: '#30373d', metalness: .72, roughness: .32, envMapIntensity: .7 });
    const rubber = new T.MeshStandardMaterial({ color: '#161c21', metalness: 0, roughness: .85 });
    const head = new T.MeshPhysicalMaterial({ color: '#303a43', metalness: .4, roughness: .28, clearcoat: .65, clearcoatRoughness: .2 });
    const visor = new T.MeshPhysicalMaterial({ color: '#071820', metalness: .18, roughness: .12, clearcoat: 1, clearcoatRoughness: .12, transmission: 0 });
    const fastener = new T.MeshStandardMaterial({ color: '#79868e', metalness: .92, roughness: .24 });
    const led = new T.MeshStandardMaterial({ color: '#5dabb5', emissive: '#3b929e', emissiveIntensity: .35, roughness: .3 });
    let shells = 0, joints = 0, elastomers = 0;
    model.traverse(node => {
        if (!(node instanceof T.Mesh)) return;
        if (!node.geometry.getAttribute('normal')) node.geometry.computeVertexNormals();
        const source = Array.isArray(node.material) ? node.material[0] : node.material;
        const name = source.name;
        if (/rubber|contour/.test(name)) { node.material = rubber; elastomers++; }
        else if (/head_link/.test(name)) node.material = head;
        else if (/yaw|roll|pitch|waist_support/.test(name)) { node.material = joint; joints++; }
        else if (name !== 'logo_link') {
            node.material = shell; shells++;
            // STL parts have no UVs. Give the finish a metre-based planar projection.
            if (!node.geometry.getAttribute('uv')) {
                node.geometry.computeBoundingBox();
                const bounds = node.geometry.boundingBox!, span = bounds.getSize(new T.Vector3());
                const axes: Array<'x' | 'y' | 'z'> = ['x', 'y', 'z'];
                axes.sort((a, b) => span[b] - span[a]);
                const points = node.geometry.getAttribute('position'), uv: number[] = [];
                const point = new T.Vector3();
                for (let i = 0; i < points.count; i++) {
                    point.fromBufferAttribute(points, i);
                    uv.push((point[axes[0]] - bounds.min[axes[0]]) / .25, (point[axes[1]] - bounds.min[axes[1]]) / .25);
                }
                node.geometry.setAttribute('uv', new T.Float32BufferAttribute(uv, 2));
            }
        }
    });
    model.updateMatrixWorld(true);
    let surfaceDetails = 0;
    function detail(part: T.Object3D, y: number, z: number, radius: number, material: T.Material, ring = false) {
        const bounds = new T.Box3().setFromObject(part);
        const ray = new T.Raycaster(new T.Vector3(bounds.max.x + .15, y, z), new T.Vector3(-1, 0, 0));
        const hit = ray.intersectObject(part, false)[0];
        if (!hit?.face) return;
        const normal = hit.face.normal.clone().applyNormalMatrix(new T.Matrix3().getNormalMatrix(part.matrixWorld));
        const mesh = new T.Mesh(ring ? new T.TorusGeometry(radius, .0012, 6, 24) : new T.CylinderGeometry(radius, radius, .0018, 20), material);
        mesh.position.copy(hit.point).addScaledVector(normal, .0014);
        mesh.quaternion.setFromUnitVectors(new T.Vector3(0, ring ? 0 : 1, ring ? 1 : 0), normal);
        model.add(mesh); part.attach(mesh); surfaceDetails++;
    }
    const face = model.getObjectByName('head_link_visual');
    if (face) {
        const b = new T.Box3().setFromObject(face), centre = b.getCenter(new T.Vector3()), size = b.getSize(new T.Vector3());
        detail(face, centre.y, centre.z, Math.min(size.z * .17, .016), visor);
        detail(face, centre.y, centre.z, Math.min(size.z * .18, .017), fastener, true);
        detail(face, centre.y - size.y * .18, centre.z, .004, led);
    }
    const chest = model.getObjectByName('torso_link_visual');
    if (chest) {
        const b = new T.Box3().setFromObject(chest), c = b.getCenter(new T.Vector3()), size = b.getSize(new T.Vector3());
        for (const y of [-.28, .28]) for (const z of [-.32, .32]) detail(chest, c.y + y * size.y, c.z + z * size.z, .0035, fastener);
    }
    return { shells, joints, elastomers, surfaceDetails };
}
