/* Statenvertaling 2026 — Navigatie */

const Navigation = {
    currentBook: null,
    currentChapter: null,

    init() {
        window.addEventListener('hashchange', () => this.handleHash());
    },

    async renderBookNav() {
        const manifest = await DataLoader.loadManifest();
        const nav = document.getElementById('book-nav');
        nav.innerHTML = '';
        nav.className = 'nav-bar book-nav-grouped';

        // Boekvolgorde uit gebruikersopties (canoniek / tenach / chronologisch / auteur / lengte)
        const mode = (typeof Opties !== 'undefined' && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
        const bookOrder = getBookOrderGroups(mode, manifest);

        const bookById = {};
        for (const b of manifest.books) bookById[b.id] = b;

        const addGroup = (label, books) => {
            if (books.length === 0) return;
            const group = document.createElement('div');
            group.className = 'nav-group';
            const lbl = document.createElement('span');
            lbl.className = 'nav-group-label';
            lbl.textContent = label;
            group.appendChild(lbl);
            for (const book of books) {
                const btn = document.createElement('button');
                btn.textContent = book.nameDutch;
                btn.dataset.bookId = book.id;
                btn.addEventListener('click', () => {
                    const firstCh = book.chaptersIncluded[0];
                    location.hash = `#${book.id}/${firstCh}`;
                });
                group.appendChild(btn);
            }
            nav.appendChild(group);
        };

        for (const [label, ids] of Object.entries(bookOrder)) {
            const books = ids.map(id => bookById[id]).filter(Boolean);
            addGroup(label, books);
        }
        // Eventuele ontbrekende boeken
        const assignedIds = new Set(Object.values(bookOrder).flat());
        const unassigned = manifest.books.filter(b => !assignedIds.has(b.id) &&
            isBookVisibleInNavigation(b));
        if (unassigned.length > 0) addGroup('Overig', unassigned);
    },

    async renderChapterNav(bookId) {
        const manifest = await DataLoader.loadManifest();
        const bookMeta = manifest.books.find(b => b.id === bookId);
        if (!bookMeta) return;

        const nav = document.getElementById('chapter-nav');
        nav.innerHTML = '';
        nav.className = 'nav-bar';

        // Laad boekdata om status per hoofdstuk te bepalen
        const book = await DataLoader.loadBook(bookId);

        for (const ch of bookMeta.chaptersIncluded) {
            const btn = document.createElement('button');
            btn.textContent = ch;
            btn.dataset.chapter = ch;
            btn.addEventListener('click', () => {
                location.hash = `#${bookId}/${ch}`;
            });

            // Groen kleuren als alle verzen "final" zijn
            if (book) {
                const chapter = book.chapters.find(c => c.number === ch);
                if (chapter && chapter.verses.length > 0) {
                    const allFinal = chapter.verses.every(v => v.status === 'final');
                    if (allFinal) btn.classList.add('chapter-approved');
                }
            }

            nav.appendChild(btn);
        }
    },

    updateActiveButtons() {
        // Book buttons
        document.querySelectorAll('#book-nav button').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.bookId === this.currentBook);
        });
        // Chapter buttons
        document.querySelectorAll('#chapter-nav button').forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.chapter) === this.currentChapter);
        });
    },

    async handleHash() {
        const hash = location.hash.slice(1); // verwijder #
        if (!hash) {
            // Zonder hash toont index.html het startscherm (js/startscherm.js).
            if (window.OVStart && document.documentElement.classList.contains('ov-start')) return;
            if (window.OVStart && this.currentBook) { window.OVStart.toon(); return; }
            // Default: eerste boek, eerste hoofdstuk
            const manifest = await DataLoader.loadManifest();
            if (manifest.books.length > 0) {
                const first = manifest.books[0];
                location.hash = `#${first.id}/${first.chaptersIncluded[0]}`;
            }
            return;
        }

        const parts = hash.split('/');
        const bookId = parts[0];
        const chapter = parseInt(parts[1]) || 1;
        const targetVerse = parts[2] ? parseInt(parts[2]) : null;

        if (bookId !== this.currentBook) {
            this.currentBook = bookId;
            await this.renderChapterNav(bookId);
        }
        this.currentChapter = chapter;
        this.updateActiveButtons();

        // Synchroniseer sidebar
        if (typeof Sidebar !== 'undefined') {
            Sidebar.updateActive(bookId, chapter);
            Sidebar.markApprovedChapters(bookId);
        }

        // Laad en render het hoofdstuk
        await App.renderChapter(bookId, chapter);

        // Naar een specifiek vers scrollen + selecteren, anders naar boven
        if (targetVerse && App.focusVerse) {
            App.focusVerse(bookId, chapter, targetVerse);
        } else {
            // Naar boven uitlijnen — ook het werkelijke scroll-element (#content op
            // mobiel), anders bleef de gekozen hoofdstuktekst halverwege ('gecentreerd').
            window.scrollTo(0, 0);
            const sc = (App._getScroller && App._getScroller()) || document.getElementById('content');
            if (sc && sc !== document.scrollingElement && sc !== document.documentElement) sc.scrollTop = 0;
        }
    },

    async navigateRelative(offset) {
        if (!this.currentBook) return;
        const chapterBtns = document.querySelectorAll('#chapter-nav button');
        const chapters = Array.from(chapterBtns).map(b => parseInt(b.dataset.chapter));
        const idx = chapters.indexOf(this.currentChapter);
        const newIdx = idx + offset;
        if (newIdx >= 0 && newIdx < chapters.length) {
            location.hash = `#${this.currentBook}/${chapters[newIdx]}`;
            return;
        }
        // Voorbij de boekgrens → naar het aangrenzende boek (in de actieve volgorde)
        try {
            const manifest = await DataLoader.loadManifest();
            const mode = (window.Opties && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
            const orderIds = (typeof getFlatBookOrder === 'function')
                ? getFlatBookOrder(mode, manifest)
                : manifest.books.map(b => b.id);
            const byId = Object.fromEntries(manifest.books.map(b => [b.id, b]));
            const bIdx = orderIds.indexOf(this.currentBook);
            if (bIdx < 0) return;
            if (newIdx < 0 && bIdx > 0) {
                // Laatste hoofdstuk van het vorige boek
                const prev = byId[orderIds[bIdx - 1]];
                const last = prev.chaptersIncluded[prev.chaptersIncluded.length - 1];
                location.hash = `#${prev.id}/${last}`;
            } else if (newIdx >= chapters.length && bIdx < orderIds.length - 1) {
                // Eerste hoofdstuk van het volgende boek
                const next = byId[orderIds[bIdx + 1]];
                location.hash = `#${next.id}/${next.chaptersIncluded[0]}`;
            }
        } catch (e) { console.warn('[Navigation] cross-book nav faalde:', e); }
    }
};
