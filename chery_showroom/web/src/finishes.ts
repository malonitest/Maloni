import * as T from 'three';

const noise = (x: number, y: number) => {
    let n = Math.imul(x + 17, 374761393) ^ Math.imul(y + 29, 668265263);
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
};
function texture(canvas: HTMLCanvasElement, color = false) {
    const map = new T.CanvasTexture(canvas);
    map.colorSpace = color ? T.SRGBColorSpace : T.NoColorSpace;
    map.wrapS = map.wrapT = T.RepeatWrapping; map.anisotropy = 4;
    return map;
}

/** Small, deterministic, tileable maps: no downloaded assets or random reload variants. */
export function architecturalFinish(kind: 'basalt' | 'plaster') {
    const size = 512;
    const canvases = Array.from({ length: 3 }, () => {
        const canvas = document.createElement('canvas'); canvas.width = canvas.height = size; return canvas;
    });
    const images = canvases.map(c => c.getContext('2d')!.createImageData(size, size));
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
        const grain = noise(x, y), fine = noise(x * 3, y * 3);
        // Periodic low-frequency layers keep the repeat boundary continuous.
        const cloud = Math.sin(x / size * Math.PI * 4 + Math.sin(y / size * Math.PI * 2))
            * Math.cos(y / size * Math.PI * 4);
        const vein = Math.pow(Math.max(0, Math.sin(x / size * Math.PI * 6 + Math.sin(y / size * Math.PI * 4))), 22);
        const base = kind === 'basalt' ? [47, 54, 52] : [230, 229, 222];
        const variation = kind === 'basalt' ? (grain - .5) * 12 + cloud * 3 + vein * 5 : cloud * 1.3 + (grain - .5) * 2;
        const index = (y * size + x) * 4;
        images[0].data.set([...base.map(v => v + variation), 255], index);
        const roughness = kind === 'basalt' ? 185 + grain * 30 + cloud * 6 : 235 + grain * 15;
        images[1].data.set([roughness, roughness, roughness, 255], index);
        const height = 110 + fine * 34 + (kind === 'basalt' ? vein * 6 : grain * 12);
        images[2].data.set([height, height, height, 255], index);
    }
    canvases.forEach((c, i) => c.getContext('2d')!.putImageData(images[i], 0, 0));
    return { map: texture(canvases[0], true), roughnessMap: texture(canvases[1]), bumpMap: texture(canvases[2]) };
}

export function informationScreen(name: string, index: number) {
    const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 640;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#142c26'; ctx.fillRect(0, 0, 1024, 640);
    ctx.fillStyle = '#b7a476'; ctx.fillRect(44, 46, 5, 544);
    ctx.font = '500 32px sans-serif'; ctx.fillText('M A L O N I', 88, 91);
    ctx.textAlign = 'right'; ctx.fillStyle = '#a4b5a8'; ctx.font = '26px sans-serif'; ctx.fillText(`EXHIBIT 0${index + 1}`, 942, 91);
    ctx.textAlign = 'left'; ctx.fillStyle = '#f1f0e5'; ctx.font = '500 63px sans-serif';
    ctx.fillText(name.replace(/ 20\d\d$/, '').toUpperCase(), 88, 205, 850);
    ctx.font = '28px sans-serif'; ctx.fillStyle = '#b9c5b9'; ctx.fillText('AUTOMOTIVE COLLECTION  /  ' + name.slice(-4), 90, 258);
    ctx.strokeStyle = '#a5b8ae'; ctx.lineWidth = 4; ctx.beginPath();
    ctx.moveTo(125, 436); ctx.lineTo(144, 391); ctx.lineTo(288, 369); ctx.lineTo(374, 313);
    ctx.lineTo(644, 313); ctx.lineTo(735, 368); ctx.lineTo(864, 389); ctx.lineTo(892, 436); ctx.stroke();
    for (const x of [280, 749]) { ctx.beginPath(); ctx.arc(x, 435, 43, 0, Math.PI * 2); ctx.stroke(); }
    ctx.strokeStyle = '#718b7d'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(90, 523); ctx.lineTo(944, 523); ctx.stroke();
    ctx.fillStyle = '#c9d2c7'; ctx.font = '27px sans-serif'; ctx.fillText('DESIGN  /  COMFORT  /  PERSONAL CONSULTATION', 90, 578);
    return texture(canvas, true);
}

export function conciergeScreen() {
    const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 640;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#dfe7df'; ctx.fillRect(0, 0, 1024, 640);
    ctx.fillStyle = '#203c32'; ctx.fillRect(0, 0, 1024, 126);
    ctx.fillStyle = '#e9e7d9'; ctx.font = '500 48px sans-serif'; ctx.fillText('MALONI  /  CONCIERGE', 48, 80);
    ctx.fillStyle = '#263d32'; ctx.font = '500 46px sans-serif'; ctx.fillText('Welcome to our gallery', 48, 212);
    ctx.fillStyle = '#617364'; ctx.font = '27px sans-serif'; ctx.fillText('Choose a car  ·  personal consultation', 48, 266);
    for (const [i, model] of ['BMW X1', 'VOLVO XC60', 'CHERY TIGGO 8 PRO'].entries()) {
        const y = 310 + i * 93;
        ctx.fillStyle = '#f7f6ed'; ctx.fillRect(48, y, 928, 74);
        ctx.fillStyle = ['#722734', '#a4b1b7', '#264e61'][i]; ctx.fillRect(66, y + 17, 40, 40);
        ctx.fillStyle = '#314838'; ctx.font = '30px sans-serif'; ctx.fillText(model, 130, y + 48);
    }
    return texture(canvas, true);
}
