/* Het spoor — markeert in de leestekst elk woord dat afwijkt van de SV1888.
 *
 * Bron: per vers `phraseDiff` ([{old, new, principe}]) uit data/<boek>/<h>.json.
 * De phraseDiff zegt wélke woorden veranderd zijn, maar niet wáár in het vers.
 * Dat zoeken we zelf uit, in twee stappen:
 *
 *   1. Een woordvolgorde-vergelijking (LCS) tussen textSV1888 en text2026 geeft
 *      de woorden in text2026 die niet in de SV1888 terugkomen. Een
 *      phraseDiff-regel wordt alleen gemarkeerd op een plek waar zijn `new` ook
 *      echt als gewijzigd uit die vergelijking komt. Zo krijgt in "heeft het
 *      niet begrepen" (Joh 1:5) het tweede "het" het spoor, niet het eerste.
 *   2. Een tweede vergelijking tussen text2026 en de tekst zoals hij in het
 *      document staat (na Godsnaam, maten, namen enz.) vertaalt die plek naar
 *      de DOM. Woorden die een leesoptie daarna nog heeft omgezet, vallen bij
 *      die vergelijking af en krijgen géén spoor: liever een markering missen
 *      dan een verkeerde tonen.
 *
 * De markering wikkelt alleen bestaande tekstknopen in een <span>; de
 * textContent van het vers verandert dus niet (markeringen en kopiëren blijven
 * gelijk werken). Aan/uit via de knop "Verschillen SV-OV" (standaard uit).
 */
