import { renderDailyNote, renderGenericNote } from "./noteRendering.js";

export function renderViewer(note, activeKind, elements) {
  if (!note) {
    elements.viewerEmpty.hidden = false;
    elements.viewerContent.hidden = true;
    return;
  }
  elements.viewerEmpty.hidden = true;
  elements.viewerContent.hidden = false;
  elements.noteTitle.textContent = note.title || "未命名紀錄";
  elements.noteMeta.textContent = note.subtitle || "";
  elements.noteBody.innerHTML = activeKind === "daily" ? renderDailyNote(note.content || "") : renderGenericNote(note.content || "");
}
