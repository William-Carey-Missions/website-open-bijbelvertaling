const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { startFixture } = require('./helpers/browser-fixture.cjs');
let fixture, browser, base, locationId, pageAs;
before(async () => {
    fixture = await startFixture();
    ({ browser, base, locationId, pageAs } = fixture);
});
after(async () => { await fixture.close(); });

test('management pages apply the saved or system theme before opening display settings', async () => {
    for (const file of ['beoordelingen.html', 'beoordelingsgeschiedenis.html', 'gebruikers.html']) {
        for (const [system, saved, expected] of [
            ['dark', null, 'donker'], ['light', 'auto', 'licht'],
            ['dark', 'licht', 'licht'], ['light', 'donker', 'donker'],
        ]) {
            const page = await pageAs('admin');
            await page.emulateMedia({ colorScheme: system });
            await page.addInitScript(choice => {
                if (choice) localStorage.setItem('sv2026_vertaalopties', JSON.stringify({ thema: choice }));
                document.addEventListener('DOMContentLoaded', () => {
                    window.themeAtDOMContentLoaded = document.documentElement.dataset.theme;
                });
            }, saved);
            await page.goto(base + '/' + file);
            assert.equal(await page.evaluate(() => themeAtDOMContentLoaded), expected, file + ' / ' + system + ' / ' + saved);
            const stored = await page.evaluate(() => localStorage.getItem('sv2026_vertaalopties'));
            const background = await page.locator('body').evaluate(body => getComputedStyle(body).backgroundColor);
            await page.locator('#topnav-weergave').click();
            await page.locator('#sidebar-right[open]').waitFor();
            assert.equal(await page.locator('html').getAttribute('data-theme'), expected);
            assert.equal(await page.locator('body').evaluate(body => getComputedStyle(body).backgroundColor), background);
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('html').getAttribute('data-theme'), expected);
            assert.equal(await page.evaluate(() => localStorage.getItem('sv2026_vertaalopties')), stored);
            await page.close();
        }
    }
});

test('the shared theme toggle changes once before and after loading display settings', async () => {
    for (const file of ['beoordelingen.html', 'over-ov.html', 'statistieken.html', 'index.html#genesis/1']) {
        const page = await pageAs('admin');
        await page.emulateMedia({ colorScheme: 'light' });
        await page.addInitScript(() => {
            localStorage.setItem('sv2026_vertaalopties', JSON.stringify({ thema: 'licht', godsnaam: 'klassiek' }));
        });
        await page.goto(base + '/' + file);
        await page.locator('#topnav-theme-toggle').click();
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'donker', file);
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('sv2026_vertaalopties')).thema), 'donker');
        await page.locator('#topnav-weergave').click();
        await page.locator('#sidebar-right[open]').waitFor();
        assert.equal(await page.evaluate(() => Opties.state.thema), 'donker');
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'donker');
        await page.keyboard.press('Escape');
        await page.locator('#topnav-theme-toggle').click();
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'licht', file);
        assert.equal(await page.evaluate(() => Opties.state.thema), 'licht');
        assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('sv2026_vertaalopties')).godsnaam), 'klassiek');
        await page.locator('#topnav-weergave').click();
        await page.locator('#sidebar-right [data-optie="thema"]').selectOption('donker');
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'donker');
        await page.keyboard.press('Escape');
        await page.close();
    }
});

test('the standalone reader also applies the shared theme without loading the options panel', async () => {
    const page = await pageAs('admin');
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto(base + '/lees.html#genesis/1');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'donker');
    assert.equal(await page.evaluate(() => typeof Opties), 'undefined');
    await page.close();
});

test('cloud and documentation pages apply the same shared theme', async () => {
    const page = await pageAs('admin');
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto(base + '/index.html#genesis/1');
    await page.waitForFunction(() => window.Opties?._initialized);
    await page.addScriptTag({ path: require('node:path').join(__dirname, '../js/cloud-opties.js') });
    await page.evaluate(() => {
        Opties.state.thema = 'donker';
        CloudOpties._applyAll();
    });
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'donker');
    // Sinds de splitsing geen wiki-frame meer: de documentatiepagina zelf.
    await page.goto(base + '/statistieken.html');
    await page.locator('h1').waitFor();
    await page.locator('#topnav-theme-toggle').click();
    await page.locator('html[data-theme="donker"]').waitFor();
    await page.locator('#topnav-weergave').click();
    await page.locator('#sidebar-right[open]').waitFor();
    await page.locator('#sidebar-right [data-optie="thema"]').selectOption('licht');
    await page.locator('html[data-theme="licht"]').waitFor();
    await page.close();
});

