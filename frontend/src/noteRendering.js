export function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function renderGenericNote(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^## (.*)$/gm, "<h3>$1</h3>")
    .replace(/^# (.*)$/gm, "<h2>$1</h2>")
    .replace(/^\- \*\*(.*?)\*\*：(.*)$/gm, "<div class=\"generic-note-item\"><strong>$1</strong><span>$2</span></div>")
    .replace(/^\- (.*)$/gm, "<div class=\"generic-note-bullet\">$1</div>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/^/, "<p>")
    .replace(/$/, "</p>");
}

export function parseStructuredSections(text) {
  const sections = [];
  let current = null;

  for (const rawLine of String(text || "").split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("## ")) {
      if (current) sections.push(current);
      current = { title: line.slice(3).trim(), items: [], paragraphs: [] };
      continue;
    }
    if (!current) {
      current = { title: "", items: [], paragraphs: [] };
    }
    const kvMatch = line.match(/^\- \*\*(.*?)\*\*：(.*)$/);
    if (kvMatch) {
      current.items.push({ label: kvMatch[1].trim(), value: kvMatch[2].trim() });
      continue;
    }
    const bulletMatch = line.match(/^\- (.*)$/);
    if (bulletMatch) {
      current.paragraphs.push(bulletMatch[1].trim());
      continue;
    }
    current.paragraphs.push(line);
  }

  if (current) sections.push(current);
  return sections.filter((section) => section.title || section.items.length || section.paragraphs.length);
}

export function renderDailyNote(text) {
  const sections = parseStructuredSections(text);
  const hasStructuredContent = sections.some((section) => section.title || section.items.length);
  if (!sections.length || !hasStructuredContent) {
    return renderGenericNote(text);
  }

  return `
    <div class="daily-report">
      ${sections
        .map((section, index) => {
          const itemsHtml = section.items.length
            ? index === 0
              ? `<div class="summary-ribbon">${section.items
                  .map(
                    (item) => `
                      <div class="summary-ribbon-item">
                        <span class="summary-ribbon-label">${escapeHtml(item.label)}</span>
                        <strong class="summary-ribbon-value">${escapeHtml(item.value || "-")}</strong>
                      </div>
                    `,
                  )
                  .join("")}</div>`
              : `<div class="detail-table">${section.items
                  .map(
                    (item) => `
                      <div class="detail-table-row">
                        <span class="detail-label">${escapeHtml(item.label)}</span>
                        <strong class="detail-value">${escapeHtml(item.value || "-")}</strong>
                      </div>
                    `,
                  )
                  .join("")}</div>`
            : "";

          const paragraphsHtml = section.paragraphs.length
            ? `<div class="section-notes">${section.paragraphs
                .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
                .join("")}</div>`
            : "";

          return `
            <section class="daily-report-section${index === 0 ? " summary-section" : ""}">
              ${section.title ? `<h3 class="section-title">${escapeHtml(section.title)}</h3>` : ""}
              ${itemsHtml}
              ${paragraphsHtml}
            </section>
          `;
        })
        .join("")}
    </div>
  `;
}
