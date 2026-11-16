"""Score every model against SNOTEL and learn per-model bias + skill weights.

For each observed day D we look up the forecasts issued on D, D-1 and D-2 (lead 0-2)
from data/forecasts/ and compare liquid precip (clean, no snow-ratio guessing) with
the SNOTEL precip gauge. Two numbers come out per model:
  bias_ratio  observed / forecast liquid over the window (clamped 0.6-1.6). >1 = model runs dry here.
  skill       median model MAE / this model's MAE (clamped 0.5-2). Multiplies the blend weight.
The NWS gridded forecast has no liquid field, so it is scored on snow vs snow-depth gain
for display only and keeps its fixed weight.

Two things keep the correction useful when there is little recent data:
  terrain priors  each model's observed / forecast liquid over last winter (`terrain_priors`).
                  bias_ratio starts there and moves to the recent ratio as wet days add up.
  snow_cal        the blend's snow total against the resort's own reported snowfall, since
                  the resort's stake, not the Vail gauge, is what skiers compare us with.
"""
from datetime import date, timedelta

from .util import r1

MIN_DAYS = 5
WINDOW_DAYS = 45
WET = 0.03  # inches liquid: ignore bone-dry days where everyone is "right"
BIAS_CLAMP = (0.8, 1.25)  # kept narrow: one winter at one gauge is thin evidence
LEAD_GROUPS = ("short", "mid", "long")
PRIOR_WEIGHT_IN = 1.0   # the prior counts as this many inches of forecast liquid
PRIOR_MIN_DAYS = 30
CAL_WEIGHT_IN = 6.0     # snow calibration starts at 1.0 and counts as this many inches of snow
CAL_CLAMP = (0.7, 1.4)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _lead_priors(prior):
    """{short, mid, long} from a prior that may be a bare number, a dict, or missing."""
    if isinstance(prior, dict):
        short = prior.get("short", 1.0)
        return {g: _clamp(prior.get(g, short), *BIAS_CLAMP) for g in LEAD_GROUPS}
    return {g: _clamp(1.0 if prior is None else prior, *BIAS_CLAMP) for g in LEAD_GROUPS}


def _by_lead(prior, short_ratio):
    """Recent scoring covers days 0-2 only, so the longer ranges keep their own prior and
    move by the same factor the short range moved from its prior."""
    lp = _lead_priors(prior)
    factor = short_ratio / lp["short"] if lp["short"] else 1.0
    out = {"short": short_ratio}
    for g in LEAD_GROUPS[1:]:
        out[g] = round(_clamp(lp[g] * factor, *BIAS_CLAMP), 2)
    return out


def terrain_priors(model_daily, observed_daily):
    """Per-model observed / forecast liquid over a past season: {model: {bias_ratio, n, ...}}.

    Coarse global models smooth the mountains away and run dry on the upper mountain;
    high-resolution ones mostly don't. This measures it, model by model.
    """
    out = {}
    for m, daily in model_daily.items():
        pairs = [(f, observed_daily[d]) for d, f in daily.items() if f is not None and d in observed_daily]
        f_sum, o_sum = sum(f for f, _ in pairs), sum(o for _, o in pairs)
        if len(pairs) < PRIOR_MIN_DAYS or f_sum < 1.0:
            continue
        out[m] = {"bias_ratio": round(_clamp(o_sum / f_sum, *BIAS_CLAMP), 2), "n": len(pairs),
                  "forecast_in": round(f_sum, 1), "observed_in": round(o_sum, 1)}
    return out


def prior_season(today):
    """The last finished cold season (Nov 1 - Apr 30) before `today`."""
    end_year = today.year if today.month >= 5 else today.year - 1
    return date(end_year - 1, 11, 1), date(end_year, 4, 30)


def compute(observed_daily, load_forecast, today=None, priors=None, resort_daily=None):
    """`load_forecast(date_str)` returns the forecast document issued that day, or None.

    `priors` is {model: {lead group: bias_ratio}} from `terrain_priors` (a bare number
    means the same prior at every range). `resort_daily` is {date: inches}
    of the resort's 24-hour snowfall as reported on the morning of that date.
    """
    today = today or date.today()
    priors = priors or {}
    resort_daily = resort_daily or {}
    cal_fc = cal_obs = 0.0
    cal_n = 0
    pairs = {}        # model -> [(fcst_liquid, obs_liquid)]
    snow_pairs = {}   # model -> [(fcst_snow, obs_snow)]
    history = []      # blend vs observed, for the dashboard
    cache = {}

    def issued(d):
        if d not in cache:
            cache[d] = load_forecast(d)
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
                # The resort's morning report covers roughly the day before (5 am to 5 am).
                reported = resort_daily.get((d + timedelta(days=1)).isoformat())
                history.append({"date": d_str, "forecast": blend_day["snow"], "low": blend_day["low"],
                                "high": blend_day["high"], "observed": r1(obs_snow), "observed_liquid": obs_liq,
                                "resort": reported})
                if reported is not None:
                    cal_fc += blend_day["snow"] / (lead1.get("snow_cal") or 1.0)  # before calibration
                    cal_obs += reported
                    cal_n += 1
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
        prior = _lead_priors(priors.get(m))["short"]
        # Shrink toward the prior: with no recent liquid the prior stands, and a few wet
        # days are not allowed to swing the correction on their own.
        ratio = (o_sum + PRIOR_WEIGHT_IN * prior) / (f_sum + PRIOR_WEIGHT_IN)
        stats[m] = {"n": len(ps), "mae_liquid_in": round(mae, 3), "prior": prior,
                    "bias_ratio": round(_clamp(ratio, *BIAS_CLAMP), 2)}
        stats[m]["bias_by_lead"] = _by_lead(priors.get(m), stats[m]["bias_ratio"])
    maes = sorted(s["mae_liquid_in"] for s in stats.values() if s["n"] >= MIN_DAYS)
    median = maes[len(maes) // 2] if maes else None
    for m, s in stats.items():
        if s["n"] < MIN_DAYS or not median:
            s["skill"] = 1.0
        else:
            s["skill"] = round(_clamp(median / max(s["mae_liquid_in"], 0.005), 0.5, 2.0), 2)
    for m, prior in priors.items():  # models with nothing scored yet still get their prior
        lp = _lead_priors(prior)
        stats.setdefault(m, {"n": 0, "prior": lp["short"], "bias_ratio": lp["short"], "skill": 1.0,
                             "bias_by_lead": _by_lead(prior, lp["short"])})
    for m, ps in snow_pairs.items():
        s = stats.setdefault(m, {"n": 0, "bias_ratio": 1.0, "skill": 1.0})
        s["mae_snow_in"] = round(sum(abs(f - o) for f, o in ps) / len(ps), 2)
        s["n_snow"] = len(ps)

    cal = _clamp((cal_obs + CAL_WEIGHT_IN) / (cal_fc + CAL_WEIGHT_IN), *CAL_CLAMP)
    return {"updated": today.isoformat(), "window_days": WINDOW_DAYS, "models": stats,
            "snow_cal": {"ratio": round(cal, 2), "n": cal_n,
                         "forecast_in": round(cal_fc, 1), "resort_in": round(cal_obs, 1)},
            "history": history[-30:]}
