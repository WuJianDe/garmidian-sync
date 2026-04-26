export async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "操作失敗");
  }
  return payload;
}

export function buildActionPayload(action, startDate, endDate) {
  if (action === "stop") {
    return undefined;
  }
  if (action !== "run-range") {
    return undefined;
  }
  if (!startDate || !endDate) {
    throw new Error("請先輸入開始日期與結束日期。");
  }
  return { start_date: startDate, end_date: endDate };
}
