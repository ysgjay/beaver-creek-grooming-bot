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
  const fmtDay = (s) => { const d = pd(s); return `${WD[d.getDay()]} ${MO[d.getMonth()]} ${d.getDate()}`; };
  const inch = (x) => (x == null ? "–" : (x >= 1 || x === 0 ? Math.round(x) : x.toFixed(1)) + '"');
  const hourLabel = (t) => { const h = Number(t.slice(11, 13)); return `${h % 12 || 12}${h < 12 ? "a" : "p"}`; };
  const todayIso = () => iso(new Date());

  async function getJSON(path, { fresh = false } = {}) {
    try {
      const r = await fetch(path, { cache: fresh ? "no-cache" : "default" });
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }

  /* ---------------- themes ---------------- */
  const THEMES = [
    { id: "auto", name: "Match phone", mood: "Corduroy by day, Night Cat in dark mode", bg: "#eef2f5", ac: "#0e1a2b" },
    { id: "corduroy", name: "Corduroy", mood: "Fresh-groomed at first chair", bg: "#eef2f5", ac: "#2f6fa8", font: "Barlow+Condensed:wght@700" },
    { id: "trailsign", name: "Trail Sign", mood: "Enamel signage, blunt and legible", bg: "#f4f4f0", ac: "#1b7a3e", font: "Overpass:wght@800" },
    { id: "patrol", name: "Patrol", mood: "Red jacket, white cross", bg: "#f3f5f6", ac: "#c8102e", font: "Archivo:wght@800" },
    { id: "alpenglow", name: "Alpenglow", mood: "Last pink light on the Gore Range", bg: "#2b1f2a", ac: "#ff8e72", font: "Bricolage+Grotesque:wght@700" },
    { id: "beacon", name: "Beacon", mood: "Transceiver yellow, glove-proof", bg: "#f6c915", ac: "#0b4f9e", font: "Chakra+Petch:wght@700" },
    { id: "liftticket", name: "Lift Ticket", mood: "Thermal print with a day-glow stripe", bg: "#ffffff", ac: "#d6006e", font: null },
    { id: "nightcat", name: "Night Cat", mood: "Snowcat headlights at 3 a.m.", bg: "#0e1a2b", ac: "#ffb52e", font: "Saira+Condensed:wght@700" },
    { id: "amberlens", name: "Amber Lens", mood: "Flat-light goggle tint", bg: "#3a2410", ac: "#ff9a1f", font: "Barlow:wght@700" },
    { id: "bluebird", name: "Bluebird", mood: "Cloudless morning after a storm", bg: "#dcebfa", ac: "#0a5bd3", font: "Outfit:wght@700" },
    { id: "glade", name: "Glade", mood: "Spruce shade and low sun", bg: "#12261e", ac: "#f2c14e", font: "Bitter:wght@700" },
  ];
  const loadedFonts = new Set(["Outfit:wght@700"]);
  function applyTheme(id) {
    const t = THEMES.find((x) => x.id === id) || THEMES[0];
    if (t.id === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t.id;
    if (t.font && !loadedFonts.has(t.font)) {
      loadedFonts.add(t.font);
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = `https://fonts.googleapis.com/css2?family=${t.font}&display=swap`;
      document.head.appendChild(l);
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#eef2f5";
    try { localStorage.setItem("theme", t.id); } catch (e) {}
  }
  function currentTheme() { try { return localStorage.getItem("theme") || "bluebird"; } catch (e) { return "bluebird"; } }
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
  const groomedRuns = (r) => r ? [...(r.featured || []), ...(r.overnight || []), ...(r.morning || [])] : [];

  /* ---------------- shared pieces ---------------- */
  function runsBlock(runs) {
    if (!runs) return "";
    const groups = [["Groomers of the day", runs.groomers_of_the_day || runs.featured, "featured"],
      ["Groomed overnight", runs.overnight, ""], ["Morning grooming", runs.morning, ""]].filter(([, l]) => l && l.length);
    if (!groups.length) return `<p class="muted small">No run names listed on this map.</p>`;
    return `<div class="runs">${groups.map(([t, l, cls]) =>
      `<div><h3>${t}</h3><ul class="chips ${cls}">${l.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>`).join("")}</div>`;
  }

  /* ---------------- chart kit ----------------
     Every chart is a draw(width) -> [height, svgBody] function, mounted responsively.
     Elements with data-tip show a tooltip on hover, focus or tap. */
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
    };
    requestAnimationFrame(render);
    new ResizeObserver(render).observe(el);
    return el;
  }
  const niceMax = (v) => [2, 4, 6, 8, 12, 16, 24, 36, 48].find((n) => n >= v) || 60;
  const dayTick = (d) => { const dt = pd(d); return { wk: dt.getDay() === 0 || dt.getDay() === 6, label: `${WD[dt.getDay()][0]}${dt.getDate()}` }; };
  const val = (x) => (x >= 1 ? Math.round(x) : x >= 0.1 ? x.toFixed(1) : "0");
  const dayLabels = (dates, x, y) => dates.map((d, i) => { const t = dayTick(d); return `<text class="${t.wk ? "wk" : ""}" x="${x(i)}" y="${y}" text-anchor="middle">${t.label}</text>`; }).join("");

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
        s += `<text class="${k.wk ? "wk" : ""}" x="${x + cw / 2}" y="53" text-anchor="middle">${k.label}</text>`;
      });
      return [58, s];
    }, "10-day snowfall, one cell per day");
  }

  // Forecast: each day is a snow stake. Solid = expected; hatched = how much more it could
  // reach (the upper estimate), capped by a dashed line and labeled; notch = low end.
  function stakeChart(days) {
    return mountChart((W) => {
      const H = 220, L = 24, T = 18, B = 24, ph = H - T - B, slot = (W - L) / days.length, sw = Math.min(24, slot * 0.58);
      const max = niceMax(Math.max(4, ...days.map((d) => d.high ?? d.snow))), y = (v) => T + ph - (v / max) * ph, step = max / 4;
      let s = `<defs><pattern id="over" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--accent-soft)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--accent)" stroke-width="2" opacity=".55"/></pattern></defs>`;
      for (let v = 0; v <= max; v += step) s += `<line class="grid" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" opacity=".6"/><text x="${L - 5}" y="${y(v) + 4}" text-anchor="end">${v}"</text>`;
      days.forEach((d, i) => {
        const cx = L + slot * i + slot / 2, x0 = cx - sw / 2, hi = d.high ?? d.snow, lo = d.low ?? d.snow;
        s += `<rect x="${x0}" y="${T}" width="${sw}" height="${ph}" rx="3" fill="var(--surface-2)" stroke="var(--line)" stroke-width="1.2"/>`;
        for (let v = 1; v < max; v++) { const major = v % step === 0; if (max > 24 && !major && v % 2) continue;
          s += `<line x1="${x0}" x2="${x0 + (major ? sw : sw * 0.32)}" y1="${y(v)}" y2="${y(v)}" stroke="var(--ink-2)" stroke-width="${major ? 1 : 0.7}" opacity="${major ? 0.55 : 0.4}"/>`; }
        if (hi - d.snow >= 0.2) {
          s += `<rect x="${x0 + 1}" y="${y(hi)}" width="${sw - 2}" height="${y(d.snow) - y(hi)}" fill="url(#over)"/>`;
          s += `<line x1="${x0 - 2}" x2="${x0 + sw + 2}" y1="${y(hi)}" y2="${y(hi)}" stroke="var(--accent)" stroke-width="1.6" stroke-dasharray="3 2"/>`;
          s += `<text x="${cx}" y="${y(hi) - 4}" text-anchor="middle" style="fill:var(--accent);font-weight:600">${val(hi)}</text>`;
        }
        if (d.snow > 0.05) s += `<path d="M${x0 + 1},${y(0)}V${y(d.snow) + 3}q${sw / 4},-4 ${sw / 2 - 1},-1q${sw / 4},3 ${sw / 2 - 1},-1V${y(0)}Z" fill="var(--snow-fill)" stroke="var(--accent)" stroke-width="1.2"/>`;
        if (lo < d.snow - 0.2) s += `<path d="M${x0 + sw},${y(lo)}l5,-3.5v7Z" fill="var(--ink)"/>`;
        s += `<text class="val" x="${cx}" y="${Math.min(y(0) - 4, y(d.snow) + 13)}" text-anchor="middle" style="font-weight:600">${d.snow >= 0.1 ? val(d.snow) : ""}</text>`;
        s += `<rect x="${cx - slot / 2}" y="0" width="${slot}" height="${H}" fill="transparent" tabindex="0" data-tip="${fmtDay(d.date)}: ${inch(d.snow)} expected. Low end ${inch(lo)}, could reach ${inch(hi)}"/>`;
      });
      return [H, s + dayLabels(days.map((d) => d.date), (i) => L + slot * i + slot / 2, H - 5)];
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
        s += `<text class="val" x="${x(n - 1)}" y="${y(e.total) - 8}" text-anchor="end">${inch(e.total)} by ${fmtDay(e.date).slice(0, 3)} ${pd(e.date).getDate()}</text>`;
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

  /* ---------------- TODAY ---------------- */
  function viewToday() {
    const L = S.latest;
    const v = document.createElement("div");
    v.className = "view";
    if (!L) { v.innerHTML = `<p class="offline">The morning report isn't available yet. Check your connection and try again.</p>`; return v; }
    const g = L.grooming || {}, fc = L.forecast || {}, obs = L.observed || {}, rs = L.resort || {};
    const r24 = rs.last_24h_in ?? obs.snow_in;
    const isToday = L.date === todayIso();
    const now = (L.hourly?.hours || [])[0];

    const sentAt = L.delivery?.sent_at ? L.delivery.sent_at.slice(11, 16) : null;
    v.innerHTML = `
      ${S.offline ? `<p class="offline">You're offline. Showing the report saved on ${fmtDay(L.date)}.</p>` : ""}
      <div class="status-line">
        <span class="pill ${g.new_map ? "" : "quiet"}">${g.new_map ? "New grooming report" : "No new grooming report yet"}</span>
        <span>${sentAt ? `Sent ${sentAt}` : `Updated ${isToday ? "" : fmtDay(L.date) + " "}${(L.generated || "").slice(11, 16)}`}</span>
        ${rs.updated_time ? `<span>· Snow report ${esc(rs.updated_time)}</span>` : ""}
      </div>

      <section class="card" aria-label="Conditions">
        <div class="cond">
          <div><span class="label">New 24h</span><span class="big">${inch(r24)}</span></div>
          <div><span class="label">Base</span><span class="mid">${inch(rs.base_in)}</span><span class="sub">Season ${inch(rs.season_in)}</span></div>
          <div><span class="label">Now</span><span class="mid">${now ? now.temp + "°" : "–"}</span><span class="sub">${now ? `Feels ${now.feels}°` : ""}</span></div>
          <div><span class="label">Wind</span><span class="mid">${now ? now.wind : "–"}</span><span class="sub">${now ? `${esc(now.dir)} g${now.gust ?? "–"}` : ""}</span></div>
        </div>
        ${now ? `<div class="hours">${L.hourly.hours.slice(1).map((h) => `<div class="hour"><span class="t">${hourLabel(h.time)}</span><span class="temp">${h.temp}°</span><span class="small">${esc(h.dir)} ${h.wind}</span>${h.snow ? `<span class="num small">${h.snow}"</span>` : ""}</div>`).join("")}</div>` : ""}
      </section>

      <section class="card" aria-labelledby="h-groom">
        <div class="card-head"><h2 id="h-groom">Grooming</h2><span class="muted small">${g.runs?.map_date ? esc(g.runs.map_date) : ""}</span></div>
        <div class="groom">
          ${g.image ? `<button class="map-btn" type="button" id="map-open" aria-label="Open the grooming map full size"><img src="/${esc(g.image)}" alt="Beaver Creek grooming map" decoding="async"></button>` : `<p class="muted">No grooming map yet.</p>`}
          ${runsBlock(g.runs)}
        </div>
      </section>

      <section class="card" aria-labelledby="h-fc">
        <div class="card-head"><h2 id="h-fc">Snow forecast</h2><a class="link" href="#forecast">Full forecast</a></div>
        <div class="status-line"><span>Next 5 days <strong class="num">${inch(fc.next_1_5)}</strong>${fc.next_1_5_range ? ` (likely ${inch(fc.next_1_5_range[0])}–${inch(fc.next_1_5_range[1])})` : ""}</span><span>· Days 6–10 <strong class="num">${inch(fc.next_6_10)}</strong></span></div>
        <div id="fc-mini"></div>
      </section>

      <section class="card" aria-labelledby="h-cam">
        <div class="card-head"><h2 id="h-cam">Snow stake</h2><span class="muted small">Tap to switch cams</span></div>
        <div id="cams"></div>
      </section>
      <a class="btn secondary block" href="#help" data-goto="alerts">Get this report at 7:00 by email or notification</a>`;

    if (fc.days?.length) $("#fc-mini", v).appendChild(heatStrip(fc.days));
    const mb = $("#map-open", v);
    if (mb) mb.addEventListener("click", () => openLightbox("/" + g.image, "Grooming map"));
    renderCams($("#cams", v), L);
    return v;
  }

  function renderCams(el, L) {
    const cams = (S.cfg?.cams || []).slice();
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
    v.className = "view";
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
      card.innerHTML = `
        <div class="month-nav"><button type="button" data-ym="${prevYm}" aria-label="Previous month">‹</button><h2>${MONTH_FULL[m - 1]} ${y}</h2><button type="button" data-ym="${nextYm}" aria-label="Next month">›</button></div>
        <div class="stats">${statTiles}</div>
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
        <div class="card-head" style="margin-top:4px"><h3>Snowfall so far in ${MONTH_FULL[m - 1]}</h3><span class="muted small">dashed = forecast</span></div>
        <div id="accum"></div>`;
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
    el.className = "card";
    el.innerHTML = `
      <div class="month-nav"><button type="button" data-step="-1" aria-label="Previous day">‹</button><h2>${fmtDay(d)}</h2><button type="button" data-step="1" aria-label="Next day">›</button></div>
      <div class="snow-grid">
        <div><span class="label">New snow</span><span class="big">${inch(morningSnow(d))}</span></div>
        <div><span class="label">Base</span><span class="mid">${inch(r.base_in)}</span></div>
        <div><span class="label">Forecast then</span><span class="mid">${inch(r.next_1_5)}</span><span class="sub">next 5 days</span></div>
      </div>
      ${r.map ? `<button class="map-btn" type="button" data-map="${esc(r.map)}"><img src="/${esc(r.map)}" alt="Grooming map for ${fmtDay(d)}" loading="lazy"></button>` : `<p class="muted small">No grooming map saved for this day.</p>`}
      ${runsBlock({ groomers_of_the_day: r.featured, overnight: r.overnight, morning: r.morning })}
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

  /* ---------------- FORECAST ---------------- */
  function viewForecast() {
    const v = document.createElement("div");
    v.className = "view";
    const fc = S.latest?.forecast || {}, days = fc.days || [], labels = fc.model_labels || {};
    const vm = S.verification?.models || {};
    const hist = (S.verification?.history || []).slice(-10).reverse();
    v.innerHTML = `
      <section class="card">
        <div class="card-head"><h2>10-day snowfall</h2><span class="muted small">Blended from ${(fc.models_used || []).length} models</span></div>
        <div class="snow-grid">
          <div><span class="label">Days 1–5</span><span class="big">${inch(fc.next_1_5)}</span><span class="sub">${fc.next_1_5_range ? `likely ${inch(fc.next_1_5_range[0])}–${inch(fc.next_1_5_range[1])}` : ""}</span></div>
          <div><span class="label">Days 6–10</span><span class="mid">${inch(fc.next_6_10)}</span><span class="sub">${fc.next_6_10_range ? `${inch(fc.next_6_10_range[0])}–${inch(fc.next_6_10_range[1])}` : ""}</span></div>
          <div><span class="label">6"+ day odds</span><span class="mid">${fc.powder_odds_pct == null ? "–" : fc.powder_odds_pct + "%"}</span><span class="sub">next 5 days</span></div>
        </div>
        <div id="fc-chart"></div>
        <div class="legend"><span><i style="background:var(--snow-fill);border:1px solid var(--accent)"></i>Expected</span><span><i class="hatch"></i>Could reach (upper estimate)</span><span><i style="background:none;border-left:6px solid var(--ink);border-top:4px solid transparent;border-bottom:4px solid transparent;width:0;height:0;border-radius:0"></i>Low end</span></div>
      </section>

      <section class="card">
        <div class="card-head"><h2>Model votes</h2><span class="muted small">${(fc.models_used || []).length} models</span></div>
        <div id="fc-votes"></div>
        <div class="legend"><span><i style="background:var(--ink);opacity:.72;border-radius:50%"></i>One model's call</span><span><i style="background:var(--accent);height:4px;border-radius:2px"></i>Blend</span><span>Tight cluster = models agree</span></div>
      </section>

      <section class="card">
        <h2>Next 12 hours</h2>
        <div class="scroll"><table><thead><tr><th>Hour</th><th>Temp</th><th>Feels</th><th>Wind</th><th>Gust</th><th>Snow</th><th>Cloud</th></tr></thead><tbody>
          ${(S.latest?.hourly?.hours || []).map((h) => `<tr><td>${hourLabel(h.time)}</td><td>${h.temp}°</td><td>${h.feels}°</td><td>${esc(h.dir)} ${h.wind}</td><td>${h.gust ?? "–"}</td><td>${h.snow ? h.snow + '"' : "–"}</td><td>${h.cloud}%</td></tr>`).join("")}
        </tbody></table></div>
      </section>

      <section class="card">
        <details><summary>Every model, day by day</summary>
          <div class="scroll"><table><thead><tr><th>Model</th>${days.map((d) => `<th>${WD[pd(d.date).getDay()]} ${pd(d.date).getDate()}</th>`).join("")}<th>Weight ×</th></tr></thead><tbody>
            <tr><td><strong>Blend</strong></td>${days.map((d) => `<td><strong>${inch(d.snow)}</strong></td>`).join("")}<td></td></tr>
            ${(fc.models_used || []).map((m) => `<tr><td>${esc(labels[m] || m)}</td>${days.map((d) => `<td>${d.models?.[m] != null ? inch(d.models[m]) : "·"}</td>`).join("")}<td>${(vm[m]?.skill ?? 1).toFixed(2)}</td></tr>`).join("")}
          </tbody></table></div>
        </details>
        <details><summary>How the forecast is built</summary>
          <ol class="steps">
            <li>Seven public weather models (NOAA's GFS, HRRR and National Blend, ECMWF, ICON, GEM, UKMO) for this exact spot, with temperature corrected to 10,476 ft. The NWS forecasters' snowfall joins as an eighth voice.</li>
            <li>Liquid precipitation becomes snow with a temperature-based ratio tuned for dry Colorado snow, about 15 to 1 in the teens.</li>
            <li>Every model is scored daily against the Vail Mountain SNOTEL gauge. Models that run dry here are scaled up, and models that keep missing get less weight.</li>
            <li>High-resolution models lead for 48 hours, global models after that. Ensemble runs give the range and the powder odds.</li>
          </ol>
        </details>
        <details><summary>Forecast vs. what fell</summary>
          ${hist.length ? `<div class="scroll"><table><thead><tr><th>Day</th><th>Forecast</th><th>Range</th><th>Fell</th></tr></thead><tbody>${hist.map((h) => `<tr><td>${fmtDay(h.date)}</td><td>${inch(h.forecast)}</td><td>${inch(h.low)}–${inch(h.high)}</td><td>${inch(h.observed)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="muted small">Scores appear after a few days of forecasts are saved.</p>`}
        </details>
      </section>`;
    if (days.length) {
      $("#fc-chart", v).appendChild(stakeChart(days));
      $("#fc-votes", v).appendChild(votesChart(days, labels));
    }
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
        const r = await fetch("/api/subscribe", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, website: $("#website", v).value }) });
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
    const save = (sub) => fetch("/api/push", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sub.toJSON()) });
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
  function viewHelp() {
    const v = document.createElement("div");
    v.className = "view";
    const c = S.cfg || {};
    const q = new URLSearchParams(location.search).get("email");
    const notice = q === "confirmed" ? `<p class="offline" role="status">You're subscribed. The report arrives at 7:00 each morning.</p>`
      : q === "invalid" ? `<p class="offline" role="status">That confirmation link didn't work. Sign up again below.</p>` : "";
    v.innerHTML = `
      <section class="card patrol" aria-labelledby="h-patrol">
        <h2 id="h-patrol">Call Beaver Creek Ski Patrol</h2>
        <p style="margin:0">For an injury or emergency on the mountain:</p>
        <span class="number">(970) 754-6911</span>
        <div class="call-grid">
          <a class="btn block" href="tel:+19707546911">Call Ski Patrol now</a>
          <button class="btn secondary block" type="button" data-copy="970-754-6911">Copy number</button>
        </div>
        <p class="small muted" style="margin:0">For a life-threatening emergency, call 911.</p>
      </section>

      <section class="card">
        <h2>When you call, tell them</h2>
        <ol class="say">
          <li>The run name, or the nearest trail sign or lift tower number.</li>
          <li>What happened and how many people are hurt.</li>
          <li>Your phone number, and stay where patrol can find you.</li>
        </ol>
        <p class="small muted" style="margin:0">Cross your skis or board upright in the snow above the injured person so others can see you.</p>
      </section>

      <section class="card">
        <h2>Other numbers</h2>
        <div class="contact"><span>Ski Patrol, non-emergency</span><a class="n" href="tel:+19707546610">(970) 754-6610</a></div>
        <div class="contact"><span>Beaver Creek Security</span><a class="n" href="tel:+19707545848">(970) 754-5848</a></div>
        <div class="contact"><span>Emergency</span><a class="n" href="tel:911">911</a></div>
        <p class="small muted" style="margin:0">Numbers from Beaver Creek's Safety on the Mountain page, checked Nov 15, 2026. Save them in your phone before you ski.</p>
      </section>

      <section class="card">
        <h2 id="alerts">Get the 7:00 report</h2>
        ${notice}
        <form id="email-form" class="signup" novalidate>
          <label for="email-input" class="label">Email, every morning</label>
          <div class="signup-row">
            <input id="email-input" type="email" inputmode="email" autocomplete="email" placeholder="you@example.com" required>
            <input type="text" name="website" id="website" tabindex="-1" autocomplete="off" aria-hidden="true" class="hp">
            <button class="btn" type="submit">Sign up</button>
          </div>
          <p class="small muted" id="email-msg" style="margin:0">We'll send one confirmation email first. Every report has a one-tap unsubscribe.</p>
        </form>
        <div class="signup">
          <span class="label">App notifications</span>
          <div class="signup-row"><span class="small" id="push-state" style="flex:1">Checking…</span><button class="btn secondary" type="button" id="push-btn" hidden>Turn on</button></div>
          <p class="small muted" id="push-hint" style="margin:0"></p>
        </div>
      </section>

      <section class="card">
        <h2>About the numbers</h2>
        <p class="small" style="margin:0">Grooming comes from the resort's nightly grooming map. Snow totals come from the resort's report, or the Vail Mountain SNOTEL station when the resort hasn't reported. The forecast blends seven public weather models and the National Weather Service, checked every day against what actually fell. Cams are the resort's own.</p>
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
    const cur = currentTheme(), curM = currentMaterial();
    openSheet("Look", `<h3>Finish</h3><div class="seg" style="grid-template-columns:repeat(5,1fr)">${MATERIALS.map((m) =>
      `<button type="button" data-material-id="${m.id}" aria-pressed="${m.id === curM}" title="${m.mood}">${m.name}</button>`).join("")}</div>
      <h3>Colors</h3><div class="theme-grid">${THEMES.map((t) =>
      `<button class="theme-opt" type="button" data-theme-id="${t.id}" aria-pressed="${t.id === cur}"><span class="swatch" style="--sw-bg:${t.bg};--sw-ac:${t.ac}"></span><span><strong>${t.name}</strong><br><span class="small muted">${t.mood}</span></span></button>`).join("")}</div>`,
    (ov) => {
      ov.querySelectorAll("[data-theme-id]").forEach((b) => b.addEventListener("click", () => {
        applyTheme(b.dataset.themeId);
        ov.querySelectorAll("[data-theme-id]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      }));
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
    $("#subtitle").textContent = { today: S.latest ? fmtDay(S.latest.date) + " · Snow Desk" : "Snow Desk", calendar: "History", forecast: "Full forecast", help: "Help & ski patrol" }[name];
    const my = ++routing;
    const view = await VIEWS[name]();
    if (my !== routing) return;
    $("#tip").hidden = true;
    $("#main").replaceChildren(view);
    if (S.goto) { const t = document.getElementById(S.goto); S.goto = null; if (t) t.closest(".card").scrollIntoView({ block: "start" }); }
  }

  async function boot() {
    applyTheme(currentTheme());
    applyMaterial(currentMaterial());
    const [latest, cfg] = await Promise.all([getJSON("/data/latest.json", { fresh: true }), getJSON("/config.json")]);
    S.latest = latest; S.cfg = cfg;
    if (!latest) {
      // Offline: the service worker may still have the last report.
      S.latest = await getJSON("/data/latest.json");
      S.offline = !!S.latest;
    }
    route();
    window.addEventListener("hashchange", () => { window.scrollTo({ top: 0 }); route(); });
    getJSON("/data/verification.json").then((v) => { S.verification = v; if ((location.hash || "#today") === "#forecast") route(); });
    if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  boot();
})();
