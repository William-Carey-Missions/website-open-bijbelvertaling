const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { chromium } = require('playwright');
const root = join(__dirname, '..');
const host = readFileSync(join(root, 'CNAME'), 'utf8').trim();
const source = readFileSync(join(root, 'js/analytics.js'), 'utf8');
const theme = readFileSync(join(root, 'js/theme.js'), 'utf8');
const key = 'ogw_statistics_consent_v1';
let browser;
before(async () => {
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH ||
        (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : '/usr/bin/google-chrome') });
});
after(async () => { if (browser) await browser.close(); });

// An isolated transport records actual browser requests. The Google tag is
// replaced by a small protocol consumer; these tests send no real measurements.
async function fixture(options = {}) {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    const requests = [];
    const html = '<!doctype html><html><head><title>Persoonlijke zoekterm</title>' +
        '<script src="/js/theme.js"></script></head><body><form><input name="email" value="persoon@example.test"></form></body></html>';
    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (/google(tagmanager|-analytics)\.com$/.test(url.hostname)) {
            requests.push({ url: url.href, referrer: route.request().headers().referer || '' });
            if (url.pathname === '/gtag/js') return route.fulfill({ contentType: 'text/javascript', body: `
                window.__commands = [];
                function command(args) {
                    const a = Array.from(args); window.__commands.push(a);
                    if (a[0] === 'event' && a[1] === 'page_view' &&
                        !window['ga-disable-' + a[2].send_to]) {
                        fetch('https://www.google-analytics.com/g/collect?event=page_view&dl=' + encodeURIComponent(a[2].page_location));
                    }
                }
                window.dataLayer.forEach(command);
                window.dataLayer.push = function(args) { command(args); return Array.prototype.push.call(this,args); };
            ` });
            return route.fulfill({ body: '', contentType: 'text/plain' });
        }
        if (url.pathname === '/js/theme.js') return route.fulfill({ contentType: 'text/javascript', body: theme });
        if (url.pathname === '/js/analytics.js') return route.fulfill({ contentType: 'text/javascript', body: source });
        return route.fulfill({ contentType: 'text/html', body: html });
    });
    if (options.choice) await context.addInitScript(({ key, choice }) => { if (localStorage.getItem(key) === null) localStorage.setItem(key, choice); }, { key, choice: options.choice });
    const page = await context.newPage();
    await page.goto((options.base || 'https://' + host) + '/index.html?email=persoon@example.test#genesis/1');
    return { page, context, requests };
}

test('no Google request before a choice or after refusal, including a return visit', async () => {
    const { page, context, requests } = await fixture();
    await page.locator('#analytics-consent').waitFor({ state: 'visible' });
    assert.equal(requests.length, 0);
    await page.click('#analytics-deny');
    assert.equal(await page.evaluate(key => localStorage.getItem(key), key), 'denied');
    await page.reload();
    await page.locator('#analytics-settings').waitFor();
    assert.equal(requests.length, 0);
    await context.close();
});

test('acceptance loads one tag and sends only sanitized manual page views', async () => {
    const { page, context, requests } = await fixture();
    await page.click('#analytics-accept');
    await page.waitForFunction(() => window.__commands?.some(a => a[0] === 'event'));
    await page.evaluate(() => { history.replaceState({}, '', '?query=geheim#genesis/2'); });
    await page.waitForFunction(() => window.__commands.filter(a => a[0] === 'event').length === 2);
    await page.evaluate(() => { window.dispatchEvent(new HashChangeEvent('hashchange')); history.replaceState({}, '', '?email=ander#genesis/2'); });
    await page.waitForTimeout(40);
    const commands = await page.evaluate(() => window.__commands);
    const config = commands.find(a => a[0] === 'config')[2];
    assert.equal(config.send_page_view, false);
    assert.equal(config.allow_google_signals, false);
    assert.equal(config.allow_ad_personalization_signals, false);
    const views = commands.filter(a => a[0] === 'event');
    assert.equal(views.length, 2);
    assert.equal(views[0][2].page_location, 'https://' + host + '/index.html#genesis/1');
    assert.equal(views[1][2].page_location, 'https://' + host + '/index.html#genesis/2');
    assert.doesNotMatch(JSON.stringify(commands), /persoon|geheim|email=|query=|Persoonlijke/);
    assert.equal(requests.filter(r => r.url.includes('/gtag/js')).length, 1);
    assert.equal(requests.find(r => r.url.includes('/gtag/js')).referrer, '');
    await page.evaluate(() => { history.pushState({}, '', '#zoeken/persoon@example.test'); });
    await page.waitForFunction(() => window.__commands.filter(a => a[0] === 'event').length === 3);
    const last = await page.evaluate(() => window.__commands.filter(a => a[0] === 'event').at(-1)[2]);
    assert.equal(last.page_location, 'https://' + host + '/index.html');
    await context.close();
});

test('revocation disables the tag, removes its cookies and does not send a denied ping', async () => {
    const { page, context, requests } = await fixture({ choice: 'granted' });
    await page.waitForFunction(() => window.__commands?.some(a => a[0] === 'event'));
    await page.evaluate(() => { document.cookie = '_ga=fixture; path=/'; });
    await page.click('#analytics-settings');
    const before = requests.length;
    await Promise.all([page.waitForEvent('load'), page.click('#analytics-deny')]);
    await page.locator('#analytics-settings').waitFor();
    assert.equal(requests.length, before);
    assert.equal(await page.evaluate(key => localStorage.getItem(key), key), 'denied');
    assert.doesNotMatch(await page.evaluate(() => document.cookie), /_ga=/);
    await context.close();
});

test('localhost, lookalike origins and iframe documents never initialize statistics', async () => {
    for (const base of ['http://localhost:8000', 'https://' + host + '.example.test']) {
        const { page, context, requests } = await fixture({ base, choice: 'granted' });
        assert.equal(await page.locator('#analytics-settings').count(), 0);
        assert.equal(requests.length, 0);
        await context.close();
    }
    const { page, context, requests } = await fixture();
    await page.evaluate(() => {
        const frame = document.createElement('iframe'); frame.src = '/wiki.html'; document.body.append(frame);
    });
    await page.waitForFunction(() => document.querySelector('iframe').contentDocument?.readyState === 'complete');
    const frame = page.frames()[1];
    assert.equal(await frame.locator('#analytics-settings').count(), 0);
    assert.equal(requests.length, 0);
    await context.close();
});

test('duplicate bootstrap execution does not duplicate the UI, tag or page view', async () => {
    const { page, context, requests } = await fixture({ choice: 'granted' });
    await page.waitForFunction(() => window.__commands?.some(a => a[0] === 'event'));
    await page.addScriptTag({ content: theme });
    await page.addScriptTag({ content: source });
    assert.equal(await page.locator('#analytics-settings').count(), 1);
    assert.equal(requests.filter(r => r.url.includes('/gtag/js')).length, 1);
    assert.equal(await page.evaluate(() => window.__commands.filter(a => a[0] === 'event').length), 1);
    await context.close();
});
