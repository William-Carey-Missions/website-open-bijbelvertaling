/* Open Vertaling — gedeelde bovenbalk (shared nav).
 * Gebruik: laad /js/auth-bootstrap.js als module in de head; plaats
 * <nav id="topnav"></nav> in de body en laad dit script er direct na.
 * Injecteert de canonieke balk (merk, links, zoekbalk, thema-knop, auth-slot, hamburger)
 * en zet de actieve link op basis van de huidige pagina. Zo blijft de nav overal gelijk. */
(function () {
    /* www doorsturen naar het kale domein.
       De site is op twee adressen bereikbaar, en dat zijn voor de browser en
       voor externe diensten twee losse werelden: aparte sessie, aparte
       localStorage met je instellingen en markeringen, aparte caches, en een
       tweede versie voor zoekmachines terwijl de canonical naar het kale
       domein wijst. Het feedbackformulier werkte er ook niet, omdat de
       maildienst per domein moet worden vrijgegeven.
       Hoort eigenlijk als 301 in de serverconfiguratie; tot die er is doen we
       het hier. replace() en geen href, zodat de terugknop niet vastloopt. */
    if (location.hostname === 'www.openvertaling.nl') {
        location.replace('https://openvertaling.nl' + location.pathname +
                         location.search + location.hash);
        return;
    }

    /* Adressen van de zustersites (OGW voor wiki en achtergrond). Pagina's
       die ze al bij het laden nodig hebben, laden sites.js zelf vooraan. */
    if (!window.KASites && !document.querySelector('script[src$="sites.js"]')) {
        var sitesScript = document.createElement('script');
        sitesScript.src = 'js/sites.js';
        document.head.appendChild(sitesScript);
    }

    var nav = document.getElementById('topnav');
    if (!nav) return;

    if (!document.querySelector('script[src$="global-options-host.js"]')) {
        var hostScript = document.createElement('script');
        hostScript.src = 'js/global-options-host.js';
        document.head.appendChild(hostScript);
    }

    /* Ingebed in de wiki? Die laadt pagina's in een iframe, en dan verschijnt
       de hele site nóg een keer binnen zichzelf: een tweede bovenbalk, en bij
       acht pagina's ook een tweede documentatie-zijbalk. Binnen een iframe
       renderen we daarom geen navigatie en laden we de zweefknoppen niet. De
       markering op <html> laat de CSS de eigen zijbalk van de pagina en de
       lege balk verbergen. */
    var ingebed;
    try { ingebed = window.self !== window.top; }
    catch (e) { ingebed = true; }   // andere herkomst: dan zitten we zeker ingebed
    if (ingebed) {
        document.documentElement.classList.add('ov-ingebed');
        return;
    }

    nav.innerHTML =
        '<div class="topnav-brand">' +
            '<a class="topnav-brand-link" href="index.html" aria-label="Open Vertaling — naar de startpagina">' +
                '<img class="topnav-logo" src="/images/branding/open-vertaling-logo-light.svg" alt="Open Vertaling" width="200" height="60" fetchpriority="high">' +
            '</a>' +
        '</div>' +
        '<div class="topnav-links" id="topnav-links">' +
            '<a href="/over-ov.html">Over ons</a>' +
            '<a href="index.html#johannes/1">Tekst</a>' +
            '<button class="topnav-mobile-weergave" id="topnav-mobile-weergave" type="button" aria-label="Weergave openen" aria-controls="sidebar-right" aria-expanded="false">Weergave</button>' +
        '</div>' +
        '<input type="search" id="topnav-search-input" class="topnav-search-input" placeholder="Zoek in Gods Woord… (Ctrl+K)" autocomplete="off" aria-label="Zoeken in Gods Woord" onkeydown="if(event.key===\'Enter\'){var q=this.value.trim();if(q){location.href=\'index.html?q=\'+encodeURIComponent(q);}}">' +
        '<button class="topnav-weergave" id="topnav-weergave" type="button" aria-label="Weergave openen" aria-controls="sidebar-right" aria-expanded="false" title="Weergave"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h10"/><path d="M18 7h2"/><circle cx="16" cy="7" r="2"/><path d="M4 17h3"/><path d="M11 17h9"/><circle cx="9" cy="17" r="2"/></svg><span>Weergave</span></button>' +
        '<button class="topnav-theme" id="topnav-theme-toggle" title="Thema: licht/donker" aria-label="Wissel thema"><svg class="theme-icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg><svg class="theme-icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>' +
        '<a class="topnav-wcm" href="https://williamcareymissions.nl/" target="_blank" rel="noopener" aria-label="William Carey Missions"><img src="/images/branding/william-carey-missions.png" alt="" width="36" height="36"><span>William Carey<br>Missions</span></a>' +
        '<span id="topnav-auth-home" hidden></span>' +
        '<div id="auth-slot" class="topnav-auth"></div>' +
        '<button class="topnav-hamburger" id="topnav-hamburger" onclick="document.getElementById(\'topnav-links\').classList.toggle(\'open\');this.classList.toggle(\'open\')" title="Menu" aria-label="Menu" aria-expanded="false"><span></span><span></span><span></span></button>';

    var footer = document.createElement('footer');
    footer.className = 'ka-footer';
    footer.id = 'ka-footer';
    footer.innerHTML = '<div class="ka-footer-in"><div><strong>Open Vertaling</strong>' +
        '<p>Een herziening van de Statenvertaling. Vrij te gebruiken onder CC0.</p></div>' +
        '<nav aria-label="Lezen"><a href="index.html#johannes/1">Bijbel</a><a href="downloads.html">Downloads</a></nav>' +
        '<nav aria-label="Over ons"><a href="https://williamcareymissions.nl/over-ons" target="_blank" rel="noopener">William Carey Missions</a></nav></div>';
    function plaatsFooter() { if (!footer.isConnected) document.body.appendChild(footer); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', plaatsFooter);
    else plaatsFooter();

    // Gebruik overal exact hetzelfde auth-element. Op mobiel staat het in het
    // hamburgermenu; op grotere schermen keert het terug naar de hoofdbalk.
    var authSlot = document.getElementById('auth-slot');
    var authHome = document.getElementById('topnav-auth-home');
    var navLinks = document.getElementById('topnav-links');
    var mobileAuthQuery = window.matchMedia('(max-width: 768px)');
    function placeAuthSlot() {
        if (!authSlot || !authHome || !navLinks) return;
        if (mobileAuthQuery.matches) navLinks.appendChild(authSlot);
        else authHome.insertAdjacentElement('afterend', authSlot);
    }
    placeAuthSlot();
    if (mobileAuthQuery.addEventListener) mobileAuthQuery.addEventListener('change', placeAuthSlot);
    else if (mobileAuthQuery.addListener) mobileAuthQuery.addListener(placeAuthSlot);

    var optiesKnoppen = [
        document.getElementById('topnav-weergave'),
        document.getElementById('topnav-mobile-weergave')
    ].filter(Boolean);
    function openWeergave(trigger) {
            if (window.OptionsPanel && document.getElementById('sidebar-right')) {
                // De hoofdlezer heeft het paneel al in het document; daar
                // hoeft de host niet eerst asynchroon te worden geladen.
                window.OptionsPanel.open(trigger);
            } else if (window.GlobalOptionsHost) {
                window.GlobalOptionsHost.ensure().then(function () {
                    window.OptionsPanel.open(trigger);
                });
            } else {
                window.addEventListener('ov:options-host-loaded', function () {
                    openWeergave(trigger);
                }, { once: true });
            }
    }
    optiesKnoppen.forEach(function (optiesKnop) {
        optiesKnop.dataset.globalOptionsBound = 'true';
        optiesKnop.addEventListener('click', function () { openWeergave(optiesKnop); });
    });

    document.getElementById('topnav-theme-toggle').addEventListener('click', function () {
        window.OVTheme.toggle();
    });

    var page = (location.pathname.split('/').pop() || 'index.html');
    nav.querySelectorAll('.topnav-links a').forEach(function (link) {
        const href = link.getAttribute('href') || '';
        if (href.split('#')[0] === page) link.classList.add('active');
    });

    // Mobiele zoomregeling (zweefknop −/+) — self-contained, op elke pagina.
    if (!document.querySelector('script[src$="zoom.js"]')) {
        var zs = document.createElement('script'); zs.src = 'js/zoom.js'; zs.async = false;
        document.head.appendChild(zs);
    }

    // Scherm aan houden — alleen waar daadwerkelijk gelezen wordt, niet op
    // contact- of overzichtspagina's waar niemand lang blijft.
    var leespagina = (page === 'index.html' || page === 'lees.html' || page === '');
    if (leespagina && !document.querySelector('script[src$="wake-lock.js"]')) {
        var ws = document.createElement('script'); ws.src = 'js/wake-lock.js'; ws.async = false;
        document.head.appendChild(ws);
    }

    // Natuurgeluid onder de voorlezing. Doet niets zolang er geen opnames in
    // data/natuurgeluiden.json staan, dus veilig om altijd te laden.
    if (leespagina && !document.querySelector('script[src$="natuurgeluid.js"]')) {
        var ns = document.createElement('script'); ns.src = 'js/natuurgeluid.js'; ns.async = false;
        document.head.appendChild(ns);
    }
})();
