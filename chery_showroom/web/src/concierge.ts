/** Authenticated requests are owned by the dashboard. The iframe never polls state. */
export function createConcierge(vehicle: () => string, react: () => void, modelAvailable: boolean) {
    const tr = (text: string) => (window as unknown as {L?: (text: string) => string}).L?.(text) || text;
    const panel = document.querySelector<HTMLDetailsElement>('#concierge')!;
    const form = document.querySelector<HTMLFormElement>('#concierge-form')!;
    const input = document.querySelector<HTMLInputElement>('#concierge-question')!;
    const submit = document.querySelector<HTMLButtonElement>('#concierge-send')!;
    const answer = document.querySelector<HTMLParagraphElement>('#concierge-answer')!;
    let runId = '', pending = '', timer = 0, available = false;
    const finish = () => { clearTimeout(timer); pending = ''; submit.disabled = !available; };
    window.addEventListener('message', event => {
        if (event.source !== parent || event.origin !== location.origin || !event.data || typeof event.data !== 'object') return;
        const data = event.data;
        const locale = window as unknown as {applyShowroomLanguage?: (language: string) => void; L?: (text: string) => string};
        if(data.type === 'showroom-state') locale.applyShowroomLanguage?.(data.language);
        const tr = (text: string) => locale.L?.(text) || text;
        if (data.type === 'showroom-state' && typeof data.runId === 'string') {
            if (runId && runId !== data.runId) { finish(); answer.textContent = tr('The scene was reset. You can ask a new question.'); }
            runId = data.runId;
            const wasAvailable = available;
            available = modelAvailable && data.receptionAvailable === true;
            submit.disabled = !!pending || !available;
            if (!modelAvailable) answer.textContent = 'The humanoid model is unavailable. You can explore the showroom; restore the graphics assets and reload the page.';
            else if (!available) answer.textContent = tr('The conversation is unavailable. Reconnect to the dashboard.');
            else if (!wasAvailable) answer.textContent = tr('Hello. Ask about the displayed cars or robots. A salesperson can confirm prices and exact specifications.');
        }
        if (data.type === 'showroom-reception-reply' && data.requestId === pending && data.runId === runId) {
            finish();
            answer.textContent = typeof data.reply === 'string' ? data.reply : 'Could not process the question. Please try again.';
            if (data.ok) react();
        }
    });
    form.addEventListener('submit', event => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || !runId || !available || pending || parent === window) return;
        pending = crypto.randomUUID(); submit.disabled = true;
        answer.textContent = tr('The humanoid is processing your question…');
        parent.postMessage({ type: 'showroom-reception-question', text, car: vehicle(), runId, requestId: pending }, location.origin);
        timer = window.setTimeout(() => { finish(); answer.textContent = tr('The reply timed out. Reconnect to the dashboard and try again.'); }, 12000);
    });
    submit.disabled = true;
    if (parent === window) answer.textContent = tr('Open the 3D showroom in the simulation dashboard to start a conversation.');
    else parent.postMessage({ type: 'showroom-ready' }, location.origin);
    return { open: () => { panel.open = true; input.focus(); } };
}
