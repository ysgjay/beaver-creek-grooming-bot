const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const source = readFileSync('public/appearance.js', 'utf8');

function browser({ stored = null, dark = false, blocked = false } = {}) {
  const dataset = {}, meta = {}, status = {}, events = [], listeners = {};
  const storage = new Map(stored ? [['chair0.appearance', stored]] : []);
  const device = { matches: dark, addEventListener: (_, fn) => { listeners.device = fn; } };
  const window = { addEventListener: (name, fn) => { listeners[name] = fn; } };
  const document = { documentElement: { dataset }, querySelector: s => s.includes('status-bar') ? status : meta, dispatchEvent: e => events.push(e) };
  runInNewContext(source, {
    document, window, matchMedia: () => device,
    localStorage: { getItem: k => { if (blocked) throw Error('Storage blocked'); return storage.get(k); }, setItem: (k,v) => { if (blocked) throw Error('Storage blocked'); storage.set(k,v); } },
    CustomEvent: class { constructor(type, options) { this.type=type; this.detail=options.detail; } },
  });
  return { api: window.Appearance, dataset, meta, status, storage, events, device,
    system(next) { device.matches=next; listeners.device(); },
    storageEvent(key,newValue) { listeners.storage({key,newValue}); } };
}
test('first paint follows a dark device when there is no saved choice', () => {
  const b=browser({dark:true});
  assert.equal(b.dataset.appearance,'dark'); assert.equal(b.meta.content,'#071b2e');
  assert.equal(b.api.preference(),'system'); assert.equal(b.status.content,'black-translucent');
});
test('a saved light override wins over a dark device, including later device changes', () => {
  const b=browser({stored:'light',dark:true});
  b.system(false); b.system(true);
  assert.equal(b.dataset.appearance,'light'); assert.equal(b.meta.content,'#dcebfa');
});
test('manual selection persists and returning to System resumes live device changes', () => {
  const b=browser(); b.api.set('dark');
  assert.equal(b.storage.get('chair0.appearance'),'dark'); assert.equal(b.dataset.appearance,'dark');
  b.api.set('system'); assert.equal(b.dataset.appearance,'light');
  b.system(true); assert.equal(b.dataset.appearance,'dark');
  assert.equal(b.events.at(-1).detail.changed,true);
});
test('blocked storage still supports appearance changes for the current visit', () => {
  const b=browser({dark:true,blocked:true}); b.api.set('light'); b.system(true);
  assert.equal(b.api.preference(),'light'); assert.equal(b.dataset.appearance,'light');
});
test('invalid old choices fall back to System and clearing storage resyncs open tabs', () => {
  const b=browser({stored:'nightcat'}); assert.equal(b.api.preference(),'system');
  b.storageEvent('chair0.appearance','dark'); assert.equal(b.dataset.appearance,'dark');
  b.storageEvent('unrelated','light'); assert.equal(b.dataset.appearance,'dark');
  b.storageEvent(null,null); assert.equal(b.dataset.appearance,'light');
});
test('a preference change with the same resolved appearance does not rebuild the radar', () => {
  const b=browser({dark:true}); b.api.set('dark');
  assert.equal(b.events.at(-1).detail.changed,false); assert.equal(b.api.preference(),'dark');
});
