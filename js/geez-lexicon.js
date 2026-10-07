/* Open Vertaling — Ge'ez-lexicon (Ethiopische boeken)
 *
 * Ge'ez (Ethiopisch/Fidäl) heeft geen Strong's-nummers, dus de gewone Strong's-
 * lexiconpopup werkt er niet voor. Deze module maakt Ge'ez-grondtekstwoorden
 * selecteerbaar: klik op een woord → popup met (a) het woord, (b) een Latijnse
 * transliteratie (deterministisch uit het Fidäl-syllabarium), en (c) opzoeklinks
 * naar online Ge'ez-woordenboeken (Dillmann/Beta maṣāḥǝft, Wiktionary).
 */
(function () {
    'use strict';

    // 34 basismedeklinkers van het Ethiopisch syllabarium, in Unicode-volgorde
    // (elk blok van 8 codepunten begint op U+1200 + n*8).
    const CONS = [
        'h', 'l', 'ḥ', 'm', 'ś', 'r', 's', 'š', 'q', 'q̈', 'b', 'v', 't', 'č', 'ḫ', 'n',
        'ñ', 'ʾ', 'k', 'ḵ', 'w', 'ʿ', 'z', 'ž', 'y', 'd', 'ǧ', 'g', 'ṭ', 'č̣', 'p̣', 'ṣ',
        'ṣ́', 'f', 'p'
    ];
    // Klinkerordes 1..7 (+ labiovelaar-varianten); order 6 (ǝ) = geen/zwakke klinker.
    const VOW = ['ä', 'u', 'i', 'a', 'e', '', 'o', 'wa'];

    function translitChar(ch) {
        const c = ch.codePointAt(0);
        // Ethiopisch hoofdblok U+1200–U+135A (syllaben)
        if (c >= 0x1200 && c <= 0x135A) {
            const idx = c - 0x1200;
            const cons = CONS[Math.floor(idx / 8)];
            const vow = VOW[idx % 8];
            if (cons === undefined) return ch;
            return cons + vow;
        }
        // Ethiopische woordscheider (፡) en leestekens → spatie/weglaten
        if (c === 0x1361) return ' ';
        if (c >= 0x1362 && c <= 0x1368) return '';
        return ch;
    }

    function transliterate(word) {
        let out = '';
        for (const ch of (word || '')) out += translitChar(ch);
        return out.replace(/\s+/g, ' ').trim();
    }

    let popupEl = null;
    function closePopup() { if (popupEl) { popupEl.remove(); popupEl = null; } }

    function place(anchorEl) {
        const r = anchorEl.getBoundingClientRect();
        popupEl.style.top = (r.bottom + window.scrollY + 6) + 'px';
        popupEl.style.left = Math.min(r.left + window.scrollX, window.scrollX + window.innerWidth - popupEl.offsetWidth - 12) + 'px';
    }
    function esc(s) { return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

    function showPopup(word, anchorEl) {
        closePopup();
        const ds = (anchorEl && anchorEl.dataset) || {};
        const tr = ds.translit || transliterate(word);
        const bet = ds.betekenis || '';
        popupEl = document.createElement('div');
        popupEl.className = 'geez-lex-popup';
        popupEl.innerHTML =
            `<div class="geez-lex-word" lang="gez">${esc(word)}</div>` +
            (tr ? `<div class="geez-lex-translit">${esc(tr)}</div>` : '') +
            (bet ? `<div class="geez-lex-betekenis">${esc(bet)}</div>`
                 : `<div class="geez-lex-empty">betekenis nog niet beschikbaar</div>`) +
            (ds.strongs ? `<div class="geez-lex-strongs">${esc(ds.strongs)}</div>` : '') +
            geezLexLink(ds.strongs, word);
        document.body.appendChild(popupEl);
        place(anchorEl);
    }

    // Link naar het woordenboek: bij een OV-strongs (OVG####) rechtstreeks naar het
    // Dillmann-lemma; anders zoeken op het woord.
    function geezLexLink(strongs, word) {
        if (strongs && /^OVG(\d+)/.test(strongs)) {
            var n = parseInt(strongs.replace(/^OVG0*/, ''), 10);
            return `<a class="geez-lex-link" target="_top" href="${KASites.url('ogw', 'lexicon-viewer.html')}?taal=geez&zoek=${encodeURIComponent('OVG' + n)}">In het woordenboek (Dillmann) →</a>`;
        }
        return `<a class="geez-lex-link" target="_top" href="${KASites.url('ogw', 'lexicon-viewer.html')}?taal=geez&zoek=${encodeURIComponent(word)}">In het woordenboek opzoeken →</a>`;
    }

    function showLatinPopup(word, anchorEl) {
        closePopup();
        const ds = (anchorEl && anchorEl.dataset) || {};
        const lemma = ds.lemma || '';
        const bet = ds.betekenis || '';
        popupEl = document.createElement('div');
        popupEl.className = 'geez-lex-popup';
        popupEl.innerHTML =
            `<div class="geez-lex-word" lang="la">${esc(word)}</div>` +
            (lemma ? `<div class="geez-lex-translit">${esc(lemma)}</div>` : '') +
            (bet ? `<div class="geez-lex-betekenis">${esc(bet)}</div>`
                 : `<div class="geez-lex-empty">betekenis nog niet beschikbaar</div>`) +
            (ds.strongs ? `<div class="geez-lex-strongs">${esc(ds.strongs)}</div>` : '') +
            `<a class="geez-lex-link" target="_top" href="${KASites.url('ogw', 'lexicon-viewer.html')}?taal=latijn&zoek=${encodeURIComponent(lemma || word)}">In het woordenboek (Lewis &amp; Short) →</a>`;
        document.body.appendChild(popupEl);
        place(anchorEl);
    }

    // Globale klik-afhandeling: klik op een Ge'ez- of Latijns woord toont de popup; klik elders sluit.
    document.addEventListener('click', function (e) {
        const gw = e.target.closest && e.target.closest('.geez-word');
        const lw = e.target.closest && e.target.closest('.latin-word');
        if (gw) {
            e.stopPropagation();
            showPopup(gw.dataset.geez || gw.textContent, gw);
        } else if (lw) {
            e.stopPropagation();
            showLatinPopup(lw.textContent, lw);
        } else if (popupEl && !(e.target.closest && e.target.closest('.geez-lex-popup'))) {
            closePopup();
        }
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePopup(); });

    window.GeezLexicon = { transliterate: transliterate };
})();
