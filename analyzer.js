/* Silence Agent — donor inflow analyzer, JS port of analyzer.py (Master Prompt v1.0).
   Pure functions over an array-of-arrays log. Used by index.html; testable in Node. */
"use strict";

const CONFIG = {
  fading_threshold: 0.80,
  cv_threshold: 0.75,
  min_receipts: 6,
  supply_drop_pct: 0.10,
  category_exposure_pct: 0.30,
  max_tasks: 15,
  window_weeks: 16,
};

const HEADER_CANDIDATES = {
  donor_name: ["sourcedonor", "donor", "donorname", "donorid", "source"],
  receipt_date: ["datereceived", "receiptdate", "date", "received"],
  weight_lbs: ["weightlb", "weightlbs", "weight", "lbs", "pounds", "netweight"],
  item: ["itemname", "productdescription", "product", "description", "item"],
  category: ["category", "productcategory", "foodcategory"],
  donation_type: ["donationtype", "sourcetype", "type"],
  notes: ["inspectionnotes", "notes", "condition"],
  recall: ["recallstatus", "recall", "hold"],
  expected_qty: ["expectedqty", "qtyexpected", "expectedunits"],
  received_qty: ["qtyreceivedunits", "receivedqty", "qtyreceived", "unitsreceived"],
};

const CATEGORY_RULES = [
  ["Produce", /apple|banana|zucchini|corn|pepper|melon|strawberr|greens|tomato|peach|stone fruit|salad mix|bagged salad|produce/],
  ["Protein", /turkey|chicken|beef|pork|deli meat|fish|meat/],
  ["Dairy & Eggs", /butter|egg|cheese|milk|yogurt|dairy/],
  ["Bakery & Prepared", /bread|bakery|pastry|bagel|sandwich|salads|dough|prepared|caf/],
  ["Shelf-Stable", /sugar|rice|pasta|dried fruit|snack|peanut butter|bean|canned|cereal|shelf|chocolate|candy|jelly|commodit|box/],
];

const DONOR_TYPE_PATTERN = /donat|drive/;
const NON_DONOR_PATTERN = /purchas|usda|tefap|csfp/;
const REJECT_PATTERN = /reject|culled|spoil|discard/;

