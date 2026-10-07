/* Reader-optie: toon per vers het oudste bewaarde handschrift (origineel + überhaupt).
 * Zelfstandig; leest data/verse-witnesses.json en annoteert .verse-row-elementen.
 * Aan/uit via de optie 'Oudste handschrift per vers' (checkbox #toggle-hs-vers). */
(function () {
    'use strict';
    var KEY = 'hsPerVers';
    var vw = null, loading = false, observer = null;

    function jaarLabel(y) { return y < 0 ? Math.abs(y) + ' v.Chr.' : y + ' n.Chr.'; }

    function witnessFor(book, ch, v) {
        if (!vw) return null;
        var e = (vw.boeken || {})[book]; if (!e || !e.origineel) return null;
        var ex = (e.uitzonderingen || {})[ch + ':' + v] || {};
        return { orig: ex.origineel || e.origineel, alle: ex.alle || e.alle };
    }

    function esc(s) { return (s == null ? '' : String(s)).replace(/[&<>"]/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]; }); }
    function kort(naam) { return naam.replace(/^Codex\s+/, '').replace(/\s*\(Septuaginta\)/, ' (LXX)'); }
    function annotateRow(row) {
        if (row.querySelector(':scope > .hs-vers-tag')) return;
        var book = row.getAttribute('data-book'), ch = row.getAttribute('data-chapter'), v = row.getAttribute('data-verse');
        if (!book || !ch || !v) return;
        var w = witnessFor(book, ch, v); if (!w) return;
        // Toon per vers alleen het ÉCHT oudste bewaarde handschrift (de oudste getuige
        // überhaupt, ongeacht taal — meestal de Griekse Septuaginta bij het OT). Geen
        // tweede regel: bv. bij Genesis niet ook Leningradensis (1008) tonen als de
        // Septuaginta ouder is.
        var best = w.orig;
        if (w.alle && typeof w.alle.jaar === 'number' && w.alle.jaar < best.jaar) best = w.alle;
        var titel = 'Oudste bewaarde tekst van dit vers: ' + best.naam + ' (' + jaarLabel(best.jaar) + '). Klik voor de foto en toelichting.';
        var html = '<span class="hs-vw-kop">Oudste handschrift</span>' +
            '<a class="hs-vw-link" target="_top" href="' + KASites.url('ogw', 'handschriften.html?ms=' + encodeURIComponent(best.ms)) + '" title="' + esc(titel) + '">' +
            '<span class="hs-vw-naam">' + esc(kort(best.naam)) + '</span><span class="hs-vw-jaar">' + jaarLabel(best.jaar) + '</span></a>';
        var tag = document.createElement('div');
        tag.className = 'hs-vers-tag';
        tag.innerHTML = html;
        row.appendChild(tag);
    }

    function annotateAll() {
        if (!vw) return;
        var rows = document.querySelectorAll('.verse-row[data-verse]');
        for (var i = 0; i < rows.length; i++) annotateRow(rows[i]);
    }

    function clearAll() {
        var t = document.querySelectorAll('.hs-vers-tag');
        for (var i = 0; i < t.length; i++) t[i].parentNode && t[i].parentNode.removeChild(t[i]);
    }

    var _timer = null;
    function scheduleAnnotate() { clearTimeout(_timer); _timer = setTimeout(annotateAll, 120); }

    function enable() {
        document.body.classList.add('hs-per-vers-aan');
        localStorage.setItem(KEY, '1');
        if (vw) { annotateAll(); startObserver(); return; }
        if (loading) return; loading = true;
        fetch('data/verse-witnesses.json').then(function (r) { return r.json(); }).then(function (d) {
            vw = d; loading = false; annotateAll(); startObserver();
        }).catch(function () { loading = false; });
    }
    function disable() {
        document.body.classList.remove('hs-per-vers-aan');
        localStorage.removeItem(KEY);
        stopObserver(); clearAll();
    }
    function startObserver() {
        if (observer) return;
        var c = document.getElementById('verses-container') || document.getElementById('content');
        if (!c) return;
        observer = new MutationObserver(scheduleAnnotate);
        observer.observe(c, { childList: true, subtree: true });
    }
    function stopObserver() { if (observer) { observer.disconnect(); observer = null; } }

    function init() {
        var cb = document.getElementById('toggle-hs-vers');
        var on = localStorage.getItem(KEY) === '1';
        if (cb) {
            cb.checked = on;
            cb.addEventListener('change', function () { this.checked ? enable() : disable(); });
        }
        if (on) enable();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
