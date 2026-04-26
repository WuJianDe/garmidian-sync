export function formatTaipeiDateTime(value) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const lookup = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${lookup.year}-${lookup.month}-${lookup.day} ${lookup.hour}:${lookup.minute}:${lookup.second}`;
}

export function recordDateKey(record) {
  if (record?.sort_key) {
    return String(record.sort_key);
  }
  const source = [record?.id, record?.title, record?.subtitle].filter(Boolean).join(" ");
  const match = source.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

export function sortRecordsNewestFirst(records) {
  return [...records].sort((left, right) => {
    const leftDate = recordDateKey(left);
    const rightDate = recordDateKey(right);
    if (leftDate !== rightDate) {
      return rightDate.localeCompare(leftDate);
    }
    return String(right.title || right.id || "").localeCompare(String(left.title || left.id || ""), "zh-Hant");
  });
}
