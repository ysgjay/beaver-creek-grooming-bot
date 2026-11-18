/* Owner stats page: reads /api/stats with the admin password (kept on this device only).
   Days are Mountain Time, labeled weekday over MM/DD. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const mmdd = (d) => `${d.slice(5, 7)}/${d.slice(8, 10)}`;
  const wd = (d) => WD[new Date(d + "T12:00:00Z").getUTCDay()];
  const n0 = (x) => Number(x || 0).toLocaleString();
  const KEY = "adminKey";
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} },
  };

  function daysBack(today, n) {
    const out = [], t = new Date(today + "T12:00:00Z");
    for (let i = n - 1; i >= 0; i--) { const d = new Date(t); d.setUTCDate(t.getUTCDate() - i); out.push(d.toISOString().slice(0, 10)); }
    return out;
  }

  // Bars per day; series stack. Hover a day for its numbers.
  function bars(days, series, valueOf, tipOf) {
    const W = 600, H = 190, L = 30, B = 40, T = 8, w = (W - L) / days.length;
    const tot = days.map((d) => series.reduce((a, s) => a + (valueOf(d, s.key) || 0), 0));
    const max = Math.max(1, ...tot);
    const step = max <= 4 ? 1 : Math.ceil(max / 4 / (max > 40 ? 10 : 1)) * (max > 40 ? 10 : 1);
    const top = Math.ceil(max / step) * step, y = (v) => T + (H - B - T) * (1 - v / top);
    let g = "";
    for (let v = 0; v <= top; v += step) g += `<line class="grid" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 4}" y="${y(v) + 5}" text-anchor="end">${v}</text>`;
    days.forEach((d, i) => {
      const x = L + i * w;
      g += `<rect class="hit" data-i="${i}" x="${x}" y="${T}" width="${w}" height="${H - B - T}"/><rect class="hl" x="${x}" y="${T}" width="${w}" height="${H - B - T}" fill="transparent"/>`;
      let acc = 0;
      series.forEach((s, si) => {
        const v = valueOf(d, s.key) || 0; if (!v) return;
        const y1 = y(acc + v), h = y(acc) - y1 - (si && acc ? 0 : 0);
        const gap = acc ? 2 : 0;
        g += `<rect class="${s.cls}" x="${x + w * .18}" y="${y1}" width="${w * .64}" height="${Math.max(1, h - gap)}" rx="2" pointer-events="none"/>`;
        acc += v;
      });
      if (i % 5 === (days.length - 1) % 5) g += `<text x="${x + w / 2}" y="${H - B + 17}" text-anchor="middle">${wd(d)}</text><text x="${x + w / 2}" y="${H - B + 33}" text-anchor="middle">${mmdd(d)}</text>`;
    });
    const svg = `<svg class="ad-svg" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
    return { svg, wire: (el) => wireTip(el.querySelector("svg"), (i) => `<strong>${wd(days[i])} ${mmdd(days[i])}</strong><br>${tipOf(days[i])}`) };
  }

  function wireTip(svg, html) {
    const tip = $("#tip");
    const show = (e) => {
      const r = e.target.closest(".hit"); if (!r) { tip.hidden = true; return; }
      tip.innerHTML = html(Number(r.dataset.i)); tip.hidden = false;
      const x = Math.min(innerWidth - tip.offsetWidth - 8, e.clientX + 12);
      tip.style.left = `${Math.max(8, x)}px`; tip.style.top = `${e.clientY - tip.offsetHeight - 12}px`;
    };
    svg.addEventListener("pointermove", show);
    svg.addEventListener("pointerdown", show);
    svg.addEventListener("pointerleave", () => (tip.hidden = true));
  }

  const card = (title, sub, body, cls = "") => `<section class="card ${cls}"><h2>${title}</h2>${sub ? `<p class="sub">${sub}</p>` : ""}${body}</section>`;
  const legend = (items) => `<div class="ad-legend">${items.map(([cls, label]) => `<span><i style="background:var(${cls})"></i>${label}</span>`).join("")}</div>`;

  function render(s) {
    const days = daysBack(s.today, s.days);
    const sig = s.signups || {}, vis = s.visits || {};
    const active = s.email.active || 0, pending = s.email.pending || 0, unsub = s.email.unsubscribed || 0;
    const w = s.window || {};
    const kpi = (v, label) => `<div class="card ad-kpi"><b>${n0(v)}</b><span>${label}</span></div>`;
    const kpis = `<div class="ad-kpis">
      ${kpi(active, "Email subscribers")}${kpi(s.push, "App notifications")}${kpi(pending, "Waiting to confirm")}
      ${kpi(w["1"]?.visitors, "Visitors today")}${kpi(w["7"]?.visitors, "Visitors, 7 days")}${kpi(w["30"]?.visitors, "Visitors, 30 days")}</div>`;

    const sg = bars(days, [{ key: "confirmed", cls: "b1" }, { key: "push", cls: "b2" }], (d, k) => sig[d]?.[k],
      (d) => `${sig[d]?.confirmed || 0} email confirmed · ${sig[d]?.push || 0} app<br>${sig[d]?.requested || 0} forms sent${sig[d]?.unsubscribed ? ` · ${sig[d].unsubscribed} unsubscribed` : ""}`);
    const sum = (k) => days.reduce((a, d) => a + (sig[d]?.[k] || 0), 0);
    const signupsCard = card("Sign-ups, last 30 days",
      `${sum("confirmed")} emails confirmed, ${sum("push")} app notifications, ${sum("unsubscribed")} unsubscribed. ${n0(s.multi)} subscribers follow 2+ resorts (combined email).`,
      legend([["--snow", "Email confirmed"], ["--frost-metric-heat", "App notifications"]]) + sg.svg);

    const vg = bars(days, [{ key: "visitors", cls: "b1" }], (d) => vis[d]?.visitors, (d) => `${vis[d]?.visitors || 0} visitors · ${vis[d]?.views || 0} views`);
    const since = s.counting_since ? ` Counting since ${mmdd(s.counting_since)}.` : " Counting starts with the next visit.";
    const visitsCard = card("Visitors per day", `${n0(w["30"]?.views)} views in 30 days, ${n0(s.returning)} visitors came back on 2+ days.${since}`, vg.svg);

    const slugs = new Set([...Object.keys(s.resorts || {}), ...Object.keys(s.by_resort || {})]);
    const rows = [...slugs].map((k) => ({ k, name: s.names?.[k] || k, e: s.resorts?.[k]?.email || 0, p: s.resorts?.[k]?.push || 0, v: s.by_resort?.[k] || 0 }))
      .sort((a, b) => (b.e + b.p) - (a.e + a.p) || b.v - a.v);
    const vmax = Math.max(1, ...rows.map((r) => r.v));
    const resortCard = card("By resort", "Active email subscribers, app notification devices, and visitors who opened that resort in 30 days.",
      rows.length ? `<table class="ad-t"><thead><tr><th>Resort</th><th>Email</th><th>App</th><th>Visitors</th></tr></thead><tbody>${rows.map((r) =>
        `<tr><td>${esc(r.name)}</td><td>${r.e}</td><td>${r.p}</td><td>${r.v}<span class="bar" style="width:${Math.round(40 * r.v / vmax)}px"></span></td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">Nothing yet.</p>`);

    const tabs = ["today", "forecast", "calendar", "help"].map((t) => [t, s.by_view?.[t] || 0]);
    const dev = s.devices || {}, all = dev.all || 0, pct = (x) => (all ? Math.round(100 * x / all) + "%" : "–");
    const useCard = card("How it's used", "Last 30 days.",
      `<table class="ad-t"><thead><tr><th>Tab</th><th>Views</th></tr></thead><tbody>${tabs.map(([t, n]) => `<tr><td>${t[0].toUpperCase() + t.slice(1)}</td><td>${n0(n)}</td></tr>`).join("")}</tbody></table>
       <table class="ad-t"><thead><tr><th>Visitors</th><th>Share</th></tr></thead><tbody>
       <tr><td>On a phone</td><td>${pct(dev.phone)}</td></tr><tr><td>From the Home Screen app</td><td>${pct(dev.home_screen)}</td></tr>
       <tr><td>Came back on 2+ days</td><td>${pct(s.returning)}</td></tr></tbody></table>`);

    const recent = s.recent || [];
    const recentCard = card("Latest sign-ups", `${n0(active + pending + unsub)} addresses in all: ${n0(active)} active, ${n0(pending)} pending, ${n0(unsub)} unsubscribed. Addresses are shortened here.`,
      recent.length ? `<table class="ad-t"><thead><tr><th>Email</th><th>Resorts</th><th>Date</th></tr></thead><tbody>${recent.map((r) =>
        `<tr><td>${esc(r.email)} <span class="ad-pill ${esc(r.status)}">${esc(r.status)}</span></td><td>${esc(r.resorts.map((k) => s.names?.[k] || k).join(", "))}</td><td>${mmdd(r.at.slice(0, 10))}</td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">No sign-ups yet.</p>`, "wide");

    const off = !!store.get("noCount");
    $("#ad-body").innerHTML = kpis + `<div class="ad-grid">${signupsCard}${visitsCard}${resortCard}${useCard}${recentCard}</div>
      <div class="ad-foot"><label><input type="checkbox" id="ad-nocount"${off ? " checked" : ""}> Don't count my visits on this device</label>
      <span>Visits are counted by the app itself: a random id per browser, no cookies or IPs. Updated ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}.</span></div>`;
    const cards = $("#ad-body").querySelectorAll(".ad-grid .card");
    sg.wire(cards[0]); vg.wire(cards[1]);
    $("#ad-nocount").addEventListener("change", (e) => store.set("noCount", e.target.checked ? "1" : null));
    $("#ad-sub").textContent = `Private · Mountain Time · ${wd(s.today)} ${mmdd(s.today)}`;
  }

  async function load() {
    const key = store.get(KEY);
    if (!key) return showLogin();
    $("#ad-body").innerHTML = `<div class="skeleton"></div>`;
    let r;
    try { r = await fetch("/api/stats", { headers: { Authorization: `Bearer ${key}` }, cache: "no-store" }); } catch (e) { r = null; }
    if (r && r.status === 401) { store.set(KEY, null); return showLogin("That password didn't work."); }
    if (!r || !r.ok) { $("#ad-body").innerHTML = `<p class="small muted">Couldn't load stats. Try Refresh.</p>`; return; }
    $("#ad-login").hidden = true; $("#ad-lock").hidden = false; $("#ad-refresh").hidden = false;
    store.set("noCount", store.get("noCount") ?? "1");   // the owner's own device isn't counted unless they turn it back on
    render(await r.json());
  }
  function showLogin(msg = "") {
    $("#ad-body").innerHTML = ""; $("#ad-lock").hidden = true; $("#ad-refresh").hidden = true;
    $("#ad-login").hidden = false; $("#ad-msg").textContent = msg; $("#ad-key").focus();
  }
  $("#ad-login").addEventListener("submit", (e) => { e.preventDefault(); store.set(KEY, $("#ad-key").value.trim()); $("#ad-key").value = ""; load(); });
  $("#ad-lock").addEventListener("click", () => { store.set(KEY, null); showLogin(); });
  $("#ad-refresh").addEventListener("click", load);
  load();
})();
