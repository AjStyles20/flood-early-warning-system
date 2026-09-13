// These tests execute rendering and event handlers with a small DOM stand-in.
// They do not claim a real-browser visual or screen-reader certification.
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  const classes = new Set();
  return {
    hidden: true, innerHTML: '', textContent: '', events: {}, attributes: {}, children: [],
    classList: { toggle(name) { classes.has(name) ? classes.delete(name) : classes.add(name); }, remove(name) { classes.delete(name); }, contains(name) { return classes.has(name); } },
    addEventListener(name, handler) { (this.events[name] ||= []).push(handler); },
    setAttribute(name, value) { this.attributes[name] = value; },
    appendChild(node) { this.children.push(node); }, after(node) { this.children.push(node); },
    focus() { this.focused = true; }, remove() {},
  };
}

function load(name, ids = [], context = {}, initial = {}) {
  const nodes = Object.fromEntries(ids.map(id => [id, element()]));
  for (const [id, fields] of Object.entries(initial)) Object.assign(nodes[id], fields);
  const events = {};
  const document = {
    body: element(),
    getElementById(id) { return nodes[id] || null; },
    createElement() { return element(); },
    querySelector(selector) { return nodes[selector] || null; },
    querySelectorAll() { return []; },
    addEventListener(name, handler) { (events[name] ||= []).push(handler); },
  };
  const sandbox = {
    document, console, URL, AbortController, setTimeout, clearTimeout, setInterval() {}, clearInterval() {},
    sessionStorage: { getItem() { return null; }, setItem() {} },
    window: { FLOODWATCH_CONTEXT: context, addEventListener() {}, scrollY: 0 },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'static/js', name), 'utf8'), sandbox);
  return { sandbox, nodes, events };
}

test('bell uses persistent timestamps and escapes submitted text', () => {
  const { sandbox } = load('site.js');
  const list = element();
  sandbox.renderNotificationList(list, [{ station_name: '<img onerror=alert(1)>', risk_level: 'High', message: '<script>bad</script>', updated_at: '2026-09-08T10:00:00Z', channels: { sms: 'simulated' } }]);
  assert.ok(list.innerHTML.includes('&lt;img'));
  assert.ok(!list.innerHTML.includes('<script>'));
  assert.ok(!list.innerHTML.includes('Time not recorded'));
  assert.ok(list.innerHTML.includes('Simulated SMS'));
});

test('shared user menu opens, updates ARIA, and closes with Escape', () => {
  const { sandbox, nodes, events } = load('site.js', ['user-menu-btn', 'user-dropdown-pane', 'menu-toggle-btn', '.command-sidebar', '.nav-links']);
  events.DOMContentLoaded[0]();
  nodes['user-menu-btn'].events.click[0]({ stopPropagation() {} });
  assert.equal(nodes['user-dropdown-pane'].hidden, false);
  assert.equal(nodes['user-menu-btn'].attributes['aria-expanded'], 'true');
  events.keydown.forEach(callback => callback({ key: 'Escape' }));
  assert.equal(nodes['user-dropdown-pane'].hidden, true);
  nodes['menu-toggle-btn'].events.click[0]();
  assert.equal(nodes['.command-sidebar'].classList.contains('sidebar-collapsed'), true);
});

test('news blocks non-web URLs and preserves configured-empty state', () => {
  const { sandbox, nodes } = load('news.js', ['news-feed-status', 'news-feed-list']);
  assert.equal(sandbox.newsSafeUrl('javascript:alert(1)'), '');
  assert.equal(sandbox.newsSafeUrl('file:///secret'), '');
  sandbox.renderNewsFeed({ configured: true, provider: 'rss', articles: [], message: 'Provider unavailable' });
  assert.ok(nodes['news-feed-list'].innerHTML.includes('No articles'));
  assert.ok(!nodes['news-feed-list'].innerHTML.includes('not connected'));
  sandbox.renderNewsFeed({ configured: true, provider: 'rss', articles: [{ url: 'javascript:alert(1)', title: 'bad' }, { url: 'https://example.org/update', title: '<b>Title</b>' }] });
  assert.ok(!nodes['news-feed-list'].innerHTML.includes('javascript:'));
  assert.ok(nodes['news-feed-list'].innerHTML.includes('&lt;b&gt;Title'));
});

