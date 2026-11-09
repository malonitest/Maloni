import * as T from 'three';
import { appearance as look, atmospheres, type Ambience } from './appearance';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export function lightGallery(scene: T.Scene) {
    RectAreaLightUniformsLib.init();
    const sun = new T.DirectionalLight(look.sun.color, look.sun.intensity);
    sun.position.set(...look.sun.position); sun.target.position.set(0, 0, -1);
    sun.castShadow = true;
    // Fit the light frustum to the entire fixed building, not an oversized empty region.
    sun.updateMatrixWorld(); sun.target.updateMatrixWorld(); sun.shadow.updateMatrices(sun);
    const bounds = new T.Box3(new T.Vector3(-9.1, 0, -6.6), new T.Vector3(9.1, 5.1, 6.6));
    bounds.applyMatrix4(sun.shadow.camera.matrixWorldInverse);
    Object.assign(sun.shadow.camera, { left: bounds.min.x - .3, right: bounds.max.x + .3,
        bottom: bounds.min.y - .3, top: bounds.max.y + .3, near: Math.max(.1, -bounds.max.z - .5), far: -bounds.min.z + .5 });
    sun.shadow.camera.updateProjectionMatrix();
    sun.shadow.normalBias = look.sun.normalBias; sun.shadow.bias = look.sun.bias;
    sun.shadow.radius = 2;
    scene.add(sun, sun.target);
    // Large emitters produce broad car highlights and softly illuminated faces.
    const roof = new T.RectAreaLight(0xfffaf2, look.fixtures.vehicle.intensity, 15.8, look.fixtures.vehicle.length);
    roof.position.set(0, look.fixtures.vehicle.height, -3.6); roof.lookAt(0, 0, -3.6); scene.add(roof);
    const desk = new T.RectAreaLight(0xfffaf2, look.fixtures.desk.intensity, look.fixtures.desk.width, look.fixtures.desk.length);
    desk.position.set(...look.fixtures.desk.position); desk.lookAt(-2.2, .9, 2); scene.add(desk);
    const fill = new T.HemisphereLight(0xe7eef4, 0x88857f, look.fill); scene.add(fill);
    return { sun, setAmbience(mode: Ambience) {
        const settings = atmospheres[mode];
        sun.intensity = settings.sun; sun.color.setHex(settings.sunColor);
        roof.intensity = settings.fixture; desk.intensity = settings.desk;
        roof.color.setHex(settings.fixtureColor); desk.color.setHex(settings.fixtureColor);
        fill.intensity = settings.fill;
        scene.environmentIntensity = settings.environment;
    } };
}

/** Freeze scene-local reflections once; parked vehicles do not require per-frame probes. */
export function bakeVehicleReflections(renderer: T.WebGLRenderer, scene: T.Scene, vehicles: T.Object3D[], positions: number[][], heights: number[] = []) {
    const pmrem = new T.PMREMGenerator(renderer);
    const maps: T.WebGLRenderTarget[] = [];
    const visibility = vehicles.map(v => v.visible);
    vehicles.forEach(v => { v.visible = false; });
    try {
        for (let i = 0; i < vehicles.length; i++) {
            const cube = new T.WebGLCubeRenderTarget(128, { type: T.HalfFloatType, generateMipmaps: true, minFilter: T.LinearMipmapLinearFilter });
            const camera = new T.CubeCamera(.05, 80, cube);
            camera.position.set(positions[i][0], heights[i] ?? look.reflection.height, -positions[i][1]);
            camera.update(renderer, scene);
            const environment = pmrem.fromCubemap(cube.texture); maps.push(environment);
            const assigned = new Set<T.MeshStandardMaterial>();
            vehicles[i].traverse(object => {
                if (!(object instanceof T.Mesh)) return;
                for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
                    if (material instanceof T.MeshStandardMaterial && !assigned.has(material)) {
                        assigned.add(material);
                        // Regenerating a static probe must not multiply the finish darker each time.
                        const base = material.userData.reflectionBaseIntensity ?? material.envMapIntensity;
                        material.userData.reflectionBaseIntensity = base;
                        material.envMap = environment.texture; material.envMapIntensity = base * look.reflection.intensity; material.needsUpdate = true;
                    }
                }
            });
            cube.dispose();
        }
    } finally {
        vehicles.forEach((v, i) => { v.visible = visibility[i]; }); pmrem.dispose();
    }
    return maps;
}

/** Optional high-profile contact occlusion; economy keeps the single forward-render pass. */
export function createPresentationPipeline(renderer: T.WebGLRenderer, scene: T.Scene, camera: T.PerspectiveCamera) {
    let composer: EffectComposer | null = null;
    let ao: GTAOPass | null = null;
    let high = false;
    let fxaa: ShaderPass | null = null;
    function configure(enabled: boolean) {
        high = enabled;
        if (high && !composer) {
            composer = new EffectComposer(renderer);
            composer.addPass(new RenderPass(scene, camera));
            ao = new GTAOPass(scene, camera, 512, 512);
            ao.blendIntensity = look.ao.intensity;
            ao.updateGtaoMaterial({ radius: look.ao.radius, distanceExponent: 1.2, thickness: look.ao.thickness, samples: 8 });
            ao.updatePdMaterial({ lumaPhi: 5, depthPhi: 2, normalPhi: 3, radius: 4, samples: 8 });
            composer.addPass(ao); composer.addPass(new OutputPass());
            fxaa = new ShaderPass(FXAAShader); composer.addPass(fxaa);
        }
    }
    return {
        configure,
        resize: (w: number, h: number) => { if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); fxaa!.uniforms.resolution.value.set(1 / (w * renderer.getPixelRatio()), 1 / (h * renderer.getPixelRatio())); } },
        render: () => { if (high && composer) composer.render(); else renderer.render(scene, camera); },
    };
}
