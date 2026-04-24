# Garmin Obsidian Sync

把 Garmin Connect 資料同步到本機，整理成 Obsidian 筆記，並透過本機網頁直接查看每日與活動紀錄。

## 架構

`Garmin Connect -> python-garminconnect -> JSON 快照 -> 本專案匯出器 -> Obsidian Markdown`

底層資料同步依賴 `python-garminconnect`，並利用 token store 降低每次都重新登入 Garmin SSO 的需求。前端使用 `Vite`，後端使用 Python API。

來源：

- [python-garminconnect GitHub](https://github.com/cyberjunky/python-garminconnect)

## 專案內容

- `config.example.json`
  你的 Garmin 帳號、Obsidian vault 路徑與輸出設定範例。
- `src/garmin_obsidian_sync/garmin_connect_sync.py`
  負責登入 Garmin、抓取每日資料與活動資料，並保存成 JSON 快照。
- `src/garmin_obsidian_sync/exporter.py`
  從 JSON 快照中整理每日筆記與活動筆記。
- `src/garmin_obsidian_sync/cli.py`
  提供 `init`、`sync`、`export`、`doctor`、`run` 五個指令。
- `src/garmin_obsidian_sync/webapp.py`
  提供本機 API 與靜態前端入口。
- `frontend/`
  Vite 前端，負責同步畫面、紀錄列表與筆記閱讀介面。
- `start-web-ui.bat`
  Windows 一鍵啟動本機服務與瀏覽器頁面。
- `.github/workflows/ci.yml`
  每次 push / PR 自動跑基本驗證。
- `CONTRIBUTING.md`
  團隊協作、commit 與 PR 流程。
- `docs/git-workflow.md`
  這個 repo 的 git 使用方式。

## 安裝

建議使用虛擬環境：

```powershell
python -m venv .venv
.venv\Scripts\activate
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\pip.exe install -e .
```

## 設定

先複製範例設定：

```powershell
Copy-Item config.example.json config.local.json
```

你需要修改以下欄位：

- `garmin.initial_start_date`
- `obsidian.vault_path`

建議不要把 Garmin 帳密直接寫在 `config.local.json`。這個專案支援從環境變數讀取：

- `GARMIN_USERNAME`
- `GARMIN_PASSWORD`

PowerShell 範例：

```powershell
$env:GARMIN_USERNAME="your-email@example.com"
$env:GARMIN_PASSWORD="your-garmin-password"
```

如果你真的要從設定檔讀，也仍然可以填 `garmin.username` 與 `garmin.password`，但不建議。

如果你不想每次手動輸入，也可以在專案根目錄建立 `.env` 檔：

```powershell
Copy-Item .env.example .env
```

然後把 `.env` 改成：

```dotenv
GARMIN_USERNAME=your-email@example.com
GARMIN_PASSWORD=your-garmin-password
```

程式會在讀取 `config.local.json` 前自動載入 `.env`。`.env` 已加入 `.gitignore`，不會被提交。

## 推薦日常流程

第一次設定：

```powershell
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json init
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json doctor
```

之後日常同步：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run
```

### Obsidian 輸出位置

如果你想輸出到：

`D:\Notes\MyVault\Health\Garmin`

那就把：

- `obsidian.vault_path` 設成 `D:/Notes/MyVault`
- `obsidian.root_folder` 設成 `Health/Garmin`

## 使用方式

### 最方便的方式：點一下打開網頁

直接雙擊專案根目錄的 `start-web-ui.bat`，它會啟動本機服務，然後自動打開瀏覽器頁面。

預設網址：

`http://127.0.0.1:8765/`

你可以在網頁裡直接：

- 抓最新資料並匯出
- 完整同步並匯出
- 查看已匯出的每日紀錄
- 查看已匯出的活動紀錄
- 在頁面中直接閱讀筆記內容
- 搜尋已匯出的每日與活動紀錄

### 指令方式

初始化本地設定與目錄：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json init
```

初次全量同步：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json sync --full
```

只輸出 Markdown：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json export
```

檢查本機設定、資料夾與同步狀態：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json doctor
```

同步並匯出：

```powershell
.venv\Scripts\python.exe -m src.garmin_obsidian_sync.cli --config config.local.json run
```

## 前端開發

這個專案現在使用 `Vite` 作為前端開發環境。

第一次安裝：

```powershell
cd frontend
npm install
```

前端開發模式：

```powershell
cd frontend
npm run dev
```

預設開發網址：

`http://127.0.0.1:5173/`

開發模式下會自動代理到本機 Python API `http://127.0.0.1:8765/`。

正式建置：

```powershell
cd frontend
npm run build
```

建置完成後，`start-web-ui.bat` 啟動的 Python 服務會直接提供 `frontend/dist` 裡的靜態前端。

### Garmin 限流重試

如果 Garmin SSO 暫時回 `429 Too Many Requests`，同步器會自動等待後重試。預設值在 `retry` 區塊：

- `attempts`: 最多重試次數
- `initial_delay_seconds`: 第一次等待秒數
- `backoff_multiplier`: 每次失敗後的退避倍率
- `max_delay_seconds`: 每次等待的上限秒數

### Token 快取

系統會把 Garmin 登入 token 保存在專案內的 `.runtime/home/garminconnect_tokens`。

如果 token 仍有效，之後同步就不一定需要重新打 Garmin SSO。

## 輸出結果

預設會在你的 Obsidian vault 生成：

- `Health/Garmin/_Indexes/Daily Index.md`
- `Health/Garmin/_Indexes/Activity Index.md`
- `Health/Garmin/Daily/YYYY/MM/YYYY-MM-DD.md`
- `Health/Garmin/Activities/YYYY/YYYY-MM-DD-HHMM-activity-id.md`

## 注意事項

- 本專案會把 Garmin token 與執行環境放在專案內的 `.runtime/home`，避免污染你使用者家目錄。
- 同步資料會保存在指定的 `healthdata_dir/raw` 之下，格式是 JSON 快照。
- 匯出器會從 JSON 快照生成 Obsidian 筆記，方便你自己看，也方便後續分析。
- `frontend/dist` 和 `frontend/node_modules` 都是本機建置產物，不需要提交到 Git。

## Git Flow

這個 repo 已內建基本協作流程：

- `main` 作為穩定分支
- 功能開發使用 `feature/*`
- 問題修正使用 `fix/*`
- 維護工作使用 `chore/*`
- PR 合併前跑 GitHub Actions CI

詳細流程請看：

- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [docs/git-workflow.md](./docs/git-workflow.md)
