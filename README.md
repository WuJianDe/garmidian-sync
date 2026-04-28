# Garmin Obsidian Sync

把 Garmin Connect 的每日健康資料與活動紀錄同步到本機，整理成 Obsidian Markdown 筆記，並提供本機 Web UI 檢視同步狀態、每日摘要與活動內容。

## 功能

- 從 Garmin Connect 抓取每日健康快照與活動資料。
- 將原始 JSON 快照保存在本機，方便重建或除錯。
- 匯出 Obsidian 筆記，包含每日紀錄、活動紀錄、索引與 AI 分析資料。
- 產生 `Health/Garmin/AI` 下的摘要檔，方便 AI 工具讀取。
- 提供本機 Web UI，可直接執行同步、匯出、取消任務與閱讀筆記。
- 支援 `.env` 載入 Garmin 帳密，避免把敏感資訊寫進設定檔。
- 內建 Garmin 登入限流、網路錯誤與設定問題的基礎診斷。

## 資料流

```text
Garmin Connect
  -> data/HealthData/raw/*.json
  -> Python exporter
  -> Obsidian Markdown / AI summaries
  -> local Web UI
```

## 目錄結構

- `src/garmin_obsidian_sync/`
  Python 後端、Garmin 同步、Obsidian 匯出器、CLI 與本機 API。
- `frontend/`
  Vite 前端，負責本機 Web UI。
- `api/`
  API 開發模式入口，會啟動 Python API 並監看重啟。
- `tests/`
  Python 單元測試。
- `frontend/tests/`
  前端純邏輯測試。
- `data/`
  預設健康資料快照位置。
- `.runtime/`
  Garmin token 與執行期暫存資料。

## 安裝

需求：

- Python 3.10+
- Node.js / npm
- 可登入的 Garmin Connect 帳號
- 一個本機 Obsidian vault

建立 Python 環境：

```powershell
python -m venv .venv
.venv\Scripts\activate
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\pip.exe install -e .
```

安裝前端與 API 開發依賴：

```powershell
cd frontend
npm install
cd ..\api
npm install
cd ..
```

## 設定

建立本機設定與環境變數檔：

```powershell
Copy-Item config.example.json config.local.json
Copy-Item .env.example .env
```

至少需要修改 `config.local.json`：

- `garmin.initial_start_date`
- `obsidian.vault_path`

建議把 Garmin 帳密放在 `.env`：

```dotenv
GARMIN_USERNAME=your-email@example.com
GARMIN_PASSWORD=your-garmin-password
```

`config.local.json` 不需要也不建議放 Garmin 帳號密碼；程式會依照 `username_env` 與 `password_env` 指定的環境變數名稱讀取 `.env` 或系統環境變數。

常用設定：

- `garmin.latest_lookback_days`
  一般同步往回抓取的每日資料天數。
- `garmin.download_latest_activities`
  一般同步抓取的近期活動數量。
- `garmin.download_all_activities`
  完整同步抓取的活動數量上限。
- `retry.*`
  Garmin 登入或連線失敗時的重試策略。
- `obsidian.root_folder`
  匯出到 vault 內的根目錄，預設為 `Health/Garmin`。
- `export.daily_limit_per_section`
  每日筆記各區塊顯示的項目數量上限。

## CLI 使用

初始化資料夾與本機儲存：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json init
```

檢查設定：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json doctor
```

同步近期資料並匯出 Obsidian 筆記：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run
```

指定日期範圍同步並匯出：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run --start-date 2026-04-01 --end-date 2026-04-27
```

完整同步：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run --full
```

只抓 Garmin JSON，不匯出：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json sync
```

只用現有 JSON 重建 Obsidian：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json export
```

## Web UI

第一次使用 Web UI 前先建置前端：

```powershell
npm run build
```

啟動本機 Web UI：

```powershell
start-web-ui.bat
```

也可以直接啟動 Python server：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.webapp --config config.local.json
```

預設網址：

- Web UI：`http://127.0.0.1:8765/`
- 狀態 API：`http://127.0.0.1:8765/api/status`
- 紀錄 API：`http://127.0.0.1:8765/api/records`

開發模式：

雙擊資料夾內的 `start-dev.bat`，會自動開啟 API 與前端開發伺服器，並打開前端網址。

也可以手動啟動：

```powershell
npm run dev:frontend
npm run dev:api
```

開發模式預設網址：

- 前端：`http://127.0.0.1:5173/`
- API：`http://127.0.0.1:8765/`

## 匯出內容

Obsidian 預設會生成：

- `Health/Garmin/Daily/YYYY/MM/YYYY-MM-DD.md`
- `Health/Garmin/Activities/YYYY/YYYY-MM-DD-活動名稱-activity-id.md`
- `Health/Garmin/_Indexes/Daily Index.md`
- `Health/Garmin/_Indexes/Activity Index.md`
- `Health/Garmin/AI/latest-status.md`
- `Health/Garmin/AI/daily-summary.md`
- `Health/Garmin/AI/activity-summary.md`
- `Health/Garmin/AI/daily-summary.jsonl`
- `Health/Garmin/AI/activity-summary.jsonl`

AI 資料策略：

- `latest-status.md` 聚焦最新狀態，適合快速掌握目前趨勢。
- `daily-summary.md`、`activity-summary.md` 與 JSONL 檔保留完整已同步歷史，適合長期分析。
- 如果要讓 AI 工具掃描，建議直接指定 `Health/Garmin/AI`。

## 測試與建置

Python 測試：

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.test_exporter tests.test_webapp -v
```

前端測試：

```powershell
npm test --prefix frontend
```

前端建置：

```powershell
npm run build
```

## 開發筆記

主要 Python 模組：

- `garmin_connect_sync.py`
  與 Garmin Connect 溝通，抓取每日與活動 JSON。
- `exporter.py`
  匯出流程總入口，負責 daily、activity 與 AI 匯出。
- `translations.py`
  Garmin 狀態值、活動型別與代碼翻譯。
- `formatters.py`
  距離、時間、卡路里與日期格式化工具。
- `runtime.py`
  進度回報、取消檢查與錯誤分類等共用執行工具。
- `webapp.py`
  本機 API 與靜態前端入口。
- `cli.py`
  `init`、`sync`、`export`、`doctor`、`run` 指令。

主要前端模組：

- `frontend/src/main.js`
  啟動頁面與整體狀態協調。
- `frontend/src/apiClient.js`
  API 請求與 action payload 建構。
- `frontend/src/dateUtils.js`
  台北時間格式與紀錄排序。
- `frontend/src/statusView.js`
  同步狀態與進度列渲染。
- `frontend/src/recordListView.js`
  左側紀錄列表與搜尋過濾。
- `frontend/src/viewerView.js`
  右側閱讀區渲染。
- `frontend/src/noteRendering.js`
  每日摘要與一般筆記的 HTML 渲染邏輯。

## 注意事項

- Garmin token 會放在 `.runtime/home/garminconnect_tokens`。
- 原始 JSON 快照會放在 `data/HealthData/raw`，或 `config.local.json` 的 `storage.healthdata_dir` 指定位置。
- Web 閱讀模式不顯示 raw JSON，但 Obsidian 筆記仍保留原始資料折疊區塊。
- 同步與匯出支援進度回報與取消。
- Garmin 可能限制頻繁登入；若遇到限流，請稍後再試並避免短時間反覆重啟同步。
