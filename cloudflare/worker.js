// Cloudflare Worker (free plan): the scheduler.
// Cron fires every 30 minutes from 3:00 to 9:30 a.m. Mountain time and once mid-afternoon,
// and calls the Vercel function, which does the work and decides whether anything changed.
// Waiting on the fetch doesn't count toward the Worker's CPU limit.
export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(trigger(env, event.cron));
  },
  // GET /?key=<CRON_SECRET>&force=1 runs it by hand (handy after a deploy).
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.get("key") !== env.CRON_SECRET) return new Response("Not found", { status: 404 });
    const res = await trigger(env, "manual", url.searchParams.get("force") === "1");
    return new Response(res, { headers: { "content-type": "application/json" } });
  },
};

async function trigger(env, why, force = false) {
  const res = await fetch(`${env.RUN_URL}${force ? "?force=1" : ""}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.CRON_SECRET}`, "User-Agent": "snow-desk-cron" },
  });
  const body = await res.text();
  console.log(why, res.status, body.slice(0, 500));
  return body;
}
