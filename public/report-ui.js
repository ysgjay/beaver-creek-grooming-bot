/* Report presentation only. Keep source dates separate from the time the app is opened. */
((root) => {
  "use strict";
  const DEFAULT_ZONE = "America/Denver";
  const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const number = (v) => typeof v === "number" && Number.isFinite(v);
  const pad = (v) => String(v).padStart(2, "0");
  function validDay(y, m, d) {
    const date = new Date(Date.UTC(+y, +m - 1, +d));
    return date.getUTCFullYear() === +y && date.getUTCMonth() === +m - 1 && date.getUTCDate() === +d
      ? `${y}-${pad(m)}-${pad(d)}` : null;
  }
  function zoned(value, zone = DEFAULT_ZONE) {
    const date = value instanceof Date ? value : new Date(value);
    if (!Number.isFinite(date.getTime())) return null;
    let parts;
    try { parts = new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(date); }
    catch (_) { return zoned(date, DEFAULT_ZONE); }
    const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
    return { day: `${p.year}-${p.month}-${p.day}`, hour: +p.hour, minute: +p.minute };
  }
  function parts(value, zone = DEFAULT_ZONE) {
    if (value instanceof Date || typeof value === "number") return zoned(value, zone);
    if (typeof value !== "string" || !value.trim()) return null;
    const s = value.trim();
    if (/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/i.test(s)) return zoned(s, zone);
    const epoch = /\/Date\((\d{12,13})/.exec(s);
    if (epoch) return zoned(+epoch[1], zone);
    let m = /\b(20\d\d)-(\d{1,2})-(\d{1,2})(?=T|\b)/.exec(s), day = null;
    if (m) day = validDay(m[1], m[2], m[3]);
    else if ((m = /\b(\d{1,2})\/(\d{1,2})\/(20\d\d)\b/.exec(s))) day = validDay(m[3], m[1], m[2]);
    else if ((m = /\b([A-Za-z]+)\.? (\d{1,2}),? (20\d\d)\b/.exec(s))) {
      const month = MONTHS.indexOf(m[1].slice(0, 3).toLowerCase());
      if (month >= 0) day = validDay(m[3], month + 1, m[2]);
    }
    let hour = null, minute = null;
    const clock = /\b(\d{1,2}):(\d{2})\s*([AP]M)\b/i.exec(s);
    const isoClock = /[T ](\d{2}):(\d{2})(?::\d{2})?/.exec(s);
    if (clock && +clock[1] >= 1 && +clock[1] <= 12 && +clock[2] < 60) {
      hour = +clock[1] % 12 + (clock[3].toUpperCase() === "PM" ? 12 : 0); minute = +clock[2];
    } else if (isoClock && +isoClock[1] < 24 && +isoClock[2] < 60) { hour = +isoClock[1]; minute = +isoClock[2]; }
    return day || hour !== null ? { day, hour, minute } : null;
  }
  const dateKey = (now = Date.now(), zone) => zoned(now, zone)?.day || null;
  const hourKey = (p) => p?.day && p.hour !== null ? `${p.day}T${pad(p.hour)}` : null;
  // By region, not abbreviation: British Columbia keeps daylight time year-round from 11/2026,
  // which Intl reports as "MST", but it's still Pacific time there.
  const ZONES = { "America/Los_Angeles": "PT", "America/Vancouver": "PT", "America/Denver": "MT", "America/Boise": "MT",
    "America/Edmonton": "MT", "America/Phoenix": "MT", "America/Chicago": "CT", "America/New_York": "ET",
    "America/Toronto": "ET", "America/Detroit": "ET", "America/Montreal": "ET", "America/Halifax": "AT" };
  function zoneLabel(zone = DEFAULT_ZONE) {
    if (ZONES[zone]) return ZONES[zone];
    try { return new Intl.DateTimeFormat("en", { timeZone: zone, timeZoneName: "short" }).formatToParts(new Date()).find((p) => p.type === "timeZoneName").value.replace(/([PMCE])[SD]T/, "$1T"); }
    catch (_) { return "local time"; }
  }
  function dayLabel(day) {
    const p = parts(day);
    if (!p?.day) return null;  // weekday + MM/DD, e.g. "Sun 11/15"
    const wd = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short" }).format(new Date(p.day + "T12:00:00Z"));
    return `${wd} ${p.day.slice(5, 7)}/${p.day.slice(8, 10)}`;
  }
  function clockLabel(p) { return p?.hour !== null && p?.hour !== undefined ? `${p.hour % 12 || 12}${p.minute ? ":" + pad(p.minute) : ""} ${p.hour < 12 ? "AM" : "PM"}` : null; }
  function stamp(value, zone, today, withDate = false) {
    const p = parts(value, zone);
    if (!p) return null;
    const clock = clockLabel(p), date = p.day && (withDate || p.day !== today || !clock) ? dayLabel(p.day) : null;
    return [date, clock && `${clock} ${zoneLabel(zone)}`].filter(Boolean).join(", ") || null;
  }
  function forecastHours(hours, zone, now = Date.now()) {
    const key = hourKey(zoned(now, zone));
    const rows = (Array.isArray(hours) ? hours : []).map((hour) => ({ hour, key: hourKey(parts(hour?.time, zone)) })).filter((x) => x.key).sort((a, b) => a.key.localeCompare(b.key));
    const selected = rows.find((x) => x.key === key) || rows.filter((x) => x.key < key).at(-1) || rows[0];
    const status = !selected ? "missing" : selected.key === key ? "current" : selected.key < key ? "past" : "future";
    return { selected: selected?.hour || null, status, upcoming: rows.filter((x) => x.key >= key).map((x) => x.hour), later: rows.filter((x) => x.key > key).map((x) => x.hour), all: rows.map((x) => x.hour) };
  }
  function groomingDate(grooming, generated, zone, today) {
    const list = !!grooming?.list;
    const day = parts(list ? generated : grooming?.runs?.map_date, zone)?.day || null;
    const age = day && today ? Math.round((Date.parse(today + "T12:00:00Z") - Date.parse(day + "T12:00:00Z")) / 86400000) : null;
    return { day, age, label: dayLabel(day), list };
  }
  function snowSource(resort, observed, zone, today) {
    if (number(resort?.last_24h_in)) {
      const values = Object.values(resort.stamps || {});
      const raw = values.find((v) => parts(v, zone)?.day && parts(v, zone)?.hour !== null) || values.find((v) => parts(v, zone)?.day);
      const date = raw ? parts(raw, zone)?.day : null;
      let time = raw ? stamp(raw, zone, today) : null;
      if (raw && parts(raw, zone)?.hour === null && resort.updated_time) time = [date !== today && dayLabel(date), stamp(resort.updated_time, zone, today)].filter(Boolean).join(", ");
      return { value: resort.last_24h_in, source: "Resort snow", stamp: time || stamp(resort.updated_time, zone, today) || "Report time unavailable" };
    }
    return { value: number(observed?.snow_in) ? observed.snow_in : null, source: number(observed?.snow_in) ? "SNOTEL snow" : "Snow report", stamp: stamp(observed?.as_of, zone, today) || "Report time unavailable" };
  }
  function outlook(days, today) {
    const rows = (Array.isArray(days) ? days : []).filter((d) => parts(d?.date)?.day === d.date && number(d.snow) && d.snow >= 0).sort((a, b) => a.date.localeCompare(b.date));
    const at = (offset) => { const d = new Date(today + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + offset); return d.toISOString().slice(0, 10); };
    const total = (start) => {
      const selected = Array.from({ length: 5 }, (_, i) => rows.find((d) => d.date === at(start + i)));
      return selected.every(Boolean) ? Math.round(selected.reduce((sum, d) => sum + d.snow, 0) * 10) / 10 : null;
    };
    const future = rows.filter((d) => d.date >= today && d.date < at(10));
    const peak = future.filter((d) => d.snow > 0).reduce((best, d) => !best || d.snow > best.snow ? d : best, null);
    return { first: total(0), second: total(5), peak, available: future.length > 0, startsToday: rows[0]?.date === today };
  }
  const api = { number, parts, dateKey, zoneLabel, dayLabel, clockLabel, stamp, forecastHours, groomingDate, snowSource, outlook };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReportUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
