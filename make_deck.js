const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5

// Palette — Forest & Moss (food/harvest), red reserved strictly for silence flags
const FOREST = "1E4620", MOSS = "97BC62", CREAM = "F5F5F5", INK = "1A1A1A",
      RED = "C0392B", GREEN = "3E7C42", GRAY = "6B7280", WHITE = "FFFFFF";
const W = 13.33, H = 7.5;

// motif: status dots
function dot(slide, x, y, color, d = 0.16) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color } });
}
function dotRow(slide, x, y, n, redIdx = -1) {
  for (let i = 0; i < n; i++) dot(slide, x + i * 0.28, y, i === redIdx ? RED : MOSS, 0.14);
}
function pageNum(slide, n) {
  slide.addText(String(n), { x: W - 0.7, y: H - 0.5, w: 0.4, h: 0.3,
    fontSize: 10, color: GRAY, align: "right", fontFace: "Calibri", margin: 0 });
}

// ---------------- 1. TITLE (dark) ----------------
let s = pres.addSlide();
s.background = { color: FOREST };
// scattered network dots, one red
const pts = [[1.0,1.0],[2.1,0.7],[3.3,1.3],[11.2,0.9],[12.1,1.5],[10.4,6.3],[11.6,6.6],[1.2,6.4],[2.4,6.7],[12.3,3.6]];
pts.forEach(([x,y],i)=>dot(s,x,y,i===4?RED:MOSS,0.18));
s.addText("The Silence Agent", { x: 1.5, y: 2.35, w: 10.3, h: 1.2, fontSize: 54,
  bold: true, color: WHITE, fontFace: "Cambria", align: "center", margin: 0 });
s.addText("The most expensive supply-chain failures are the ones\nthat don't announce themselves.",
  { x: 2.2, y: 3.6, w: 8.9, h: 1.1, fontSize: 20, italic: true, color: MOSS,
    fontFace: "Calibri", align: "center", margin: 0 });
s.addText("AI vigilance for food bank partner networks  •  built for Food Bank of Contra Costa & Solano",
  { x: 2.2, y: 5.3, w: 8.9, h: 0.5, fontSize: 14, color: "CADCB8",
    fontFace: "Calibri", align: "center", margin: 0 });
s.addText("Nicole Trahan  •  AISCO Hackathon  •  July 2026", { x: 2.2, y: 6.55, w: 8.9,
  h: 0.4, fontSize: 12, color: "9FB18F", fontFace: "Calibri", align: "center", margin: 0 });

// ---------------- 2. THE PROBLEM ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Two unpredictable streams. Cash absorbs the failure.", { x: 0.6, y: 0.45,
  w: 12.1, h: 0.8, fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
s.addText("Food Bank of Contra Costa & Solano — from their own audited financial statements",
  { x: 0.6, y: 1.2, w: 12.1, h: 0.4, fontSize: 14, color: GRAY, fontFace: "Calibri", margin: 0 });
const stats = [
  ["–$6.1M", "FY2023 deficit when donations\nfell and demand didn't", FOREST],
  ["$10.8M", "spent panic-buying food that\nyear — double the next year", RED],
  ["Every 2 years", "how often partner agencies are\nmonitored (their own job posting)", RED],
];
stats.forEach((st, i) => {
  const x = 0.6 + i * 4.15;
  s.addShape("roundRect", { x, y: 2.0, w: 3.85, h: 2.5, fill: { color: CREAM },
    rectRadius: 0.08, shadow: { type: "outer", angle: 90, blur: 6, offset: 2, color: "999999", opacity: 0.3 } });
  s.addText(st[0], { x: x + 0.2, y: 2.25, w: 3.45, h: 0.95, fontSize: st[0].length > 8 ? 30 : 44,
    bold: true, color: st[2], fontFace: "Cambria", align: "center", margin: 0 });
  s.addText(st[1], { x: x + 0.25, y: 3.3, w: 3.35, h: 1.0, fontSize: 14, color: INK,
    fontFace: "Calibri", align: "center", margin: 0 });
});
s.addText([
  { text: "And the quietest failure of all:  ", options: { bold: true, color: INK } },
  { text: "when a partner pantry stops ordering or a grocery donor slowly fades, no alarm exists. Nobody notices until a neighborhood loses food access — or cash replaces donations that slipped away.",
    options: { color: INK } },
], { x: 0.6, y: 5.0, w: 12.1, h: 1.1, fontSize: 17, fontFace: "Calibri", margin: 0 });
dotRow(s, 0.6, 6.45, 14, 9);
s.addText("245 partner agencies — who notices when one goes quiet?", { x: 4.8, y: 6.32,
  w: 7.9, h: 0.4, fontSize: 13, italic: true, color: GRAY, fontFace: "Calibri", margin: 0 });
