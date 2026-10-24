/* Reader presentation, shared through the main controller object. */
const ChapterRenderer = {
    /* De kanttekeningen van één vers, voor de kolom rechts naast de tekst. */
    kanttekeningCel(verse, bookId, chapterNum) {
        const noten = (verse.marginNotes || []).filter(n => n && (n.text2026 || n.text1637));
        if (!noten.length) return null;
        const cel = document.createElement('div');
        cel.className = 'verse-cell col-kt';
        cel.dataset.col = 'kt';
        for (const noot of noten) {
            const item = document.createElement('p');
            item.className = 'kt-item' + (noot.type === 'crossref' ? ' kt-verwijzing' : '');
            item.dataset.note = noot.marker;
            const merk = document.createElement('button');
            merk.type = 'button';
            merk.className = 'kt-m';
            merk.dataset.note = noot.marker;
            merk.textContent = noot.marker;
            merk.title = 'Kanttekening ' + noot.marker + ' openen';
            const tekst = document.createElement('span');
            const bron = noot.text2026 || noot.text1637;
            if (typeof References !== 'undefined' && typeof References.linkify === 'function') tekst.innerHTML = References.linkify(bron, bookId, chapterNum);
            else tekst.textContent = bron;
            item.appendChild(merk);
            item.appendChild(tekst);
            cel.appendChild(item);
        }
        return cel;
    },

    async renderChapter(bookId, chapterNum, opts = {}) {
        if (!opts.append && !opts.prepend) document.getElementById('chapter-verification')?.remove();
        await App._laadVerified();   // banner mag niet op verouderde info draaien
        const append = !!opts.append;    // doorlopend-lezen: hoofdstuk onderaan toevoegen
        const prepend = !!opts.prepend;  // doorlopend-lezen: hoofdstuk bovenaan toevoegen
        // Manifest (klein) + chapter (klein) parallel
        const [book, chapter] = await Promise.all([
            DataLoader.loadBook(bookId),                      // bouwt lazy book-object
            DataLoader.loadChapter(bookId, chapterNum),       // alleen huidige chapter
        ]);
        if (!book) {
            document.getElementById('verses-container').innerHTML = '<p>Boek niet gevonden.</p>';
            return;
        }
        if (!chapter) {
            document.getElementById('verses-container').innerHTML = '<p>Hoofdstuk niet gevonden.</p>';
            return;
        }
        const isExternalTranslation = false;
        // Pre-fetch buurchapters bij idle (volgende klik = instant)
        DataLoader.prefetchAdjacent(bookId, chapterNum);
        // Boeknaam onthouden (gebruikt door scroll-spy bij doorlopend lezen)
        App._contNames = App._contNames || {};
        App._contNames[bookId] = book.nameDutch;

        if (!append && !prepend) {
        // Titel — concept-marker bij niet-geverifieerde hoofdstukken
        App._setTitle(bookId, chapterNum);
        // Chapter-footer label (sticky onderaan)
        const chfLabel = document.getElementById('chapter-footer-label');
        if (chfLabel) {
            const total = (book.chapters && book.chapters.length) || (book.chaptersIncluded && book.chaptersIncluded.length) || 0;
            chfLabel.textContent = total ? `${book.nameDutch} ${chapterNum} / ${total}` : `${book.nameDutch} ${chapterNum}`;
        }
        // Audio play-knop tonen voor hoofdstukken met voorlezing
        App._updateAudioPlayer(bookId, chapterNum);
        // AI-concept-banner tonen voor niet-geverifieerde hoofdstukken
        App._updateVerifiedBanner(bookId, chapterNum);



        // Boek- en hoofdstukinleiding worden nu INLINE in de tekstkolom getoond
        // (zie hieronder), niet meer in een apart frame.
        const bookIntroEl = document.getElementById('book-intro');
        if (bookIntroEl) bookIntroEl.style.display = 'none';
        const introFrame = document.getElementById('chapter-intro');
        if (introFrame) introFrame.style.display = 'none';
        }  // einde if(!append): bovenstaande chrome alleen bij normaal renderen

        // Pericoop-kopjes (NBG-stijl indeling, eigen koppen) — eenmalig laden
        if (App._pericopen === undefined) {
            App._pericopen = null;
            try { App._pericopen = await (await fetch('data/pericopen.json')).json(); }
            catch (e) { App._pericopen = {}; }
        }
        const pericMap = {};
        for (const p of (isExternalTranslation ? [] : ((App._pericopen && App._pericopen[bookId]) || []))) {
            if (p.c === chapterNum) pericMap[p.v] = p.t;
        }

        // Verzen renderen
        const container = document.getElementById('verses-container');
        // sink = waar de nieuwe nodes heen gaan. Bij prepend bouwen we eerst in een
        // fragment, en plaatsen dat daarna bovenaan (met scroll-compensatie).
        const sink = prepend ? document.createDocumentFragment() : container;
        if (!append && !prepend) {
            container.innerHTML = '';
        }
        if (append || prepend) {
            // Doorlopend lezen: scheidingskop voor het toegevoegde hoofdstuk
            const sep = document.createElement('div');
            sep.className = 'chapter-separator';
            sep.textContent = `${book.nameDutch} ${chapterNum}`;
            sep.dataset.book = bookId;
            sep.dataset.chapter = chapterNum;
            sink.appendChild(sep);
        }

        // Boekinleiding inline in de tekstkolom (alleen bij hoofdstuk 1, onder de
        // hoofdstukkop), zichtbaar via instelling (body.show-book-intro)
        if (!isExternalTranslation && chapterNum === 1 && book.bookIntro && (book.bookIntro.text2026 || book.bookIntro.text1637)) {
            const bIntro = document.createElement('div');
            bIntro.className = 'book-intro-inline';
            bIntro.dataset.book = bookId;
            bIntro.innerHTML = '<span class="book-intro-label">Boekinleiding:</span> ' +
                (book.bookIntro.text2026 || book.bookIntro.text1637);
            sink.appendChild(bIntro);
        }

        // Hoofdstukinleiding inline in de tekstkolom (onder de hoofdstukkop),
        // zichtbaar via instelling (body.show-chapter-intro)
        if (chapter.chapterIntro && (chapter.chapterIntro.text2026 || chapter.chapterIntro.text1637)) {
            const intro = document.createElement('div');
            intro.className = 'chapter-intro-inline';
            intro.dataset.book = bookId;
            intro.dataset.chapter = chapterNum;
            intro.textContent = chapter.chapterIntro.text2026 || chapter.chapterIntro.text1637;
            sink.appendChild(intro);
        }

        for (const verse of chapter.verses) {
            // Pericoop-kop vóór dit vers?
            if (pericMap[verse.number]) {
                const h = document.createElement('div');
                h.className = 'pericope-heading';
                // Pas vertalingsopties (Godsnaam) ook op de kop toe, zodat de
                // perikoopkopjes synchroon lopen met de tekst (JAHWEH/HEERE/…).
                const pTitle = pericMap[verse.number];
                if (typeof Opties !== 'undefined' && Opties.transformOV) {
                    h.innerHTML = Opties.transformOV(pTitle, book.testament);
                } else {
                    h.textContent = pTitle;
                }
                sink.appendChild(h);
            }
            const row = document.createElement('div');
            row.className = 'verse-row';
            // Statuskleur volgt de enige bron (VERIFIED_CHAPTERS): een nagekeken hoofdstuk
            // toont 'final' (groen), anders de redactionele status van het vers zelf.
            row.dataset.status = App._isVerified(bookId, chapterNum) ? 'final' : (verse.status || 'empty');
            row.dataset.book = bookId;
            row.dataset.chapter = chapterNum;
            row.dataset.verse = verse.number;

            // Open Vertaling: gebruik text2026_html (met inline nootcijfers) als die er is,
            // anders text2026 of textHerzien als platte tekst
            let openVertaling = verse.text2026_html || verse.text2026 || verse.textHerzien || '';
            // Pas vertalingsopties toe (Godsnaam etc.) — alleen tekst, niet HTML-tags
            if (!isExternalTranslation && typeof Opties !== 'undefined') openVertaling = Opties.transformOV(openVertaling, book.testament);
            // Optioneel: geografische locaties markeren (nu Genesis)
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.markeerGeo) openVertaling = Opties.markeerGeo(openVertaling, bookId, chapterNum, verse.number);
            // Optioneel: Bijbelse maten vervangen door metrisch of imperiaal
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.rekenMaten) openVertaling = Opties.rekenMaten(openVertaling, bookId, chapterNum, verse.number);
            // Optioneel: "het negende uur" vervangen door moderne kloktijd.
            // Het testament bepaalt of de nacht drie of vier waken telt.
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.rekenTijden) openVertaling = Opties.rekenTijden(openVertaling, bookId, chapterNum, verse.number, book.testament);

            row.innerHTML = `<div class="verse-num" data-col="num">${verse.number}</div>
                <div class="verse-cell col-2026" data-col="2026">${openVertaling}</div>`;
            // Kanttekeningen als eigen cel; op brede schermen staat die rechts
            // naast de tekst, smal blijft het bij de pop-up (zie publication.css).
            const kanttekeningen = ChapterRenderer.kanttekeningCel(verse, bookId, chapterNum);
            if (kanttekeningen) row.appendChild(kanttekeningen);
            // Versdata voor de knop Verschillen SV-OV (js/spoor.js).
            row._ovVers = verse;
            sink.appendChild(row);
            if (!isExternalTranslation) Editor.attachVerseListeners(row, bookId, chapterNum, verse);
            // Rechtermuisknop op versnummer = tag toevoegen
            row.querySelector('.verse-num').addEventListener('contextmenu', (e) => {
                e.preventDefault();
                if (typeof Tags !== 'undefined') {
                    Tags.showAddTagPopup(bookId, chapterNum, verse.number, e.target);
                }
            });
        }

        // Doorlopend lezen: prepend-fragment bovenaan plaatsen met scroll-compensatie
        // zodat de leespositie niet verspringt.
        if (prepend) {
            const scroller = App._getScroller();
            const prevH = scroller ? scroller.scrollHeight : 0;
            const prevTop = scroller ? scroller.scrollTop : 0;
            container.insertBefore(sink, container.firstChild);
            if (scroller) scroller.scrollTop = prevTop + (scroller.scrollHeight - prevH);
        }

        // Verschillen SV-OV: gewijzigde woorden markeren als de knop aan staat.
        if (window.OVSpoor) OVSpoor.markeerRijen(container);

        this.updateProgress();
        this.updateGrid();
        // Pas kolomvolgorde toe op nieuwe rijen
        if (typeof updateStickyOffset === 'function') updateStickyOffset();
        // Tags tonen bij verzen
        if (typeof Tags !== 'undefined') Tags.renderTagsForChapter(bookId, chapterNum);
        // Highlights toepassen op nieuwe rijen
        if (typeof Highlight !== 'undefined') Highlight.applyToChapter(bookId, chapterNum);
        // Doorlopend lezen: sentinel/observer beheren
        App._afterRenderContinuous(append, prepend);
        // Versmarkering wordt NIET meer op scroll gezet (gaf een storende "bracket"
        // tijdens gewoon lezen). De markering verschijnt alleen tijdens het voorlezen,
        // exact op het vers dat klinkt (zie audio timeupdate + _followAudio).
        App._clearVerseFocus();
        Verification.readerRendered(bookId, chapterNum, false, chapter._verificationSourceHash, append || prepend);
    },
};
