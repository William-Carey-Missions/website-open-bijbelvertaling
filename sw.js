/* Open Vertaling — Service Worker
 *
 * Strategieën:
 *   - shell (HTML/CSS/JS): cache-first met background network-update
 *   - data (JSON): network-first — bewerkte verzen+stats altijd vers, cache als offline-fallback
 *   - lexicon (grote JS): cache-first, geen revalidate (zelden gewijzigd)
 *
 * Versionering: bump VERSION bij elke deploy om alle caches te vernieuwen.
 */

const VERSION = 'v0.60.0';
// New reader modules must not be mixed with HTML from before verification.
const CACHE_VERSION = `${VERSION}-verification-v13-splitsing1-ontwerp1-kunst20261025-publicatie20261025-statistics-consent1`;
const SHELL_CACHE   = `shell-${CACHE_VERSION}`;
const DATA_CACHE    = `data-${CACHE_VERSION}`;
const LEXICON_CACHE = `lexicon-${CACHE_VERSION}`;

// Pre-cache: minimal kritieke files voor instant 1e bezoek
const PRECACHE_URLS = [
    '/',
    '/index.html',
    '/llms.txt',
    '/LLM.txt',
    '/css/publication.css',
    '/images/branding/open-vertaling-logo-light.svg',
    '/js/theme.js',
    '/js/analytics.js?v=1',
    '/js/auth-bootstrap.js',
    '/js/firebase-config.js',
    '/js/auth.js',
    '/js/iframe-navigation.js',
    '/css/style.css',
    '/js/storage.js',
    '/js/i18n.js',
    '/js/reader-policy.js',
    '/js/teksteditie.js',
    '/js/data-loader.js',
    '/js/verification.js',
    '/js/review-components.js',
    '/js/verification-display.js',
    '/js/collaboration.js',
    '/correcties.html',
    '/js/corrections.js',
    '/css/corrections.css',
    '/css/collaboration.css',
    '/js/chapter-renderer.js',
    '/css/verification.css',
    '/js/citatie-uit.js',
    '/js/assets.js',
    '/js/book-orders.js',
    '/js/navigation.js',
    // Lokale fonts — pre-cachen zodat ze ook in slechte verbinding-situaties direct aanwezig zijn
    // Ontwerp 2026: Source Serif 4 (Bijbeltekst), IBM Plex Sans/Mono (interface).
    // Alleen de latin-subsets; latin-ext laadt de browser pas als een tekst
    // die tekens nodig heeft. Fira Sans en EB Garamond zijn geen hoofdletter
    // meer en worden niet meer vooraf opgehaald.
    '/fonts/source-serif-4-latin-normal.woff2',
    '/fonts/source-serif-4-latin-italic.woff2',
    '/fonts/ibm-plex-sans-latin-400.woff2',
    '/fonts/ibm-plex-sans-latin-500.woff2',
    '/fonts/ibm-plex-sans-latin-600.woff2',
    '/fonts/ibm-plex-mono-latin-500.woff2',
    '/fonts/noto-serif-hebrew.woff2',
    '/css/fonts.css',
    '/css/ontwerp.css',
    '/js/startscherm.js',
    '/js/sidebar.js',
    '/js/app.js',
    '/js/opties.js',
    '/js/optie-maten.js',
    '/js/references.js',
    '/js/verwijzing-popup.js',
    '/css/verwijzing-popup.css',
    '/js/editor.js',
    '/js/export.js',
    '/js/verse-select.js',
    '/js/highlight.js',
    '/js/tags.js',
    '/js/search.js',
    '/js/cloud-opties.js',
    '/js/sites.js',
    '/data/books.json',
    '/i18n/nl.json',
    '/data/stats.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(SHELL_CACHE).then(cache =>
            // Per file proberen — als 1 faalt, geen volledige install-fail
            Promise.allSettled(PRECACHE_URLS.map(url =>
                cache.add(url).catch(err => console.warn('SW precache miss:', url, err))
            ))
        ).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        // Verwijder oude caches
        const keys = await caches.keys();
        // Remove authenticated responses saved by older versions of the worker.
        for (const key of keys) {
            const cache = await caches.open(key);
            for (const request of await cache.keys()) {
                if (new URL(request.url).pathname.startsWith('/api/') || request.headers.has('Authorization')) {
                    await cache.delete(request);
                }
            }
        }
        await Promise.all(
            keys.filter(k => ![SHELL_CACHE, DATA_CACHE, LEXICON_CACHE].includes(k))
                .map(k => caches.delete(k))
        );
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);
    // Only handle same-origin
    if (url.origin !== self.location.origin) return;

    const path = url.pathname;
    if (path.startsWith('/api/') || req.headers.has('Authorization')) {
        event.respondWith(fetch(req, { cache: 'no-store' }));
        return;
    }

    // Lexicon (grote JS)
    if (path.endsWith('/js/hebreeuws-woordenboek.js') || path.endsWith('/js/grieks-woordenboek.js') || path.endsWith('/js/grieks-tbesg.js')) {
        event.respondWith(cacheFirst(req, LEXICON_CACHE));
        return;
    }

    // Data files (JSON in /data/): network-first — bewerkte verzen + stats altijd
    // direct vers; cache alleen als offline-fallback. (Voorheen stale-while-
    // revalidate, waardoor net-bewerkte tekst één refresh achterliep.)
    if (path.startsWith('/data/') && (path.endsWith('.json') || path.endsWith('.geojson'))) {
        event.respondWith(networkFirst(req, DATA_CACHE));
        return;
    }

    // Merkbestanden en hoofdstukinitialen houden stabiele publieke bestandsnamen.
    // Haal ze online eerst opnieuw op, zodat vernieuwde beelden niet achter een
    // oude cache blijven hangen; offline blijft de laatste versie beschikbaar.
    if (path.startsWith('/images/branding/') || path.startsWith('/images/initialen/') ||
        path === '/favicon.svg' || path.startsWith('/icons/')) {
        event.respondWith(networkFirst(req, SHELL_CACHE));
        return;
    }

    // CSS + JS: network-first — stijl/gedrag-wijzigingen meteen zichtbaar,
    // cache alleen als fallback (offline). Voorkomt "verandering pas na 2e refresh".
    if (path.endsWith('.css') || path.endsWith('.js')) {
        event.respondWith(networkFirst(req, SHELL_CACHE));
        return;
    }

    // HTML: network-first — altijd de nieuwste pagina als online (voorkomt dat
    // mobiel een versie achterloopt met verouderde JS-structuur); cache = offline-fallback.
    // Een adres dat op / eindigt (bijv. /bijbel/genesis/) is ook een pagina.
    if (path.endsWith('.html') || path.endsWith('/')) {
        event.respondWith(networkFirst(req, SHELL_CACHE));
        return;
    }

    // Deze twee wiki-illustraties kunnen opnieuw gegenereerd worden onder
    // dezelfde stabiele bestandsnaam. Haal ze daarom online altijd vers op.
    if (/\/images\/wiki\/(?:bronnen\/)?(?:liederen|gebeden)\.webp$/.test(path)) {
        event.respondWith(networkFirst(req, SHELL_CACHE));
        return;
    }

    // Fonts, images, alles anders: cache-first
    event.respondWith(cacheFirst(req, SHELL_CACHE));
});