pageNum(s, 2);

// ---------------- 3. THE INSIGHT ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Their systems record everything — and watch nothing.", { x: 0.6, y: 0.45,
  w: 12.1, h: 0.8, fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
// left: what exists
s.addShape("roundRect", { x: 0.6, y: 1.6, w: 5.9, h: 4.3, fill: { color: CREAM }, rectRadius: 0.08 });
s.addText("What food banks have", { x: 0.95, y: 1.85, w: 5.2, h: 0.45, fontSize: 20,
  bold: true, color: FOREST, fontFace: "Calibri", margin: 0 });
s.addText([
  { text: "Ordering runs on Agency Express + Navision — every order logged (their AR job posting)", options: { bullet: true, breakLine: true } },
  { text: "Dashboards and reports — answers to questions someone thought to ask", options: { bullet: true, breakLine: true } },
  { text: "One Agency Relations coordinator (~$29/hr) carries ~245 partner relationships; formal monitoring = a site visit every other year (their own posting)", options: { bullet: true } },
], { x: 0.95, y: 2.45, w: 5.2, h: 3.1, fontSize: 15, color: INK, fontFace: "Calibri",
    paraSpaceAfter: 10, margin: 0 });
// right: what's missing
s.addShape("roundRect", { x: 6.85, y: 1.6, w: 5.9, h: 4.3, fill: { color: FOREST }, rectRadius: 0.08 });
s.addText("What nothing does", { x: 7.2, y: 1.85, w: 5.2, h: 0.45, fontSize: 20,
  bold: true, color: WHITE, fontFace: "Calibri", margin: 0 });
s.addText([
  { text: "Notice a pantry that broke its 2-year ordering rhythm", options: { bullet: true, breakLine: true } },
  { text: "Notice a donor shrinking 5% a month — every week looks normal; only the trend is abnormal", options: { bullet: true, breakLine: true } },
  { text: "These fail for human reasons: volunteer burnout, a manager change, quiet financial stress. Nobody calls the food bank.", options: { bullet: true } },
], { x: 7.2, y: 2.45, w: 5.2, h: 3.1, fontSize: 15, color: WHITE, fontFace: "Calibri",
    paraSpaceAfter: 10, margin: 0 });
s.addText([
  { text: "Their own AI-in-food-banking brief asks for exactly this (Theme 5):  ", options: { bold: true, color: FOREST } },
  { text: "warn ", options: { italic: true, color: FOREST } },
  { text: "\u201Cbefore neighbors quietly stop coming\u201D", options: { italic: true, bold: true, color: RED } },
  { text: " — and show up with support before a partner has to ask.", options: { italic: true, color: FOREST } },
], { x: 0.6, y: 6.25, w: 12.1, h: 0.55, fontSize: 16.5, fontFace: "Cambria",
    align: "center", margin: 0 });
pageNum(s, 3);

// ---------------- 4. THE AGENT ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Three agents. Three desks. One human decision.", { x: 0.6, y: 0.45, w: 12.1,
  h: 0.8, fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
