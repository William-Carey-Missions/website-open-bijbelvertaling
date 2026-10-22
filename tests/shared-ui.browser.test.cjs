const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { startFixture } = require('./helpers/browser-fixture.cjs');
const menus = require('./fixtures/doc-menus.json');
let fixture;
before(async () => { fixture = await startFixture(); });
after(async () => { await fixture.close(); });

test('documentation menus preserve every existing link, label, active state and indentation', async () => {
    for (const menu of menus) {
        const page = await fixture.pageAs('admin');
        await page.emulateMedia({ colorScheme: 'light' });
        await page.goto(fixture.base + '/' + menu.file);
        const sidebar = page.locator('.doc-sidebar');
        const actual = await sidebar.locator('a').evaluateAll(links => links.map(a => ({
            href: a.getAttribute('href'), label: a.textContent,
            active: getComputedStyle(a).fontWeight === '600',
            child: getComputedStyle(a).paddingLeft === '32px',
        })));
        assert.deepEqual(actual, menu.links, menu.file);
        assert.equal(await sidebar.isVisible(), true);
        const desktop = await sidebar.boundingBox();
        assert.equal(desktop.width, 220, menu.file);
        await page.evaluate(() => OVTheme.apply('donker'));
        const dark = await sidebar.evaluate(nav => {
            const probe = document.createElement('span');
            probe.style.color = 'var(--text-primary)';
            probe.style.background = 'var(--bg-surface)';
            nav.append(probe);
            const expected = { color: getComputedStyle(probe).color, background: getComputedStyle(probe).backgroundColor };
            probe.remove();
            return { expected, background: getComputedStyle(nav).backgroundColor,
                colors: Array.from(nav.querySelectorAll('a')).map(a => getComputedStyle(a).color) };
        });
        assert.equal(dark.background, dark.expected.background, menu.file);
        assert.ok(dark.colors.every(color => color === dark.expected.color), menu.file);
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await sidebar.locator('a').count(), menu.links.length);
        assert.ok((await sidebar.boundingBox()).width <= 390, menu.file);
        const mobilePadding = await sidebar.locator('a').evaluateAll(links => links.map(a => getComputedStyle(a).paddingLeft));
        assert.ok(mobilePadding.every(padding => padding === '10px'), menu.file);
        await page.evaluate(file => {
            const frame = document.createElement('iframe');frame.id = 'menu-frame';frame.src = file;document.body.append(frame);
        }, menu.file);
        const embedded = page.frameLocator('#menu-frame');
        await embedded.locator('.doc-sidebar a').first().waitFor({ state: 'attached' });
        assert.equal(await embedded.locator('.doc-sidebar').isVisible(), false, menu.file);
        assert.equal(await embedded.locator('#topnav').isVisible(), false, menu.file);
        await page.close();
    }
});

test('both iframe link policies preserve hashes, external links and query navigation', async () => {
    for (const [file, preserveQuery] of [['afgoden.html', true], ['changelog.html', false]]) {
        const page = await fixture.pageAs('admin');
        const script = `<script>document.addEventListener('DOMContentLoaded',()=>{
            const box=document.createElement('div');box.id='probe';
            for(const href of ['index.html#genesis/1','#section','?filter=1','mailto:test@example.test','https://example.test','javascript:void(0)']){
                const a=document.createElement('a');a.setAttribute('href',href);a.textContent=href;box.append(a);
            } document.body.append(box);
        });</script>`;
        await page.route('**/' + file, async route => {
            const response = await route.fetch();
            await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head>' + script) });
        });
        await page.goto(fixture.base + '/over-ov.html');
        await page.evaluate(file => {
            const iframe = document.createElement('iframe');iframe.id='probe-frame';iframe.src=file;document.body.append(iframe);
        }, file);
        const frame = page.frameLocator('#probe-frame');
        await frame.locator('#probe').waitFor();
        const targets = await frame.locator('#probe a').evaluateAll(links => links.map(a => a.target));
        assert.deepEqual(targets, ['_top', '', preserveQuery ? '' : '_top', '', '', '']);
        assert.equal(await frame.locator('body').evaluate(body => body.classList.contains('in-iframe')), true);
        assert.equal(await frame.locator('#topnav').isVisible(), false);
        await page.close();
    }
});

