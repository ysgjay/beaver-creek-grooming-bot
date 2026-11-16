/* Snow Audit page: reads /data/audit/<resort>.json (built by bcbot/audit.py) and the raw log
   from /api/audit. Dates are the resort's local days, shown as weekday over MM/DD. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const mmdd = (d) => `${d.slice(5, 7)}/${d.slice(8, 10)}`;
  const wd = (d) => WD[new Date(d + "T12:00:00Z").getUTCDay()];
  const dayCell = (d) => `<span class="day"><small>${wd(d)}</small>${mmdd(d)}</span>`;
  const narrow = () => matchMedia("(max-width: 699px)").matches;
  const GROUPS = { short: [0, 1], mid: [2, 4], long: [5, 9] };
  const GROUP_LABEL = { short: "Short", mid: "Mid", long: "Long" };
  const S = { slug: null, data: null, metric: "snow", kind: "live", sel: null, trail: 0, log: null, filters: {} };
  const unit = () => (S.metric === "snow" ? '"' : '" water');
  const fmt = (v) => (v == null ? "–" : S.metric === "snow" ? v.toFixed(1) : v.toFixed(2));
  const name = (k) => (S.data?.sources || []).find((s) => s.key === k)?.label || k;

  function acc(source, leads, kinds) {
    const a = new Array(11).fill(0);
    const src = S.data.agg?.[S.metric]?.[source] || {};
    for (const l of leads) for (const k of kinds) (src[String(l)]?.[k] || []).forEach((v, i) => (a[i] += v));
    return a;
  }
  const kinds = () => (S.kind === "both" ? ["live", "replay"] : ["live"]);

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // ---------- cards ----------
  function scoreboard() {
    const src = S.data.sources.map((s) => s.key).filter((k) => S.data.agg?.[S.metric]?.[k]);
    if (!src.length) return card("Scoreboard", "", `<p class="au-empty">${S.metric === "snow" ? "No graded snow days yet. Live calls are graded against the resort's report the morning after; the first ones land after the first snow." : "No graded days yet."}</p>`);
    let max = 0;
    const cells = {};
    // Phones: Short / Mid / Long columns; wider screens: every day ahead, 0 to 9.
    const cols = narrow() ? Object.entries(GROUPS).map(([g, [a, b]]) => ({ key: g, label: `${GROUP_LABEL[g]}<small>${a}–${b} days</small>`, leads: [...Array(b - a + 1).keys()].map((i) => i + a), what: `${GROUP_LABEL[g].toLowerCase()} range` }))
      : [...Array(10).keys()].map((l) => ({ key: String(l), label: String(l), leads: [l], what: `${l} days ahead` }));
    for (const k of src) for (const col of cols) {
      const a = acc(k, col.leads, kinds()), live = acc(k, col.leads, ["live"]);
      const mae = a[0] >= 3 ? a[1] / a[0] : null;
      cells[k + col.key] = { mae, n: a[0], live: live[0], rep: a[0] - live[0] };
      if (mae != null) max = Math.max(max, mae);
    }
    const head = `<tr><th class="src"></th>${cols.map((c) => `<th>${c.label}</th>`).join("")}${Object.keys(GROUPS).map((g) => `<th class="gr" title="${GROUP_LABEL[g]} range">${g[0].toUpperCase()}</th>`).join("")}</tr>`;
    const rows = src.map((k) => {
      const tds = cols.map((col) => {
        const c = cells[k + col.key], l = col.what;
        if (c.mae == null) return `<td class="c na" title="${c.n} days">·</td>`;
        const t = max ? c.mae / max : 0;
        const bg = `color-mix(in oklab, var(--snow) ${Math.round(12 + t * 78)}%, var(--frost-metric-soft))`;
        const rep = S.kind === "both" && c.live < 3 && c.rep > 0;
        return `<td class="c${t > 0.55 ? " dark" : ""}${rep ? " rep" : ""}" style="background-color:${bg}" title="${esc(name(k))}, ${l}: average miss ${fmt(c.mae)}${unit()} over ${c.live} live + ${c.rep} replay days">${fmt(c.mae)}</td>`;
      }).join("");
      const gr = Object.keys(GROUPS).map((g) => {
        const c = S.data.grades?.[S.metric]?.[k]?.[g] || {};
        if (c.grade && c.grade !== "New") return `<td><span class="grade" title="${GROUP_LABEL[g]}: ${c.n} live days, ${fmt(c.live_mae)}${unit()} average miss">${c.grade}</span></td>`;
        if (c.hint) return `<td><span class="grade hint hatch" title="New: ${c.n} live days. Replay suggests ${c.hint} (${c.n_replay} days)">${c.hint}</span></td>`;
        return `<td><span class="grade new" title="New: ${c.n || 0} live days so far">–</span></td>`;
      }).join("");
      return `<tr class="${k === "blend" ? "blend" : ""}${k === S.sel ? " sel" : ""}" data-src="${esc(k)}"><th class="src" title="${esc(name(k))}">${esc(name(k))}</th>${tds}${gr}</tr>`;
    }).join("");
    const legend = `<div class="legend-ramp"><span>Closer</span><i></i><span>Bigger miss</span>${S.kind === "both" ? `<span class="hatch"></span><span>mostly replay</span>` : ""}<span>· S M L = grades</span></div><p class="small muted au-note">Live = frozen ~2 AM calls. Replay = rebuilt from archived runs, water only.</p>`;
    return card("Scoreboard", `Average miss in ${S.metric === "snow" ? "inches of snow" : "inches of water"}${narrow() ? "" : ", by days ahead"}`,
      `<table class="sb${narrow() ? " groups" : ""}"><thead>${head}</thead><tbody>${rows}</tbody></table>${legend}`, "sb-card");
  }

  function biasStrip() {
    const src = S.data.sources.map((s) => s.key).filter((k) => k !== "mean" && S.data.agg?.[S.metric]?.[k]);
    const rows = src.map((k) => {
      const all = acc(k, [...Array(10).keys()], kinds());
      if (all[0] < 3 || !all[4]) return null;
      const gs = Object.values(GROUPS).map(([a, b]) => acc(k, [...Array(b - a + 1).keys()].map((i) => i + a), kinds())).filter((g) => g[0] >= 3 && g[4]).map((g) => g[3] / g[4]);
      return { k, r: all[3] / all[4], lo: Math.min(...gs), hi: Math.max(...gs), n: all[0] };
    }).filter(Boolean);
    if (!rows.length) return card("Runs dry or wet", "", `<p class="au-empty">Needs a few graded days first.</p>`);
    const W = 320, L = 92, R = 8, rowH = 16, H = rows.length * rowH + 22;
    const x = (r) => L + ((Math.log2(Math.min(2, Math.max(0.5, r))) + 1) / 2) * (W - L - R);
    const body = rows.map((o, i) => {
      const y = 14 + i * rowH;
      const rad = Math.min(6, 2.5 + Math.sqrt(o.n) / 3);
      return `<text x="0" y="${y + 3}" class="lbl">${esc(name(o.k)).slice(0, 18)}</text>
        <line class="whisk" x1="${x(o.lo)}" x2="${x(o.hi)}" y1="${y}" y2="${y}"/>
        <circle class="dot" cx="${x(o.r)}" cy="${y}" r="${rad}"><title>${esc(name(o.k))}: calls ${Math.round(o.r * 100)}% of what fell (${o.n} days)</title></circle>`;
    }).join("");
    const svg = `<svg class="au-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="How much each source runs dry or wet">
      <line class="zero" x1="${x(1)}" x2="${x(1)}" y1="4" y2="${H - 14}"/>
      ${body}
      <text x="${x(0.5)}" y="${H - 2}">½ (dry)</text><text x="${x(1) - 6}" y="${H - 2}">1</text><text x="${x(2) - 30}" y="${H - 2}">2× (wet)</text></svg>`;
    return card("Runs dry or wet", "Call ÷ what fell; the line shows short to long range", svg);
  }

  function ledger() {
    const st = S.data.storms || [];
    if (!S.data.resort || S.data.resort === "all") return "";
    if (!st.length) return card("Storm ledger", "", `<p class="au-empty">No snow days graded yet.</p>`);
    const rows = st.map((s) => {
      const fell = s.metric === "snow" ? `${s.resort.toFixed(1)}"` : `${s.snotel?.toFixed(2)}" w`;
      const c3 = s.call3 == null ? "–" : s.metric === "snow" ? `${s.call3.toFixed(1)}"` : `${s.call3.toFixed(2)}" w`;
      const who = (b) => (b ? `${esc(name(b[0]))}` : "–");
      return `<tr><td>${dayCell(s.date)}</td><td class="num">${fell}${s.kind === "replay" ? '<span class="rchip" title="Replay">R</span>' : ""}</td>
        <td class="num" title="${s.call3_source === "blend" ? "Our blend" : "Plain average"}, 3 days ahead">${c3}</td><td>${who(s.best)}</td><td class="worst">${who(s.worst)}</td>
        <td>${(s.flags || []).map((f) => `<span class="flag">${f}</span>`).join("")}</td></tr>`;
    }).join("");
    return card("Storm ledger", "Snow days: what fell, the call 3 days out, and the best and worst source the day before",
      `<div class="ledger-wrap"><table class="ledger"><thead><tr><th>Day</th><th class="num">Fell</th><th class="num">3 days out</th><th>Best</th><th class="worst">Worst</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`);
  }

  function trail() {
    const ts = S.data.trails || [];
    if (!S.data.resort || S.data.resort === "all") return "";
    if (!ts.length) return card("Call trail", "", `<p class="au-empty">Shows how each source's call for a storm moved as it got closer. It starts with the next storm of 2"+ in the live calls.</p>`);
    const t = ts[Math.min(S.trail, ts.length - 1)];
    const W = 320, H = 150, L = 26, B = 18, T = 8;
    const vals = Object.values(t.sources).flat().map((p) => p[1]).concat(t.truth ?? []);
    const maxY = Math.max(2, ...vals) * 1.1;
    const x = (lead) => L + ((9 - lead) / 9) * (W - L - 6);
    const y = (v) => T + (1 - v / maxY) * (H - T - B);
    const lines = Object.entries(t.sources).sort(([a], [b]) => (a === "blend") - (b === "blend")).map(([k, pts]) =>
      `<path class="ln${k === "blend" ? " blend" : ""}${k === S.sel ? " sel" : ""}" d="${pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")}"><title>${esc(name(k))}: ${pts.map((p) => `${p[0]}d ${p[1]}"`).join(", ")}</title></path>`).join("");
    const ticks = [9, 7, 5, 3, 1, 0].map((l) => `<text x="${x(l) - 3}" y="${H - 4}">${l}</text>`).join("");
    const yt = [0, Math.round(maxY / 2), Math.round(maxY)].map((v) => `<text x="0" y="${y(v) + 3}">${v}"</text><line class="axis" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" opacity=".4"/>`).join("");
    const truth = t.truth != null ? `<line class="truth" x1="${L}" x2="${W}" y1="${y(t.truth)}" y2="${y(t.truth)}"/><text class="lbl" x="${W - 60}" y="${y(t.truth) - 4}">fell ${t.truth}"</text>` : "";
    const tabs = ts.length > 1 ? `<div class="au-tabs">${ts.map((x, i) => `<button type="button" data-trail="${i}" aria-pressed="${i === S.trail}">${x.label} ${mmdd(x.date)}</button>`).join("")}</div>` : "";
    return card("Call trail", `${t.label}, ${wd(t.date)} ${mmdd(t.date)}: each source's snow call by days ahead`,
      `${tabs}<svg class="au-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Call trail">${yt}${lines}${truth}${ticks}</svg><p class="small muted" style="margin:0">Thick line: our blend. Days ahead along the bottom.</p>`);
  }

  function rangeCheck() {
    const r = S.data.range;
    if (!S.data.resort || S.data.resort === "all") return "";
    const body = r && r.n ? `<div class="au-stat"><strong>${Math.round((100 * r.inside) / r.n)}%</strong><strong class="au-stat-n">${r.inside}</strong><span class="small muted">of ${r.n} days landed inside our "low to could reach" range, 1 to 5 days out. Target: about 8 in 10.</span></div>`
      : `<p class="au-empty">Counts how often what fell landed inside the range we sent. Starts with live calls.</p>`;
    return card("Range check", "", body);
  }

  function weights() {
    const w = S.data.weights || {};
    if (!S.data.resort || S.data.resort === "all") return "";
    const days = [...new Set(Object.values(w).flat().map((p) => p[0]))].sort();
    if (days.length < 2) return card("Weight history", "", `<p class="au-empty">How much the blend trusts each model, day by day. Logged from ${days[0] ? mmdd(days[0]) : "the next morning run"}; the chart appears after two days.</p>`);
    const W = 320, H = 120, L = 26, B = 16, T = 6;
    const x = (d) => L + (days.indexOf(d) / (days.length - 1)) * (W - L - 6);
    const y = (v) => T + (1 - (Math.min(2, Math.max(0.5, v)) - 0.5) / 1.5) * (H - T - B);
    const lines = Object.entries(w).map(([m, pts]) => {
      let d = "";
      pts.forEach((p, i) => { const px = x(p[0]).toFixed(1), py = y(p[1] ?? 1).toFixed(1); d += i ? `H${px}V${py}` : `M${px},${py}`; });
      return `<path class="ln${m === S.sel ? " sel" : ""}" d="${d}"><title>${esc(name(m))}: skill ${pts[pts.length - 1][1]}</title></path>`;
    }).join("");
    const grid = [0.5, 1, 2].map((v) => `<text x="0" y="${y(v) + 3}">${v}×</text><line class="${v === 1 ? "zero" : "axis"}" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}" opacity=".5"/>`).join("");
    const ticks = [days[0], days[days.length - 1]].map((d, i) => `<text x="${i ? W - 28 : L}" y="${H - 2}">${mmdd(d)}</text>`).join("");
    return card("Weight history", "Each model's skill multiplier in the blend (1× = its starting weight)",
      `<svg class="au-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Weight history">${grid}${lines}${ticks}</svg>`);
  }

  function card(title, sub, body, cls = "") {
    return `<section class="card ${cls}"><div class="card-head"><h2>${esc(title)}</h2></div>${sub ? `<p class="sub">${esc(sub)}</p>` : ""}${body}</section>`;
  }

  function headline() {
    const d = S.data, h = d.headline, v = d.verdict, bits = [];
    if (v) bits.push(`${wd(v.date)} ${mmdd(v.date)}: ${v.fell}" fell, the blend said ${v.blend}" (missed by ${v.miss}")${v.best ? `, best was ${esc(name(v.best))}` : ""}.`);
    if (h) bits.push(`Blend beat ${h.beat} of ${h.of} sources over the last ${h.days} days.`);
    const days = d.days || {};
    const counts = `<span class="muted"> ${days.live || 0} live + ${days.replay || 0} replay days graded${d.resorts ? ` across ${d.resorts} resorts` : ""}${d.stations?.length ? ` · SNOTEL ${esc(d.stations.join(", "))}` : ""}.</span>`;
    $("#au-headline").innerHTML = (bits.join(" ") || "The record starts with this morning's call.") + counts;
  }

  function render() {
    if (!S.data) return;
    headline();
    const g = $("#au-grid");
    g.innerHTML = `<div class="au-col">${scoreboard()}</div><div class="au-col">${biasStrip()}${ledger()}</div><div class="au-col">${trail()}${rangeCheck()}${weights()}</div>`;
    g.querySelectorAll("tr[data-src]").forEach((tr) => tr.addEventListener("click", () => { S.sel = S.sel === tr.dataset.src ? null : tr.dataset.src; render(); }));
    g.querySelectorAll("[data-trail]").forEach((b) => b.addEventListener("click", () => { S.trail = +b.dataset.trail; render(); }));
  }

  // ---------- log drawer ----------
  function csvURL(all) {
    const p = new URLSearchParams({ resort: S.slug, format: "csv" });
    if (!all) {
      if (S.filters.kind) p.set("kind", S.filters.kind);
      if (S.filters.source) p.set("source", S.filters.source);
      if (S.filters.lead !== undefined && S.filters.lead !== "") p.set("lead", S.filters.lead);
      if (S.log) { p.set("from", S.log.from); p.set("to", S.log.to); }
    }
    return `/api/audit?${p}`;
  }

  function renderLog() {
    const body = $("#au-log-body"), f = S.filters;
    if (!S.log) return;
    const days = S.log.days.filter((d) => {
      if (f.flagged && !(d.flags || []).filter((x) => x !== "gauge-gap").length) return false;
      if (f.storm && !((d.resort_snow || 0) >= 2 || (d.snotel_liquid || 0) >= 0.15)) return false;
      return true;
    });
    const n = (v, dp = 1) => (v == null ? "–" : (+v).toFixed(dp));
    body.innerHTML = `<div class="hdr"><span>Day</span><span>Resort</span><span>SNOTEL water</span><span>Depth change</span><span>Flags</span></div>` +
      (days.length ? days.map((d) => {
        const calls = (d.calls || []).filter((c) => (!f.source || c[0] === f.source) && (f.lead === undefined || f.lead === "" || String(c[1]) === f.lead) && (!f.kind || c[2] === f.kind));
        return `<details><summary><span>${wd(d.date)} ${mmdd(d.date)}</span><span>${n(d.resort_snow)}"</span><span>${n(d.snotel_liquid, 2)}"</span><span>${n(d.snotel_depth)}"</span><span>${(d.flags || []).map((x) => `<span class="flag">${x}</span>`).join("")} <span class="muted">${calls.length} calls</span></span></summary>
          ${callTable(calls)}</details>`;
      }).join("") : `<p class="small muted">Nothing matches.</p>`);
    $("#au-csv").href = csvURL(false);
    $("#au-csv-all").href = csvURL(true);
  }

  // One small table per day: a row per source, a column per day ahead (snow, with water in the tooltip).
  function callTable(calls) {
    if (!calls.length) return '<p class="small muted">No calls match.</p>';
    const by = {};
    for (const c of calls) (by[c[0]] ||= {})[c[1] + c[2]] = c;
    const leads = [...new Set(calls.map((c) => c[1]))].sort((a, b) => b - a);
    const n = (v, dp) => (v == null ? "" : (+v).toFixed(dp));
    const cell = (c) => {
      if (!c) return "<td></td>";
      const main = c[4] != null ? n(c[4], 1) : n(c[3], 2) + "w";
      const tip = `${c[2]}${c[3] != null ? `, ${n(c[3], 2)}" water` : ""}${c[5] != null ? `, range ${n(c[5], 1)}–${n(c[6], 1)}"` : ""}`;
      return `<td class="${c[2] === "replay" ? "hatch" : ""}" title="${tip}">${main}</td>`;
    };
    return `<table class="calls"><thead><tr><th>Days ahead</th>${leads.map((l) => `<th>${l}</th>`).join("")}</tr></thead><tbody>${Object.keys(by).map((s) =>
      `<tr><th>${esc(name(s))}</th>${leads.map((l) => cell(by[s][l + "live"] || by[s][l + "replay"])).join("")}</tr>`).join("")}</tbody></table>`;
  }

  async function openLog() {
    const dlg = $("#au-log");
    if (S.slug === "all") { $("#au-log-body").innerHTML = `<p class="small muted">Pick a resort to see its log.</p>`; dlg.showModal(); return; }
    dlg.showModal();
    if (!S.log || S.log.resort !== S.slug) {
      $("#au-log-body").innerHTML = `<p class="small muted">Loading…</p>`;
      try { S.log = await getJSON(`/api/audit?resort=${encodeURIComponent(S.slug)}&log=1`); }
      catch (e) { $("#au-log-body").innerHTML = `<p class="small muted">The log couldn't load (${esc(e.message)}).</p>`; return; }
    }
    const srcs = [...new Set(S.log.days.flatMap((d) => d.calls.map((c) => c[0])))];
    $("#au-f-source").innerHTML = `<option value="">All</option>` + srcs.map((s) => `<option value="${esc(s)}">${esc(name(s))}</option>`).join("");
    $("#au-f-lead").innerHTML = `<option value="">All</option>` + [...Array(10).keys()].map((l) => `<option value="${l}">${l} days</option>`).join("");
    $("#au-f-source").value = S.filters.source || ""; $("#au-f-lead").value = S.filters.lead ?? "";
    renderLog();
  }

  function wire() {
    document.querySelectorAll("[data-metric]").forEach((b) => b.addEventListener("click", () => {
      S.metric = b.dataset.metric; document.querySelectorAll("[data-metric]").forEach((x) => x.setAttribute("aria-pressed", x === b)); render();
    }));
    document.querySelectorAll("[data-kind]").forEach((b) => b.addEventListener("click", () => {
      S.kind = b.dataset.kind; document.querySelectorAll("[data-kind]").forEach((x) => x.setAttribute("aria-pressed", x === b)); render();
    }));
    $("#au-log-btn").addEventListener("click", openLog);
    $("#au-log-close").addEventListener("click", () => $("#au-log").close());
    $("#au-log").addEventListener("click", (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });
    document.querySelectorAll(".chip[data-f]").forEach((b) => b.addEventListener("click", () => {
      S.filters[b.dataset.f] = !S.filters[b.dataset.f]; b.setAttribute("aria-pressed", !!S.filters[b.dataset.f]); renderLog();
    }));
    [["#au-f-source", "source"], ["#au-f-lead", "lead"], ["#au-f-kind", "kind"]].forEach(([sel, key]) =>
      $(sel).addEventListener("change", (e) => { S.filters[key] = e.target.value; renderLog(); }));
    $("#au-resort").addEventListener("change", (e) => {
      history.pushState(null, "", `/audit/${e.target.value}`); load(e.target.value);
    });
    window.addEventListener("popstate", () => load(slugFromPath()));
    matchMedia("(max-width: 699px)").addEventListener("change", render);
  }

  function slugFromPath() {
    const m = location.pathname.match(/^\/audit\/([a-z0-9-]+)/);
    if (m) return m[1];
    try { return localStorage.getItem("resort") || "beaver-creek"; } catch (e) { return "beaver-creek"; }
  }

  async function load(slug) {
    S.slug = slug; S.trail = 0; S.sel = null;
    $("#au-resort").value = slug;
    $("#au-back").href = "/#forecast";
    try {
      S.data = await getJSON(`/data/audit/${slug}.json`);
    } catch (e) {
      S.data = null;
      $("#au-headline").textContent = "";
      $("#au-grid").innerHTML = `<section class="card"><h2>Not graded yet</h2><p class="small muted" style="margin:0">This resort's report card appears after its first saved morning call and the first pass over past winters. Check back in an hour.</p></section>`;
      return;
    }
    render();
  }

  (async () => {
    wire();
    try {
      const list = await getJSON("/resorts.json");
      const sel = $("#au-resort");
      sel.innerHTML = `<option value="all">All resorts</option>` + list.resorts.map((r) => `<option value="${esc(r.slug)}">${esc(r.name)}</option>`).join("");
    } catch (e) {}
    load(slugFromPath());
  })();
})();
