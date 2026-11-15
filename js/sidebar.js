/* Open Vertaling — Sidebar boomnavigatie */

const Sidebar = {
    init() {
        this.setupToggle();
        this.setupMobileBackdrop();
        this.setupSearch();
    },

    isMobile() { return window.matchMedia('(max-width: 768px)').matches; },

    setupToggle() {
        const sidebar = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('sidebar-toggle');
        const openBtn = document.getElementById('sidebar-open');
        if (!sidebar || !toggleBtn || !openBtn) return;

        const collapse = () => {
            sidebar.classList.remove('mobile-open');
            sidebar.classList.add('collapsed');
            openBtn.style.display = 'block';
            document.body.classList.toggle('drawer-open', this._anyDrawerOpen());
            if (!this.isMobile()) localStorage.setItem('sv2026_sidebarCollapsed', 'true');
        };

        const expand = () => {
            sidebar.classList.remove('collapsed');
            if (this.isMobile()) {
                sidebar.classList.add('mobile-open');
                if (window.OptionsPanel) OptionsPanel.close();
                document.body.classList.add('drawer-open');
            } else {
                openBtn.style.display = 'none';
            }
            if (!this.isMobile()) localStorage.setItem('sv2026_sidebarCollapsed', 'false');
        };

        // Default state: desktop = open; mobile = collapsed
        if (this.isMobile()) {
            collapse();
        } else if (localStorage.getItem('sv2026_sidebarCollapsed') === 'true') {
            collapse();
        } else {
            openBtn.style.display = 'none';
        }

        toggleBtn.addEventListener('click', collapse);
        openBtn.addEventListener('click', expand);
    },

    setupMobileBackdrop() {
        const bd = document.getElementById('mobile-backdrop');
        if (!bd) return;
        bd.addEventListener('click', () => {
            this._closeLeft();
        });
    },

    _closeLeft() {
        const s = document.getElementById('sidebar');
        const o = document.getElementById('sidebar-open');
        if (!s) return;
        s.classList.remove('mobile-open');
        s.classList.add('collapsed');
        if (o && this.isMobile()) o.style.display = 'block';
        document.body.classList.toggle('drawer-open', this._anyDrawerOpen());
    },
    _anyDrawerOpen() {
        return document.querySelector('#sidebar.mobile-open') !== null;
    },

    setupSearch() {
        const input = document.getElementById('book-search');
        if (!input) return;
        input.addEventListener('input', () => {
            const q = input.value.toLowerCase().trim();
            document.querySelectorAll('.tree-book').forEach(book => {
                const name = book.dataset.name.toLowerCase();
                const match = !q || name.includes(q);
                book.style.display = match ? '' : 'none';
            });
            // Open alle groepen bij zoeken
            if (q) {
                document.querySelectorAll('.tree-group').forEach(g => g.classList.remove('collapsed'));
            }
        });
    },

    async renderTree() {
        const manifest = await DataLoader.loadManifest();
        const tree = document.getElementById('sidebar-tree');
        tree.innerHTML = '';

        // Boekvolgorde uit gebruikersopties (canoniek / tenach / chronologisch / auteur / lengte)
        const mode = (typeof Opties !== 'undefined' && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
        const bookOrder = getBookOrderGroups(mode, manifest);

        // Maak een lookup van book id -> book object
        const bookById = {};
        for (const b of manifest.books) {
            bookById[b.id] = b;
        }

        const groups = Object.entries(bookOrder).map(([label, ids]) => ({
            label,
            books: ids.map(id => bookById[id]).filter(Boolean)
        }));

        // Voeg eventuele ontbrekende boeken toe aan de juiste groep
        const assignedIds = new Set(Object.values(bookOrder).flat());
        const unassigned = manifest.books.filter(b => !assignedIds.has(b.id) &&
            isBookVisibleInNavigation(b));
        if (unassigned.length > 0) {
            groups.push({ label: 'Overig', books: unassigned });
        }

        for (const group of groups) {
            const books = group.books;
            if (books.length === 0) continue;

            const groupEl = document.createElement('div');
            // De apocriefen staan standaard dicht: zestien boeken, met de
            // Ethiopische er nog onder, die de canon anders uit beeld duwen.
            // Zoeken klapt alle groepen weer open.
            groupEl.className = group.label === 'Apocriefen' ? 'tree-group collapsed' : 'tree-group';

            const labelEl = document.createElement('div');
            labelEl.className = 'tree-group-label';
            labelEl.innerHTML = `<span class="arrow">▼</span> ${group.label} <span style="opacity:0.4;font-size:10px;">(${books.length})</span>`;
            labelEl.addEventListener('click', () => {
                groupEl.classList.toggle('collapsed');
            });
            groupEl.appendChild(labelEl);

            const booksContainer = document.createElement('div');
            booksContainer.className = 'tree-books';

            const ethSet = new Set(window.ETHIOPIC_BOOKS);
            let ethHeaderDone = false;
            for (const book of books) {
                // Sub-kop vóór het eerste Ethiopische boek (subcategorie binnen Apocriefen)
                if (!ethHeaderDone && ethSet.has(book.id)) {
                    const sub = document.createElement('div');
                    sub.className = 'tree-subgroup-label';
                    sub.textContent = window.ETHIOPIC_GROUP_LABEL;
                    booksContainer.appendChild(sub);
                    ethHeaderDone = true;
                }
                const bookEl = document.createElement('div');
                bookEl.className = 'tree-book collapsed'; // standaard ingeklapt
                bookEl.dataset.name = book.nameDutch;
                bookEl.dataset.bookId = book.id;

                const bookLabel = document.createElement('div');
                bookLabel.className = 'tree-book-label';
                bookLabel.innerHTML = `<span class="arrow">▼</span> ${book.nameDutch}`;
                bookLabel.addEventListener('click', (e) => {
                    // Toggle open/dicht
                    bookEl.classList.toggle('collapsed');
                    // Als net geopend, navigeer naar eerste hoofdstuk
                    if (!bookEl.classList.contains('collapsed') && book.chaptersIncluded.length > 0) {
                        location.hash = `#${book.id}/${book.chaptersIncluded[0]}`;
                    }
                });
                bookEl.appendChild(bookLabel);

                // Hoofdstuk-knoppen
                const chaptersEl = document.createElement('div');
                chaptersEl.className = 'tree-chapters';

                for (const ch of book.chaptersIncluded) {
                    const btn = document.createElement('button');
                    btn.className = 'tree-ch-btn';
                    btn.textContent = ch;
                    btn.dataset.bookId = book.id;
                    btn.dataset.chapter = ch;
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        location.hash = `#${book.id}/${ch}`;
                    });
                    chaptersEl.appendChild(btn);
                }

                bookEl.appendChild(chaptersEl);
                booksContainer.appendChild(bookEl);
            }

            groupEl.appendChild(booksContainer);
            tree.appendChild(groupEl);
        }
    },

    updateActive(bookId, chapter) {
        // Boek-labels
        document.querySelectorAll('.tree-book-label').forEach(el => {
            const bookEl = el.parentElement;
            const isActive = bookEl.dataset.bookId === bookId;
            el.classList.toggle('active', isActive);
            // Open het actieve boek
            if (isActive) {
                bookEl.classList.remove('collapsed');
            }
        });

        // Hoofdstuk-knoppen
        document.querySelectorAll('.tree-ch-btn').forEach(btn => {
            const isActive = btn.dataset.bookId === bookId && parseInt(btn.dataset.chapter) === chapter;
            btn.classList.toggle('active', isActive);
        });

        // Scroll actief boek in view
        const activeLabel = document.querySelector('.tree-book-label.active');
        if (activeLabel) {
            activeLabel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    },

    async markApprovedChapters(bookId) {
        const book = await DataLoader.loadBook(bookId);
        if (!book) return;

        for (const chapter of book.chapters) {
            if (chapter.verses.length > 0) {
                const allFinal = chapter.verses.every(v => v.status === 'final');
                if (allFinal) {
                    const btn = document.querySelector(`.tree-ch-btn[data-book-id="${bookId}"][data-chapter="${chapter.number}"]`);
                    if (btn) btn.classList.add('approved');
                }
            }
        }
    }
};
