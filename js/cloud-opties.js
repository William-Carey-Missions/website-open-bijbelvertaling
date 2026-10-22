/* Cloud-opties — sync layer tussen Opties.state (localStorage)
 *  en Firestore: users/{uid}/data/opties (single document).
 *
 * Strategie (zelfde als CloudHighlights):
 *  - Bij login: pull cloud-state; bij eerste login zonder lokale wijziging
 *    adopteer cloud, anders last-writer-wins op _meta.lastLocalEdit
 *  - Daarna: elke Opties.save() wordt gedebounced naar Firestore geschreven
 *  - Bij logout: stop syncing; localStorage blijft authoritative
 */

const CloudOpties = {
    SAVE_DEBOUNCE_MS: 1200,
    enabled: false,
    uid: null,
    docRef: null,
    saveTimer: null,
    lastPushedJSON: null,

    init() {
        if (!window.Auth || !window.Opties) return;
        // Wrap Opties.save: roep cloud-sync na elke lokale save
        const origSave = Opties.save.bind(Opties);
        Opties.save = () => {
            origSave();
            Opties.state._meta = Opties.state._meta || {};
            Opties.state._meta.lastLocalEdit = Date.now();
            try { localStorage.setItem(Opties.STORAGE_KEY, JSON.stringify(Opties.state)); } catch (e) {}
            this.scheduleSave();
        };

        Auth.onChange((user) => {
            if (user) this.attach(user);
            else      this.detach();
        });
    },

    async attach(user) {
        if (!window._fb || !window._fb.db) return;
        this.uid = user.uid;
        const { doc } = window._fb.fsMod;
        this.docRef = doc(window._fb.db, 'users', this.uid, 'data', 'opties');
        this.enabled = true;
        await this.pullAndMerge();
    },

    detach() {
        this.enabled = false;
        this.uid = null;
        this.docRef = null;
        if (this.saveTimer) { clearTimeout(this.saveTimer); this.saveTimer = null; }
    },

    async pullAndMerge() {
        if (!this.docRef) return;
        try {
            const { getDoc } = window._fb.fsMod;
            const snap = await getDoc(this.docRef);
            if (!snap.exists()) {
                await this.pushNow();
                return;
            }
            const cloud = snap.data() || {};
            const cloudState = cloud.state || {};
            const cloudTs = (cloudState._meta && cloudState._meta.lastLocalEdit) || 0;
            const localTs = (Opties.state._meta && Opties.state._meta.lastLocalEdit) || 0;

            // Eerste-keer login zonder lokale aanpassing → adopteer cloud,
            // anders last-writer-wins.
            const localTouched = !!(Opties.state._meta && Opties.state._meta.lastLocalEdit);
            const adoptCloud = !localTouched || cloudTs > localTs;

            if (adoptCloud) {
                const merged = { ...Opties.DEFAULTS };
                for (const k of Object.keys(cloudState)) merged[k] = cloudState[k];
                Opties.state = merged;
                Opties.enforceReaderOptions();
                try { localStorage.setItem(Opties.STORAGE_KEY, JSON.stringify(Opties.state)); } catch (e) {}
                this.lastPushedJSON = JSON.stringify(Opties.state);
                this._applyAll();
            } else {
                await this.pushNow();
            }
        } catch (e) {
            console.warn('[CloudOpties] pull failed:', e);
        }
    },

    /** Synchroniseer UI + rendering met de (nieuwe) Opties.state. */
    _applyAll() {
        try {
            // Radio/checkbox-inputs bijwerken
            document.querySelectorAll('[data-optie]').forEach(input => {
                if (input.tagName === 'SELECT') {
                    input.value = Opties.state[input.dataset.optie];
                } else {
                    input.checked = Opties.state[input.dataset.optie] === input.value;
                }
            });
            if (Opties.applyLayoutClass) Opties.applyLayoutClass();
            if (Opties.applyVerseNumbersClass) Opties.applyVerseNumbersClass();
            OVTheme.apply(Opties.state.thema);
            // Boekvolgorde kan veranderd zijn → sidebar/nav opnieuw
            if (typeof Sidebar !== 'undefined' && Sidebar.renderTree) Sidebar.renderTree();
            if (typeof Navigation !== 'undefined' && Navigation.renderBookNav) Navigation.renderBookNav();
            // Tekst opnieuw renderen voor godsnaam/sheol-keuzes
            if (Opties.applyToCurrentChapter) Opties.applyToCurrentChapter();
        } catch (e) { console.warn('[CloudOpties] apply failed:', e); }
    },

    scheduleSave() {
        if (!this.enabled || !this.docRef) return;
        if (this.saveTimer) clearTimeout(this.saveTimer);
        this.saveTimer = setTimeout(() => this.pushNow(), this.SAVE_DEBOUNCE_MS);
    },

    async pushNow() {
        if (!this.enabled || !this.docRef) return;
        try {
            const { setDoc } = window._fb.fsMod;
            const payload = { state: Opties.state, updatedAt: Date.now() };
            const json = JSON.stringify(payload.state);
            if (json === this.lastPushedJSON) return;
            await setDoc(this.docRef, payload);
            this.lastPushedJSON = json;
        } catch (e) {
            console.warn('[CloudOpties] push failed:', e);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => CloudOpties.init(), 200);
});
window.CloudOpties = CloudOpties;