const steps = [
  ["1  WATCHER", "Never sleeps. Two transparent rules learn every partner's own rhythm — auditable math decides WHETHER something is anomalous. No black box.", "silent pantry: gap > 2\u00D7 own median interval\nfading donor: 4-wk avg < 80% of prior 12 wks\n(+ same-time-last-year seasonal guard)"],
  ["2  INVESTIGATOR", "Gathers evidence with tools before recommending: order history (cold stop or taper?), neighbor agencies (isolated or regional?), local donors (shared upstream cause?). Produces hypothesis + confidence + purchase-impact estimate.", ""],
  ["3  DISPATCHER", "Routes each flag to the right desk with a drafted message: pantry flags \u2192 Agency Relations, donor flags \u2192 Food Sourcing, regional patterns \u2192 Director of Operations. A human reviews and sends — always.", ""],
];
steps.forEach((stp, i) => {
  const x = 0.6 + i * 4.15;
  s.addShape("roundRect", { x, y: 1.7, w: 3.85, h: 4.2, fill: { color: i === 1 ? FOREST : CREAM }, rectRadius: 0.08 });
  const fg = i === 1 ? WHITE : INK, hd = i === 1 ? MOSS : FOREST;
  s.addText(stp[0], { x: x + 0.25, y: 1.95, w: 3.35, h: 0.5, fontSize: 21, bold: true,
    color: hd, fontFace: "Calibri", margin: 0 });
  s.addText(stp[1], { x: x + 0.25, y: 2.55, w: 3.35, h: 2.4, fontSize: 13, color: fg,
    fontFace: "Calibri", margin: 0 });
  if (stp[2]) s.addText(stp[2], { x: x + 0.25, y: 4.85, w: 3.35, h: 1.0, fontSize: 10.5,
    italic: true, color: GREEN, fontFace: "Courier New", margin: 0 });
});
s.addText("Live example: one flagged agency in Antioch \u2192 investigator found two neighbors also dark \u2192 reclassified REGIONAL \u2192 dispatcher escalated to the director instead of emailing one pantry.",
  { x: 0.6, y: 6.15, w: 12.1, h: 0.7, fontSize: 14.5, bold: true, color: RED, fontFace: "Calibri",
    align: "center", margin: 0 });
pageNum(s, 4);

// ---------------- 5. PROOF (metrics + chart) ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Tested against a network we built to fail", { x: 0.6, y: 0.45, w: 12.1, h: 0.8,
  fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
s.addText("245 simulated agencies + 30 donors shaped to FBCCS's real scale. We injected 5 silent pantries and 3 fading donors — then scored the agent against the answer key.",
  { x: 0.6, y: 1.2, w: 12.1, h: 0.55, fontSize: 15, color: GRAY, fontFace: "Calibri", margin: 0 });
const proof = [
  ["5/5", "silent pantries caught"], ["3/3", "fading donors caught"],
  ["1.2%", "false-positive rate\n(3 courtesy calls per quarter)"],
];
proof.forEach((p, i) => {
  const x = 0.6 + i * 2.35;
  s.addText(p[0], { x, y: 2.15, w: 2.15, h: 0.9, fontSize: 48, bold: true, color: FOREST,
    fontFace: "Cambria", align: "center", margin: 0 });
  s.addText(p[1], { x, y: 3.05, w: 2.15, h: 0.85, fontSize: 12.5, color: INK,
    fontFace: "Calibri", align: "center", margin: 0 });
});
s.addChart("bar", [{
  name: "Days until a silent pantry is noticed",
  labels: ["Silence Agent", "Status quo (quarterly review)"],
  values: [17, 75],
}], {
  x: 7.6, y: 1.95, w: 5.1, h: 3.6, barDir: "bar",
  chartColors: [FOREST, "B9B9B9"],
  showTitle: true, title: "Days until a silent pantry is noticed",
  titleFontSize: 13, titleColor: INK,
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: INK, dataLabelFontSize: 14,
  catAxisLabelColor: INK, catAxisLabelFontSize: 12,
  valAxisLabelColor: GRAY, valAxisLabelFontSize: 10,
  valGridLine: { color: "E5E5E5", size: 1 }, catGridLine: { style: "none" },
  showLegend: false,
});
s.addText("58 days of invisible coverage gap, eliminated.", { x: 0.6, y: 4.35, w: 6.6,
  h: 0.5, fontSize: 19, bold: true, italic: true, color: RED, fontFace: "Cambria", margin: 0 });
s.addText("Then we tested blind: a second network the agent had never seen — different anomaly count, different dates, plus a trap: an agency that slowed but kept ordering. Result: 4/4 unseen silences caught, 0 missed, trap correctly NOT flagged (the per-agency baseline adapts).",
  { x: 0.6, y: 4.95, w: 6.6, h: 1.25, fontSize: 14, color: INK, fontFace: "Calibri", margin: 0 });
s.addText("Seeded and reproducible — the live demo runs this exact pipeline on the blind data.",
  { x: 0.6, y: 6.3, w: 12.1, h: 0.45, fontSize: 14, italic: true, color: GRAY,
    fontFace: "Calibri", margin: 0 });
pageNum(s, 5);

// ---------------- 6. THE MATH ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("What silence costs — at their audited $1.97/lb", { x: 0.6, y: 0.45, w: 12.1,
  h: 0.8, fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