test('evaluation distinguishes missing metrics from zero and uses percent units', () => {
  const { sandbox } = load('evaluation.js');
  assert.equal(sandbox.pct(undefined), 'Not recorded');
  assert.equal(sandbox.pct(0), '0.0%');
  assert.ok(sandbox.bar('Accuracy', 99.7, 100).includes('99.7%'));
  assert.ok(sandbox.bar('False positives', 0, 10).includes('width: 0%'));
  assert.ok(sandbox.bar('Recall', null, 100).includes('not recorded'));
});

test('guest has no workflow buttons; resolved operator alerts retain history', () => {
  const guest = load('dashboard.js').sandbox;
  assert.equal(guest.alertWorkflowButtons({ id: 1, status: 'new' }), '');
  const operator = load('dashboard.js', [], { canOperate: true }).sandbox;
  const resolved = operator.alertWorkflowButtons({ id: 1, status: 'resolved' });
  assert.ok(resolved.includes('View history'));
  assert.ok(!resolved.includes('data-alert-action="resolve"'));
});

test('alert audit loads into a focusable panel and escapes operator notes', async () => {
  const { sandbox, nodes } = load('dashboard.js', ['alert-queue'], { canOperate: true });
  sandbox.fetch = async () => ({ ok: true, json: async () => [{ action: 'acknowledge', from_status: 'new', to_status: 'acknowledged', notes: '<script>bad</script>', operator_email: 'operator@example.com' }] });
  await sandbox.changeAlertWorkflow(7, 'audit');
  const panel = nodes['alert-queue'].children[0];
  assert.ok(panel.focused);
  assert.ok(panel.innerHTML.includes('&lt;script&gt;'));
  assert.ok(!panel.innerHTML.includes('<script>'));
});

test('CSV upload gives an actionable permission error', async () => {
  const { sandbox, nodes } = load('data.js', ['telemetry-csv-file', 'csv-upload-status']);
  nodes['telemetry-csv-file'].files = ['evidence.csv'];
  sandbox.FormData = class {};
  sandbox.fetch = async () => ({ status: 403 });
  await sandbox.uploadTelemetryCsv({ preventDefault() {}, currentTarget: element() });
  assert.ok(nodes['csv-upload-status'].textContent.includes('Operator role required'));
});

function contactHarness(config = { publicKey: 'public-test', serviceId: 'service-test', contactTemplateId: 'template-test' }) {
  const harness = load('contact.js', ['emailjs-config', 'contact-form', 'contact-submit', 'contact-status', 'name', 'email', 'subject', 'message'], {}, {
    'emailjs-config': { textContent: JSON.stringify(config) },
    'name': { value: 'Ada' }, 'email': { value: 'ada@example.com' },
    'subject': { value: 'Station question' }, 'message': { value: 'Please explain this station.' },
  });
  const form = harness.nodes['contact-form'];
  form.reportValidity = () => true;
  form.resetCount = 0;
  form.reset = () => { form.resetCount++; };
  harness.sandbox.showNotice = () => {};
  harness.sandbox.document.body.dataset = {};
  harness.sandbox.window.location = { href: '' };
  harness.sandbox.Date = { now: () => 10000 };
  harness.submit = () => harness.sandbox.submitContact({ preventDefault() {}, currentTarget: form });
  return harness;
}

test('contact sends only after submit, with exactly the approved EmailJS payload', async () => {
  const h = contactHarness();
  const calls = [];
  h.sandbox.fetch = async (...args) => { calls.push(args); return { status: 200 }; };
  h.events.DOMContentLoaded[0]();
  assert.equal(calls.length, 0, 'Page load must not send contact data');
  await h.submit();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'https://api.emailjs.com/api/v1.0/email/send');
  assert.equal(calls[0][1].credentials, 'omit');
  assert.equal(calls[0][1].redirect, 'error');
  assert.deepEqual(JSON.parse(calls[0][1].body), {
    service_id: 'service-test', template_id: 'template-test', user_id: 'public-test',
    template_params: { from_name: 'Ada', from_email: 'ada@example.com', reply_to: 'ada@example.com', subject: 'Station question', message: 'Please explain this station.' },
  });
  assert.equal(h.nodes['contact-form'].resetCount, 1);
  assert.equal(h.nodes['contact-form'].attributes['aria-busy'], 'false');
  assert.equal(h.nodes['contact-submit'].disabled, false);
  assert.ok(h.nodes['contact-status'].textContent.includes('Inbox delivery has not been confirmed'));
});

