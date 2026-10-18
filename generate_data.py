"""
Mock data generator — anchored to FBCCS's real published shape.
Sources: FY2025 audited financials (agencies ~245, $1.97/lb donated valuation,
~30 retail donors is an assumption to validate with ops).

Generates 2 years of history ending at SIM_TODAY, with injected ground-truth
anomalies so detection metrics can be scored against an answer key.
"""
import json
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(42)  # reproducible on stage

SIM_TODAY = date(2026, 7, 13)
START = SIM_TODAY - timedelta(days=730)

N_AGENCIES = 245
N_DONORS = 30
LB_VALUE = 1.97  # FBCCS FY2025 audited financials, Note 5/6

CITIES = ["Concord", "Richmond", "Antioch", "Pittsburg", "Vallejo", "Fairfield",
          "Vacaville", "Walnut Creek", "Martinez", "Brentwood", "San Pablo", "Suisun City"]

CITY_COORDS = {
    "Concord": (37.9780, -122.0311), "Richmond": (37.9358, -122.3477),
    "Antioch": (38.0049, -121.8058), "Pittsburg": (38.0280, -121.8847),
    "Vallejo": (38.1041, -122.2566), "Fairfield": (38.2494, -122.0400),
    "Vacaville": (38.3566, -121.9877), "Walnut Creek": (37.9101, -122.0652),
    "Martinez": (38.0194, -122.1341), "Brentwood": (37.9319, -121.6958),
    "San Pablo": (37.9621, -122.3456), "Suisun City": (38.2383, -122.0402),
}

# ---------------- Agencies & orders ----------------
def make_agencies():
    rows = []
    for i in range(N_AGENCIES):
        cadence = rng.choice([7, 14, 28], p=[0.25, 0.5, 0.25])  # weekly/biweekly/monthly
        base_lbs = float(np.round(rng.lognormal(mean=7.0, sigma=0.6), 0))  # ~1100 lbs median
        city = rng.choice(CITIES)
        lat, lon = CITY_COORDS[city]
        rows.append({
            "agency_id": f"A{i:03d}",
            "name": f"Agency {i:03d}",
            "city": city,
            "lat": lat + float(rng.normal(0, 0.012)),
            "lon": lon + float(rng.normal(0, 0.012)),
            "households_served": int(rng.integers(60, 1200)),
            "cadence_days": int(cadence),
            "base_order_lbs": base_lbs,
        })
    return pd.DataFrame(rows)

def make_orders(agencies, silent_ids, silence_starts):
    rows = []
    for _, a in agencies.iterrows():
        d = START + timedelta(days=int(rng.integers(0, a.cadence_days)))
        while d <= SIM_TODAY:
            # injected silence: agency stops ordering at its silence_start
            if a.agency_id in silent_ids and d >= silence_starts[a.agency_id]:
                break
            # natural jitter: orders slip a few days; occasional skipped order (life happens)
            if rng.random() > 0.04:  # 4% random skip keeps healthy agencies noisy
                lbs = max(50, rng.normal(a.base_order_lbs, a.base_order_lbs * 0.18))
                rows.append({"agency_id": a.agency_id, "order_date": d.isoformat(),
                             "pounds": float(np.round(lbs, 0))})
            d += timedelta(days=int(a.cadence_days + rng.integers(-2, 3)))
    return pd.DataFrame(rows)

# ---------------- Donors & pickups ----------------
def make_donors():
    rows = []
    for i in range(N_DONORS):
        rows.append({
            "donor_id": f"D{i:02d}",
            "name": f"Retail Donor {i:02d}",
            "chain": rng.choice(["ChainA", "ChainB", "ChainC", "Independent"]),
            "city": rng.choice(CITIES),
            "base_weekly_lbs": float(np.round(rng.lognormal(mean=6.7, sigma=0.5), 0)),
        })
    return pd.DataFrame(rows)

def make_pickups(donors, decay_ids, decay_starts):
    rows = []
    for _, dn in donors.iterrows():
        d = START
        week = 0
        while d <= SIM_TODAY:
            mult = 1.0
            # mild seasonality: holiday bump Nov-Dec, summer dip
            m = d.month
            if m in (11, 12): mult *= 1.25
            if m in (6, 7): mult *= 0.9
            # injected decay: linear slide to ~65% over 12 weeks, then flat
            if dn.donor_id in decay_ids and d >= decay_starts[dn.donor_id]:
                wks = (d - decay_starts[dn.donor_id]).days / 7
                mult *= max(0.65, 1 - 0.03 * wks)
            lbs = max(0, rng.normal(dn.base_weekly_lbs * mult, dn.base_weekly_lbs * 0.15))
            rows.append({"donor_id": dn.donor_id, "week_start": d.isoformat(),
                         "pounds": float(np.round(lbs, 0))})
            d += timedelta(days=7)
            week += 1
    return pd.DataFrame(rows)

# ---------------- Inject ground truth ----------------
agencies = make_agencies()
donors = make_donors()

# 5 silent agencies: silences begin 20-60 days before SIM_TODAY (detectable window)
silent_ids = list(rng.choice(agencies.agency_id, size=5, replace=False))
silence_starts = {aid: SIM_TODAY - timedelta(days=int(rng.integers(20, 61)))
                  for aid in silent_ids}

# 3 decaying donors: decay begins 10-16 weeks ago
decay_ids = list(rng.choice(donors.donor_id, size=3, replace=False))
decay_starts = {did: SIM_TODAY - timedelta(weeks=int(rng.integers(10, 17)))
                for did in decay_ids}

orders = make_orders(agencies, set(silent_ids), silence_starts)
pickups = make_pickups(donors, set(decay_ids), decay_starts)

agencies.to_csv("data/agencies.csv", index=False)
orders.to_csv("data/orders.csv", index=False)
donors.to_csv("data/donors.csv", index=False)
pickups.to_csv("data/pickups.csv", index=False)

ground_truth = {
    "sim_today": SIM_TODAY.isoformat(),
    "lb_value_usd": LB_VALUE,
    "silent_agencies": {a: silence_starts[a].isoformat() for a in silent_ids},
    "decaying_donors": {d: decay_starts[d].isoformat() for d in decay_ids},
}
with open("data/ground_truth.json", "w") as f:
    json.dump(ground_truth, f, indent=2)

print(f"agencies={len(agencies)} orders={len(orders)} donors={len(donors)} pickup-weeks={len(pickups)}")
print("injected silent agencies:", ground_truth["silent_agencies"])
print("injected decaying donors:", ground_truth["decaying_donors"])
