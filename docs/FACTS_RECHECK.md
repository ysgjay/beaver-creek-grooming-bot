# Scheduled facts re-check (runbook for the daily Claude task)

The `/api/facts` cron (14:30 UTC) reads every source page. A fact whose page read cleanly with no change is
confirmed in Blob with no PR. Everything else goes in the **queue**:
- facts whose page changed (`reason: "changed"`, with the lines `added` and `removed`);
- facts that are due and couldn't be confirmed: the page failed, or the value is "not posted".

This task works the queue and opens **one PR**. Young merges it. Never merge it yourself.

## Steps
1. **Read the queue.**
   - Fetch `https://snow.0xm.studio/api/facts?queue=1` with the Vercel connector's `web_fetch_vercel_url` (this
     container can't reach the site directly).
   - If that fails, run `python -m bcbot.facts due` and use that list, with every item treated as "due".
   - If the queue is empty, stop. Make no PR.
2. **Re-read each source page, at most 40 items, changes first.** Use WebFetch. epicpass.com blocks WebFetch, so
   skip it and list it in the PR. For each item, find the sentence on the page that gives the value.
3. **Update the data files only where the value really changed or was newly posted.**
   - Shared facts: edit `announced`, `lift_hours`, `trail_maps`, `epic_access` or `ikon_access` in
     `bcbot/facts_data/shared.json`. Bump `checked_shared` only if you re-read the Epic or Ikon page.
   - Hand-checked facts: edit `bcbot/facts_data/curated.json` (resort, then kind).
   - Add `"evidence": "<quote>"` to each fact you change in curated.json.
   - Keep the JSON sorted and indented the way it is (`json.dumps(..., indent=1, sort_keys=True, ensure_ascii=False)`).
   - Don't edit `bcbot/facts.py`.
   - Set `checked` to today. Dates are ISO in code and MM/DD in prose.
   - Write values in the house style: plain sentences, "9 AM to 4 PM", no copied marketing text.
   - If a page still says the same thing, change nothing. The watch confirms those on its own.
4. **Flag for a closer look and don't change.** Any date moving more than 14 days, any value you can't back with a
   quote, any page that looks like last season's, and any change of `value` to None. List these under
   "Needs eyes" in the PR.
5. **Test.** Run `python -m pytest -q tests/test_facts.py`. `test_fact_values_pass_sanity_checks` must pass.
   Then run the full suite once.
6. **Open the PR.**
   - Branch `claude/facts-recheck-YYYY-MM-DD`, title "Resort facts re-check MM/DD".
   - Body: a table of resort, fact, old value, new value and the verbatim source quote (under 25 words), then
     "Needs eyes", then pages that failed.
   - End with the repo's PR attribution lines.
7. **Report.** End with a 2-line summary: how many facts changed, how many need eyes, and the PR link.

## Rules
- Sources are the resort's own pages, epicpass.com or ikonpass.com. No third-party sites except as a lead.
- Link to trail maps, never copy the art.
- If an operator has asked for a takedown (see `docs/RESORT_FACTS.md`), don't re-add their content.
- Bill nothing new. Add no keys or secrets.