const math = [
  ["One silent pantry (built)", "$4,300 / month", "1,100 lbs × 2 missed cycles × $1.97\n≈ 400–800 households unserved — invisibly"],
  ["One fading store (built)", "$31K / year", "300 lbs/wk lost × 52 × $1.97\n— and no single week looked wrong"],
  ["ROADMAP: forecasting trims panic-buying 5–10%", "$275–550K / year", "their purchased food swung\n$10.8M → $5.5M in one year"],
  ["Cost to run the agent", "< $1K / year", "nightly script + AI triage.\nTheir printer lease: $72K."],
];
math.forEach((mrow, i) => {
  const x = 0.6 + (i % 2) * 6.25, y = 1.65 + Math.floor(i / 2) * 2.45;
  s.addShape("roundRect", { x, y, w: 5.95, h: 2.2, fill: { color: i === 3 ? FOREST : CREAM }, rectRadius: 0.08 });
  const fg = i === 3 ? WHITE : INK, big = i === 3 ? MOSS : (i === 2 ? GREEN : RED);
  s.addText(mrow[0], { x: x + 0.3, y: y + 0.18, w: 5.35, h: 0.4, fontSize: 14, bold: true,
    color: fg, fontFace: "Calibri", margin: 0 });
  s.addText(mrow[1], { x: x + 0.3, y: y + 0.58, w: 5.35, h: 0.75, fontSize: 32, bold: true,
    color: big, fontFace: "Cambria", margin: 0 });
  s.addText(mrow[2], { x: x + 0.3, y: y + 1.38, w: 5.35, h: 0.75, fontSize: 12.5,
    color: i === 3 ? "D8E4CC" : GRAY, fontFace: "Calibri", margin: 0 });
});
s.addText("Honest sizing: low six figures directly, on a $157M operation — the cheapest lever with the most asymmetric payoff. You don't measure a smoke detector by average annual fire savings.",
  { x: 0.6, y: 6.45, w: 12.1, h: 0.65, fontSize: 15, bold: true, italic: true, color: FOREST,
    fontFace: "Cambria", align: "center", margin: 0 });
pageNum(s, 6);

// ---------------- 7. COVERAGE + SCALE ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Where this sits in the supply chain", { x: 0.6, y: 0.45,
  w: 12.1, h: 0.8, fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
const cov = [
  ["ACCEPTING DONATIONS", "COVERED", "Fading-donor detection catches inbound decline before the source is lost", GREEN],
  ["ALLOCATING & DISTRIBUTING", "COVERED", "Silent-pantry detection monitors the health of the 245-agency network — the mission's last mile", GREEN],
  ["PURCHASING", "EXPOSURE QUANTIFIED", "Every flag prices its replacement cost against their $5.5M purchased-food line; full forecasting = roadmap", MOSS],
  ["WAREHOUSING · PACKING · DELIVERY", "OUT OF SCOPE — DELIBERATELY", "The middle of the chain announces its own failures. We took the ends, where failure is silent.", GRAY],
];
cov.forEach((c, i) => {
  const y = 1.55 + i * 1.18;
  s.addShape("roundRect", { x: 0.6, y, w: 12.1, h: 1.0, fill: { color: CREAM }, rectRadius: 0.06 });
  s.addText(c[0], { x: 0.9, y: y + 0.12, w: 3.6, h: 0.75, fontSize: 14.5, bold: true,
    color: INK, fontFace: "Calibri", valign: "middle", margin: 0 });
  s.addText(c[1], { x: 4.5, y: y + 0.12, w: 2.6, h: 0.75, fontSize: 12.5, bold: true,
    color: c[3], fontFace: "Calibri", valign: "middle", margin: 0 });
  s.addText(c[2], { x: 7.2, y: y + 0.12, w: 5.2, h: 0.75, fontSize: 12, color: GRAY,
    fontFace: "Calibri", valign: "middle", margin: 0 });
});
s.addText("Built for one food bank by design — ports to ~200 Feeding America banks as-is (same ordering platforms, same CSV in, same digest out). Aggregated silences also map where the safety net is fraying: root-cause intelligence for the mission their board funded.",
  { x: 0.6, y: 6.35, w: 12.1, h: 0.75, fontSize: 14, italic: true, color: FOREST,
    fontFace: "Calibri", align: "center", margin: 0 });
