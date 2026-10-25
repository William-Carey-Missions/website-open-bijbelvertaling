/* Gedeeld thema: synchroon in de head laden, vóór de eerste paginaweergave. */
(function (global) {
    'use strict';
    var storageKey = 'sv2026_vertaalopties';

    function readOptions() {
        var saved = localStorage.getItem(storageKey);
        return saved === null ? {} : JSON.parse(saved);
    }

    function apply(choice) {
        var theme = choice === 'auto'
            ? (global.matchMedia('(prefers-color-scheme: dark)').matches ? 'donker' : 'licht')
            : choice;
        document.documentElement.dataset.theme = theme;
        document.querySelectorAll('[data-optie="thema"]').forEach(function (control) {
            // De keuze staat in een drieknopsschakelaar; bij een radio zou
            // control.value zetten de keuze zelf overschrijven.
            if (control.type === 'radio') control.checked = control.value === choice;
            else control.value = choice;
        });
        if (global.OptionsPanel) global.OptionsPanel.syncOptionMirrors();
        global.dispatchEvent(new Event('ov:theme-changed'));
    }

    function toggle() {
        var choice = document.documentElement.dataset.theme === 'donker' ? 'licht' : 'donker';
        if (global.Opties && global.Opties._initialized) {
            global.Opties.state.thema = choice;
            global.Opties.save();
        } else {
            // Het paneel is lui geladen; bewaar ook dan alle andere instellingen.
            var state = readOptions();
            state.thema = choice;
            localStorage.setItem(storageKey, JSON.stringify(state));
            global.dispatchEvent(new CustomEvent('ov:opties-gewijzigd', { detail: { state: state } }));
        }
        apply(choice);
    }

    global.OVTheme = { apply: apply, toggle: toggle };
    try {
        apply(readOptions().thema ?? 'auto');
    } catch (error) {
        console.error('[Theme] Thema-instellingen konden niet worden geladen.', error);
    }
    // Eén lokale bootstrap voor alle gewone en gegenereerde pagina's.
    if (global.top === global.self && !document.getElementById('ogw-analytics-bootstrap')) {
        var analytics = document.createElement('script');
        analytics.id = 'ogw-analytics-bootstrap';
        analytics.async = true;
        analytics.src = '/js/analytics.js?v=1';
        document.head.appendChild(analytics);
    }
})(window);
