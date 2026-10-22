/* Open Vertaling — Mobiele navigatie (≤768px)
 *
 * Vervangt de sidebar-driehoekjes op mobiel door:
 *   - boek-dropdown (links)  → kies boek (gegroepeerd OT/NT/Apocrief)
 *   - hoofdstuk-dropdown (midden) → kies hoofdstuk
 *   - opties-knop (rechts) → opent #sidebar-right als drawer
 *   - footer met ◀ vorig | "Boek X / Y" | volgend ▶
 *
 * Desktop (>768px) blijft ongewijzigd: CSS verbergt deze elementen.
 */

const MobileNav = {
    inited: false,
    booksByGroup: null,         // [{label, books: [...]}]
    bookById: null,             // id -> book meta

    isMobile() { return window.matchMedia('(max-width: 768px)').matches; },

    BOOK_GROUPS: [
        ['Pentateuch', ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium']],
        ['Historische boeken', ['jozua','richteren','ruth','1samuel','2samuel','1koningen','2koningen','1kronieken','2kronieken','ezra','nehemia','esther']],
        ['Poëtische boeken', ['job','psalmen','spreuken','prediker','hooglied']],
        ['Grote profeten', ['jesaja','jeremia','klaagliederen','ezechiel','daniel']],
        ['Kleine profeten', ['hosea','joel','amos','obadja','jona','micha','nahum','habakuk','zefanja','haggai','zacharia','maleachi']],
        ['Apocriefen', ['3ezra','4ezra','tobit','judith','boekderwijsheid','jezussirach','baruch','estherapocrief','gebedvanazaria','gezangindevuuroven','susanna','belenddedraak','gebedvanmanasse','1makkabeeen','2makkabeeen','3makkabeeen']],
        ['Evangeliën', ['mattheus','markus','lukas','johannes']],
        ['Handelingen', ['handelingen']],
        ['Brieven van Paulus', ['romeinen','1korinthiers','2korinthiers','galaten','efeziers','filippenzen','kolossenzen','1tessalonicensen','2tessalonicensen','1timotheus','2timotheus','titus','filemon']],
        ['Algemene brieven', ['hebreeen','jakobus','1petrus','2petrus','1johannes','2johannes','3johannes','judas']],
        ['Openbaring', ['openbaring']],
    ],

    pickerMode: null,           // 'books' | 'chapters'
    pickerBookId: null,         // boek waarvoor we hoofdstukken tonen

    async init() {
        if (this.inited) return;
        this.inited = true;

        const bookBtn = document.getElementById('mobile-book-btn');
        if (!bookBtn) return;

        // Manifest preloaden voor naam-mapping
        const manifest = await DataLoader.loadManifest();
        this.bookById = {};
        for (const b of manifest.books) this.bookById[b.id] = b;

        // Open direct bij de hoofdstukken van het huidige boek. Via Terug kan
        // de lezer vervolgens een ander boek kiezen.
        bookBtn.addEventListener('click', () => {
            const huidigBoek = Navigation.currentBook;
            this.openPicker(huidigBoek ? 'chapters' : 'books', huidigBoek || null);
        });

        // KT-popup aan/uit toggle
        const ktBtn = document.getElementById('mobile-kt-btn');
        if (ktBtn) {
            ktBtn.addEventListener('click', () => {
                const on = !ktBtn.classList.contains('is-on');
                ktBtn.classList.toggle('is-on', on);
                ktBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
                document.body.classList.toggle('kt-popup-mode', on);
                const cb = document.getElementById('toggle-kt-popup');
                if (cb) cb.checked = on;
            });
        }

        // Overlay-controls
        document.getElementById('mp-close').addEventListener('click', () => this.closePicker());
        document.getElementById('mp-back').addEventListener('click', () => {
            if (this.pickerMode === 'chapters') this.openPicker('books');
            else this.closePicker();
        });

        // Opties-knop opent het gedeelde modale optiespaneel.

        // Reageer op hash-veranderingen
        window.addEventListener('hashchange', () => this.syncFromState());
        setTimeout(() => this.syncFromState(), 50);
    },

    openPicker(mode, bookId = null) {
        const overlay = document.getElementById('mobile-picker');
        const body    = document.getElementById('mp-body');
        const title   = document.getElementById('mp-title');
        const back    = document.getElementById('mp-back');
        if (!overlay || !body) return;
        this.pickerMode = mode;
        body.innerHTML = '';
        if (mode === 'books') {
            title.textContent = 'Kies een boek';
            back.classList.add('hidden');
            this._renderBooks(body);
        } else {
            const book = this.bookById[bookId];
            if (!book) return;
            this.pickerBookId = bookId;
            title.textContent = `${book.nameDutch} — kies hoofdstuk`;
            back.classList.remove('hidden');
            this._renderChapters(body, book);
        }
        overlay.classList.remove('hidden');
        overlay.setAttribute('aria-hidden', 'false');
        // Body-scroll blokkeren
        document.body.style.overflow = 'hidden';
        // Boekenlijst: meteen naar het huidige (actieve) boek scrollen
        if (mode === 'books') {
            const active = body.querySelector('.mp-item.active');
            if (active) active.scrollIntoView({ block: 'center' });
        }
    },

    closePicker() {
        const overlay = document.getElementById('mobile-picker');
        if (overlay) {
            overlay.classList.add('hidden');
            overlay.setAttribute('aria-hidden', 'true');
        }
        document.body.style.overflow = '';
        this.pickerMode = null;
    },

    _renderBooks(body) {
        const currentBook = Navigation.currentBook;
        // Zoekbalk bovenin
        const search = document.createElement('input');
        search.type = 'search';
        search.className = 'mp-search';
        search.placeholder = 'Zoek een boek…';
        search.setAttribute('aria-label', 'Zoek een boek');
        search.addEventListener('input', () => {
            const q = search.value.trim().toLowerCase();
            body.querySelectorAll('.mp-group').forEach(grp => {
                let anyVisible = false;
                grp.querySelectorAll('.mp-item').forEach(item => {
                    const match = !q || item.textContent.toLowerCase().includes(q);
                    item.style.display = match ? '' : 'none';
                    if (match) anyVisible = true;
                });
                grp.style.display = anyVisible ? '' : 'none';
            });
        });
        body.appendChild(search);

        // De boekvolgorde komt uit Leesvoorkeuren; de boekenpicker toont alleen
        // de zoekfunctie en de boeken in de daar gekozen volgorde.
        const mode = (window.Opties && Opties.state && Opties.state.boekvolgorde) || 'canoniek';

        // Groepen volgens de gekozen volgorde (val terug op de statische canon)
        let groups = this.BOOK_GROUPS;
        try {
            if (typeof getBookOrderGroups === 'function') {
                const g = getBookOrderGroups(mode, { books: Object.values(this.bookById) });
                if (g) groups = Object.entries(g);
            }
        } catch (e) {}

        for (const [label, ids] of groups) {
            const books = ids.map(id => this.bookById[id]).filter(book => book &&
                (typeof isBookVisibleInNavigation !== 'function' || isBookVisibleInNavigation(book)));
            if (!books.length) continue;
            const grp = document.createElement('div');
            grp.className = 'mp-group';
            const lbl = document.createElement('div');
            lbl.className = 'mp-group-label';
            lbl.textContent = label;
            grp.appendChild(lbl);
            const list = document.createElement('div');
            list.className = 'mp-list';
            for (const b of books) {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'mp-item' + (b.id === currentBook ? ' active' : '');
                item.textContent = b.nameDutch;
                item.addEventListener('click', () => {
                    const chapters = b.chaptersIncluded || [];
                    if (chapters.length === 1) {
                        // 1-hoofdstuk-boek: direct navigeren, picker dicht
                        location.hash = `#${b.id}/${chapters[0]}`;
                        this.closePicker();
                        setTimeout(() => this.syncFromState(), 80);
                    } else {
                        // Meerdere hoofdstukken: door naar hoofdstuk-keuze
                        this.openPicker('chapters', b.id);
                    }
                });
                list.appendChild(item);
            }
            grp.appendChild(list);
            body.appendChild(grp);
        }
    },

    _renderChapters(body, book) {
        const hashParts = location.hash.replace(/^#/, '').split('/');
        const currentBook = Navigation.currentBook || hashParts[0];
        const currentChapter = Navigation.currentChapter || parseInt(hashParts[1], 10) || 1;
        const sameBook = (book.id === currentBook);
        const list = document.createElement('div');
        list.className = 'mp-list mp-chapters';
        for (const ch of book.chaptersIncluded) {
            const item = document.createElement('button');
            item.type = 'button';
            const verified = (window.App && App._isVerified) ? App._isVerified(book.id, ch) : false;
            item.className = 'mp-item'
                + (sameBook && ch === currentChapter ? ' active' : '')
                + (verified ? '' : ' unverified');
            if (!verified) item.title = 'Concept — nog niet handmatig gecontroleerd';
            item.textContent = ch;
            item.addEventListener('click', () => {
                // Direct het topbar-label updaten zodat het niet de oude waarde
                // toont terwijl Navigation nog moet bijwerken via hashchange.
                const bookLbl = document.querySelector('#mobile-book-btn .mp-label');
                if (bookLbl) bookLbl.textContent = `${book.nameDutch} ${ch}`;
                location.hash = `#${book.id}/${ch}`;
                this.closePicker();
                // Backup: sync na korte delay (na Navigation hashchange handler)
                setTimeout(() => this.syncFromState(), 80);
            });
            list.appendChild(item);
        }
        body.appendChild(list);
    },

    async _populateBooks(sel) {
        const manifest = await DataLoader.loadManifest();

        // Hergebruik dezelfde groep-volgorde als sidebar/Navigation
        const bookOrder = {
            'Pentateuch': ['genesis', 'exodus', 'leviticus', 'numeri', 'deuteronomium'],
            'Historische boeken': ['jozua','richteren','ruth','1samuel','2samuel','1koningen','2koningen','1kronieken','2kronieken','ezra','nehemia','esther'],
            'Poëtische boeken': ['job','psalmen','spreuken','prediker','hooglied'],
            'Grote profeten': ['jesaja','jeremia','klaagliederen','ezechiel','daniel'],
            'Kleine profeten': ['hosea','joel','amos','obadja','jona','micha','nahum','habakuk','zefanja','haggai','zacharia','maleachi'],
            'Apocriefen': ['3ezra','4ezra','tobit','judith','boekderwijsheid','jezussirach','baruch','estherapocrief','gebedvanazaria','gezangindevuuroven','susanna','belenddedraak','gebedvanmanasse','1makkabeeen','2makkabeeen','3makkabeeen'],
            'Evangeliën': ['mattheus','markus','lukas','johannes'],
            'Handelingen': ['handelingen'],
            'Brieven van Paulus': ['romeinen','1korinthiers','2korinthiers','galaten','efeziers','filippenzen','kolossenzen','1tessalonicensen','2tessalonicensen','1timotheus','2timotheus','titus','filemon'],
            'Algemene brieven': ['hebreeen','jakobus','1petrus','2petrus','1johannes','2johannes','3johannes','judas'],
            'Openbaring': ['openbaring'],
        };

        this.bookById = {};
        for (const b of manifest.books) this.bookById[b.id] = b;

        sel.innerHTML = '';
        // placeholder
        const ph = document.createElement('option');
        ph.value = '';
        ph.textContent = 'Kies boek…';
        ph.disabled = true;
        ph.selected = true;
        sel.appendChild(ph);

        for (const [label, ids] of Object.entries(bookOrder)) {
            const books = ids.map(id => this.bookById[id]).filter(book => book &&
                (typeof isBookVisibleInNavigation !== 'function' || isBookVisibleInNavigation(book)));
            if (books.length === 0) continue;
            const og = document.createElement('optgroup');
            og.label = label;
            for (const b of books) {
                const o = document.createElement('option');
                o.value = b.id;
                o.textContent = b.nameDutch;
                og.appendChild(o);
            }
            sel.appendChild(og);
        }
        // Eventuele ontbrekende boeken (Ethiopische stub-boeken hier altijd verbergen)
        const assigned = new Set(Object.values(bookOrder).flat());
        const rest = manifest.books.filter(b => !assigned.has(b.id) &&
            (typeof isBookVisibleInNavigation !== 'function' || isBookVisibleInNavigation(b)));
        if (rest.length > 0) {
            const og = document.createElement('optgroup');
            og.label = 'Overig';
            for (const b of rest) {
                const o = document.createElement('option');
                o.value = b.id;
                o.textContent = b.nameDutch;
                og.appendChild(o);
            }
            sel.appendChild(og);
        }
    },

    _populateChapters(bookId, currentChapter) {
        const sel = document.getElementById('mobile-chapter-select');
        if (!sel) return;
        const book = this.bookById && this.bookById[bookId];
        if (!book) { sel.innerHTML = ''; return; }
        sel.innerHTML = '';
        for (const ch of book.chaptersIncluded) {
            const o = document.createElement('option');
            o.value = ch;
            o.textContent = ch;
            if (ch === currentChapter) o.selected = true;
            sel.appendChild(o);
        }
    },

    syncFromState() {
        if (!this.bookById) return;
        // De URL-hash is leidend (boek én hoofdstuk samen). Navigation.* kan kort
        // achterlopen na een boekwissel → gaf bv. 'Genesis 91' (oud hoofdstuk bij
        // nieuw boek). Daarom hash eerst, Navigation alleen als fallback.
        const hashMatch = (location.hash || '').match(/#([a-z0-9]+)(?:\/(\d+))?/i);
        const bookId = (hashMatch && hashMatch[1]) || Navigation.currentBook;
        if (!bookId) return;
        const book = this.bookById[bookId];
        let ch = (hashMatch && hashMatch[2]) ? parseInt(hashMatch[2], 10)
                 : (Navigation.currentChapter || 1);
        // Valideer tegen de hoofdstukken van dít boek (voorkomt onmogelijke nummers).
        if (book && Array.isArray(book.chaptersIncluded) && book.chaptersIncluded.indexOf(ch) === -1) {
            ch = book.chaptersIncluded[0];
        }

        // Knop-label updaten — combineer boek + hoofdstuk in één label
        const bookLbl = document.querySelector('#mobile-book-btn .mp-label');
        if (bookLbl && book) bookLbl.textContent = `${book.nameDutch} ${ch}`;

        // Footer-label "Boek X / Y"
        const label = document.getElementById('mobile-chapter-label');
        if (label && book) {
            const total = book.chaptersIncluded.length;
            label.textContent = `${book.nameDutch} ${ch} / ${total}`;
        }

        // Vorig/volgend-knop verbergen aan de uiterste grenzen
        // (Genesis 1 = geen 'vorig'; laatste hfdst van het laatste boek = geen 'volgend').
        try {
            const mode = (window.Opties && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
            const manifest = { books: Object.values(this.bookById) };
            const orderIds = (typeof getFlatBookOrder === 'function')
                ? getFlatBookOrder(mode, manifest) : manifest.books.map(b => b.id);
            const bIdx = orderIds.indexOf(bookId);
            const chs = (book && book.chaptersIncluded) || [];
            const atFirst = bIdx === 0 && ch === chs[0];
            const atLast = bIdx === orderIds.length - 1 && ch === chs[chs.length - 1];
            const prevBtn = document.getElementById('mobile-prev-btn');
            const nextBtn = document.getElementById('mobile-next-btn');
            // Alleen aan de absolute uiteinden verbergen; elders blijven de knoppen
            // actief — navigateRelative() steekt dan de boekgrens over.
            if (prevBtn) { prevBtn.style.visibility = atFirst ? 'hidden' : ''; prevBtn.disabled = atFirst; }
            if (nextBtn) { nextBtn.style.visibility = atLast ? 'hidden' : ''; nextBtn.disabled = atLast; }
        } catch (e) {}
    },

};

document.addEventListener('DOMContentLoaded', () => {
    // Wacht een tick zodat App.init() en Navigation.init() klaar zijn met manifest-laden
    setTimeout(() => MobileNav.init(), 0);
});
