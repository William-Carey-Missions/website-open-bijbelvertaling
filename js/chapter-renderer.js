/* Reader presentation, shared through the main controller object. */
const ChapterRenderer = {
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
        if (chapter._unavailable) {
            const meta = chapter._translation || { code: 'nl-ov', naam: 'Open Vertaling' };
            const message = (typeof I18n !== 'undefined')
                ? I18n.t('edition.unavailable', { boek: book.nameDutch, editie: meta.naam })
                : `${book.nameDutch} is niet beschikbaar in ${meta.naam}.`;
            const action = (typeof I18n !== 'undefined') ? I18n.t('edition.openDutch') : 'Open dit boek in Open Vertaling';
            const href = `${location.pathname}?editie=nl-ov#${bookId}/${chapterNum}`;
            document.getElementById('verses-container').innerHTML =
                `<section class="translation-unavailable"><p>${App._escapeStrongHtml(message)}</p>` +
                `<a href="${App._escapeStrongHtml(href)}">${App._escapeStrongHtml(action)}</a></section>`;
            // Geen tekst in deze editie: ook de voorlezing van het vorige hoofdstuk stoppen.
            App._updateAudioPlayer(bookId, chapterNum);
            return;
        }
        const translationMeta = chapter._translation || null;
        const isExternalTranslation = !!translationMeta;
        const primaryEditionCode = translationMeta ? translationMeta.code : 'nl-ov';
        const configuredParallels = (typeof Opties !== 'undefined' && Array.isArray(Opties.state.parallelEdities))
            ? Opties.state.parallelEdities.filter(code => code !== primaryEditionCode).slice(0, 3)
            : [];
        const parallelEditions = [];
        const unavailableParallelNames = [];
        if (typeof TekstEditie !== 'undefined') {
            const loadedParallels = await Promise.all(configuredParallels.map(async code => {
                const parallelChapter = await TekstEditie.loadChapterForEdition(code, bookId, chapterNum);
                if (!parallelChapter || parallelChapter._unavailable) {
                    const missingMeta = parallelChapter && parallelChapter._translation;
                    unavailableParallelNames.push(missingMeta ? missingMeta.naam : code);
                    return null;
                }
                const meta = parallelChapter._translation || await TekstEditie.metadata(code);
                return {
                    code,
                    meta,
                    verses: new Map((parallelChapter.verses || []).map(item => [Number(item.number), item])),
                };
            }));
            parallelEditions.push(...loadedParallels.filter(Boolean));
        }
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
        App._updateEthiopicBanner(book);
        App._updateDatingBox(book);

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
            if (unavailableParallelNames.length) {
                const unavailable = document.createElement('div');
                unavailable.className = 'parallel-editions-unavailable';
                unavailable.textContent = `Niet beschikbaar voor dit hoofdstuk: ${unavailableParallelNames.join(', ')}.`;
                container.appendChild(unavailable);
            }
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

            // Hebreeuws/Grieks kolom — klikbare woorden met Strong's
            const showStrongs = typeof Opties !== 'undefined' && Opties.state.strongs === 'aan';
            let hebrewHtml;
            const isGeez = book.testament === 'ET';
            if (verse.grondtekst && verse.grondtekst.length > 0) {
                const words = verse.grondtekst.map(w => {
                    const translit = w.transliteratie || '';
                    const gloss = w.gloss || '';
                    // Apocriefen hebben geen Strong's — toon dan lemma als subtext (of niets)
                    const strongs = w.strongs || '';
                    const subText = strongs || w.lemma || '';
                    const dataAttr = strongs ? ` data-strongs="${strongs}"` : '';
                    const subHtml = subText ? `<br><span class="strongs-sub">${subText}</span>` : '';
                    const attr = v => String(v == null ? '' : v).replace(/"/g, '&quot;');
                    // Ge'ez heeft geen Strong's → eigen OV-strongs (OVG, uit Dillmann); klikbaar via geez-word
                    if (isGeez) {
                        const ovg = w.strongs ? `<br><span class="strongs-sub ov-strongs">${attr(w.strongs)}</span>` : '';
                        return `<span class="strongs-word geez-word" data-geez="${attr(w.woord)}" data-translit="${attr(translit)}" data-betekenis="${attr(w.betekenis)}" data-strongs="${attr(w.strongs || '')}">${w.woord}${ovg}</span>`;
                    }
                    // Latijn (4 Ezra) heeft geen Strong's → eigen OV-strongs (OVL, uit Lewis & Short)
                    if (bookId === '4ezra') {
                        const ovl = w.strongs ? `<br><span class="strongs-sub ov-strongs">${attr(w.strongs)}</span>` : '';
                        return `<span class="strongs-word latin-word" data-lemma="${attr(w.lemma)}" data-betekenis="${attr(w.betekenis)}" data-strongs="${attr(w.strongs || '')}">${w.woord}${ovl}</span>`;
                    }
                    return `<span class="strongs-word"${dataAttr} data-transliteratie="${translit}" data-gloss="${gloss}">${w.woord}${subHtml}</span>`;
                }).join(' ');
                // Schrift-richting/taal per grondtekst: Hebreeuws (OT) = RTL; Grieks
                // (NT + apocriefen) en Ge'ez (Ethiopisch) = LTR; 4 Ezra = Latijn.
                const t = book.testament;
                let langAttr = '';
                if (bookId === '4ezra') langAttr = ' lang="la"';
                else if (t === 'ET') langAttr = ' lang="gez"';
                else if (t === 'NT' || t === 'AP') langAttr = ' lang="grc"';
                hebrewHtml = `<span class="hebrew-text"${langAttr}>${words}</span>`;
                if (verse.hebrewMeaning) {
                    hebrewHtml += `<span class="hebrew-meaning">${verse.hebrewMeaning}</span>`;
                }
            } else if (verse.hebrew) {
                hebrewHtml = `<span class="hebrew-text">${verse.hebrew}</span><span class="hebrew-meaning">${verse.hebrewMeaning || ''}</span>`;
            } else {
                hebrewHtml = '<span style="color:#bbb;font-style:italic;direction:ltr;font-size:12px">—</span>';
            }

            // Open Vertaling: gebruik text2026_html (met inline nootcijfers) als die er is,
            // anders text2026 of textHerzien als platte tekst
            let openVertaling = verse.text2026_html || verse.text2026 || verse.textHerzien || '';
            // Pas vertalingsopties toe (Godsnaam etc.) — alleen tekst, niet HTML-tags
            if (!isExternalTranslation && typeof Opties !== 'undefined') openVertaling = Opties.transformOV(openVertaling, book.testament);
            if (primaryEditionCode === 'nl-opv' && typeof Opties !== 'undefined' && Opties.transformOPV) openVertaling = Opties.transformOPV(openVertaling);
            // Optioneel: geografische locaties markeren (nu Genesis)
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.markeerGeo) openVertaling = Opties.markeerGeo(openVertaling, bookId, chapterNum, verse.number);
            // Optioneel: Bijbelse maten vervangen door metrisch of imperiaal
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.rekenMaten) openVertaling = Opties.rekenMaten(openVertaling, bookId, chapterNum, verse.number);
            // Optioneel: "het negende uur" vervangen door moderne kloktijd.
            // Het testament bepaalt of de nacht drie of vier waken telt.
            if (!isExternalTranslation && typeof Opties !== 'undefined' && Opties.rekenTijden) openVertaling = Opties.rekenTijden(openVertaling, bookId, chapterNum, verse.number, book.testament);

            // Alleen gecontroleerde koppelingen staan inline in de Nederlandse OV-tekst.
            // Nooit een extra grondtekstregel: de lezer ziet uitsluitend aanklikbare nummers
            // direct na het Nederlandse woord waarop de koppeling betrekking heeft.
            let sv1888Text = verse.textSV1888_html || verse.textSV1888 || '';
            if (showStrongs && verse.woordnummers && verse.woordnummers.length > 0) {
                openVertaling = this.renderStrongLinks(openVertaling, verse.woordnummers);
            }

            // Diff-kolom: toon phrase-level wijzigingen als "oud → nieuw"
            let diffHtml = '';
            if (verse.phraseDiff && verse.phraseDiff.length > 0) {
                diffHtml = verse.phraseDiff.map(d => {
                    // Sommige geïmporteerde revisies dragen meerdere principes als array.
                    // De leesweergave mag daardoor nooit vóór de initiaal-rendering afbreken.
                    const principe = Array.isArray(d.principe)
                        ? (d.principe[0] || '')
                        : String(d.principe || '');
                    const badge = principe ? `<a class="principe-badge cat-${principe[0]}" href="principes.html#${principe}" title="${principe}">${principe}</a>` : '';
                    const escOld = (d.old || '').replace(/'/g, "\\'");
                    const escNew = (d.new || '').replace(/'/g, "\\'");
                    const escPrincipe = principe.replace(/'/g, "\\'");
                    const undoBtn = `<button class="undo-diff-btn" title="Uitzondering maken" onclick="undoDiff('${bookId}', ${chapterNum}, ${verse.number}, '${escPrincipe}', '${escOld}', '${escNew}')">✕</button>`;
                    if (d.old && d.new) {
                        return `<span class="diff-change">${badge}${undoBtn}<span class="diff-old">${d.old}</span> → <span class="diff-new">${d.new}</span></span>`;
                    } else if (d.new) {
                        return `<span class="diff-added">${badge}${undoBtn}+ ${d.new}</span>`;
                    } else if (d.old) {
                        return `<span class="diff-removed">${badge}${undoBtn}− ${d.old}</span>`;
                    }
                    return '';
                }).join('');
            }

            // Kanttekeningen 1637 (alleen-lezen)
            let margin1637Html = '';
            if (verse.marginNotes && verse.marginNotes.length > 0) {
                margin1637Html = verse.marginNotes.map(n =>
                    `<div class="note-item"><span class="note-marker-label">${n.marker}</span><span class="note-type-label">${n.type === 'crossref' ? 'kruisverw.' : ''}</span> ${References.linkify(n.text1637, bookId, chapterNum)}</div>`
                ).join('');
            } else {
                margin1637Html = '<span style="color:#bbb;font-style:italic;font-size:12px">—</span>';
            }

            // Kanttekeningen hertaald (bewerkbaar per noot)
            let margin2026Html = '';
            if (verse.marginNotes && verse.marginNotes.length > 0) {
                margin2026Html = verse.marginNotes.map((n, i) => {
                    let linkedText = n.text2026 ? References.linkify(n.text2026, bookId, chapterNum) : '';
                    if (linkedText && window.NootGrondwoorden) linkedText = NootGrondwoorden.link(linkedText, verse);
                    return `<div class="note-item"><span class="note-marker-label">${n.marker}</span> <span class="margin-note-edit">${linkedText}</span></div>`;
                }).join('');
            } else {
                margin2026Html = '<span style="color:#bbb;font-style:italic;font-size:12px">—</span>';
            }

            // SV2000.net kanttekeningen (alleen-lezen)
            let marginSV1888Html = '';
            if (verse.marginNotes && verse.marginNotes.length > 0) {
                const sv2000Notes = verse.marginNotes.filter(n => n.textSV1888);
                if (sv2000Notes.length > 0) {
                    marginSV1888Html = sv2000Notes.map(n =>
                        `<div class="note-item"><span class="note-marker-label">${n.marker}</span> ${n.textSV1888}</div>`
                    ).join('');
                } else {
                    marginSV1888Html = '<span style="color:#bbb;font-style:italic;font-size:12px">—</span>';
                }
            } else {
                marginSV1888Html = '<span style="color:#bbb;font-style:italic;font-size:12px">—</span>';
            }

            // Kanttekening diff (SV1888 vs OV2026)
            let noteDiffHtml = '';
            if (verse.marginNotes && verse.marginNotes.length > 0) {
                const noteDiffs = verse.marginNotes.filter(n => n.noteDiff && n.noteDiff.length > 0);
                if (noteDiffs.length > 0) {
                    noteDiffHtml = noteDiffs.map(n => {
                        const changes = n.noteDiff.map(d => {
                            const badge = d.principe ? `<a class="principe-badge cat-${d.principe[0]}" href="principes.html#${d.principe}" title="${d.principe}">${d.principe}</a>` : '';
                            if (d.old && d.new) {
                                return `<span class="diff-change">${badge}<span class="diff-old">${d.old}</span> → <span class="diff-new">${d.new}</span></span>`;
                            } else if (d.new) {
                                return `<span class="diff-added">${badge}+ ${d.new}</span>`;
                            } else if (d.old) {
                                return `<span class="diff-removed">${badge}− ${d.old}</span>`;
                            }
                            return '';
                        }).join(' ');
                        return `<div class="note-item"><span class="note-marker-label">${n.marker}</span> ${changes}</div>`;
                    }).join('');
                }
            }

            let editionTextHtml = openVertaling;
            if (parallelEditions.length) {
                const primaryName = translationMeta ? translationMeta.naam : 'Open Vertaling';
                const layout = (typeof Opties !== 'undefined' && Opties.state.kolomLayout === 'eronder') ? 'eronder' : 'naast';
                const parallelHtml = parallelEditions.map(item => {
                    const parallelVerse = item.verses.get(Number(verse.number));
                    if (!parallelVerse) return '';
                    let text = parallelVerse.text2026_html || parallelVerse.text2026 || '';
                    // De Godsnaam-keuze geldt ook in de parallelle kolom.
                    if (typeof Opties !== 'undefined') {
                        if (item.code === 'nl-ov') text = Opties.transformOV(text, book.testament);
                        else if (item.code === 'nl-opv' && Opties.transformOPV) text = Opties.transformOPV(text);
                    }
                    const meta = item.meta || { naam: item.code, taal: '', richting: 'ltr' };
                    return `<section class="parallel-edition" data-editie="${App._escapeStrongHtml(item.code)}" data-edition-label="${App._escapeStrongHtml(meta.naam)}" lang="${App._escapeStrongHtml(meta.taal || '')}" dir="${meta.richting === 'rtl' ? 'rtl' : 'ltr'}">${text}</section>`;
                }).join('');
                editionTextHtml = `<div class="edition-comparison" data-layout="${layout}" style="--edition-count:${parallelEditions.length + 1}">` +
                    `<section class="parallel-edition primary-edition" data-editie="${App._escapeStrongHtml(primaryEditionCode)}" data-edition-label="${App._escapeStrongHtml(primaryName)}">${openVertaling}</section>` +
                    parallelHtml + '</div>';
            }

            row.innerHTML = `
                <div class="verse-num" data-col="num" title="Klik voor status">${verse.number}</div>
                <div class="verse-cell col-1637" data-col="1637">${verse.text1637_html || verse.text1637}</div>
                <div class="verse-cell col-margin1637" data-col="margin1637">${margin1637Html}</div>
                <div class="verse-cell col-sv1888" data-col="sv1888">${sv1888Text}</div>
                <div class="verse-cell col-marginSV1888" data-col="marginSV1888">${marginSV1888Html}</div>
                <div class="verse-cell col-2026" data-col="2026"${translationMeta ? ` lang="${App._escapeStrongHtml(translationMeta.taal)}" dir="${translationMeta.richting === 'rtl' ? 'rtl' : 'ltr'}"` : ''}>${editionTextHtml}</div>
                <div class="verse-cell col-margin2026" data-col="margin2026">${margin2026Html}</div>
                <div class="verse-cell col-hebrew" data-col="hebrew">${hebrewHtml}</div>
                <div class="verse-cell col-diff" data-col="diff">${diffHtml}</div>
                <div class="verse-cell col-noteDiff" data-col="noteDiff">${noteDiffHtml}</div>
            `;

            // Versdata bewaren voor het spoor (SV1888-wijzigingen), alleen bij de OV zelf.
            if (!isExternalTranslation) row._ovVers = verse;
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

        this.updateProgress();
        this.updateGrid();
        // Pas kolomvolgorde toe op nieuwe rijen
        if (typeof ColumnReorder !== 'undefined') ColumnReorder.reorderDOM();
        if (typeof updateStickyOffset === 'function') updateStickyOffset();
        // Tags tonen bij verzen
        if (typeof Tags !== 'undefined') Tags.renderTagsForChapter(bookId, chapterNum);
        // Begrippen herladen bij boekwisseling — eerst checkbox-state synchroniseren
        if (typeof Begrippen !== 'undefined') {
            const begrCb = document.getElementById('toggle-begrippen') || document.getElementById('quick-begrippen');
            if (begrCb && begrCb.checked) Begrippen.active = true;
            Begrippen.reload(bookId);
        }
        // Highlights toepassen op nieuwe rijen
        if (typeof Highlight !== 'undefined') Highlight.applyToChapter(bookId, chapterNum);
        // Versierde initiaal (drop-cap) op het eerste vers
        App._applyDropcap();
        // Het spoor: gewijzigde woorden t.o.v. SV1888 markeren (na de initiaal,
        // zodat die de eerste letter al uit de tekst heeft gehaald).
        if (window.OVSpoor) OVSpoor.markeerRijen(container);
        // Doorlopend lezen: sentinel/observer beheren
        App._afterRenderContinuous(append, prepend);
        // Versmarkering wordt NIET meer op scroll gezet (gaf een storende "bracket"
        // tijdens gewoon lezen). De markering verschijnt alleen tijdens het voorlezen,
        // exact op het vers dat klinkt (zie audio timeupdate + _followAudio).
        App._clearVerseFocus();
        Verification.readerRendered(bookId, chapterNum, false, chapter._verificationSourceHash, append || prepend);
    },
};