test('provider rejection and rate limiting preserve entries and re-enable submission', async () => {
  for (const status of [400, 401, 429, 500]) {
    const h = contactHarness();
    let count = 0;
    h.sandbox.fetch = async () => { count++; return { status }; };
    await h.submit();
    assert.equal(count, 1);
    assert.equal(h.nodes['contact-form'].resetCount, 0);
    assert.equal(h.nodes.message.value, 'Please explain this station.');
    assert.ok(h.nodes['contact-status'].textContent.includes('entries have been kept'));
    assert.equal(h.nodes['contact-submit'].disabled, false);
  }
});

test('network failure is reported as uncertain acceptance without automatic retry', async () => {
  const h = contactHarness();
  let count = 0;
  h.sandbox.fetch = async () => { count++; throw new Error('offline'); };
  await h.submit();
  assert.equal(count, 1);
  assert.equal(h.nodes['contact-form'].resetCount, 0);
  assert.ok(h.nodes['contact-status'].textContent.includes('could not confirm'));
});

test('timeout aborts the request, retains the message and permits a later retry', async () => {
  const h = contactHarness();
  let timeout;
  let cleared = false;
  h.sandbox.setTimeout = (callback, delay) => { assert.equal(delay, 15000); timeout = callback; return 77; };
  h.sandbox.clearTimeout = id => { assert.equal(id, 77); cleared = true; };
  h.sandbox.fetch = (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('aborted')));
  });
  const pending = h.submit();
  timeout();
  await pending;
  assert.equal(cleared, true);
  assert.equal(h.nodes['contact-form'].resetCount, 0);
  assert.equal(h.nodes['contact-submit'].disabled, false);
  assert.ok(h.nodes['contact-status'].textContent.includes('check before resending'));
});

test('repeat submissions while pending and within one second do not send duplicates', async () => {
  const h = contactHarness();
  let resolveRequest;
  let count = 0;
  h.sandbox.fetch = () => { count++; return new Promise(resolve => { resolveRequest = resolve; }); };
  const pending = h.submit();
  assert.equal(h.nodes['contact-submit'].disabled, true);
  await h.submit();
  assert.equal(count, 1);
  resolveRequest({ status: 200 });
  await pending;
  await h.submit();
  assert.equal(count, 1);
  assert.ok(h.nodes['contact-status'].textContent.includes('wait a moment'));
});

test('successful response never erases edits made while the old message was pending', async () => {
  const h = contactHarness();
  h.sandbox.fetch = async () => { h.nodes.message.value = 'A newer draft'; return { status: 200 }; };
  await h.submit();
  assert.equal(h.nodes['contact-form'].resetCount, 0);
  assert.equal(h.nodes.message.value, 'A newer draft');
});

test('missing or partial EmailJS configuration uses an email draft without sending or clearing', async () => {
  for (const config of [{}, { publicKey: 'only-one-id' }]) {
    const h = contactHarness(config);
    let calls = 0;
    h.sandbox.fetch = async () => { calls++; throw new Error('Must not send'); };
    h.sandbox.document.body.dataset.contactEmail = 'team@example.com';
    await h.submit();
    assert.equal(calls, 0);
    assert.ok(h.sandbox.window.location.href.startsWith('mailto:team@example.com?subject='));
    assert.equal(h.nodes['contact-form'].resetCount, 0);
    assert.ok(h.nodes['contact-status'].textContent.includes('Review and send'));
  }
});

test('unconfigured contact and blank or invalid input do not transmit data', async () => {
  const h = contactHarness({});
  let calls = 0;
  h.sandbox.fetch = async () => { calls++; throw new Error('Must not send'); };
  await h.submit();
  assert.ok(h.nodes['contact-status'].textContent.includes('not connected'));
  h.nodes.message.value = '   ';
  await h.submit();
  assert.ok(h.nodes['contact-status'].textContent.includes('complete every field'));
  h.nodes['contact-form'].reportValidity = () => false;
  await h.submit();
  assert.equal(calls, 0);
});

test('newsletter requests remain mail drafts and do not claim a saved subscription', async () => {
  const h = contactHarness();
  const newsletter = element();
  newsletter.querySelector = () => ({ value: 'subscriber@example.com' });
  h.sandbox.document.querySelectorAll = () => [newsletter];
  h.sandbox.document.body.dataset.contactEmail = 'team@example.com';
  let message;
  h.sandbox.showNotice = (title, body) => { message = body; };
  let calls = 0;
  h.sandbox.fetch = async () => { calls++; };
  h.events.DOMContentLoaded[0]();
  await newsletter.events.submit[0]({ preventDefault() {} });
  assert.equal(calls, 0);
  assert.ok(h.sandbox.window.location.href.startsWith('mailto:'));
  assert.ok(message.includes('No subscription has been saved'));
});
