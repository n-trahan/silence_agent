"""
Investigation Agent — the agentic layer.

For each detection flag, the agent INVESTIGATES before recommending:
it queries the order history, checks whether neighboring agencies are also
quiet (regional vs. organizational cause), checks whether nearby donors are
fading (shared upstream cause), then writes a hypothesis with evidence and
chooses the response channel (email / call-first / escalate).

Architecture (say this to judges):
  deterministic sensors -> agentic analyst -> human actuator.
  Math decides WHETHER something is anomalous (auditable).
  The agent decides WHAT IT MEANS and WHAT TO DO (reasoning).
  A human decides to act (relationships, not tickets).

Modes:
  LIVE  — ANTHROPIC_API_KEY set: Claude runs the loop itself via tool use,
          choosing which queries to run and when to conclude.
  DEMO  — offline: the same tools run in a fixed sequence and a transparent
          heuristic writes the brief. Identical output shape; no network.

Usage:
  python3 investigate.py                          # demo data
  python3 investigate.py blind_test/orders_export_2026-07-13.csv
"""
import json
import os
import sys

import numpy as np
import pandas as pd

LB = 1.97
LIVE = bool(os.environ.get("ANTHROPIC_API_KEY"))

# ---------------- load whichever network was passed ----------------
orders_path = sys.argv[1] if len(sys.argv) > 1 else "data/orders.csv"
orders = pd.read_csv(orders_path, parse_dates=["order_date"])
AS_OF = orders.order_date.max()

if "agency_name" in orders.columns:
    info = orders.groupby("agency_id").agg(name=("agency_name", "last"),
                                           city=("city", "last")).reset_index()
else:
    ref = pd.read_csv("data/agencies.csv")
    info = ref[["agency_id", "name", "city"]]
info = info.set_index("agency_id")

pickups = None
for p in (orders_path.replace("orders_export", "pickups_export"), "data/pickups.csv"):
    if os.path.exists(p):
        pk = pd.read_csv(p, parse_dates=["week_start"])
        pickups = pk
        break

donor_city = None
for p in ("blind_test/donors.csv", "data/donors.csv"):
    if os.path.exists(p):
        dc = pd.read_csv(p)
        if pickups is not None and dc.donor_id.isin(pickups.donor_id).mean() > 0.5:
            donor_city = dc.set_index("donor_id")
            break

# ---------------- detection (sensors) ----------------
def detect_silent():
    out = []
    for aid, grp in orders.groupby("agency_id"):
        d = grp.order_date.sort_values()
        if len(d) < 6:
            continue
        med = float(d.diff().dt.days.dropna().median())
        gap = (AS_OF - d.max()).days
        if gap > 2.0 * med:
            out.append({"agency_id": aid, "median_interval": med, "days_quiet": gap})
    return out

# ---------------- tools the agent can call ----------------
def tool_order_history(agency_id: str) -> dict:
    """Last 10 orders + trend: did volume taper before the silence, or stop cold?"""
    g = orders[orders.agency_id == agency_id].sort_values("order_date")
    last10 = g.tail(10)
    first5, last5 = last10.pounds.head(5).mean(), last10.pounds.tail(5).mean()
    taper = bool(last5 < 0.75 * first5)
    return {
        "agency_id": agency_id,
        "orders_on_record": int(len(g)),
        "tenure_days": int((g.order_date.max() - g.order_date.min()).days),
        "last_10_dates": [d.strftime("%Y-%m-%d") for d in last10.order_date],
        "last_10_pounds": [int(x) for x in last10.pounds],
        "volume_tapered_before_silence": taper,
        "avg_order_lbs": int(g.pounds.tail(6).mean()),
    }

