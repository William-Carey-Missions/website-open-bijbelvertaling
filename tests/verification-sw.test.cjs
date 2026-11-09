const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function worker(caches, fetch) {
    const handlers = {};
    vm.runInNewContext(fs.readFileSync('sw.js', 'utf8'), {
        self: { addEventListener: (name, fn) => { handlers[name] = fn; },
            location: { origin: 'https://example.test' }, clients: { claim: async () => {} } },
        caches, fetch, URL, console,
    });
    return handlers;
}

test('API and authenticated GETs bypass every service-worker cache', async () => {
    let networkCalls = 0;
    const handlers = worker(new Proxy({}, { get() { throw Error('Unexpected cache access'); } }),
        async (_request, options) => {
            assert.equal(options.cache, 'no-store');
            networkCalls++;
            return new Response('{}');
        });
    for (const request of [
        new Request('https://example.test/api/collaboration/subject'),
        new Request('https://example.test/private', { headers: { Authorization: 'Bearer user' } }),
    ]) {
        let response;
        handlers.fetch({ request, respondWith(promise) { response = promise; } });
        await response;
    }
    assert.equal(networkCalls, 2);
});

test('activation removes private responses retained by previous workers', async () => {
    const removed = [];
    const requests = [
        new Request('https://example.test/api/collaboration/reviews'),
        new Request('https://example.test/private', { headers: { Authorization: 'Bearer user' } }),
        new Request('https://example.test/data/books.json'),
    ];
    const handlers = worker({
        keys: async () => ['data-v0.56.0'],
        open: async () => ({ keys: async () => requests, delete: async r => removed.push(r.url) }),
        delete: async () => true,
    });
    let completed;
    handlers.activate({ waitUntil(promise) { completed = promise; } });
    await completed;
    assert.deepEqual(removed, requests.slice(0, 2).map(r => r.url));
});

test('extensionless document URLs such as /index fetch current HTML before old cache', async () => {
    const handlers = worker({ open: async () => ({
        match: async () => new Response('old HTML'), put: async () => {},
    }) }, async () => new Response('current HTML'));
    let response;
    handlers.fetch({ request: { url: 'https://example.test/index', method: 'GET', mode: 'navigate', destination: 'document', headers: new Headers() }, respondWith(p) { response = p; } });
    assert.equal(await (await response).text(), 'current HTML');
});

test('audio manifests and byte-range requests bypass the shell cache', async () => {
    const handlers = worker(new Proxy({}, { get() { throw Error('Unexpected cache access'); } }),
        async request => new Response(request.headers.get('Range') || 'fresh catalog'));
    for (const request of [
        new Request('https://example.test/audio/higgs-20261109/catalogus.json'),
        new Request('https://example.test/audio/higgs-20261109/nl-ov/genesis/1-m.mp3', {headers:{Range:'bytes=0-127'}}),
    ]) {
        let response;
        handlers.fetch({request,respondWith(p) {response=p;}});
        assert.equal(await (await response).text(),request.headers.get('Range') || 'fresh catalog');
    }
});
