// Render content.json (from build_content.py) into a Word document.
//   NODE_PATH=/opt/docbuild/node_modules node build_docx.js <out.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow,
  TableCell, WidthType, ShadingType, BorderStyle, ImageRun, PageBreak, Footer, Header,
  PageNumber, LevelFormat, TableLayoutType,
} = require("docx");

const HERE = __dirname;
const content = JSON.parse(fs.readFileSync(path.join(HERE, "content.json"), "utf8"));
const OUT = process.argv[2] || path.join(HERE, "Thesis_Experiments_Report.docx");

const INK = "1D2A33", MUTED = "5F6B73", ACCENT = "1F5F73", RULE = "C9D1D6",
      HEAD_FILL = "E6EEF1", EMPH_FILL = "F3F6EC", CALLOUT_FILL = "EEF4F6";
const FONT = "Calibri";
const CONTENT_W = 9360;  // DXA; A4 width 11906 minus 1273 margins each side

const thin = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function runs(text, opts = {}) {
  return [new TextRun({ text, font: FONT, color: INK, size: 22, ...opts })];
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}

function cell(text, w, { header = false, fill = null, bold = false } = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: { top: thin, bottom: thin, left: none, right: none },
    shading: fill ? { type: ShadingType.CLEAR, color: "auto", fill } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      spacing: { before: 0, after: 0, line: 260 },
      children: [new TextRun({ text, font: FONT, size: header ? 18 : 19, bold: header || bold,
                               color: header ? ACCENT : INK })],
    })],
  });
}

function caption(text) {
  return new Paragraph({
    keepNext: true, spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, font: FONT, size: 20, bold: true, color: INK })],
  });
}

function sourceLine(text) {
  return new Paragraph({
    spacing: { before: 60, after: 200 },
    children: [new TextRun({ text: "Source: " + text, font: FONT, size: 16, italics: true, color: MUTED })],
  });
}

// Bullet list definition; each numbered list adds its own so it restarts at 1.
const numConfigs = [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
  alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] }];

const children = [];
for (const b of content.blocks) {
  switch (b.t) {
    case "title":
      children.push(new Paragraph({ spacing: { before: 2600, after: 0 }, children: [] }));
      children.push(new Paragraph({
        spacing: { after: 300 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 12 } },
        children: [new TextRun({ text: b.title, font: FONT, size: 44, bold: true, color: INK })],
      }));
      children.push(new Paragraph({ spacing: { after: 200 },
        children: [new TextRun({ text: b.subtitle, font: FONT, size: 30, color: ACCENT })] }));
      children.push(new Paragraph({ spacing: { after: 0 },
        children: [new TextRun({ text: b.meta, font: FONT, size: 22, color: MUTED })] }));
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    case "h1":
      children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, children: [new TextRun({ text: b.text })] }));
      break;
    case "h2":
      children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [new TextRun({ text: b.text })] }));
      break;
    case "h3":
      children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, children: [new TextRun({ text: b.text })] }));
      break;
    case "p":
      children.push(new Paragraph({ spacing: { after: 140, line: 300 }, alignment: AlignmentType.JUSTIFIED,
                                    children: runs(b.text) }));
      break;
    case "bullets":
    case "numbered": {
      let ref = "bul";
      if (b.t === "numbered") {
        ref = "num" + numConfigs.length;
        numConfigs.push({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] });
      }
      for (const it of b.items) {
        children.push(new Paragraph({ numbering: { reference: ref, level: 0 },
          spacing: { after: 80, line: 290 }, children: runs(it) }));
      }
      break;
    }
    case "callout":
      children.push(new Table({
        width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
        layout: TableLayoutType.FIXED,
        rows: [new TableRow({ cantSplit: true, children: [new TableCell({
          width: { size: CONTENT_W, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: CALLOUT_FILL },
          borders: { top: none, bottom: none, right: none,
                     left: { style: BorderStyle.SINGLE, size: 24, color: ACCENT } },
          margins: { top: 140, bottom: 140, left: 220, right: 220 },
          children: [
            new Paragraph({ spacing: { after: 80 },
              children: [new TextRun({ text: b.title, font: FONT, size: 22, bold: true, color: ACCENT })] }),
            new Paragraph({ spacing: { after: 0, line: 290 }, children: runs(b.text) }),
          ],
        })] })],
      }));
      children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      break;
    case "table": {
      children.push(caption(b.caption));
      const emph = new Set(b.emph || []);
      const rows = [new TableRow({ tableHeader: true, cantSplit: true,
        children: b.header.map((h, i) => cell(h, b.widths[i], { header: true, fill: HEAD_FILL })) })];
      b.rows.forEach((r, ri) => rows.push(new TableRow({ cantSplit: true,
        children: r.map((c, i) => cell(c, b.widths[i], { fill: emph.has(ri) ? EMPH_FILL : null,
                                                         bold: emph.has(ri) && i === 0 })) })));
      children.push(new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: b.widths,
                                layout: TableLayoutType.FIXED, rows }));
      children.push(sourceLine(b.source));
      break;
    }
    case "figure": {
      const img = pngSize(path.join(HERE, b.file));
      const wpx = Math.round(b.width_in * 96);
      const hpx = Math.round(wpx * img.h / img.w);
      children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 60 },
        children: [new ImageRun({ type: "png", data: img.data, transformation: { width: wpx, height: hpx },
                                  altText: { title: b.caption, description: b.caption, name: b.file } })] }));
      children.push(new Paragraph({ spacing: { before: 40, after: 40 },
        children: [new TextRun({ text: b.caption, font: FONT, size: 19, bold: true, color: INK })] }));
      children.push(sourceLine(b.source));
      break;
    }
    case "pagebreak":
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    default:
      throw new Error("unknown block " + b.t);
  }
}

const doc = new Document({
  creator: "Thesis experiments", title: "Experimental work: design, results and robustness",
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 34, bold: true, color: INK },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 27, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true, color: INK },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: numConfigs },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 },
                          margin: { top: 1300, bottom: 1300, left: 1273, right: 1273 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Experimental work · IoT smart-home threat detection", font: FONT, size: 16, color: MUTED })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: MUTED })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
