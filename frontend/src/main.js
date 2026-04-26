import "./style.css";
import { buildActionPayload, fetchJson } from "./apiClient.js";
import { filteredRecords as filterRecords, renderRecordList as renderRecordListView } from "./recordListView.js";
import { applyStatusToElements } from "./statusView.js";
import { renderViewer as renderViewerView } from "./viewerView.js";

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
        <p class="lead">同步 Garmin 資料、查看每日健康摘要與活動紀錄，都在同一個本機頁面完成。</p>
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
        <div class="metric-card">
          <span class="metric-label">最後同步</span>
          <strong class="metric-small" id="lastSyncAt">-</strong>
        </div>
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

    <section class="panel action-panel">
      <div>
        <h2>同步操作</h2>
        <p class="panel-copy">平常直接抓最新資料；若要補指定區間，再輸入開始日與結束日執行。</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" data-action="run-latest">抓最新資料並匯出</button>
        <button class="btn btn-muted" data-action="stop">停止同步</button>
      </div>
      <div class="range-controls">
        <label class="field">
          <span class="field-label">開始日期</span>
          <input id="rangeStartDate" class="field-input" type="date" />
        </label>
        <label class="field">
          <span class="field-label">結束日期</span>
          <input id="rangeEndDate" class="field-input" type="date" />
        </label>
        <button class="btn btn-warm" data-action="run-range">依區間同步並匯出</button>
      </div>
      <div class="status-row">
        <span class="status-pill" id="taskStatus">等待操作</span>
        <span class="status-pill soft" id="taskName">目前任務：無</span>
        <span class="status-pill soft" id="lastResult">最近結果：-</span>
        <span class="status-pill soft" id="errorCategory">錯誤分類：-</span>
      </div>
      <div class="progress-block">
        <div class="progress-head">
          <strong id="progressLabel">目前步驟：待命</strong>
          <span id="progressMeta">0 / 0</span>
        </div>
        <div class="progress-bar">
          <div id="progressFill" class="progress-fill"></div>
        </div>
        <div id="currentDay" class="current-day">目前日期：-</div>
      </div>
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
  taskStatus: document.querySelector("#taskStatus"),
  taskName: document.querySelector("#taskName"),
  lastResult: document.querySelector("#lastResult"),
  errorCategory: document.querySelector("#errorCategory"),
  progressLabel: document.querySelector("#progressLabel"),
  progressMeta: document.querySelector("#progressMeta"),
  progressFill: document.querySelector("#progressFill"),
  currentDay: document.querySelector("#currentDay"),
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
  rangeStartDate: document.querySelector("#rangeStartDate"),
  rangeEndDate: document.querySelector("#rangeEndDate"),
};

function renderStatus() {
  applyStatusToElements(state.status, elements);
}

function renderViewer() {
  renderViewerView(state.selectedNote, state.activeKind, elements);
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
    const payload = buildActionPayload(action, elements.rangeStartDate.value, elements.rangeEndDate.value);
    await fetchJson(`/api/actions/${action}`, {
      method: "POST",
      headers: payload ? { "Content-Type": "application/json" } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    });
    await refreshStatus();
    await refreshRecords();
  } catch (error) {
    alert(error.message);
  }
}

function filteredRecordsFromState() {
  return filterRecords(state.records[state.activeKind] || [], state.query);
}

function renderRecordList() {
  renderRecordListView(filteredRecordsFromState(), state.selectedId, elements.recordList, (noteId) => {
    void loadNote(state.activeKind, noteId);
  });
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
