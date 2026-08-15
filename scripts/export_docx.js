#!/usr/bin/env node
/*
 * Export the complete Markdown manuscript to professional DOCX editions.
 * This implementation is original to this repository and does not include
 * code or prompt text from third-party proprietary DOCX skills.
 */

const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  Bookmark,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  InternalHyperlink,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  SectionType,
  TextRun,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const MANUSCRIPT = path.join(ROOT, "03-manuscript");
const EXPORT_DIR = path.join(ROOT, "exports");

const BOOK_TITLE = "Осколки Бездны";
const SERIES_TITLE = "Хроники Этериума";
const SUBTITLE = "Книга первая · роман";

const FORMATS = {
  editorial: {
    file: "Хроники_Этериума_Осколки_Бездны_редакторская.docx",
    label: "Редакторская версия",
    page: { width: 11906, height: 16838 }, // A4
    margin: { top: 1134, right: 1134, bottom: 1134, left: 1701, header: 567, footer: 567 },
    font: "Times New Roman",
    fontSize: 24, // half-points: 12 pt
    line: 360, // 1.5 lines
    firstLine: 709, // 1.25 cm
    bodyColor: "1F1F1F",
    headingColor: "2B2522",
    contentsColor: "5A4A42",
    chapterSize: 32,
    titleSize: 48,
    seriesSize: 26,
    compactContents: false,
    headerText: "Осколки Бездны · редакторская версия",
  },
  reader: {
    file: "Хроники_Этериума_Осколки_Бездны_читательская.docx",
    label: "Читательская версия",
    page: { width: 8391, height: 11906 }, // A5
    margin: { top: 907, right: 850, bottom: 1020, left: 850, gutter: 284, header: 454, footer: 510 },
    font: "Georgia",
    fontSize: 21, // 10.5 pt
    line: 276,
    firstLine: 567, // 1 cm
    bodyColor: "24201E",
    headingColor: "3A2F2A",
    contentsColor: "67544B",
    chapterSize: 30,
    titleSize: 46,
    seriesSize: 24,
    compactContents: true,
    headerText: "Хроники Этериума · Осколки Бездны",
  },
};

function chapterFiles() {
  const found = [];
  for (const arc of fs.readdirSync(MANUSCRIPT).filter((x) => /^arc-\d+$/.test(x)).sort()) {
    const dir = path.join(MANUSCRIPT, arc);
    for (const name of fs.readdirSync(dir).filter((x) => /^ch-\d+\.md$/.test(x))) {
      const number = Number(name.match(/\d+/)[0]);
      found.push({ number, file: path.join(dir, name) });
    }
  }
  found.sort((a, b) => a.number - b.number);
  const expected = Array.from({ length: 36 }, (_, i) => i + 1);
  const actual = found.map((x) => x.number);
  if (JSON.stringify(expected) !== JSON.stringify(actual)) {
    throw new Error(`Ожидались главы 1–36, получено: ${actual.join(", ")}`);
  }
  return found;
}

function validateSource(text, file) {
  if (text.includes("\uFFFD")) throw new Error(`Повреждённый символ U+FFFD: ${file}`);
  const headings = text.match(/^# Глава \d+\s*$/gm) || [];
  if (headings.length !== 1) throw new Error(`Ожидался один заголовок главы: ${file}`);
}

function inlineRuns(text, cfg) {
  const runs = [];
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      runs.push(new TextRun({ text: text.slice(cursor, match.index), font: cfg.font, size: cfg.fontSize, color: cfg.bodyColor }));
    }
    const token = match[0];
    const bold = token.startsWith("**");
    const content = bold ? token.slice(2, -2) : token.slice(1, -1);
    runs.push(new TextRun({
      text: content,
      bold,
      italics: !bold,
      font: cfg.font,
      size: cfg.fontSize,
      color: cfg.bodyColor,
    }));
    cursor = match.index + token.length;
  }
  if (cursor < text.length) {
    runs.push(new TextRun({ text: text.slice(cursor), font: cfg.font, size: cfg.fontSize, color: cfg.bodyColor }));
  }
  return runs.length ? runs : [new TextRun({ text, font: cfg.font, size: cfg.fontSize, color: cfg.bodyColor })];
}

function bodyParagraph(text, cfg, firstInChapter = false) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 0, after: 0, line: cfg.line },
    indent: { firstLine: firstInChapter && cfg === FORMATS.reader ? 0 : cfg.firstLine },
    widowControl: true,
    children: inlineRuns(text, cfg),
  });
}

function sceneBreak(cfg) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: cfg.compactContents ? 180 : 240, after: cfg.compactContents ? 180 : 240, line: cfg.line },
    keepLines: true,
    children: [new TextRun({ text: "* * *", font: cfg.font, size: cfg.fontSize, color: cfg.contentsColor })],
  });
}

function chapterHeading(number, cfg, first) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    alignment: AlignmentType.CENTER,
    pageBreakBefore: !first,
    keepNext: true,
    spacing: { before: cfg.compactContents ? 420 : 520, after: cfg.compactContents ? 460 : 520 },
    children: [
      new Bookmark({
        id: `chapter_${number}`,
        children: [new TextRun({
          text: `Глава ${number}`,
          font: cfg.font,
          size: cfg.chapterSize,
          bold: true,
          color: cfg.headingColor,
        })],
      }),
    ],
  });
}

