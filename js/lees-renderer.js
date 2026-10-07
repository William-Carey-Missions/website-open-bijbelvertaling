/* Reader presentation, shared through the main controller object. */
const LeesRenderer = {
    updateHeading(book, chapterNum) {
        // Heading — concept-marker bij niet-geverifieerde hoofdstukken
        const headingEl = document.getElementById('chapter-heading');
        const isVerified = this._isVerified(this.currentBook, chapterNum);
        VerificationDisplay.title(headingEl, `${book.nameDutch} ${chapterNum}`,
            isVerified || !Verification.textVisible(this.currentBook, chapterNum));
    },
    async _updateDatingBox(book) {
        if (this._bookDating === undefined) {
            this._bookDating = null;
            try { this._bookDating = await this.fetchJSON('/data/book-dating.json'); }
            catch (e) { this._bookDating = {}; }
        }
        const d = this._bookDating && this._bookDating[book.id];
        let box = document.getElementById('book-dating');
        if (!box) {
            box = document.createElement('div');
            box.id = 'book-dating';
            box.className = 'book-dating';
            const heading = document.getElementById('chapter-heading');
            if (heading && heading.parentNode) heading.parentNode.insertBefore(box, heading.nextSibling);
        }
        const handschriftenUrl = KASites.url('ogw', `handschriften/${encodeURIComponent(book.id)}.html`);
        const handschriftenTitel = 'Open de handschriftenpagina met oudste fragment, vindgeschiedenis en scans';
        const parts = [];
        if (d && (d.schrijftijdKort || d.schrijftijd)) parts.push(`<a class="dating-link" href="${handschriftenUrl}" title="${handschriftenTitel}"><span class="dating-label">Schrijftijd:</span> ${d.schrijftijdKort || d.schrijftijd}</a>`);
        // Alleen het jaartal van het oudste handschrift tonen (geen siglum/nummer); details staan op de handschriftenpagina.
        const oudsteJaar = d && (d.oudsteDatum || d.oudsteHandschrift);
        if (oudsteJaar) parts.push(`<a class="dating-link" href="${handschriftenUrl}" title="${handschriftenTitel}"><span class="dating-label">Oudste handschrift:</span> ${String(oudsteJaar).split(' (')[0]}</a>`);
        box.innerHTML = '<img class="dating-icon" src="images/iconen/instellingen/oudste-handschrift.png" alt="" aria-hidden="true">' + parts.join(' &nbsp;·&nbsp; ');
        box.style.display = 'block';
    },

    _updateEthiopicBanner(book) {
        const isEth = book && (book.testament === 'ET' || (window.ETHIOPIC_BOOKS && window.ETHIOPIC_BOOKS.includes(book.id)));
        const isApoc = book && book.testament === 'AP';
        let banner = document.getElementById('ethiopic-banner');
        // Alleen de apocriefe boeken krijgen een waarschuwing; de Ethiopische boeken niet meer.
        if (isEth || !isApoc) { if (banner) banner.style.display = 'none'; return; }
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'ethiopic-banner';
            banner.className = 'ethiopic-banner';
            const versesEl = document.getElementById('verses');
            if (versesEl && versesEl.parentNode) versesEl.parentNode.insertBefore(banner, versesEl);
        }
        banner.innerHTML = '<strong>⚠ Apocrief boek - geen onderdeel van de canon van Gods Woord</strong>';
        banner.style.display = 'block';
    },

    async updateAudioPlayer(bookId, book, chapter) {
        const audioEl = document.getElementById('audio-el');
        const playBtn = document.getElementById('audio-play-big');
        const voiceBtn = document.getElementById('audio-voice');
        const label   = document.getElementById('reader-footer-label');
        if (!audioEl || !playBtn) return;

        if (label) label.textContent = `${(book && book.nameDutch) || bookId} ${chapter}`;
        try { audioEl.pause(); } catch (e) {}

        // Onthoud huidig hoofdstuk zodat de stem-toggle dezelfde audio herlaadt
        this._audioBookId = bookId;
        this._audioChapter = chapter;

        const ov = window.OV_AUDIO;
        if (!ov || !ov.available(bookId, chapter)) {
            playBtn.classList.add('hidden');
            if (voiceBtn) voiceBtn.classList.add('hidden');
            audioEl.removeAttribute('src');
            return;
        }
        audioEl.src = ov.src(bookId, chapter);
        playBtn.classList.remove('is-playing');
        playBtn.classList.remove('hidden');
        if (voiceBtn) {
            voiceBtn.classList.remove('hidden');
            voiceBtn.textContent = ov.label();
        }

        // Probeer chunk-audio (optionele godsnaam/kopjes/intro). Geen manifest → losse MP3 blijft.
        this._setupChunks(bookId, chapter);
    },

    // Laad een chunk-manifest en stuur de speler daarmee aan. Geen manifest →
    // niets doen (de losse-MP3-bron in updateAudioPlayer blijft actief).
    async _setupChunks(bookId, chapter) {
        if (this._chunkCtl) { try { this._chunkCtl.destroy(); } catch (e) {} this._chunkCtl = null; }
        this._updateChunkSettingsUI(false);
        if (!window.ChunkedAudio || !window.OV_AUDIO) return;
        const voice = OV_AUDIO.getVoice ? OV_AUDIO.getVoice() : 'm';
        const manifest = await ChunkedAudio.load(bookId, chapter, voice);
        // Hoofdstuk kan intussen gewisseld zijn → verouderde load negeren.
        if (!manifest || this._audioBookId !== bookId || this._audioChapter !== chapter) return;
        const audioEl = document.getElementById('audio-el');
        if (!audioEl) return;
        const settings = ChunkedAudio.defaultSettings();
        this._chunkCtl = ChunkedAudio.createController(audioEl, manifest, settings, {
            onVerse: (n) => { this._highlightAudioVerse && this._highlightAudioVerse(n); }
        });
        this._updateChunkSettingsUI(true);
    },

    // Injecteer (eenmalig) een tandwiel-knop + paneel naast de stem-knop, en
    // toon/verberg het al naar gelang er chunk-audio beschikbaar is.
    _updateChunkSettingsUI(available) {
        const voiceBtn = document.getElementById('audio-voice');
        let btn = document.getElementById('audio-settings-btn');
        if (!available) { if (btn) btn.classList.add('hidden'); this._closeChunkPanel && this._closeChunkPanel(); return; }
        if (!btn) {
            btn = document.createElement('button');
            btn.id = 'audio-settings-btn';
            btn.className = 'audio-settings-btn';
            btn.type = 'button';
            btn.title = 'Voorlees-instellingen (godsnaam, kopjes)';
            btn.setAttribute('aria-label', 'Voorlees-instellingen');
            btn.textContent = '⚙';
            if (voiceBtn && voiceBtn.parentNode) voiceBtn.parentNode.insertBefore(btn, voiceBtn.nextSibling);
            else document.body.appendChild(btn);
            btn.addEventListener('click', (e) => { e.stopPropagation(); this._toggleChunkPanel(); });
        }
        btn.classList.remove('hidden');
    },

    _toggleChunkPanel() {
        let panel = document.getElementById('audio-settings-panel');
        if (panel) { this._closeChunkPanel(); return; }
        const s = ChunkedAudio.defaultSettings();
        panel = document.createElement('div');
        panel.id = 'audio-settings-panel';
        panel.className = 'audio-settings-panel';
        panel.innerHTML =
            '<div class="asp-row"><span class="asp-label">Godsnaam voorlezen</span>' +
            '<div class="asp-seg" role="group">' +
              ['heere', 'jahweh', 'jehova'].map(k =>
                `<button type="button" data-god="${k}" class="${s.divineName === k ? 'on' : ''}">${k === 'heere' ? 'HEERE' : (k === 'jahweh' ? 'JAHWEH' : 'Jehova')}</button>`).join('') +
            '</div></div>' +
            `<label class="asp-check"><input type="checkbox" data-opt="headings" ${s.headings ? 'checked' : ''}> Kopjes voorlezen</label>` +
            `<label class="asp-check"><input type="checkbox" data-opt="announce" ${s.announce ? 'checked' : ''}> Boeknaam + hoofdstuk aankondigen</label>`;
        const btn = document.getElementById('audio-settings-btn');
        (btn && btn.parentNode ? btn.parentNode : document.body).appendChild(panel);

        panel.querySelectorAll('[data-god]').forEach(b => b.addEventListener('click', () => {
            const cur = ChunkedAudio.defaultSettings();
            cur.divineName = b.getAttribute('data-god');
            panel.querySelectorAll('[data-god]').forEach(x => x.classList.toggle('on', x === b));
            this._applyChunkSettings(cur);
        }));
        panel.querySelectorAll('[data-opt]').forEach(cbx => cbx.addEventListener('change', () => {
            const cur = ChunkedAudio.defaultSettings();
            cur[cbx.getAttribute('data-opt')] = cbx.checked;
            this._applyChunkSettings(cur);
        }));
        this._closeChunkPanel = () => { const p = document.getElementById('audio-settings-panel'); if (p) p.remove(); document.removeEventListener('click', this._chunkPanelOutside); };
        this._chunkPanelOutside = (ev) => { const p = document.getElementById('audio-settings-panel'); if (p && !p.contains(ev.target) && ev.target.id !== 'audio-settings-btn') this._closeChunkPanel(); };
        setTimeout(() => document.addEventListener('click', this._chunkPanelOutside), 0);
    },

    _applyChunkSettings(settings) {
        ChunkedAudio.saveSettings(settings);
        if (this._chunkCtl) this._chunkCtl.setSettings(settings);
    },

    setupAudioPlayer() {
        const audioEl = document.getElementById('audio-el');
        const playBtn = document.getElementById('audio-play-big');
        const voiceBtn = document.getElementById('audio-voice');
        if (!audioEl || !playBtn) return;

        playBtn.addEventListener('click', () => {
            if (audioEl.paused) audioEl.play();
            else audioEl.pause();
        });
        audioEl.addEventListener('play', () => {
            playBtn.classList.add('is-playing');
            playBtn.setAttribute('aria-label', 'Pauzeer voorlezing');
        });
        audioEl.addEventListener('pause', () => {
            playBtn.classList.remove('is-playing');
            playBtn.setAttribute('aria-label', 'Speel voorlezing af');
        });

        // Stem-toggle (man/vrouw): wissel bron, behoud positie + afspeelstatus
        if (voiceBtn) {
            voiceBtn.addEventListener('click', () => {
                const ov = window.OV_AUDIO;
                if (!ov || this._audioBookId == null) return;
                const wasPlaying = !audioEl.paused;
                ov.toggleVoice();
                voiceBtn.textContent = ov.label();

                // Chunk-modus: manifest voor de nieuwe stem herladen, plek behouden.
                if (this._chunkCtl) {
                    const verse = this._chunkCtl.currentVerse();
                    this._setupChunks(this._audioBookId, this._audioChapter).then(() => {
                        if (this._chunkCtl) {
                            if (verse != null) this._chunkCtl.seekToVerse(verse);
                            if (wasPlaying) this._chunkCtl.play();
                        }
                    });
                    return;
                }

                const pos = audioEl.currentTime || 0;
                audioEl.src = ov.src(this._audioBookId, this._audioChapter);
                audioEl.addEventListener('loadedmetadata', function once() {
                    audioEl.removeEventListener('loadedmetadata', once);
                    try { audioEl.currentTime = Math.min(pos, audioEl.duration || pos); } catch (e) {}
                    if (wasPlaying) audioEl.play();
                });
            });
        }
    },

    renderChapterButtons(book) {
        const container = document.getElementById('chapter-buttons');
        container.innerHTML = '';
        const chapters = book.chapters.map(c => c.number);
        for (const ch of chapters) {
            const btn = document.createElement('button');
            btn.textContent = ch;
            btn.classList.toggle('active', ch === this.currentChapter);
            btn.classList.toggle('unverified', !this._isVerified(this.currentBook, ch));
            btn.title = this._isVerified(this.currentBook, ch) ? '' : 'Concept — nog niet handmatig gecontroleerd';
            btn.addEventListener('click', () => {
                location.hash = `#${this.currentBook}/${ch}`;
            });
            container.appendChild(btn);
        }
    },

    async renderChapter(book, chapterNum) {
        await Lees._laadVerified();
        this._bookObj = book;   // bewaren voor o.a. de Arabisch-toggle-herrender
        // Verzen zitten in een apart per-hoofdstuk-bestand (post chapter-split)
        let chapter = book.chapters.find(c => c.number === chapterNum);
        if (chapter && (!chapter.verses || chapter.verses.length === 0)) {
            try {
                const ch = await this.loadChapter(book.id || this.currentBook, chapterNum);
                if (ch && ch.verses) {
                    chapter = Object.assign({}, chapter, ch);
                } else {
                    chapter.verses = [];
                }
            } catch (e) {
                console.warn('loadChapter mislukt:', e);
                chapter.verses = [];
            }
        }
        if (!chapter) return;

        this.updateHeading(book, chapterNum);

        // Book intro (only chapter 1)
        const introEl = document.getElementById('book-intro');
        if (chapterNum === 1 && book.bookIntro && book.bookIntro.text2026) {
            introEl.innerHTML = `
                <span class="book-intro-label">Boekinleiding</span>
                <div class="book-intro-text">${book.bookIntro.text2026}</div>`;
            introEl.classList.remove('hidden');
            introEl.classList.add('collapsed');
            introEl.onclick = () => introEl.classList.toggle('collapsed');
        } else {
            introEl.classList.add('hidden');
        }

        // Chapter intro
        const chIntroEl = document.getElementById('chapter-intro');
        const chIntro = chapter.chapterIntro;
        if (chIntro && typeof chIntro === 'object' && chIntro.text2026) {
            chIntroEl.textContent = chIntro.text2026;
            chIntroEl.style.display = '';
        } else {
            chIntroEl.style.display = 'none';
        }

        // Parallelle vertalingen (optioneel, per boek geladen en gecached)
        const bidP = book.id || this.currentBook;
        const parallels = [];
        this._parCache = this._parCache || {};
        for (const cfg of Lees.PARALLEL) {
            if (localStorage.getItem(cfg.ls) !== '1') continue;
            try {
                const ck = cfg.dir + '/' + bidP;
                if (!(ck in this._parCache)) {
                    this._parCache[ck] = await fetch('data/' + cfg.dir + '/' + bidP + '.json').then(r => r.ok ? r.json() : null).catch(() => null);
                }
                const data = this._parCache[ck];
                const chData = data ? (data[String(chapterNum)] || null) : null;
                if (chData) parallels.push({ cfg, chData });
            } catch (e) { /* skip */ }
        }

        // Verses
        const versesEl = document.getElementById('verses');
        versesEl.innerHTML = '';
        for (const verse of chapter.verses) {
            const span = document.createElement('span');
            span.className = 'verse-span';
            span.dataset.verse = verse.number;

            // Verse number
            const num = document.createElement('span');
            num.className = 'verse-num';
            num.textContent = verse.number;
            span.appendChild(num);

            // Verse text (use text2026_html which has god-speaks + note-markers)
            const textNode = document.createElement('span');
            textNode.className = 'verse-text';
            const html = verse.text2026_html || verse.text2026 || '';
            textNode.innerHTML = this.wrapWordsWithStrongs(html, verse.woordnummers);
            span.appendChild(textNode);
            // Parallelle vertalingen onder het vers
            for (const par of parallels) {
                const t = par.chData[String(verse.number)];
                if (!t) continue;
                const pl = document.createElement('div');
                pl.className = 'verse-parallel verse-' + par.cfg.key;
                pl.setAttribute('lang', par.cfg.lang);
                if (par.cfg.rtl) pl.setAttribute('dir', 'rtl');
                pl.textContent = t;
                span.appendChild(pl);
            }

            // Versnummer-klik = navigatie/note-popup behavior (bestaande gedrag)
            num.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleVerseClick(e, verse.number);
            });

            // Klik op vers-tekst → selecteer de hele vers-tekst (browser-native via Range API).
            // Dit triggert selectionchange → toolbar onderin verschijnt.
            // Skip note-markers / strong's / begrip-links — die hebben eigen acties.
            // Drag-select (>5px verplaatsing) wordt niet overruled — gebruiker kan nog steeds
            // een woord/zin slepen.
            let downX = 0, downY = 0;
            span.addEventListener('pointerdown', (e) => {
                downX = e.clientX; downY = e.clientY;
            });
            span.addEventListener('pointerup', (e) => {
                if (e.target.closest('.note-marker, .strongs-inline, a, .begrip-link, .verse-num')) return;
                const moved = Math.hypot(e.clientX - downX, e.clientY - downY);
                if (moved > 5) return; // user drag-selecteerde een sub-stuk
                // Selecteer de hele vers-tekst programmatisch
                const textEl = span.querySelector('.verse-text');
                if (!textEl) return;
                const sel = window.getSelection();
                if (!sel) return;
                sel.removeAllRanges();
                const range = document.createRange();
                range.selectNodeContents(textEl);
                sel.addRange(range);
                // selectionchange-listener triggert vanzelf en toont toolbar
            });

            // Space between verses
            span.appendChild(document.createTextNode(' '));

            versesEl.appendChild(span);
        }

        // Attach note-marker click handlers
        versesEl.querySelectorAll('.note-marker').forEach(marker => {
            marker.addEventListener('click', (e) => {
                e.preventDefault();
                const verseNum = parseInt(marker.closest('.verse-span')?.dataset.verse);
                const noteId = marker.dataset.note;
                this.showNotes(chapter, verseNum, noteId);
            });
        });
        Verification.readerRendered(this.currentBook, chapterNum, true, chapter._verificationSourceHash);
    },

    wrapWordsWithStrongs(html, woordnummers) {
        if (!this.wordNumbersEnabled() || !window.OVWoordnummers) return html;
        return window.OVWoordnummers.renderInline(html, woordnummers || []);
    },

    wordNumbersEnabled() {
        try {
            const state = JSON.parse(localStorage.getItem('sv2026_vertaalopties') || '{}');
            return state.strongs === 'aan';
        } catch (e) {
            return false;
        }
    },
};
