import test from "node:test";
import assert from "node:assert/strict";

import { escapeHtml, parseStructuredSections, renderDailyNote, renderGenericNote } from "../src/noteRendering.js";

test("escapeHtml escapes unsafe characters", () => {
  assert.equal(escapeHtml('<tag attr="x">'), "&lt;tag attr=&quot;x&quot;&gt;");
});

test("parseStructuredSections splits headings and key values", () => {
  const input = `
## 全天累積

- **全天步數**：17326
- **全天距離**：13.62 公里

## 今日活動合計

- 這一區只統計今天抓到的活動紀錄
- **活動次數**：2
`;

  const sections = parseStructuredSections(input);
  assert.equal(sections.length, 2);
  assert.equal(sections[0].title, "全天累積");
  assert.deepEqual(sections[0].items[0], { label: "全天步數", value: "17326" });
  assert.equal(sections[1].paragraphs[0], "這一區只統計今天抓到的活動紀錄");
});

test("renderGenericNote keeps generic bullet layout", () => {
  const rendered = renderGenericNote("## 區塊\n\n- **欄位**：內容");
  assert.match(rendered, /generic-note-item/);
  assert.match(rendered, /<h3>區塊<\/h3>/);
});

test("renderDailyNote uses summary ribbon and detail table", () => {
  const rendered = renderDailyNote(`
## 全天累積

- **全天步數**：17326
- **全天距離**：13.62 公里

## 今日活動合計

- **活動次數**：2
`);

  assert.match(rendered, /summary-ribbon/);
  assert.match(rendered, /detail-table/);
  assert.match(rendered, /全天步數/);
  assert.match(rendered, /活動次數/);
});

test("renderDailyNote falls back to generic note when no sections exist", () => {
  const rendered = renderDailyNote("純文字內容");
  assert.doesNotMatch(rendered, /daily-report/);
  assert.match(rendered, /<p>純文字內容<\/p>/);
});
