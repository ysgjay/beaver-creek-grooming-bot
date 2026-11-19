# 0xSnow SEO guideline

Internal rules for building and tuning public pages (`/resorts/*`, `/passes/*`). Read this before you add a page,
change a title or rename a heading. Research behind it: the "0xSnow SEO opportunities" doc (Google Trends and
autocomplete pulled 11/19/2026).

## 1. Match the words people search

Google Trends, US, 5-year average, "vail snow report" = 100:

| Query | Index | What we build |
| --- | --- | --- |
| park city / breckenridge snow report | 86 to 90 | Resort report page |
| ikon / epic pass blackout dates | 50 to 54 | `/passes/<pass>-blackout-dates` |
| keystone / beaver creek / copper snow report | 28 to 41 | Resort report page |
| vail trail map | 39 | Trail map link on every resort page (link, never copy the art) |
| is vail open, vail webcam | 22 each | Opening facts on the guide page; cams link |
| ski resorts open now | 8 | State table (low priority) |
| vail vs aspen | 4 | Skip |
| colorado ski resorts opening dates | 1 | Facts only, no standalone page |
| vail grooming report | 1 | Grooming section + PDF link (our edge, not our headline) |

Rules that follow:

- **Lead with "snow report".** Titles and H1s start with `<Resort> snow report`. Grooming goes after the colon:
  `Vail snow report today (11/19): grooming and forecast | 0xSnow`.
- **Put the date in the title** as MM/DD. People search "today", and a visible date shows the page is fresh.
- **Use the searcher's word first and the official word second.** Example: "blackout dates" in the H1, and Epic's
  term, "restricted peak dates", in the title and body.
- **Answer the next search on the page.** Under each report's lead there is one line of links: trail map, webcams,
  grooming map PDF, pass blackout dates, and hours and opening day (`_quick_links` in `bcbot/pages.py`).

## 2. Page types and their jobs

| Page | URL | Target query | Must have |
| --- | --- | --- | --- |
| Resort report (today) | `/resorts/<slug>` | `<resort> snow report`, `... today` | Date in title and H1, numbers in the first sentence, quick links, WebPage + BreadcrumbList JSON-LD |
| Resort report (archive) | `/resorts/<slug>/<date>` | `<resort> snow report <date>` | BlogPosting JSON-LD, its own canonical, never edited after the day |
| Resort guide | `/resorts/<slug>/guide` | trail map, hours, opening/closing day, passes | Every fact sourced and dated (`bcbot/facts.py`), FAQ JSON-LD |
| State table | `/resorts/colorado`, `/resorts/utah` | `<state> snow report today` | Sorted by new snow, faded rows for stale data |
| Pass blackout dates | `/passes/epic-blackout-dates`, `/passes/ikon-blackout-dates` | `<pass> blackout dates`, `... restricted dates` | "Is today a blackout date?" answer at the top, dates table, resort table, FAQ JSON-LD |
| Hub | `/resorts` | brand + "ski resort snow reports" | Links to every page above |

Before you add a new page type, check it has a query with real demand (index 5 or more in the table above, or a
fresh Trends check). Don't make one page per question. Put the answer on the page that already ranks.

## 3. Writing rules

- The first sentence holds the numbers: new snow, base and runs groomed. Never write a clause without its number
  (`summary()` enforces this).
- Dates are MM/DD everywhere, with the weekday in front where space allows ("Fri 11/27").
- One H1 per page. H2s name the thing people search ("Grooming", "Snow forecast", "2026/27 dates").
- Never copy resort art (trail maps, logos). Link to it with `rel="nofollow"`. Cams use the resort's own image URL.
- Every fact carries a source link and a checked date. Re-check cadence is in `docs/RESORT_FACTS.md`.
- Don't say "Open Snow" or anything close to it. The brand is 0xSnow, written exactly that way.

## 4. Technical checklist for any new public page

1. Render it as server HTML from `bcbot/pages.py` through `shell()`, which gives the title, description,
   canonical, OG tags, RSS and the Markdown alternate.
2. Add a clean URL rewrite in `vercel.json` and a route in `api/page.py`.
3. Add it to `sitemap()`. New pages already get an IndexNow ping when a post is sent; for one-off pages, submit the
   URL in Search Console.
4. Add JSON-LD that fits the page (WebPage, BlogPosting, FAQPage or BreadcrumbList) and make sure it parses (tests do).
5. Thin pages (no data yet) get `noindex=True`.
6. Add a test to `tests/test_pages.py` that checks the exact title and the H1.
7. Set the cache to match: today pages `max-age=300`, archives a day or more, evergreen pages about an hour.

## 5. Seasonal calendar

Publish or refresh 2 to 4 weeks before each spike.

| When | Spike | Action |
| --- | --- | --- |
| Aug to Oct | Pass questions, next season's opening dates | Roll dates and pass tables to the new season |
| Nov | Snow report searches start (about a quarter of peak); Thanksgiving blackout dates | Check pass pages before 11/27 |
| Dec to Feb | Snow report at peak; blackout searches peak in Dec | Keep reports on time; nothing structural ships the week of 12/22 |
| Mar | Snow report at half; closing day searches | Closing dates re-checked every 2 days from 3/1 |
| Apr to Jul | Near zero | Build new page types, then refresh the research in Trends |

## 6. Measuring

- Search Console (`sc-domain:snow.0xm.studio`, signed in as jay@0xm.studio): check Queries and Pages every 2 weeks.
  Each title should rank for the query it targets.
- Re-pull Trends once a season. It runs from the jay@0xm.studio Chrome (it's blocked from cloud sessions).
- Skip paid keyword tools until Search Console shows traffic worth tuning.
