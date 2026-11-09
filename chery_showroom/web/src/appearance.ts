/** Shared art direction. Distances are metres; light positions use Three Y-up. */
export const appearance = {
    exposure: 1.0,
    environment: .86,
    sun: { color: 0xfffaf2, intensity: .96, position: [-5, 8, 12] as [number, number, number], normalBias: .009, bias: -.0001 },
    fixtures: {
        vehicle: { height: 4.61, offset: 1.25, width: .64, length: 3.42, intensity: 2.35 },
        desk: { position: [-2.2, 4.56, 2.2] as [number, number, number], width: 3.4, length: 1.5, intensity: 2.2 },
    },
    fill: .42,
    stone: { roughness: .72, clearcoat: .10, normal: .045 },
    wood: { roughness: .75, normal: .12 },
    contacts: { vehicle: .23, wheel: .48, furnishing: .2 },
    ao: { intensity: .38, radius: .19, thickness: .3 },
    reflection: { height: 1.35, intensity: .85, floorIntensity: .45 },
    paint: { roughness: .29, metalness: .23, clearcoat: 1, clearcoatRoughness: .14, envMapIntensity: 1.05 },
    chrome: { roughness: .24, metalness: .92, envMapIntensity: .85 },
    trim: { roughness: .63, metalness: .03, envMapIntensity: .45 },
    rubber: { roughness: .94, metalness: 0, envMapIntensity: .18 },
    glass: { roughness: .16, metalness: .06, clearcoat: .8, envMapIntensity: .7, transmission: 0 },
} as const;

export const atmospheres = {
    day: { exposure: appearance.exposure, environment: appearance.environment, sun: appearance.sun.intensity,
        sunColor: appearance.sun.color, fill: appearance.fill, fixture: appearance.fixtures.vehicle.intensity,
        desk: appearance.fixtures.desk.intensity, fixtureColor: 0xfffaf2, background: .7, cutaway: '#e4e7e3', fog: '#bac7cd' },
    evening: { exposure: 1.0, environment: .24, sun: .08, sunColor: 0xaac4e8, fill: .16,
        fixture: 5.2, desk: 4.2, fixtureColor: 0xffead3, background: .055, cutaway: '#192426', fog: '#253138' },
} as const;
export type Ambience = keyof typeof atmospheres;
