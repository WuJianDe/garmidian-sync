import test from "node:test";
import assert from "node:assert/strict";

import { applyStatusToElements, errorCategoryLabel } from "../src/statusView.js";

function buildElements() {
  return {
    dailyCount: { textContent: "" },
    activityCount: { textContent: "" },
    lastSyncAt: { textContent: "" },
    taskStatus: { textContent: "", className: "" },
    taskName: { textContent: "" },
    lastResult: { textContent: "" },
    errorCategory: { textContent: "" },
    progressLabel: { textContent: "" },
    progressMeta: { textContent: "" },
    progressFill: { style: { width: "" } },
    currentDay: { textContent: "" },
    logOutput: { textContent: "" },
    actionButtons: [{ dataset: { action: "run-latest" }, disabled: false }, { dataset: { action: "stop" }, disabled: true }],
    rangeStartDate: { disabled: false },
    rangeEndDate: { disabled: false },
  };
}

test("errorCategoryLabel maps known categories", () => {
  assert.equal(errorCategoryLabel("rate_limit"), "Garmin 限流");
  assert.equal(errorCategoryLabel(""), "-");
});

test("applyStatusToElements updates visible status and button states", () => {
  const elements = buildElements();
  applyStatusToElements(
    {
      daily_count: 10,
      activity_count: 3,
      last_sync_at: "2026-04-25T08:45:41Z",
      running: true,
      last_exit_code: null,
      task_name: "抓最新資料並匯出",
      last_result: "執行中",
      error_category: "",
      current_step: "抓取每日快照",
      progress_current: 2,
      progress_total: 4,
      current_day: "2026-04-25",
      log: "同步中",
    },
    elements,
  );

  assert.equal(elements.dailyCount.textContent, "10");
  assert.equal(elements.activityCount.textContent, "3");
  assert.match(elements.lastSyncAt.textContent, /2026-04-25/);
  assert.equal(elements.taskStatus.textContent, "執行中");
  assert.equal(elements.actionButtons[0].disabled, true);
  assert.equal(elements.actionButtons[1].disabled, false);
  assert.equal(elements.rangeStartDate.disabled, true);
  assert.equal(elements.progressFill.style.width, "50%");
});