const norm = (s) => String(s ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");

/* ---- date handling: everything becomes an integer epoch-day (UTC) ---- */
function toEpochDay(v) {
  if (v == null || v === "") return null;
  if (typeof v === "number" && isFinite(v)) {           // Excel serial
    const d = Math.floor(v) - 25569;
    return d > -20000 && d < 200000 ? d : null;
  }
  if (v instanceof Date && !isNaN(v)) {
    return Math.round(Date.UTC(v.getUTCFullYear(), v.getUTCMonth(), v.getUTCDate()) / 86400000);
  }
  const t = Date.parse(String(v).trim());
  return isNaN(t) ? null : Math.floor((t + 43200000) / 86400000); // noon-shift kills tz drift
}
const dayToISO = (d) => new Date(d * 86400000).toISOString().slice(0, 10);
const mondayOf = (d) => d - (((d + 3) % 7 + 7) % 7);   // epoch day 0 = Thu; Mon-start week

/* ---- Step 0: header detection + mapping ---- */
function detectHeader(rows) {
  const required = [HEADER_CANDIDATES.donor_name, HEADER_CANDIDATES.receipt_date,
                    HEADER_CANDIDATES.weight_lbs];
  for (let i = 0; i < Math.min(10, rows.length); i++) {
    const cells = (rows[i] || []).filter((v) => v != null && v !== "").map(norm);
    const hits = required.filter((cands) =>
      cands.some((cand) => cells.some((c) => c === cand || c.includes(cand)))).length;
    if (hits === 3) {
      const cols = (rows[i] || []).map((v, j) => v != null && String(v).trim() !== "" ? String(v).trim() : `col${j}`);
      return { cols, data: rows.slice(i + 1).filter((r) => r && r.some((v) => v != null && v !== "")) };
    }
  }
  const cols = (rows[0] || []).map((v, j) => v != null ? String(v).trim() : `col${j}`);
  return { cols, data: rows.slice(1) };
}

function mapHeaders(cols) {
  const mapping = {};
  const used = new Set();
  const normed = cols.map((c) => norm(c));
  for (const [canon, cands] of Object.entries(HEADER_CANDIDATES)) {
    for (const cand of cands) {
      const idx = normed.findIndex((n, j) => !used.has(j) && (n === cand || n.includes(cand)));
      if (idx !== -1) { mapping[canon] = idx; used.add(idx); break; }
    }
  }
  const missing = ["donor_name", "receipt_date", "weight_lbs"].filter((f) => !(f in mapping));
  if (missing.length) {
    throw new Error(`Required field(s) could not be mapped: ${missing.join(", ")}. Columns found: ${cols.join(", ")}`);
  }
  return mapping;
}

const categorize = (item) => {
  const s = String(item ?? "").toLowerCase();
  for (const [cat, pat] of CATEGORY_RULES) if (pat.test(s)) return cat;
  return "Other";
};

/* ---- Step 0b: clean ---- */
function clean(cols, data, mapping) {
  const rep = { merges: [], dropped_dates: 0, invalid_weights: 0,
                excluded_non_donor: {}, rows_in: data.length };
  let rows = data.map((r) => {
    const get = (f) => (f in mapping ? r[mapping[f]] : undefined);
    return {
      donor_name: String(get("donor_name") ?? "").trim().replace(/\s+/g, " "),
      day: toEpochDay(get("receipt_date")),
      weight: Number(get("weight_lbs")),
      item: String(get("item") ?? ""),
      category: "category" in mapping ? String(get("category")) : categorize(get("item")),
      donation_type: String(get("donation_type") ?? ""),
      notes: String(get("notes") ?? ""),
      shortfall: ("expected_qty" in mapping && "received_qty" in mapping)
        ? Number(get("received_qty")) < Number(get("expected_qty")) : false,
    };
  });

  rows = rows.filter((r) => !["", "nan", "none", "undefined"].includes(r.donor_name.toLowerCase()));

  // donor inflows only
  if (rows.some((r) => r.donation_type.trim() !== "")) {
    const excluded = rows.filter((r) => {
      const t = r.donation_type.toLowerCase();
      return !(DONOR_TYPE_PATTERN.test(t) && !NON_DONOR_PATTERN.test(t));
    });
    for (const r of excluded) rep.excluded_non_donor[r.donation_type] = (rep.excluded_non_donor[r.donation_type] || 0) + 1;
    rows = rows.filter((r) => !excluded.includes(r));
  } else {
    const drop = rows.filter((r) => NON_DONOR_PATTERN.test(r.donor_name.toLowerCase()));
    for (const r of drop) rep.excluded_non_donor[r.donor_name] = (rep.excluded_non_donor[r.donor_name] || 0) + 1;
    rows = rows.filter((r) => !drop.includes(r));
  }

  rep.dropped_dates = rows.filter((r) => r.day == null).length;
  rows = rows.filter((r) => r.day != null);
  rep.invalid_weights = rows.filter((r) => !isFinite(r.weight) || r.weight <= 0).length;
  rows = rows.filter((r) => isFinite(r.weight) && r.weight > 0);

  // merge donor-name variants (casefold/punct-insensitive; canonical = mode)
  const byKey = {};
  for (const r of rows) {
    const k = norm(r.donor_name);
    (byKey[k] = byKey[k] || []).push(r.donor_name);
  }
  const canonical = {};
  for (const [k, names] of Object.entries(byKey)) {
    const counts = {};
    for (const n of names) counts[n] = (counts[n] || 0) + 1;
    const canon = Object.entries(counts).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0][0];
    canonical[k] = canon;
    const variants = [...new Set(names)].filter((n) => n !== canon).sort();
    if (variants.length) rep.merges.push(`${variants.join(" / ")} -> ${canon}`);
  }
  for (const r of rows) {
    r.donor_name = canonical[norm(r.donor_name)];
    r.rejected = REJECT_PATTERN.test(r.notes.toLowerCase());
  }
  rep.rows_kept = rows.length;
  return { rows, rep };
}

