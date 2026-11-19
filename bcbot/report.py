"""Compose the daily report: email subject, plain text (email text part, ntfy) and app push payload."""
from datetime import date, datetime

from . import config


def resort_name(day):
    return (day or {}).get("resort_name") or config.RESORT_NAME or "Beaver Creek"


def app_url(day=None):
    """The app, opened on this report's resort (Beaver Creek is the app's default)."""
    from .resorts import DEFAULT
    slug = (day or {}).get("resort_slug") or config.RESORT or DEFAULT
    return config.DASHBOARD_URL if slug == DEFAULT else f"{config.DASHBOARD_URL.rstrip('/')}/?resort={slug}"


def mmdd(d):
    """Dates read as month/day everywhere (Young's preference): 11/15."""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d.month}/{d.day}"


def map_date(text):
    """The grooming PDF's "November 15, 2026" as 11/15 (unchanged if it doesn't parse)."""
    try:
        return mmdd(datetime.strptime(text.strip(), "%B %d, %Y").date())
    except (AttributeError, ValueError):
        return text


def pretty_date(d):
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d.strftime('%a')} {mmdd(d)}"


def short_date(d):
    return mmdd(d)


def _in(x):
    return "–" if x is None else f'{x:.0f}"' if x >= 1 or x == 0 else f'{x:.1f}"'


def _hour_label(iso):
    h = datetime.fromisoformat(iso).hour
    return f"{(h % 12) or 12}{'a' if h < 12 else 'p'}"


def compose(day):
    """`day` is the record written to data/days/<date>.json."""
    fc = day.get("forecast") or {}
    obs = day.get("observed") or {}
    resort = day.get("resort") or {}
    lines = [f"🎿 {resort_name(day)} {'Snow' if (day.get('grooming') or {}).get('none') else 'Grooming'} — {pretty_date(day['date'])}"]
    g = day.get("grooming", {})
    if not g.get("new_map", True) and not g.get("none"):
        lines.append("(No groomed runs reported yet today)" if g.get("list") else "(No new grooming map posted yet today)")
    runs = g.get("runs") or {}
    if runs.get("groomers_of_the_day"):
        lines.append("⭐ Groomers of the day: " + ", ".join(runs["groomers_of_the_day"]))
    if runs.get("overnight"):
        lines.append("🚜 Groomed overnight: " + ", ".join(runs["overnight"]))
    if runs.get("morning"):
        lines.append("☀️ Morning grooming: " + ", ".join(runs["morning"]))
    for area, names in (runs.get("areas") or {"Groomed": runs.get("groomed") or []}).items():
        if names:
            lines.append(f"🚜 {area}: " + ", ".join(names))

    snow = []
    if resort.get("last_24h_in") is not None:
        snow.append(f"Resort 24h: {_in(resort['last_24h_in'])}")
    if obs.get("snow_in") is not None:
        snow.append(f"SNOTEL 24h: {_in(obs['snow_in'])}")
    if snow:
        lines.append("❄️ " + " | ".join(snow))

    if fc.get("days"):
        lo, hi = fc.get("next_1_5_range", [None, None])
        lines.append(f"📈 Next 5 days: {_in(fc['next_1_5'])} (range {_in(lo)}–{_in(hi)})")
        lines.append(f"🔭 Days 6–10: {_in(fc['next_6_10'])}")
        best = max(fc["days"], key=lambda x: x["snow"])
        if best["snow"] >= 1:
            lines.append(f"🏔️ Snowiest day: {short_date(best['date'])} — {_in(best['snow'])}")

    hours = (day.get("hourly") or {}).get("hours", [])
    if hours:
        lines.append("")
        lines.append("🌡️ Today:")
        for h in hours[::2][:6]:
            wind = f"{h['dir']} {h['wind']}" + (f" g{h['gust']}" if h.get("gust") else "")
            snow_txt = f", {h['snow']}\" snow" if h.get("snow") else ""
            lines.append(f"{_hour_label(h['time'])}: {h['temp']}° (feels {h['feels']}°), {wind} mph{snow_txt}")

    lines.append("")
    lines.append(f"📊 Forecast, cams & history: {app_url(day)}")
    return "\n".join(lines)


def subject(day):
    """The inbox line carries the morning's numbers: 'Beaver Creek: 2" new, 14 groomed, gusts to 31 mph'.

    No date: the inbox shows it. At most three facts, in order of what matters most that morning.
    """
    from .mailer import groomed_runs, ski_hours
    fc = day.get("forecast") or {}
    g = day.get("grooming") or {}
    rs = day.get("resort") or {}
    n = len(groomed_runs(g.get("runs") or {}))
    r24 = rs.get("last_24h_in", (day.get("observed") or {}).get("snow_in"))
    parts = []
    if day.get("preseason") and not n:
        parts.append(f"Opens {mmdd(config.OPENING_DAY)}")
    if r24 is not None and r24 >= 0.5:
        parts.append(f"{_in(r24)} new")
    if n:
        parts.append(f"{n} groomed")
    elif not g.get("none") and not g.get("new_map", True) and not day.get("preseason"):
        parts.append("no new grooming map yet")
    gust = max([h.get("gust") or 0 for h in ski_hours(day)] or [0])
    if gust >= 30:
        parts.append(f"gusts to {gust} mph")
    if fc.get("next_1_5") is not None and fc["next_1_5"] >= 1:
        parts.append(f"{_in(fc['next_1_5'])} next 5 days")
    if not parts:
        parts.append("Snow report" if g.get("none") else "Grooming map")
    return ("Test · " if day.get("test") else "") + f"{resort_name(day)}: " + ", ".join(parts[:3])


def push_payload(day, map_url):
    """Short notification: what's groomed and what's coming. Tapping opens Today."""
    fc = day.get("forecast") or {}
    runs = (day.get("grooming") or {}).get("runs") or {}
    groomed = runs.get("groomers_of_the_day", []) + runs.get("overnight", []) + runs.get("morning", []) + runs.get("groomed", [])
    rs = day.get("resort") or {}
    r24 = rs.get("last_24h_in", (day.get("observed") or {}).get("snow_in"))
    body = []
    if day.get("powder"):
        body.append(day["powder"])
    if groomed:
        body.append("Groomed: " + ", ".join(groomed[:6]) + ("…" if len(groomed) > 6 else ""))
    body.append(f"New snow {_in(r24)} · Next 5 days {_in(fc.get('next_1_5'))}")
    payload = {"title": ("Test · " if day.get("test") else "") + f"{resort_name(day)} · {short_date(day['date'])}", "body": "\n".join(body),
               "url": app_url(day), "tag": f"report-{day.get('resort_slug') or 'beaver-creek'}-{day['date']}"}
    if map_url:
        payload["image"] = map_url
    return payload


def powder_alert(fc, name=None):
    """Short alert text when the next 48h blend crosses the powder threshold, else None."""
    days = (fc or {}).get("days", [])[:2]
    total = sum(d["snow"] for d in days)
    if total >= config.POWDER_ALERT_INCHES:
        return f"❄️ Powder alert: {total:.0f}\" forecast for {name or config.RESORT_NAME} in the next 48 hours."
    return None
