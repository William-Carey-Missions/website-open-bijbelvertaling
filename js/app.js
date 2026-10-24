/* Open Vertaling — Hoofdapplicatie */

const App = {
    // Alle kolom-keys in volgorde (num is altijd zichtbaar)
    ALL_COLS: ['1637', 'margin1637', 'sv1888', 'marginSV1888', '2026', 'margin2026', 'hebrew', 'diff', 'noteDiff'],

    _escapeStrongHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },


    // AUDIO_AVAILABLE leeft in js/audio-available.js (window.AUDIO_AVAILABLE) —
    // niet hier definieren. Wordt door de TTS-rollout-script bijgewerkt.

    // Alleen de Bijbeltekst; toevoegingen hebben een afzonderlijke beoordeling.
    VERIFIED_CHAPTERS: {},
    _verifiedGeladen: null,

    _laadVerified() { return Verification.loadChapters(App); },

    _isVerified(bookId, chapter) { return Verification.chapterVerified(App, bookId, chapter); },

    _updateVerifiedBanner(bookId, chapter) {
        VerificationDisplay.banner(bookId, chapter);
    },


    _updateAudioPlayer(bookId, chapter) {
        const playBtn = document.getElementById('audio-play-big');
        const playMob = document.getElementById('audio-play-mobile');
        const speedBtn = document.getElementById('audio-speed');
        const speedMob = document.getElementById('audio-speed-mobile');
        const scrubWrap = document.getElementById('audio-scrubber-wrap');
        const scrubMob = document.getElementById('audio-scrubber-mobile');
        const audioEl = document.getElementById('audio-el');
        // Containers ook hide-en zodat ze geen ruimte innemen op hoofdstukken zonder audio
        const chfCenter = playBtn ? playBtn.closest('.chf-center') : null;
        const mfnAudio = playMob ? playMob.closest('.mfn-audio') : null;
        const voiceBtn = document.getElementById('audio-voice');
        const voiceMob = document.getElementById('audio-voice-mobile');
        if (!audioEl) return;
        try { audioEl.pause(); } catch (e) {}

        // Onthoud huidig hoofdstuk voor de stem-toggle
        App._audioBookId = bookId;
        App._audioChapter = chapter;

        const ov = window.OV_AUDIO;
        const show = !!(ov && ov.available(bookId, chapter));
        const setHidden = (el, hide) => { if (el) el.classList.toggle('hidden', hide); };
        setHidden(playBtn, !show);
        setHidden(playMob, !show);
        setHidden(speedBtn, !show);
        setHidden(speedMob, !show);
        setHidden(scrubWrap, !show);
        setHidden(scrubMob, !show);
        setHidden(chfCenter, !show);
        setHidden(mfnAudio, !show);
        setHidden(voiceBtn, !show);
        setHidden(voiceMob, !show);
        if (!show) { audioEl.removeAttribute('src'); App._autoplayNext = false; return; }
        audioEl.src = ov.src(bookId, chapter);
        // Auto-doorspelen: na 'ended' navigeren we naar het volgende hoofdstuk;
        // zodra dat fragment geladen is, meteen verder afspelen.
        if (App._autoplayNext) {
            App._autoplayNext = false;
            audioEl.addEventListener('loadedmetadata', function once() {
                audioEl.removeEventListener('loadedmetadata', once);
                App._announceThenPlay(audioEl, chapter);
            });
        }
        if (voiceBtn) voiceBtn.textContent = ov.label();
        if (voiceMob) voiceMob.textContent = ov.label();
        if (playBtn) playBtn.classList.remove('is-playing');
        if (playMob) playMob.classList.remove('is-playing');
        // Reset scrubber
        const scrubber = document.getElementById('audio-scrubber');
        const cur = document.getElementById('audio-time-cur');
        const tot = document.getElementById('audio-time-tot');
        if (scrubber) scrubber.value = 0;
        if (cur) cur.textContent = '0:00';
        if (tot) tot.textContent = '0:00';
    },

    // Kondig "Hoofdstuk N" aan en start daarna de voorlezing.
    // Voorkeur: een vooraf gegenereerde clip in DEZELFDE stem
    // (audio/_announce/{m|v}/{n}.mp3). Niet aanwezig → browser-spraak als fallback.
    _announceThenPlay(audioEl, chapter) {
        const start = () => { try { audioEl.play().catch(() => {}); } catch (e) {} };
        if (chapter == null) { start(); return; }
        const voice = (window.OV_AUDIO && OV_AUDIO.getVoice) ? OV_AUDIO.getVoice() : 'v';
        let done = false;
        const once = (fn) => { if (!done) { done = true; fn(); } };
        try {
            const clip = new Audio(window.OV_ASSETS.url(`audio/_announce/${voice}/${chapter}.mp3`));
            clip.addEventListener('ended', () => once(start));
            clip.addEventListener('error', () => once(() => App._announceTTS(chapter, start)));
            clip.play().catch(() => once(() => App._announceTTS(chapter, start)));
        } catch (e) {
            once(() => App._announceTTS(chapter, start));
        }
    },

    // Fallback: spreek "Hoofdstuk N" uit via de browser-spraak, dan callback.
    _announceTTS(chapter, then) {
        let started = false;
        const go = () => { if (!started) { started = true; then(); } };
        try {
            const synth = window.speechSynthesis;
            if (synth && window.SpeechSynthesisUtterance) {
                const u = new SpeechSynthesisUtterance('Hoofdstuk ' + chapter);
                u.lang = 'nl-NL'; u.rate = 0.95;
                u.onend = go; u.onerror = go;
                synth.cancel(); synth.speak(u);
                setTimeout(go, 2500);
                return;
            }
        } catch (e) {}
        go();
    },

    _setupAudioPlayer() {
        const audioEl = document.getElementById('audio-el');
        const playBtn = document.getElementById('audio-play-big');
        const playMob = document.getElementById('audio-play-mobile');
        const speedBtn = document.getElementById('audio-speed');
        const speedMob = document.getElementById('audio-speed-mobile');
        const scrubber = document.getElementById('audio-scrubber');
        const curEl = document.getElementById('audio-time-cur');
        const totEl = document.getElementById('audio-time-tot');
        if (!audioEl || (!playBtn && !playMob)) return;
        if (audioEl._wired) return;
        audioEl._wired = true;

        const fmt = (sec) => {
            if (!isFinite(sec) || sec < 0) return '0:00';
            const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
            return `${m}:${s.toString().padStart(2, '0')}`;
        };

        // Play / pause — beide knoppen (desktop + mobile) wirelinen
        const togglePlay = () => {
            if (audioEl.paused) audioEl.play();
            else audioEl.pause();
        };
        if (playBtn) playBtn.addEventListener('click', togglePlay);
        if (playMob) playMob.addEventListener('click', togglePlay);
        const _curVoice = () => (window.OV_AUDIO && OV_AUDIO.getVoice) ? OV_AUDIO.getVoice() : 'v';
        audioEl.addEventListener('play', () => {
            if (playBtn) playBtn.classList.add('is-playing');
            if (playMob) playMob.classList.add('is-playing');
            // Tijdsbestand laden voor exacte versmarkering tijdens het voorlezen
            if (App._audioBookId != null) App._loadAudioTiming(App._audioBookId, App._audioChapter, _curVoice());
        });
        audioEl.addEventListener('pause', () => {
            if (playBtn) playBtn.classList.remove('is-playing');
            if (playMob) playMob.classList.remove('is-playing');
            App._clearVerseFocus();
        });
        // Einde hoofdstuk → automatisch doorspelen naar het volgende hoofdstuk
        // (navigeert ook over de boekgrens; _updateAudioPlayer start het fragment).
        audioEl.addEventListener('ended', () => {
            App._clearVerseFocus();
            App._autoplayNext = true;
            if (typeof Navigation !== 'undefined' && Navigation.navigateRelative) {
                Navigation.navigateRelative(1);
            }
        });

        // === Versmarkering + meescrollen met de voorlezing ===
        // Strikt gekoppeld aan het SPELENDE hoofdstuk (App._audioBookId/_audioChapter):
        // exact via het per-vers tijdsbestand, anders een schatting BINNEN dit
        // hoofdstuk. Zo kan de markering nooit naar een ánder hoofdstuk wegspringen
        // wanneer er meerdere hoofdstukken tegelijk geladen zijn (doorlopend lezen).
        // Handmatig scrollen pauzeert het meescrollen ~6s.
        App._userScrollAt = App._userScrollAt || 0;
        if (!App._userScrollWired) {
            App._userScrollWired = true;
            ['wheel', 'touchmove'].forEach(ev =>
                window.addEventListener(ev, () => { App._userScrollAt = Date.now(); }, { passive: true }));
        }
        audioEl.addEventListener('timeupdate', () => {
            if (audioEl.paused || App._audioBookId == null) return;
            App._followAudio(App._audioBookId, App._audioChapter, _curVoice(),
                             audioEl.currentTime, audioEl.duration);
        });

        // Snelheid: 1× → 1.25× → 1.5× → 2× → 0.75× → 1× (gedeeld tussen desktop + mobile)
        const cycle = [1, 1.25, 1.5, 2, 0.75];
        let idx = 0;
        const cycleSpeed = () => {
            idx = (idx + 1) % cycle.length;
            audioEl.playbackRate = cycle[idx];
            const lbl = cycle[idx] + '×';
            if (speedBtn) speedBtn.textContent = lbl;
            if (speedMob) speedMob.textContent = lbl;
        };
        if (speedBtn) speedBtn.addEventListener('click', cycleSpeed);
        if (speedMob) speedMob.addEventListener('click', cycleSpeed);

        // Stem-toggle (man/vrouw): wissel bron, behoud positie + afspeelstatus
        const voiceBtn = document.getElementById('audio-voice');
        const voiceMob = document.getElementById('audio-voice-mobile');
        const toggleVoice = () => {
            const ov = window.OV_AUDIO;
            if (!ov || App._audioBookId == null) return;
            const wasPlaying = !audioEl.paused;
            const pos = audioEl.currentTime || 0;
            ov.toggleVoice();
            const lbl = ov.label();
            if (voiceBtn) voiceBtn.textContent = lbl;
            if (voiceMob) voiceMob.textContent = lbl;
            // Opties-radio's synchroniseren
            document.querySelectorAll('input[name="opt-stem"]').forEach(r => { r.checked = (r.value === ov.getVoice()); });
            audioEl.src = ov.src(App._audioBookId, App._audioChapter);
            audioEl.addEventListener('loadedmetadata', function once() {
                audioEl.removeEventListener('loadedmetadata', once);
                try { audioEl.currentTime = Math.min(pos, audioEl.duration || pos); } catch (e) {}
                if (wasPlaying) audioEl.play();
            });
        };
        if (voiceBtn) voiceBtn.addEventListener('click', toggleVoice);
        if (voiceMob) voiceMob.addEventListener('click', toggleVoice);

        // Scrubber: doorspoelen + tijd-display (desktop + mobiel)
        const scrubbers = [document.getElementById('audio-scrubber'),
                           document.getElementById('audio-scrubber-mobile')].filter(Boolean);
        if (scrubbers.length) {
            audioEl.addEventListener('loadedmetadata', () => {
                scrubbers.forEach(s => { s.max = audioEl.duration || 0; });
                if (totEl) totEl.textContent = fmt(audioEl.duration);
            });
            audioEl.addEventListener('timeupdate', () => {
                scrubbers.forEach(s => { if (!s._dragging) s.value = audioEl.currentTime; });
                if (curEl) curEl.textContent = fmt(audioEl.currentTime);
            });
            scrubbers.forEach(s => {
                s.addEventListener('input', () => {
                    s._dragging = true;
                    if (curEl) curEl.textContent = fmt(parseFloat(s.value));
                });
                s.addEventListener('change', () => {
                    audioEl.currentTime = parseFloat(s.value);
                    s._dragging = false;
                });
            });
        }

        // === Opties-paneel: stem (man/vrouw) + afspeelsnelheid ===
        const storedSpeed = parseFloat(localStorage.getItem('ov_speed')) || 1;
        audioEl.playbackRate = storedSpeed;
        // Opgeslagen snelheid opnieuw toepassen bij elk nieuw fragment
        audioEl.addEventListener('loadedmetadata', () => {
            audioEl.playbackRate = parseFloat(localStorage.getItem('ov_speed')) || 1;
        });
        // Stem opnieuw laden met behoud van positie + status
        const reloadVoice = () => {
            const ov = window.OV_AUDIO;
            if (!ov || App._audioBookId == null) return;
            const wasPlaying = !audioEl.paused;
            const pos = audioEl.currentTime || 0;
            audioEl.src = ov.src(App._audioBookId, App._audioChapter);
            const lbl = ov.label();
            if (voiceBtn) voiceBtn.textContent = lbl;
            if (voiceMob) voiceMob.textContent = lbl;
            audioEl.addEventListener('loadedmetadata', function once() {
                audioEl.removeEventListener('loadedmetadata', once);
                try { audioEl.currentTime = Math.min(pos, audioEl.duration || pos); } catch (e) {}
                if (wasPlaying) audioEl.play();
            });
        };
        const ovHelper = window.OV_AUDIO;
        document.querySelectorAll('input[name="opt-stem"]').forEach(r => {
            if (ovHelper) r.checked = (r.value === ovHelper.getVoice());
            r.addEventListener('change', () => {
                if (!r.checked || !window.OV_AUDIO) return;
                window.OV_AUDIO.setVoice(r.value);
                reloadVoice();
            });
        });
        const speedSel = document.getElementById('opt-audio-speed');
        if (speedSel) {
            speedSel.value = String(storedSpeed);
            speedSel.addEventListener('change', () => {
                const sp = parseFloat(speedSel.value) || 1;
                localStorage.setItem('ov_speed', String(sp));
                audioEl.playbackRate = sp;
                const lbl = sp + '×';
                if (speedBtn) speedBtn.textContent = lbl;
                if (speedMob) speedMob.textContent = lbl;
            });
        }
    },

    COL_WIDTHS: {
        // minmax(0, 1fr) i.p.v. '1fr' zodat lange content een kolom niet
        // breder duwt dan zijn helft — bij 2 zichtbare kolommen wordt het echt 50/50.
        '1637': 'minmax(0, 1fr)', 'margin1637': 'minmax(0, 1fr)',
        'sv1888': 'minmax(0, 1fr)', 'marginSV1888': 'minmax(0, 1fr)',
        '2026': 'minmax(0, 1fr)', 'margin2026': 'minmax(0, 1fr)',
        'nbg51': 'minmax(0, 1fr)', 'hsv': 'minmax(0, 1fr)',
        'hebrew': 'minmax(0, 1fr)', 'diff': 'minmax(0, 1fr)', 'noteDiff': 'minmax(0, 1fr)'
    },

    async init() {
        // Eerst de nagekeken-lijst, want sidebar.js, mobile-nav.js en de
        // hoofdstukknoppen lezen die synchroon. Renderen ze eerder, dan lijkt
        // alles concept te zijn.
        await App._laadVerified();
        Navigation.init();
        Editor.init();

        References.init();
        this.initColumnToggles();
        const notesToggle = document.getElementById('toggle-kanttekeningen');
        const applyNotes = () => {
            document.body.classList.toggle('kt-popup-mode', notesToggle.checked);
            localStorage.setItem('ov_kanttekeningen', String(notesToggle.checked));
        };
        notesToggle.checked = localStorage.getItem('ov_kanttekeningen') !== 'false';
        applyNotes();
        notesToggle.addEventListener('change', applyNotes);

        // Verschillen SV-OV: woorden die afwijken van de SV1888 markeren (js/spoor.js).
        // Twee knoppen (hoofdstukbalk en mobiele balk) met één stand.
        const diffKnoppen = document.querySelectorAll('[data-verschillen-knop]');
        if (diffKnoppen.length && window.OVSpoor) {
            const zetKnoppen = () => diffKnoppen.forEach(knop => knop.setAttribute('aria-pressed', OVSpoor.aan() ? 'true' : 'false'));
            zetKnoppen();
            diffKnoppen.forEach(knop => knop.addEventListener('click', () => {
                const container = document.getElementById('verses-container');
                OVSpoor.zet(!OVSpoor.aan());
                if (OVSpoor.aan()) OVSpoor.markeerRijen(container);
                else OVSpoor.wis(container);
                zetKnoppen();
            }));
        }


        Sidebar.init();

        await Navigation.renderBookNav();
        await Sidebar.renderTree();

        // Audio play-knop in chapter-footer wirelinen
        App._setupAudioPlayer();

        // Toolbar knoppen
        document.getElementById('btn-save').addEventListener('click', () => Editor.saveAll());
        document.getElementById('btn-export').addEventListener('click', () => {
            if (Navigation.currentBook) {
                ExportImport.exportBook(Navigation.currentBook);
            }
        });
        document.getElementById('btn-export-edits').addEventListener('click', () => {
            ExportImport.exportAllEdits();
        });
        document.getElementById('btn-import').addEventListener('click', () => {
            ExportImport.importEdits();
        });
        document.getElementById('btn-approve').addEventListener('click', () => {
            if (!Navigation.currentBook || !Navigation.currentChapter) {
                alert('Selecteer eerst een hoofdstuk.');
                return;
            }
            const book = DataLoader.cache[Navigation.currentBook];
            const name = book ? book.nameDutch : Navigation.currentBook;
            if (confirm(`Weet u zeker dat u ${name} ${Navigation.currentChapter} als definitief wilt goedkeuren?\n\nAlle verzen worden op status "definitief" gezet en het hoofdstuk wordt als JSON gedownload.`)) {
                ExportImport.approveChapter(Navigation.currentBook, Navigation.currentChapter);
            }
        });
        document.getElementById('btn-reset').addEventListener('click', () => {
            if (confirm('Weet u zeker dat u alle lokale bewerkingen wilt wissen? De data wordt opnieuw geladen vanuit de JSON-bestanden.')) {
                Storage.clearAll();
                DataLoader.cache = {};
                location.reload();
            }
        });

        // Laad vanuit URL hash of default
        if (location.hash) {
            await Navigation.handleHash();
        } else {
            // Trigger default
            Navigation.handleHash();
        }
    },

    ...ChapterRenderer,

    // Scroll naar een specifiek vers en selecteer/markeer het (bv. vanaf Onderwerpen)
    focusVerse(bookId, ch, vs) {
        let tries = 0;
        const tryFocus = () => {
            const row = document.querySelector(`.verse-row[data-book="${bookId}"][data-chapter="${ch}"][data-verse="${vs}"]`)
                     || document.querySelector(`.verse-row[data-verse="${vs}"]`);
            if (!row) {
                if (tries++ < 20) { setTimeout(tryFocus, 80); } else { window.scrollTo(0, 0); }
                return;
            }
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            try {
                if (window.VerseSelect && VerseSelect._key) {
                    VerseSelect.clearAll();
                    VerseSelect.select(VerseSelect._key(row));
                    VerseSelect.lastClicked = VerseSelect._key(row);
                    VerseSelect.updateUI();
                } else {
                    row.classList.add('verse-selected');
                }
            } catch (e) {}
            row.classList.add('verse-flash');
            setTimeout(() => row.classList.remove('verse-flash'), 1700);
        };
        setTimeout(tryFocus, 60);
    },

    // Hoofdstuktitel (met concept-marker) zetten — gedeeld door render + scroll-spy
    _setTitle(bookId, chapterNum) {
        VerificationDisplay.readerTitle(App, bookId, chapterNum);
    },

    // Bepaal het scrollbare element (document of #content)
    _getScroller() {
        const c = document.getElementById('content');
        if (c && c.scrollHeight > c.clientHeight + 5) return c;
        return document.scrollingElement || document.documentElement;
    },

    // === Doorlopend lezen (lazy-load hoofdstukken bij omhoog/omlaag scrollen) ===
    _afterRenderContinuous(append, prepend) {
        const container = document.getElementById('verses-container');
        if (!container) return;
        const on = localStorage.getItem('doorlopend') === 'true';
        document.body.classList.toggle('doorlopend-aan', on);
        let bottom = document.getElementById('continuous-sentinel');
        let top = document.getElementById('continuous-sentinel-top');
        if (!on) {
            if (bottom) bottom.remove();
            if (top) top.remove();
            if (App._contObserver) { App._contObserver.disconnect(); App._contObserver = null; }
            return;
        }
        App._setupScrollSpy();
        if (!append && !prepend) {
            App._contLast = { bookId: Navigation.currentBook, chapterNum: Navigation.currentChapter };
            App._contFirst = { bookId: Navigation.currentBook, chapterNum: Navigation.currentChapter };
            App._contLoading = false;
        }
        if (!bottom) { bottom = document.createElement('div'); bottom.id = 'continuous-sentinel'; bottom.style.height = '1px'; }
        if (!top) { top = document.createElement('div'); top.id = 'continuous-sentinel-top'; top.style.height = '1px'; }
        container.appendChild(bottom);                       // altijd onderaan
        container.insertBefore(top, container.firstChild);   // altijd bovenaan
        if (!App._contObserver) {
            App._contObserver = new IntersectionObserver((entries) => {
                for (const e of entries) {
                    if (!e.isIntersecting) continue;
                    if (e.target.id === 'continuous-sentinel-top') App._loadPrevContinuous();
                    else App._loadNextContinuous();
                }
            }, { rootMargin: '600px 0px' });
        } else {
            App._contObserver.disconnect();
        }
        App._contObserver.observe(bottom);
        App._contObserver.observe(top);
    },

    async _loadNextContinuous() {
        if (App._contLoading || localStorage.getItem('doorlopend') !== 'true') return;
        const last = App._contLast;
        if (!last) return;
        App._contLoading = true;
        try {
            const manifest = await DataLoader.loadManifest();
            const mode = (window.Opties && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
            const orderIds = (typeof getFlatBookOrder === 'function')
                ? getFlatBookOrder(mode, manifest) : manifest.books.map(b => b.id);
            const byId = Object.fromEntries(manifest.books.map(b => [b.id, b]));
            const cur = byId[last.bookId];
            const chs = (cur && cur.chaptersIncluded) || [];
            const idx = chs.indexOf(last.chapterNum);
            let nextBook = null, nextCh = null;
            if (idx >= 0 && idx < chs.length - 1) {
                nextBook = last.bookId; nextCh = chs[idx + 1];
            } else {
                const bi = orderIds.indexOf(last.bookId);
                const nb = (bi >= 0 && bi < orderIds.length - 1) ? byId[orderIds[bi + 1]] : null;
                if (nb && nb.chaptersIncluded && nb.chaptersIncluded.length) {
                    nextBook = nb.id; nextCh = nb.chaptersIncluded[0];
                }
            }
            if (nextCh != null) {
                await App.renderChapter(nextBook, nextCh, { append: true });
                App._contLast = { bookId: nextBook, chapterNum: nextCh };
            }
        } catch (e) { console.warn('[doorlopend] laden volgende hoofdstuk faalde:', e); }
        App._contLoading = false;
    },

    async _loadPrevContinuous() {
        if (App._contLoading || localStorage.getItem('doorlopend') !== 'true') return;
        const first = App._contFirst;
        if (!first) return;
        App._contLoading = true;
        try {
            const manifest = await DataLoader.loadManifest();
            const mode = (window.Opties && Opties.state && Opties.state.boekvolgorde) || 'canoniek';
            const orderIds = (typeof getFlatBookOrder === 'function')
                ? getFlatBookOrder(mode, manifest) : manifest.books.map(b => b.id);
            const byId = Object.fromEntries(manifest.books.map(b => [b.id, b]));
            const cur = byId[first.bookId];
            const chs = (cur && cur.chaptersIncluded) || [];
            const idx = chs.indexOf(first.chapterNum);
            let prevBook = null, prevCh = null;
            if (idx > 0) {
                prevBook = first.bookId; prevCh = chs[idx - 1];
            } else {
                const bi = orderIds.indexOf(first.bookId);
                const pb = (bi > 0) ? byId[orderIds[bi - 1]] : null;
                if (pb && pb.chaptersIncluded && pb.chaptersIncluded.length) {
                    prevBook = pb.id; prevCh = pb.chaptersIncluded[pb.chaptersIncluded.length - 1];
                }
            }
            if (prevCh != null) {
                await App.renderChapter(prevBook, prevCh, { prepend: true });
                App._contFirst = { bookId: prevBook, chapterNum: prevCh };
            }
        } catch (e) { console.warn('[doorlopend] vorige hoofdstuk laden faalde:', e); }
        App._contLoading = false;
    },

    // Scroll-spy: werk de hoofdstuktitel bovenaan (en de URL) bij naar het
    // hoofdstuk dat momenteel boven in beeld staat — alleen bij doorlopend lezen.
    _setupScrollSpy() {
        if (App._scrollSpyWired) return;
        App._scrollSpyWired = true;
        let ticking = false;
        const onScroll = () => {
            if (localStorage.getItem('doorlopend') !== 'true') return;
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(() => { ticking = false; App._updateTitleFromScroll(); });
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        const sc = document.getElementById('content');
        if (sc) sc.addEventListener('scroll', onScroll, { passive: true });
    },

    _updateTitleFromScroll() {
        const rows = document.querySelectorAll('#verses-container .verse-row');
        if (!rows.length) return;
        const threshold = 140;   // net onder de sticky bovenbalk
        let cur = null;
        for (const r of rows) {
            const rect = r.getBoundingClientRect();
            if (rect.bottom > threshold) { cur = r; break; }
        }
        if (!cur) cur = rows[rows.length - 1];
        const bookId = cur.dataset.book;
        const ch = parseInt(cur.dataset.chapter, 10);
        if (!bookId || !ch) return;
        if (App._spyBook === bookId && App._spyChapter === ch) return;
        App._spyBook = bookId; App._spyChapter = ch;
        App._setTitle(bookId, ch);
        // footer-label + interne navigatiepointers meenemen (voor vorige/volgende)
        if (typeof Navigation !== 'undefined') {
            Navigation.currentBook = bookId;
            Navigation.currentChapter = ch;
        }
        try { history.replaceState(null, '', `#${bookId}/${ch}`); } catch (e) {}
        // replaceState vuurt geen 'hashchange' → mobiele topbalk-knop zelf bijwerken,
        // anders blijft die het oude hoofdstuk tonen tijdens doorlopend scrollen.
        if (typeof MobileNav !== 'undefined' && MobileNav.syncFromState) {
            try { MobileNav.syncFromState(); } catch (e) {}
        }
        // Harde koppeling audio ↔ scrollpositie: de voorleesspeler volgt het
        // hoofdstuk dat in beeld is. Alleen wanneer er NIET wordt afgespeeld —
        // tijdens het voorlezen scrollt de tekst zelf mee, dan niet resetten.
        const audioEl = document.getElementById('audio-el');
        if (!audioEl || audioEl.paused) App._updateAudioPlayer(bookId, ch);
    },

    // === Versmarkering tijdens voorlezen ===
    // De markering verschijnt ALLEEN tijdens audio-voorlezen en staat exact op het
    // vers dat klinkt — op basis van een per-vers tijdsbestand
    // (data/audio-timing/{boek}/{hfdst}-{m|v}.json: [{v,t}], t = starttijd in sec).
    // Is er geen tijdsbestand, dan tonen we NIETS (liever geen markering dan een gok).
    _clearVerseFocus() {
        if (App._focusedRow) { App._focusedRow.classList.remove('verse-focus'); App._focusedRow = null; }
    },

    async _loadAudioTiming(bookId, ch, voice) {
        const key = `${bookId}/${ch}-${voice}`;
        App._timingCache = App._timingCache || {};
        if (key in App._timingCache) return App._timingCache[key];
        let data = null;
        try {
            const r = await fetch(`data/audio-timing/${bookId}/${ch}-${voice}.json`);
            if (r.ok) {
                const j = await r.json();
                const arr = Array.isArray(j) ? j : (j.verses || []);
                data = arr.map(x => ({ v: x.v != null ? x.v : x.verse, t: x.t != null ? x.t : x.start }))
                          .filter(x => x.v != null && x.t != null)
                          .sort((a, b) => a.t - b.t);
                if (!data.length) data = null;
            }
        } catch (e) { data = null; }
        App._timingCache[key] = data;
        return data;
    },

    // Bepaal het versnummer dat NU klinkt, binnen het opgegeven (spelende) hoofdstuk.
    // Exact via tijdsbestand; anders een schatting op tekstlengte BINNEN dit hoofdstuk.
    _currentAudioVerse(bookId, ch, voice, t, duration) {
        const timing = App._timingCache && App._timingCache[`${bookId}/${ch}-${voice}`];
        if (timing && timing.length) {
            let cur = timing[0].v;
            for (const seg of timing) { if (t >= seg.t) cur = seg.v; else break; }
            return cur;
        }
        // Fallback (nog geen tijdsbestand): schat BINNEN dit hoofdstuk, nooit erbuiten.
        if (!duration) return null;
        const rows = Array.from(document.querySelectorAll(
            `#verses-container .verse-row[data-book="${bookId}"][data-chapter="${ch}"]`));
        if (!rows.length) return null;
        let cum = 0;
        const map = rows.map(r => { cum += ((r.textContent || '').trim().length) || 1; return { v: parseInt(r.dataset.verse, 10), end: cum }; });
        const pos = (t / duration) * cum;
        for (const m of map) { if (pos < m.end) return m.v; }
        return map[map.length - 1].v;
    },

    // Markeer (en scroll naar) het vers dat klinkt — strikt binnen het spelende
    // hoofdstuk, dus geen wegspringen naar een ander hoofdstuk in doorlopend lezen.
    _followAudio(bookId, ch, voice, t, duration) {
        const cur = App._currentAudioVerse(bookId, ch, voice, t, duration);
        if (cur == null) return;
        const row = document.querySelector(
            `#verses-container .verse-row[data-book="${bookId}"][data-chapter="${ch}"][data-verse="${cur}"]`);
        if (!row || row === App._focusedRow) return;
        if (App._focusedRow) App._focusedRow.classList.remove('verse-focus');
        row.classList.add('verse-focus');
        App._focusedRow = row;
        // Meescrollen, tenzij de gebruiker net handmatig scrolde (~6s rust).
        if (!App._userScrollAt || (Date.now() - App._userScrollAt > 6000)) {
            try { row.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) {}
        }
    },

    updateProgress() {
        const rows = document.querySelectorAll('.verse-row');
        if (rows.length === 0) return;

        let counts = { empty: 0, draft: 0, review: 0, final: 0 };
        rows.forEach(r => {
            const s = r.dataset.status || 'empty';
            if (counts[s] !== undefined) counts[s]++;
        });

        const total = rows.length;
        const done = counts.final;
        const pct = Math.round((done / total) * 100);

        document.getElementById('progress-fill').style.width = pct + '%';
        document.getElementById('progress-text').textContent =
            `${done}/${total} definitief (${counts.draft} concept, ${counts.review} review)`;
    },

    // === Kolom-toggle logica ===
    initColumnToggles() {
        const content = document.getElementById('content');
        this.ALL_COLS.forEach(col => content.classList.toggle('hide-' + col, col !== '2026'));
        this.updateGrid();
    },

    updateGrid() {
        const content = document.getElementById('content');
        content.classList.add('reading-mode');
    }

};

// Stel column-headers sticky offset in op basis van header-hoogte
function updateStickyOffset() {
    const topnav = document.getElementById('topnav');
    const header = document.getElementById('app-header');
    const topbar = document.getElementById('content-topbar');
    const colHeaders = document.querySelector('.column-headers');
    const navH = topnav ? topnav.offsetHeight : 0;
    if (header) header.style.top = navH + 'px';
    const headerH = header ? header.offsetHeight : 0;
    // app-header is leeg op tekstpagina → vaak height 0
    if (topbar) topbar.style.top = (navH + headerH) + 'px';
    if (colHeaders) {
        const topbarH = topbar ? topbar.offsetHeight : 0;
        colHeaders.style.top = (navH + headerH + topbarH) + 'px';
    }
}

// Uitzondering: wijziging ongedaan maken via server
async function undoDiff(boek, hoofdstuk, vers, principe, oud, nieuw) {
    if (!confirm(`Wijziging "${oud} → ${nieuw}" ongedaan maken?`)) return;
    const resp = await fetch('/api/uitzondering', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({boek, hoofdstuk, vers, principe, oud, nieuw, actie: 'undo'})
    });
    if (resp.ok) {
        // Cache wissen zodat data opnieuw geladen wordt
        if (typeof DataLoader !== 'undefined') delete DataLoader.cache[boek];
        location.reload();
    } else {
        alert('Fout bij ongedaan maken van wijziging.');
    }
}

// Start de applicatie
document.addEventListener('DOMContentLoaded', () => {
    App.init();
    if (typeof Opties !== 'undefined') Opties.init();
    setTimeout(updateStickyOffset, 100);
    window.addEventListener('resize', updateStickyOffset);

    // Sluit dropdown bij klik buiten
    document.addEventListener('click', (e) => {
        const wrapper = document.getElementById('column-toggles-wrapper');
        if (wrapper && !wrapper.contains(e.target)) {
            document.getElementById('columns-dropdown')?.classList.remove('open');
        }
    });
});

// Hamburger menu: sluit bij klik buiten
document.addEventListener('click', (e) => {
    const links = document.getElementById('topnav-links');
    const hamburger = document.getElementById('topnav-hamburger');
    if (!links || !hamburger) return;
    if (!links.contains(e.target) && !hamburger.contains(e.target)) {
        links.classList.remove('open');
        hamburger.classList.remove('open');
    }
});

// Globaal beschikbaar maken (zoals window.Opties) — handig voor o.a. navigation.js en tests.
if (typeof window !== 'undefined') window.App = App;
