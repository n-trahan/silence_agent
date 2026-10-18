"""
Silence detection engine.
Rule 1 (silent agency):   days_since_last_order > 2.0 x agency's own median interval
Rule 2 (fading donor):    last-4-week avg < 0.80 x prior-12-week baseline avg
Outputs flags.json for the agent layer, and metrics.json scored against ground truth.
"""
import json
import numpy as np
import pandas as pd
from datetime import date

GAP_MULTIPLIER = 2.0
DECAY_RATIO = 0.80

agencies = pd.read_csv("data/agencies.csv")
orders = pd.read_csv("data/orders.csv", parse_dates=["order_date"])
donors = pd.read_csv("data/donors.csv")
pickups = pd.read_csv("data/pickups.csv", parse_dates=["week_start"])
gt = json.load(open("data/ground_truth.json"))
TODAY = pd.Timestamp(gt["sim_today"])
LB = gt["lb_value_usd"]

flags = []

# ---------- Rule 1: silent agencies ----------
for aid, grp in orders.groupby("agency_id"):
    dates = grp.order_date.sort_values()
    if len(dates) < 6:
        continue
    intervals = dates.diff().dt.days.dropna()
    med = float(intervals.median())
    gap = (TODAY - dates.max()).days
    if gap > GAP_MULTIPLIER * med:
        a = agencies.set_index("agency_id").loc[aid]
        missed_cycles = int(gap // med)
        lbs_at_risk = float(grp.pounds.tail(6).mean() * missed_cycles)
        flags.append({
            "type": "silent_agency", "entity_id": aid, "name": a["name"],
            "city": a.city, "households_served": int(a.households_served),
            "median_interval_days": med, "days_since_last_order": gap,
            "missed_cycles": missed_cycles,
            "est_undelivered_lbs": round(lbs_at_risk, 0),
            "est_undelivered_usd": round(lbs_at_risk * LB, 0),
        })

# ---------- Rule 2: fading donors ----------
for did, grp in pickups.groupby("donor_id"):
    g = grp.sort_values("week_start")
    if len(g) < 16:
        continue
    recent = g.pounds.tail(4).mean()
    baseline = g.pounds.iloc[-16:-4].mean()
    # seasonal guard: also require decline vs the SAME 4 weeks last year,
    # so a normal summer dip doesn't fire (the baseline window is spring-heavy)
    yoy = g.pounds.iloc[-56:-52].mean() if len(g) >= 56 else None
    seasonal_ok = (yoy is None) or (recent < DECAY_RATIO * yoy)
    if baseline > 0 and recent < DECAY_RATIO * baseline and seasonal_ok:
        d = donors.set_index("donor_id").loc[did]
        weekly_loss = baseline - recent
        flags.append({
            "type": "fading_donor", "entity_id": did, "name": d["name"],
            "chain": d.chain, "city": d.city,
            "baseline_weekly_lbs": round(float(baseline), 0),
            "recent_weekly_lbs": round(float(recent), 0),
            "decline_pct": round(100 * (1 - recent / baseline), 1),
            "annualized_loss_lbs": round(float(weekly_loss * 52), 0),
            "annualized_replacement_usd": round(float(weekly_loss * 52 * LB), 0),
        })

with open("output/flags.json", "w") as f:
    json.dump(flags, f, indent=2)

# ---------- Score against ground truth ----------
true_silent = set(gt["silent_agencies"])
true_decay = set(gt["decaying_donors"])
flag_silent = {f["entity_id"] for f in flags if f["type"] == "silent_agency"}
flag_decay = {f["entity_id"] for f in flags if f["type"] == "fading_donor"}

# time-to-detection: first day the rule WOULD have fired, vs silence start
ttd = []
for aid in true_silent & flag_silent:
    grp = orders[orders.agency_id == aid]
    med = grp.order_date.sort_values().diff().dt.days.dropna().median()
    silence_start = pd.Timestamp(gt["silent_agencies"][aid])
    last_order = grp.order_date.max()
    fire_day = last_order + pd.Timedelta(days=GAP_MULTIPLIER * med)
    ttd.append((fire_day - silence_start).days)

metrics = {
    "agency_detection": {
        "injected": len(true_silent),
        "caught": len(true_silent & flag_silent),
        "missed": sorted(true_silent - flag_silent),
        "false_positives": len(flag_silent - true_silent),
        "false_positive_rate_pct": round(100 * len(flag_silent - true_silent) / len(agencies), 2),
        "median_days_to_detection": float(np.median(ttd)) if ttd else None,
        "status_quo_days_to_detection": "~75 (quarterly agency review)",
    },
    "donor_detection": {
        "injected": len(true_decay),
        "caught": len(true_decay & flag_decay),
        "missed": sorted(true_decay - flag_decay),
        "false_positives": len(flag_decay - true_decay),
    },
    "impact": {
        "undelivered_lbs_flagged": sum(f["est_undelivered_lbs"] for f in flags if f["type"] == "silent_agency"),
        "undelivered_usd_flagged": sum(f["est_undelivered_usd"] for f in flags if f["type"] == "silent_agency"),
        "donor_annualized_loss_lbs": sum(f["annualized_loss_lbs"] for f in flags if f["type"] == "fading_donor"),
        "donor_annualized_replacement_usd": sum(f["annualized_replacement_usd"] for f in flags if f["type"] == "fading_donor"),
        "valuation_note": f"${LB}/lb per FBCCS FY2025 audited financials, Notes 5-6",
    },
}
with open("output/metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print(json.dumps(metrics, indent=2))
print(f"\ntotal flags: {len(flags)}")
