"""
Silence Agent — weekly workflow demo.

Replicates a food bank worker's Monday routine:
  1. Export order history from the ordering system (we provide the CSVs)
  2. Upload it here
  3. Review flags, edit drafted outreach, download the digest

Run:  python3 -m streamlit run app_weekly.py
Demo files: demo_uploads/orders_export_*.csv (four consecutive Mondays —
upload them in order and watch the network change week to week).
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Silence Agent — Weekly Review", layout="wide")
GREEN, RED = "#22c55e", "#ef4444"
LB = 1.97  # FBCCS FY2025 audited financials, Notes 5-6

@st.cache_data
def load_reference():
    agencies = pd.read_csv("data/agencies.csv")
    donors = pd.read_csv("data/donors.csv")
    return agencies, donors

# reference loading now happens per-upload (works with any network)

st.title("Silence Agent — Weekly Review")
st.caption("Your Monday routine: export orders from Agency Express, drop the file "
           "here, review what went quiet. The agent drafts — you decide and send.")

# ---------------- Step 1: upload ----------------
st.subheader("Step 1 — Upload this week's order export")
ocol, pcol = st.columns(2)
orders_file = ocol.file_uploader("Orders export (CSV: agency_id, order_date, pounds)",
                                 type="csv", key="orders")
pickups_file = pcol.file_uploader("Optional: retail pickups export (donor_id, week_start, pounds)",
                                  type="csv", key="pickups")

if orders_file is None:
    st.info("Waiting for a file. Demo exports for four consecutive Mondays are in "
            "the demo_uploads/ folder — upload them in date order to replay a month.")
    st.stop()

orders = pd.read_csv(orders_file, parse_dates=["order_date"])
AS_OF = orders.order_date.max()

# Build agency info from the uploaded file itself (name/city travel with the export).
# Reference files are only used when their IDs actually match — so demo data,
# blind-test data, or a real food bank's export all work without code changes.
if "agency_name" in orders.columns:
    agency_info = orders.groupby("agency_id").agg(
        name=("agency_name", "last"), city=("city", "last")).reset_index()
else:
    agency_info = pd.DataFrame({"agency_id": orders.agency_id.unique()})
    agency_info["name"] = agency_info.agency_id
    agency_info["city"] = ""

coords = None
for ref_path in ("data/agencies.csv", "blind_test/agencies.csv"):
    try:
        ref = pd.read_csv(ref_path)
        if ref.agency_id.isin(orders.agency_id).mean() > 0.5:
            if "households_served" in ref.columns:
                agency_info = agency_info.merge(
                    ref[["agency_id", "households_served"]], on="agency_id", how="left")
            if {"lat", "lon"}.issubset(ref.columns):
                coords = ref[["agency_id", "lat", "lon"]]
            break
    except FileNotFoundError:
        pass
if "households_served" not in agency_info.columns:
    agency_info["households_served"] = np.nan

st.success(f"Loaded {len(orders):,} orders across {orders.agency_id.nunique()} agencies. "
           f"Treating export date as **{AS_OF.date()}**.")

# ---------------- Step 2: detection ----------------
def detect_silent(orders, as_of):
    out = []
    for aid, grp in orders.groupby("agency_id"):
        dates = grp.order_date.sort_values()
        if len(dates) < 6:
            continue
        med = float(dates.diff().dt.days.dropna().median())
        gap = (as_of - dates.max()).days
        if gap > 2.0 * med:
            missed = int(gap // med)
            lbs = float(grp.pounds.tail(6).mean() * missed)
            out.append({"agency_id": aid, "median_interval": med, "days_quiet": gap,
                        "missed_cycles": missed, "undelivered_lbs": round(lbs),
                        "undelivered_usd": round(lbs * LB)})
    return pd.DataFrame(out)

def detect_fading(pickups, as_of):
    out = []
    for did, grp in pickups.groupby("donor_id"):
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
                        "annual_replacement_usd": round(float(loss * 52 * LB))})
    return pd.DataFrame(out)

silent = detect_silent(orders, AS_OF)
fading = pd.DataFrame()
if pickups_file is not None:
    pk = pd.read_csv(pickups_file, parse_dates=["week_start"])
    fading = detect_fading(pk, AS_OF)

# ---------------- investigation engine (the agentic layer) ----------------
import os
LIVE = bool(os.environ.get("ANTHROPIC_API_KEY"))
_info = agency_info.set_index("agency_id")

donor_city_ref = None
if pickups_file is not None:
    for ref_path in ("blind_test/donors.csv", "data/donors.csv"):
        try:
            dc = pd.read_csv(ref_path)
            if dc.donor_id.isin(pk.donor_id).mean() > 0.5:
                donor_city_ref = dc.set_index("donor_id")
                break
        except FileNotFoundError:
            pass

def tool_order_history(aid):
    g = orders[orders.agency_id == aid].sort_values("order_date")
    last10 = g.tail(10)
    taper = bool(last10.pounds.tail(5).mean() < 0.75 * last10.pounds.head(5).mean())
    return {"orders_on_record": int(len(g)),
            "tenure_days": int((g.order_date.max() - g.order_date.min()).days),
            "last_10_dates": [d.strftime("%Y-%m-%d") for d in last10.order_date],
            "volume_tapered_before_silence": taper}

def tool_check_neighbors(aid):
    city = _info.loc[aid, "city"]
    sibs = [a for a in _info[_info.city == city].index if a != aid]
    quiet = []
    for s_ in sibs:
        d = orders[orders.agency_id == s_].order_date.sort_values()
        if len(d) < 6:
            continue
        if (AS_OF - d.max()).days > 1.5 * d.diff().dt.days.dropna().median():
            quiet.append(s_)
    return {"city": str(city), "sibling_agencies": len(sibs),
            "siblings_also_quiet": quiet,
            "pattern": "REGIONAL" if len(quiet) >= 2 else "ISOLATED"}

def tool_check_local_donors(aid):
    if pickups_file is None or donor_city_ref is None:
        return {"available": False}
    city = _info.loc[aid, "city"]
    fading_local = []
    for did in donor_city_ref[donor_city_ref.city == city].index:
        g = pk[pk.donor_id == did].sort_values("week_start")
        if len(g) >= 16 and g.pounds.tail(4).mean() < 0.8 * g.pounds.iloc[-16:-4].mean():
            fading_local.append(str(did))
    return {"available": True, "local_donors_fading": fading_local}

def run_investigation(aid, flag_row):
    hist = tool_order_history(aid)
    nbrs = tool_check_neighbors(aid)
    dnrs = tool_check_local_donors(aid)
    trace = {"get_order_history": hist, "check_neighbor_agencies": nbrs,
             "check_local_donors": dnrs}
    name, city = _info.loc[aid, "name"], _info.loc[aid, "city"]

    if LIVE:
        try:
            import anthropic, json as _json
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=700,
                system=("You are a food bank network investigator. Given a silence flag "
                        "and evidence gathered by tools, produce JSON only: "
                        '{"hypothesis":..., "confidence":"high|medium|low", '
                        '"pattern":"ISOLATED|REGIONAL", '
                        '"channel":"email|call_first|escalate_to_director", '
                        '"reasoning":..., "outreach_draft": warm <=100-word message}. '
                        "Escalate only for regional patterns or long-tenured cold stops."),
                messages=[{"role": "user", "content":
                           f"Flag: {flag_row.to_dict()}\nAgency: {name}, {city}\n"
                           f"Evidence: {_json.dumps(trace)}"}])
            text = msg.content[0].text.replace("```json", "").replace("```", "").strip()
            return _json.loads(text), trace
        except Exception as e:
            st.toast(f"Live agent unavailable ({e}); using offline analyst.")

    tenure_yrs = round(hist["tenure_days"] / 365, 1)
    if nbrs["pattern"] == "REGIONAL":
        hyp = (f"Regional disruption in {city}: {len(nbrs['siblings_also_quiet'])} other "
               f"agencies there are also quiet — shared local cause more likely than "
               f"agency-specific failure.")
        channel, conf = "escalate_to_director", "medium"
    elif hist["volume_tapered_before_silence"]:
        hyp = ("Gradual decline: volume tapered before the silence — consistent with "
               "shrinking capacity (volunteers, storage, funding), not sudden closure.")
        channel, conf = "call_first", "medium"
    else:
        hyp = (f"Sudden organizational disruption: {tenure_yrs} yrs of steady rhythm, "
               f"then a cold stop — pattern matches coordinator loss or abrupt failure.")
        channel = ("call_first" if flag_row.days_quiet > 3 * flag_row.median_interval
                   else "email")
        conf = "high" if tenure_yrs > 1.5 else "medium"
    donors_note = (f" Also: {len(dnrs['local_donors_fading'])} retail donor(s) in {city} "
                   f"fading — log for quarterly root-cause report."
                   if dnrs.get("available") and dnrs.get("local_donors_fading") else "")
    return ({"hypothesis": hyp, "confidence": conf, "pattern": nbrs["pattern"],
             "channel": channel,
             "reasoning": (f"{'Taper' if hist['volume_tapered_before_silence'] else 'Cold stop'} "
                           f"after {tenure_yrs} yrs / {hist['orders_on_record']} orders. "
                           f"Neighbors: {nbrs['pattern']} "
                           f"({len(nbrs['siblings_also_quiet'])}/{nbrs['sibling_agencies']} "
                           f"quiet).{donors_note}"),
             "outreach_draft": (f"Hi {name} team,\n\nWe noticed a change in your usual "
                                f"ordering rhythm and wanted to reach out personally. If "
                                f"anything has shifted — volunteers, space, funding — we'd "
                                f"love to help you keep serving your neighbors, whether "
                                f"that's delivery support, a schedule change, or just a "
                                f"conversation. You matter to us.\n\nWarmly,\n"
                                f"Agency Relations")}, trace)

# ---------------- Step 3: review ----------------
st.subheader("Step 2 — This week's flags")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Agencies on rhythm", f"{orders.agency_id.nunique() - len(silent)}")
m2.metric("Silent agencies", len(silent), delta=None)
m3.metric("Fading donors", len(fading) if len(fading) else 0)
risk = (int(silent.undelivered_usd.sum()) if len(silent) else 0) + \
       (int(fading.annual_replacement_usd.sum()) if len(fading) else 0)
m4.metric("$ at stake", f"${risk:,}")

# map (only when coordinates exist for this network)
if coords is not None:
    mm = coords.copy()
    flagged = set(silent.agency_id) if len(silent) else set()
    mm["color"] = [RED if a in flagged else GREEN for a in mm.agency_id]
    mm["size"] = [150 if a in flagged else 25 for a in mm.agency_id]
    st.map(mm, latitude="lat", longitude="lon", color="color", size="size")

digest_lines = [f"SILENCE REPORT — export dated {AS_OF.date()} — "
                f"generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", "=" * 60]

if len(silent):
    s = silent.merge(agency_info, on="agency_id", how="left")
    s["households_served"] = s.households_served.fillna(0).astype(int)
    st.subheader("Step 3 — Review & send (agent drafts, you decide)")
    for _, r in s.sort_values(["households_served", "undelivered_usd"],
                              ascending=False).iterrows():
        hh = f"{r.households_served} households — " if r.households_served else ""
        sev = "HIGH" if r.households_served > 500 or r.missed_cycles >= 3 else "MEDIUM"
        head = (f"[{sev}] {r['name']} ({r.city}) — {r.days_quiet}d quiet "
                f"(normal: every {int(r.median_interval)}d) — {hh}"
                f"~{int(r.undelivered_lbs):,} lbs / ${int(r.undelivered_usd):,}")
        digest_lines += [head, f"    -> Agency Relations: call today; if unreachable "
                               f"in 48h, arrange temporary coverage.", ""]
        with st.expander(f"🔴 {head}"):
            if st.button("🔎 Investigate", key=f"inv_{r.agency_id}",
                         help="Agent queries order history, neighbor agencies, and "
                              "local donors, then forms a hypothesis"):
                with st.spinner("Agent investigating…"):
                    st.session_state[f"invres_{r.agency_id}"] = run_investigation(
                        r.agency_id, r)
            if f"invres_{r.agency_id}" in st.session_state:
                inv, trace = st.session_state[f"invres_{r.agency_id}"]
                badge = {"email": "✉️ EMAIL", "call_first": "📞 CALL FIRST",
                         "escalate_to_director": "🚨 ESCALATE TO DIRECTOR"}[inv["channel"]]
                st.markdown(f"**{badge}** · pattern: **{inv['pattern']}** · "
                            f"confidence: **{inv['confidence']}**")
                st.markdown(f"**Hypothesis:** {inv['hypothesis']}")
                st.caption(f"Reasoning: {inv['reasoning']}")
                with st.popover("Evidence gathered (tool trace)"):
                    st.json(trace)
                st.text_area("Drafted outreach — matched to hypothesis (edit before sending)",
                             inv["outreach_draft"], height=200, key=f"draft_{r.agency_id}")
            else:
                draft = (f"Hi {r['name']} team,\n\n"
                         f"We noticed it's been about {r.days_quiet} days since your last "
                         f"order — you're usually with us every {int(r.median_interval)} "
                         f"days — so we wanted to check in and make sure everything's okay. "
                         f"If anything has changed (volunteers, storage, schedules), we'd "
                         f"love to help, including delivery options or a temporary "
                         f"adjustment. The neighbors you serve matter to us, and so do you."
                         f"\n\nWarmly,\nAgency Relations")
                st.text_area("Drafted check-in (edit before sending)", draft, height=200,
                             key=f"draft_{r.agency_id}")
            st.button("Mark as handled ✓", key=f"done_{r.agency_id}")
else:
    st.success("No silent agencies in this export — every partner is on rhythm.")

if len(fading):
    f = fading.copy()
    try:
        for ref_path in ("data/donors.csv", "blind_test/donors.csv"):
            ref = pd.read_csv(ref_path)
            if ref.donor_id.isin(f.donor_id).mean() > 0.5:
                f = f.merge(ref[["donor_id", "name", "city"]], on="donor_id", how="left")
                break
    except FileNotFoundError:
        pass
    if "name" not in f.columns:
        f["name"], f["city"] = f.donor_id, ""
    for _, r in f.iterrows():
        line = (f"FADING DONOR: {r['name']} ({r.city}) — down {r.decline_pct}% — "
                f"${int(r.annual_replacement_usd):,}/yr replacement if lost")
        digest_lines += [line, "    -> Food Resources: schedule store visit.", ""]
        st.warning("🟠 " + line)

st.download_button("Download this week's digest (share with your team)",
                   "\n".join(digest_lines),
                   file_name=f"silence_report_{AS_OF.date()}.txt")
st.caption("Valuation $1.97/lb per FBCCS FY2025 audited financials. "
           "No data leaves this laptop.")
