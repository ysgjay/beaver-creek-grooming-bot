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
  const loadedFonts = new Set(["Barlow:wght@700"]);
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
  function currentTheme() { try { return localStorage.getItem("theme") || "amberlens"; } catch (e) { return "amberlens"; } }
  const MATERIALS = [
    { id: "flat", name: "Flat", mood: "Solid cards, the fastest" },
    { id: "glass", name: "Glass", mood: "Clear panes over an alpenglow ridge" },
    { id: "frost", name: "Frost", mood: "Frosted, grainy, like a cold window" },
    { id: "ice", name: "Ice", mood: "Crisp edges with a blue sheen" },
    { id: "powder", name: "Powder", mood: "Falling flakes, snow-capped cards" },
  ];
  function currentMaterial() { try { return localStorage.getItem("material") || "flat"; } catch (e) { return "flat"; } }
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

  function snowChart(days, { height = 200 } = {}) {
    const el = document.createElement("div");
    el.className = "chart";
    const draw = () => {
      const W = Math.max(280, Math.round(el.clientWidth || 600)), H = height, L = 26, R = 6, T = 22, B = 40;
      const max = [2, 4, 6, 8, 12, 16, 24, 36, 48].find((v) => v >= Math.max(2, ...days.map((d) => d.high ?? d.snow))) || 48;
      const step = max <= 8 ? 2 : max <= 16 ? 4 : max <= 24 ? 6 : 12;
      const ph = H - T - B, slot = (W - L - R) / days.length, bw = Math.min(24, slot * 0.55);
      const y = (v) => T + ph - (v / max) * ph;
      let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily snowfall forecast">`;
      for (let v = 0; v <= max; v += step) s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
      days.forEach((d, i) => {
        const cx = L + slot * i + slot / 2, top = y(d.snow), base = y(0), h = base - top;
        if (d.high != null && d.low != null && d.high - d.low > 0.2) {
          s += `<line class="range" x1="${cx}" x2="${cx}" y1="${y(d.low)}" y2="${y(d.high)}"/><line class="range" x1="${cx - 4}" x2="${cx + 4}" y1="${y(d.high)}" y2="${y(d.high)}"/>`;
        }
        if (h >= 0.5) {
          const r = Math.min(4, h, bw / 2), x0 = cx - bw / 2, x1 = cx + bw / 2;
          s += `<path class="bar" data-i="${i}" d="M${x0},${base}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x1 - r}Q${x1},${top} ${x1},${top + r}V${base}Z"/>`;
        } else s += `<line x1="${cx - bw / 2}" x2="${cx + bw / 2}" y1="${base - 1}" y2="${base - 1}" stroke="var(--snow)" stroke-width="2"/>`;
        const ly = Math.min(top, d.high != null ? y(d.high) : top) - 6;
        s += `<text class="val" x="${cx}" y="${ly}" text-anchor="middle">${d.snow >= 1 ? Math.round(d.snow) : d.snow >= 0.1 ? d.snow.toFixed(1) : "0"}</text>`;
        const dt = pd(d.date), wk = dt.getDay() === 0 || dt.getDay() === 6;
        s += `<text class="${wk ? "wk" : ""}" x="${cx}" y="${H - B + 17}" text-anchor="middle">${WD[dt.getDay()]}</text><text class="${wk ? "wk" : ""}" x="${cx}" y="${H - B + 33}" text-anchor="middle">${dt.getDate()}</text>`;
        s += `<rect class="hit" data-i="${i}" x="${L + slot * i}" y="0" width="${slot}" height="${H}" tabindex="0" aria-label="${fmtDay(d.date)}: ${inch(d.snow)}"/>`;
      });
      el.innerHTML = s + "</svg>";
      const tip = $("#tip"), labels = (S.latest?.forecast?.model_labels) || {};
      el.querySelectorAll(".hit").forEach((hit) => {
        const show = () => {
          const d = days[+hit.dataset.i];
          const models = Object.entries(d.models || {}).sort((a, b) => b[1] - a[1]).map(([m, v]) => `${esc(labels[m] || m)} ${inch(v)}`).join(" · ");
          tip.innerHTML = `<strong>${fmtDay(d.date)}: ${inch(d.snow)}</strong>${d.low != null ? `<br>Likely ${inch(d.low)}–${inch(d.high)}` : ""}${models ? `<br>${models}` : ""}`;
          tip.hidden = false;
          const r = hit.getBoundingClientRect();
          tip.style.left = Math.max(8, Math.min(innerWidth - tip.offsetWidth - 8, r.left + r.width / 2 - tip.offsetWidth / 2)) + "px";
          tip.style.top = Math.max(8, r.top + 4 - tip.offsetHeight) + "px";
          el.querySelectorAll(".bar").forEach((b) => b.classList.toggle("active", b.dataset.i === hit.dataset.i));
        };
        const hide = () => { tip.hidden = true; el.querySelectorAll(".bar.active").forEach((b) => b.classList.remove("active")); };
        hit.addEventListener("mouseenter", show); hit.addEventListener("focus", show); hit.addEventListener("click", show);
        hit.addEventListener("mouseleave", hide); hit.addEventListener("blur", hide);
      });
    };
    requestAnimationFrame(draw);
    new ResizeObserver(() => draw()).observe(el);
    return el;
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
      </section>`;

    if (fc.days?.length) $("#fc-mini", v).appendChild(snowChart(fc.days, { height: 140 }));
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
        <div class="legend"><span><i style="background:color-mix(in oklab, var(--snow) 50%, var(--surface))"></i>New snow that morning</span><span><i style="background:var(--accent);border-radius:50%"></i>Grooming report saved</span></div>`;
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
      ${r.cam ? `<div class="cam-main"><img src="/${esc(r.cam)}" alt="Snow stake on ${fmtDay(d)}" loading="lazy"><span class="cap">Snow stake</span></div>` : ""}`;
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
    const maxHigh = Math.max(1, ...days.map((d) => d.high ?? d.snow));
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
        <p class="muted small">Bars are the blend. The line shows the likely range from ${fc.ensemble_members || "ensemble"} model runs. Tap a day for each model's number.</p>
      </section>

      <section class="card">
        <h2>Day by day</h2>
        <div class="day-rows">${days.map((d) => `<div class="day-row"><span><strong>${WD[pd(d.date).getDay()]}</strong> <span class="muted">${pd(d.date).getDate()}</span></span>
          <span class="range-track" aria-hidden="true"><span class="r" style="left:${(d.low / maxHigh) * 100}%;width:${((d.high - d.low) / maxHigh) * 100}%"></span><span class="m" style="left:${(d.snow / maxHigh) * 100}%"></span></span>
          <span class="num" style="text-align:right">${inch(d.snow)}</span></div>`).join("")}</div>
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
    if (days.length) $("#fc-chart", v).appendChild(snowChart(days));
    return v;
  }

  /* ---------------- HELP ---------------- */
  function viewHelp() {
    const v = document.createElement("div");
    v.className = "view";
    const c = S.cfg || {};
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
        <h2>Get the report every morning</h2>
        ${c.ntfy_topic ? `<div class="contact"><span>Phone notifications (free ntfy app). Subscribe to <strong class="num">${esc(c.ntfy_topic)}</strong></span><a class="btn secondary" href="https://ntfy.sh/${esc(c.ntfy_topic)}" target="_blank" rel="noopener">Open</a></div>` : ""}
        ${c.telegram ? `<div class="contact"><span>Telegram channel</span><a class="btn secondary" href="${esc(c.telegram)}" target="_blank" rel="noopener">Join</a></div>` : ""}
        <p class="small muted" style="margin:0">On iPhone, tap Share, then Add to Home Screen to open Snow Desk like an app. It keeps the last report for when you lose signal.</p>
      </section>

      <section class="card">
        <h2>About the numbers</h2>
        <p class="small" style="margin:0">Grooming comes from the resort's nightly grooming map. Snow totals come from the resort's report, or the Vail Mountain SNOTEL station when the resort hasn't reported. The forecast blends seven public weather models and the National Weather Service, checked every day against what actually fell. Cams are the resort's own.</p>
      </section>`;
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
