# The Silence Agent — Food Bank Supply-Chain Vigilance

*AISCO Hackathon 2026 · Honorable Mention · built for the Food Bank of Contra Costa & Solano (FBCCS)*

> **Just want to see the interface?** The browser-only version, with no install and no AI connection, is at [n-trahan/silence_agent_lite](https://github.com/n-trahan/silence_agent_lite).

**Thesis:** the most expensive supply-chain failures produce no signal. The ordering system records every order, but nothing notices when orders *stop*. The Silence Agent watches for absence: partner agencies that go quiet and retail donors whose pickups quietly fade. It then investigates each flag and drafts outreach for a human to review and send.

## Architecture

```
deterministic sensors  ->  agentic analyst  ->  human actuator
 (pandas rules)            (Claude + 3 tools)     (staff review & send)
```

- **Math decides *whether* something is anomalous**, so detection stays auditable.
- **The agent decides *what it means and what to do*.** It works out a likely cause, a confidence level, whether the problem is isolated or regional, and which channel to use.
- **A human decides to act.** Partners are relationships, not tickets.

### 1. Watcher (detection, no LLM)
- **Silent agency:** `days_since_last_order > 2.0 × that agency's own median order interval`. The baseline adapts to each agency, so one that moves from weekly to biweekly ordering is not flagged.
- **Fading donor:** `4-week avg < 0.80 × prior 12-week avg`, and also below the same period last year. The year-over-year guard suppresses seasonal false alarms.

### 2. Investigator (Claude via the Anthropic API)
For each flag, three Python tools gather structured evidence:

| Tool | Question it answers |
|---|---|
| `get_order_history` | Did volume taper before the silence, or stop cold? |
| `check_neighbor_agencies` | Are nearby agencies also quiet? (isolated vs. regional) |
| `check_local_donors` | Are local donors fading too? (shared upstream cause) |

Claude returns JSON with a hypothesis, a confidence level, a pattern (`ISOLATED`/`REGIONAL`), a channel (`email` / `call_first` / `escalate_to_director`), its reasoning, and an outreach draft written for that case.

### 3. Dispatcher
Routes each flag to the owning team (Agency Relations, Food Resources, or Operations), escalating regional patterns to the director, with the drafted message attached.

## Two modes

| Mode | When | What happens |
|---|---|---|
| **Live** | `ANTHROPIC_API_KEY` is set | `investigate.py`: Claude runs the full tool-use loop, choosing which tools to call and when to conclude (up to 6 rounds). `app_weekly.py`: the tools run in a fixed order, then one Claude call writes the brief. |
| **Offline** | no key | The same tools run in a fixed order, and a transparent rule-based analyst writes a brief with the same output shape. No network needed. |

If a live call fails (wifi, rate limit, bad key), the app shows a notice and falls back to offline mode, so the demo never breaks. The model is set to `claude-sonnet-4-6` in `investigate.py`, `app_weekly.py`, and `agent.py`.

## Run it

```bash
pip install -r requirements.txt

# Offline mode (no key needed)
python3 -m streamlit run app_weekly.py

# Live Claude mode
export ANTHROPIC_API_KEY=sk-ant-...      # lasts for this terminal session only
python3 -m streamlit run app_weekly.py
```

**Weekly workflow demo (`app_weekly.py`):** upload `demo_uploads/orders_export_*.csv` in date order to watch the network change week to week. Or upload the blind test export (`blind_test/orders_export_2026-07-13.csv`), click **Investigate** on agency **B013 (Antioch)**, and see it escalate as a *regional* pattern: two neighboring Antioch agencies are also dark.

**Terminal agent (the clearest demonstration of tool use):**
```bash
python3 investigate.py blind_test/orders_export_2026-07-13.csv
```

**Full pipeline on synthetic data:**
```bash
python3 generate_data.py   # 2 years of seeded synthetic history + injected ground truth
python3 detect.py          # runs detection, scores against the answer key
python3 agent.py           # triages flags, drafts outreach, prints a daily digest
python3 -m streamlit run app.py   # time-slider map demo
```

Never commit your API key. `.env` files are already excluded in `.gitignore`.

## Results (reproducible, seeded)

All data is **synthetic**. It is shaped like an FBCCS receiving log and order export, not real records.

**Blind test** (`blind_test/`, answer key sealed in `ANSWER_KEY.json`):
- 4 of 4 injected silent agencies caught
- 1 false positive (B141)
- The "trap" agency (B048), which slowed its ordering but kept ordering, was correctly *not* flagged

**Development dataset** (`generate_data.py`, seed 42, scored by `detect.py`):

| Metric | Result |
|---|---|
| Silent agencies caught | 4 of 5 (missed A227) |
| Fading donors caught | 1 of 3 (missed D13, D29) |
| False positives | 2 agencies (0.8% of 245), 0 donors |
| Median time to detection | 16 days vs. ~75 days for a quarterly review |
| Undelivered food surfaced | ~18K lbs / ~$35K at FBCCS's audited $1.97/lb |

Dollar figures estimate exposure, not measured savings.

## Grounded in FBCCS public filings
- FY2023 purchased food of $10.8M vs. $5.5M in FY2024 (audited financial statements)
- $1.97/lb in-kind valuation (Feeding America cost-study method, FY2025 audited statements, Notes 5–6)
- ~245 partner agencies, monitored formally every other year (FBCCS job posting)
- Design informed by interviews with FBCCS and Alameda County Community Food Bank staff

## Deploying for real
A weekly CSV export of `(agency_id, order_date, pounds)`, plus optionally `(donor_id, week_start, pounds)`, is all it needs. No system replacement, no new hardware.

## Repo contents

| Path | Purpose |
|---|---|
| `app_weekly.py` | Streamlit weekly workflow: upload, flags, Investigate button, live/offline Claude path |
| `app.py` | Streamlit time-slider map demo (offline) |
| `investigate.py` | Terminal investigation agent with the full Claude tool-use loop |
| `agent.py` | Triage, severity, routing, and drafted outreach (optional live Claude) |
| `detect.py` | Detection rules, scored against ground truth |
| `generate_data.py` | Seeded synthetic network (245 agencies, 30 donors, 2 years) |
| `make_weekly_exports.py` | Builds the `demo_uploads/` weekly CSVs |
| `make_blind_test.py` | Builds the sealed `blind_test/` network and answer key |
| `make_deck.js`, `silence-agent-deck.pptx` | Pitch deck and its generator |
| `data/`, `demo_uploads/`, `blind_test/`, `output/` | Synthetic data and sample outputs |

---

*Built by Nicole Trahan, Karen Wu, and Sai for the AISCO Hackathon, July 2026. The earlier browser-only version lives at [silence_agent_lite](https://github.com/n-trahan/silence_agent_lite).*
