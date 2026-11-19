# Making 0xSnow discoverable—and dependable—in AI search

**Prepared by: Codex External Research Review Team**  
**Authorship: AI-generated research and code review, published at the repository owner’s request.**

**Research date: November 18, 2026, Eastern Time.** Live captures continued into November 19 UTC. Chair 0 / Snow Desk is now branded **0xSnow**. This report uses the current name and audits [snow.0xm.studio](https://snow.0xm.studio/).

## Decision

**Keep the existing public HTML pages. Make their claims traceable and their freshness unambiguous before investing in more AI distribution.** The site already has server-rendered resort reports, dated archives, regional pages, sourced guides, a sitemap, RSS, IndexNow code, Markdown, JSON and `llms.txt`. Rebuilding these would duplicate recent work.

The best next investment is a shared public data representation that preserves source, observation period, time zone, forecast issue time, elevation, uncertainty and missing-data status across the app, HTML, Markdown and JSON. Then expose the forecast audit as readable HTML and measure real indexing and citations. A small, read-only MCP integration can follow if people want to connect 0xSnow directly to an assistant.

Three findings drive this recommendation:

1. **An attribution error is already public.** Telluride’s page says the resort reports 2 inches of new snow, but its stored resort report is empty. The number comes from a nearby SNOTEL snow-depth calculation. Making that claim easier for AI systems to repeat would amplify an error.
2. **The essential crawlable pages already work.** Beaver Creek’s report returns substantial HTML and the same response to five tested search-crawler user-agent strings. The remaining visibility questions require verified crawler logs and webmaster reports, not another rendering framework.
3. **Accuracy evidence is early and easy to overstate.** The sampled Beaver Creek audit showed one live day and 379 replay days. Replay precipitation evidence is not a verified live snowfall track record.

No production changes, deployments, merges, subscriptions or messages to third parties were made. The original checkout was treated as read-only.

## Evidence and scope

Labels used below:

- **Verified:** directly observed in live responses, inspected code or current primary documentation.
- **Inference:** a reasoned consequence of that evidence, not a measured ranking effect.
- **Unknown:** requires account access, production logs, provider testing or source confirmation.
- **Unsupported:** no primary evidence found for the proposed benefit or claim.

Repository findings are pinned to [main commit 413056c](https://github.com/ysgjay/beaver-creek-grooming-bot/commit/413056ccf6a163ad4082d2107e50e28af2b21535), which includes the public-page styling update from PR #91. That was 21 commits ahead of the original handoff checkout, so advice based solely on the older checkout would miss important existing work. Repository configuration is not proof that every optional service is deployed.

The audit combined raw HTTP responses, rendered browser inspection, source inspection and official provider documentation. It sampled Beaver Creek, Vail, Telluride and Snowbird, a regional page, a guide, dated reports, machine representations, robots, sitemap, feeds and invalid URLs. It did not inspect Search Console, Bing Webmaster Tools, production firewall settings or verified crawler traffic. It did not run a controlled experiment inside all five consumer assistants.


A [sanitized evidence file](audit-evidence.json) preserves response details, timestamps, hashes and selected factual observations without raw operational payloads.

## 1. What exists today

| Surface | Verified result | Implication |
|---|---|---|
| [Home / interactive app](https://snow.0xm.studio/) | HTTP 200; title, description, canonical, Open Graph and WebSite/Organization markup. Initial HTML contains navigation and about 196 characters of extracted text, without the report facts. The browser app fills them in. | Preserve the app experience, but use the public reports as primary citation destinations. |
| [Resort hub](https://snow.0xm.studio/resorts) and [Colorado](https://snow.0xm.studio/resorts/colorado) | Server-rendered HTML with resort links and comparison information. | A useful discovery path already exists. Attribution and comparable observation periods need to survive aggregation. |
| [Beaver Creek report](https://snow.0xm.studio/resorts/beaver-creek) | HTTP 200; about 28 KB of HTML, self-canonical, summary, tables, report content and WebPage/BreadcrumbList markup. | The main report does not require JavaScript to expose its facts. |
| [Dated report](https://snow.0xm.studio/resorts/beaver-creek/2026-11-17) | HTTP 200; dated self-canonical and BlogPosting markup. | Historical citation URLs exist. Their snapshot semantics need tightening. |
| [Resort guide](https://snow.0xm.studio/resorts/beaver-creek/guide) | Sourced resort facts and checked dates. | Reuse this provenance pattern for snow, grooming and forecast data. |
| [Markdown](https://snow.0xm.studio/resorts/beaver-creek.md) / [JSON](https://snow.0xm.studio/resorts/beaver-creek.json) | HTTP 200; appropriate content types; canonical link header to HTML. JSON permits cross-origin public reads. | Good integration starting point. Both lose material context from the stored data. |
| [Sitemap](https://snow.0xm.studio/sitemap.xml), [RSS](https://snow.0xm.studio/feed.xml), [llms.txt](https://snow.0xm.studio/llms.txt) | Available. Sitemap contained 139 URLs in the capture. `llms.txt` lists all 22 resort report routes. | Maintain these; do not treat their existence as evidence of indexing or citation. |
| [Forecast audit](https://snow.0xm.studio/audit/beaver-creek) | HTTP 200, but initial HTML is a generic shell without resort scores, canonical or structured data. The browser loads the data later. | This is the clearest remaining rendering opportunity. |
| Invalid resort / future nonexistent archive | Real 404 and noindex in sampled responses. | Good behavior; retain it. |
| `/openapi.json` | HTTP 404; no published specification found in inspected code. | A public contract would be new work, not a prerequisite for ordinary search. |

**Crawler smoke test:** Beaver Creek returned HTTP 200 and identical 28,470-byte bodies for `OAI-SearchBot`, `Googlebot`, `bingbot`, `PerplexityBot` and `Claude-SearchBot` user-agent strings. This tests response behavior from the research network. It does **not** authenticate those bots, establish their actual crawl success or rule out IP-based challenges.

Responses identified Vercel. Repository documentation describes Cloudflare as a scheduler; that does not establish that Cloudflare proxies the website. Main also contains a Render worker and self-hosted Open-Meteo configuration, with a shadow-mode rollout. Their live deployment state remains unknown. [Architecture and current handoff](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/docs/HANDOFF.md), [Render configuration](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/docs/RENDER.md).

## 2. How the major assistants find and use websites

Four separate mechanisms matter. **Search indexing** makes pages candidates for retrieval. **Answer grounding and citation** select and use some retrieved content. **Training** can affect model development but is not a freshness or citation channel. **Connected tools** retrieve explicitly configured data through an API or MCP server. Permission for one is not a universal switch for the others.

| Provider / product | Documented behavior and controls | Action for 0xSnow |
|---|---|---|
| **ChatGPT search** | `OAI-SearchBot` supports search; `GPTBot` supports training and is independently controllable. `ChatGPT-User` performs user-directed access; robots rules may not apply to these requests. OpenAI publishes crawler IP information. [Crawler documentation](https://developers.openai.com/api/docs/bots). ChatGPT also uses third-party search partners; a specific placement is not guaranteed. [ChatGPT search help](https://help.openai.com/en/articles/9237897-searching-the-web-with-chatgpt). | Keep public reports accessible to search and user retrieval. Treat training permission as a separate owner choice. Do not assume that being in Bing alone ensures ChatGPT citations. |
| **Google AI Overviews / AI Mode** | These use the Search foundation. Existing SEO practices, accessible content and index eligibility apply; no special AI schema is required. Google explicitly says `llms.txt` does not affect Search visibility. [Current AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide). | Verify indexability and Google’s current Search generative AI setting. Prioritize clear, useful content over AI-specific files or repeated question pages. |
| **Gemini and Google grounding products** | `Google-Extended` is a robots product token, not a separate HTTP crawler identity. It governs specified training uses and grounding in Gemini Apps and Vertex AI Grounding with Google Search; it does not control inclusion or ranking in Google Search. [Google crawler reference](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers). | Do not describe Google-Extended as a training-only opt-out. Decide its policy with the Gemini grounding consequence in view. |
| **Bing / Microsoft Copilot** | Microsoft documents Bing web grounding for Microsoft 365 Copilot and Copilot Chat. [Microsoft documentation](https://learn.microsoft.com/en-us/copilot/plan/manage-public-web-access). Bing’s AI Performance reporting exposes citation activity across supported experiences; it is not a universal authority score. [Bing announcement](https://blogs.bing.com/webmaster/2026/2/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview/). | Verify Bing indexing, retain IndexNow and use the owner reports. Do not generalize one Copilot product’s behavior to every product carrying the name. |
| **Perplexity** | `PerplexityBot` supports search and is not used to train foundation models. `Perplexity-User` performs user-directed retrieval and generally ignores robots. Published IP lists support verification and firewall configuration. [Official crawler guide](https://docs.perplexity.ai/docs/resources/perplexity-crawlers). | Make the same public content available to verified search and user fetches. Test organic discovery separately from giving Perplexity a direct URL. |
| **Claude** | `ClaudeBot` is for model development; `Claude-SearchBot` supports search; `Claude-User` retrieves content for users. Anthropic says these bots respect robots and do not bypass CAPTCHAs. [Official crawler guide](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler). | Keep search/user access working and decide training policy separately. A CAPTCHA on public reports can prevent access despite permissive robots. |

### Current Google details that change the usual advice

Google’s current documentation says its **Search generative AI inclusion control** rolled out worldwide on August 31, 2026. Check Settings → Search generative AI for the relevant property, including whether it inherits a parent property’s choice. A setting on `0xm.studio` could therefore matter to the snow subdomain. This is separate from general Search ranking and from training controls. The account’s actual setting was not inspected. [Search generative AI control](https://support.google.com/webmasters/answer/16908024).

Google also documents a **Generative AI performance report** for impressions in AI Overviews and AI Mode. It may be absent when impressions are insufficient; it excludes Search Labs experiments and uses Pacific Time for dates. Use it alongside ordinary Search performance and site analytics; it does not measure every assistant or every downstream answer. [Report documentation](https://support.google.com/webmasters/answer/16984139).

FAQ rich results were removed in May 2026 according to Google’s current changelog. The existing FAQ markup can describe real page content, but building more of it for a Google rich-result payoff is no longer justified. [Search documentation updates](https://developers.google.com/search/updates).

### Claims to reject

- **Unsupported:** “Allow training bots and the model will recommend us.” Training access neither guarantees inclusion nor provides current snow conditions.
- **Unsupported:** “An MCP server automatically places us in AI search.” A connection is an explicit distribution mechanism, not general web indexing.
- **Unsupported:** “`llms.txt` or Markdown creates a ranking boost.” The former is a proposal; Google explicitly denies a Search effect. Keep the existing low-cost navigation file, without treating it as a growth strategy. [Proposal](https://llmstxt.org/).
- **Unsupported:** “JSON-LD guarantees citations” or “IndexNow instantly indexes every update.” The latter notifies participating engines of changes and does not guarantee indexing. [IndexNow FAQ](https://www.indexnow.org/faq).
- **Unsupported:** “AI crawlers never execute JavaScript.” Capabilities differ. The defensible engineering choice is to serve essential facts in HTML so access does not depend on execution.

## 3. Reliability issues to fix before expanding reach

### P0: distinguish resort observations from station-derived estimates

**Verified:** the captured [Telluride report](https://snow.0xm.studio/resorts/telluride) said “The resort reports 2\" of new snow in the last 24 hours.” Its stored `resort` object was empty. The available observation was from station `1344:CO:SNTL`, labeled Alta Lakes in configuration.

`mailer.new_snow()` can substitute `observed.snow_in` when the resort field is absent; `pages.summary()` wraps the result in “The resort reports.” The JSON projection and regional summaries reuse that value. The SNOTEL calculation is the nonnegative difference between the maximum and first of the last up-to-25 available snow-depth observations. It is not a direct snowfall measurement, and counting readings does not prove a continuous 24-hour interval. [Summary code](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/pages.py), [shared snow helper](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/mailer.py), [SNOTEL calculation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/sources/snotel.py).

**Change:** represent these as different metrics. For this capture, the resort snowfall field should be unavailable, with an explanation that an official feed is not integrated. A separate station section can report a **derived maximum snow-depth rise of 2 inches**, with station, method, timestamps and interval completeness. Avoid ranking this directly against resorts’ reported 24-hour snowfall without a visible qualification.

Similarly, “the resort hasn’t posted grooming” is stronger than the evidence when 0xSnow has no integrated grooming source. Use “Grooming data is not available in 0xSnow for this resort.” Distinguish `not_integrated`, `not_published`, `fetch_failed`, `stale`, `partial` and confirmed zero.

### P0: carry the source’s clock, not just the page’s date

**Verified:** the Beaver Creek snapshot was generated at `2026-11-18T14:01-07:00`. Its resort source string said November 18 at 5:32 AM MST. Its grooming map was dated November 16. These are three different freshness clocks.

The app visibly warned that the map was two days old. The public HTML’s image alternative text used the report date, while the caption named the older map date. The clean JSON omitted the map date and stale status entirely. The HTML summary exposed only “5:32 AM” for the resort report, without its full date or time zone. [Public rendering](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/webreport.py), [machine projection](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/llm.py).

**Change:** show report date, source publication time, source check time and source validity period separately. A successful fetch of an old map must not make that map fresh. Use offset-bearing timestamps plus `America/Denver`; do not infer SNOTEL’s timestamp basis from the resort’s location. Preserve the original source timestamp string until its conversion is verified. Apply stale status to each field or section, then derive a page-level warning.

The current title always says “today,” even if the stored report is from an earlier day. Compare the report’s local date with the resort’s actual current date before using that word. Overnight publication windows should show “awaiting today’s report” with yesterday’s dated values, not silently relabel them.

### P0: preserve missingness and the forecast window

**Verified:** the sampled report’s HTML and Markdown use a dash for very small/zero daily snowfall. JSON retains a numeric zero. A dash also represents other absent information. Consumers cannot reliably distinguish dry weather, a trace amount and no data.

In `forecast.build()`, unavailable dates can be skipped before the first five entries are summed. Under a date gap, “next five days” can therefore cover more than five calendar dates. Ensemble aggregation also substitutes zero for missing daily snow values. These are code-level failure paths; the audit did not establish that the captured five-day total was affected. [Forecast implementation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/forecast.py).

**Change:** select an exact calendar interval, record expected/available hours and dates, and return a partial or unavailable total when coverage is insufficient. Use `0` only for a real zero; use `null` plus a reason for unavailable values. Preserve exact numeric values in data while choosing explicit human labels such as “0 in” or “less than 0.1 in” according to a documented rounding rule.

### P1: make the morning report and current forecast distinct

`latest_day()` prefers a sent report snapshot when one exists. This is reasonable for a daily edition but does not necessarily provide the latest forecast. In the captured evening page, the lead still told readers to expect 30°F at 2 PM. The “First chair to last” table extended from 2 PM to 10 PM because the hourly helper falls back to the first nine available hours. [Page selection](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/pages.py), [hour selection](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/mailer.py).

**Change:** label the existing page “Daily report, published …” if it is an edition. Add a distinct current-forecast page only if it updates independently. Give each an explicit as-of time and link to the other. Label a fallback hourly window with its actual start and end, rather than calling evening hours lift hours. Preserve the ice-glass appearance and blue charts; these changes concern content and semantics, not a redesign.

### P1: stop implying that the model range is a calibrated probability interval

The code uses ensemble 10th–90th percentiles when enough members exist, widens the upper bound to include deterministic model outcomes, and keeps the blend inside the bounds. Without enough members it uses a different range method. This is not an untouched 80% prediction interval. “Most likely” also overstates what a weighted blend alone establishes. [Range calculation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/forecast.py).

**Change:** say “blend estimate” and “model range” until empirical coverage supports a more specific claim. Publish the algorithm version, contributing models, available member count, forecast point and coverage. Derive counts from the snapshot: older documentation says 82 ensemble members, while the inspected data reported 212. Do not hardcode a marketing count.

### P1: make historical reports reproducible

The code attempts to freeze sent reports under `data/posts/<date>.json`, but falls back to mutable daily data for older posts. The sampled November 18 Beaver Creek frozen-post URL returned 404, while the current report was available. That is evidence that the fallback matters, not proof that all archives lack snapshots. Archive rendering also imports current resort facts. [Archive implementation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/pages.py).

**Change:** retain a versioned, immutable core report at publication; attach a revision ID and content hash. Corrections should produce a new revision with a reason, previous revision link and corrected timestamp. Keep current resort facts visibly separate from facts as published in the historical report. Do not backfill a forecast made today into what appears to be yesterday’s issued forecast. `datePublished` must mean publication of that edition; `dateModified` must track a meaningful revision.

## 4. Make forecast accuracy an evidence product

The existing audit is a valuable foundation: it records live calls and replay data separately and distinguishes snowfall from liquid precipitation. In the captured Beaver Creek view, however, the headline was **1 live + 379 replay days graded**. That is not enough to claim that 0xSnow is more accurate than a competitor, the official resort forecast or a baseline. [Live audit](https://snow.0xm.studio/audit/beaver-creek), [audit implementation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/audit.py).

Publish a server-rendered summary and downloadable, sanitized observations with these dimensions:

| Dimension | Required interpretation |
|---|---|
| Live versus replay | Separate tables, denominators and conclusions. Historical precipitation replay is not a live snowfall backtest. |
| Forecast vintage | Exact time the prediction was recorded, provider/model initialization where available, valid period, lead time and model/blend version. A date alone cannot establish equal information availability. |
| Observation truth | Resort report or named station, measurement type, elevation/location, observation window, source correction status and units. Snow depth, snowfall, SWE and liquid precipitation are different quantities. |
| Evaluation sample | Unique valid days and storms, forecast–observation pairs, missing/excluded rows, source coverage and evaluation dates. Pooled lead rows are not necessarily independent days. |
| Baselines | Compare on the same forecast/observation cohort and lead times: plain average and the relevant available models or official product. Do not compare each model’s easiest available subset. |
| Metrics | MAE and signed bias; an explicitly defined skill score against the paired baseline; threshold-event precision/recall where useful; interval coverage and width. State units and whether scores are conditional on events. |
| Uncertainty | Confidence intervals or resampling grouped by storm/date, sufficient sample disclosure, and restrained conclusions during the early season. |
| Learning versus evaluation | Freeze each forecast before outcomes. Record the calibration/weights used; learn only from information available then. Keep tuning periods separate from held-out evaluation. |

Two current implementation details deserve special care. The audit’s event inclusion threshold is `max(forecast, observed) >= 1 inch` for snow and `>= 0.05 inch` for water, so the resulting error score is not an unconditional all-day MAE. The grade threshold is eight accumulated samples, and lead grouping can pool multiple rows for a valid day. Label these denominators correctly before describing them as eight independent days of evidence. The existing database has a record timestamp, but that does not replace a provider’s model initialization time. [Audit code](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/audit.py).

A morning resort “last 24 hours” report is currently assigned to the previous calendar date. Verify the actual source reporting window before matching it to a midnight-to-midnight forecast. Likewise, a nearby SNOTEL station can provide useful corroboration while sampling a different elevation and exposure. NRCS itself distinguishes snow depth, snow water equivalent and precipitation in its measurement descriptions. [NRCS measurement overview](https://www.nrcs.usda.gov/resources/education-and-teaching-materials/water-and-climate-data-collection-and-stewardship).

A defensible early headline is: **“Live verification is collecting data. Replay results describe historical liquid precipitation and are shown separately.”** Once adequate paired evidence exists, publish the actual result with dates, sample size, uncertainty and exclusions. This original, auditable work is a stronger reason for others to cite 0xSnow than another generic resort description.

## 5. Discovery and technical changes

### HTML and URL structure

Keep `bcbot/pages.py` and `bcbot/webreport.py` as the public rendering layer. Render a shared, validated public report into HTML, Markdown and JSON. There is no demonstrated need to migrate the app to a new frontend framework for this task.

| URL | Role / recommended behavior |
|---|---|
| `/` | Keep the interactive app; include a visible, crawlable link to the resort hub in initial HTML and a short description of the independent publisher. |
| `/resorts` and `/resorts/{region}` | Existing discovery and comparison pages. Show per-resort source type, as-of time and stale status; only compare equivalent metrics. |
| `/resorts/{slug}` | Existing daily edition or latest report, with that meaning stated explicitly. Self-canonical. |
| `/resorts/{slug}/{YYYY-MM-DD}` | Existing dated edition. Self-canonical; revision history and stable historical core. |
| `/resorts/{slug}/forecast` | Proposed only for a distinct, frequently updated forecast. Server-rendered summary, time/elevation, daily table and chart equivalent. |
| `/resorts/{slug}/guide` | Existing sourced evergreen facts; keep checked dates, official links and meaningful expiry warnings. |
| `/audit/{slug}` | Existing URL; add initial HTML results, methodology links, sample sizes and live/replay distinction. |
| `/audit/{slug}.json` and `.csv` | Proposed clean, sanitized read-only exports with explicit filters and bounded size. |
| `/methodology`, `/sources`, `/corrections` | Proposed publisher-level explanations, source/rights register and correction policy/history. |
| `/developers` and `/openapi.json` | Proposed documentation and API contract once the data semantics are stable. |

Hashes such as `/#today` are useful app state but are not independently fetchable server documents. Use real URLs for independently useful reports; keep hash navigation for the app itself. Do not create dozens of near-duplicate “best snow today” or question-variant pages. Google recommends real URLs for content views and warns against fragment-dependent indexing. [URL guidance](https://developers.google.com/search/docs/crawling-indexing/url-structure).

For charts, include a visible summary and equivalent HTML table with dates, units, elevation, source and missing values. Link from the chart to its exact data representation. These are useful to people, accessibility tools and retrievers. Avoid hidden crawler-only prose. Map alternative text must identify the actual map date and purpose; detailed run names belong in text, not in a giant image description.

### Metadata and structured data

Continue self-canonicals for distinct current and historical pages. Avoid canonicalizing all dated editions to “today,” which would erase the intended historical identity. Keep alternate representations linked to the human citation URL; a canonical header is a hint, not a promise that every assistant will consolidate JSON and HTML.

Use `WebSite` and `Organization` for 0xSnow, `WebPage` for a living report and `Article`/`BlogPosting` for a genuine dated edition. `SkiResort` can identify the subject; it must not imply that 0xSnow owns or represents the resort. Match all structured facts to visible content. [Schema.org SkiResort](https://schema.org/SkiResort).

For an actual downloadable audit dataset, `Dataset` can describe name, creator, measurement scope, temporal/spatial coverage, variable definitions and distributions. Add a license only where the rights are known. This supports a data discovery use case, not a generic promise of higher AI rankings. [Google Dataset documentation](https://developers.google.com/search/docs/appearance/structured-data/dataset).

Example report metadata pattern—not a claim that this proposed version is live:

```html
<title>Beaver Creek snow report — November 18, 2026 | 0xSnow</title>
<meta name="description" content="Beaver Creek's resort report lists 1 inch of new snow, updated Nov 18 at 5:32 AM MST. Grooming map: Nov 16; stale. Independent daily report.">
<link rel="canonical" href="https://snow.0xm.studio/resorts/beaver-creek/2026-11-18">
<link rel="alternate" type="application/json" href="https://snow.0xm.studio/resorts/beaver-creek/2026-11-18.json">
<link rel="alternate" type="text/markdown" href="https://snow.0xm.studio/resorts/beaver-creek/2026-11-18.md">
```

The image and description should not make a stale grooming map look current. Prefer an original report card for social previews, with its date and verified facts, subject to the rights review below.

### Robots, access controls and the firewall

The current robots file allows the main search, user-fetch and training tokens while disallowing `/admin`, `/stats` and `/api/`. This is permissive for discovery. It also explicitly allows training; that is an owner policy choice, not a search requirement. No robots change is necessary merely to launch this roadmap. [Current robots](https://snow.0xm.studio/robots.txt).

Do not open all of `/api/` to fix public audit exports. Put public reads on clean dedicated URLs and leave administrative operations protected. Robots rules and `noindex` are not authentication. Keep subscriptions, email addresses, push endpoints, admin metrics, tokens, raw logs and write operations outside the public contract.

Verify real bot identities using each provider’s published verification method; user-agent strings alone are spoofable. Review response codes, challenge rates and latency for public routes. Vercel offers distinct controls for verified bots and AI crawling. Allow the intended verified public reads without disabling protections on account or write routes. If Cloudflare later fronts the domain, inspect its rules separately; some firewall rules can act before bot settings. [Vercel bot management](https://vercel.com/docs/bot-management), [Cloudflare rule interaction](https://developers.cloudflare.com/ai-crawl-control/configuration/ai-crawl-control-with-bots/).

### Freshness, caching, sitemaps and IndexNow

The dynamic report code sets a five-minute browser cache, a ten-minute shared cache and up to one hour of stale-while-revalidate. Dated pages allow much longer shared caching and stale reuse. The sampled responses did not include ETag or Last-Modified on dynamic reports. Long cache reuse is acceptable for immutable editions; it is less suitable for content advertised as current. [Page response handler](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/api/page.py).

Define separate freshness budgets for the daily edition, current forecast, source observations and archive corrections. Derive an ETag from the published revision and Last-Modified from the actual content change. Use explicit stale status even when serving the most recent available data. A fast response does not establish a fresh source.

Sitemap `lastmod` should follow meaningful content revisions rather than merely the report date or every request. Include only canonical, useful, indexable pages. The current archive cap is 400 dates per resort; add archive pagination/indexing before it silently makes older public history harder to discover. Split sitemaps as scale requires. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

The IndexNow key file was reachable. The existing submission helper is gated on `VERCEL_ENV == production`, swallows errors and returns a status without a durable retry workflow. If the publisher moves to Render, that gate needs explicit review. Use a host-independent publication setting, submit changed public URLs after successful publication, record outcomes and retry transient failures. IndexNow is a change notification, not an indexing guarantee or a broadcast to all LLM providers. [Implementation](https://github.com/ysgjay/beaver-creek-grooming-bot/blob/413056ccf6a163ad4082d2107e50e28af2b21535/bcbot/pages.py), [IndexNow FAQ](https://www.indexnow.org/faq).

## 6. A trustworthy public data contract

The current JSON endpoint is a useful projection, but it omits source dates, source URLs for the weather values, time zone, forecast elevation, issue/run metadata and grooming stale status. It also inherits the resort/SNOTEL attribution problem. Fix these semantics before documenting them as a stable API.

The companion [public data contract example](public-report-contract-example.json) is an illustrative migration specimen built from the captured Beaver Creek report. It intentionally leaves unrecorded timestamps and observation-window boundaries null. It is not a production response or a claim that the proposed schema exists.

| Contract element | Rule |
|---|---|
| Identity | `schema_version`, resort ID, report ID, revision ID, canonical citation URL and representation URL. Preserve the alias relationship from Chair 0 / Snow Desk to 0xSnow in publisher information. |
| Time | Offset-bearing event timestamps plus IANA resort time zone; separate report generation, source publication, source check, observation interval and forecast issue/model initialization. Unknown timestamps remain null. |
| Observation | Typed metric, numeric value or null, explicit unit, measurement status, source ID and validity interval. Distinguish official reported snowfall from derived station depth rise. |
| Location | Coordinates and elevation for the forecast and every observation station, with elevation units and basis. Do not imply that the town, resort base, forecast point and station are interchangeable. |
| Forecast | Explicit valid start/end, expected coverage, available coverage, model/blend version, members/models used, transformations and uncertainty method. Version any method change. |
| Missingness | Enumerated reason, not an empty string or zero. Empty run lists need a coverage/status field explaining whether none were groomed or none were available. |
| Provenance | Stable source IDs, clickable official URLs, source type, raw timestamp string where necessary, attribution and rights scope. |
| History | Snapshot/revision metadata, correction reason and previous version. A rolling report URL and an immutable edition URL have different contracts. |
| Safety boundary | Public allowlist only. No delivery results, subscriber records, authentication material, internal exception strings or administrative controls. |

The sampled raw `data/latest.json` includes delivery-result counts and internal error fields. The clean report endpoint already filters much of this, which is the right direction. No subscriber emails or credentials were identified in the sampled payloads; that observation is not a complete privacy audit. Publish the explicit projection rather than a general-purpose dump of Blob or database records.

Expose bounded read operations: list supported resorts, fetch latest report, fetch a dated edition, fetch a forecast by point/band, and fetch audit results by period/lead/kind. Return useful errors for unsupported resorts, missing dates and invalid units. Use a versioned schema and stable error codes, sensible limits and conditional requests. Never accept arbitrary upstream URLs from callers.

An OpenAPI document would make these HTTP operations easier to integrate and validate. It is an API description, not a submission to an assistant’s search index. Choose a version supported by intended clients; OpenAPI 3.1 is a reasonable interoperability choice, not a claim to be the newest specification. [OpenAPI 3.1.1 specification](https://spec.openapis.org/oas/v3.1.1.html).

### When MCP is worth building

Build MCP after the contract is reliable and there is a concrete connection use case—for example, “compare my selected resorts using the freshest available report and disclose missing sources.” Start with read-only tools such as `list_resorts`, `get_resort_report`, `get_forecast` and `get_forecast_verification`. Return structured data and canonical human citation links. Reject unsupported dates and ambiguous units instead of guessing.

ChatGPT’s current plugin publishing documentation describes review and publishing into a directory; availability there does not guarantee prominent suggestions. Claude and Perplexity document explicitly added MCP connections, and Gemini documents configured function/tool integrations. These are additional access channels, not automatic organic discovery. [OpenAI publishing](https://developers.openai.com/plugins/deploy/app-review), [Claude connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Perplexity MCP](https://www.perplexity.ai/help-center/en/articles/11502712-local-and-remote-mcps-for-perplexity), [Gemini tools](https://aistudio.google.com/docs/function-calling).

Keep public weather reads separate from any future account actions. A read-only server does not need access to subscriber or admin data. Add authentication only for genuinely private features; do not expose a generic database query or arbitrary network-fetch tool. Measure actual connected usage before investing in directory distribution or elaborate assistant-specific interfaces.

## 7. Attribution, media rights and publisher trust

**Open-Meteo:** its data license permits reuse under CC BY 4.0 with attribution, a license link and indication of changes. Link the source and license, and describe transformations such as blending, snow conversion and calibration. API service terms are a separate question from the data license; the free service has usage and noncommercial restrictions. The site’s actual commercial status, usage and service agreement were not established. A self-hosted server also does not eliminate terms for public fallback/history calls. [Data license](https://open-meteo.com/en/licence), [service terms](https://open-meteo.com/en/terms).

**Resort maps and camera imagery:** the repository rehosts grooming-map derivatives and camera snapshots, and a grooming image is used for sharing metadata. Beaver Creek’s published website terms restrict copying/distribution of site materials. That is a concrete reason to check permissions; it does not establish the rights status of every Lumiplan PDF, Brown Rice image or existing agreement. Do not assume that public availability grants redistribution rights. Record the applicable source, owner, permission and allowed uses for each asset. Prefer official links or authorized embeds where reuse permission is unresolved. [Beaver Creek policies](https://www.beavercreek.com/policies?tc_1=5).

**Government sources:** preserve NOAA/NWS and NRCS attribution, measurement definitions and exceptions. NWS describes its information as public domain except where otherwise noted and cautions against misrepresenting altered products as official. A derived 0xSnow blend should be identified as such. Do not place one blanket CC BY license over third-party maps, photographs and all source data. [NWS disclaimer](https://beta.weather.gov/disclaimer/).

Add a short publisher page naming the responsible maintainer, scope, contact/correction path, funding model if relevant and independence from resorts. Explain how sources are selected, how frequently each is checked, what happens when a source fails and how corrections propagate to archives. Use real expertise and verifiable work; do not manufacture credentials, reviews or claims of affiliation. These steps improve accountability. Their exact effect on AI ranking remains unmeasured.

## 8. Prioritized implementation roadmap

Effort estimates are rough engineering days for someone familiar with the repository, excluding waiting for search engines, rights responses or a season of forecast outcomes. **Confidence refers to the value of the engineering change, not a promised citation lift.**

| Priority | Change and acceptance condition | Repository mapping | Impact / effort / confidence |
|---|---|---|---|
| **P0** | Remove silent SNOTEL substitution in claims of official snowfall. A Telluride fixture must say official data unavailable and label the station-derived metric separately across every format. | `bcbot/mailer.py`, `pages.py`, `webreport.py`, `llm.py`, `resorts.py`, `sources/snotel.py` | Critical factual reliability; 1–2 days; high. |
| **P0** | Introduce source/status/time fields and one public report projection. HTML/MD/JSON agree on value, unit, date, source and missingness. | New shared projection module; `bcbot/main.py`, `llm.py`, `webreport.py`, source adapters | High reliability and reuse; 2–4 days; high. |
| **P0** | Enforce exact forecast periods and coverage; never fill missing model data with zero. Handle gaps, partial days and zero wind/snow correctly. | `bcbot/forecast.py`, `sources/openmeteo.py`, report helpers | High numerical correctness; 1–3 days; high. |
| **P1** | Fix stale map metadata, “today” labels, full timestamps and hourly headings. Clearly distinguish daily edition from current forecast. | `bcbot/pages.py`, `webreport.py`, `llm.py`, app report presentation | High answer correctness; 1–2 days; high. |
| **P1** | Inspect Search Console/Bing ownership, indexing, Google AI inclusion inheritance and verified bot logs; record a baseline. | Existing owner tools; `docs/SEO.md`; hosting access logs | High diagnostic value; 0.5–1 day setup; high. |
| **P1** | Render audit results and caveats in initial HTML; expose clean public data exports and methodology. | `bcbot/audit.py`, `api/audit.py`, `api/page.py`, `public/audit.js`, `vercel.json` | High unique citation potential; 2–4 days; medium for visibility, high for accessibility. |
| **P1** | Make archive core snapshots immutable and corrections versioned. Publish complete manifests atomically. | `bcbot/pages.py`, `store.py`, daily publisher | High historical reliability; 2–4 days; high. |
| **P1** | Separate current/archive cache policies, add validators, accurate sitemap modification times and durable IndexNow outcomes. Review the Render production gate. | `api/page.py`, `bcbot/pages.py`, `worker.py`, `vercel.json`, `render.yaml` | Medium/high freshness reliability; 1–2 days; high. |
| **P1** | Complete attribution links and source/media permission register; use permitted preview imagery. | Renderer footers, image pipeline, `/sources`, documentation | High trust and operational clarity; 0.5–2 days plus external responses; high. |
| **P2** | Publish stable versioned JSON/OpenAPI documentation and machine-readable audit distributions. | `bcbot/llm.py`, new contract/schema, `api/page.py`, rewrites | Medium integration benefit; 1–3 days after P0; high. |
| **P2** | Build a small read-only MCP pilot only for a demonstrated connected-assistant use case. | Separate adapter over the public contract | Medium direct-user benefit, uncertain organic reach; 2–4 days; medium. |
| **Maintain** | Keep current sitemap, RSS, useful guides and `llms.txt`; remove drift. | `bcbot/pages.py`, `llm.py`, `facts.py`, `guide.py`, `docs/SEO.md` | Useful hygiene; under 0.5 day initial review; high for consistency, low for `llms.txt` ranking benefit. |

Suggested sequence:

1. **First work package:** attribution, missingness, timestamps and forecast period integrity; add regression fixtures for the observed failures.
2. **Second work package:** owner-tool baseline, public audit HTML, methodology, source attribution and stale-content fixes.
3. **Third work package:** stable snapshots/corrections, publication caching and notification reliability, versioned API documentation.
4. **After evidence of demand:** MCP pilot and directory distribution. Continue accumulating prospective forecast verification throughout.

Avoid a site rewrite, mass AI-generated landing pages, paid “AI citation submission” promises, an unrestricted public API, or claims that the current live sample proves forecast superiority.

## 9. Evaluation: measure discovery and answer correctness separately

### Establish the baseline

Use Search Console URL Inspection and indexing reports on representative current, dated, guide and audit URLs. Record Google-selected canonical, last crawl and exclusion reason where available. Review the Google generative AI inclusion setting and performance report. In Bing Webmaster Tools, review indexing, IndexNow outcomes and AI Performance. Repository notes say the properties were verified, but this research did not confirm current account state.

Log verified crawler requests by provider, public route, timestamp, response code, latency and challenge outcome. Separate ordinary visitors, claimed user agents and authenticated bot identities. Track assistant referral traffic where present, but recognize that citations need not produce clicks and referrers can be absent. Do not retain unnecessary user query or identity data.

Run the same prompt set in ChatGPT search, Google AI search/Gemini as separately identified surfaces, Microsoft Copilot, Perplexity and Claude web search. Record product/mode, date, locale, account conditions, whether web search ran, exact answer, citation URLs and the report revision available at that moment. Repeat each prompt three times in fresh conversations; repeat the batch after meaningful changes and after enough recrawl time. Avoid presenting a single successful answer as a stable result.

Keep three experiment types separate:

- **Organic:** no brand or URL supplied. Measures whether the site is discovered and selected.
- **Named-source:** ask for 0xSnow by name. Measures entity recognition and retrieval.
- **Direct URL / connected tool:** explicitly provide a page or connection. Measures access and faithful extraction, not organic discovery.

### Query set

| Test prompt or fixture | What a correct result must preserve |
|---|---|
| “How much new snow did Beaver Creek report today?” | Official source, report date/time, inches, no station substitution. |
| “Which Beaver Creek runs were groomed this morning?” | Actual current source date; no invented runs from an empty or stale map. |
| “How much snow did Telluride get in the last 24 hours?” | Official data versus Alta Lakes derived depth rise; explicit missing source if necessary. |
| “Where has the most new snow in Colorado today?” | Comparable observation periods and sources; excludes or labels incompatible estimates. |
| “Compare Beaver Creek and Vail snowfall over the next five days.” | Exact date window, forecast points/elevations, issue times and model ranges. |
| “What is Beaver Creek’s forecast at the base versus upper mountain?” | Correct point/band values; no mixing elevation-specific temperature with unrelated snow totals. |
| “Will Beaver Creek definitely get at least six inches this weekend?” | No certainty from an uncalibrated range; defines weekend dates and uncertainty. |
| “What did 0xSnow forecast for Beaver Creek on November 17, 2026?” | Forecast as issued then, not a later replay or updated forecast. |
| “How accurate has 0xSnow’s snow forecast been?” | Live versus replay, metric, sample size, period and limitations. |
| “Is 0xSnow more accurate than the plain model average?” | Paired evidence or insufficient-evidence answer; no unsupported superiority. |
| “What time do Beaver Creek lifts open, and when was that checked?” | Official sourced guide fact, checked date and seasonal caveats. |
| “Does my pass have holiday blackout dates at these resorts?” | Exact named pass product, season and resort applicability, with current official source. |
| “Use this dated 0xSnow URL and summarize snow and grooming.” | Preserves edition date and stale map date; cites the dated URL. |
| “Find Chair 0 Snow Desk’s Beaver Creek report.” | Recognizes the 0xSnow rename and reaches the canonical current site. |
| Missing forecast-day fixture | Returns partial/unavailable total with missing dates, not a zero or shifted five-day interval. |
| Old report at local midnight / DST fixture | Correct resort-local date and offset; does not call yesterday’s values “today.” |
| Zero / trace / missing fixture | Distinguishes all three consistently across HTML, Markdown, JSON and tools. |
| Corrected archive fixture | Identifies revised value, revision time and prior edition; old citations remain interpretable. |

The capture date is a preseason date for some resorts; distinguish parser/citation regression fixtures from a later test of in-season organic demand. Refresh “today” prompts and expected values at each run. Never judge a historical prompt against the current live page alone.

### Success measures and release gates

| Measure | Proposed target / interpretation |
|---|---|
| Public fact consistency | 100% agreement among formats for value, unit, source, valid period, stale status and citation URL on the fixture set. Critical attribution errors block release. |
| Missing-data behavior | All gap/zero/trace/not-integrated tests pass. No missing input silently becomes zero. |
| Source freshness | Every volatile value has an as-of or explicit unknown status. Successful publication does not reset the source’s age. |
| Publication propagation | Proposed service objective: 95% of successful current-report publications visible at public endpoints within five minutes. Tune cache policy to this target; measure source-to-ingest delay separately. |
| Retrieval reliability | Track verified public-bot 2xx/304 success and challenges; investigate any persistent 403/429/5xx by provider. Do not treat a spoofed-UA test as the metric. |
| Indexing | Track eligible canonical URLs submitted, indexed and excluded by reason. Index coverage is diagnostic, not a guarantee of AI inclusion. |
| Organic citation share | Fraction of eligible organic test answers citing 0xSnow, reported by provider and query group with repetitions. Baseline first; no defensible fixed uplift is available yet. |
| Answer fidelity | Score every substantive cited claim against the timestamped source. Require zero critical source/date/observed-versus-forecast confusions in release tests; report residual provider errors honestly. |
| Forecast evidence | Publish paired sample size, dates, metrics and uncertainty. Do not promote “better accuracy” until the held-out live comparison supports the precise claim. |
| Connected utility | For an MCP pilot, measure successful grounded answers, correct citations, freshness and real repeat use. Do not count it as organic search growth. |

## 10. Remaining unknowns and final recommendation

The unresolved operational questions are actual indexing status; Google AI control inheritance; verified provider crawl traffic; hosting firewall configuration; whether Render is live; precise source observation windows and SNOTEL time basis; model initialization metadata; permissions for rehosted media; and consumer-assistant citation performance. These are explicitly outside what the captured responses prove.

The web search tool did not return the site in a small set of exact-domain searches and could not fetch some live URLs, while ordinary HTTP and the browser could. Those results are limitations of this research channel, not proof that the site is globally unindexed or blocks AI crawlers.

**Recommended investment:** make 0xSnow the source that can explain each number—who reported it, what it measures, where and when it applies, how fresh it is and how well past forecasts held up. The existing HTML foundation is sufficient to start. Fix the concrete reliability defects, expose the original audit evidence, verify real crawler access and measure citations. Add connected-assistant distribution after the underlying information can be trusted.**
