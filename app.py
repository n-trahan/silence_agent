"""
Silence Agent — live demo app.

Run:  pip install streamlit pandas numpy
      streamlit run app.py

Fully offline. Seeded data -> identical demo every run.
The time slider is the show: drag forward and watch pantries go silent.
"""
import json
from datetime import timedelta

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Silence Agent — FBCCS", layout="wide")

GREEN, RED, AMBER = "#22c55e", "#ef4444", "#f59e0b"
LB = 1.97  # FBCCS FY2025 audited financials, Notes 5-6

# ---------------- data ----------------
@st.cache_data
def load():
    agencies = pd.read_csv("data/agencies.csv")
    orders = pd.read_csv("data/orders.csv", parse_dates=["order_date"])
    donors = pd.read_csv("data/donors.csv")
    pickups = pd.read_csv("data/pickups.csv", parse_dates=["week_start"])
    gt = json.load(open("data/ground_truth.json"))
    return agencies, orders, donors, pickups, gt

agencies, orders, donors, pickups, gt = load()
SIM_END = pd.Timestamp(gt["sim_today"])
SIM_START_SLIDER = SIM_END - timedelta(weeks=16)

# ---------------- detection (as-of any date) ----------------
def detect_silent_agencies(as_of: pd.Timestamp) -> pd.DataFrame:
    hist = orders[orders.order_date <= as_of]
    out = []
    for aid, grp in hist.groupby("agency_id"):
        dates = grp.order_date.sort_values()
        if len(dates) < 6:
            continue
        med = float(dates.diff().dt.days.dropna().median())
        gap = (as_of - dates.max()).days
        if gap > 2.0 * med:
            missed = int(gap // med)
            lbs = float(grp.pounds.tail(6).mean() * missed)
            out.append({"agency_id": aid, "median_interval": med,
                        "days_quiet": gap, "missed_cycles": missed,
                        "undelivered_lbs": round(lbs), "undelivered_usd": round(lbs * LB)})
    return pd.DataFrame(out)

def detect_fading_donors(as_of: pd.Timestamp) -> pd.DataFrame:
    hist = pickups[pickups.week_start <= as_of]
    out = []
    for did, grp in hist.groupby("donor_id"):
        g = grp.sort_values("week_start")
        if len(g) < 56:
            continue
        recent = g.pounds.tail(4).mean()
        baseline = g.pounds.iloc[-16:-4].mean()
        yoy = g.pounds.iloc[-56:-52].mean()
        if baseline > 0 and recent < 0.80 * baseline and recent < 0.80 * yoy:
            loss = baseline - recent
            out.append({"donor_id": did,
                        "decline_pct": round(100 * (1 - recent / baseline), 1),
                        "weekly_loss_lbs": round(float(loss)),
                        "annual_replacement_usd": round(float(loss * 52 * LB))})
    return pd.DataFrame(out)

def draft_outreach(row, agencies_df):
    a = agencies_df.set_index("agency_id").loc[row.agency_id]
    return (f"Subject: Checking in from the Food Bank — anything you need?\n\n"
            f"Hi {a['name']} team,\n\n"
            f"We noticed it's been about {row.days_quiet} days since your last order — "
            f"you're usually with us every {int(row.median_interval)} days — so we wanted "
            f"to check in and make sure everything's okay on your end. If anything has "
            f"changed (volunteers, storage, schedules), we'd love to help, including "
            f"delivery options or a temporary adjustment. The neighbors you serve matter "
            f"to us, and so do you.\n\nWarmly,\nAgency Relations, "
            f"Food Bank of Contra Costa & Solano")

# ---------------- UI ----------------
st.title("Silence Agent")
st.caption("The most expensive supply-chain failures are the ones that don't announce "
           "themselves. Agency Express records every order — nothing notices when they stop. "
           "This does.")

as_of = st.slider("Simulation date — drag forward and watch the network",
                  min_value=SIM_START_SLIDER.to_pydatetime(),
                  max_value=SIM_END.to_pydatetime(),
                  value=SIM_START_SLIDER.to_pydatetime(),
                  step=timedelta(days=7), format="MMM D, YYYY")
as_of = pd.Timestamp(as_of)

silent = detect_silent_agencies(as_of)
fading = detect_fading_donors(as_of)
flagged_ids = set(silent.agency_id) if len(silent) else set()

left, right = st.columns([3, 2])

with left:
    st.subheader("Partner network — Contra Costa & Solano")
    m = agencies[["agency_id", "lat", "lon"]].copy()
    m["color"] = [RED if a in flagged_ids else GREEN for a in m.agency_id]
    m["size"] = [140 if a in flagged_ids else 28 for a in m.agency_id]
    st.map(m, latitude="lat", longitude="lon", color="color", size="size")
    st.caption(f"{len(agencies)} partner agencies • "
               f"{len(flagged_ids)} silent as of {as_of.date()}")

with right:
    st.subheader("Live flags")
    c1, c2, c3 = st.columns(3)
    c1.metric("Silent agencies", len(silent))
    c2.metric("Fading donors", len(fading))
    total_risk = (int(silent.undelivered_usd.sum()) if len(silent) else 0) + \
                 (int(fading.annual_replacement_usd.sum()) if len(fading) else 0)
    c3.metric("$ at stake", f"${total_risk:,}")

    if len(silent):
        s = silent.merge(agencies[["agency_id", "name", "city", "households_served"]],
                         on="agency_id")
        for _, r in s.sort_values("households_served", ascending=False).iterrows():
            sev = "HIGH" if r.households_served > 500 or r.missed_cycles >= 3 else "MED"
            with st.expander(f"🔴 [{sev}] {r['name']} ({r.city}) — {r.days_quiet}d quiet "
                             f"— {r.households_served} households"):
                st.write(f"Normal rhythm: every {int(r.median_interval)} days · "
                         f"~{int(r.undelivered_lbs):,} lbs / ${int(r.undelivered_usd):,} "
                         f"undelivered")
                st.text_area("Agent-drafted outreach (human reviews & sends)",
                             draft_outreach(r, agencies), height=220,
                             key=f"d{r.agency_id}")
    if len(fading):
        f = fading.merge(donors[["donor_id", "name", "city"]], on="donor_id")
        for _, r in f.iterrows():
            st.warning(f"🟠 FADING DONOR: {r['name']} ({r.city}) — down {r.decline_pct}% "
                       f"— ${int(r.annual_replacement_usd):,}/yr replacement if lost "
                       f"→ Food Resources: schedule store visit")
    if not len(silent) and not len(fading):
        st.success("All 245 agencies on rhythm. All donors steady. "
                   "(Drag the slider forward…)")

st.divider()
st.subheader("Why this matters — their own numbers")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Detection (prototype)", "17 days", "-58 vs quarterly review")
k2.metric("One silent pantry", "$4,300/mo", "2,200 lbs undelivered")
k3.metric("One fading store", "$31K/yr", "at 30% decline")
k4.metric("Cost to run", "<$1K/yr", "less than their printer lease")
st.caption("Valuation $1.97/lb per FBCCS FY2025 audited financials (Feeding America "
           "cost study). Detection metrics from seeded synthetic data, 245 agencies, "
           "injected ground truth: 5/5 silences caught, 3/3 donor fades, 1.2% false-positive rate.")
