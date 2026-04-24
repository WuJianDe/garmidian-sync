import "./style.css";

const state = {
  status: null,
  records: {
    daily: [],
    activity: [],
  },
  activeKind: "daily",
  selectedId: "",
  selectedNote: null,
  query: "",
};

const app = document.querySelector("#app");

app.innerHTML = `
  <div class="shell">
    <section class="hero panel">
      <div class="hero-copy">
        <p class="eyebrow">Garmin x Obsidian</p>
        <h1>健康紀錄中心</h1>
        <p class="lead">同步 Garmin 資料、查看每日健康摘要、閱讀活動紀錄，都在同一個本機頁面完成。</p>
      </div>
      <div class="hero-metrics">
        <div class="metric-card">
          <span class="metric-label">每日筆記</span>
          <strong class="metric-value" id="dailyCount">-</strong>
        </div>
        <div class="metric-card">
          <span class="metric-label">活動筆記</span>
          <strong class="metric-value" id="activityCount">-</strong>
        </div>
        <div class="metric-card metric-wide">
          <span class="metric-label">最後同步</span>
          <strong class="metric-small" id="lastSyncAt">-</strong>
        </div>
        <div class="metric-card metric-wide">
          <span class="metric-label">目前狀態</span>
          <strong class="metric-small" id="heroStatus">待命中</strong>
        </div>
      </div>
    </section>

    <section class="panel action-panel">
      <div>
        <h2>同步操作</h2>
        <p class="panel-copy">平常直接抓最新資料就可以；要補歷史資料時，再執行完整同步。</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" data-action="run-latest">抓最新資料並匯出</button>
        <button class="btn btn-warm" data-action="run-full">完整同步並匯出</button>
      </div>
      <div class="status-row">
        <span class="status-pill" id="taskStatus">等待操作</span>
        <span class="status-pill soft" id="taskName">目前任務：無</span>
        <span class="status-pill soft" id="lastCode">最後狀態碼：-</span>
        <span class="status-pill soft" id="lastResult">最近結果：-</span>
      </div>
    </section>

    <section class="content-grid">
      <aside class="panel sidebar">
        <div class="sidebar-head">
          <div>
            <h2>已匯出紀錄</h2>
            <p class="panel-copy">切換每日與活動，左側挑一篇，右側直接閱讀。</p>
          </div>
          <div class="tabs">
            <button class="tab active" data-kind="daily">每日</button>
            <button class="tab" data-kind="activity">活動</button>
          </div>
        </div>
        <input id="searchInput" class="search-input" type="search" placeholder="搜尋日期、活動名稱、關鍵字" />
        <div id="recordList" class="record-list"></div>
      </aside>

      <main class="panel viewer">
        <div id="viewerEmpty" class="viewer-empty">請先從左側選擇一篇紀錄。</div>
        <div id="viewerContent" hidden>
          <div class="viewer-head">
            <div>
              <h2 id="noteTitle" class="viewer-title">-</h2>
              <div id="noteMeta" class="viewer-meta">-</div>
            </div>
          </div>
          <article id="noteBody" class="viewer-body"></article>
        </div>
      </main>
    </section>

    <section class="panel log-panel">
      <div class="log-head">
        <h2>執行紀錄</h2>
        <p class="panel-copy">這裡會顯示最新同步輸出與錯誤訊息。</p>
      </div>
      <pre id="logOutput" class="log-output">尚未執行任何動作。</pre>
    </section>
  </div>
`;