def tool_check_neighbors(agency_id: str) -> dict:
    """Are OTHER agencies in the same city also quiet? Regional vs. isolated."""
    city = info.loc[agency_id, "city"]
    sibs = [a for a in info[info.city == city].index if a != agency_id]
    quiet = []
    for aid in sibs:
        d = orders[orders.agency_id == aid].order_date.sort_values()
        if len(d) < 6:
            continue
        med = d.diff().dt.days.dropna().median()
        if (AS_OF - d.max()).days > 1.5 * med:
            quiet.append(aid)
    return {"city": str(city), "sibling_agencies": len(sibs),
            "siblings_also_quiet": quiet,
            "pattern": "REGIONAL" if len(quiet) >= 2 else "ISOLATED"}

def tool_check_local_donors(agency_id: str) -> dict:
    """Are retail donors in the same city fading? Shared upstream cause."""
    if pickups is None or donor_city is None:
        return {"available": False}
    city = info.loc[agency_id, "city"]
    local = donor_city[donor_city.city == city].index
    fading = []
    for did in local:
        g = pickups[pickups.donor_id == did].sort_values("week_start")
        if len(g) < 16:
            continue
        if g.pounds.tail(4).mean() < 0.8 * g.pounds.iloc[-16:-4].mean():
            fading.append(str(did))
    return {"available": True, "city": str(city),
            "local_donors": int(len(local)), "local_donors_fading": fading}

TOOLS = {"get_order_history": tool_order_history,
         "check_neighbor_agencies": tool_check_neighbors,
         "check_local_donors": tool_check_local_donors}

TOOL_SPECS = [
    {"name": "get_order_history",
     "description": "Last 10 orders, tenure, and whether volume tapered before the silence (taper suggests gradual decline; cold stop suggests sudden organizational failure).",
     "input_schema": {"type": "object", "properties": {"agency_id": {"type": "string"}},
                      "required": ["agency_id"]}},
    {"name": "check_neighbor_agencies",
     "description": "Whether other agencies in the same city are also quiet. Two or more quiet siblings suggests a REGIONAL cause (shared facility, local event); isolated silence suggests an agency-specific cause.",
     "input_schema": {"type": "object", "properties": {"agency_id": {"type": "string"}},
                      "required": ["agency_id"]}},
    {"name": "check_local_donors",
     "description": "Whether retail donors in the same city are fading — a shared upstream community signal.",
     "input_schema": {"type": "object", "properties": {"agency_id": {"type": "string"}},
                      "required": ["agency_id"]}},
]

SYSTEM = """You are the investigation agent for a food bank's partner network.
A detection rule flagged an agency as silent. Investigate before recommending:
use your tools to establish (a) cold stop vs. taper, (b) isolated vs. regional
pattern, (c) any shared upstream donor signal. Then produce JSON:
{"hypothesis": one-sentence most-likely cause with evidence,
 "confidence": "high|medium|low",
 "pattern": "ISOLATED|REGIONAL",
 "channel": "email|call_first|escalate_to_director",
 "reasoning": 2-3 sentences citing the evidence you gathered,
 "outreach_draft": warm non-accusatory message (<=100 words) matched to your hypothesis}
Escalate to director only for regional patterns or large long-tenured agencies
stopping cold. Respond with JSON only."""

# ---------------- LIVE: Claude runs the loop ----------------
def investigate_live(flag):
    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content":
                 f"Flag: {json.dumps(flag)}. Agency name: {info.loc[flag['agency_id'],'name']}, "
                 f"city: {info.loc[flag['agency_id'],'city']}. Investigate and conclude."}]
    trace = []
    for _ in range(6):  # max tool rounds
        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=900,
                                      system=SYSTEM, tools=TOOL_SPECS, messages=messages)
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            text = "".join(b.text for b in resp.content if b.type == "text")
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text), trace
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            out = TOOLS[tu.name](**tu.input)
            trace.append({"tool": tu.name, "result": out})
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("agent did not conclude in 6 rounds")

