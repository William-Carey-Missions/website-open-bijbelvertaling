/* Open Vertaling — AUDIO_AVAILABLE + stem-keuze
 * GENEREER-OUTPUT. Higgs Audio v3, man + vrouw. Alleen hoofdstukken met beide
 * stemmen daadwerkelijk op de server (consistent met wat afspeelbaar is).
 */
window.AUDIO_AVAILABLE = {
    '1johannes': [1,2,3,4,5],
    '1koningen': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22],
    '1korinthiers': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
    '1kronieken': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29],
    '1makkabeeen': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
    '1petrus': [1,2,3,4,5],
    '1samuel': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31],
    '1tessalonicensen': [1,2,3,4,5],
    '1timotheus': [1,2,3,4,5,6],
    '2johannes': [1],
    '2koningen': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25],
    '2korinthiers': [1,2,3,4,5,6,7,8,9,10,11,12,13],
    '2kronieken': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36],
    '2makkabeeen': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15],
    '2petrus': [1,2,3],
    '2samuel': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24],
    '2tessalonicensen': [1,2,3],
    '2timotheus': [1,2,3,4],
    '3ezra': [1,2,3,4,5,6,7,8,9],
    '3johannes': [1],
    '3makkabeeen': [1,2,3,4,5,6,7],
    '4ezra': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
    amos: [1,2,3,4,5,6,7,8],
    baruch: [1,2,3,4,5,6],
    efeziers: [1,2,3,4,5,6],
    ezra: [1,2,3,4,5,6,7,8,9,10],
    filemon: [1],
    filippenzen: [1,2,3,4],
    galaten: [1,2,3,4,5,6],
    gebedvanmanasse: [1],
    genesis: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],
    handelingen: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28],
    hebreeen: [1,2,3,4,5,6,7,8,9,10,11,12,13],
    jakobus: [1,2,3,4,5],
    johannes: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21],
    judas: [1],
    kolossenzen: [1,2,3,4],
    lukas: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24],
    markus: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
    mattheus: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28],
    openbaring: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22],
    psalmen: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150],
    romeinen: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
    susanna: [1],
    titus: [1,2,3],
};

/* Centrale stem-helper — gedeeld door lees.js en app.js. */
window.OV_AUDIO = {
    labels: { m: 'Man', v: 'Vrouw' },
    getVoice() { const v = localStorage.getItem('ov_voice'); return (v === 'v' || v === 'm') ? v : 'm'; },
    setVoice(v) { if (v === 'm' || v === 'v') localStorage.setItem('ov_voice', v); },
    toggleVoice() { const nv = this.getVoice() === 'm' ? 'v' : 'm'; this.setVoice(nv); return nv; },
    label(v) { return this.labels[v || this.getVoice()]; },
    src(bookId, chapter) { return window.OV_ASSETS.url(`audio/${bookId}/${chapter}-${this.getVoice()}.mp3`); },
    // De opnames lezen de Open Vertaling voor. Staat er een andere teksteditie in
    // beeld, zoals de Open Parafrase Weergave, dan hoort de opname niet bij de tekst.
    available(bookId, chapter) {
        const editie = (window.TekstEditie && typeof window.TekstEditie.code === 'function') ? window.TekstEditie.code() : 'nl-ov';
        if (editie !== 'nl-ov') return false;
        const list = (window.AUDIO_AVAILABLE || {})[bookId] || []; return list.includes(chapter);
    },
};
