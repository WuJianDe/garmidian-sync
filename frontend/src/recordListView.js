import { sortRecordsNewestFirst } from "./dateUtils.js";

export function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function filteredRecords(records, query) {
  const sorted = sortRecordsNewestFirst(records || []);
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return sorted;
  }
  return sorted.filter((record) =>
    [record.title, record.subtitle].filter(Boolean).join(" ").toLowerCase().includes(normalizedQuery),
  );
}

export function renderRecordList(records, selectedId, container, onSelect) {
  if (!records.length) {
    container.innerHTML = '<div class="record-empty">目前找不到符合條件的紀錄。</div>';
    return;
  }
  container.innerHTML = records
    .map((record) => {
      const activeClass = record.id === selectedId ? " active" : "";
      return `
        <button class="record-card${activeClass}" data-note-id="${record.id}">
          <div class="record-title">${escapeHtml(record.title)}</div>
          <div class="record-subtitle">${escapeHtml(record.subtitle || "")}</div>
        </button>
      `;
    })
    .join("");

  container.querySelectorAll("[data-note-id]").forEach((button) => {
    button.addEventListener("click", () => {
      onSelect(button.dataset.noteId);
    });
  });
}
