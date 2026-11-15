"""Score every model against SNOTEL and learn per-model bias + skill weights.

For each observed day D we look up the forecasts issued on D, D-1 and D-2 (lead 0-2)
from data/forecasts/ and compare liquid precip (clean, no snow-ratio guessing) with
the SNOTEL precip gauge. Two numbers come out per model:
  bias_ratio  observed / forecast liquid over the window (clamped 0.6-1.6). >1 = model runs dry here.
  skill       median model MAE / this model's MAE (clamped 0.5-2). Multiplies the blend weight.
The NWS gridded forecast has no liquid field, so it is scored on snow vs snow-depth gain
for display only and keeps its fixed weight.
"""
from datetime import date, timedelta

from . import config
from .util import r1, read_json

MIN_DAYS = 5
WINDOW_DAYS = 45
WET = 0.03  # inches liquid: ignore bone-dry days where everyone is "right"


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def compute(observed_daily, forecasts_dir=None, today=None):
    forecasts_dir = forecasts_dir or (config.DATA_DIR / "forecasts")
    today = today or date.today()
    pairs = {}        # model -> [(fcst_liquid, obs_liquid)]
    snow_pairs = {}   # model -> [(fcst_snow, obs_snow)]
    history = []      # blend vs observed, for the dashboard
    cache = {}

    def issued(d):
        if d not in cache:
            cache[d] = read_json(forecasts_dir / f"{d}.json")
        return cache[d]

    start = today - timedelta(days=WINDOW_DAYS)
    for d_str, obs in sorted(observed_daily.items()):
        d = date.fromisoformat(d_str)
        if d < start or d >= today:
            continue
        obs_liq = obs.get("precip_in")
        obs_snow = max(0.0, obs.get("depth_change_in") or 0.0)
        lead1 = issued((d - timedelta(days=1)).isoformat())
        if lead1:
            blend_day = next((x for x in lead1.get("days", []) if x["date"] == d_str), None)
            if blend_day:
                history.append({"date": d_str, "forecast": blend_day["snow"], "low": blend_day["low"],
                                "high": blend_day["high"], "observed": r1(obs_snow), "observed_liquid": obs_liq})
        for lead in range(3):
            fc = issued((d - timedelta(days=lead)).isoformat())
            if not fc:
                continue
            for m, daily in fc.get("raw", {}).items():
                v = daily.get(d_str)
                if not v:
                    continue
                if v.get("liquid") is not None and obs_liq is not None:
                    if v["liquid"] >= WET or obs_liq >= WET:
                        pairs.setdefault(m, []).append((v["liquid"], obs_liq))
                if v.get("snow") is not None:
                    snow_pairs.setdefault(m, []).append((v["snow"], obs_snow))

    stats = {}
    for m, ps in pairs.items():
        mae = sum(abs(f - o) for f, o in ps) / len(ps)
        f_sum, o_sum = sum(f for f, _ in ps), sum(o for _, o in ps)
        stats[m] = {"n": len(ps), "mae_liquid_in": round(mae, 3),
                    "bias_ratio": round(_clamp(o_sum / f_sum, 0.6, 1.6), 2) if f_sum > 0.05 else 1.0}
    maes = sorted(s["mae_liquid_in"] for s in stats.values() if s["n"] >= MIN_DAYS)
    median = maes[len(maes) // 2] if maes else None
    for m, s in stats.items():
        if s["n"] < MIN_DAYS or not median:
            s["bias_ratio"], s["skill"] = 1.0, 1.0
        else:
            s["skill"] = round(_clamp(median / max(s["mae_liquid_in"], 0.005), 0.5, 2.0), 2)
    for m, ps in snow_pairs.items():
        s = stats.setdefault(m, {"n": 0, "bias_ratio": 1.0, "skill": 1.0})
        s["mae_snow_in"] = round(sum(abs(f - o) for f, o in ps) / len(ps), 2)
        s["n_snow"] = len(ps)

    return {"updated": today.isoformat(), "window_days": WINDOW_DAYS, "models": stats,
            "history": history[-30:]}