test('reader chapter and verse clicks link the authenticated account; signout clears identities', async () => {
    const page = await pageAs('admin');
    await page.goto(base + '/index.html#genesis/1');
    const chapter = page.locator('#chapter-verification');
    const verify = chapter.getByRole('button', { name: 'Verifiëren: Genesis 1', exact: true });
    await verify.waitFor();
    await page.waitForFunction(() => !document.querySelector('#chapter-verification button').disabled);
    await verify.click();
    await chapter.getByText('Verificatie opgeslagen.', { exact: true }).waitFor();
    assert.match(await chapter.innerText(), /Admin/);
    assert.equal(await page.locator('#chapter-title .chapter-concept-tag').count(), 0);
    const verse = page.locator('[data-verification="text-verse:genesis/1/1"]');
    // A chapter review now covers the unchanged components of its verses too.
    await verse.getByRole('button', { name: 'Geverifieerd: Genesis 1:1', exact: true }).waitFor();
    await verse.getByRole('button', { name: 'Beoordelingsacties: Genesis 1:1', exact: true }).click();
    await verse.getByRole('button', { name: 'Intrekken', exact: true }).click();
    await verse.getByRole('button', { name: 'Verifiëren: Genesis 1:1', exact: true }).click();
    await verse.getByText('Verificatie opgeslagen.', { exact: true }).waitFor();
    await page.evaluate(() => setTestUser('reviewer'));
    await page.waitForFunction(() => Collaboration.currentUser?.uid === 'reviewer');
    await chapter.getByRole('button', { name: 'Geverifieerd: Genesis 1', exact: true }).waitFor();
    assert.equal(await page.locator('.verification-author').count(), 0);
    const result = await page.evaluate(async () => (await Collaboration.api('/subject?type=text-chapter&id=genesis/1')).subject);
    assert.equal('latestReview' in result, false);
    await page.evaluate(() => setTestUser(null));
    await chapter.getByRole('button', { name: 'Geverifieerd: Genesis 1', exact: true }).waitFor();
    assert.equal(await chapter.getByRole('button', { name: 'Intrekken' }).count(), 0);
    await page.close();
});

test('location verification uses the same control and permission checks', async () => {
    const page = await pageAs('reviewer');
    await page.goto(base + '/plaats.html?plaats=' + encodeURIComponent(locationId));
    const control = page.locator('.ov-verification');
    const verify = control.getByRole('button', { name: /^Verifiëren:/ });
    await verify.waitFor();
    await page.waitForFunction(() => !document.querySelector('.ov-verification button').disabled);
    await verify.click();
    await control.getByText('Verificatie opgeslagen.', { exact: true }).waitFor();
    assert.equal(await control.locator('.verification-author').count(), 0);
    await page.evaluate(() => setTestUser('admin'));
    await page.waitForFunction(() => Collaboration.currentUser?.email === 'admin@example.test');
    await control.locator('.verification-author').waitFor();
    assert.match(await control.innerText(), /Reviewer/);
    await page.close();
});

test('review history is administrator-only and regular users cannot verify', async () => {
    const page = await pageAs('reviewer');
    await page.goto(base + '/beoordelingen.html');
    await page.locator('.collaboration-main:not([hidden])').waitFor();
    assert.equal(await page.getByRole('link', { name: 'Beoordelingsgeschiedenis', exact: true }).count(), 0);
    await page.goto(base + '/lees.html#genesis/2');
    await page.locator('#chapter-verification button').waitFor();
    await page.evaluate(() => setTestUser('reader'));
    await page.waitForFunction(() => Collaboration.currentUser?.uid === 'reader');
    await page.waitForFunction(() => document.querySelector('#chapter-verification button')?.disabled === true);
    await page.close();
});

