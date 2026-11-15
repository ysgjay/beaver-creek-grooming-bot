(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const parseDate = (s) => { const [y, m, d] = s.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
  const fmtDay = (s) => { const d = parseDate(s); return `${WD[d.getDay()]} ${MO[d.getMonth()]} ${d.getDate()}`; };
  const inches = (x) => (x == null ? "–" : (x >= 1 || x === 0 ? Math.round(x) : x.toFixed(1)) + '"');
  const hourLabel = (iso) => { const h = Number(iso.slice(11, 13)); return `${h % 12 || 12}${h < 12 ? "a" : "p"}`; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function getJSON(path) {
    try {
      const r = await fetch(path, { cache: "no-cache" });
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }

  let latest = null, index = null, verification = null, cfg = null;

  /* ---------- summary ---------- */
  function renderSummary(day) {
    const fc = day.forecast || {}, obs = day.observed || {}, resort = day.resort || {};
    const r24 = resort.last_24h_in ?? obs.snow_in;
    $("s-24h").textContent = inches(r24);
    $("s-24h-src").textContent = resort.last_24h_in != null ? "resort reported"
      : obs.snow_in != null ? "Vail Mtn SNOTEL" : "no report";
    $("s-15").textContent = inches(fc.next_1_5);
    $("s-610").textContent = inches(fc.next_6_10);
    const rg = (r) => (r ? `range ${inches(r[0])}–${inches(r[1])}` : " ");
    $("s-15-range").textContent = rg(fc.next_1_5_range);
    $("s-610-range").textContent = rg(fc.next_6_10_range);
    $("s-odds").textContent = fc.powder_odds_pct == null ? "–" : fc.powder_odds_pct + "%";

    const g = day.grooming || {};
    const chip = $("status-chip");
    chip.className = "chip " + (g.new_map ? "fresh" : "stale");
    chip.textContent = g.new_map ? "New grooming map" : "No new map today";
    $("updated").textContent = day.generated ? "Updated " + fmtDay(day.generated) + " " + day.generated.slice(11, 16) : "";
  }

  /* ---------- chart ---------- */
  function niceMax(v) {
    const steps = [2, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 48];
    return steps.find((s) => s >= v) || Math.ceil(v / 12) * 12;
  }

  function renderChart(day) {
    const fc = day.forecast || {}, days = fc.days || [];
    const el = $("chart");
    if (!days.length) { el.innerHTML = '<p class="muted">No forecast available.</p>'; return; }
    const W = 640, H = 230, L = 30, R = 8, T = 30, B = 44;
    const max = niceMax(Math.max(2, ...days.map((d) => d.high ?? d.snow)));
    const step = max <= 8 ? 2 : max <= 16 ? 4 : max <= 30 ? 6 : 12;
    const ph = H - T - B, pw = W - L - R, slot = pw / days.length;
    const bw = Math.min(24, slot * 0.55);
    const y = (v) => T + ph - (v / max) * ph;
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">`;
    for (let v = 0; v <= max; v += step) {
      s += `<line class="${v === 0 ? "axis" : "gridline"}" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`;
      s += `<text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    // 1-5 / 6-10 bands
    if (days.length > 5) {
      const xs = L + slot * 5;
      s += `<line class="gridline" x1="${xs}" x2="${xs}" y1="${T - 18}" y2="${H - B}"/>`;
      s += `<text class="band-label" x="${L + 2}" y="${T - 10}">Days 1–5 · ${inches(fc.next_1_5)}</text>`;
      s += `<text class="band-label" x="${xs + 6}" y="${T - 10}">Days 6–10 · ${inches(fc.next_6_10)}</text>`;
    }
    days.forEach((d, i) => {
      const cx = L + slot * i + slot / 2;
      const top = y(d.snow), base = y(0);
      const h = base - top;
      if (d.high != null && d.low != null && d.high - d.low > 0.2) {
        s += `<line class="range" x1="${cx}" x2="${cx}" y1="${y(d.low)}" y2="${y(d.high)}"/>`;
        s += `<line class="range" x1="${cx - 4}" x2="${cx + 4}" y1="${y(d.high)}" y2="${y(d.high)}"/>`;
      }
      if (h >= 0.5) {
        const r = Math.min(4, h, bw / 2), x0 = cx - bw / 2, x1 = cx + bw / 2;
        s += `<path class="bar" data-i="${i}" d="M${x0},${base} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x1 - r} Q${x1},${top} ${x1},${top + r} V${base} Z"/>`;
      } else {
        s += `<line class="axis" x1="${cx - bw / 2}" x2="${cx + bw / 2}" y1="${base - 1}" y2="${base - 1}" style="stroke:var(--snow);stroke-width:2"/>`;
      }
      const labelY = Math.min(top, d.high != null ? y(d.high) : top) - 6;
      s += `<text class="val" x="${cx}" y="${labelY}" text-anchor="middle">${d.snow >= 0.5 ? Math.round(d.snow) : "0"}</text>`;
      const dt = parseDate(d.date), wkend = dt.getDay() === 0 || dt.getDay() === 6;
      s += `<text class="day-wk${wkend ? " weekend" : ""}" x="${cx}" y="${H - B + 18}" text-anchor="middle">${WD[dt.getDay()].slice(0, 2)}</text>`;
      s += `<text class="${wkend ? "weekend" : ""}" x="${cx}" y="${H - B + 34}" text-anchor="middle">${dt.getDate()}</text>`;
      s += `<rect class="hit" data-i="${i}" x="${L + slot * i}" y="${T - 20}" width="${slot}" height="${H - T - B + 54}" tabindex="0"/>`;
    });
    s += "</svg>";
    el.innerHTML = s;

    const tip = $("tip"), panel = el.closest(".panel"), labels = fc.model_labels || {};
    const show = (target) => {
      const i = Number(target.dataset.i), d = days[i];
      const models = Object.entries(d.models || {}).sort((a, b) => b[1] - a[1])
        .map(([m, v]) => `${esc(labels[m] || m)} ${inches(v)}`).join(" · ");
      tip.innerHTML = `<strong>${fmtDay(d.date)}: ${inches(d.snow)}</strong>` +
        (d.low != null ? `Likely ${inches(d.low)}–${inches(d.high)}<br>` : "") + `<span>${models}</span>`;
      tip.hidden = false;
      const pr = panel.getBoundingClientRect(), tr = target.getBoundingClientRect();
      const left = Math.max(8, Math.min(pr.width - tip.offsetWidth - 8, tr.left - pr.left + tr.width / 2 - tip.offsetWidth / 2));
      tip.style.left = left + "px";
      tip.style.top = (tr.top - pr.top - tip.offsetHeight + 16) + "px";
      el.querySelectorAll(".bar").forEach((b) => b.classList.toggle("active", b.dataset.i === String(i)));
    };
    const hide = () => { tip.hidden = true; el.querySelectorAll(".bar.active").forEach((b) => b.classList.remove("active")); };
    el.querySelectorAll(".hit").forEach((h) => {
      h.addEventListener("mouseenter", () => show(h));
      h.addEventListener("focus", () => show(h));
      h.addEventListener("click", () => show(h));
      h.addEventListener("mouseleave", hide);
      h.addEventListener("blur", hide);
    });
  }

  function renderModelsTable(day) {
    const fc = day.forecast || {}, days = fc.days || [], labels = fc.model_labels || {};
    const vm = (verification && verification.models) || {};
    const models = (fc.models_used || []).filter((m) => days.some((d) => d.models && d.models[m] != null));
    let h = "<thead><tr><th>Model</th>" + days.map((d) => `<th>${fmtDay(d.date).slice(0, 3)} ${parseDate(d.date).getDate()}</th>`).join("") +
      "<th>Weight ×</th><th>Bias ×</th></tr></thead><tbody>";
    h += `<tr class="blend"><td>Blend</td>` + days.map((d) => `<td class="num">${inches(d.snow)}</td>`).join("") + "<td></td><td></td></tr>";
    models.forEach((m) => {
      const st = vm[m] || {};
      h += `<tr><td>${esc(labels[m] || m)}</td>` + days.map((d) => `<td class="num">${d.models && d.models[m] != null ? inches(d.models[m]) : "·"}</td>`).join("") +
        `<td class="num">${(st.skill ?? 1).toFixed(2)}</td><td class="num">${(st.bias_ratio ?? 1).toFixed(2)}</td></tr>`;
    });
    $("models-table").innerHTML = h + "</tbody>";
    const n = fc.ensemble_members;
    $("models-note").textContent = `Values are already bias-corrected. Weight × and Bias × come from the last ${verification?.window_days ?? 45} days of scoring against SNOTEL (1.00 = not enough data yet).` +
      (n ? ` Range uses ${n} ensemble runs.` : "");
  }

  /* ---------- map ---------- */
  function renderMap(day) {
    const g = day.grooming || {};
    const img = $("map");
    if (g.image) {
      img.src = g.image;
      $("map-open").hidden = false;
      $("map-none").hidden = true;
      const mapDate = g.image.match(/(\d{4}-\d{2}-\d{2})/);
      $("map-date").textContent = mapDate ? "Posted " + fmtDay(mapDate[1]) : "";
    } else {
      $("map-open").hidden = true;
      $("map-none").hidden = false;
      $("map-date").textContent = "";
    }
  }
  $("map-open").addEventListener("click", () => {
    $("lightbox-img").src = $("map").src;
    $("lightbox").hidden = false;
    $("lightbox-close").focus();
  });
  const closeLb = () => { $("lightbox").hidden = true; $("map-open").focus(); };
  $("lightbox-close").addEventListener("click", closeLb);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("lightbox").hidden) closeLb(); });

  /* ---------- hourly ---------- */
  function renderHourly(day) {
    const hr = day.hourly || {}, hours = hr.hours || [];
    const labels = (day.forecast && day.forecast.model_labels) || {};
    $("hourly-model").textContent = hr.model ? "Model: " + (labels[hr.model] || hr.model) : "";
    if (!hours.length) { $("hourly").innerHTML = '<tbody><tr><td class="muted">No hourly data.</td></tr></tbody>'; return; }
    const row = (name, fn) => `<tr><th scope="row">${name}</th>${hours.map((h) => `<td>${fn(h)}</td>`).join("")}</tr>`;
    $("hourly").innerHTML = "<thead>" + row("", (h) => hourLabel(h.time)).replace(/<td>/g, "<th>").replace(/<\/td>/g, "</th>") + "</thead><tbody>" +
      row("Temp °F", (h) => h.temp ?? "–") +
      row("Feels", (h) => h.feels ?? "–") +
      row("Wind mph", (h) => `${h.dir} ${h.wind ?? "–"}`) +
      row("Gust", (h) => h.gust ?? "–") +
      row("Snow", (h) => (h.snow ? h.snow + '"' : "–")) +
      row("Cloud %", (h) => h.cloud ?? "–") + "</tbody>";
  }

  /* ---------- verification ---------- */
  function renderVerify() {
    const hist = (verification && verification.history) || [];
    $("verify-station").textContent = verification?.station ? "Ground truth: SNOTEL " + verification.station.split(":")[0] : "";
    if (!hist.length) { $("verify").hidden = true; $("verify-empty").hidden = false; return; }
    $("verify").hidden = false; $("verify-empty").hidden = true;
    const rows = hist.slice(-14).reverse().map((h) => {
      const inRange = h.observed >= h.low - 0.5 && h.observed <= h.high + 0.5;
      return `<tr><td>${fmtDay(h.date)}</td><td class="num">${inches(h.forecast)}</td><td class="num muted">${inches(h.low)}–${inches(h.high)}</td>` +
        `<td class="num ${inRange ? "hit" : "miss"}">${inches(h.observed)}</td></tr>`;
    }).join("");
    $("verify").innerHTML = "<thead><tr><th>Day</th><th>Forecast (day before)</th><th>Range</th><th>Fell</th></tr></thead><tbody>" + rows + "</tbody>";
  }

  /* ---------- cams ---------- */
  function renderCams(day) {
    const cams = (cfg && cfg.cams) || [];
    const items = cams.map((u, i) => ({ src: u, cap: i === 0 ? "Snow stake (live)" : `Cam ${i + 1}` }));
    if (day.cam) items.unshift({ src: day.cam, cap: "Stake at report time" });
    $("cams-panel").hidden = !items.length;
    $("cams").innerHTML = items.map((c) => `<figure><img src="${esc(c.src)}" alt="${esc(c.cap)}" loading="lazy"><figcaption>${esc(c.cap)}</figcaption></figure>`).join("");
  }

  /* ---------- archive ---------- */
  function renderArchive(current) {
    const days = (index && index.days) || [];
    $("archive").innerHTML = days.map((d) =>
      `<li class="${d.date === current ? "current" : ""}"><a href="#day-${d.date}"><span><span class="dot${d.new_map ? "" : " none"}"></span>${fmtDay(d.date)}</span>` +
      `<span class="meta">${d.resort_24h ?? d.snow_24h ?? 0}" fell · ${inches(d.next_1_5)} next 5d</span></a></li>`).join("") ||
      '<li class="muted small">The archive fills in one report per day.</li>';
  }

  /* ---------- subscribe ---------- */
  function renderSubscribe() {
    const c = cfg || {};
    const cards = [];
    if (c.ntfy_topic) {
      const url = `${(c.ntfy_server || "https://ntfy.sh").replace(/\/$/, "")}/${c.ntfy_topic}`;
      cards.push(`<div class="sub-card"><h3>Phone notifications</h3><p>Free, no phone number needed. Install the ntfy app (iPhone or Android), tap +, and subscribe to this topic:</p><code>${esc(c.ntfy_topic)}</code><a class="btn" href="${esc(url)}" target="_blank" rel="noopener">Open in ntfy</a></div>`);
    }
    if (c.telegram) cards.push(`<div class="sub-card"><h3>Telegram</h3><p>Join the channel for the map and forecast every morning.</p><a class="btn" href="${esc(c.telegram)}" target="_blank" rel="noopener">Join channel</a></div>`);
    if (c.signup_form) cards.push(`<div class="sub-card"><h3>Email</h3><p>Get the same report in your inbox.</p><a class="btn" href="${esc(c.signup_form)}" target="_blank" rel="noopener">Sign up</a></div>`);
    cards.push(`<div class="sub-card"><h3>Home screen</h3><p>On iPhone, tap Share, then Add to Home Screen to open this page like an app.</p></div>`);
    $("subscribe").innerHTML = cards.join("");
  }

  /* ---------- routing ---------- */
  async function show(dateStr) {
    let day = latest;
    const past = dateStr && latest && dateStr !== latest.date;
    if (past) day = (await getJSON(`data/days/${dateStr}.json`)) || latest;
    $("viewing-past").hidden = !past;
    if (past) $("viewing-date").textContent = fmtDay(dateStr);
    renderSummary(day);
    renderChart(day);
    renderModelsTable(day);
    renderMap(day);
    renderHourly(day);
    renderCams(day);
    renderArchive(day.date);
  }
  const route = () => {
    const m = location.hash.match(/^#day-(\d{4}-\d{2}-\d{2})$/);
    show(m ? m[1] : null);
    if (m) window.scrollTo({ top: 0 });
  };

  async function boot() {
    [latest, index, verification, cfg] = await Promise.all([
      getJSON("data/latest.json"), getJSON("data/index.json"), getJSON("data/verification.json"), getJSON("config.json"),
    ]);
    if (!latest) {
      $("status-chip").textContent = "No data yet";
      return;
    }
    renderVerify();
    renderSubscribe();
    route();
    window.addEventListener("hashchange", route);
  }
  boot();
})();
