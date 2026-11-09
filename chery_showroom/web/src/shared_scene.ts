/** Public, metre-based scene contract served by the same owner as native physics. */
export type Point = [number,number,number];
export type SceneObject = {
    kind: string; position: Point; size?: Point; yaw: number; parent?: string;
    collision: boolean | {offset?: Point; yaw?: number; floor_to_top?: boolean};
    parts?: Record<string,{size?: Point; height?: number; offset: Point}>;
};
export type SharedScene = {version: number; units: string; up_axis: string; objects: Record<string,SceneObject>};
export function worldObject(scene: SharedScene, name: string, trail: string[] = []): SceneObject {
    if (scene.version !== 1 || scene.units !== 'metres' || scene.up_axis !== 'z') throw Error('Unsupported showroom layout');
    const object = scene.objects[name];
    if (!object || trail.includes(name)) throw Error('Missing or cyclic scene object: '+name);
    let position: Point = [...object.position], yaw = object.yaw;
    if (object.parent) {
        const parent=worldObject(scene,object.parent,[...trail,name]), c=Math.cos(parent.yaw),s=Math.sin(parent.yaw);
        position=[parent.position[0]+c*position[0]-s*position[1],parent.position[1]+s*position[0]+c*position[1],parent.position[2]+position[2]];
        yaw+=parent.yaw;
    }
    if (position.length!==3 || ![...position,yaw].every(Number.isFinite)) throw Error('Invalid scene pose: '+name);
    return {...object,position,yaw};
}
