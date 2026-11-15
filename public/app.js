(() => {
  "use strict";

  /* ---------------- helpers ---------------- */
  const $ = (sel, el = document) => el.querySelector(sel);
  const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pd = (s) => { const [y, m, d] = s.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const addDays = (s, n) => { const d = pd(s); d.setDate(d.getDate() + n); return iso(d); };
  const fmtDay = (s) => { const d = pd(s); return `${WD[d.getDay()]} ${d.getMonth() + 1}/${d.getDate()}`; };
  const inch = (x) => (x == null ? "–" : (x >= 1 || x === 0 ? Math.round(x) : x.toFixed(1)) + '"');
  // The PDF says "November 15, 2026"; show it as 11/15 like every other date.
  const mapDate = (t) => { const m = /^([A-Za-z]+) (\d{1,2}), \d{4}$/.exec(t || ""); const i = m ? MONTH_FULL.indexOf(m[1]) : -1; return i < 0 ? t : `Map ${i + 1}/${m[2]}`; };
  const hourLabel = (t) => { const h = Number(t.slice(11, 13)); return `${h % 12 || 12}${h < 12 ? "a" : "p"}`; };
  // "Today" is the resort's calendar day, not the viewer's: someone checking from another
  // time zone sees the same day the mountain is on. Report times are already resort-local text.
  const RESORT_TZ = "America/Denver";
  const todayIso = () => {
    try { return new Intl.DateTimeFormat("en-CA", { timeZone: resortInfo().timezone || S.cfg?.timezone || RESORT_TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()); }
    catch (e) { return iso(new Date()); }
  };

  /* ---------------- resorts ----------------
     Beaver Creek's archive lives at /data/..., every other resort's one folder down
     (/data/vail/...). The picked resort is remembered on this device; ?resort= in a link
     (emails and notifications use it) picks one too. */
  const DEFAULT_RESORT = "beaver-creek";
  const R = { list: [{ slug: DEFAULT_RESORT, name: "Beaver Creek", timezone: RESORT_TZ }], slug: DEFAULT_RESORT };
  const resortInfo = () => R.list.find((r) => r.slug === R.slug) || R.list[0];
  const dataPath = (p) => (R.slug === DEFAULT_RESORT ? p : p.replace(/^\/data\//, `/data/${R.slug}/`));
  function pickResort(slug, remember = true) {
    R.slug = R.list.some((r) => r.slug === slug) ? slug : DEFAULT_RESORT;
    if (remember) { try { localStorage.setItem("resort", R.slug); } catch (e) {} }
    document.title = `Snow Desk · ${resortInfo().name}`;
    const sel = $("#resort-select");
    if (sel) sel.value = R.slug;
  }

  async function getJSON(path, { fresh = false } = {}) {
    path = dataPath(path);
    try {
      const r = await fetch(path, { cache: fresh ? "no-cache" : "default" });
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }

  /* ---------------- themes ---------------- */
  // One look: Bluebird, switching to Night Cat when the phone is in dark mode.
  const THEMES = {
    bluebird: { font: "Outfit:wght@700" },
    nightcat: { font: "Saira+Condensed:wght@700" },
  };
  const loadedFonts = new Set(["Outfit:wght@700"]);
  const darkQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function currentTheme() { return darkQuery && darkQuery.matches ? "nightcat" : "bluebird"; }
  function applyTheme(id) {
    const t = THEMES[id] || THEMES.bluebird;
    document.documentElement.dataset.theme = THEMES[id] ? id : "bluebird";
    if (t.font && !loadedFonts.has(t.font)) {
      loadedFonts.add(t.font);
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = `https://fonts.googleapis.com/css2?family=${t.font}&display=swap`;
      document.head.appendChild(l);
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#dcebfa";
  }
  try { localStorage.removeItem("theme"); } catch (e) {}   // the old colour picker's choice
  if (darkQuery) {
    const onScheme = () => applyTheme(currentTheme());
    darkQuery.addEventListener ? darkQuery.addEventListener("change", onScheme) : darkQuery.addListener(onScheme);
  }
  const MATERIALS = [
    { id: "flat", name: "Flat", mood: "Solid cards, the fastest" },
    { id: "glass", name: "Glass", mood: "Clear panes over an alpenglow ridge" },
    { id: "frost", name: "Frost", mood: "Frosted, grainy, like a cold window" },
    { id: "ice", name: "Ice", mood: "Crisp edges with a blue sheen" },
    { id: "powder", name: "Powder", mood: "Falling flakes, snow-capped cards" },
  ];
  function currentMaterial() { try { return localStorage.getItem("material") || "frost"; } catch (e) { return "frost"; } }
  function applyMaterial(id) {
    if (id === "flat") delete document.documentElement.dataset.material;
    else document.documentElement.dataset.material = id;
    try { localStorage.setItem("material", id); } catch (e) {}
  }

  /* ---------------- state ---------------- */
  const S = { latest: null, verification: null, cfg: null, months: {}, offline: false, cal: { mode: "month", month: null, sel: null } };

  async function month(ym) {
    if (!(ym in S.months)) S.months[ym] = (await getJSON(`/data/months/${ym}.json`)) || { month: ym, days: {} };
    return S.months[ym];
  }
  const dayRow = (d) => (S.months[d.slice(0, 7)] || { days: {} }).days[d] || null;

  // Snow you'd find that morning: the resort's 24h report, else SNOTEL's gain the day before.
  function morningSnow(d) {
    const r = dayRow(d);
    if (r && r.resort_24h != null) return r.resort_24h;
    const prev = dayRow(addDays(d, -1));
    if (prev && prev.snotel_new_in != null) return prev.snotel_new_in;
    if (r && r.snotel_24h != null) return r.snotel_24h;
    return null;
  }
  const groomedRuns = (r) => r ? [...(r.featured || []), ...(r.overnight || []), ...(r.morning || []), ...(r.groomed || [])] : [];

  /* ---------------- shared pieces ---------------- */
  function runsBlock(runs) {
    if (!runs) return "";
    const groups = [["Groomers of the day", runs.groomers_of_the_day || runs.featured, "featured"],
      ["Groomed overnight", runs.overnight, ""], ["Morning grooming", runs.morning, ""],
      ...(runs.areas ? Object.entries(runs.areas).map(([a, l]) => [a, l, ""]) : [["Groomed", runs.groomed, ""]])].filter(([, l]) => l && l.length);
    if (!groups.length) return `<p class="muted small">No run names listed on this map.</p>`;
    return `<div class="runs">${groups.map(([t, l, cls]) =>
      `<div><h3>${t}</h3><ul class="chips ${cls}">${l.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>`).join("")}</div>`;
  }

  /* ---------------- chart kit ----------------
     Every chart is a draw(width) -> [height, svgBody] function, mounted responsively.
     Elements with data-tip show a tooltip on hover, focus or tap. */
  function bindTips(el) {
    const tip = $("#tip");
    el.querySelectorAll("[data-tip]").forEach((t) => {
      const show = () => {
        tip.textContent = t.dataset.tip; tip.hidden = false;
        const r = t.getBoundingClientRect();
        tip.style.left = Math.max(8, Math.min(innerWidth - tip.offsetWidth - 8, r.left + r.width / 2 - tip.offsetWidth / 2)) + "px";
        tip.style.top = Math.max(8, r.top - tip.offsetHeight - 6) + "px";
      };
      const hide = () => { tip.hidden = true; };
      t.addEventListener("mouseenter", show); t.addEventListener("focus", show); t.addEventListener("click", show);
      t.addEventListener("mouseleave", hide); t.addEventListener("blur", hide);
    });
  }
  function mountChart(draw, label) {
    const el = document.createElement("div");
    el.className = "chart";
    let lastW = 0;
    const render = () => {
      const W = Math.max(260, Math.round(el.clientWidth || 360));
      if (W === lastW) return;
      lastW = W;
      const [H, body] = draw(W);
      el.innerHTML = `<svg viewBox="-2 -2 ${W + 4} ${H + 4}" role="img" aria-label="${esc(label)}">${body}</svg>`;
      bindTips(el);
    };
    requestAnimationFrame(render);
    new ResizeObserver(render).observe(el);
    return el;
  }
  const niceMax = (v) => [2, 4, 6, 8, 12, 16, 24, 36, 48].find((n) => n >= v) || 60;
  // Day labels read month/day ("11/15"); weekends are bold. Narrow slots (phones) get a smaller size so ten fit.
  const dayTick = (d) => { const dt = pd(d); return { wk: dt.getDay() === 0 || dt.getDay() === 6, label: `${dt.getMonth() + 1}/${dt.getDate()}` }; };
  const tickSize = (slot) => (slot < 30 ? ' style="font-size:9px;letter-spacing:-.03em"' : slot < 36 ? ' style="font-size:10px"' : "");
  const val = (x) => (x >= 1 ? Math.round(x) : x >= 0.1 ? x.toFixed(1) : "0");
  const dayLabels = (dates, x, y) => { const size = tickSize(dates.length > 1 ? x(1) - x(0) : 99); return dates.map((d, i) => { const t = dayTick(d); return `<text class="${t.wk ? "wk" : ""}" x="${x(i)}" y="${y}" text-anchor="middle"${size}>${t.label}</text>`; }).join(""); };

  // Today: ten days in one row. Cell color deepens with snow; number inside.
  function heatStrip(days) {
    return mountChart((W) => {
      const gap = 3, cw = (W - gap * (days.length - 1)) / days.length; let s = "";
      days.forEach((d, i) => {
        const x = i * (cw + gap), t = Math.min(1, d.snow / 10), k = dayTick(d.date);
        const fill = d.snow < 0.1 ? "var(--surface-2)" : `color-mix(in oklab, var(--accent) ${Math.round(16 + t * 84)}%, var(--surface))`;
        const ink = t > 0.5 ? "var(--on-accent)" : "var(--ink)";
        s += `<rect x="${x}" y="0" width="${cw}" height="38" rx="7" fill="${fill}" tabindex="0" data-tip="${fmtDay(d.date)}: ${inch(d.snow)} expected, likely ${inch(d.low)}–${inch(d.high)}"/>`;
        s += `<text class="val" x="${x + cw / 2}" y="24" text-anchor="middle" style="fill:${ink};pointer-events:none">${d.snow < 0.1 ? "–" : val(d.snow)}</text>`;
        s += `<text class="${k.wk ? "wk" : ""}" x="${x + cw / 2}" y="53" text-anchor="middle"${tickSize(cw + gap)}>${k.label}</text>`;
      });
      return [58, s];
    }, "10-day snowfall, one cell per day");
  }

  // Forecast: each day is a snow stake. Solid = expected; hatched = how much more it could
  // reach (the upper estimate), capped by a dashed line with its number above; notch = low end.
  // Labels never sit on the bars: the upper number rides above its cap, and the expected
  // number gets its own row under the baseline, so short and tall days read the same way.
  function stakeChart(days, plotH, pick) {
    return mountChart((W) => {
      const L = W < 340 ? 20 : 24, T = 20, ph = plotH || 168, base = T + ph, valY = base + 16, dateY = base + 32, H = dateY + 4;
      const slot = (W - L) / days.length, sw = Math.max(12, Math.min(30, slot * 0.5)), small = slot < 40;
      const max = niceMax(Math.max(4, ...days.map((d) => d.high ?? d.snow))), y = (v) => T + ph - (v / max) * ph, step = max / 4;
      let s = `<defs><pattern id="over" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="var(--accent-soft)"/><line x1="0" y1="0" x2="0" y2="5" stroke="var(--accent)" stroke-width="1.4" opacity=".45"/></pattern></defs>`;
      for (let v = 0; v <= max; v += step) s += `<line class="grid" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" opacity="${v ? 0.6 : 1}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" style="font-size:11px">${v}"</text>`;
      days.forEach((d, i) => {
        const cx = L + slot * i + slot / 2, x0 = cx - sw / 2, hi = d.high ?? d.snow, lo = d.low ?? d.snow;
        // The stake: an empty tube with ruler ticks every inch, longer at each gridline.
        s += `<rect x="${x0}" y="${T}" width="${sw}" height="${ph}" rx="3" fill="var(--surface-2)" stroke="var(--line)" stroke-width="1"/>`;
        for (let v = 1; v < max; v++) { const major = v % step === 0; if (max > 24 && !major && v % 2) continue;
          s += `<line x1="${x0}" x2="${x0 + (major ? sw * 0.5 : sw * 0.28)}" y1="${y(v)}" y2="${y(v)}" stroke="var(--ink-2)" stroke-width="${major ? 1 : 0.7}" opacity="${major ? 0.45 : 0.3}"/>`; }
        // Drift amplitude: shrinks for shallow days so it never pokes above the value.
        const depth = y(0) - y(d.snow), a = depth >= 1.5 ? Math.min(2.5, depth / 3) : 0;
        if (hi - d.snow >= 0.2) {
          // Hatching runs down under the drift's troughs so the snow's wavy edge meets it with no gap.
          s += `<rect x="${x0 + 0.5}" y="${y(hi)}" width="${sw - 1}" height="${Math.min(y(0), y(d.snow) + 2 * a + 0.5) - y(hi)}" fill="url(#over)"/>`;
          s += `<line x1="${x0}" x2="${x0 + sw}" y1="${y(hi)}" y2="${y(hi)}" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="3 2"/>`;
          s += `<text class="up" x="${cx}" y="${y(hi) - 5}" text-anchor="middle">${val(hi)}</text>`;
        }
        // Snow in the tube, with a gentle drift on top.
        if (a) { const top = y(d.snow) + a;
          s += `<path d="M${x0 + 0.5},${y(0)}V${top}q${sw / 4},${-a * 1.6} ${sw / 2 - 0.5},0q${sw / 4},${a * 1.6} ${sw / 2},0V${y(0)}Z" fill="var(--snow-fill)" stroke="var(--accent)" stroke-width="1.2" stroke-linejoin="round"/>`; }
        // Low end: a small notch on the stake's right edge, kept inside the plot.
        if (lo < d.snow - 0.2) { const ly = Math.min(y(0) - 3, y(lo)); s += `<path d="M${x0 + sw + 1},${ly}l4.5,-3v6Z" fill="var(--ink)" opacity=".8"/>`; }
        s += d.snow >= 0.1 ? `<text class="val" x="${cx}" y="${valY}" text-anchor="middle">${val(d.snow)}</text>`
                           : `<text x="${cx}" y="${valY}" text-anchor="middle" opacity=".55">–</text>`;
        s += `<rect x="${cx - slot / 2}" y="0" width="${slot}" height="${H}" rx="8" fill="transparent" tabindex="0" ${pick ? `class="day-hit" role="button" data-day="${i}" aria-label="${fmtDay(d.date)}, show each model's call" ` : ""}data-tip="${fmtDay(d.date)}: ${inch(d.snow)} expected. Low end ${inch(lo)}, could reach ${inch(hi)}"/>`;
      });
      return [H, `<g class="stakes${small ? " small" : ""}">` + s + dayLabels(days.map((d) => d.date), (i) => L + slot * i + slot / 2, dateY) + "</g>"];
    }, "Snow stakes: expected snow per day with its upper estimate");
  }

  // Forecast detail: each dot is one model's call; the bar is the blend.
  function votesChart(days, labels) {
    return mountChart((W) => {
      const H = 190, L = 24, T = 10, B = 22, ph = H - T - B, slot = (W - L) / days.length;
      const all = days.flatMap((d) => Object.values(d.models || {})).concat(days.map((d) => d.snow));
      const max = niceMax(Math.max(2, ...all)), y = (v) => T + ph - (v / max) * ph; let s = "";
      for (let v = 0; v <= max; v += max / 4) s += `<line class="grid" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 5}" y="${y(v) + 4}" text-anchor="end">${v}"</text>`;
      days.forEach((d, i) => {
        const cx = L + slot * i + slot / 2, entries = Object.entries(d.models || {}).sort((a, b) => a[1] - b[1]);
        s += `<line x1="${cx - slot * 0.34}" x2="${cx + slot * 0.34}" y1="${y(d.snow)}" y2="${y(d.snow)}" stroke="var(--accent)" stroke-width="3.5" stroke-linecap="round"/>`;
        const spread = Math.min(3.4, slot / (entries.length + 3));
        entries.forEach(([m, v], j) => { s += `<circle cx="${cx + (j - (entries.length - 1) / 2) * spread}" cy="${y(v)}" r="3.4" fill="var(--ink)" fill-opacity=".72" stroke="var(--surface)" stroke-width="1.2"/>`; });
        s += `<rect x="${cx - slot / 2}" y="0" width="${slot}" height="${H}" fill="transparent" tabindex="0" data-tip="${fmtDay(d.date)}. Blend ${inch(d.snow)}. ${entries.slice().reverse().map(([m, v]) => `${(labels[m] || m).split(" (")[0]} ${inch(v)}`).join(", ")}"/>`;
      });
      return [H, s + dayLabels(days.map((d) => d.date), (i) => L + slot * i + slot / 2, H - 4)];
    }, "Model votes: each model's snowfall call per day");
  }

  // Calendar month: running total of new snow, extended by the forecast for the current month.
  function accumChart(points, ahead) {
    return mountChart((W) => {
      const H = 150, L = 28, R = 10, T = 18, B = 22, ph = H - T - B, n = points.length + ahead.length;
      const last = points.length ? points[points.length - 1].total : 0;
      const max = niceMax(Math.max(2, last, ...ahead.map((a) => a.hi)));
      const x = (i) => L + (W - L - R) * (n > 1 ? i / (n - 1) : 0), y = (v) => T + ph - (v / max) * ph; let s = "";
      for (let v = 0; v <= max; v += max / 4) s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 5}" y="${y(v) + 4}" text-anchor="end">${v}"</text>`;
      if (points.length) {
        s += `<path d="M${x(0)},${y(0)}L${points.map((p, i) => `${x(i)},${y(p.total)}`).join("L")}L${x(points.length - 1)},${y(0)}Z" fill="var(--accent)" opacity=".12"/>`;
        s += `<path d="M${points.map((p, i) => `${x(i)},${y(p.total)}`).join("L")}" fill="none" stroke="var(--accent)" stroke-width="2.2" stroke-linejoin="round"/>`;
      }
      if (ahead.length) {
        const o = points.length - 1, base = { total: last, lo: last, hi: last };
        const seq = [base, ...ahead];
        s += `<path d="M${seq.map((a, i) => `${x(o + i)},${y(a.hi)}`).join("L")}L${seq.map((a, i) => `${x(o + i)},${y(a.lo)}`).reverse().join("L")}Z" fill="var(--accent)" opacity=".10"/>`;
        s += `<path d="M${seq.map((a, i) => `${x(o + i)},${y(a.total)}`).join("L")}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 3"/>`;
        const e = ahead[ahead.length - 1];
        s += `<text class="val" x="${x(n - 1)}" y="${y(e.total) - 8}" text-anchor="end">${inch(e.total)} by ${pd(e.date).getMonth() + 1}/${pd(e.date).getDate()}</text>`;
      }
      if (points.length) {
        const p = points[points.length - 1];
        s += `<circle cx="${x(points.length - 1)}" cy="${y(p.total)}" r="4.5" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>`;
        if (!ahead.length) s += `<text class="val" x="${x(points.length - 1) - 8}" y="${y(p.total) - 9}" text-anchor="end">${inch(p.total)}</text>`;
      }
      [...points, ...ahead].forEach((p, i) => { s += `<rect x="${x(i) - 6}" y="0" width="12" height="${H}" fill="transparent" tabindex="0" data-tip="${fmtDay(p.date)}: ${inch(p.total)} so far${p.hi != null ? ` (forecast, likely ${inch(p.lo)}–${inch(p.hi)})` : p.add ? `, +${inch(p.add)} that day` : ""}"/>`; });
      const all = [...points, ...ahead], every = Math.ceil(all.length / 7);
      all.forEach((p, i) => { if (i % every === 0 || i === all.length - 1) s += `<text x="${x(i)}" y="${H - 5}" text-anchor="middle">${pd(p.date).getDate()}</text>`; });
      return [H, s];
    }, "Month-to-date snowfall total");
  }

  // Day view: snow per hour (bars) under the temperature line, labeled every 3 hours.
  function hourlyChart(hours) {
    return mountChart((W) => {
      const H = 150, L = 4, T = 24, B = 22, ph = H - T - B, slot = (W - L) / hours.length, bw = Math.min(16, slot * 0.55);
      const smax = Math.max(0.5, ...hours.map((h) => h.snow || 0)), temps = hours.map((h) => h.temp);
      const tmin = Math.min(...temps), tmax = Math.max(...temps);
      const ys = (v) => T + ph - (v / smax) * ph * 0.55, yt = (v) => T + 2 + ((tmax - v) / Math.max(1, tmax - tmin)) * ph * 0.36;
      const cx = (i) => L + slot * i + slot / 2; let s = `<line class="grid" x1="${L}" x2="${W}" y1="${ys(0)}" y2="${ys(0)}"/>`;
      hours.forEach((h, i) => {
        const hh = ys(0) - ys(h.snow || 0);
        if (hh > 0.5) s += `<rect x="${cx(i) - bw / 2}" y="${ys(h.snow)}" width="${bw}" height="${hh}" rx="3" fill="var(--snow-fill)" stroke="var(--accent)" stroke-width="1"/>`;
        if (h.snow >= 0.1) s += `<text class="val" x="${cx(i)}" y="${ys(h.snow) - 3}" text-anchor="middle">${h.snow}</text>`;
        s += `<text x="${cx(i)}" y="${H - 5}" text-anchor="middle">${hourLabel(h.time)}</text>`;
        s += `<rect x="${cx(i) - slot / 2}" y="0" width="${slot}" height="${H}" fill="transparent" tabindex="0" data-tip="${hourLabel(h.time)}: ${h.temp}°F, feels ${h.feels}°, ${h.dir} ${h.wind} mph, ${h.snow ? h.snow + '" snow' : "no snow"}"/>`;
      });
      s += `<path d="M${hours.map((h, i) => `${cx(i)},${yt(h.temp)}`).join("L")}" fill="none" stroke="var(--accent)" stroke-width="2.2" stroke-linejoin="round"/>`;
      hours.forEach((h, i) => { if (i % 3 === 0 || i === hours.length - 1) s += `<circle cx="${cx(i)}" cy="${yt(h.temp)}" r="3.8" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/><text class="val" x="${cx(i)}" y="${yt(h.temp) - 8}" text-anchor="middle">${h.temp}°</text>`; });
      return [H, s];
    }, "Hourly temperature and snowfall");
  }

  function openLightbox(src, alt) {
    const ov = $("#overlay");
    ov.innerHTML = `<div class="lightbox" role="dialog" aria-label="${esc(alt)}"><button class="close" type="button">Close</button><div class="scrollbox"><img src="${esc(src)}" alt="${esc(alt)}"></div></div>`;
    const close = () => { ov.innerHTML = ""; document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    $(".close", ov).addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    $(".close", ov).focus();
  }

  function openSheet(title, html, onMount) {
    const ov = $("#overlay");
    ov.innerHTML = `<div class="sheet-backdrop"><div class="sheet" role="dialog" aria-label="${esc(title)}"><div class="sheet-head"><h2>${esc(title)}</h2><button class="btn secondary" type="button" data-close>Done</button></div>${html}</div></div>`;
    const close = () => { ov.innerHTML = ""; document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    ov.querySelector("[data-close]").addEventListener("click", close);
    ov.querySelector(".sheet-backdrop").addEventListener("click", (e) => { if (e.target.classList.contains("sheet-backdrop")) close(); });
    document.addEventListener("keydown", onKey);
    onMount && onMount(ov, close);
  }

  // Temperatures at the resort's elevation bands (base, mid, peak), when the report carries them.
  const bandsOf = (L) => (L?.bands || []).filter((b) => b && b.label && (b.now || b.hours?.length));
  const bandFt = (b) => (b.elevation_ft ? `${Number(b.elevation_ft).toLocaleString("en-US")} ft` : "");
  const bandTemp = (b, time) => { const h = (b.hours || []).find((x) => (x.time || "").slice(0, 13) === (time || "").slice(0, 13)); return h && h.temp != null ? `${h.temp}°` : "–"; };
  const WIDE = "(min-width: 1200px)";

  /* ---------------- TODAY ---------------- */
  function viewToday() {
    const L = S.latest;
    const v = document.createElement("div");
    v.className = "view v-today";
    if (!L) { v.innerHTML = `<p class="offline">The morning report isn't available yet. Check your connection and try again.</p>`; return v; }
    const g = L.grooming || {}, fc = L.forecast || {}, obs = L.observed || {}, rs = L.resort || {};
    const r24 = rs.last_24h_in ?? obs.snow_in;
    const isToday = L.date === todayIso();
    const now = (L.hourly?.hours || [])[0];
    const bands = bandsOf(L);
    if (g.none) v.classList.add("no-groom");
    if (S.offline) v.classList.add("is-offline");

    const sentAt = L.delivery?.sent_at ? L.delivery.sent_at.slice(11, 16) : null;
    v.innerHTML = `
      ${S.offline ? `<p class="offline">You're offline. Showing the report saved on ${fmtDay(L.date)}.</p>` : ""}
      <div class="status-line">
        ${g.none ? "" : `<span class="pill ${g.new_map ? "" : "quiet"}">${g.new_map ? "New grooming report" : "No new grooming report yet"}</span>`}
        <span>${sentAt ? `Sent ${sentAt}` : `Updated ${isToday ? "" : fmtDay(L.date) + " "}${(L.generated || "").slice(11, 16)}`}</span>
        ${rs.updated_time ? `<span>· Snow report ${esc(rs.updated_time)}</span>` : ""}
      </div>

      <section class="card a-cond" aria-label="Conditions">
        <div class="cond">
          <div><span class="label">New 24h</span><span class="big">${inch(r24)}</span></div>
          <div><span class="label">Base<span class="wide-only"> depth</span></span><span class="mid">${inch(rs.base_in)}</span><span class="sub">Season ${inch(rs.season_in)}</span></div>
          <div><span class="label">Now</span><span class="mid">${now ? now.temp + "°" : "–"}</span><span class="sub">${now ? `Feels ${now.feels}°` : ""}</span></div>
          <div><span class="label">Wind</span><span class="mid">${now ? now.wind : "–"}</span><span class="sub">${now ? `${esc(now.dir)} g${now.gust ?? "–"}` : ""}</span></div>
        </div>
        ${bands.length ? `<div class="status-line bands"><span>Temp now</span>${bands.map((b) => { const t = b.now?.temp ?? b.hours?.[0]?.temp; return t == null ? "" : `<span title="${bandFt(b)}">· ${esc(b.label)} <strong class="num">${t}°</strong></span>`; }).join("")}</div>` : ""}
        ${now ? `<div class="hours">${L.hourly.hours.slice(1).map((h) => `<div class="hour"><span class="t">${hourLabel(h.time)}</span><span class="temp">${h.temp}°</span><span class="small">${esc(h.dir)} ${h.wind}</span>${h.snow ? `<span class="num small">${h.snow}"</span>` : ""}</div>`).join("")}</div>` : ""}
      </section>

      ${g.none ? "" : `<section class="card a-groom" aria-labelledby="h-groom">
        <div class="card-head"><h2 id="h-groom">Grooming</h2><span class="muted small">${g.runs?.map_date ? esc(mapDate(g.runs.map_date)) : ""}</span></div>
        <div class="groom">
          ${g.image ? `<button class="map-btn" type="button" id="map-open" aria-label="Open the grooming map full size"><img src="/${esc(g.image)}" alt="${esc(resortInfo().name)} grooming map" decoding="async"></button>` : `<p class="muted">No grooming map yet.</p>`}
          ${runsBlock(g.runs)}
        </div>
      </section>`}

      <section class="card a-fc" aria-labelledby="h-fc">
        <div class="card-head"><h2 id="h-fc">Snow forecast</h2><a class="link" href="#forecast">Full forecast</a></div>
        <div class="status-line"><span>Next 5 days <strong class="num">${inch(fc.next_1_5)}</strong>${fc.next_1_5_range ? ` (likely ${inch(fc.next_1_5_range[0])}–${inch(fc.next_1_5_range[1])})` : ""}</span><span>· Days 6–10 <strong class="num">${inch(fc.next_6_10)}</strong></span></div>
        <div id="fc-mini"></div>
      </section>

      <section class="card a-cam" aria-labelledby="h-cam">
        <div class="card-head"><h2 id="h-cam">Snow stake</h2><span class="muted small">Tap to switch cams</span></div>
        <div id="cams"></div>
      </section>
      <a class="btn secondary block a-cta" href="#help" data-goto="alerts">Get this report at 7:00 by email or notification</a>`;

    if (fc.days?.length) $("#fc-mini", v).appendChild(heatStrip(fc.days));
    const mb = $("#map-open", v);
    if (mb) mb.addEventListener("click", () => openLightbox("/" + g.image, "Grooming map"));
    renderCams($("#cams", v), L);
    return v;
  }

  function renderCams(el, L) {
    const cams = (resortInfo().cams || (R.slug === DEFAULT_RESORT ? S.cfg?.cams : null) || []).slice();
    const minute = Math.floor(Date.now() / 60000);
    const items = cams.map((c) => ({ label: c.label, src: `${c.image}?t=${minute}`, live: c.live }));
    if (L?.cam) items.splice(1, 0, { label: `Stake at ${(L.generated || "").slice(11, 16) || "report"}`, src: "/" + L.cam, live: null });
    if (!items.length) { el.innerHTML = `<p class="muted">No cams configured.</p>`; return; }
    let sel = 0;
    const draw = () => {
      const c = items[sel];
      const inner = `<img src="${esc(c.src)}" alt="${esc(c.label)} cam" decoding="async"><span class="cap">${esc(c.label)}${c.live ? " · tap for live video" : ""}</span>`;
      el.innerHTML = (c.live ? `<a class="cam-main" style="display:block" href="${esc(c.live)}" target="_blank" rel="noopener">${inner}</a>` : `<div class="cam-main">${inner}</div>`) + `
        <div class="cam-row" style="margin-top:6px">${items.map((it, i) => `<button type="button" data-i="${i}" aria-pressed="${i === sel}"><img src="${esc(it.src)}" alt="" loading="lazy"><span>${esc(it.label)}</span></button>`).join("")}</div>`;
      el.querySelectorAll(".cam-row button").forEach((b) => b.addEventListener("click", () => { sel = +b.dataset.i; draw(); }));
    };
    draw();
  }

  /* ---------------- CALENDAR ---------------- */
  async function viewCalendar() {
    const v = document.createElement("div");
    v.className = "view v-cal";
    const C = S.cal;
    C.sel = C.sel || (S.latest?.date || todayIso());
    C.month = C.month || C.sel.slice(0, 7);
    const [y, m] = C.month.split("-").map(Number);
    const prevYm = iso(new Date(y, m - 2, 1)).slice(0, 7), nextYm = iso(new Date(y, m, 1)).slice(0, 7);
    await Promise.all([month(C.month), month(prevYm)]);

    // Week (Mon-Sun) containing the selected day.
    const sel = pd(C.sel), dow = (sel.getDay() + 6) % 7;
    const weekStart = addDays(C.sel, -dow), weekDays = [...Array(7)].map((_, i) => addDays(weekStart, i));
    await month(weekDays[6].slice(0, 7));
    const wk = weekDays.map((d) => ({ d, s: morningSnow(d), r: dayRow(d) }));
    const wkTotal = wk.reduce((a, x) => a + (x.s || 0), 0), wkReports = wk.filter((x) => groomedRuns(x.r).length || x.r?.map).length;

    const monthDays = [...Array(new Date(y, m, 0).getDate())].map((_, i) => iso(new Date(y, m - 1, i + 1)));
    const mSnow = monthDays.map((d) => ({ d, s: morningSnow(d) }));
    const mTotal = mSnow.reduce((a, x) => a + (x.s || 0), 0);
    const best = mSnow.reduce((a, x) => ((x.s || 0) > (a.s || 0) ? x : a), { s: 0 });
    const mReports = monthDays.filter((d) => { const r = dayRow(d); return r && (groomedRuns(r).length || r.map); }).length;
    const season = Object.values(S.months).flatMap((mm) => Object.values(mm.days)).map((r) => r.season_in).filter((x) => x != null).pop();

    const statTiles = C.mode === "week"
      ? `<div><span class="label">Snowfall this week</span><span class="mid">${inch(wkTotal)}</span></div>
         <div><span class="label">Grooming reports</span><span class="mid">${wkReports}</span></div>`
      : `<div><span class="label">Snowfall in ${MO[m - 1]}</span><span class="mid">${inch(mTotal)}</span></div>
         <div><span class="label">Snowiest day</span><span class="mid">${best.s ? inch(best.s) : "–"}</span><span class="sub">${best.d ? fmtDay(best.d) : "&nbsp;"}</span></div>
         <div><span class="label">Grooming reports</span><span class="mid">${mReports}</span></div>
         <div><span class="label">Season to date</span><span class="mid">${inch(season)}</span><span class="sub">resort reported</span></div>`;

    v.innerHTML = `
      <div class="seg" role="group" aria-label="Calendar view">
        ${["day", "week", "month"].map((k) => `<button type="button" data-mode="${k}" aria-pressed="${C.mode === k}">${k[0].toUpperCase() + k.slice(1)}</button>`).join("")}
      </div>
      <section class="card" id="cal-card"></section>
      <section class="card" aria-labelledby="h-feed">
        <div class="card-head"><h2 id="h-feed">Grooming reports</h2><span class="muted small">Newest first</span></div>
        <div class="feed" id="feed"></div>
        <button class="btn secondary block" type="button" id="more">Show earlier reports</button>
      </section>`;
    v.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => { C.mode = b.dataset.mode; route(); }));

    const card = $("#cal-card", v);
    if (C.mode === "day") {
      card.replaceWith(await dayCard(C.sel));
    } else if (C.mode === "week") {
      const max = Math.max(1, ...wk.map((x) => x.s || 0));
      card.innerHTML = `
        <div class="month-nav"><button type="button" data-step="-7" aria-label="Previous week">‹</button><h2>Week of ${fmtDay(weekStart)}</h2><button type="button" data-step="7" aria-label="Next week">›</button></div>
        <div class="stats">${statTiles}</div>
        <div class="week-bars" aria-label="Snowfall by day">${wk.map((x) => `<div><span class="num">${x.s == null ? "–" : inch(x.s)}</span><span class="b" style="height:${((x.s || 0) / max) * 80}%"></span><span>${WD[pd(x.d).getDay()]}</span></div>`).join("")}</div>
        <div class="feed">${wk.slice().reverse().filter((x) => groomedRuns(x.r).length).map((x) => feedItem(x.d, x.r)).join("") || `<p class="muted small">No grooming reports this week.</p>`}</div>`;
      card.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => { C.sel = addDays(C.sel, +b.dataset.step); C.month = C.sel.slice(0, 7); route(); }));
    } else {
      const first = (new Date(y, m - 1, 1).getDay() + 6) % 7, today = todayIso();
      // Two groups so wide screens can set the calendar beside the totals; on a phone they
      // interleave back into one column (see .cal-main / .cal-side in app.css).
      card.classList.add("month");
      card.innerHTML = `
        <div class="cal-main">
        <div class="month-nav"><button type="button" data-ym="${prevYm}" aria-label="Previous month">‹</button><h2>${MONTH_FULL[m - 1]} ${y}</h2><button type="button" data-ym="${nextYm}" aria-label="Next month">›</button></div>
        <div class="cal" role="grid" aria-label="${MONTH_FULL[m - 1]} ${y}">
          ${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => `<span class="dow">${d.slice(0, 2)}</span>`).join("")}
          ${Array(first).fill('<button class="empty" tabindex="-1" aria-hidden="true"></button>').join("")}
          ${monthDays.map((d) => {
            const s = morningSnow(d), r = dayRow(d), heat = s ? Math.min(1, s / 12) : 0;
            const cls = [d === today ? "today" : "", d === C.sel ? "sel" : "", d > today ? "future" : ""].join(" ");
            return `<button type="button" class="${cls}" data-day="${d}" style="${heat ? `background:color-mix(in oklab, var(--snow) ${Math.round(12 + heat * 55)}%, var(--surface));` : ""}" aria-label="${fmtDay(d)}${s != null ? ", " + inch(s) + " new snow" : ""}${groomedRuns(r).length ? ", grooming report" : ""}">
              <span class="d">${pd(d).getDate()}</span>${s ? `<span class="s">${inch(s)}</span>` : "<span></span>"}${groomedRuns(r).length || r?.map ? '<span class="g"></span>' : ""}</button>`;
          }).join("")}
        </div>
        <div class="legend"><span><i style="background:color-mix(in oklab, var(--snow) 50%, var(--surface))"></i>New snow that morning</span><span><i style="background:var(--accent);border-radius:50%"></i>Grooming report saved</span></div>
        </div>
        <div class="cal-side">
        <div class="stats">${statTiles}</div>
        <div class="card-head" style="margin-top:4px"><h3>Snowfall so far in ${MONTH_FULL[m - 1]}</h3><span class="muted small">dashed = forecast</span></div>
        <div id="accum"></div>
        </div>`;
      // Running total for the month; the current month continues with the forecast.
      let run = 0;
      const pts = monthDays.filter((d) => d <= today).map((d) => { const add = morningSnow(d) || 0; run += add; return { date: d, total: run, add }; });
      const ahead = [];
      if (C.month === today.slice(0, 7) && S.latest?.forecast?.days) {
        let t = run, lo = run, hi = run;
        S.latest.forecast.days.filter((f) => f.date > today && f.date.slice(0, 7) === C.month)
          .forEach((f) => { t += f.snow; lo += f.low ?? f.snow; hi += f.high ?? f.snow; ahead.push({ date: f.date, total: t, lo, hi }); });
      }
      if (pts.length || ahead.length) $("#accum", card).appendChild(accumChart(pts, ahead));
      card.querySelectorAll("[data-ym]").forEach((b) => b.addEventListener("click", () => { C.month = b.dataset.ym; route(); }));
      card.querySelectorAll("[data-day]").forEach((b) => b.addEventListener("click", () => { C.sel = b.dataset.day; showDaySheet(b.dataset.day); }));
    }

    // Feed: newest first across loaded months, loading earlier months on demand.
    let feedMonths = [C.month, prevYm];
    const drawFeed = () => {
      const rows = feedMonths.flatMap((ym) => Object.values((S.months[ym] || { days: {} }).days))
        .filter((r) => groomedRuns(r).length || r.map).sort((a, b) => (a.date < b.date ? 1 : -1));
      $("#feed", v).innerHTML = rows.map((r) => feedItem(r.date, r)).join("") || `<p class="muted small">No grooming reports saved for ${MONTH_FULL[m - 1]} yet.</p>`;
    };
    drawFeed();
    $("#more", v).addEventListener("click", async () => {
      const last = feedMonths[feedMonths.length - 1].split("-").map(Number);
      const ym = iso(new Date(last[0], last[1] - 2, 1)).slice(0, 7);
      await month(ym); feedMonths.push(ym); drawFeed();
    });
    v.addEventListener("click", (e) => { const f = e.target.closest("[data-feed]"); if (f) showDaySheet(f.dataset.feed); });
    return v;
  }

  function feedItem(d, r) {
    const runs = groomedRuns(r);
    return `<button class="feed-item" type="button" data-feed="${d}">
      ${r?.map ? `<img src="/${esc(r.map)}" alt="" loading="lazy">` : '<span class="noimg"></span>'}
      <span><strong>${fmtDay(d)}</strong><span class="muted small">${runs.length} runs${morningSnow(d) ? ` · ${inch(morningSnow(d))} new` : ""}</span><span class="runs-line">${esc(runs.join(", ")) || "Map only"}</span></span></button>`;
  }

  async function dayCard(d) {
    await month(d.slice(0, 7)); await month(addDays(d, -1).slice(0, 7));
    const r = dayRow(d) || {};
    const el = document.createElement("section");
    el.className = "card day-card";
    el.innerHTML = `
      <div class="month-nav"><button type="button" data-step="-1" aria-label="Previous day">‹</button><h2>${fmtDay(d)}</h2><button type="button" data-step="1" aria-label="Next day">›</button></div>
      <div class="snow-grid">
        <div><span class="label">New snow</span><span class="big">${inch(morningSnow(d))}</span></div>
        <div><span class="label">Base</span><span class="mid">${inch(r.base_in)}</span></div>
        <div><span class="label">Forecast then</span><span class="mid">${inch(r.next_1_5)}</span><span class="sub">next 5 days</span></div>
      </div>
      ${r.map ? `<button class="map-btn" type="button" data-map="${esc(r.map)}"><img src="/${esc(r.map)}" alt="Grooming map for ${fmtDay(d)}" loading="lazy"></button>` : `<p class="muted small">No grooming map saved for this day.</p>`}
      ${runsBlock({ groomers_of_the_day: r.featured, overnight: r.overnight, morning: r.morning, groomed: r.groomed })}
      <div id="day-hourly"></div>
      ${r.cam ? `<div class="cam-main"><img src="/${esc(r.cam)}" alt="Snow stake on ${fmtDay(d)}" loading="lazy"><span class="cap">Snow stake</span></div>` : ""}`;
    const rec = S.latest?.date === d ? S.latest : await getJSON(`/data/days/${d}.json`);
    const hrs = rec?.hourly?.hours || [];
    if (hrs.length) {
      const box = el.querySelector("#day-hourly");
      box.innerHTML = `<div class="card-head"><h3>Hourly snow and temperature</h3><span class="muted small">from the ${(rec.generated || "").slice(11, 16)} report</span></div>`;
      box.appendChild(hourlyChart(hrs));
    }
    el.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => { S.cal.sel = addDays(d, +b.dataset.step); S.cal.month = S.cal.sel.slice(0, 7); route(); }));
    const mb = el.querySelector("[data-map]");
    if (mb) mb.addEventListener("click", () => openLightbox("/" + mb.dataset.map, "Grooming map"));
    return el;
  }

  async function showDaySheet(d) {
    const card = await dayCard(d);
    openSheet(fmtDay(d), "", (ov, close) => {
      card.querySelector(".month-nav").remove();
      ov.querySelector(".sheet").appendChild(card);
      const full = document.createElement("button");
      full.className = "btn secondary block"; full.type = "button"; full.textContent = "Open in day view";
      full.addEventListener("click", () => { close(); S.cal.mode = "day"; S.cal.sel = d; route(); });
      ov.querySelector(".sheet").appendChild(full);
    });
  }

  /* ---------------- RADAR ---------------- */
  // A vector map (MapLibre, vendored in /vendor, with OpenFreeMap's keyless style) repainted in the theme's colours.
  // If the library, WebGL or the style can't load, it falls back to a fixed grid of 256px image tiles.
  // Past frames are NEXRAD composites and future frames are HRRR simulated radar, both from Iowa State's Mesonet tile cache.
  const RADAR = { z: 7, cols: 4, rows: 3, src: "https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0", base: "https://tile.openstreetmap.org", style: "https://tiles.openfreemap.org/styles/positron" };
  const worldPx = (lat, lon, z) => { const n = 256 * 2 ** z, sn = Math.sin(lat * Math.PI / 180); return [(lon + 180) / 360 * n, (0.5 - Math.log((1 + sn) / (1 - sn)) / (4 * Math.PI)) * n]; };
  function radarFrames(now) {
    const p2 = (n) => String(n).padStart(2, "0");
    const t0 = Math.floor(now / 300000) * 300000, out = [];
    for (let m = 55; m >= 5; m -= 5) out.push({ t: t0 - m * 60000, layer: `nexrad-n0q-m${p2(m)}m`, kind: "Radar" });
    out.push({ t: t0, layer: "nexrad-n0q", kind: "Radar, latest" });
    // The newest HRRR run is ready about 50 minutes after the next hour starts, so a run two hours back is always there.
    const init = Math.floor(now / 3600000 - 2) * 3600000, d = new Date(init);
    const stamp = `${d.getUTCFullYear()}${p2(d.getUTCMonth() + 1)}${p2(d.getUTCDate())}${p2(d.getUTCHours())}00`;
    for (let t = (Math.floor(t0 / 1800000) + 1) * 1800000, i = 0; i < 24; i++, t += 1800000) {
      const f = Math.round((t - init) / 60000);
      if (f > 1080) break;
      out.push({ t, layer: `hrrr::REFD-F${String(f).padStart(4, "0")}-${stamp}`, kind: "Model forecast" });
    }
    return out;
  }
  // Each resort is a marker with its name. Resorts sit close together, so each label takes the first side
  // (above, below, right, left, then further out) where it doesn't cover a label or marker already placed.
  // `spots` are {name, x, y, me} in pixels; returns the side for each, selected resort first.
  function labelSides(spots) {
    const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
    const placed = spots.map((s) => [s.x - 7, s.y - 7, s.x + 7, s.y + 7]);
    const out = new Map();
    [...spots].sort((a, b) => b.me - a.me).forEach((s) => {
      const w = s.name.length * 6.2 + 10, h = w / 2, boxes = {
        n: [s.x - h, s.y - 26, s.x + h, s.y - 11], s: [s.x - h, s.y + 11, s.x + h, s.y + 26],
        e: [s.x + 11, s.y - 8, s.x + 11 + w, s.y + 8], w: [s.x - 11 - w, s.y - 8, s.x - 11, s.y + 8],
        s2: [s.x - h, s.y + 27, s.x + h, s.y + 42], n2: [s.x - h, s.y - 42, s.x + h, s.y - 27],
      };
      const side = Object.keys(boxes).find((k) => !placed.some((p) => hit(boxes[k], p))) || "n";
      placed.push(boxes[side]);
      out.set(s, side);
    });
    return out;
  }

  // ---- One-colour look: the map and the radar both take their colours from the theme. ----
  const rgbOf = (c) => { const m = /^#?([0-9a-f]{6})$/i.exec(String(c).trim()); const n = m ? parseInt(m[1], 16) : 0x808080; return [n >> 16, (n >> 8) & 255, n & 255]; };
  const hexOf = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  const mixRgb = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
  function radarPalette() {
    const cs = getComputedStyle(document.documentElement), v = (n) => rgbOf(cs.getPropertyValue(n));
    const bg = v("--bg"), ink = v("--ink"), white = [255, 255, 255], black = [0, 0, 0];
    const accent = v("--accent");
    const dark = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) < 110;
    const ramp = dark
      ? [mixRgb(bg, accent, 0.36), mixRgb(bg, accent, 0.55), mixRgb(bg, accent, 0.75), mixRgb(bg, accent, 0.92), mixRgb(accent, white, 0.4)]
      : [mixRgb(white, accent, 0.3), mixRgb(white, accent, 0.5), mixRgb(white, accent, 0.72), accent, mixRgb(accent, black, 0.35)];
    const map = dark
      ? { land: bg, hills: mixRgb(bg, ink, 0.07), water: mixRgb(bg, black, 0.35), roads: mixRgb(bg, ink, 0.26), lines: mixRgb(bg, ink, 0.14), labels: mixRgb(bg, ink, 0.66), halo: bg }
      : { land: mixRgb(bg, white, 0.55), hills: mixRgb(bg, white, 0.12), water: mixRgb(bg, ink, 0.07), roads: mixRgb(bg, ink, 0.24), lines: mixRgb(bg, ink, 0.1), labels: mixRgb(bg, ink, 0.68), halo: mixRgb(bg, white, 0.55) };
    return { dark, ramp, map: Object.fromEntries(Object.entries(map).map(([k, c]) => [k, hexOf(c)])), pin: hexOf(ink), pinText: hexOf(dark ? bg : white) };   // markers in the theme's ink, so they stand apart from the accent-coloured radar
  }
  // How strong an echo is, 0 to 1, from its colour in the standard radar palette. That palette runs
  // cyan, blue, green, yellow, orange, red, magenta, and is not ordered by brightness, so this goes by hue.
  function echoStrength(r, g, b) {
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, val = mx / 255;
    if (mx === 0 || d / mx < 0.2) return 0.05;
    let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h = (h * 60 + 360) % 360;
    const dim = (span) => Math.min(1, Math.max(0, (1 - val) / span));
    if (h >= 165 && h < 255) return 0.05 + 0.30 * (h - 165) / 90;   // cyan to blue: light
    if (h >= 75 && h < 165) return 0.35 + 0.22 * dim(0.45);         // greens: moderate
    if (h >= 45 && h < 75) return 0.57 + 0.13 * dim(0.3);           // yellows
    if (h >= 15 && h < 45) return 0.74;                             // orange
    if (h < 15 || h >= 330) return 0.8 + 0.12 * dim(0.3);           // reds: heavy
    return 0.96;                                                    // magenta and beyond
  }
  // Repaint one radar tile in the theme's ramp. Throws if the tile can't be read (blocked cross-origin).
  let radarRamp = null;
  function recolorRadar(bitmap) {
    const c = document.createElement("canvas"); c.width = bitmap.width; c.height = bitmap.height;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(bitmap, 0, 0);
    const img = ctx.getImageData(0, 0, c.width, c.height), px = img.data, ramp = radarRamp;
    for (let i = 0; i < px.length; i += 4) {
      if (!px[i + 3]) continue;
      const t = echoStrength(px[i], px[i + 1], px[i + 2]) * (ramp.length - 1), k = Math.min(ramp.length - 2, Math.floor(t)), f = t - k;
      px[i] = ramp[k][0] + (ramp[k + 1][0] - ramp[k][0]) * f;
      px[i + 1] = ramp[k][1] + (ramp[k + 1][1] - ramp[k][1]) * f;
      px[i + 2] = ramp[k][2] + (ramp[k + 1][2] - ramp[k][2]) * f;
    }
    // Blend each pixel with its neighbours (alpha-weighted), so blocks soften and lone specks of noise fade.
    const w = c.width, h = c.height, src = new Float32Array(px.length), tmp = new Float32Array(px.length);
    for (let i = 0; i < px.length; i += 4) { const a = px[i + 3] / 255; src[i] = px[i] * a; src[i + 1] = px[i + 1] * a; src[i + 2] = px[i + 2] * a; src[i + 3] = px[i + 3]; }
    const pass = (from, to, step, len, lines, lineStep) => {
      for (let l = 0; l < lines; l++) for (let k = 0; k < len; k++) {
        const i = l * lineStep + k * step, a = k > 0 ? i - step : i, b = k < len - 1 ? i + step : i;
        for (let ch = 0; ch < 4; ch++) to[i + ch] = (from[a + ch] + 2 * from[i + ch] + from[b + ch]) / 4;
      }
    };
    pass(src, tmp, 4, w, h, w * 4); pass(tmp, src, w * 4, h, w, 4);
    for (let i = 0; i < px.length; i += 4) { const a = src[i + 3] / 255; if (a > 0) { px[i] = src[i] / a; px[i + 1] = src[i + 1] / a; px[i + 2] = src[i + 2] / a; } px[i + 3] = src[i + 3]; }
    ctx.putImageData(img, 0, 0);
    return c;
  }
  // The map library is only fetched when the Forecast tab is opened.
  let mapLib = null;
  const loadMapLib = () => mapLib || (mapLib = new Promise((ok, fail) => {
    const ready = (gl) => {
      // Radar tiles go through this so they can be repainted before the map draws them.
      gl.addProtocol("radarmono", async (params, abort) => {
        const res = await fetch(params.url.replace("radarmono://", "https://"), { signal: abort.signal });
        if (!res.ok) throw new Error(`radar tile ${res.status}`);
        const canvas = recolorRadar(await createImageBitmap(await res.blob()));
        return { data: await createImageBitmap(canvas) };
      });
      ok(gl);
    };
    if (window.maplibregl) return ready(window.maplibregl);
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/vendor/maplibre-gl.css"; document.head.appendChild(css);
    const js = document.createElement("script"); js.src = "/vendor/maplibre-gl.js";
    js.onload = () => (window.maplibregl ? ready(window.maplibregl) : fail(new Error("map library missing")));
    js.onerror = () => { mapLib = null; fail(new Error("map library failed to load")); };
    document.head.appendChild(js);
  }));
  // Repaint the vector style in the theme's colours. Layers are matched by type and name, so a change
  // in the style's layer list degrades to that layer's own colour, not to an error.
  function themeStyle(style, c) {
    (style.layers || []).forEach((l) => {
      const p = (l.paint = l.paint || {});
      if (l.type === "background") p["background-color"] = c.land;
      else if (l.type === "fill") { p["fill-color"] = /water|ocean|lake/.test(l.id) ? c.water : /building/.test(l.id) ? c.lines : c.hills; delete p["fill-pattern"]; delete p["fill-outline-color"]; }
      else if (l.type === "line") p["line-color"] = /water/.test(l.id) ? c.water : /boundary|admin/.test(l.id) ? c.lines : c.roads;
      else if (l.type === "symbol") { p["text-color"] = c.labels; p["text-halo-color"] = c.halo; delete p["icon-color"]; }
    });
    return style;
  }
  // Used when the vector style can't be fetched: the standard street map, drained of colour by the renderer.
  const rasterStyle = (c, dark) => ({ version: 8, sources: { osm: { type: "raster", tiles: [`${RADAR.base}/{z}/{x}/{y}.png`], tileSize: 256, maxzoom: 19, attribution: "© OpenStreetMap" } },
    layers: [{ id: "bg", type: "background", paint: { "background-color": c.land } }, { id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -1, "raster-contrast": -0.25, "raster-opacity": dark ? 0.25 : 0.7 } }] });

  let radarMap = null;
  function mountRadar(card) {
    const r = resortInfo();
    if (radarMap) { try { radarMap.remove(); } catch {} radarMap = null; }
    if (!card || r?.lat == null || r?.lon == null) { card?.remove(); return; }
    const frames = radarFrames(Date.now()), nowIdx = frames.findIndex((f) => f.layer === "nexrad-n0q");
    const fmt = new Intl.DateTimeFormat("en-US", { timeZone: r.timezone || S.cfg?.timezone || RESORT_TZ, month: "numeric", day: "numeric", hour: "numeric", minute: "2-digit" });
    const resortsOnMap = R.list.filter((o) => o.lat != null && o.lon != null);
    const pal = radarPalette();
    radarRamp = pal.ramp;
    card.innerHTML = `
      <div class="card-head"><h2>Radar</h2><span class="muted small" id="radar-when" aria-live="polite"></span></div>
      <div class="radar-map${pal.dark ? " dark" : ""}" id="radar-map" style="--radar-land:${pal.map.land};--radar-pin:${pal.pin};--radar-pin-text:${pal.pinText}">
        <span class="radar-legend" id="radar-legend" hidden>Light <i style="background:linear-gradient(90deg, ${pal.ramp.map(hexOf).join(", ")})"></i> Heavy</span>
        <p class="radar-none muted small" id="radar-none" hidden>No radar image for this time.</p>
      </div>
      <div class="radar-ctl">
        <button class="btn secondary" type="button" id="radar-play">Play</button>
        <input type="range" id="radar-time" min="0" max="${frames.length - 1}" step="1" value="${nowIdx}" aria-label="Radar time, from an hour ago to 12 hours ahead">
        <button class="btn secondary" type="button" id="radar-now">Now</button>
      </div>
      <p class="muted small radar-note">Slide left for the past hour of radar and right for the next 12 hours from the HRRR model. Mountains block the radar beam, so light snow on the hill can be missing. Use two fingers to move the map.</p>`;
    const map = $("#radar-map", card), slider = $("#radar-time", card), play = $("#radar-play", card), when = $("#radar-when", card), none = $("#radar-none", card);
    let cur = -1, timer = null, view = null;   // view = { show(i, prev), preload(i), failed(i) }
    const show = (i) => {
      const prev = cur; cur = i;
      slider.value = i;
      const f = frames[i];
      when.textContent = `${fmt.format(new Date(f.t)).replace(",", "")} · ${f.kind}`;
      slider.setAttribute("aria-valuetext", when.textContent);
      if (view) { view.show(i, prev); none.hidden = !view.failed(i); }
    };
    const stop = () => { clearInterval(timer); timer = null; play.textContent = "Play"; };
    play.addEventListener("click", () => {
      if (timer) return stop();
      play.textContent = "Pause";
      if (cur === frames.length - 1) show(0);
      timer = setInterval(() => {
        if (!card.isConnected) return stop();
        const next = (cur + 1) % frames.length;
        show(next);
        view?.preload((next + 1) % frames.length);   // start loading the frame after this one
        if (next === frames.length - 1) stop();
      }, 700);
    });
    slider.addEventListener("input", () => { stop(); show(Number(slider.value)); });
    $("#radar-now", card).addEventListener("click", () => { stop(); show(nowIdx); });
    show(nowIdx);
    const refresh = () => { if (view) none.hidden = !view.failed(cur); };
    const start = (v) => { if (!card.isConnected) return; view = v; view.show(cur, -1); refresh(); };
    radarVector(map, r, resortsOnMap, frames, refresh, pal).then(start).catch(() => { if (card.isConnected) start(radarTiles(map, r, resortsOnMap, frames, refresh)); });
  }

  // Sharp vector map (MapLibre + OpenFreeMap, no API key) that can be moved and zoomed.
  async function radarVector(map, r, list, frames, refresh, pal) {
    const gl = await loadMapLib();
    let style = rasterStyle(pal.map, pal.dark);
    try {
      const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 6000);
      const res = await fetch(RADAR.style, { signal: ctl.signal });
      clearTimeout(t);
      if (res.ok) style = themeStyle(await res.json(), pal.map);
    } catch {}
    if (!map.isConnected) throw new Error("card closed");
    const holder = document.createElement("div"); holder.className = "radar-gl"; map.prepend(holder);
    let m;
    try {
      m = new gl.Map({ container: holder, style, center: [r.lon, r.lat], zoom: 6.4, minZoom: 4, maxZoom: 10, cooperativeGestures: true, dragRotate: false, pitchWithRotate: false, attributionControl: { compact: true } });
      radarMap = m;
      m.touchZoomRotate.disableRotation();
      await new Promise((ok, fail) => { m.once("load", ok); m.on("error", (e) => { if (!m.loaded() && !e.sourceId) fail(e.error || new Error("map failed")); }); setTimeout(() => fail(new Error("map timed out")), 12000); });
    } catch (e) {
      try { m?.remove(); } catch {}
      radarMap = null; holder.remove();
      throw e;
    }
    // Show every resort at once.
    const b = new gl.LngLatBounds(); list.forEach((o) => b.extend([o.lon, o.lat]));
    if (list.length > 1) m.fitBounds(b, { padding: { top: 48, bottom: 36, left: 64, right: 64 }, maxZoom: 7.5, duration: 0 });
    const pins = list.map((o) => {
      const el = document.createElement("div"); el.className = "radar-pin";
      el.innerHTML = `<span class="radar-dot${o.slug === r.slug ? " me" : ""}"><b>${esc(o.name)}</b></span>`;
      new gl.Marker({ element: el, anchor: "center" }).setLngLat([o.lon, o.lat]).addTo(m);
      return { o, label: el.querySelector("b") };
    });
    const relabel = () => {
      const spots = pins.map((p) => { const pt = m.project([p.o.lon, p.o.lat]); return { p, name: p.o.name, x: pt.x, y: pt.y, me: p.o.slug === r.slug }; });
      labelSides(spots).forEach((side, s) => { s.p.label.className = side; });
    };
    relabel(); m.on("zoomend", relabel); m.on("resize", relabel);
    // Radar frames are image layers under the map's labels, repainted in the theme's ramp on the way in.
    // Tiles stop at zoom 6 and are smoothed as they are enlarged, which turns the square radar pixels into soft shapes.
    const under = (m.getStyle().layers.find((l) => l.type === "symbol") || {}).id;
    const added = new Set(), failed = new Set();
    const id = (i) => `radar-${i}`;
    const add = (i) => {
      if (added.has(i) || radarMap !== m) return;
      added.add(i);
      m.addSource(id(i), { type: "raster", tiles: [`${RADAR.src.replace("https://", "radarmono://")}/${frames[i].layer}/{z}/{x}/{y}.png`], tileSize: 256, maxzoom: 6, attribution: "NOAA, Iowa State Mesonet" });
      m.addLayer({ id: id(i), type: "raster", source: id(i), paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 0 }, "raster-resampling": "linear", "raster-fade-duration": 0 } }, under);
    };
    const frameOf = (e) => { const n = /^radar-(\d+)$/.exec(e.sourceId || e.source?.id || ""); return n ? Number(n[1]) : null; };
    m.on("error", (e) => { const i = frameOf(e); if (i != null) { failed.add(i); refresh(); } });
    m.on("data", (e) => { const i = frameOf(e); if (i != null && e.tile && failed.delete(i)) refresh(); });
    $("#radar-legend", map.parentNode).hidden = false;
    const tuck = () => map.querySelector(".maplibregl-ctrl-attrib")?.classList.remove("maplibregl-compact-show");   // start as the small (i) button
    tuck(); m.once("idle", tuck);
    return {
      show(i, prev) { if (radarMap !== m) return; add(i); if (prev >= 0 && prev !== i && added.has(prev)) m.setPaintProperty(id(prev), "raster-opacity", 0); m.setPaintProperty(id(i), "raster-opacity", 0.88); },
      preload: add,
      failed: (i) => failed.has(i),
    };
  }

  // Fallback when the map library or WebGL isn't available: a fixed grid of 256px image tiles centred on the resort.
  function radarTiles(map, r, list, frames, refresh) {
    const { z, cols, rows } = RADAR, [px, py] = worldPx(r.lat, r.lon, z);
    const tx = Math.floor(px / 256), ty = Math.floor(py / 256);
    const x0 = tx - (px / 256 - tx >= 0.5 ? 1 : 2), y0 = ty - 1;
    const pos = `left:calc(50% - ${(px - x0 * 256).toFixed(1)}px);top:calc(50% - ${(py - y0 * 256).toFixed(1)}px)`;
    const tiles = (url) => { let s = ""; for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) s += `<img src="${url}/${z}/${x0 + i}/${y0 + j}.png" alt="" decoding="async" draggable="false">`; return s; };
    const spots = list.map((o) => { const [ox, oy] = worldPx(o.lat, o.lon, z); return { name: o.name, x: ox - px, y: oy - py, me: o.slug === r.slug }; });
    const sides = labelSides(spots);
    const dots = spots.map((s) => `<span class="radar-dot${s.me ? " me" : ""}" style="left:calc(50% + ${s.x.toFixed(1)}px);top:calc(50% + ${s.y.toFixed(1)}px)"><b class="${sides.get(s)}">${esc(s.name)}</b></span>`).join("");
    map.insertAdjacentHTML("afterbegin", `
        <div class="radar-tiles radar-base" style="${pos}">${tiles(RADAR.base)}</div>
        <div class="radar-tint"></div>
        <svg class="radar-defs" aria-hidden="true"><filter id="radar-soft" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="2.4"/><feComponentTransfer><feFuncA type="linear" slope="2.6"/></feComponentTransfer></filter></svg>
        ${dots}
        <span class="radar-attr">© OpenStreetMap · NOAA, Iowa State Mesonet</span>`);
    map.querySelectorAll(".radar-base img").forEach((im) => im.addEventListener("error", () => { im.style.visibility = "hidden"; }));
    const layers = new Map();
    const layerFor = (i) => {
      if (layers.has(i)) return layers.get(i);
      const el = document.createElement("div");
      el.className = "radar-tiles radar-frame"; el.style.cssText = pos; el.innerHTML = tiles(`${RADAR.src}/${frames[i].layer}`);
      el.failed = 0;
      el.querySelectorAll("img").forEach((im) => im.addEventListener("error", () => { im.style.visibility = "hidden"; el.failed++; refresh(); }));
      map.insertBefore(el, map.querySelector(".radar-dot, .radar-attr"));
      layers.set(i, el);
      return el;
    };
    return {
      show(i, prev) { const el = layerFor(i); if (prev >= 0 && prev !== i) layers.get(prev)?.classList.remove("on"); el.classList.add("on"); },
      preload: layerFor,
      failed: (i) => (layers.get(i)?.failed || 0) >= cols * rows,
    };
  }

  // Selecting a day in the 10-day chart opens that day's model votes: a pop-up beside the bar on
  // wide screens, a bottom sheet on a phone. The same bar, the close button, Esc or a click outside closes it.
  function dayVotes(card, days, labels, modelCount) {
    const chart = $("#fc-chart", card);
    let open = -1, pop = null;
    const one = (x) => (x >= 0.05 ? `${Math.round(x * 10) / 10}"` : '0"');   // tenths, so close calls stay distinguishable
    const body = (d) => {
      const votes = Object.entries(d.models || {}).filter(([, x]) => x != null).sort((a, b) => b[1] - a[1]);
      const max = Math.max(1, d.high ?? 0, d.snow, ...votes.map(([, x]) => x));
      const row = (name, x, blend) => `<div class="vp-row${blend ? " blend" : ""}"><span>${esc(name)}</span><span class="vp-bar"><i style="width:${Math.round((x / max) * 100)}%"></i></span><span class="num">${one(x)}</span></div>`;
      let rowsHtml = "", placed = false;
      votes.forEach(([m, x]) => { if (!placed && x < d.snow) { rowsHtml += row("Blend", d.snow, true); placed = true; } rowsHtml += row(labels[m] || m, x); });
      if (!placed) rowsHtml += row("Blend", d.snow, true);
      const mark = d.snow >= 1 ? Math.floor(d.snow) : 0, agree = votes.filter(([, x]) => (mark ? x >= mark : x >= 0.1)).length;
      return `<p class="muted small">Blend ${one(d.snow)}. Range ${one(d.low ?? d.snow)} to ${one(d.high ?? d.snow)}. ${votes.length} of ${modelCount || votes.length} models reach this day.</p>
        <div class="vp-rows">${rowsHtml}</div>
        <p class="small">${votes.length ? `${agree} of ${votes.length} models show ${mark ? `${mark} ${mark === 1 ? "inch" : "inches"} or more` : "some snow"}.` : "No model reaches this day yet."}</p>`;
    };
    const close = () => {
      if (pop) pop.remove();
      pop = null; open = -1;
      chart.querySelectorAll(".day-hit.sel").forEach((r) => r.classList.remove("sel"));
      document.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onOutside);
    };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    const onOutside = (e) => { if (pop && !pop.contains(e.target) && !e.target.closest(".day-hit")) close(); };
    const show = (i, hit) => {
      const d = days[i], title = `Model votes, ${dayTick(d.date).label}`;
      $("#tip").hidden = true;
      if (!matchMedia("(min-width: 900px)").matches) { close(); openSheet(title, body(d)); return; }
      if (open === i) return close();
      close(); open = i; hit.classList.add("sel");
      pop = document.createElement("div");
      pop.className = "votes-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", title);
      pop.innerHTML = `<div class="vp-head"><h3>${title}</h3><button type="button" class="vp-close" aria-label="Close">×</button></div>${body(d)}`;
      card.appendChild(pop);
      // Sit beside the selected bar, on whichever side has room, and stay inside the card.
      const c = card.getBoundingClientRect(), h = hit.getBoundingClientRect(), w = pop.offsetWidth, gap = 8;
      const right = h.right - c.left + gap, left = h.left - c.left - gap - w;
      pop.style.left = Math.max(8, Math.min(c.width - w - 8, right + w <= c.width - 8 ? right : left)) + "px";
      pop.style.top = Math.max(8, Math.min(c.height - pop.offsetHeight - 8, h.top - c.top)) + "px";
      pop.querySelector(".vp-close").addEventListener("click", () => { close(); hit.focus(); });
      document.addEventListener("keydown", onKey); document.addEventListener("pointerdown", onOutside);
    };
    chart.addEventListener("click", (e) => { const hit = e.target.closest(".day-hit"); if (hit) show(+hit.dataset.day, hit); });
    chart.addEventListener("keydown", (e) => {
      const hit = e.target.closest?.(".day-hit"); if (!hit) return;
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(+hit.dataset.day, hit); }
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = chart.querySelector(`.day-hit[data-day="${+hit.dataset.day + (e.key === "ArrowRight" ? 1 : -1)}"]`); if (n) { e.preventDefault(); n.focus(); } }
    });
    // A redraw (resize) replaces the bars, so drop any open pop-up with them.
    new ResizeObserver(() => { if (pop && !chart.querySelector(".day-hit.sel")) close(); }).observe(chart);
  }

  /* ---------------- FORECAST ---------------- */
  function viewForecast() {
    const v = document.createElement("div");
    v.className = "view v-fc";
    const fc = S.latest?.forecast || {}, days = fc.days || [], labels = fc.model_labels || {};
    const bands = bandsOf(S.latest);
    // The hourly strip stacks the temperatures like the mountain: peak on top, base at the bottom.
    const rows = bands.slice().reverse(), midBand = rows.find((b) => b.key === "mid") || rows[Math.floor(rows.length / 2)];
    const hours = S.latest?.hourly?.hours || [], snowMax = Math.max(0.5, ...hours.map((h) => h.snow || 0));
    const vm = S.verification?.models || {};
    const hist = (S.verification?.history || []).slice(-10).reverse();
    v.innerHTML = `
      <section class="card a-hours">
        <div class="card-head"><h2>Next 12 hours</h2><span class="muted small">${rows.length > 1 ? "Temperature at " + rows.map((b) => `${esc(b.label).toLowerCase()} ${bandFt(b)}`).join(", ") + " · wind in mph" : "Wind in mph"}</span></div>
        <div class="hstrip" role="group" aria-label="Next 12 hours, hour by hour">
          <div class="hs-col hs-labels" aria-hidden="true"><span class="t"></span><span class="sn">Snow</span>${rows.length ? rows.map((b) => `<span class="${b === midBand ? "mid" : "tmp"}">${esc(b.label)}</span>`).join("") : '<span class="mid">Temp</span>'}<span class="w">Wind</span></div>
          ${hours.map((h) => `<div class="hs-col" tabindex="0" data-tip="${hourLabel(h.time)}: ${rows.length ? rows.map((b) => `${esc(b.label)} ${bandTemp(b, h.time)}`).join(", ") : h.temp + "°"}, feels ${h.feels}°. Wind ${esc(h.dir)} ${h.wind} mph${h.gust != null ? ", gusts " + h.gust : ""}. ${h.snow ? h.snow + " in. snow" : "No snow"}, cloud ${h.cloud}%">
            <span class="t">${hourLabel(h.time)}</span>
            <span class="sn">${h.snow ? `<b>${h.snow}"</b>` : ""}<i class="${h.snow ? "on" : ""}" style="height:${h.snow ? Math.max(3, Math.round((h.snow / snowMax) * 20)) : 2}px"></i></span>
            ${rows.length ? rows.map((b) => `<span class="${b === midBand ? "mid" : "tmp"}">${bandTemp(b, h.time)}</span>`).join("") : `<span class="mid">${h.temp}°</span>`}
            <span class="w">${esc(h.dir)} ${h.wind}</span>
          </div>`).join("")}
        </div>
      </section>

      <section class="card a-ten">
        <div class="card-head"><h2>10-day snowfall</h2><span class="muted small">Blended from ${(fc.models_used || []).length} models</span></div>
        <div class="snow-grid">
          <div><span class="label">Days 1–5</span><span class="big">${inch(fc.next_1_5)}</span><span class="sub">${fc.next_1_5_range ? `likely ${inch(fc.next_1_5_range[0])}–${inch(fc.next_1_5_range[1])}` : ""}</span></div>
          <div><span class="label">Days 6–10</span><span class="mid">${inch(fc.next_6_10)}</span><span class="sub">${fc.next_6_10_range ? `${inch(fc.next_6_10_range[0])}–${inch(fc.next_6_10_range[1])}` : ""}</span></div>
          <div><span class="label">6"+ day odds</span><span class="mid">${fc.powder_odds_pct == null ? "–" : fc.powder_odds_pct + "%"}</span><span class="sub">next 5 days</span></div>
        </div>
        <div id="fc-chart"></div>
        <div class="legend stake-legend"><span><i style="background:var(--snow-fill);border:1px solid var(--accent)"></i>Expected</span><span><i class="hatch"></i>Could reach</span><span><i class="notch"></i>Low end</span><span class="pick-hint">Select a day to see each model's call.</span></div>
      </section>

      <section class="card a-radar" id="radar-card"></section>

      <section class="card a-more">
        <details><summary>Model votes, all 10 days</summary>
          <div id="fc-votes"></div>
          <div class="legend"><span><i style="background:var(--ink);opacity:.72;border-radius:50%"></i>One model's call</span><span><i style="background:var(--accent);height:4px;border-radius:2px"></i>Blend</span><span>Tight cluster = models agree</span></div>
        </details>
        <details><summary>Every model, day by day</summary>
          <div class="scroll"><table><thead><tr><th>Model</th>${days.map((d) => `<th>${dayTick(d.date).label}</th>`).join("")}<th>Weight ×</th></tr></thead><tbody>
            <tr><td><strong>Blend</strong></td>${days.map((d) => `<td><strong>${inch(d.snow)}</strong></td>`).join("")}<td></td></tr>
            ${(fc.models_used || []).map((m) => `<tr><td>${esc(labels[m] || m)}</td>${days.map((d) => `<td>${d.models?.[m] != null ? inch(d.models[m]) : "·"}</td>`).join("")}<td>${(vm[m]?.skill ?? 1).toFixed(2)}</td></tr>`).join("")}
          </tbody></table></div>
        </details>
        <details><summary>How the forecast is built</summary>
          <ol class="steps">
            <li>Public weather models (NOAA's GFS, HRRR, NAM and National Blend, ECMWF, ICON, GEM, UKMO) for a point on the upper mountain, not the town below, with temperature corrected to that elevation. The NWS forecasters' snowfall joins as one more voice.</li>
            <li>Liquid precipitation becomes snow with a temperature-based ratio tuned for dry Colorado snow, about 15 to 1 in the teens. Humidity decides rain or snow near freezing.</li>
            <li>Every model is scored daily against the ${esc(resortInfo().snotel || "nearest")} SNOTEL gauge, starting from how it did last winter. Models that run dry here are scaled up, and models that keep missing get less weight. The total is then checked against the resort's own snow report.</li>
            <li>High-resolution models lead for 48 hours, global models after that. Ensemble runs give the range and the powder odds.</li>
          </ol>
        </details>
        <details><summary>Forecast vs. what fell</summary>
          ${hist.length ? `<div class="scroll"><table><thead><tr><th>Day</th><th>Forecast</th><th>Range</th><th>Fell</th></tr></thead><tbody>${hist.map((h) => `<tr><td>${fmtDay(h.date)}</td><td>${inch(h.forecast)}</td><td>${inch(h.low)}–${inch(h.high)}</td><td>${inch(h.observed)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="muted small">Scores appear after a few days of forecasts are saved.</p>`}
        </details>
      </section>`;
    if (days.length) {
      // On wide screens the stakes grow to fill the card beside the radar.
      const plotH = matchMedia(WIDE).matches ? Math.max(168, Math.min(380, innerHeight - 564)) : 168;
      $("#fc-chart", v).appendChild(stakeChart(days, plotH, true));
      $("#fc-votes", v).appendChild(votesChart(days, labels));
      dayVotes($(".a-ten", v), days, labels, (fc.models_used || []).length);
    }
    bindTips($(".hstrip", v));
    mountRadar($("#radar-card", v));
    return v;
  }

  /* ---------------- sign-ups ---------------- */
  function wireEmailForm(v) {
    const form = $("#email-form", v), msg = $("#email-msg", v), input = $("#email-input", v);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = input.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(email)) { msg.textContent = "Enter an email address like you@example.com."; input.focus(); return; }
      const btn = form.querySelector("button"); btn.disabled = true; msg.textContent = "Sending…";
      try {
        const r = await fetch("/api/subscribe", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, resorts: picked(v, "email-resort"), website: $("#website", v).value }) });
        const j = await r.json().catch(() => ({}));
        msg.textContent = j.message || (r.ok ? "Check your inbox for a confirmation link." : "Sign-up didn't work. Please try again.");
        if (r.ok) input.value = "";
      } catch (err) { msg.textContent = "You seem to be offline. Try again when you have signal."; }
      btn.disabled = false;
    });
  }

  const b64ToBytes = (s) => { const b = atob((s + "===".slice((s.length + 3) % 4)).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from(b, (c) => c.charCodeAt(0)); };
  async function wirePush(v) {
    const state = $("#push-state", v), btn = $("#push-btn", v), hint = $("#push-hint", v);
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent), standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      state.textContent = ios && !standalone ? "Add Snow Desk to your Home Screen to get notifications." : "This browser can't show notifications.";
      if (ios && !standalone) hint.textContent = "In Safari, tap Share, then Add to Home Screen, then open Snow Desk from your Home Screen and come back here.";
      return;
    }
    const reg = await navigator.serviceWorker.register("/sw.js").catch(() => null);
    if (!reg) { state.textContent = "Notifications aren't available here."; return; }
    // The public key comes from the server, derived from VAPID_PRIVATE_KEY, so the two can never drift apart.
    const appKey = async () => (await (await fetch("/api/push")).json()).publicKey;
    const pushPicks = () => {
      const boxes = [...v.querySelectorAll('input[name="push-resort"]')];
      if (!boxes.length) return [R.slug];
      const a = boxes.filter((b) => b.checked).map((b) => b.value);
      try { localStorage.setItem("pushResorts", JSON.stringify(a)); } catch (e) {}
      return a.length ? a : [R.slug];
    };
    try { // show what this device chose last time
      const had = JSON.parse(localStorage.getItem("pushResorts") || "null");
      if (Array.isArray(had) && had.length) v.querySelectorAll('input[name="push-resort"]').forEach((b) => { b.checked = had.includes(b.value); });
    } catch (e) {}
    const save = (sub) => fetch("/api/push", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...sub.toJSON(), resorts: pushPicks() }) });
    v.querySelectorAll('input[name="push-resort"]').forEach((b) => b.addEventListener("change", async () => {
      const sub = await reg.pushManager.getSubscription();
      if (sub) { const r = await save(sub).catch(() => null); hint.textContent = r?.ok ? "Saved." : "Couldn't save. Please try again."; }
      else pushPicks();
    }));
    // If the app's key changed since this browser subscribed, move the subscription to the new key quietly.
    const refresh = async () => {
      const sub = await reg.pushManager.getSubscription();
      if (!sub || Notification.permission !== "granted" || !sub.options?.applicationServerKey) return;
      const key = b64ToBytes(await appKey());
      const had = new Uint8Array(sub.options.applicationServerKey);
      if (had.length === key.length && had.every((b, i) => b === key[i])) return;
      await fetch("/api/push", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) });
      await sub.unsubscribe();
      await save(await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }));
    };
    const render = async () => {
      const sub = await reg.pushManager.getSubscription();
      const denied = Notification.permission === "denied";
      state.textContent = sub ? "On: you'll get the morning report, with any powder alert in it." : denied ? "Blocked in your browser settings." : "Off";
      btn.textContent = sub ? "Turn off" : "Turn on";
      btn.hidden = denied && !sub;
      hint.textContent = denied ? "Allow notifications for snow.0xm.studio in your browser or phone settings, then reload." : "";
    };
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          await fetch("/api/push", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: existing.endpoint }) });
          await existing.unsubscribe();
        } else {
          if (await Notification.requestPermission() !== "granted") { await render(); btn.disabled = false; return; }
          const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(await appKey()) });
          const r = await save(sub);
          if (!r.ok) { await sub.unsubscribe(); hint.textContent = "Couldn't turn on notifications. Please try again."; }
        }
      } catch (e) { hint.textContent = "Couldn't change notifications. Please try again."; }
      btn.disabled = false;
      render();
    });
    await refresh().catch(() => {});
    render();
  }

  /* ---------------- HELP ---------------- */
  const tel = (n) => "tel:+1" + String(n).replace(/\D/g, "");
  function patrolCards() {
    const r = resortInfo(), p = r.patrol;
    const tell = `
      <section class="card">
        <h2>When you call, tell them</h2>
        <ol class="say">
          <li>The run name, or the nearest trail sign or lift tower number.</li>
          <li>What happened and how many people are hurt.</li>
          <li>Your phone number, and stay where patrol can find you.</li>
        </ol>
        <p class="small muted" style="margin:0">Cross your skis or board upright in the snow above the injured person so others can see you.</p>
      </section>`;
    if (!p) return `
      <section class="card patrol" aria-labelledby="h-patrol">
        <h2 id="h-patrol">${esc(r.name)} Ski Patrol</h2>
        <p style="margin:0">For a life-threatening emergency, call 911. Tell any lift operator or employee, and they will radio patrol.</p>
        <div class="call-grid"><a class="btn block" href="tel:911">Call 911</a>
          <a class="btn secondary block" href="${esc(r.site)}" target="_blank" rel="noopener">Resort safety info</a></div>
        <p class="small muted" style="margin:0">Snow Desk doesn't list ${esc(r.name)}'s patrol numbers yet.</p>
      </section>${tell}`;
    return `
      <section class="card patrol" aria-labelledby="h-patrol">
        <h2 id="h-patrol">Call ${esc(r.name)} Ski Patrol</h2>
        <p style="margin:0">For an injury or emergency on the mountain:</p>
        <span class="number">${esc(p.emergency)}</span>
        <div class="call-grid">
          <a class="btn block" href="${tel(p.emergency)}">Call Ski Patrol now</a>
          <button class="btn secondary block" type="button" data-copy="${esc(p.emergency.replace(/[()]/g, "").replace(" ", "-"))}">Copy number</button>
        </div>
        <p class="small muted" style="margin:0">For a life-threatening emergency, call 911.</p>
      </section>
${tell}
      <section class="card">
        <h2>Other numbers</h2>
        ${p.non_emergency ? `<div class="contact"><span>Ski Patrol, non-emergency</span><a class="n" href="${tel(p.non_emergency)}">${esc(p.non_emergency)}</a></div>` : ""}
        ${p.security ? `<div class="contact"><span>${esc(r.name)} Security</span><a class="n" href="${tel(p.security)}">${esc(p.security)}</a></div>` : ""}
        <div class="contact"><span>Emergency</span><a class="n" href="tel:911">911</a></div>
        <p class="small muted" style="margin:0">Numbers from ${esc(r.name)}'s Safety on the Mountain page${p.checked ? `, checked ${esc(p.checked)}` : ""}. Save them in your phone before you ski.</p>
      </section>`;
  }

  // Which resorts' reports to get (email and app notifications). Starts with the one on screen.
  function resortPicks(name) {
    if (R.list.length < 2) return "";
    return `<fieldset class="resort-picks"><legend class="label">Resorts</legend>${R.list.map((r) =>
      `<label><input type="checkbox" name="${name}" value="${r.slug}"${r.slug === R.slug ? " checked" : ""}> ${esc(r.name)}</label>`).join("")}</fieldset>`;
  }
  const picked = (v, name) => { const a = [...v.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value); return a.length ? a : [R.slug]; };

  function viewHelp() {
    const v = document.createElement("div");
    v.className = "view v-help";
    const c = S.cfg || {};
    const q = new URLSearchParams(location.search).get("email");
    const notice = q === "confirmed" ? `<p class="offline" role="status">You're subscribed. The report arrives at 7:00 each morning.</p>`
      : q === "invalid" ? `<p class="offline" role="status">That confirmation link didn't work. Sign up again below.</p>` : "";
    v.innerHTML = `
      ${patrolCards()}

      <section class="card">
        <h2 id="alerts">Get the 7:00 report</h2>
        ${notice}
        <form id="email-form" class="signup" novalidate>
          <label for="email-input" class="label">Email, every morning</label>
          ${resortPicks("email-resort")}
          <div class="signup-row">
            <input id="email-input" type="email" inputmode="email" autocomplete="email" placeholder="you@example.com" required>
            <input type="text" name="website" id="website" tabindex="-1" autocomplete="off" aria-hidden="true" class="hp">
            <button class="btn" type="submit">Sign up</button>
          </div>
          <p class="small muted" id="email-msg" style="margin:0">We'll send one confirmation email first. Every report has a one-tap unsubscribe.</p>
        </form>
        <div class="signup">
          <span class="label">App notifications</span>
          ${resortPicks("push-resort")}
          <div class="signup-row"><span class="small" id="push-state" style="flex:1">Checking…</span><button class="btn secondary" type="button" id="push-btn" hidden>Turn on</button></div>
          <p class="small muted" id="push-hint" style="margin:0"></p>
        </div>
      </section>

      <section class="card">
        <h2>About the numbers</h2>
        <p class="small" style="margin:0">Grooming comes from the resort's nightly grooming map. Snow totals come from the resort's report, or the ${esc(resortInfo().snotel || "nearest")} SNOTEL station when the resort hasn't reported. The forecast blends public weather models and the National Weather Service, checked every day against what actually fell. Cams are the resort's own.</p>
      </section>`;
    wireEmailForm(v);
    wirePush(v);
    v.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = "Copied"; } catch (e) { b.textContent = b.dataset.copy; }
    }));
    return v;
  }

  /* ---------------- theme sheet ---------------- */
  function showThemes() {
    const curM = currentMaterial();
    openSheet("Look", `<h3>Finish</h3><div class="seg" style="grid-template-columns:repeat(5,1fr)">${MATERIALS.map((m) =>
      `<button type="button" data-material-id="${m.id}" aria-pressed="${m.id === curM}" title="${m.mood}">${m.name}</button>`).join("")}</div>
      <p class="small muted">Colors follow your phone: light by day, dark in dark mode.</p>`,
    (ov) => {
      ov.querySelectorAll("[data-material-id]").forEach((b) => b.addEventListener("click", () => {
        applyMaterial(b.dataset.materialId);
        ov.querySelectorAll("[data-material-id]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      }));
    });
  }
  $("#theme-btn").addEventListener("click", showThemes);
  document.addEventListener("click", (e) => { const g = e.target.closest("[data-goto]"); if (g) S.goto = g.dataset.goto; });

  /* ---------------- routing ---------------- */
  const VIEWS = { today: viewToday, calendar: viewCalendar, forecast: viewForecast, help: viewHelp };
  let routing = 0;
  async function route() {
    const tab = (location.hash.slice(1) || "today");
    const name = VIEWS[tab] ? tab : "today";
    document.querySelectorAll(".tabbar a").forEach((a) => { if (a.dataset.tab === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    $("#subtitle").textContent = { today: S.latest ? fmtDay(S.latest.date) + " · Snow Desk" : "Chair 0: Snow Desk", calendar: "History", forecast: "Full forecast", help: "Help & ski patrol" }[name];
    const my = ++routing;
    const view = await VIEWS[name]();
    if (my !== routing) return;
    $("#tip").hidden = true;
    $("#main").replaceChildren(view);
    const ts = $("#top-status"), sl = view.querySelector(":scope > .status-line");
    if (ts) ts.innerHTML = sl ? sl.innerHTML : "";
    if (S.goto) { const t = document.getElementById(S.goto); S.goto = null; if (t) t.closest(".card").scrollIntoView({ block: "start" }); }
  }

  async function loadResortData() {
    S.latest = null; S.verification = null; S.months = {}; S.offline = false;
    S.cal = { mode: "month", month: null, sel: null };
    const latest = await getJSON("/data/latest.json", { fresh: true });
    S.latest = latest;
    if (!latest) {
      // Offline: the service worker may still have the last report.
      S.latest = await getJSON("/data/latest.json");
      S.offline = !!S.latest;
    }
    const slug = R.slug;
    getJSON("/data/verification.json").then((v) => { if (slug !== R.slug) return; S.verification = v; if ((location.hash || "#today") === "#forecast") route(); });
  }

  function wireResortSelect() {
    const sel = $("#resort-select"), h1 = $(".brand h1");
    if (!sel || R.list.length < 2) { if (h1) h1.textContent = resortInfo().name; return; }
    sel.innerHTML = R.list.map((r) => `<option value="${r.slug}">${esc(r.name)}</option>`).join("");
    sel.value = R.slug;
    sel.hidden = false; h1.hidden = true;
    sel.addEventListener("change", async () => {
      pickResort(sel.value);
      const u = new URL(location.href); u.searchParams.delete("resort"); history.replaceState(null, "", u);
      $("#main").innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;
      await loadResortData();
      route();
    });
  }

  async function boot() {
    applyTheme(currentTheme());
    applyMaterial(currentMaterial());
    const [list, cfg] = await Promise.all([getJSON("/resorts.json"), getJSON("/config.json")]);
    S.cfg = cfg;
    if (list?.resorts?.length) R.list = list.resorts;
    let saved = null;
    try { saved = localStorage.getItem("resort"); } catch (e) {}
    const linked = new URLSearchParams(location.search).get("resort");
    pickResort(linked || saved || DEFAULT_RESORT, !!linked);
    wireResortSelect();
    await loadResortData();
    route();
    window.addEventListener("hashchange", () => { window.scrollTo({ top: 0 }); route(); });
    if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  boot();
})();
