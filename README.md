# Garmin Obsidian Sync

把 Garmin Connect 資料同步到本機，整理成 Obsidian 筆記，並提供本機網頁直接查看每日與活動紀錄。

## 目前架構

資料流：

`Garmin Connect -> JSON 快照 -> 匯出器 -> Obsidian Markdown / AI 摘要 -> 本機網頁閱讀`

主要目錄：

- `src/garmin_obsidian_sync/`
  Python 後端、同步流程、匯出器、API。
- `frontend/`
  Vite 前端。
- `api/`
  API 開發模式入口。
- `tests/`
  Python 測試。
- `frontend/tests/`
  前端純邏輯測試。

## Python 模組分工

- `garmin_connect_sync.py`
  與 Garmin Connect 溝通，抓取每日與活動 JSON。
- `exporter.py`
  匯出流程總入口，負責協調 daily / activity / AI 匯出。
- `translations.py`
  Garmin 狀態值、活動型別、代碼翻譯。
- `formatters.py`
  距離、時間、卡路里、日期等格式化工具。
- `runtime.py`
  進度回報、取消檢查、錯誤分類等共用執行工具。
- `webapp.py`
  本機 API 與靜態前端入口。
- `cli.py`
  `init`、`sync`、`export`、`doctor`、`run` 指令。

## 前端模組分工

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
  每日摘要 / 一般筆記的 HTML 渲染邏輯。

## 安裝

建議使用虛擬環境：

```powershell
python -m venv .venv
.venv\Scripts\activate
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\pip.exe install -e .
```

前端依賴：

```powershell
cd frontend
npm install
cd ..\api
npm install
```

## 設定

先建立本機設定：

```powershell
Copy-Item config.example.json config.local.json
```

至少需要修改：

- `garmin.initial_start_date`
- `obsidian.vault_path`

建議把 Garmin 帳密放在 `.env`：

```powershell
Copy-Item .env.example .env
```

`.env` 內容：

```dotenv
GARMIN_USERNAME=your-email@example.com
GARMIN_PASSWORD=your-garmin-password
```

## 日常使用

初始化：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json init
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json doctor
```

平常同步：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run
```

只重建 Obsidian：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json export
```

## 開發

前端：

```powershell
cd frontend
npm run dev
```

API：

```powershell
cd api
npm run dev
```

預設網址：

- 前端：`http://127.0.0.1:5173/`
- API：`http://127.0.0.1:8765/`

## 測試

Python：

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.test_exporter tests.test_webapp -v
```

前端：

```powershell
npm test --prefix frontend
```

建置：

```powershell
npm run build
```

## 匯出結果

Obsidian 會生成：

- `Health/Garmin/Daily/YYYY/MM/YYYY-MM-DD.md`
- `Health/Garmin/Activities/YYYY/YYYY-MM-DD-活動名稱-activity-id.md`
- `Health/Garmin/_Indexes/Daily Index.md`
- `Health/Garmin/_Indexes/Activity Index.md`
- `Health/Garmin/AI/latest-status.md`
- `Health/Garmin/AI/daily-summary.md`
- `Health/Garmin/AI/activity-summary.md`
- `Health/Garmin/AI/daily-summary.jsonl`
- `Health/Garmin/AI/activity-summary.jsonl`

如果要讓 AI 掃描，建議直接指定：

`Health/Garmin/AI`

## 注意事項

- Garmin token 會放在 `.runtime/home/garminconnect_tokens`
- 原始 JSON 快照會放在 `healthdata_dir/raw`
- Web 閱讀模式不顯示 raw JSON，但 Obsidian 筆記仍保留原始資料折疊區塊
- 同步與匯出支援進度回報與取消
