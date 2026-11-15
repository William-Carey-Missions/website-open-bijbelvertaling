/* Versleepbare grens tussen de leestekst en de kanttekeningen.
 *
 * Op brede schermen met de kanttekeningen aan staan tekst en noten naast elkaar
 * (zie css/publication.css). De verhouding komt uit twee variabelen op
 * #verses-container; deze module zet één greep op de grens, laat die slepen en
 * met de pijltjestoetsen verschuiven, en onthoudt de keuze. Dubbelklik zet de
 * standaard terug.
 *
 * Geen lookbehind: die breekt de lezer op iPadOS 15. */
(function (global) {
    'use strict';

    var OPSLAG = 'ov_kt_aandeel';
    var STANDAARD = 1 / 2.7;          // gelijk aan 1.7fr tegen 1fr
    var MIN = 0.2, MAX = 0.6;
    var greep = null, sleept = false, bekeken = null, waarnemer = null;

    function begrens(aandeel) {
        if (typeof aandeel !== 'number' || !isFinite(aandeel)) return STANDAARD;
        return Math.min(MAX, Math.max(MIN, aandeel));
    }

    /* Welk deel van de rij krijgen de noten als de greep op x staat? */
    function aandeelUit(x, links, rechts) {
        var breed = rechts - links;
        if (!(breed > 0)) return STANDAARD;
        return Math.round(begrens((rechts - x) / breed) * 1000) / 1000;
    }

    function bewaard() {
        try {
            var waarde = parseFloat(global.localStorage.getItem(OPSLAG));
            return isFinite(waarde) ? begrens(waarde) : STANDAARD;
        } catch (e) { return STANDAARD; }
    }

    function container() { return global.document.getElementById('verses-container'); }

    function actief() {
        var doc = global.document;
        return doc.body.classList.contains('kt-popup-mode') &&
            global.matchMedia('(min-width: 1100px)').matches &&
            !!doc.querySelector('#content.reading-mode #verses-container .verse-row .col-kt');
    }

    function zet(aandeel, bewaar) {
        var c = container();
        if (!c) return;
        aandeel = begrens(aandeel);
        c.style.setProperty('--kt-tekst', (1 - aandeel).toFixed(3) + 'fr');
        c.style.setProperty('--kt-noten', aandeel.toFixed(3) + 'fr');
        if (greep) greep.setAttribute('aria-valuenow', String(Math.round(aandeel * 100)));
        if (bewaar) {
            try { global.localStorage.setItem(OPSLAG, String(aandeel)); } catch (e) { /* zonder opslag werkt het alleen deze keer */ }
        }
        plaats();
    }

    /* De rij waarvan de breedte de verhouding bepaalt: de eerste met noten. */
    function meetRij() {
        var noot = global.document.querySelector('#verses-container .verse-row .col-kt');
        if (!noot) return null;
        var rij = noot.closest('.verse-row');
        var tekst = rij.querySelector('.col-2026');
        if (!tekst) return null;
        var r = rij.getBoundingClientRect(), t = tekst.getBoundingClientRect(), n = noot.getBoundingClientRect();
        return { links: t.left, rechts: r.right - (r.right - n.right), grens: n.left, top: r.top };
    }

    function plaats() {
        var c = container();
        if (!c || !greep) return;
        // De lezer leegt de container bij elk nieuw hoofdstuk; zet de greep terug.
        if (greep.parentNode !== c) c.appendChild(greep);
        if (bekeken !== c) {
            if (waarnemer) waarnemer.disconnect();
            waarnemer = new global.MutationObserver(function () { if (!sleept) plaats(); });
            waarnemer.observe(c, { childList: true });
            bekeken = c;
            zet(bewaard(), false);
        }
        if (!actief()) { greep.hidden = true; return; }
        var m = meetRij();
        if (!m) { greep.hidden = true; return; }
        var kader = c.getBoundingClientRect();
        greep.hidden = false;
        greep.style.left = (m.grens - kader.left - 14) + 'px';
    }

    function maakGreep() {
        var c = container();
        if (!c || greep) return;
        greep = global.document.createElement('div');
        greep.className = 'kt-greep';
        greep.setAttribute('role', 'separator');
        greep.setAttribute('aria-orientation', 'vertical');
        greep.setAttribute('aria-label', 'Breedte van tekst en kanttekeningen');
        greep.setAttribute('aria-valuemin', String(MIN * 100));
        greep.setAttribute('aria-valuemax', String(MAX * 100));
        greep.tabIndex = 0;
        greep.title = 'Sleep om de breedte van tekst en kanttekeningen te kiezen; dubbelklik zet hem terug';
        greep.hidden = true;
        c.appendChild(greep);

        greep.addEventListener('pointerdown', function (e) {
            sleept = true;
            greep.classList.add('is-sleept');
            global.document.body.classList.add('kt-sleept');
            greep.setPointerCapture(e.pointerId);
            e.preventDefault();
        });
        greep.addEventListener('pointermove', function (e) {
            if (!sleept) return;
            var m = meetRij();
            if (m) zet(aandeelUit(e.clientX, m.links, m.rechts), false);
        });
        function stop(e) {
            if (!sleept) return;
            sleept = false;
            greep.classList.remove('is-sleept');
            global.document.body.classList.remove('kt-sleept');
            try { greep.releasePointerCapture(e.pointerId); } catch (x) { /* al losgelaten */ }
            var huidig = parseFloat(greep.getAttribute('aria-valuenow')) / 100;
            zet(huidig, true);
        }
        greep.addEventListener('pointerup', stop);
        greep.addEventListener('pointercancel', stop);
        greep.addEventListener('dblclick', function () { zet(STANDAARD, true); });
        greep.addEventListener('keydown', function (e) {
            var huidig = parseFloat(greep.getAttribute('aria-valuenow')) / 100;
            if (e.key === 'ArrowLeft') zet(huidig + 0.02, true);
            else if (e.key === 'ArrowRight') zet(huidig - 0.02, true);
            else if (e.key === 'Home' || e.key === 'Enter') zet(STANDAARD, true);
            else return;
            e.preventDefault();
        });
    }

    function start() {
        var c = container();
        if (!c) return;
        maakGreep();
        zet(bewaard(), false);
        plaats();
        new global.MutationObserver(plaats).observe(global.document.body, { attributes: true, attributeFilter: ['class'] });
        global.addEventListener('resize', plaats);
        global.addEventListener('load', plaats);
    }

    global.KolomBreedte = { aandeelUit: aandeelUit, begrens: begrens, STANDAARD: STANDAARD };
    if (global.document.readyState === 'loading') global.document.addEventListener('DOMContentLoaded', start);
    else start();
})(typeof window !== 'undefined' ? window : this);