test('the top history link opens a separate administrator page with a return link', async () => {
    const page = await pageAs('admin');
    let historyRequests = 0;
    page.on('request', request => {
        if (new URL(request.url()).pathname === '/api/collaboration/reviews' && request.method() === 'GET') historyRequests++;
    });
    await page.goto(base + '/beoordelingen.html');
    await page.locator('.collaboration-main:not([hidden])').waitFor();
    assert.equal(await page.locator('a#review-history-link').getAttribute('href'), 'beoordelingsgeschiedenis.html');
    const open = page.getByRole('link', { name: 'Beoordelingsgeschiedenis', exact: true });
    await open.waitFor();
    await page.waitForFunction(() => document.querySelector('#reviews-page').textContent.length > 0);
    assert.equal(historyRequests, 0, 'History is loaded only when requested');
    const buttonBox = await open.boundingBox();
    assert.ok(buttonBox.y >= 0 && buttonBox.y + buttonBox.height < 720);
    await open.click();
    await page.waitForURL(base + '/beoordelingsgeschiedenis.html');
    await page.getByRole('heading', { name: 'Beoordelingsgeschiedenis', level: 1, exact: true }).waitFor();
    assert.equal(await page.locator('dialog').count(), 0);
    assert.equal(await page.locator('#reviews-table').count(), 0);
    assert.equal(await page.locator('[data-collaboration-link="review"]').getAttribute('class'), 'active');
    await page.waitForFunction(() => document.querySelector('#review-events-page').textContent.length > 0);
    assert.equal(historyRequests, 1);
    assert.equal(await page.evaluate(() => window.scrollY), 0);
    assert.equal(await page.getByRole('button', { name: 'Vorige', exact: true }).isDisabled(), true);
    await page.getByRole('link', { name: 'Terug naar beoordelingen', exact: true }).click();
    await page.waitForURL(base + '/beoordelingen.html');
    await open.waitFor();
    assert.equal(await page.locator('#review-events-table').count(), 0);
    await open.click();
    await page.waitForURL(base + '/beoordelingsgeschiedenis.html');
    await page.locator('#review-events-table tbody tr').first().waitFor();
    await page.evaluate(() => setTestUser('reviewer'));
    await page.waitForURL(url => url.pathname === '/index.html');
    assert.equal(await page.locator('#review-events-table').count(), 0);
    await page.close();
});

test('direct history navigation denies non-administrators without requesting private history', async () => {
    for (const user of ['reviewer', 'reader', null]) {
        const page = await pageAs(user);
        let historyRequests = 0;
        page.on('request', request => {
            if (new URL(request.url()).pathname === '/api/collaboration/reviews') historyRequests++;
        });
        await page.goto(base + '/beoordelingsgeschiedenis.html');
        await page.waitForURL(url => url.pathname === '/index.html');
        assert.equal(historyRequests, 0);
        await page.close();
    }
});

test('a late history response cannot repopulate the page while an account switch resolves', async () => {
    const page = await pageAs('admin');
    let release, captured, delivered;
    const gate = new Promise(resolve => { release = resolve; });
    const capture = new Promise(resolve => { captured = resolve; });
    const delivery = new Promise(resolve => { delivered = resolve; });
    await page.route(url => url.pathname === '/api/collaboration/reviews', async route => {
        const response = await route.fetch();
        captured();
        await gate;
        await route.fulfill({ response });
        delivered();
    });
    let releaseSession;
    const sessionGate = new Promise(resolve => { releaseSession = resolve; });
    await page.route(url => url.pathname === '/api/collaboration/session', async route => {
        if (route.request().headers().authorization !== 'Bearer reviewer') return route.continue();
        await sessionGate;
        await route.continue();
    });
    await page.goto(base + '/beoordelingsgeschiedenis.html');
    await capture;
    await page.evaluate(() => setTestUser('reviewer'));
    await page.waitForFunction(() => !Collaboration.ready && !Collaboration.currentUser);
    release();
    await delivery;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('.collaboration-main').isVisible(), false);
    assert.equal(await page.locator('#review-events-table tbody').innerText(), '');
    releaseSession();
    await page.waitForURL(url => url.pathname === '/index.html');
    await page.close();
});