# ---------------- DEMO: same tools, transparent heuristic synthesis ----------------
def investigate_demo(flag):
    aid = flag["agency_id"]
    hist = tool_order_history(aid)
    nbrs = tool_check_neighbors(aid)
    dnrs = tool_check_local_donors(aid)
    trace = [{"tool": "get_order_history", "result": hist},
             {"tool": "check_neighbor_agencies", "result": nbrs},
             {"tool": "check_local_donors", "result": dnrs}]

    name, city = info.loc[aid, "name"], info.loc[aid, "city"]
    tenure_yrs = round(hist["tenure_days"] / 365, 1)
    regional = nbrs["pattern"] == "REGIONAL"
    tapered = hist["volume_tapered_before_silence"]

    if regional:
        hyp = (f"Regional disruption in {city}: {len(nbrs['siblings_also_quiet'])} other "
               f"agencies there are also quiet — shared local cause more likely than "
               f"agency-specific failure.")
        channel, conf = "escalate_to_director", "medium"
    elif tapered:
        hyp = (f"Gradual decline: volume tapered before the silence, consistent with "
               f"shrinking capacity (volunteers, storage, or funding) rather than a "
               f"sudden closure.")
        channel, conf = "call_first", "medium"
    else:
        hyp = (f"Sudden organizational disruption: {tenure_yrs} years of steady rhythm, "
               f"then a cold stop with no taper — pattern matches coordinator loss or "
               f"abrupt operational failure.")
        channel = "call_first" if flag["days_quiet"] > 3 * flag["median_interval"] else "email"
        conf = "high" if tenure_yrs > 1.5 else "medium"

    donors_note = ""
    if dnrs.get("available") and dnrs.get("local_donors_fading"):
        donors_note = (f" Note: {len(dnrs['local_donors_fading'])} retail donor(s) in "
                       f"{city} are also fading — possible community-level stress signal "
                       f"worth logging for the quarterly root-cause report.")

    draft = (f"Hi {name} team,\n\nWe noticed a change in your usual ordering rhythm and "
             f"wanted to reach out personally. If anything has shifted on your end — "
             f"volunteers, space, funding, anything — we'd love to help you keep serving "
             f"your neighbors, whether that's delivery support, a schedule change, or "
             f"just a conversation. You matter to us.\n\nWarmly,\nAgency Relations")

    return {"hypothesis": hyp, "confidence": conf, "pattern": nbrs["pattern"],
            "channel": channel,
            "reasoning": (f"Order history shows {'a taper' if tapered else 'a cold stop'} "
                          f"after {tenure_yrs} yrs / {hist['orders_on_record']} orders. "
                          f"Neighbor check: {nbrs['pattern']} "
                          f"({len(nbrs['siblings_also_quiet'])} of {nbrs['sibling_agencies']} "
                          f"siblings quiet).{donors_note}"),
            "outreach_draft": draft}, trace

# ---------------- run ----------------
flags = detect_silent()
print(f"INVESTIGATION AGENT — {'LIVE (Claude tool-use)' if LIVE else 'DEMO (offline)'}")
print(f"Export as of {AS_OF.date()} — {len(flags)} silent agencies to investigate\n" + "=" * 70)

briefs = []
for flag in flags:
    result, trace = (investigate_live(flag) if LIVE else investigate_demo(flag))
    briefs.append({"flag": flag, "investigation": result, "tool_trace": trace})
    aid = flag["agency_id"]
    print(f"\n{info.loc[aid,'name']} ({info.loc[aid,'city']}) — "
          f"{flag['days_quiet']}d quiet (normal: {int(flag['median_interval'])}d)")
    print(f"  tools used: {', '.join(t['tool'] for t in trace)}")
    print(f"  pattern: {result['pattern']} | confidence: {result['confidence']} | "
          f"channel: {result['channel'].upper()}")
    print(f"  hypothesis: {result['hypothesis']}")
    print(f"  reasoning: {result['reasoning']}")

os.makedirs("output", exist_ok=True)
with open("output/investigations.json", "w") as f:
    json.dump(briefs, f, indent=2)
print(f"\n{'=' * 70}\nFull briefs (with drafted outreach) -> output/investigations.json")
