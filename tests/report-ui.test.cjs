const { test } = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../public/report-ui.js');
const zone = 'America/Denver';
const today = '2026-11-15';

test('report timestamps use resort time, including a UTC date boundary', () => {
  assert.equal(ui.stamp('2026-11-16T02:01:00Z', zone, today, true), 'Sun 11/15, 7:01 PM MT');
  assert.equal(ui.dateKey('2026-11-16T02:01:00Z', zone), today);
  assert.equal(ui.stamp('2026-11-15T05:34:00', zone, today), '5:34 AM MT');
});
test('map dates accept source date formats and reject unknown or impossible dates', () => {
  assert.equal(ui.parts('November 13, 2026 — Park City')?.day, '2026-11-13');
  assert.equal(ui.parts('11/13/2026')?.day, '2026-11-13');
  assert.equal(ui.parts('2026-02-30'), null);
  assert.equal(ui.parts('No report yet'), null);
  assert.equal(ui.parts(null), null);
});
test('map age follows the printed map date, never the downloaded filename', () => {
  assert.equal(ui.groomingDate({ image:'maps/2026-11-15.jpg', runs:{map_date:'November 13, 2026'} }, today, zone, today).age, 2);
  assert.equal(ui.groomingDate({ image:'maps/2026-11-15.jpg' }, today, zone, today).age, null);
  assert.equal(ui.groomingDate({ runs:{map_date:'2026-10-31'} }, today, zone, '2026-11-02').age, 2);
});
test('list grooming labels its checked date instead of pretending to have a map date', () => {
  const d = ui.groomingDate({ list:true }, '2026-11-15T14:01:00Z', zone, today);
  assert.equal(d.day, today); assert.equal(d.age, 0); assert.equal(d.list, true);
});
test('hourly conditions choose the current resort hour, not the first saved hour', () => {
  const rows = [14,15,16].map(h => ({time:`2026-11-15T${h}:00`,temp:h}));
  const result = ui.forecastHours(rows, zone, '2026-11-15T22:40:00Z');
  assert.equal(result.selected.temp, 15); assert.equal(result.status, 'current');
  assert.deepEqual(result.later.map(x=>x.temp), [16]);
});
test('stale, missing and future-only hourly forecasts stay explicit', () => {
  const rows = [{time:'2026-11-15T14:00',temp:35}];
  assert.equal(ui.forecastHours(rows,zone,'2026-11-16T10:00:00Z').status,'past');
  assert.equal(ui.forecastHours(rows,zone,'2026-11-15T10:00:00Z').status,'future');
  assert.equal(ui.forecastHours([],zone).status,'missing');
  assert.deepEqual(ui.forecastHours(rows,zone,'2026-11-16T10:00:00Z').upcoming,[]);
});
test('zero resort snow takes precedence over SNOTEL and retains its own report time', () => {
  const snow = ui.snowSource({last_24h_in:0,stamps:{updated:'November 15, 2026'},updated_time:'5:34 AM'}, {snow_in:4,as_of:today}, zone,today);
  assert.equal(snow.value,0); assert.equal(snow.source,'Resort snow'); assert.equal(snow.stamp,'5:34 AM MT');
});
test('a stale snow report includes its date, with a truthful observed fallback', () => {
  assert.match(ui.snowSource({last_24h_in:1,stamps:{date:'November 13, 2026'},updated_time:'5:34 AM'},null,zone,today).stamp,/Fri 11\/13/);
  const fallback = ui.snowSource({}, {snow_in:0.5,as_of:'2026-11-14'},zone,today);
  assert.equal(fallback.source,'SNOTEL snow'); assert.equal(fallback.value,0.5); assert.match(fallback.stamp,/11\/14/);
  assert.equal(ui.snowSource({},null,zone,today).value,null);
  assert.equal(ui.snowSource({},null,zone,today).stamp,'Report time unavailable');
});
const forecast = Array.from({length:10},(_,i)=>({date:`2026-11-${15+i}`,snow:i===5?5:0.1}));
test('the outlook finds the actual peak day and sums complete five-day windows', () => {
  const o = ui.outlook(forecast,today);
  assert.equal(o.first,0.5); assert.equal(o.second,5.4); assert.equal(o.peak.date,'2026-11-20');
  assert.equal(o.startsToday,true);
});
test('partial, missing and old forecasts cannot turn missing snow into zero', () => {
  assert.equal(ui.outlook(forecast.slice(1),today).first,null);
  assert.equal(ui.outlook([{date:today,snow:null}],today).available,false);
  assert.equal(ui.outlook(forecast,'2026-12-01').available,false);
  assert.equal(ui.outlook(forecast,'2026-11-16').startsToday,false);
  assert.equal(ui.outlook([],today).first,null);
});
test('forecast windows work across a month boundary and zero snow is valid', () => {
  const rows = ['2026-11-29','2026-11-30','2026-12-01','2026-12-02','2026-12-03'].map(date=>({date,snow:0}));
  assert.equal(ui.outlook(rows,'2026-11-29').first,0);
  assert.equal(ui.outlook(rows,'2026-11-29').peak,null);
});