test('the history page supports pagination, mobile layout, loading errors and an empty history', async () => {
    const page = await pageAs('admin');
    let scenario = 'many';
    const offsets = [];
    await page.route(url => url.pathname === '/api/collaboration/reviews', async route => {
        const offset = Number(new URL(route.request().url()).searchParams.get('offset'));
        offsets.push(offset);
        if (scenario === 'error') return route.fulfill({ status: 500, json: { error: 'Private backend details' } });
        const response = await route.fetch({ url: base + '/api/collaboration/reviews?offset=0&limit=1' });
        const payload = await response.json();
        const count = scenario === 'empty' ? 0 : Math.min(100, 101 - offset);
        await route.fulfill({ json: {
            total: scenario === 'empty' ? 0 : 101,
            items: Array.from({ length: count }, (_, index) => ({ ...payload.items[0],
                id: 'event-' + (offset + index), label: 'Controle ' + (offset + index + 1) })),
        } });
    });
    await page.goto(base + '/beoordelingen.html');
    const open = page.getByRole('link', { name: 'Beoordelingsgeschiedenis', exact: true });
    if (process.env.OV_SCREENSHOTS) {
        await open.waitFor();
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/history-button.png' });
    }
    await open.click();
    await page.waitForURL(base + '/beoordelingsgeschiedenis.html');
    const history = page.locator('.collaboration-main');
    await history.getByText('1–100 van 101', { exact: true }).waitFor();
    assert.equal(await history.locator('tbody tr').count(), 100);
    const next = history.getByRole('button', { name: 'Volgende', exact: true });
    const nextBox = await next.boundingBox();
    assert.ok(nextBox.y >= 0 && nextBox.y + nextBox.height <= 720, 'Pagination is visible without scrolling the table');
    await next.click();
    await history.getByText('101–101 van 101', { exact: true }).waitFor();
    assert.equal(await history.locator('tbody tr').count(), 1);
    assert.equal(await next.isDisabled(), true);
    await history.getByRole('button', { name: 'Vorige', exact: true }).click();
    await history.getByText('1–100 van 101', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.scrollY), 0);
    if (process.env.OV_SCREENSHOTS) {
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/history-desktop.png' });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    const returnBox = await page.getByRole('link', { name: 'Terug naar beoordelingen', exact: true }).boundingBox();
    assert.ok(returnBox.x >= 0 && returnBox.x + returnBox.width <= 390);
    assert.ok(returnBox.y >= 0 && returnBox.y + returnBox.height <= 844);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (process.env.OV_SCREENSHOTS) {
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/history-mobile.png' });
        await page.evaluate(() => document.documentElement.dataset.theme = 'donker');
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/history-mobile-dark.png' });
    }
    scenario = 'error';
    await page.reload();
    await history.getByText('Er is een fout opgetreden. Controleer het logboek.', { exact: true }).waitFor();
    assert.doesNotMatch(await history.innerText(), /Private backend details/);
    scenario = 'empty';
    await page.reload();
    await history.getByText('Nog geen beslissingen.', { exact: true }).waitFor();
    assert.equal(await next.isDisabled(), true);
    assert.equal(await history.getByRole('button', { name: 'Vorige', exact: true }).isDisabled(), true);
    assert.deepEqual(offsets, [0, 100, 0, 0, 0]);
    await page.close();
});

test('an administrator response arriving after signout cannot restore verifier identities', { timeout: 15000 }, async () => {
    const page = await pageAs('admin');
    let release, captured;
    const gate = new Promise(resolve => { release = resolve; });
    const capture = new Promise(resolve => { captured = resolve; });
    let delivered;
    const delivery = new Promise(resolve => { delivered = resolve; });
    await page.route(url => url.pathname === '/api/collaboration/subject'
        && url.searchParams.get('type') === 'text-chapter' && url.searchParams.get('id') === 'genesis/1', async route => {
        if (route.request().headers().authorization !== 'Bearer admin') return route.continue();
        const response = await route.fetch();
        assert.match(await response.text(), /"latestReview"/);
        captured();
        await gate;
        await route.fulfill({ response });
        delivered();
    });
    await page.goto(base + '/index.html#genesis/1');
    await capture;
    await page.evaluate(() => setTestUser(null));
    await page.waitForFunction(() => Collaboration.ready && !Collaboration.currentUser);
    release();
    await delivery;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('.verification-author').count(), 0);
    assert.equal(await page.getByRole('button', { name: 'Intrekken', exact: true }).count(), 0);
    await page.close();
});