function parseChapter(item, cfg, firstChapter) {
  const source = fs.readFileSync(item.file, "utf8").replace(/\r\n/g, "\n").trim();
  validateSource(source, item.file);
  const lines = source.split("\n");
  const children = [chapterHeading(item.number, cfg, firstChapter)];
  let firstBody = true;
  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;
    if (line === "---") {
      children.push(sceneBreak(cfg));
      firstBody = true;
      continue;
    }
    if (/^#{1,6}\s/.test(line)) {
      throw new Error(`Неожиданный Markdown-заголовок в прозе: ${item.file}:${i + 1}`);
    }
    children.push(bodyParagraph(line, cfg, firstBody));
    firstBody = false;
  }
  return children;
}

function titleAndContents(cfg, chapters) {
  const title = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: cfg.compactContents ? 1900 : 2400, after: 260 },
      children: [new TextRun({ text: SERIES_TITLE.toUpperCase(), font: cfg.font, size: cfg.seriesSize, color: cfg.contentsColor, characterSpacing: 60 })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 180, after: 280 },
      children: [new TextRun({ text: BOOK_TITLE, font: cfg.font, size: cfg.titleSize, bold: true, color: cfg.headingColor })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 100, after: 0 },
      children: [new TextRun({ text: SUBTITLE, font: cfg.font, size: cfg.seriesSize, italics: true, color: cfg.contentsColor })],
    }),
  ];
  if (cfg.label) {
    title.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 900, after: 0 },
      children: [new TextRun({ text: cfg.label, font: cfg.font, size: 18, color: "77706C", smallCaps: true })],
    }));
  }
  title.push(new Paragraph({ children: [new PageBreak()] }));
  title.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 240, after: 360 },
    children: [new TextRun({ text: "Содержание", font: cfg.font, size: 30, bold: true, color: cfg.headingColor })],
  }));
  for (const chapter of chapters) {
    title.push(new Paragraph({
      alignment: AlignmentType.LEFT,
      spacing: { before: 0, after: cfg.compactContents ? 40 : 70, line: 240 },
      indent: { left: cfg.compactContents ? 850 : 1200 },
      children: [new InternalHyperlink({
        anchor: `chapter_${chapter.number}`,
        children: [new TextRun({
          text: `Глава ${chapter.number}`,
          font: cfg.font,
          size: cfg.compactContents ? 19 : 21,
          color: cfg.contentsColor,
        })],
      })],
    }));
  }
  return title;
}

function bodyHeader(cfg) {
  return new Header({
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      border: { bottom: { color: "C9C1BC", style: BorderStyle.SINGLE, size: 4, space: 4 } },
      spacing: { after: 80 },
      children: [new TextRun({ text: cfg.headerText, font: cfg.font, size: 16, color: "77706C", smallCaps: true })],
    })],
  });
}

function bodyFooter(cfg) {
  const children = cfg === FORMATS.editorial
    ? [new TextRun({ text: "Страница ", font: cfg.font, size: 16, color: "77706C" }), PageNumber.CURRENT,
       new TextRun({ text: " из ", font: cfg.font, size: 16, color: "77706C" }), PageNumber.TOTAL_PAGES_IN_SECTION]
    : [PageNumber.CURRENT];
  return new Footer({
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children,
    })],
  });
}

async function build(kind) {
  const cfg = FORMATS[kind];
  if (!cfg) throw new Error(`Неизвестный формат: ${kind}`);
  const chapters = chapterFiles();
  const front = titleAndContents(cfg, chapters);
  const body = [];
  chapters.forEach((chapter, index) => body.push(...parseChapter(chapter, cfg, index === 0)));

  const doc = new Document({
    creator: "",
    title: `${SERIES_TITLE} — ${BOOK_TITLE}`,
    subject: "Роман",
    description: cfg.label,
    keywords: "фэнтези, роман, Хроники Этериума, Осколки Бездны",
    features: { updateFields: true },
    styles: {
      default: {
        document: {
          run: { font: cfg.font, size: cfg.fontSize, color: cfg.bodyColor },
          paragraph: { spacing: { after: 0, line: cfg.line } },
        },
        heading1: {
          run: { font: cfg.font, size: cfg.chapterSize, bold: true, color: cfg.headingColor },
          paragraph: { alignment: AlignmentType.CENTER, keepNext: true },
        },
      },
    },
    sections: [
      {
        properties: { page: { size: cfg.page, margin: cfg.margin } },
        children: front,
      },
      {
        properties: {
          type: SectionType.NEXT_PAGE,
          page: { size: cfg.page, margin: cfg.margin, pageNumbers: { start: 1 } },
        },
        headers: { default: bodyHeader(cfg) },
        footers: { default: bodyFooter(cfg) },
        children: body,
      },
    ],
  });

  fs.mkdirSync(EXPORT_DIR, { recursive: true });
  const target = path.join(EXPORT_DIR, cfg.file);
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(target, buffer);
  return { target, bytes: buffer.length, paragraphs: body.length };
}

async function main() {
  const requested = process.argv.slice(2).filter((x) => !x.startsWith("-"));
  const kinds = requested.length ? requested : ["editorial", "reader"];
  for (const kind of kinds) {
    const result = await build(kind);
    console.log(`${kind}: ${result.target} (${result.bytes} bytes, ${result.paragraphs} body blocks)`);
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
