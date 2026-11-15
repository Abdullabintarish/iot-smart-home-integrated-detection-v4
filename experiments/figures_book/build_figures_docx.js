// Figures booklet: every figure in thesis_writing_package/Thesis_Figures_and_Tables_Index.md
// plus the v3 figures from make_v3_figures.py. Images are read only; nothing is redrawn here.
//   NODE_PATH=/opt/docbuild/node_modules node build_figures_docx.js <out.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, ImageRun, PageBreak, Footer,
  PageNumber, BorderStyle,
} = require("docx");

const HERE = __dirname;
const SUB = path.resolve(HERE, "..", "..");
const OUT = process.argv[2] || path.join(HERE, "Thesis_Figures.docx");

const INK = "1D2A33", MUTED = "5F6B73", ACCENT = "1F5F73";
const FONT = "Calibri";
const MAX_W = 620, MAX_H = 800;  // px at 96 dpi; A4 text block is about 624 x 900

const SECTIONS = [
  { title: "Part A. Figures used in Chapters 4 and 5", figs: [
    { no: "4.1", file: "code/demo/screenshots/1_overview.png",
      title: "Research Overview page of the demonstration app",
      text: "Overview page of the Streamlit demonstration app, showing the Run B headline results read from the saved pipeline outputs.",
      src: "results/stage5_report.json", status: "P" },
    { no: "5.1", file: "report/fig_metrics_comparison.png",
      title: "Detection metrics, fragmented baseline vs integrated condition",
      text: "Accuracy, macro precision, macro recall, macro F1, FPR and FNR on the 1,692,332 held-out test events. Fragmented: macro F1 0.995, FPR 0.005. Integrated: macro F1 0.834, FPR 0.102. The integrated condition scores worse on all six metrics.",
      src: "metrics/stage5_report.json", status: "P" },
    { no: "5.2", file: "report/fig_per_class_f1.png",
      title: "Per-class F1 on the held-out test events",
      text: "The integrated condition has a lower F1 than the baseline for every class. The largest gaps are for malware (1.000 → 0.587) and c2 (0.982 → 0.739), the two smallest classes.",
      src: "metrics/stage5_report.json → *.per_class", status: "P" },
    { no: "5.3", file: "report/fig_confusion_fragmented.png",
      title: "Confusion matrix, fragmented baseline",
      text: "Event counts with row-normalised shares; rows are actual classes and columns are predicted classes. 566 of 122,807 benign events are predicted as an attack (FPR 0.0046).",
      src: "metrics/stage5_report.json → fragmented.confusion_matrix", status: "P" },
    { no: "5.4", file: "report/fig_confusion_integrated.png",
      title: "Confusion matrix, integrated condition",
      text: "Incident predictions propagated to member events; same layout as Figure 5.3. The largest error is recon → dos (25,014). 12,540 of 122,807 benign events are predicted as an attack (FPR 0.1021).",
      src: "metrics/stage5_report.json → integrated.confusion_matrix", status: "P" },
    { no: "5.5", file: "report/fig_alert_reduction.png",
      title: "Alert reduction, overall",
      text: "4,211,383 raw events grouped into 704,090 incidents: an 83.3% reduction (mean 5.98 events per incident). Always report this next to the IoT-23 figure (42.09%, Figure 5.6).",
      src: "metrics/stage5_report.json → alert_reduction", status: "P" },
    { no: "5.6", file: "report/fig_alert_reduction_by_dataset.png",
      title: "Alert reduction by dataset (log scale)",
      text: "Bot-IoT: 3,000,000 events into 2,619 incidents (99.91%). IoT-23: 1,211,383 events into 701,471 incidents (42.09%). The overall 83.28% mostly reflects the large Bot-IoT flood and scan incidents.",
      src: "metrics/stage5_report.json → alert_reduction_by_dataset", status: "P" },
    { no: "5.x", file: "report/fig_importance_integrated.png",
      title: "Integrated model feature importance (optional, supports §5.3)",
      text: "Random Forest (Gini) importance. Only three of the seven incident features are used: span_s 0.361, events_per_s 0.334, n_events 0.305. The other four are constant in training and have importance 0.",
      src: "metrics/stage5_report.json → integrated.feature_importance", status: "P" },
    { no: "5.7", file: "experiments/thesis_report/fig_2_ablation.png",
      title: "Ablation: macro F1 and FPR by feature set and correlation window",
      text: "Mean over 5 seeds. Incident-only false-positive rates (about 9%) are omitted from the right panel so that the smaller differences stay visible.",
      src: "experiments/ablation/results/full/ablation_summary.csv", status: "S" },
    { no: "5.8", file: "experiments/thesis_report/fig_3_crosslog_seeds.png",
      title: "Cross-log macro F1 per seed and condition",
      text: "Cross-log conditions on the held-out captures across 20 seeds (R1). Interpret as in Chapter 5 §5.8.4.",
      src: "experiments/cross_log/results/stage4_results.json", status: "S" },
    { no: "5.y", file: "experiments/thesis_report/fig_1_runB_runT.png",
      title: "Run B vs Run T (optional)",
      text: "Fragmented vs integrated detection in Run B (incident-grouped split) and Run T (temporal hold-out). Run T accuracy is affected by the cut artefact in Bot-IoT DoS (Chapter 5 §5.6).",
      src: "metrics/stage5_report.json; ../thesis_final_validation/supplementary_temporal/code/results/stage5_report.json", status: "S" },
  ]},
  { title: "Part B. Appendix figures (run transcripts)", figs: [
    { no: "A.1", file: "report/fig_terminal_stage1.png",
      title: "Stage 1 collection transcript",
      text: "13 source files (10 IoT-23 Zeek captures, 3 Bot-IoT CSV files); 4,211,383 rows staged in 26 shards; peak RSS 556 MB; runtime 20 s.",
      src: "transcripts/stage1_run.log", status: "P" },
    { no: "A.2", file: "report/fig_terminal_run.png",
      title: "Stages 2–5 transcript",
      text: "Feature selection, correlation (704,090 incidents), detection on 1,692,332 held-out events and evaluation, including the bootstrap interval of the macro-F1 difference (−0.1614 [−0.2055, −0.1280]). Total 311.1 s, peak RSS 3,819 MB.",
      src: "transcripts/run_pipeline_run.log", status: "P" },
  ]},
  { title: "Part C. Supplementary v3 figures (corrected experiments, not yet in the chapters)", figs: [
    { no: "V3.1", file: "experiments/figures_book/v3_figures/fig_v3_1_loso_per_source.png",
      title: "Leave-one-source-out: macro F1 per unseen source",
      text: "Each of the 13 sources is held out in turn; values are the mean of 5 seeds. The source-specific baseline (frag_soft) is chosen without held-out labels. Incident context raises macro F1 on most sources but lowers it on several (for example IoT-23 1-1 and 42-1).",
      src: "experiments/v3/results/transfer/loso/metrics.json", status: "S" },
    { no: "V3.2", file: "experiments/figures_book/v3_figures/fig_v3_2_models_loso.png",
      title: "Model comparison on unseen sources (RF, HGB, LR)",
      text: "Mean over the 13 held-out sources. Event + incident beats event only for all three models (RF 0.372 → 0.441). None of the context gains is significant after Holm correction; only the comparisons of FPR against the baseline are.",
      src: "experiments/v3/results/transfer/loso/metrics.json; stats.json", status: "S" },
    { no: "V3.3", file: "experiments/figures_book/v3_figures/fig_v3_3_models_runB.png",
      title: "Model comparison on the Run B split (5 seeds)",
      text: "Mean ± sd over 5 seeds on the original Run B split. On this split event features alone already reach macro F1 ≈ 0.995 for RF and HGB. The FPR increase from context is specific to RF (+0.0076); HGB and LR decrease.",
      src: "experiments/v3/results/transfer/runB/metrics.json", status: "S" },
    { no: "V3.4", file: "experiments/figures_book/v3_figures/fig_v3_4_crosslog_primary.png",
      title: "Cross-log primary split with augmented training captures",
      text: "Mean macro F1 over 5 seeds with seed min–max whiskers. B − A = +0.214 (5/5 seeds positive), but the whole gain comes from capture 34-1; on 8-1, B and A are almost equal (0.526 vs 0.518).",
      src: "experiments/v3/results/cross_log/primary_augmented.json", status: "S" },
    { no: "V3.5", file: "experiments/figures_book/v3_figures/fig_v3_5_crosslog_loco.png",
      title: "Leave-one-capture-out: effect of incident context (B − A)",
      text: "Per-fold macro F1 difference, mean of 5 seeds, over 9 gated captures. 5 folds are positive and 4 negative; the positive mean is driven by 34-1 alone.",
      src: "experiments/v3/results/cross_log/loco.json", status: "S" },
  ]},
];