test('continuous reading keeps the heading control attached to the visible chapter', async () => {
    const page = await pageAs('admin');
    await page.goto(base + '/index.html#genesis/1');
    await page.locator('#chapter-verification button').first().waitFor();
    await page.evaluate(() => App.renderChapter('genesis', 2, { append: true }));
    assert.equal(await page.locator('#chapter-verification [data-verification]').getAttribute('data-verification'), 'text-chapter:genesis/1');
    await page.locator('.chapter-separator [data-verification="text-chapter:genesis/2"] button').waitFor();
    await page.evaluate(() => App._setTitle('genesis', 2));
    assert.equal(await page.locator('#chapter-verification [data-verification]').getAttribute('data-verification'), 'text-chapter:genesis/2');
    await page.close();
});

test('a changed source file cannot be verified as published content', async () => {
    const page = await pageAs('reviewer');
    await page.route('**/data/genesis/2.json', async route => {
        const response = await route.fetch();
        const chapter = await response.json();
        chapter.verses[0].text2026 = 'Changed browser copy';
        await route.fulfill({ json: chapter });
    });
    await page.goto(base + '/index.html#genesis/2');
    await page.locator('#chapter-verification button').first().waitFor();
    assert.equal(await page.locator('#chapter-verification button').isDisabled(), true);
    assert.match(await page.locator('#chapter-verification button').getAttribute('title'), /gewijzigd/);
    await page.close();
});

test('local edits made after loading cannot be signed as published text', async () => {
    const page = await pageAs('reviewer');
    await page.goto(base + '/index.html#genesis/2');
    const verify = page.locator('#chapter-verification button').first();
    await page.waitForFunction(() => document.querySelector('#chapter-verification button')?.disabled === false);
    let writes = 0;
    page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/reviews')) writes++; });
    await page.evaluate(() => Storage.saveVerse('genesis', 2, 1, { text2026: 'Mijn lokale bewerking' }));
    await verify.click();
    await page.getByText('Lokale bewerkingen kunnen niet als gepubliceerde tekst worden geverifieerd.', { exact: true }).waitFor();
    assert.equal(writes, 0);
    assert.equal(await verify.isDisabled(), true);
    await page.close();
});

test('revisiting a chapter replaces the verification fingerprint with the newly displayed bytes', async () => {
    const page = await pageAs('reviewer');
    await page.goto(base + '/index.html#genesis/1');
    await page.locator('#chapter-verification button').first().waitFor();
    await page.evaluate(() => { DataLoader.prefetchAdjacent = () => {}; location.hash = '#genesis/2'; });
    await page.locator('#chapter-verification [data-verification="text-chapter:genesis/2"] button').first().waitFor();
    await page.route('**/data/genesis/1.json', async route => {
        const response = await route.fetch();
        const chapter = await response.json();
        chapter.verses[0].text2026 = 'A different displayed revision';
        await route.fulfill({ json: chapter });
    });
    await page.evaluate(() => {
        delete DataLoader.chapterCache['nl-ov:genesis:1'];
        location.hash = '#genesis/1';
    });
    await page.locator('#chapter-verification [data-verification="text-chapter:genesis/1"] button').first().waitFor();
    await page.waitForFunction(() => document.querySelector('#chapter-verification button')?.title.includes('gewijzigd'));
    assert.equal(await page.locator('#chapter-title .chapter-concept-tag').count(), 1);
    await page.close();
});

test('administrators can grant and revoke verification permission in user management', async () => {
    const page = await pageAs('admin');
    await page.goto(base + '/gebruikers.html');
    const account = page.locator('#users-table tbody tr').filter({ hasText: 'reader@example.test' });
    await account.getByRole('checkbox', { name: 'Mag verifiëren', exact: true }).check();
    await page.waitForFunction(async () => {
        const users = await Collaboration.api('/users?q=reader@example.test');
        return users.items[0].roles.includes('reviewer');
    });
    await account.getByRole('checkbox', { name: 'Mag verifiëren', exact: true }).uncheck();
    await page.waitForFunction(async () => {
        const users = await Collaboration.api('/users?q=reader@example.test');
        return !users.items[0].roles.includes('reviewer');
    });
    assert.match(await page.locator('#role-events-table').innerText(), /Admin/);
    await page.close();
});

