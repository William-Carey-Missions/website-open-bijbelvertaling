/* Open Vertaling — Data laden (per-chapter, na chapter-split refactor) */

const DataLoader = {
    manifest: null,                 // books.json (boeken-overzicht)
    bookManifestCache: {},          // bookId -> book-manifest (zonder verzen)
    chapterCache: {},               // `${bookId}:${ch}` -> chapter-data
    cache: {},                      // bookId -> 'pseudo full book' (voor backwards-compat)
    MAX_CHAPTERS_CACHED: 30,
    _chapterCacheOrder: [],         // LRU

    async loadManifest() {
        if (this.manifest) return this.manifest;
        if (!this._manifestPromise) this._manifestPromise = fetch('data/books.json')
            .then(response => { if (!response.ok) throw new Error('Boekenlijst niet beschikbaar'); return response.json(); })
            .then(manifest => {
                manifest.books = manifest.books.filter(ReaderPolicy.allowsBook);
                this.manifest = manifest;
                return manifest;
            }).catch(error => { this._manifestPromise = null; throw error; });
        return this._manifestPromise;
    },

    /** Laadt het boek-manifest (klein, ~5KB): bookIntro + lijst chapters [{number, verseCount}]. */
    async loadBookManifest(bookId) {
        if (this.bookManifestCache[bookId]) return this.bookManifestCache[bookId];
        const m = await this.loadManifest();
        const bookMeta = m.books.find(b => b.id === bookId);
        if (!bookMeta) return null;
        const resp = await fetch(`data/${bookMeta.file}`);
        const bm = await resp.json();
        this.bookManifestCache[bookId] = bm;
        return bm;
    },

    /** Laadt 1 hoofdstuk en merget localStorage-edits. */
    async loadChapter(bookId, chapterNum) {
        const manifest = await this.loadManifest();
        const book = manifest.books.find(item => item.id === bookId);
        if (!book || !Number.isInteger(chapterNum) || !book.chaptersIncluded.includes(chapterNum)) return null;
        const key = 'nl-ov:' + bookId + ':' + chapterNum;
        if (this.chapterCache[key]) {
            this._chapterCacheOrder = this._chapterCacheOrder.filter(item => item !== key);
            this._chapterCacheOrder.push(key);
            return this.chapterCache[key];
        }
        this._pendingChapters = this._pendingChapters || new Map();
        if (this._pendingChapters.has(key)) return this._pendingChapters.get(key);
        const pending = this._loadChapterData(bookId, chapterNum, key);
        this._pendingChapters.set(key, pending);
        try { return await pending; } finally { this._pendingChapters.delete(key); }
    },

    async _loadChapterData(bookId, chapterNum, key) {
        const ch = await Verification.loadJSON('data/' + bookId + '/' + chapterNum + '.json');
        if (window.CitatieUit) CitatieUit.hoofdstuk(ch, bookId);
        const edits = typeof Storage !== 'undefined' ? Storage.getEdits(bookId) : null;
        if (edits) this._mergeChapterEdits(ch, edits, chapterNum);
        this.chapterCache[key] = ch;
        this._chapterCacheOrder.push(key);
        this._evictOld();
        return ch;
    },

    /** Backward-compat: bouwt 'oude' formaat dict {chapters: [...]} maar laadt LAZY.
     *  Voor code die nog zoekt via book.chapters.find(...) — die werkt mits de chapter al gecached is.
     *  Voor de hoofd-render-flow gebruiken we direct loadChapter().
     */
    async loadBook(bookId) {
        if (this.cache[bookId]) return this.cache[bookId];
        const bm = await this.loadBookManifest(bookId);
        if (!bm) return null;
        // Bouw lazy chapters-array: alleen number gevuld; verses worden ingevuld bij loadChapter
        const lazyChapters = (bm.chapters || []).map(c => ({
            number: c.number,
            verseCount: c.verseCount,
            verses: [],   // leeg — code die .length checkt werkt; status-checks krijgen 'false'
            _lazy: true,
        }));
        const book = { ...bm, chapters: lazyChapters };
        this.cache[bookId] = book;
        return book;
    },

    /** Pre-fetch buurchapters bij idle — geeft instant volgende-chapter klik. */
    prefetchAdjacent(bookId, chapterNum) {
        const fn = () => {
            [chapterNum - 1, chapterNum + 1].forEach(n => {
                if (n >= 1) {
                    const key = `${bookId}:${n}`;
                    if (!this.chapterCache[key]) {
                        this.loadChapter(bookId, n).catch(() => {});
                    }
                }
            });
        };
        if ('requestIdleCallback' in window) {
            requestIdleCallback(fn, { timeout: 2000 });
        } else {
            setTimeout(fn, 500);
        }
    },

    _mergeChapterEdits(chapter, edits, chapterNum) {
        const editableVerseFields = ['text2026', 'opmerkingen', 'aandachtspunten', 'status'];
        for (const [key, edit] of Object.entries(edits)) {
            const [ch, vs] = key.split(':').map(Number);
            if (ch !== chapterNum) continue;
            const verse = (chapter.verses || []).find(v => v.number === vs);
            if (!verse) continue;
            const editable = {};
            for (const field of editableVerseFields) {
                if (Object.prototype.hasOwnProperty.call(edit, field)) editable[field] = edit[field];
            }
            if (edit.marginNotes && verse.marginNotes) {
                for (const [idx, text2026] of Object.entries(edit.marginNotes)) {
                    if (verse.marginNotes[parseInt(idx)]) {
                        verse.marginNotes[parseInt(idx)].text2026 = text2026;
                    }
                }
            }
            // Alleen redactionele velden mogen uit lokale bewerkingen komen.
            // Canonieke grondtekst, provenance en woordnummerkoppelingen worden
            // altijd uit de vers gepubliceerde hoofdstukdata geladen.
            Object.assign(verse, editable);
        }
    },

    _evictOld() {
        while (this._chapterCacheOrder.length > this.MAX_CHAPTERS_CACHED) {
            const oldest = this._chapterCacheOrder.shift();
            delete this.chapterCache[oldest];
        }
    },

    invalidateCache(bookId) {
        delete this.cache[bookId];
        delete this.bookManifestCache[bookId];
        // chapter-cache for this book
        for (const key of [...this._chapterCacheOrder]) {
            if (key.includes(':' + bookId + ':') || key.startsWith(bookId + ':')) {
                const idx = this._chapterCacheOrder.indexOf(key);
                if (idx >= 0) this._chapterCacheOrder.splice(idx, 1);
                delete this.chapterCache[key];
            }
        }
    },

    invalidateAllChapters() {
        this.chapterCache = {};
        this._chapterCacheOrder = [];
    },
};

if (typeof window !== 'undefined') window.DataLoader = DataLoader;
