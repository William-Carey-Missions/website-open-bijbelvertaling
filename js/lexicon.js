/* Open Vertaling — Lexicon tooltip integratie */

const Lexicon = {
    currentTooltip: null,
    lastTrigger: null,
    strongsSheetSizeKey: 'ov-strongs-sheet-size',

    hoverTooltip: null,
    hoverTimeout: null,

    // Nederlandse vertaal-overlay (glossNl/definitieNl), lui geladen per taal
    _nl: { hebrew: null, greek: null },

    TBESG_BOOKS: {
        Gen: 'genesis', Exo: 'exodus', Lev: 'leviticus', Num: 'numeri', Deu: 'deuteronomium', Jos: 'jozua',
        Jdg: 'richteren', Rut: 'ruth', '1Sa': '1samuel', '2Sa': '2samuel', '1Ki': '1koningen', '2Ki': '2koningen',
        '3Ki': '1koningen', '4Ki': '2koningen', '1Ch': '1kronieken', '2Ch': '2kronieken', Ezr: 'ezra', Neh: 'nehemia',
        Est: 'esther', Job: 'job', Psa: 'psalmen', Pro: 'spreuken', Ecc: 'prediker', Sng: 'hooglied', Isa: 'jesaja',
        Jer: 'jeremia', Lam: 'klaagliederen', Ezk: 'ezechiel', Dan: 'daniel', Hos: 'hosea', Jol: 'joel', Amo: 'amos',
        Oba: 'obadja', Jon: 'jona', Mic: 'micha', Nah: 'nahum', Hab: 'habakuk', Zep: 'zefanja', Hag: 'haggai', Zec: 'zacharia', Mal: 'maleachi',
        Mat: 'mattheus', Mrk: 'markus', Luk: 'lukas', Jhn: 'johannes', Act: 'handelingen', Rom: 'romeinen',
        '1Co': '1korinthiers', '2Co': '2korinthiers', Gal: 'galaten', Eph: 'efeziers', Php: 'filippenzen', Phil: 'filippenzen', Col: 'kolossenzen',
        '1Th': '1tessalonicensen', '2Th': '2tessalonicensen', '1Ti': '1timotheus', '1Tim': '1timotheus', Tim: '1timotheus', '2Ti': '2timotheus', Tit: 'titus',
        Heb: 'hebreeen', Jas: 'jakobus', '1Pe': '1petrus', '1Pet': '1petrus', '2Pe': '2petrus', '1Jn': '1johannes', '1Jo': '1johannes', '2Jn': '2johannes', '3Jn': '3johannes', Jude: 'judas', Rev: 'openbaring',
        '1Es': '3ezra', '2Es': '4ezra', Tob: 'tobit', Jdt: 'judith', Wis: 'boekderwijsheid', Sir: 'jezussirach', Bar: 'baruch', '1Ma': '1makkabeeen', '1Mac': '1makkabeeen', '2Ma': '2makkabeeen', '2Mac': '2makkabeeen', '3Ma': '3makkabeeen', '3Mac': '3makkabeeen', Man: 'gebedvanmanasse', Sus: 'susanna', Bel: 'belenddedraak'
    },

    _bookNames: null,
    async ensureBookNames() {
        if (this._bookNames) return this._bookNames;
        try {
            const response = await fetch('data/books.json');
            const data = response.ok ? await response.json() : { books: [] };
            this._bookNames = Object.fromEntries((data.books || []).map(book => [book.id, book.nameDutch || book.id]));
        } catch (error) {
            this._bookNames = {};
        }
        return this._bookNames;
    },

    linkifyTbesgDefinition(definition, names) {
        return String(definition || '').replace(/<ref='([^']+)'>([^<]*)<\/ref>/g, (_match, attribute, text) => {
            const parts = String(attribute).replace(/\.$/, '').split('.');
            const bookId = this.TBESG_BOOKS[parts[0]];
            if (!bookId || !parts[1]) return text || '';
            const label = `${names[bookId] || bookId} ${parts[1]}:${parts[2] || ''}`;
            const href = `index.html#${bookId}/${parts[1]}/${parts[2] || ''}`;
            return `<a href="${href}">${this.escapeHtml(label)}</a>`;
        });
    },
    async ensureNl(lang) {
        if (this._nl[lang]) return this._nl[lang];
        const url = lang === 'hebrew' ? '/data/lexicon-nl/bdb-nl.json' : '/data/lexicon-nl/tbesg-nl.json';
        try {
            const r = await fetch(url);
            this._nl[lang] = r.ok ? await r.json() : {};
        } catch (e) { this._nl[lang] = {}; }
        return this._nl[lang];
    },

    init() {
        if (this._initialized) return;
        this._initialized = true;
        // Klik: toon uitgebreide lexicon-entry
        document.addEventListener('click', (e) => {
            // Klik op grondtekst-woord
            const wordEl = e.target.closest('.strongs-word');
            if (wordEl) {
                e.stopPropagation();
                this.hideHover();
                this.showEntry(wordEl);
                return;
            }
            // Klik op inline Strong's nummer (blauw superscript)
            const inlineEl = e.target.closest('.strongs-inline');
            if (inlineEl) {
                e.stopPropagation();
                const strongs = inlineEl.dataset.strongs || inlineEl.textContent.trim().replace(/[<>]/g, '');
                if (strongs) {
                    this.showEntryByStrongs(strongs, inlineEl);
                }
                return;
            }
            if (this.currentTooltip && !e.target.closest('.lexicon-tooltip, .strongs-sheet-panel')) {
                this.hideTooltip();
            }
        });

        // Hover: toon korte tooltip met woord + betekenis + highlight NL tekst
        document.addEventListener('mouseover', (e) => {
            const wordEl = e.target.closest('.strongs-word');
            if (wordEl && !this.currentTooltip) {
                clearTimeout(this.hoverTimeout);
                this.hoverTimeout = setTimeout(() => {
                    this.showHover(wordEl);
                    this.highlightVerseWord(wordEl);
                }, 200);
            }
        });
        document.addEventListener('mouseout', (e) => {
            const wordEl = e.target.closest('.strongs-word');
            if (wordEl) {
                clearTimeout(this.hoverTimeout);
                this.hideHover();
                this.clearHighlights();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentTooltip) {
                e.preventDefault();
                this.hideTooltip(true);
            }
        });
    },

    showHover(wordEl) {
        this.hideHover();
        const strongs = wordEl.dataset.strongs;
        if (!strongs) return;

        const woord = wordEl.textContent;
        const transliteratie = wordEl.dataset.transliteratie || '';
        const gloss = wordEl.dataset.gloss || '';

        if (!transliteratie && !gloss) return;

        const tip = document.createElement('div');
        tip.className = 'word-hover-tooltip';
        tip.innerHTML = `<strong>${woord}</strong>` +
            (transliteratie ? ` <span class="wht-translit">${transliteratie}</span>` : '') +
            (gloss ? `<br><span class="wht-gloss">${gloss}</span>` : '') +
            `<br><span class="wht-strongs">${strongs}</span>`;

        document.body.appendChild(tip);
        this.hoverTooltip = tip;

        const rect = wordEl.getBoundingClientRect();
        let left = rect.left;
        let top = rect.top - tip.offsetHeight - 6;
        if (top < 5) top = rect.bottom + 6;
        if (left + tip.offsetWidth > window.innerWidth - 10) {
            left = window.innerWidth - tip.offsetWidth - 10;
        }
        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
    },

    hideHover() {
        if (this.hoverTooltip) {
            this.hoverTooltip.remove();
            this.hoverTooltip = null;
        }
    },

    async showEntry(wordEl) {
        const strongs = wordEl.dataset.strongs;
        if (!strongs) return;
        return this.showEntryByStrongs(strongs, wordEl);
    },

    async showEntryByStrongs(strongs, anchorEl) {
        this.hideTooltip();

        const family = window.OVWoordnummers
            ? window.OVWoordnummers.familyOf(strongs)
            : (/^H\d+[A-Za-z]?$/.test(strongs) ? 'H' : (/^G\d+[A-Za-z]?$/.test(strongs) ? 'G' : null));
        if (!family) return;

        const taal = family === 'H' ? 'hebreeuws'
            : family === 'G' ? 'grieks'
                : family === 'OVL' ? 'latijn' : 'geez';
        // Het volledige woordenboek staat op Open Gods Woord.
        const fullLink = KASites.url('ogw', `lexicon-viewer.html?taal=${taal}&entry=${encodeURIComponent(strongs)}`);
        const articleLink = `${fullLink}&embed=1`;

        const sheet = document.createElement('div');
        sheet.id = 'strongs-sheet';
        sheet.className = 'strongs-sheet';
        sheet.setAttribute('role', 'dialog');
        sheet.setAttribute('aria-modal', 'true');
        sheet.setAttribute('aria-labelledby', 'strongs-sheet-number');
        sheet.innerHTML = `
            <section class="strongs-sheet-panel">
                <div class="strongs-sheet-handle" aria-hidden="true"></div>
                <div class="strongs-sheet-resize-handle" role="separator"
                    aria-label="Woordenboekvenster groter of kleiner maken"
                    aria-orientation="vertical"></div>
                <header class="strongs-sheet-header">
                    <div>
                        <span id="strongs-sheet-number" class="lexicon-strongs">${this.escapeHtml(strongs)}</span>
                        <span class="lexicon-source">Woordenboekartikel</span>
                    </div>
                    <div class="strongs-sheet-actions">
                        <a class="strongs-sheet-full-link" href="${this.escapeHtml(fullLink)}">Open op volledige pagina</a>
                        <button type="button" class="strongs-sheet-close" aria-label="Woordenboek sluiten">×</button>
                    </div>
                </header>
                <iframe id="strongs-sheet-article" class="strongs-sheet-article"
                    src="${this.escapeHtml(articleLink)}"
                    title="Woordenboekartikel ${this.escapeHtml(strongs)}"></iframe>
            </section>`;

        sheet.addEventListener('click', (event) => {
            if (event.target === sheet) this.hideTooltip(true);
        });
        sheet.addEventListener('keydown', (event) => {
            if (event.key !== 'Tab') return;
            const focusable = [...sheet.querySelectorAll('button:not([disabled]), a[href]')];
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });
        sheet.querySelector('.strongs-sheet-close').addEventListener('click', () => this.hideTooltip(true));
        document.body.appendChild(sheet);
        this.setupStrongSheetResize(sheet.querySelector('.strongs-sheet-panel'));
        document.body.classList.add('strongs-sheet-open');
        this.currentTooltip = sheet;
        this.lastTrigger = anchorEl;
        sheet.querySelector('.strongs-sheet-close').focus();
    },

    strongSheetBounds(width, height) {
        const viewportMargin = 20;
        const maxWidth = Math.max(320, window.innerWidth - (viewportMargin * 2));
        const maxHeight = Math.max(320, window.innerHeight - (viewportMargin * 2));
        return {
            width: Math.min(maxWidth, Math.max(560, Number(width) || 760)),
            height: Math.min(maxHeight, Math.max(420, Number(height) || window.innerHeight * 0.5))
        };
    },

    setupStrongSheetResize(panel) {
        if (!panel || window.matchMedia('(max-width: 768px)').matches) return;

        let stored = null;
        try {
            stored = JSON.parse(localStorage.getItem(this.strongsSheetSizeKey));
        } catch (_error) {
            stored = null;
        }
        const initial = this.strongSheetBounds(stored && stored.width, stored && stored.height);
        panel.style.width = `${initial.width}px`;
        panel.style.height = `${initial.height}px`;

        const handle = panel.querySelector('.strongs-sheet-resize-handle');
        if (!handle) return;
        handle.addEventListener('pointerdown', (event) => {
            event.preventDefault();
            const start = panel.getBoundingClientRect();
            const startX = event.clientX;
            const startY = event.clientY;
            panel.classList.add('is-resizing');
            handle.setPointerCapture(event.pointerId);

            const move = (moveEvent) => {
                const next = this.strongSheetBounds(
                    start.width + ((moveEvent.clientX - startX) * 2),
                    start.height - (moveEvent.clientY - startY)
                );
                panel.style.width = `${next.width}px`;
                panel.style.height = `${next.height}px`;
            };
            const stop = () => {
                handle.removeEventListener('pointermove', move);
                handle.removeEventListener('pointerup', stop);
                handle.removeEventListener('pointercancel', stop);
                panel.classList.remove('is-resizing');
                const size = panel.getBoundingClientRect();
                localStorage.setItem(this.strongsSheetSizeKey, JSON.stringify({
                    width: Math.round(size.width),
                    height: Math.round(size.height)
                }));
            };
            handle.addEventListener('pointermove', move);
            handle.addEventListener('pointerup', stop);
            handle.addEventListener('pointercancel', stop);
        });
    },

    escapeHtml(value) {
        const span = document.createElement('span');
        span.textContent = String(value == null ? '' : value);
        return span.innerHTML;
    },

    sanitizeDefinition(html) {
        const template = document.createElement('template');
        template.innerHTML = String(html || 'Geen woordenboekdefinitie beschikbaar.');
        const allowed = new Set(['B', 'STRONG', 'I', 'EM', 'BR', 'P', 'DIV', 'UL', 'OL', 'LI', 'SUP', 'SUB', 'SPAN', 'A']);
        [...template.content.querySelectorAll('*')].forEach(node => {
            if (!allowed.has(node.tagName)) {
                node.replaceWith(...node.childNodes);
                return;
            }
            if (node.tagName === 'A') {
                // Alleen door ons gemaakte, interne Schriftverwijzingen mogen
                // als link in een woordenboekdefinitie blijven staan.
                const href = node.getAttribute('href') || '';
                if (!/^index\.html#[a-z0-9]+\/\d+\/\d+$/i.test(href)) {
                    node.replaceWith(...node.childNodes);
                    return;
                }
                [...node.attributes].forEach(attribute => {
                    if (attribute.name !== 'href') node.removeAttribute(attribute.name);
                });
                return;
            }
            [...node.attributes].forEach(attribute => node.removeAttribute(attribute.name));
        });
        return template.innerHTML;
    },

    hideTooltip(restoreFocus = false) {
        if (this.currentTooltip) {
            this.currentTooltip.remove();
            this.currentTooltip = null;
        }
        document.body.classList.remove('strongs-sheet-open');
        if (restoreFocus && this.lastTrigger && this.lastTrigger.isConnected) {
            this.lastTrigger.focus();
        }
        this.lastTrigger = null;
    },

    // --- Grondtekst ↔ NL koppeling ---

    highlightVerseWord(wordEl) {
        // Vind de verse-row waar dit woord bij hoort
        const row = wordEl.closest('.verse-row');
        if (!row) return;

        const strongs = wordEl.dataset.strongs;
        const gloss = wordEl.dataset.gloss || '';
        if (!strongs && !gloss) return;

        // Highlight de hele vers-cellen met een subtiele achtergrond
        const cells1637 = row.querySelector('.col-1637');
        const cells2026 = row.querySelector('.col-2026');
        const cellsSV1888 = row.querySelector('.col-marginSV1888');

        // Markeer het actieve grondtekstwoord
        wordEl.classList.add('strongs-active');

        // Probeer het Nederlandse equivalent te markeren via de gloss
        if (gloss) {
            const glossWords = gloss.toLowerCase().split(/[,;/]\s*/);
            [cells1637, cells2026].forEach(cell => {
                if (!cell) return;
                const text = cell.textContent;
                // Zoek naar elk glosswoord in de Nederlandse tekst
                glossWords.forEach(gw => {
                    if (gw.length < 2) return;
                    const regex = new RegExp(`(${gw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
                    if (regex.test(text)) {
                        // Voeg een highlight-klasse toe aan de cel
                        cell.classList.add('strongs-verse-highlight');
                    }
                });
            });
        }

        // Highlight ook alle andere grondtekstwoorden met dezelfde Strong's in dit vers
        row.querySelectorAll(`.strongs-word[data-strongs="${strongs}"]`).forEach(el => {
            el.classList.add('strongs-active');
        });
    },

    clearHighlights() {
        document.querySelectorAll('.strongs-active').forEach(el => {
            el.classList.remove('strongs-active');
        });
        document.querySelectorAll('.strongs-verse-highlight').forEach(el => {
            el.classList.remove('strongs-verse-highlight');
        });
    }
};

if (typeof window !== 'undefined') window.Lexicon = Lexicon;
