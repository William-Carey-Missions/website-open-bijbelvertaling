/* Adressen van de drie zustersites: Open Vertaling (OV), Open Gods Woord
 * (OGW, wiki en broninformatie) en Open Parafrase Weergave (OPV).
 *
 * Eén plek, zodat een domeinwissel geen zoektocht door de code wordt. Lokaal
 * draaien de drie naast elkaar op vaste poorten; zo zijn kruislinks ook
 * zonder internet te testen.
 *
 * Gebruik in JS:   KASites.url('ogw', 'dieren.html?item=leeuw')
 * Gebruik in HTML: <a data-ogw-href="kaart.html">…</a>  (href wordt ingevuld)
 *
 * De productiedomeinen van OGW en OPV zijn nog voorlopig. */
(function () {
    var LOKAAL = { ov: 'http://127.0.0.1:8000', ogw: 'http://127.0.0.1:8001', opv: 'http://127.0.0.1:8002' };
    var PRODUCTIE = { ov: 'https://openvertaling.nl', ogw: 'https://opengodsword.com', opv: 'https://open-parafrase-weergave.nl' };

    var host = location.hostname;
    var basis = (host === 'localhost' || host === '127.0.0.1') ? LOKAAL : PRODUCTIE;

    function url(site, pad) {
        var b = basis[site];
        if (!b) throw new Error('Onbekende site: ' + site);
        return b + '/' + String(pad || '').replace(/^\/+/, '');
    }

    function vulLinks(root) {
        var els = (root || document).querySelectorAll('[data-ogw-href],[data-ov-href],[data-opv-href]');
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            ['ogw', 'ov', 'opv'].forEach(function (site) {
                var pad = el.getAttribute('data-' + site + '-href');
                if (pad !== null) el.setAttribute('href', url(site, pad));
            });
            // Binnen het documentatieframe hoort een andere site niet ín het
            // frame te openen.
            if (window.self !== window.top && el.tagName === 'A' && !el.target) el.target = '_top';
        }
    }

    window.KASites = { basis: basis, url: url, vulLinks: vulLinks };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { vulLinks(); });
    } else {
        vulLinks();
    }
})();