const STATUS = { P: "primary experiment (Run B)", S: "supplementary analysis" };

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}

function para(text, opts = {}, pOpts = {}) {
  return new Paragraph({ ...pOpts, children: [new TextRun({ text, font: FONT, color: INK, size: 22, ...opts })] });
}

const children = [];
// title page
children.push(new Paragraph({ spacing: { before: 2600 }, children: [] }));
children.push(new Paragraph({
  spacing: { after: 300 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 12 } },
  children: [new TextRun({ text: "Thesis Figures", font: FONT, size: 48, bold: true, color: INK })],
}));
children.push(para("Master's thesis, Part 2", { size: 30, color: ACCENT }, { spacing: { after: 200 } }));
children.push(para("Figures for Chapters 4–5, appendix transcripts and supplementary v3 results", { color: MUTED }, { spacing: { after: 600 } }));
children.push(para("Every figure is drawn from saved outputs; no model was retrained to produce this document. "
  + "Numbering follows thesis_writing_package/Thesis_Figures_and_Tables_Index.md. "
  + "Status P = primary experiment (Run B); S = supplementary analysis.", { size: 20, color: MUTED }));

// list of figures
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(para("List of figures", { size: 32, bold: true, color: ACCENT }, { spacing: { after: 200 } }));
for (const s of SECTIONS) {
  children.push(para(s.title, { bold: true, size: 21 }, { spacing: { before: 160, after: 60 } }));
  for (const f of s.figs) {
    children.push(para(`Figure ${f.no}   ${f.title}`, { size: 20 }, { spacing: { after: 30 }, indent: { left: 300 } }));
  }
}