/** Cache-first: gebruik cache, fetch alleen als miss. */
async function cacheFirst(req, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(req);
    if (cached) return cached;
    try {
        const resp = await fetch(req);
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
    } catch (e) {
        return new Response('Offline en niet in cache', { status: 503 });
    }
}

/** Cache-first met background refresh. Gebruiker krijgt direct cached versie,
 *  cache wordt op achtergrond geüpdatet voor volgende bezoek. */
async function cacheFirstWithRefresh(req, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(req);
    const fetchPromise = fetch(req).then(resp => {
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
    }).catch(() => cached || Response.error());
    return cached || fetchPromise;
}

/** Network-first: probeer netwerk, val terug op cache bij offline.
 *  Voor CSS/JS zodat wijzigingen direct zichtbaar zijn. 'no-cache' vraagt de
 *  server bij elk verzoek of het bestand veranderd is; is dat niet zo, dan komt
 *  er alleen een korte 304 terug in plaats van het hele bestand ('no-store'
 *  downloadde bij elk bezoek alle scripts en hoofdstukdata opnieuw). */
async function networkFirst(req, cacheName) {
    const cache = await caches.open(cacheName);
    try {
        const resp = await fetch(req, { cache: 'no-cache' });
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
    } catch (e) {
        const cached = await cache.match(req);
        return cached || new Response('Offline en niet in cache', { status: 503 });
    }
}

/** Stale-while-revalidate: cached versie direct, fetch op achtergrond. */
async function staleWhileRevalidate(req, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(req);
    const fetchPromise = fetch(req).then(resp => {
        if (resp.ok) cache.put(req, resp.clone());
        return resp;
    }).catch(() => null);
    return cached || fetchPromise || new Response('Offline en niet in cache', { status: 503 });
}

// Message handler — voor cache-clear van app
self.addEventListener('message', (event) => {
    if (event.data === 'clearAllCaches') {
        event.waitUntil((async () => {
            const keys = await caches.keys();
            await Promise.all(keys.map(k => caches.delete(k)));
            self.clients.matchAll().then(clients =>
                clients.forEach(c => c.postMessage('cachesCleared'))
            );
        })());
    }
});