test('central book ordering drives both navigation views for every supported mode', async () => {
    const page = await fixture.pageAs('admin');
    await page.goto(fixture.base + '/index.html#genesis/1');
    await page.waitForFunction(() => window.Opties?._initialized);
    const results = await page.evaluate(async () => {
        const manifest = await DataLoader.loadManifest();
        const result = [];
        for (const mode of Object.keys(BookOrders)) {
            Opties.state.boekvolgorde = mode;
            const expected = Object.values(getBookOrderGroups(mode, manifest)).flat();
            const assigned = new Set(expected);
            expected.push(...manifest.books.filter(b => !assigned.has(b.id) && isBookVisibleInNavigation(b)).map(b => b.id));
            await Navigation.renderBookNav();
            await Sidebar.renderTree();
            result.push({ mode, expected,
                nav: Array.from(document.querySelectorAll('#book-nav [data-book-id]')).map(a => a.dataset.bookId),
                sidebar: Array.from(document.querySelectorAll('#sidebar-tree .tree-book')).map(a => a.dataset.bookId),
            });
        }
        return result;
    });
    for (const result of results) {
        assert.deepEqual(result.nav, result.expected, result.mode);
        assert.deepEqual(result.sidebar, result.expected, result.mode);
    }
    await page.close();
});

async function realAuthPage() {
    const page = await fixture.browser.newPage({ serviceWorkers: 'block' });
    await page.route('https://**', route => route.abort());
    await page.route('**/js/firebase-config.js', route => route.fulfill({ contentType: 'text/javascript',
        body: 'window.firebaseConfig={};window.firebaseEnabled=true;' }));
    await page.route('https://www.gstatic.com/firebasejs/*/firebase-app.js', route => route.fulfill({ contentType: 'text/javascript',
        body: `export function initializeApp(){window.sdkInitializations=(window.sdkInitializations||0)+1;return {};}` }));
    await page.route('https://www.gstatic.com/firebasejs/*/firebase-firestore.js', route => route.fulfill({ contentType: 'text/javascript',
        body: 'export function getFirestore(){return {};}' }));
    await page.route('https://www.gstatic.com/firebasejs/*/firebase-auth.js', route => route.fulfill({ contentType: 'text/javascript', body: `
        let listener;
        export function getAuth(){return {};}
        export function onAuthStateChanged(auth, callback){window.sdkSubscriptions=(window.sdkSubscriptions||0)+1;listener=callback;callback(null);}
        export class GoogleAuthProvider {setCustomParameters(){}}
        export async function signInWithPopup(){listener({uid:'admin',email:'admin@example.test',displayName:'Admin',getIdToken:async()=> 'admin'});}
        export async function signOut(){listener(null);}
    ` }));
    return page;
}

test('one auth startup supports login, private roles, logout and mobile navigation', async () => {
    const page = await realAuthPage();
    await page.goto(fixture.base + '/over-ov.html');
    await page.locator('.auth-login').waitFor();
    const scripts = await page.locator('script[src]').evaluateAll(nodes => nodes.map(n => new URL(n.src).pathname));
    assert.equal(scripts.filter(src => src === '/js/auth.js').length <= 1, true, 'Auth must not be injected and statically loaded');
    assert.equal(await page.evaluate(() => sdkInitializations), 1);
    assert.equal(await page.evaluate(() => sdkSubscriptions), 1);
    await page.locator('.auth-login').click();
    await page.waitForFunction(() => Collaboration.currentUser?.roles.includes('administrator'));
    await page.locator('[data-collaboration-link="users"]').waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#topnav-hamburger').click();
    await page.locator('.auth-logout').click();
    await page.waitForFunction(() => Collaboration.ready && !Collaboration.currentUser);
    assert.equal(await page.locator('[data-collaboration-link]').count(), 0);
    assert.equal(await page.evaluate(() => sdkSubscriptions), 1);
    await page.close();
});

test('a delayed auth dependency resolves before administrator page listeners run', async () => {
    const page = await fixture.pageAs('admin');
    await page.addInitScript(() => {
        window.documentLoaded = false;
        document.addEventListener('DOMContentLoaded', () => { window.documentLoaded = true; });
    });
    let release, captured;
    const gate = new Promise(resolve => { release = resolve; });
    const seen = new Promise(resolve => { captured = resolve; });
    await page.route('**/js/auth.js', async route => {
        captured();await gate;await route.fulfill({ contentType:'text/javascript', body:'' });
    });
    const errors=[];page.on('pageerror', error => errors.push(String(error)));
    const navigation=page.goto(fixture.base + '/beoordelingsgeschiedenis.html');
    await seen;
    await page.waitForFunction(() => document.getElementById('review-events-table'));
    assert.equal(await page.evaluate(() => documentLoaded), false);
    release();await navigation;
    await page.locator('#review-events-table tbody tr').first().waitFor();
    assert.deepEqual(errors, []);
    await page.close();
});

test('nested manuscript pages also start auth exactly once', async () => {
    const page = await realAuthPage();
    await page.goto(fixture.base + '/handschriften/genesis.html');
    await page.locator('.auth-login').waitFor();
    assert.equal(await page.evaluate(() => sdkInitializations), 1);
    assert.equal(await page.evaluate(() => sdkSubscriptions), 1);
    await page.close();
});

