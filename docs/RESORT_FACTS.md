# Resort facts: how to add or re-check a resort

The guide page at `/resorts/<slug>/guide` (and its twin `/resorts/<slug>/guide.md`) shows up to 8 facts per resort:
opening day, closing day, lift hours, trail map, passes, blackout dates, lift tickets and lessons. Every fact carries
the official page it came from and the date someone read it. The page title, heading and FAQ follow whichever facts a
resort has, so a resort can go live with 2 facts and gain the rest later.

All of it lives in `bcbot/facts.py`.

## Where facts come from

1. **Shared tables (one source covers many resorts).** Read once, used everywhere.
   - `EPIC_ACCESS`: days on the Epic Pass and Epic Local Pass per resort (epicpass.com).
   - `EPIC_PEAK_DATES`: Epic peak restricted dates (they apply to the Local and Day passes where noted).
   - `IKON_ACCESS`: days on the Ikon Pass, Ikon Base Pass and Session Pass per resort (ikonpass.com compare page).
   - `IKON_BASE_DATES`: Ikon Base Pass blackout dates.
   - `ANNOUNCED`: opening and closing dates from the Vail Resorts release, the Ikon dates page or the resort.
   - `TRAIL_MAPS`: official trail map pages.
   - `LIFT_HOURS`: lift hours from each resort's own hours page (WebFetch reads most of them, Vail Resorts sites included).
   When a pass changes, edit the table once and set `CHECKED_SHARED` to the day you read it.
2. **`CURATED` (hand-checked per resort).** Anything read from the resort's own site: hours, ticket prices, lessons,
   exact map PDFs. A `CURATED` entry wins over the shared tables for that fact.

`FACTS = _build()` merges the two. Don't edit `FACTS` directly.

## Adding facts for a resort

1. Run `python -m bcbot.facts` to list every missing fact and where to read it. Resorts with a known operator get
   the exact page; others say "find the official page".
2. Open the page and read the fact yourself. **Never guess a URL or a value.** If a link redirects to another domain
   or the page won't load, leave the fact out.
3. Add it to `CURATED[slug]` in the same shape as Beaver Creek or Copper:
   `{"value": ..., "note": ..., "checked": "YYYY-MM-DD", "source": url, "source_name": "Resort: Page title"}`.
   Dates are ISO in code and shown as MM/DD. Use `"value": None` plus a `note` when the resort posts no fixed answer
   (for example, ticket prices that change by date).
4. Trail maps: link to the resort's page or PDF. Never copy or rehost the map art. List every map the resort posts in
   `maps` (`_map()` in `facts.py`): big mountains have several (Vail: Front Side, Back Bowls, Blue Sky Basin;
   A-Basin: 4). Each map can carry a high-res `image` that the guide page shows straight from the resort's server
   (`referrerpolicy="no-referrer"`, never downloaded to ours) and a `pdf`. Vail Resorts images come from
   `scene7.vailresorts.com/is/image/vailresorts/<file>?wid=4000`, using the same file name as the PDF. Check that an
   image actually loads in a browser before adding it.
5. Run `pytest -q tests/test_facts.py`. One test checks that every fact has a source and checked date.

## Owner view

`/admin` has a "Resort facts" table (`facts.grid()` via `/api/stats`): every resort by every fact, filled, not posted
by the resort, or missing, with the checked date, and amber or red when a re-check is due or stale. Hover a cell for
the value and source. "Download CSV" exports the full table (values, sources, next check date) for Excel.

## Operator page patterns

Resorts run by the same company share a site layout, so `OPERATOR_PAGES` maps fact kinds to paths:

| Operator | Resorts | Hours | Trail map | Tickets | Lessons |
|---|---|---|---|---|---|
| Vail Resorts | Beaver Creek, Vail, Breckenridge, Keystone, Crested Butte, Park City | `/explore-the-resort/about-the-resort/hours-of-operation.aspx` | `/the-mountain/about-the-mountain/trail-map.aspx` | `/plan-your-trip/lift-access/tickets.aspx` | `/plan-your-trip/ski-and-ride-lessons.aspx` |

Add a new operator once you've confirmed its paths on two of its resorts.

## Reading the sites

- Vail Resorts sites (beavercreek.com, keystoneresort.com, parkcitymountain.com) block automated page reading. Use a
  real browser and read the page by eye; Park City also blocks screenshots.
- epicpass.com reads fine in a browser but blocks crawlers.
- coppercolorado.com and ikonpass.com can be fetched directly.

## Re-check schedule

`interval_days()` sets how often each kind is re-read: closing day every 2 days from 3/1, opening day every 2 days
from 9/15 to 11/30, passes and blackout dates every 2 days from 3/1 to 4/30, ticket prices weekly in season, lessons
every 2 weeks in early season, otherwise monthly. The daily `/api/facts` cron fingerprints every source page and
alerts when a page changes or a fact is overdue. `python -m bcbot.facts due` lists overdue facts. Nothing changes on
the site automatically: a person (or Claude) re-reads the page and updates the table.

## The daily watch and the re-check queue

`watch()` (run by the `/api/facts` cron at 14:30 UTC) reads every source page in parallel and writes
`data/facts/status.json`:

- **Changes need two reads.** A page counts as changed only when its date and hour lines differ from the last confirmed
  read on two runs in a row, so one-day promos and countdowns don't flag it. `prev_lines` and `lines` keep the before
  and after.
- **Bot walls are errors.** A challenge page, a captcha or a page with no date or hour lines at all counts as a failed
  read (`errors`, `error_at`), never as a change. After 3 failed days the URL is listed in `failing` and the alert
  names it.
- **`queue` is the work list.** It holds every due fact plus every fact whose page changed after its `checked` date,
  with the lines `added` and `removed`. Changes sort first. A fact leaves the queue once it is re-checked (its
  `checked` date moves past the change).
- **Read-only access:** `GET /api/facts?queue=1` returns `queue` and `failing` without a key. The scheduled re-check
  task reads it from there. It holds public page text only.