for (const s of SECTIONS) {
  children.push(new Paragraph({ children: [new PageBreak()] }));
  children.push(para(s.title, { size: 32, bold: true, color: ACCENT }, { spacing: { after: 240 } }));
  s.figs.forEach((f, i) => {
    const file = path.join(SUB, f.file);
    const { w, h, data } = pngSize(file);
    const k = Math.min(MAX_W / w, MAX_H / h, 1);
    if (i > 0) children.push(new Paragraph({ children: [new PageBreak()] }));
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { after: 120 },
      children: [new ImageRun({ type: "png", data, transformation: { width: Math.round(w * k), height: Math.round(h * k) } })] }));
    children.push(new Paragraph({ keepNext: true, spacing: { before: 120, after: 80 }, children: [
      new TextRun({ text: `Figure ${f.no}. `, font: FONT, size: 21, bold: true, color: ACCENT }),
      new TextRun({ text: f.title, font: FONT, size: 21, bold: true, color: INK }) ] }));
    children.push(para(f.text, { size: 20 }, { keepNext: true, spacing: { after: 80 } }));
    children.push(para(`Source: ${f.src}   ·   Image: ${f.file}   ·   Status: ${f.status} (${STATUS[f.status]})`,
      { size: 16, italics: true, color: MUTED }));
  });
}

const doc = new Document({
  creator: "Thesis figures booklet",
  title: "Thesis Figures",
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 },
                          margin: { top: 1134, bottom: 1134, left: 1273, right: 1273 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: MUTED })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