(function (global) {
    'use strict';

    var WOORD = /[\p{L}\p{M}\p{N}’'-]+/gu;
    var MAX_LCS = 160 * 160;   // bescherming tegen zeer lange verzen

    function woorden(tekst) {
        var uit = [];
        var m;
        WOORD.lastIndex = 0;
        while ((m = WOORD.exec(tekst))) {
            uit.push({ w: m[0].toLowerCase().replace(/’/g, "'"), s: m.index, e: m.index + m[0].length });
        }
        return uit;
    }

    function zonderHtml(html) {
        return String(html || '').replace(/<sup[^>]*>[\s\S]*?<\/sup>/g, '').replace(/<[^>]+>/g, '')
            .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    }

    /* Langste gemeenschappelijke deelreeks; geeft voor elke index in b de
       bijbehorende index in a, of -1. */
    function koppel(a, b) {
        var n = a.length, m = b.length;
        var map = new Array(m).fill(-1);
        if (!n || !m || n * m > MAX_LCS) return map;
        var t = [];
        for (var i = 0; i <= n; i++) t.push(new Uint16Array(m + 1));
        for (i = n - 1; i >= 0; i--) {
            for (var j = m - 1; j >= 0; j--) {
                t[i][j] = a[i].w === b[j].w ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
            }
        }
        i = 0; j = 0;
        while (i < n && j < m) {
            if (a[i].w === b[j].w) { map[j] = i; i++; j++; }
            else if (t[i + 1][j] >= t[i][j + 1]) i++;
            else j++;
        }
        return map;
    }

    function principeCode(p) {
        if (Array.isArray(p)) p = p[0];
        return p ? String(p) : '';
    }

    /* Plekken (woordindices in text2026) per phraseDiff-regel. */
    function plekken(vers) {
        var diff = vers && vers.phraseDiff;
        if (!Array.isArray(diff) || !diff.length) return [];
        var sv = woorden(zonderHtml(vers.textSV1888_html || vers.textSV1888 || ''));
        var ov = woorden(vers.text2026 || zonderHtml(vers.text2026_html));
        if (!sv.length || !ov.length) return [];
        var naarSv = koppel(sv, ov);
        var gebruikt = new Array(ov.length).fill(false);
        var uit = [];
        var cursor = 0;
        diff.forEach(function (d) {
            if (!d || !d['new'] || !d.old) return;
            var nieuw = woorden(d['new']).map(function (t) { return t.w; });
            if (!nieuw.length) return;
            function zoek(van) {
                for (var k = van; k + nieuw.length <= ov.length; k++) {
                    var ok = true, gewijzigd = false;
                    for (var x = 0; x < nieuw.length; x++) {
                        if (ov[k + x].w !== nieuw[x] || gebruikt[k + x]) { ok = false; break; }
                        if (naarSv[k + x] === -1) gewijzigd = true;
                    }
                    if (ok && gewijzigd) return k;
                }
                return -1;
            }
            var k = zoek(cursor);
            if (k === -1) k = zoek(0);
            if (k === -1) return;
            for (var x = 0; x < nieuw.length; x++) gebruikt[k + x] = true;
            cursor = k + nieuw.length;
            uit.push({ van: k, tot: k + nieuw.length - 1, old: String(d.old).trim().replace(/[\s,.;:!?]+$/, ''), code: principeCode(d.principe) });
        });
        uit.ov = ov;
        return uit;
    }

    /* Tekstknopen die meetellen als leestekst (geen nootcijfers, Strong-nummers…). */
    var OVERSLAAN = 'sup, .note-marker, .strongs-inline, .strongs-sub, .verse-num, .spoor-tip, script, style';
    function tekstknopen(cel) {
        var lijst = [];
        var walker = document.createTreeWalker(cel, NodeFilter.SHOW_TEXT, {
            acceptNode: function (n) {
                var p = n.parentElement;
                if (p && p.closest(OVERSLAAN)) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var n, pos = 0;
        while ((n = walker.nextNode())) {
            lijst.push({ node: n, s: pos, e: pos + n.nodeValue.length });
            pos += n.nodeValue.length;
        }
        return lijst;
    }

    function wikkel(knopen, s, e, plek) {
        var gemaakt = [];
        // Van achter naar voren, zodat eerdere offsets geldig blijven.
        var delen = knopen.filter(function (k) { return k.e > s && k.s < e; });
        for (var i = delen.length - 1; i >= 0; i--) {
            var k = delen[i];
            var node = k.node;
            var a = Math.max(s, k.s) - k.s;
            var b = Math.min(e, k.e) - k.s;
            if (b <= a || !node.nodeValue.slice(a, b).trim()) continue;
            if (b < node.nodeValue.length) node.splitText(b);
            var midden = a > 0 ? node.splitText(a) : node;
            var span = document.createElement('span');
            span.className = 'spoor';
            span.dataset.sv = plek.old;
            span.dataset.p = plek.code || 'los';
            midden.parentNode.insertBefore(span, midden);
            span.appendChild(midden);
            gemaakt.push(span);
        }
        if (!gemaakt.length) return false;
        // Eén tabstop per wijziging, op het eerste stuk.
        var eerste = gemaakt[gemaakt.length - 1];
        eerste.tabIndex = 0;
        eerste.setAttribute('aria-description',
            'SV1888: ' + plek.old + ' · ' + (plek.code ? 'principe ' + plek.code : 'losse wijziging'));
        return true;
    }

    /* Aan/uit via de knop "Verschillen SV-OV" in de lezer; standaard uit. */
    var SLEUTEL = 'ov_verschillen';
    function aan() {
        try { return localStorage.getItem(SLEUTEL) === 'aan'; } catch (e) { return false; }
    }
    function zet(waarde) {
        try { localStorage.setItem(SLEUTEL, waarde ? 'aan' : 'uit'); } catch (e) { /* privé-venster */ }
    }

    /* Haal alle markeringen weer weg; de tekst zelf blijft ongewijzigd. */
    function wis(container) {
        if (!container) return;
        container.querySelectorAll('.spoor').forEach(function (span) {
            var ouder = span.parentNode;
            while (span.firstChild) ouder.insertBefore(span.firstChild, span);
            ouder.removeChild(span);
            ouder.normalize();
        });
        container.querySelectorAll('.verse-row[data-spoor]').forEach(function (rij) { delete rij.dataset.spoor; });
    }

    /* Markeer één vers in `cel`. Geeft het aantal gemarkeerde plekken terug. */
    function markeer(cel, vers, opties) {
        if (!cel || !vers) return 0;
        if (!(opties && opties.altijd) && !aan()) return 0;
        if (cel.querySelector('.spoor')) return 0;
        var lijst = plekken(vers);
        if (!lijst.length) return 0;
        var knopen = tekstknopen(cel);
        var weergave = knopen.map(function (k) { return k.node.nodeValue; }).join('');
        var r = woorden(weergave);
        var naarR = koppel(r, lijst.ov);
        var aantal = 0;
        for (var i = lijst.length - 1; i >= 0; i--) {
            var p = lijst[i];
            var ok = true;
            for (var x = p.van; x <= p.tot; x++) if (naarR[x] === -1) { ok = false; break; }
            if (!ok) continue;
            if (wikkel(knopen, r[naarR[p.van]].s, r[naarR[p.tot]].e, p)) aantal++;
            knopen = tekstknopen(cel);
        }
        return aantal;
    }

    /* Na een hoofdstukweergave in de hoofdlezer: alle rijen met versdata. */
    function markeerRijen(container) {
        if (!container || !aan()) return;
        container.querySelectorAll('.verse-row').forEach(function (rij) {
            var vers = rij._ovVers;
            if (!vers || rij.dataset.spoor === 'klaar') return;
            rij.dataset.spoor = 'klaar';
            var cel = rij.querySelector('.col-2026 .primary-edition') || rij.querySelector('.col-2026');
            markeer(cel, vers);
        });
    }

    /* Label binnen het scherm houden: vlak bij de rand naar binnen uitlijnen. */
    function richtLabel(e) {
        var s = e.target && e.target.closest && e.target.closest('.spoor[tabindex]');
        if (!s) return;
        var r = s.getBoundingClientRect();
        var midden = r.left + r.width / 2;
        var breed = global.innerWidth || document.documentElement.clientWidth;
        var ruimte = Math.min(220, breed * 0.4);
        if (midden < ruimte) s.dataset.tip = 'links';
        else if (breed - midden < ruimte) s.dataset.tip = 'rechts';
        else delete s.dataset.tip;
    }
    document.addEventListener('mouseover', richtLabel, true);
    document.addEventListener('focusin', richtLabel, true);

    global.OVSpoor = { markeer: markeer, markeerRijen: markeerRijen, wis: wis, aan: aan, zet: zet, _plekken: plekken };
})(window);