/* ---- helpers ---- */
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
const stdPop = (a) => { const m = mean(a); return Math.sqrt(mean(a.map((x) => (x - m) ** 2))); };
const r2 = (x) => (isFinite(x) ? Math.round(x * 100) / 100 : null);
const r1 = (x) => Math.round(x * 10) / 10;

function pctRank(values) {           // pandas rank(pct=True), average method
  const n = values.length;
  const sorted = values.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
  const out = new Array(n);
  let i = 0;
  while (i < n) {
    let j = i;
    while (j + 1 < n && sorted[j + 1][0] === sorted[i][0]) j++;
    const avgRank = (i + j + 2) / 2;   // 1-based average rank
    for (let k = i; k <= j; k++) out[sorted[k][1]] = avgRank / n;
    i = j + 1;
  }
  return out;
}

/* ---- Step 1: analyze ---- */
function analyze(rows, config = CONFIG) {
  const anchor = Math.max(...rows.map((r) => r.day));
  const windowStart = anchor - config.window_weeks * 7;
  const d = rows.filter((r) => r.day > windowStart);
  for (const r of d) r.week = mondayOf(r.day);

  const firstWeek = Math.min(...d.map((r) => r.week));
  const anchorWeek = mondayOf(anchor);
  const allWeeks = [];
  for (let w = firstWeek; w <= anchorWeek; w += 7) allWeeks.push(w);
  const nWeeks = allWeeks.length;
  const wIdx = Object.fromEntries(allWeeks.map((w, i) => [w, i]));

  const donors = [...new Set(d.map((r) => r.donor_name))].sort();
  const piv = Object.fromEntries(donors.map((n) => [n, new Array(nWeeks).fill(0)]));
  for (const r of d) piv[r.donor_name][wIdx[r.week]] += r.weight;

  const nRecent = Math.min(4, Math.max(1, nWeeks - 1));
  const nBaseline = nWeeks - nRecent;

  const grp = Object.fromEntries(donors.map((n) => [n, d.filter((r) => r.donor_name === n)]));
  const allCats = new Set(d.map((r) => r.category)).size;
  const totals = donors.map((n) => grp[n].reduce((s, r) => s + r.weight, 0));
  const amountPct = pctRank(totals);

  const dn = donors.map((n, i) => {
    const wk = piv[n];
    const recent = mean(wk.slice(-nRecent));
    const baseline = mean(wk.slice(0, nBaseline));
    const receipts = grp[n].length;
    const total = totals[i];
    const ratio = baseline > 0 ? recent / baseline : NaN;
    const m = mean(wk);
    const cv = m > 0 ? stdPop(wk) / m : NaN;
    let fading;
    if (receipts < config.min_receipts) fading = "insufficient_data";
    else if (baseline === 0) fading = recent > 0 ? "new_donor" : "insufficient_data";
    else fading = ratio < config.fading_threshold;
    const weeksActive = wk.filter((x) => x > 0).length;
    const consistency = (weeksActive / nWeeks) * 2.5;
    const amount = amountPct[i] * 2.5;
    const quality = (1 - mean(grp[n].map((r) => (r.rejected ? 1 : 0)))) * 2.5;
    const variety = Math.min((new Set(grp[n].map((r) => r.category)).size / allCats) * 2.5, 2.5);
    return {
      donor_name: n,
      donor_score: r1(consistency + amount + quality + variety),
      score_basis: "4 of 4 components",
      consistency: r1(consistency), amount: r1(amount),
      quality: r1(quality), variety: r1(variety),
      total_lbs_16wk: Math.round(total),
      recent_avg_wk_lbs: Math.round(recent),
      baseline_avg_wk_lbs: Math.round(baseline),
      fading_ratio: r2(ratio),
      fading_donor: fading,
      volatility_cv: r2(cv),
      volatile: isFinite(cv) && cv > config.cv_threshold,
      last_receipt_date: dayToISO(Math.max(...grp[n].map((r) => r.day))),
      receipts_count: receipts,
    };
  }).sort((a, b) => b.donor_score - a.donor_score);

  // category exposure of fading donors
  const fadingNames = new Set(dn.filter((r) => r.fading_donor === true).map((r) => r.donor_name));
  const catTot = {}, catFad = {}, fadingByCat = {};
  for (const r of d) {
    catTot[r.category] = (catTot[r.category] || 0) + r.weight;
    if (fadingNames.has(r.donor_name)) {
      catFad[r.category] = (catFad[r.category] || 0) + r.weight;
      (fadingByCat[r.category] = fadingByCat[r.category] || {});
      fadingByCat[r.category][r.donor_name] = (fadingByCat[r.category][r.donor_name] || 0) + r.weight;
    }
  }
  const exposure = Object.entries(catTot)
    .map(([c, t]) => [c, (catFad[c] || 0) / t])
    .sort((a, b) => b[1] - a[1]);

  return {
    donors: dn, anchor,
    window: [Math.min(...d.map((r) => r.day)), anchor],
    n_weeks: nWeeks, n_recent: nRecent, n_baseline: nBaseline,
    weekly: piv, all_weeks: allWeeks,
    exposure, cat_totals: catTot, fading_by_cat: fadingByCat,
    total_lbs: Math.round(d.reduce((s, r) => s + r.weight, 0)),
    config, detail: d,
  };
}

