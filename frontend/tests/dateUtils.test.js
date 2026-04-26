import test from "node:test";
import assert from "node:assert/strict";

import { formatTaipeiDateTime, recordDateKey, sortRecordsNewestFirst } from "../src/dateUtils.js";

test("formatTaipeiDateTime formats ISO text in Taipei timezone", () => {
  assert.equal(formatTaipeiDateTime("2026-04-25T08:45:41Z"), "2026-04-25 16:45:41");
});

test("recordDateKey prefers sort_key when present", () => {
  assert.equal(recordDateKey({ sort_key: "2026-04-25 21:10:00", title: "x" }), "2026-04-25 21:10:00");
});

test("sortRecordsNewestFirst sorts descending by date key", () => {
  const sorted = sortRecordsNewestFirst([
    { id: "a", title: "舊", sort_key: "2026-04-24 07:30:00" },
    { id: "b", title: "新", sort_key: "2026-04-24 21:10:00" },
  ]);
  assert.deepEqual(
    sorted.map((item) => item.id),
    ["b", "a"],
  );
});
