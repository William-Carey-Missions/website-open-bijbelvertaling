const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const menus = require('./fixtures/doc-menus.json');
const root = resolve(__dirname, '..');
const read = file => readFileSync(resolve(root, file), 'utf8');
const pages = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '*.html'], { cwd: root, encoding: 'utf8' })
    .split('\0').filter(Boolean).map(file => [file, read(file)]);

test('all navigation and standalone auth consumers use exactly one module entry', () => {
    let checked = 0;
    const standalone = ['lees.html', 'mockup-leesversie.html', 'technisch.html'];
    for (const [file, html] of pages) {
        assert.doesNotMatch(html, /<script[^>]+src=["'][^"']*\/(?:auth|firebase-config|collaboration)\.js["']/, file);
        if (!html.includes('topnav.js') && !standalone.includes(file)) continue;
        const entries = [...html.matchAll(/<script type="module" src="\/js\/auth-bootstrap.js"><\/script>/g)];
        assert.equal(entries.length, 1, file);
        assert.ok(entries[0].index < html.indexOf('</head>'), file);
        checked++;
    }
    assert.equal(checked, 138);
    assert.doesNotMatch(read('js/topnav.js'), /firebase-config\.js|auth\.js|collaboration\.js/);
    const bootstrap = read('js/auth-bootstrap.js');
    assert.deepEqual([...bootstrap.matchAll(/import '([^']+)';/g)].map(m => m[1]),
        ['./firebase-config.js', './auth.js', './collaboration.js']);
    assert.ok(bootstrap.indexOf('Collaboration.init()') < bootstrap.indexOf('Auth.init()'));
    for (const file of ['js/auth.js', 'js/collaboration.js']) {
        assert.doesNotMatch(read(file), /DOMContentLoaded|initializing|initialized|if \(window\.(?:Auth|Collaboration)\) return;/);
    }
});

test('all 18 iframe handlers share one implementation with the original query policy', () => {
    const preserveQuery = new Set(['afgoden', 'bomen-planten', 'dieren', 'gebeden', 'gereedschap',
        'liederen', 'materialen', 'muziekinstrumenten', 'personen', 'voedsel', 'volken-naties']);
    const topQuery = new Set(['changelog', 'geografie', 'grondteksten', 'handschriften-henoch',
        'handschriften', 'lexicon-abbott', 'lexicon-bdb']);
    let checked = 0;
    for (const [file, html] of pages) {
        assert.doesNotMatch(html, /a\.target\s*=\s*['_"]_top['"]/, file);
        const name = file.replace('.html', '');
        if (!preserveQuery.has(name) && !topQuery.has(name)) continue;
        const tags = [...html.matchAll(/<script src="js\/iframe-navigation.js"([^>]*)><\/script>/g)];
        assert.equal(tags.length, 1, file);
        assert.equal(tags[0][1].includes('data-preserve-query'), preserveQuery.has(name), file);
        checked++;
    }
    assert.equal(checked, 18);
});

test('all seven document menus use the shared renderer and stylesheet without inline copies', () => {
    for (const { file } of menus) {
        const html = read(file);
        assert.match(html, /<nav class="doc-sidebar" data-doc-menu="[^"]+"><\/nav>/, file);
        assert.equal(html.split('src="js/doc-sidebar.js"').length - 1, 1, file);
        assert.equal(html.split('href="css/doc-sidebar.css"').length - 1, 1, file);
        assert.doesNotMatch(html, /width:220px|border-left:3px solid transparent/, file);
    }
    assert.doesNotMatch(read('css/style.css'), /nav\[style\*="background: ?#f5f2ed"\]/);
});

test('both book menus consume the canonical ordering instead of copied fallback dictionaries', () => {
    for (const file of ['js/navigation.js', 'js/sidebar.js']) {
        assert.match(read(file), /const bookOrder = getBookOrderGroups\(mode, manifest\);/);
        assert.doesNotMatch(read(file), /Pentateuch|Brieven van Paulus|typeof getBookOrderGroups/);
    }
    const html = read('index.html');
    const scripts = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map(match => match[1].split('?')[0]);
    for (const file of ['navigation', 'sidebar']) {
        assert.ok(scripts.indexOf('js/book-orders.js') >= 0);
        assert.ok(scripts.indexOf('js/book-orders.js') < scripts.indexOf('js/' + file + '.js'));
    }
});

test('the worker caches the shared modules and their local dependencies', () => {
    for (const file of ['js/auth-bootstrap.js', 'js/firebase-config.js', 'js/auth.js', 'js/collaboration.js',
        'js/iframe-navigation.js', 'js/doc-sidebar.js', 'css/doc-sidebar.css']) {
        assert.ok(read(file).split('\n').length < 1000, file);
        assert.ok(read('sw.js').includes("'/" + file + "'"), file);
    }
    assert.match(read('sw.js'), /zonderbeoordeling20261115/);
});