/* ---- Step 2: follow-up tasks ---- */
function buildFollowups(res) {
  const cfg = res.config, dn = res.donors;
  const fading = dn.filter((r) => r.fading_donor === true);
  const tasks = [];
  const add = (task, why, donor, role, deadline, draft = "") =>
    tasks.push({ task, why, donor_name: donor, assigned_role: role,
                 suggested_deadline: deadline, draft_outreach: draft });

  const top5 = new Set([...dn].sort((a, b) => b.total_lbs_16wk - a.total_lbs_16wk)
                       .slice(0, 5).map((r) => r.donor_name));
  const esc = fading.filter((r) => top5.has(r.donor_name));
  if (esc.length) {
    const names = esc.map((r) => r.donor_name).join(", ");
    add(`Escalation: top-5-by-pounds donor(s) fading — ${names}`,
        esc.map((r) => `${r.donor_name}: ${r.recent_avg_wk_lbs} vs ${r.baseline_avg_wk_lbs} lbs/wk (ratio ${r.fading_ratio})`).join("; "),
        names, "Director of Operations", "within 3 days");
  }
  const hot = Object.entries(res.fading_by_cat)
    .map(([c, m]) => [c, Object.keys(m).length]).filter(([, n]) => n >= 3)
    .sort((a, b) => b[1] - a[1]);
  if (hot.length) {
    const [cat, n] = hot[0];
    add(`Escalation: ${n} donors fading simultaneously in ${cat}`,
        `${n} donors in ${cat} have fading_ratio < ${cfg.fading_threshold}`,
        "", "Director of Operations", "within 3 days");
  }

  for (const r of fading.filter((x) => x.donor_score >= 6).sort((a, b) => b.donor_score - a.donor_score)) {
    add(`Reach out to ${r.donor_name} — valuable relationship at risk`,
        `score ${r.donor_score}/10; recent ${r.recent_avg_wk_lbs} lbs/wk vs baseline ${r.baseline_avg_wk_lbs} (ratio ${r.fading_ratio}, threshold ${cfg.fading_threshold})`,
        r.donor_name, "Donor Relations", "within 1 week",
        `Hi ${r.donor_name} team, thank you for everything you make possible for our neighbors. We noticed your recent donations have been lighter than usual and wanted to check in — has anything changed on your end? We'd love to find a pickup schedule or logistics setup that works better for you.`);
  }

  const gap = Math.round(fading.reduce((s, r) => s + r.baseline_avg_wk_lbs - r.recent_avg_wk_lbs, 0));
  const totalBase = Math.round(dn.reduce((s, r) => s + r.baseline_avg_wk_lbs, 0));
  if (totalBase > 0 && gap / totalBase >= cfg.supply_drop_pct) {
    add("Model backfill via choice loads/purchases for fading-donor gap",
        `Fading donors are down ${gap.toLocaleString()} lbs/wk combined vs baseline — ${Math.round(gap / totalBase * 100)}% of total baseline inflow (${totalBase.toLocaleString()} lbs/wk), above the ${Math.round(cfg.supply_drop_pct * 100)}% trigger`,
        "", "Procurement Analyst", "within 1 week");
  }

  for (const [cat, share] of res.exposure.filter(([, s]) => s >= cfg.category_exposure_pct)) {
    const who = Object.keys(res.fading_by_cat[cat] || {});
    add(`Review stock thresholds for ${cat} — fading donors supply ${Math.round(share * 100)}% of it`,
        `Fading donors (${who.join(", ")}) supplied ${Math.round(share * 100)}% of ${cat} pounds (${Math.round(res.cat_totals[cat]).toLocaleString()} lbs total in window); trigger is ${Math.round(cfg.category_exposure_pct * 100)}%`,
        who.join(", "), "Inventory Manager", "within 2 weeks");
  }

  const vol = dn.filter((r) => r.volatile && r.fading_donor !== "insufficient_data");
  if (vol.length) {
    const names = vol.map((r) => r.donor_name).join(", ");
    add(`Review receiving schedule/dock plan for volatile donors: ${names}`,
        vol.map((r) => `${r.donor_name} CV ${r.volatility_cv}`).join("; ") + ` (threshold ${cfg.cv_threshold})`,
        names, "Warehouse Manager", "within 2 weeks");
  }
  const short = [...new Set(res.detail.filter((r) => r.shortfall).map((r) => r.donor_name))];
  if (short.length) {
    add(`Investigate expected-vs-received shortfalls: ${short.join(", ")}`,
        "Repeated shortfalls in receiving log", short.join(", "),
        "Warehouse Manager", "within 2 weeks");
  }

  for (const r of dn.slice(0, 10).filter((x) => x.fading_donor !== true).slice(0, 2)) {
    add(`Appreciation touch for ${r.donor_name}`,
        `Top-10 donor (score ${r.donor_score}/10, ${r.total_lbs_16wk.toLocaleString()} lbs in window), not fading — periodic thank-you`,
        r.donor_name, "Donor Relations", "within 2 weeks",
        `Hi ${r.donor_name} team, no ask here — just a heartfelt thank you. Your ${r.total_lbs_16wk.toLocaleString()} lbs over the past weeks have been among our most reliable sources of food for local families. We're grateful for you.`);
  }

  return tasks.slice(0, cfg.max_tasks).map((t, i) => ({ priority: i + 1, ...t }));
}

/* ---- end-to-end ---- */
function runPipeline(aoa) {
  const { cols, data } = detectHeader(aoa);
  const mapping = mapHeaders(cols);
  const mappingNames = Object.fromEntries(Object.entries(mapping).map(([k, j]) => [k, cols[j]]));
  const { rows, rep } = clean(cols, data, mapping);
  if (!rows.length) throw new Error("No usable donor rows after cleaning.");
  const res = analyze(rows);
  const followups = buildFollowups(res);
  return { res, followups, rep, mapping: mappingNames };
}

if (typeof module !== "undefined") {
  module.exports = { CONFIG, detectHeader, mapHeaders, clean, analyze, buildFollowups,
                     runPipeline, dayToISO, toEpochDay };
}
