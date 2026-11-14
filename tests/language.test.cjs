const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');
const source = readFileSync(new URL('../assets/app.js', `file://${__filename}`), 'utf8');

function page(href, links = []) {
  let url = new URL(href);
  const listeners = {};
  const history = [url.href];
  let position = 0;
  const location = {};
  for (const key of ['href', 'search', 'hash', 'origin', 'protocol']) {
    Object.defineProperty(location, key, { get: () => url[key] });
  }
  function element(attrs) {
    return {
      attrs, dataset: { lang: attrs['data-lang'] }, listeners: {},
      getAttribute: name => attrs[name],
      hasAttribute: name => Object.hasOwn(attrs, name),
      setAttribute: (name, value) => { attrs[name] = value; },
      addEventListener(name, callback) { this.listeners[name] = callback; },
    };
  }
  const buttons = ['en', 'ru'].map(lang => element({ 'data-lang': lang }));
  const anchors = links.map(link => element(typeof link === 'string' ? { href: link } : link));
  const detail = { tagName: 'DETAILS', open: false };
  const document = {
    documentElement: { lang: 'en', dataset: { enTitle: 'English title', ruTitle: 'Русский заголовок' } },
    title: 'English title',
    querySelectorAll: selector => ({ '[data-lang]': buttons, 'a[href]': anchors }[selector] || []),
    getElementById: id => id === 'stage' ? detail : null,
  };
  const window = {
    history: {
      replaceState: (_state, _title, href) => { url = new URL(href); history[position] = url.href; },
      pushState: (_state, _title, href) => {
        url = new URL(href); history.splice(++position); history.push(url.href);
      },
    },
    addEventListener: (event, callback) => { listeners[event] = callback; },
  };
  vm.runInNewContext(source, {
    URL, URLSearchParams, location, document, window,
    localStorage: { getItem() { throw new Error('Language must come from URL, not storage'); } },
  });
  return {
    document, buttons, anchors, history, detail,
    href: () => url.href,
    click: lang => buttons.find(button => button.dataset.lang === lang).listeners.click(),
    back() { url = new URL(history[--position]); listeners.popstate(); },
    forward() { url = new URL(history[++position]); listeners.popstate(); },
  };
}

test('a bare URL defaults to English and records the language without adding history', () => {
  const p = page('https://example.com/robotics-ai/');
  assert.equal(p.document.documentElement.lang, 'en');
  assert.equal(p.href(), 'https://example.com/robotics-ai/?lang=en');
  assert.equal(p.history.length, 1);
  assert.equal(p.buttons[0].attrs['aria-pressed'], 'true');
});

test('Russian bookmarks override defaults and preserve query parameters and anchors', () => {
  const p = page('https://example.com/robotics-ai/curriculum.html?view=all&lang=ru#stage');
  assert.equal(p.document.documentElement.lang, 'ru');
  assert.equal(p.document.title, 'Русский заголовок');
  assert.equal(p.detail.open, true);
  p.click('en');
  assert.equal(p.href(), 'https://example.com/robotics-ai/curriculum.html?view=all&lang=en#stage');
  assert.equal(p.document.title, 'English title');
  assert.equal(p.history.length, 2);
  p.click('en');
  assert.equal(p.history.length, 2);
  p.back();
  assert.equal(p.document.documentElement.lang, 'ru');
  p.forward();
  assert.equal(p.document.documentElement.lang, 'en');
});

test('unsupported languages normalize to English', () => {
  const p = page('https://example.com/index.html?lang=de&foo=bar');
  assert.equal(p.href(), 'https://example.com/index.html?lang=en&foo=bar');
  assert.equal(p.document.documentElement.lang, 'en');
});

test('local navigation carries language without modifying external or download links', () => {
  const p = page('https://example.com/robotics-ai/months/2027-01.html?lang=ru', [
    '../curriculum.html?view=all#M01',
    '2027-02.html',
    'https://example.com/robotics-ai/projects.html#arm',
    '/robotics-ai/',
    '#stage',
    'https://vendor.example/product.html',
    '//vendor.example/catalog/',
    '../originals/roadmap.pdf',
    { href: '../curriculum.html', download: '' },
    'mailto:test@example.com',
  ]);
  assert.deepEqual(p.anchors.map(a => a.attrs.href), [
    'https://example.com/robotics-ai/curriculum.html?view=all&lang=ru#M01',
    'https://example.com/robotics-ai/months/2027-02.html?lang=ru',
    'https://example.com/robotics-ai/projects.html?lang=ru#arm',
    'https://example.com/robotics-ai/?lang=ru',
    '#stage',
    'https://vendor.example/product.html',
    '//vendor.example/catalog/',
    '../originals/roadmap.pdf',
    '../curriculum.html',
    'mailto:test@example.com',
  ]);
  p.click('en');
  assert.match(p.anchors[0].attrs.href, /lang=en#M01$/);
  p.back();
  assert.match(p.anchors[0].attrs.href, /lang=ru#M01$/);
});

test('offline file links and reloads retain the selected language', () => {
  const p = page('file:///tmp/robotics-ai/index.html', ['months/2027-01.html#stage']);
  p.click('ru');
  assert.equal(p.href(), 'file:///tmp/robotics-ai/index.html?lang=ru');
  assert.equal(p.anchors[0].attrs.href, 'file:///tmp/robotics-ai/months/2027-01.html?lang=ru#stage');
  const reloaded = page(p.href());
  assert.equal(reloaded.document.documentElement.lang, 'ru');
});
