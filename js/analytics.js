/* Vrijwillige bezoekersstatistieken: Basic Consent Mode, geen tag zonder toestemming.
 * Enhanced Measurement moet ook in de GA4-webstream uit staan: alleen onze
 * opgeschoonde page_view-events worden verstuurd, geen formulieren/zoekopdrachten.
 * https://developers.google.com/tag-platform/security/concepts/consent-mode
 * https://developers.google.com/analytics/devguides/collection/ga4/views
 */
(function (global) {
    'use strict';
    var config = {
        hostname: 'openvertaling.nl',
        measurementId: 'G-BZGB0WJVD7',
        siteName: 'Open Vertaling',
        bibleBooks: {} // De geldige boek- en hoofdstuknummers staan hieronder.
    };
    config.bibleBooks = {"1koningen":[1,22],"1kronieken":[1,29],"1samuel":[1,31],"2koningen":[1,25],"2kronieken":[1,36],"2samuel":[1,24],"amos":[1,9],"daniel":[1,12],"deuteronomium":[1,34],"esther":[1,10],"exodus":[1,40],"ezechiel":[1,48],"ezra":[1,10],"genesis":[1,50],"habakuk":[1,3],"haggai":[1,2],"hooglied":[1,8],"hosea":[1,14],"jeremia":[1,52],"jesaja":[1,66],"job":[1,42],"jona":[1,4],"jozua":[1,24],"joel":[1,3],"klaagliederen":[1,5],"leviticus":[1,27],"maleachi":[1,4],"micha":[1,7],"nahum":[1,3],"nehemia":[1,13],"numeri":[1,36],"obadja":[1,1],"prediker":[1,12],"psalmen":[1,150],"richteren":[1,21],"ruth":[1,4],"spreuken":[1,31],"zacharia":[1,14],"zefanja":[1,3],"1johannes":[1,5],"1korinthiers":[1,16],"1petrus":[1,5],"1tessalonicensen":[1,5],"1timotheus":[1,6],"2johannes":[1,1],"2korinthiers":[1,13],"2petrus":[1,3],"2tessalonicensen":[1,3],"2timotheus":[1,4],"3johannes":[1,1],"efeziers":[1,6],"filemon":[1,1],"filippenzen":[1,4],"galaten":[1,6],"handelingen":[1,28],"hebreeen":[1,13],"jakobus":[1,5],"johannes":[1,21],"judas":[1,1],"kolossenzen":[1,4],"lukas":[1,24],"markus":[1,16],"mattheus":[1,28],"openbaring":[1,22],"romeinen":[1,16],"titus":[1,3],"1makkabeeen":[1,16],"2makkabeeen":[1,15],"3ezra":[1,9],"3makkabeeen":[1,7],"4ezra":[1,16],"baruch":[1,6],"belenddedraak":[1,1],"boekderwijsheid":[1,19],"estherapocrief":[10,16],"gebedvanazaria":[1,1],"gebedvanmanasse":[1,1],"gezangindevuuroven":[1,1],"jezussirach":[1,51],"judith":[1,16],"susanna":[1,1],"tobit":[1,14]};
    if (global.OGWStatistics || global.top !== global.self ||
        global.location.protocol !== 'https:' || global.location.hostname !== config.hostname ||
        global.location.port || !/^G-[A-Z0-9]+$/.test(config.measurementId)) return;

    var storageKey = 'ogw_statistics_consent_v1';
    var choice = readChoice();
    var loaded = false;
    var lastPage = null;
    var scheduled = false;
    var panel;
    var settingsButton;
    var disableKey = 'ga-disable-' + config.measurementId;
    global[disableKey] = choice !== 'granted';

    function readChoice() {
        try { return global.localStorage.getItem(storageKey); }
        catch (_) { return null; }
    }

    function safeLocation() {
        var hash = global.location.hash.match(/^#([a-z0-9]+)\/(\d+)(?:\/\d+)?$/);
        var route = '';
        if (hash && Object.prototype.hasOwnProperty.call(config.bibleBooks, hash[1])) {
            var range = config.bibleBooks[hash[1]];
            var chapter = Number(hash[2]);
            if (chapter >= range[0] && chapter <= range[1]) route = '#' + hash[1] + '/' + chapter;
        }
        return global.location.origin + global.location.pathname + route;
    }

    function safeReferrer() {
        try { return document.referrer ? new URL(document.referrer).origin + '/' : ''; }
        catch (_) { return ''; }
    }

    function command() { global.dataLayer.push(arguments); }

    function pageView() {
        if (choice !== 'granted' || !loaded || global[disableKey]) return;
        var page = safeLocation();
        if (lastPage === page) return;
        lastPage = page;
        command('event', 'page_view', {
            send_to: config.measurementId,
            page_location: page,
            page_title: config.siteName,
            page_referrer: safeReferrer()
        });
    }

    function schedulePageView() {
        if (scheduled) return;
        scheduled = true;
        global.setTimeout(function () { scheduled = false; pageView(); }, 0);
    }

    function enable() {
        global[disableKey] = false;
        if (loaded) { pageView(); return; }
        loaded = true;
        global.dataLayer = global.dataLayer || [];
        global.gtag = command;
        command('consent', 'default', {
            analytics_storage: 'denied', ad_storage: 'denied',
            ad_user_data: 'denied', ad_personalization: 'denied'
        });
        command('consent', 'update', {
            analytics_storage: 'granted', ad_storage: 'denied',
            ad_user_data: 'denied', ad_personalization: 'denied'
        });
        command('js', new Date());
        command('set', 'ads_data_redaction', true);
        command('set', 'url_passthrough', false);
        command('config', config.measurementId, {
            send_page_view: false,
            allow_google_signals: false,
            allow_ad_personalization_signals: false,
            page_location: safeLocation(),
            page_title: config.siteName,
            page_referrer: safeReferrer(),
            // Geen campagnewaarden uit querystrings overnemen.
            campaign_id: '(not set)', campaign_name: '(not set)', campaign_source: '(direct)',
            campaign_medium: '(none)', campaign_term: '(not set)', campaign_content: '(not set)',
            cookie_domain: config.hostname,
            cookie_flags: 'SameSite=Lax;Secure',
            cookie_expires: 60 * 60 * 24 * 180
        });
        var tag = document.createElement('script');
        tag.id = 'ogw-google-tag';
        tag.async = true;
        tag.referrerPolicy = 'no-referrer';
        tag.src = 'https://www.googletagmanager.com/gtag/js?id=' + config.measurementId;
        document.head.appendChild(tag);
        pageView();
    }

    function clearCookies() {
        document.cookie.split(';').forEach(function (entry) {
            var name = entry.split('=')[0].trim();
            if (name !== '_ga' && name.indexOf('_ga_') !== 0) return;
            ['', '; domain=' + config.hostname, '; domain=.' + config.hostname].forEach(function (domain) {
                document.cookie = name + '=; Max-Age=0; path=/' + domain + '; SameSite=Lax; Secure';
            });
        });
    }

    function choose(value, persist) {
        var wasLoaded = loaded;
        choice = value;
        // De officiële opt-out-vlag staat vóór verdere tag-/consentcommando's.
        global[disableKey] = value !== 'granted';
        if (persist !== false) {
            try { global.localStorage.setItem(storageKey, value); } catch (_) { /* Keuze geldt voor deze pagina. */ }
        }
        panel.hidden = true;
        settingsButton.setAttribute('aria-expanded', 'false');
        if (value === 'granted') enable();
        else {
            clearCookies();
            if (wasLoaded) {
                // Geen denied-consentping: stop de geladen tag en laad zonder tag opnieuw.
                var tag = document.getElementById('ogw-google-tag');
                if (tag) tag.remove();
                global.location.reload();
            }
        }
    }

    function init() {
        var style = document.createElement('style');
        style.textContent = '#analytics-consent{position:fixed;bottom:calc(134px + env(safe-area-inset-bottom,0px));right:12px;z-index:10020;' +
            'box-sizing:border-box;width:min(390px,calc(100vw - 24px));max-height:calc(100vh - 154px - env(safe-area-inset-bottom,0px));overflow:auto;padding:18px;border:1px solid var(--border-soft,#d7d4ca);' +
            'border-radius:10px;background:var(--bg-surface,#fff);color:var(--text-primary,#142e42);' +
            'box-shadow:0 4px 24px #0003;font:15px/1.5 system-ui,sans-serif}' +
            '#analytics-consent[hidden]{display:none}#analytics-consent h2{font:600 18px system-ui;margin:0 0 8px}' +
            '#analytics-consent p{margin:0 0 12px}#analytics-consent .analytics-actions{display:flex;gap:10px;flex-wrap:wrap}' +
            '#analytics-consent button,#analytics-settings{font:inherit;cursor:pointer;border:1px solid #52686b;' +
            'border-radius:6px;padding:8px 12px;background:var(--bg-surface,#fff);color:var(--text-primary,#142e42)}' +
            '#analytics-consent button:focus-visible,#analytics-settings:focus-visible{outline:3px solid #c4a048;outline-offset:3px}' +
            '#analytics-settings{position:fixed;right:12px;bottom:calc(88px + env(safe-area-inset-bottom,0px));z-index:10019;font:13px system-ui;box-shadow:0 2px 8px #0002}';
        document.head.appendChild(style);
        panel = document.createElement('section');
        panel.id = 'analytics-consent';
        panel.setAttribute('aria-labelledby', 'analytics-title');
        panel.innerHTML = '<h2 id="analytics-title">Statistieken</h2>' +
            '<p>Met jouw toestemming gebruiken we Google Analytics om te zien welke pagina’s worden gelezen. ' +
            'Daarbij worden cookies geplaatst en ontvangt Google technische bezoekgegevens. ' +
            'We sturen geen zoektermen of formulierinhoud. Je kunt je keuze altijd wijzigen via Statistieken.</p>' +
            '<div class="analytics-actions"><button type="button" id="analytics-accept">Toestaan</button>' +
            '<button type="button" id="analytics-deny">Weigeren</button></div>';
        panel.hidden = choice === 'granted' || choice === 'denied';
        settingsButton = document.createElement('button');
        settingsButton.id = 'analytics-settings';
        settingsButton.type = 'button';
        settingsButton.textContent = 'Statistieken';
        settingsButton.setAttribute('aria-controls', panel.id);
        settingsButton.setAttribute('aria-expanded', String(!panel.hidden));
        settingsButton.onclick = function () {
            panel.hidden = !panel.hidden;
            settingsButton.setAttribute('aria-expanded', String(!panel.hidden));
        };
        document.body.appendChild(panel);
        document.body.appendChild(settingsButton);
        document.getElementById('analytics-accept').onclick = function () { choose('granted'); };
        document.getElementById('analytics-deny').onclick = function () { choose('denied'); };
        if (choice === 'granted') enable();
    }

    global.OGWStatistics = { open: function () {
        if (panel) { panel.hidden = false; settingsButton.setAttribute('aria-expanded', 'true'); }
    } };
    ['pushState', 'replaceState'].forEach(function (method) {
        var original = global.history[method];
        global.history[method] = function () {
            var result = original.apply(this, arguments);
            schedulePageView();
            return result;
        };
    });
    global.addEventListener('hashchange', schedulePageView);
    global.addEventListener('popstate', schedulePageView);
    global.addEventListener('storage', function (event) {
        if (panel && event.key === storageKey && event.newValue !== choice) {
            choose(event.newValue === 'granted' ? 'granted' : 'denied', false);
        }
    });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
})(window);