test('mobile verification remains usable in the reading view', async () => {
    const page = await pageAs('admin');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + '/lees.html#genesis/2');
    await page.waitForFunction(() => document.querySelector('#chapter-verification button')?.disabled === false);
    const control = page.locator('#chapter-verification');
    await control.getByRole('button', { name: 'Verifiëren: Genesis 2', exact: true }).click();
    await control.getByText('Verificatie opgeslagen.', { exact: true }).waitFor();
    assert.equal(await page.locator('#chapter-heading .chapter-concept-tag').count(), 0);
    const box = await control.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 390);
    if (process.env.OV_SCREENSHOTS) {
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/reader-mobile.png' });
        await page.getByRole('button', { name: 'Donkere modus', exact: true }).click();
        await page.waitForFunction(() => getComputedStyle(document.body).backgroundColor === 'rgb(26, 26, 46)');
        await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/reader-mobile-dark.png' });
    }
    await page.close();
});

test('leaving an administrator page clears private data before browser history can retain it', async () => {
    const page = await pageAs('admin');
    await page.goto(base + '/index.html#genesis/1');
    await page.locator('#chapter-verification .verification-author').waitFor();
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
    assert.equal(await page.locator('.verification-author').count(), 0);
    await page.close();
});

test('verse verification stays to the right of text and changes without adding row height', async () => {
    const page = await pageAs('reviewer');
    await page.goto(base + '/index.html#genesis/2');
    await page.locator('[data-verification="text-verse:genesis/2/25"] > button').first().waitFor();
    for (const [width, layout, diff] of [[1500, 'naast', false], [1500, 'naast', true],
        [1500, 'eronder', true], [390, 'eronder', false]]) {
        await page.setViewportSize({ width, height: 900 });
        await page.evaluate(({ layout, diff }) => {
            Opties.state.kolomLayout = layout;
            Opties.applyLayoutClass();
            const checkbox = document.querySelector('[data-toggle-col="diff"]');
            checkbox.checked = diff;
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        }, { layout, diff });
        if (width < 768) await page.waitForFunction(() => document.querySelector('#sidebar').getBoundingClientRect().right <= 0);
        await page.waitForFunction(() => {
            const rows = Array.from(document.querySelectorAll('.verse-row'));
            return rows.length === 25 && rows.every(row => row.querySelector('.verification-compact > button'));
        });
        const metrics = await page.evaluate(() => {
            const rows = Array.from(document.querySelectorAll('.verse-row'));
            const rect = element => {
                const { x, y, width, height } = element.getBoundingClientRect();
                return { x, y, width, height };
            };
            const shown = rows.map(row => ({ row: rect(row), number: rect(row.querySelector('.verse-num')),
                text: rect(row.querySelector('.col-2026')),
                changes: rect(row.querySelector('.col-diff')),
                button: rect(row.querySelector('.verification-compact > button')) }));
            const controls = rows.map(row => row.querySelector('.verification-compact'));
            controls.forEach(control => control.style.display = 'none');
            const hidden = rows.map(row => rect(row));
            controls.forEach(control => control.style.removeProperty('display'));
            return { shown, hidden };
        });
        for (let index = 0; index < metrics.shown.length; index++) {
            const { row, button, number, text, changes } = metrics.shown[index];
            assert.ok(Math.abs(row.height - metrics.hidden[index].height) < 1,
                JSON.stringify({ width, layout, diff, verse: index + 1, shown: metrics.shown[index], withoutControl: metrics.hidden[index] }));
            assert.ok(button.y < row.y + 12, 'Button belongs next to the start of its verse');
            assert.ok(button.x >= 0 && button.x + button.width <= width, 'Button remains inside the viewport');
            if (number.width) assert.ok(number.x + number.width + 2 <= button.x, 'Button stays to the right of the verse number');
            assert.ok(text.x + text.width + 2 <= button.x, 'Bible text remains to the left of verification');
            if (changes.width) assert.ok(changes.x + changes.width + 2 <= button.x, 'Verification sits on the changes side without overlapping them');
        }
        if (process.env.OV_SCREENSHOTS) {
            await page.locator('.verse-row').nth(1).scrollIntoViewIfNeeded();
            await page.screenshot({ path: process.env.OV_SCREENSHOTS + '/verse-spacing-' + width + '-' + layout + '-' + diff + '.png' });
        }
    }
    const verse = page.locator('[data-verification="text-verse:genesis/2/2"]');
    await verse.getByRole('button', { name: 'Beoordelingsacties: Genesis 2:2', exact: true }).click();
    await verse.getByRole('button', { name: 'Geverifieerd: Genesis 2:2', exact: true }).waitFor();
    const popup = await verse.locator('.verification-details').boundingBox();
    assert.ok(popup.x >= 0 && popup.x + popup.width <= 390, 'Right-side details open inward and remain on screen');
    await verse.getByRole('button', { name: 'Intrekken', exact: true }).click();
    await verse.getByRole('button', { name: 'Verifiëren: Genesis 2:2', exact: true }).waitFor();
    await page.close();
});

