/* Globale host voor de ene tekstoptie-ingang op alle pagina's.
 * De dialoog komt uit de hoofdlezer, zodat Wiki en naslag exact dezelfde
 * instellingen, structuur en bediening gebruiken zonder een tweede template. */
(function (global) {
    'use strict';

    function laadScript(src, klaar) {
        if (klaar()) return Promise.resolve();
        return new Promise(function (resolve, reject) {
            var bestaand = document.querySelector('script[src$="' + src + '"]');
            if (bestaand) {
                bestaand.addEventListener('load', resolve, { once: true });
                bestaand.addEventListener('error', reject, { once: true });
                return;
            }
            var script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    function plaatsDialoog() {
        if (document.getElementById('sidebar-right')) return Promise.resolve();
        return fetch('index.html')
            .then(function (response) { return response.ok ? response.text() : Promise.reject(new Error('opties ontbreken')); })
            .then(function (html) {
                var bron = new DOMParser().parseFromString(html, 'text/html');
                var dialoog = bron.getElementById('sidebar-right');
                if (!dialoog) throw new Error('optiesdialoog ontbreekt');
                document.body.appendChild(document.importNode(dialoog, true));
            });
    }

    var ready;
    function ensure() {
        if (ready) return ready;
        ready = Promise.all([
            laadScript('js/optie-maten.js', function () { return !!global.OptieMaten; })
                .then(function () { return laadScript('js/opties.js', function () { return !!global.Opties; }); }),
            laadScript('js/tekstweergave.js', function () { return !!global.OVTekstweergave; }),
            laadScript('js/options-panel.js', function () { return !!global.OptionsPanel; })
        ]).then(function () {
            return plaatsDialoog();
        }).then(function () {
            global.Opties.init();
            global.OptionsPanel.init();
            global.dispatchEvent(new Event('ov:options-host-ready'));
        });
        return ready;
    }

    global.GlobalOptionsHost = { ensure: ensure };
    global.dispatchEvent(new Event('ov:options-host-loaded'));

    global.addEventListener('message', function (event) {
        if (!event.data || event.data.type !== 'ov:opties-gewijzigd') return;
        if (event.data.state && global.Opties) {
            global.Opties.state = { ...global.Opties.DEFAULTS, ...event.data.state };
            global.Opties.enforceReaderOptions();
            global.Opties.applyVerseNumbersClass();
            global.Opties.applyCitationsClass();
            global.Opties.applyReaderStyleClasses();
        }
        if (event.data.state) global.OVTheme.apply(event.data.state.thema ?? 'auto');
        global.dispatchEvent(new CustomEvent('ov:opties-gewijzigd', { detail: event.data }));
    });
})(window);
