// Cloudflare Worker (free plan): the scheduler.
//
// Cron fires every 15 minutes from 09:00 to 17:45 UTC (2-10 a.m. MST, 3-11 a.m. MDT) and once
// at 21:00 UTC. Cloudflare cron runs on the minute, unlike GitHub Actions' best-effort
// schedule. Each tick calls the Vercel function, which decides what to do:
// mostly a cheap "nothing changed", a full refresh before 7:00, and the 7:00 send.
//
// Reliability: 3 attempts with backoff per tick. If all fail, it pushes an alert to
// ADMIN_NTFY_TOPIC (optional). The send itself is idempotent on the Vercel side, so
// retries and the Vercel backup cron can never double-send.
export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(trigger(env, `cron ${event.cron}`));
  },
  // GET /?key=<CRON_SECRET>[&force=1] runs it by hand; &test=1 sends a labeled test report now.
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.get("key") !== env.CRON_SECRET) return new Response("Not found", { status: 404 });
    const mode = url.searchParams.get("test") === "1" ? "test" : url.searchParams.get("force") === "1" ? "force" : "";
    const res = await trigger(env, "manual", mode);
    return new Response(JSON.stringify(res), { headers: { "content-type": "application/json" } });
  },
};

async function trigger(env, why, mode = "") {
  let last = { status: 0, body: "" };
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(`${env.RUN_URL}${mode ? `?${mode}=1` : ""}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${env.CRON_SECRET}`, "User-Agent": "snow-desk-cron" },
      });
      last = { status: res.status, body: (await res.text()).slice(0, 800) };
      console.log(why, `attempt ${attempt}`, last.status, last.body);
      if (res.ok) return { ok: true, attempt, ...last };
      if (res.status === 401 || res.status === 409) break; // wrong secret, or a refused test: don't retry
    } catch (e) {
      last = { status: 0, body: String(e) };
      console.log(why, `attempt ${attempt} error`, last.body);
    }
    await new Promise((r) => setTimeout(r, attempt * 15000));
  }
  if (env.ADMIN_NTFY_TOPIC) {
    await fetch(`https://ntfy.sh/${env.ADMIN_NTFY_TOPIC}`, {
      method: "POST",
      headers: { Title: "Snow Desk run failed", Tags: "warning", Priority: "4" },
      body: `${why}: HTTP ${last.status} ${last.body}`.slice(0, 1000),
    }).catch(() => {});
  }
  return { ok: false, ...last };
}
