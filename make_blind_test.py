"""
Blind test — fresh data the agent has never seen.

New random seed, different network shape, different anomalies:
  - a different NUMBER of silent agencies (not 5)
  - different agencies, different silence start dates
  - different donors fading, at different rates
  - one deliberately tricky case: an agency that SLOWED (monthly-ish) but
    didn't stop — should NOT be flagged as silent

Writes blind_test/orders_export_*.csv (+ pickups) for upload, and a SEALED
answer key (blind_test/ANSWER_KEY.json). Don't open the key until after
you've run the uploads and written down what the agent flagged.
"""
import json
import os
import numpy as np
import pandas as pd
from datetime import date, timedelta

rng = np.random.default_rng(20260715)  # different seed than the demo (42)
os.makedirs("blind_test", exist_ok=True)

SIM_TODAY = date(2026, 7, 13)
START = SIM_TODAY - timedelta(days=730)
N_AGENCIES, N_DONORS = 245, 30

CITY_COORDS = {
    "Concord": (37.9780, -122.0311), "Richmond": (37.9358, -122.3477),
    "Antioch": (38.0049, -121.8058), "Pittsburg": (38.0280, -121.8847),
    "Vallejo": (38.1041, -122.2566), "Fairfield": (38.2494, -122.0400),
    "Vacaville": (38.3566, -121.9877), "Walnut Creek": (37.9101, -122.0652),
    "Martinez": (38.0194, -122.1341), "Brentwood": (37.9319, -121.6958),
    "San Pablo": (37.9621, -122.3456), "Suisun City": (38.2383, -122.0402),
}
CITIES = list(CITY_COORDS)

# ---- network (new shapes) ----
agencies = []
for i in range(N_AGENCIES):
    cadence = int(rng.choice([7, 14, 21, 28], p=[0.3, 0.4, 0.1, 0.2]))
    city = rng.choice(CITIES)
    agencies.append({"agency_id": f"B{i:03d}", "name": f"Agency B{i:03d}",
                     "city": city,
                     "households_served": int(rng.integers(50, 1500)),
                     "cadence_days": cadence,
                     "base_order_lbs": float(np.round(rng.lognormal(6.9, 0.7), 0))})
agencies = pd.DataFrame(agencies)

donors = pd.DataFrame([{"donor_id": f"E{i:02d}", "name": f"Retail Donor E{i:02d}",
                        "city": rng.choice(CITIES),
                        "base_weekly_lbs": float(np.round(rng.lognormal(6.6, 0.6), 0))}
                       for i in range(N_DONORS)])

# ---- unknown anomalies ----
n_silent = int(rng.integers(3, 9))                      # NOT 5
silent_ids = list(rng.choice(agencies.agency_id, n_silent, replace=False))
silence_starts = {a: SIM_TODAY - timedelta(days=int(rng.integers(15, 70)))
                  for a in silent_ids}

n_fade = int(rng.integers(2, 6))
fade_ids = list(rng.choice(donors.donor_id, n_fade, replace=False))
fade_starts = {d: SIM_TODAY - timedelta(weeks=int(rng.integers(8, 18)))
               for d in fade_ids}
fade_floor = {d: float(rng.uniform(0.45, 0.7)) for d in fade_ids}

# tricky non-anomaly: agency that doubles its interval mid-year but keeps ordering
slowed_id = rng.choice([a for a in agencies.agency_id if a not in silent_ids])
slow_start = SIM_TODAY - timedelta(days=180)

# ---- orders ----
rows = []
for _, a in agencies.iterrows():
    d = START + timedelta(days=int(rng.integers(0, a.cadence_days)))
    while d <= SIM_TODAY:
        if a.agency_id in silent_ids and d >= silence_starts[a.agency_id]:
            break
        eff = a.cadence_days
        if a.agency_id == slowed_id and d >= slow_start:
            eff = a.cadence_days * 2  # slowed, not silent
        if rng.random() > 0.05:
            lbs = max(40, rng.normal(a.base_order_lbs, a.base_order_lbs * 0.2))
            rows.append({"agency_id": a.agency_id, "agency_name": a["name"],
                         "city": a.city, "order_date": d.isoformat(),
                         "pounds": float(np.round(lbs, 0))})
        d += timedelta(days=int(eff + rng.integers(-2, 3)))
orders = pd.DataFrame(rows)

# ---- pickups ----
prow = []
for _, dn in donors.iterrows():
    d = START
    while d <= SIM_TODAY:
        mult = 1.25 if d.month in (11, 12) else (0.9 if d.month in (6, 7) else 1.0)
        if dn.donor_id in fade_ids and d >= fade_starts[dn.donor_id]:
            wks = (d - fade_starts[dn.donor_id]).days / 7
            mult *= max(fade_floor[dn.donor_id], 1 - 0.035 * wks)
        lbs = max(0, rng.normal(dn.base_weekly_lbs * mult, dn.base_weekly_lbs * 0.15))
        prow.append({"donor_id": dn.donor_id, "week_start": d.isoformat(),
                     "pounds": float(np.round(lbs, 0))})
        d += timedelta(days=7)
pickups = pd.DataFrame(prow)

# ---- weekly exports ----
for m in ["2026-06-29", "2026-07-13"]:
    c = pd.Timestamp(m)
    orders[pd.to_datetime(orders.order_date) <= c].to_csv(
        f"blind_test/orders_export_{m}.csv", index=False)
    pickups[pd.to_datetime(pickups.week_start) <= c].to_csv(
        f"blind_test/pickups_export_{m}.csv", index=False)

# reference file so app map/names work with B-network (optional swap)
agencies_out = agencies.copy()
agencies_out["lat"] = [CITY_COORDS[c][0] + rng.normal(0, 0.012) for c in agencies_out.city]
agencies_out["lon"] = [CITY_COORDS[c][1] + rng.normal(0, 0.012) for c in agencies_out.city]
agencies_out.to_csv("blind_test/agencies.csv", index=False)
donors.to_csv("blind_test/donors.csv", index=False)

key = {
    "silent_agencies": {a: silence_starts[a].isoformat() for a in silent_ids},
    "n_silent": n_silent,
    "fading_donors": {d: {"start": fade_starts[d].isoformat(),
                          "floor_pct": round(100 * (1 - fade_floor[d]), 0)}
                      for d in fade_ids},
    "n_fading": n_fade,
    "trap_slowed_but_active": str(slowed_id),
    "note": ("The 'trap' agency doubled its ordering interval 6 months ago but kept "
             "ordering. A correct agent should NOT flag it: its median interval "
             "adapts to the new rhythm. A naive fixed-threshold system would "
             "false-alarm on it."),
}
with open("blind_test/ANSWER_KEY.json", "w") as f:
    json.dump(key, f, indent=2)

print(f"Blind test written: {n_silent} silent agencies, {n_fade} fading donors, "
      f"1 trap (slowed-not-silent).")
print("Upload blind_test/orders_export_2026-07-13.csv, note what gets flagged,")
print("THEN open blind_test/ANSWER_KEY.json to score yourself.")
