"""
Agent layer — turns detection flags into triaged, actionable briefs.

Two modes:
  LIVE (hackathon): calls Claude via the Anthropic API to reason over each flag,
        assign severity, and draft outreach. `pip install anthropic`, set ANTHROPIC_API_KEY.
  DEMO (offline):   deterministic templates so the pipeline runs with no network.

Design choice worth saying out loud in the pitch: the agent DRAFTS, a human SENDS.
Partner agencies are relationships, not tickets.
"""
import json
import os
from datetime import date

flags = json.load(open("output/flags.json"))
LIVE = bool(os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM = """You are the supply-chain vigilance agent for the Food Bank of Contra Costa & Solano.
You receive anomaly flags about partner agencies and retail donors. For each flag:
1. Assign severity (LOW/MEDIUM/HIGH) considering households served, pounds at stake, and duration.
2. Recommend ONE next action and which team owns it (Agency Relations, Food Resources, or Operations).
3. Draft a warm, non-accusatory outreach email (under 120 words). These are community partners,
   often volunteer-run; the tone is "checking in because we care," never "you missed an order."
Respond in JSON: {"severity": ..., "owner": ..., "action": ..., "email_subject": ..., "email_body": ...}"""

def triage_live(flag):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(flag)}],
    )
    text = msg.content[0].text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def triage_demo(flag):
    if flag["type"] == "silent_agency":
        sev = "HIGH" if flag["households_served"] > 500 or flag["missed_cycles"] >= 3 else "MEDIUM"
        return {
            "severity": sev,
            "owner": "Agency Relations",
            "action": f"Call {flag['name']} ({flag['city']}) today; if unreachable in 48h, "
                      f"arrange temporary coverage for ~{flag['households_served']} households "
                      f"via nearest partner.",
            "email_subject": f"Checking in from the Food Bank — anything you need?",
            "email_body": (
                f"Hi {flag['name']} team,\n\nWe noticed it's been about "
                f"{flag['days_since_last_order']} days since your last order, and you're usually "
                f"with us every {int(flag['median_interval_days'])} days — so we wanted to check in "
                f"and make sure everything's okay on your end. If anything has changed (volunteers, "
                f"storage, schedules), we'd love to help — including delivery options or a temporary "
                f"adjustment. The neighbors you serve matter to us, and so do you.\n\n"
                f"Warmly,\nAgency Relations, Food Bank of Contra Costa & Solano"
            ),
        }
    else:  # fading_donor
        sev = "HIGH" if flag["decline_pct"] > 30 else "MEDIUM"
        return {
            "severity": sev,
            "owner": "Food Resources",
            "action": f"Schedule store visit with {flag['name']} ({flag['chain']}, {flag['city']}); "
                      f"pickups down {flag['decline_pct']}% — check for staffing/manager change; "
                      f"if unresolved, budget ~${int(flag['annualized_replacement_usd']):,}/yr replacement.",
            "email_subject": "Thank you — and a quick check-in on pickups",
            "email_body": (
                f"Hi {flag['name']} team,\n\nThank you for everything you donate — it matters "
                f"enormously to our community. We've noticed recent pickups are running a bit lighter "
                f"than usual and wanted to check whether anything has changed on your end — staffing, "
                f"scheduling, or how we can make donating easier. We're happy to adjust pickup times "
                f"or provide extra bins.\n\nWith gratitude,\nFood Resources, "
                f"Food Bank of Contra Costa & Solano"
            ),
        }

briefs = []
for flag in flags:
    result = triage_live(flag) if LIVE else triage_demo(flag)
    briefs.append({"flag": flag, "triage": result})

briefs.sort(key=lambda b: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[b["triage"]["severity"]]))

with open("output/briefs.json", "w") as f:
    json.dump(briefs, f, indent=2)

# ---- daily digest (what staff actually sees) ----
lines = [f"SILENCE REPORT — {date.today().isoformat()}  (mode: {'LIVE' if LIVE else 'DEMO'})",
         "=" * 60]
for b in briefs:
    f_, t = b["flag"], b["triage"]
    if f_["type"] == "silent_agency":
        headline = (f"[{t['severity']}] SILENT AGENCY: {f_['name']} ({f_['city']}) — "
                    f"{f_['days_since_last_order']}d quiet (normal: every "
                    f"{int(f_['median_interval_days'])}d) — ~{int(f_['est_undelivered_lbs']):,} lbs "
                    f"/ ${int(f_['est_undelivered_usd']):,} undelivered — "
                    f"{f_['households_served']} households affected")
    else:
        headline = (f"[{t['severity']}] FADING DONOR: {f_['name']} ({f_['city']}) — "
                    f"down {f_['decline_pct']}% — ${int(f_['annualized_replacement_usd']):,}/yr "
                    f"replacement cost if lost")
    lines.append(headline)
    lines.append(f"    -> {t['owner']}: {t['action']}")
    lines.append("")

digest = "\n".join(lines)
with open("output/daily_digest.txt", "w") as f:
    f.write(digest)
print(digest)