const elements = {
  dailyCount: document.querySelector("#dailyCount"),
  activityCount: document.querySelector("#activityCount"),
  lastSyncAt: document.querySelector("#lastSyncAt"),
  heroStatus: document.querySelector("#heroStatus"),
  taskStatus: document.querySelector("#taskStatus"),
  taskName: document.querySelector("#taskName"),
  lastCode: document.querySelector("#lastCode"),
  lastResult: document.querySelector("#lastResult"),
  logOutput: document.querySelector("#logOutput"),
  recordList: document.querySelector("#recordList"),
  searchInput: document.querySelector("#searchInput"),
  viewerEmpty: document.querySelector("#viewerEmpty"),
  viewerContent: document.querySelector("#viewerContent"),
  noteTitle: document.querySelector("#noteTitle"),
  noteMeta: document.querySelector("#noteMeta"),
  noteBody: document.querySelector("#noteBody"),
  actionButtons: Array.from(document.querySelectorAll("[data-action]")),
  tabButtons: Array.from(document.querySelectorAll("[data-kind]")),
};

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderMarkdownLike(text) {
  const escaped = escapeHtml(text);
  return escaped
    .replace(/^### (.*)$/gm, "<h4>$1</h4>")
    .replace(/^## (.*)$/gm, "<h3>$1</h3>")
    .replace(/^# (.*)$/gm, "<h2>$1</h2>")
    .replace(/^\- \*\*(.*?)\*\*：(.*)$/gm, "<div class=\"note-item\"><strong>$1</strong><span>$2</span></div>")
    .replace(/^\- (.*)$/gm, "<div class=\"note-bullet\">$1</div>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/^/, "<p>")
    .replace(/$/, "</p>");
}

function filteredRecords() {
  const records = state.records[state.activeKind] || [];
  const query = state.query.trim().toLowerCase();
  if (!query) return records;
  return records.filter((record) =>
    [record.title, record.subtitle, record.preview].filter(Boolean).join(" ").toLowerCase().includes(query),
  );
}

function renderRecordList() {
  const records = filteredRecords();
  if (!records.length) {
    elements.recordList.innerHTML = '<div class="record-empty">目前找不到符合條件的紀錄。</div>';
    return;
  }
  elements.recordList.innerHTML = records
    .map((record) => {
      const activeClass = record.id === state.selectedId ? " active" : "";
      return `
        <button class="record-card${activeClass}" data-note-id="${record.id}">
          <div class="record-title">${escapeHtml(record.title)}</div>
          <div class="record-subtitle">${escapeHtml(record.subtitle || "")}</div>
          <div class="record-preview">${escapeHtml(record.preview || "")}</div>
        </button>
      `;
    })
    .join("");

  elements.recordList.querySelectorAll("[data-note-id]").forEach((button) => {
    button.addEventListener("click", () => {
      void loadNote(state.activeKind, button.dataset.noteId);
    });
  });
}

function renderStatus() {
  const status = state.status;
  if (!status) return;
  elements.dailyCount.textContent = String(status.daily_count ?? "-");
  elements.activityCount.textContent = String(status.activity_count ?? "-");
  elements.lastSyncAt.textContent = status.last_sync_at || "-";
  elements.heroStatus.textContent = status.running ? "執行中" : (status.last_result || "待命中");
  elements.taskStatus.textContent = status.running ? "執行中" : "待命中";
  elements.taskStatus.className = `status-pill${status.running ? " warning" : status.last_exit_code ? " danger" : ""}`;
  elements.taskName.textContent = `目前任務：${status.task_name || "無"}`;
  elements.lastCode.textContent = `最後狀態碼：${status.last_exit_code ?? "-"}`;
  elements.lastResult.textContent = `最近結果：${status.last_result || "-"}`;
  elements.logOutput.textContent = status.log || "尚未執行任何動作。";
  elements.actionButtons.forEach((button) => {
    button.disabled = Boolean(status.running);
  });
}

function renderViewer() {
  if (!state.selectedNote) {
    elements.viewerEmpty.hidden = false;
    elements.viewerContent.hidden = true;
    return;
  }
  elements.viewerEmpty.hidden = true;
  elements.viewerContent.hidden = false;
  elements.noteTitle.textContent = state.selectedNote.title || "未命名紀錄";
  elements.noteMeta.textContent = [state.selectedNote.subtitle, state.selectedNote.path].filter(Boolean).join(" | ");
  elements.noteBody.innerHTML = renderMarkdownLike(state.selectedNote.content || "");
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "操作失敗");
  }
  return payload;
}

async function refreshStatus() {
  state.status = await fetchJson("/api/status");
  renderStatus();
}

async function refreshRecords() {
  const [daily, activity] = await Promise.all([
    fetchJson("/api/records?kind=daily"),
    fetchJson("/api/records?kind=activity"),
  ]);
  state.records.daily = daily.records || [];
  state.records.activity = activity.records || [];

  const currentIds = new Set((state.records[state.activeKind] || []).map((record) => record.id));
  if (!currentIds.has(state.selectedId)) {
    state.selectedId = (state.records[state.activeKind] || [])[0]?.id || "";
  }

  renderRecordList();

  if (state.selectedId) {
    await loadNote(state.activeKind, state.selectedId, true);
  } else {
    state.selectedNote = null;
    renderViewer();
  }
}

async function loadNote(kind, noteId, silent = false) {
  if (!noteId) return;
  state.selectedId = noteId;
  state.selectedNote = await fetchJson(`/api/note?kind=${encodeURIComponent(kind)}&id=${encodeURIComponent(noteId)}`);
  if (!silent) {
    renderRecordList();
  }
  renderViewer();
}

async function runAction(action) {
  try {
    await fetchJson(`/api/actions/${action}`, { method: "POST" });
    await refreshStatus();
    await refreshRecords();
  } catch (error) {
    alert(error.message);
  }
}

elements.actionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    void runAction(button.dataset.action);
  });
});

elements.tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.activeKind = button.dataset.kind;
    elements.tabButtons.forEach((tab) => tab.classList.toggle("active", tab === button));
    state.selectedId = (state.records[state.activeKind] || [])[0]?.id || "";
    renderRecordList();
    if (state.selectedId) {
      void loadNote(state.activeKind, state.selectedId);
    } else {
      state.selectedNote = null;
      renderViewer();
    }
  });
});

elements.searchInput.addEventListener("input", () => {
  state.query = elements.searchInput.value;
  renderRecordList();
});

async function bootstrap() {
  await Promise.all([refreshStatus(), refreshRecords()]);
  window.setInterval(() => {
    void refreshStatus();
  }, 2000);
}

void bootstrap();
