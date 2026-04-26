import { formatTaipeiDateTime } from "./dateUtils.js";

export function errorCategoryLabel(category) {
  const labels = {
    "": "-",
    cancelled: "已取消",
    rate_limit: "Garmin 限流",
    auth: "登入失敗",
    network: "網路連線",
    config: "設定問題",
    unknown: "未分類錯誤",
  };
  return labels[String(category || "")] || String(category || "-");
}

export function applyStatusToElements(status, elements) {
  if (!status) return;
  const progressCurrent = Number(status.progress_current ?? 0);
  const progressTotal = Number(status.progress_total ?? 0);
  const progressPercent = progressTotal > 0 ? Math.min(100, Math.round((progressCurrent / progressTotal) * 100)) : 0;

  elements.dailyCount.textContent = String(status.daily_count ?? "-");
  elements.activityCount.textContent = String(status.activity_count ?? "-");
  elements.lastSyncAt.textContent = formatTaipeiDateTime(status.last_sync_at);
  elements.taskStatus.textContent = status.running ? "執行中" : "待命中";
  elements.taskStatus.className = `status-pill${status.running ? " warning" : status.last_exit_code ? " danger" : ""}`;
  elements.taskName.textContent = `目前任務：${status.task_name || "無"}`;
  elements.lastResult.textContent = `最近結果：${status.last_result || "-"}`;
  elements.errorCategory.textContent = `錯誤分類：${errorCategoryLabel(status.error_category)}`;
  elements.progressLabel.textContent = `目前步驟：${status.current_step || "待命"}`;
  elements.progressMeta.textContent = `${progressCurrent} / ${progressTotal}`;
  elements.progressFill.style.width = `${progressPercent}%`;
  elements.currentDay.textContent = `目前日期：${status.current_day || "-"}`;
  elements.logOutput.textContent = status.log || "尚未執行任何動作。";

  elements.actionButtons.forEach((button) => {
    if (button.dataset.action === "stop") {
      button.disabled = !status.running;
      return;
    }
    button.disabled = Boolean(status.running);
  });
  elements.rangeStartDate.disabled = Boolean(status.running);
  elements.rangeEndDate.disabled = Boolean(status.running);
}