test('historical reviews stay verified; only admins see the ghost and its first sign-in', async () => {
    const publicPage = await pageAs(null);
    for (const reader of ['index.html', 'lees.html']) {
        await publicPage.goto(base + '/' + reader + '#genesis/3');
        await publicPage.locator('#chapter-verification')
            .getByRole('button', { name: 'Geverifieerd: Genesis 3', exact: true }).waitFor();
        assert.equal(await publicPage.locator('.chapter-concept-tag').count(), 0);
        assert.equal(await publicPage.locator('.verification-author').count(), 0);
        assert.doesNotMatch(await publicPage.locator('body').innerText(), /Maarten Vroegindeweij/);
    }
    await publicPage.close();
    const page = await pageAs('admin');
    await page.goto(base + '/lees.html#genesis/3');
    const author = page.locator('#chapter-verification .verification-author');
    await author.waitFor();
    assert.match(await author.innerText(), /Maarten Vroegindeweij \(nog niet aangemeld\)/);
    assert.match(await author.innerText(), /controledatum onbekend.*Geïmporteerd op/);
    const before = await page.evaluate(async () =>
        (await Collaboration.api('/subject?type=text-chapter&id=genesis/3')).subject.latestReview);
    await page.setViewportSize({ width: 390, height: 844 });
    const box = await page.locator('#chapter-verification').boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 390);

    await page.goto(base + '/beoordelingen.html');
    await page.locator('#reviews-table tbody tr').filter({ hasText: 'genesis/3' })
        .getByText('Maarten Vroegindeweij (nog niet aangemeld)', { exact: true }).waitFor();
    await page.getByRole('link', { name: 'Beoordelingsgeschiedenis', exact: true }).click();
    await page.locator('#review-events-table tbody tr').filter({ hasText: 'genesis/3' })
        .getByText(/Maarten Vroegindeweij/).waitFor();
    await page.goto(base + '/gebruikers.html');
    const account = page.locator('#users-table tbody tr').filter({ hasText: 'maartenvroegindeweij@gmail.com' });
    await account.getByText('Nog niet aangemeld', { exact: true }).waitFor();
    await page.evaluate(() => setTestUser('maarten'));
    await page.waitForFunction(() => Collaboration.currentUser?.email === 'maartenvroegindeweij@gmail.com');
    await page.waitForFunction(() => {
        const row = Array.from(document.querySelectorAll('#users-table tbody tr'))
            .find(row => row.textContent.includes('maartenvroegindeweij@gmail.com'));
        return row && !row.textContent.includes('Nog niet aangemeld');
    });
    assert.equal(await account.count(), 1);
    const after = await page.evaluate(async () =>
        (await Collaboration.api('/subject?type=text-chapter&id=genesis/3')).subject.latestReview);
    assert.equal(after.id, before.id);
    assert.equal(after.actor.uid, before.actor.uid);
    assert.equal(after.createdAt, before.createdAt);
    assert.equal(after.actor.registered, true);
    await page.goto(base + '/lees.html#genesis/3');
    await page.locator('#chapter-verification .verification-author').waitFor();
    assert.doesNotMatch(await page.locator('#chapter-verification').innerText(), /nog niet aangemeld/);
    await page.evaluate(() => setTestUser('reviewer'));
    await page.waitForFunction(() => Collaboration.currentUser?.email === 'reviewer@example.test');
    await page.locator('#chapter-verification')
        .getByRole('button', { name: 'Geverifieerd: Genesis 3', exact: true }).waitFor();
    assert.equal(await page.locator('.verification-author').count(), 0);
    await page.close();
});