pageNum(s, 7);

// ---------------- 8. SOURCES & EVIDENCE ----------------
s = pres.addSlide();
s.background = { color: WHITE };
s.addText("Every number has a document", { x: 0.6, y: 0.45, w: 12.1, h: 0.8,
  fontSize: 34, bold: true, color: INK, fontFace: "Cambria", margin: 0 });
const rows = [
  ["–$6.1M FY2023 · $10.8M \u2192 $5.5M purchased food", "FBCCS FY2024 audited financial statements (foodbankccs.org/about/financials)"],
  ["$1.97/lb valuation · 245 agencies · gov't grants $8.3M\u2192$4.8M · $500K Impact fund · $72K printer lease", "FBCCS FY2025 audited financials + single audit (ProPublica, EIN 94-2418054)"],
  ["Agencies monitored every other year · Navision + Agency Express · one coordinator, ~$29/hr", "FBCCS Agency Relations Food Access Coordinator job posting (foodbankccs.org/careers)"],
  ["\u201CBefore neighbors quietly stop coming\u201D — Theme 5; donor scoring — Theme 1", "AI wish list by Judge Daniel Rodriguez, supply chain leader, Alameda County Community Food Bank"],
  ["5/5 + 3/3 injected anomalies caught · 17-day detection · blind test 4/4 with trap passed", "Our prototype: seeded synthetic data, injected ground truth, reproducible on request"],
  ["53M Americans (1 in 6) use food banks", "Feeding America, via hackathon brief"],
];
rows.forEach((r, i) => {
  const y = 1.5 + i * 0.86;
  s.addText(r[0], { x: 0.6, y, w: 6.3, h: 0.8, fontSize: 12.5, bold: true, color: INK,
    fontFace: "Calibri", valign: "middle", margin: 0 });
  s.addText(r[1], { x: 7.05, y, w: 5.6, h: 0.8, fontSize: 11.5, color: GRAY,
    fontFace: "Calibri", valign: "middle", margin: 0 });
  if (i < rows.length - 1) s.addShape("line", { x: 0.6, y: y + 0.83, w: 12.05, h: 0,
    line: { color: "E5E5E5", width: 0.75 } });
});
s.addText("We never met their ops team — we read their filings. The first question of our pilot is the one their documents can't answer: which silence hurts most?",
  { x: 0.6, y: 6.75, w: 12.1, h: 0.55, fontSize: 13.5, italic: true, color: FOREST,
    fontFace: "Cambria", align: "center", margin: 0 });
pageNum(s, 8);

// ---------------- 9. CLOSE (dark) ----------------
s = pres.addSlide();
s.background = { color: FOREST };
dotRow(s, 4.3, 1.15, 17, 11);
s.addText("Nothing notices when the orders stop.", { x: 1.5, y: 2.05, w: 10.3, h: 0.9,
  fontSize: 40, bold: true, color: WHITE, fontFace: "Cambria", align: "center", margin: 0 });
s.addText("Now something does.", { x: 1.5, y: 3.0, w: 10.3, h: 0.9, fontSize: 40,
  bold: true, color: MOSS, fontFace: "Cambria", align: "center", margin: 0 });
s.addText("Food banking's future isn't more automation — it's anticipation.\nSilence is the one thing a dashboard can't anticipate, because it's the absence of data. That's the gap we closed.",
  { x: 1.7, y: 4.15, w: 9.9, h: 0.95, fontSize: 16, italic: true, color: "CADCB8",
    fontFace: "Cambria", align: "center", margin: 0 });
s.addText("Ask: a 2-week pilot with one food bank — a weekly CSV export in, a daily digest out. No new hardware, no integration project.\nSources: FBCCS FY2024–FY2025 audited financial statements, Form 990 (ProPublica, EIN 94-2418054), FBCCS job postings & partner-agency pages.",
  { x: 1.2, y: 5.35, w: 10.9, h: 1.0, fontSize: 12.5, color: "9FB18F", fontFace: "Calibri",
    align: "center", margin: 0 });
s.addText("Nicole Trahan", { x: 1.5, y: 6.3, w: 10.3, h: 0.4,
  fontSize: 13, color: "9FB18F", fontFace: "Calibri", align: "center", margin: 0 });

pres.writeFile({ fileName: "silence-agent-deck.pptx" }).then(() => console.log("written"));
