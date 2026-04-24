# Garmin Obsidian Sync

把 GarminDB 下載下來的 Garmin Connect 資料，整理成 Obsidian 可直接閱讀的 Markdown 筆記。

這個專案的目標有兩個：

1. 定期把 Garmin 活動與每日狀態同步到本機。
2. 在 Obsidian 中生成「每天一篇」與「每次活動一篇」的筆記，方便你自己看，也方便 Codex 後續分析。

## 架構

`Garmin Connect -> GarminDB -> SQLite/下載檔 -> 本專案匯出器 -> Obsidian Markdown`

底層資料同步依賴 GarminDB。根據 GarminDB 官方 README，目前建議的流程是先安裝 `garmindb`，再執行：

- 初次全量同步：`garmindb_cli.py --all --download --import --analyze`
- 後續增量同步：`garmindb_cli.py --all --download --import --analyze --latest`

來源：

- [GarminDB GitHub](https://github.com/tcgoetz/GarminDB)
- [GarminDb PyPI](https://pypi.org/project/GarminDb/)

## 專案內容

- `config.example.json`
  你的 Garmin 帳號、Obsidian vault 路徑與輸出設定範例。
- `src/garmin_obsidian_sync/garmindb_wrapper.py`
  負責產生 GarminDB 設定檔並呼叫 GarminDB CLI。
- `src/garmin_obsidian_sync/exporter.py`
  從 GarminDB 產生的 SQLite 資料中整理每日筆記與活動筆記。
- `src/garmin_obsidian_sync/cli.py`
  提供 `init`、`sync`、`export`、`run` 四個指令。
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
pip install -r requirements.txt
pip install -e .
```

## 設定

先複製範例設定：

```powershell
Copy-Item config.example.json config.local.json
```

你需要修改以下欄位：

- `garmin.username`
- `garmin.password`
- `garmin.initial_start_date`
- `obsidian.vault_path`

### Obsidian 輸出位置

如果你想輸出到：

`D:\Notes\MyVault\Health\Garmin`

那就把：

- `obsidian.vault_path` 設成 `D:/Notes/MyVault`
- `obsidian.root_folder` 設成 `Health/Garmin`

## 使用方式

初始化本地設定與目錄：

```powershell
garmin-obsidian-sync init --config config.local.json
```

初次全量同步：

```powershell
garmin-obsidian-sync sync --config config.local.json --full
```

只輸出 Markdown：

```powershell
garmin-obsidian-sync export --config config.local.json
```

同步並匯出：

```powershell
garmin-obsidian-sync run --config config.local.json
```

## 輸出結果

預設會在你的 Obsidian vault 生成：

- `Health/Garmin/_Indexes/Daily Index.md`
- `Health/Garmin/_Indexes/Activity Index.md`
- `Health/Garmin/Daily/YYYY/MM/YYYY-MM-DD.md`
- `Health/Garmin/Activities/YYYY/YYYY-MM-DD-HHMM-activity-id.md`

## 注意事項

- 本專案會把 GarminDB 的設定與執行環境放在專案內的 `.runtime/home/.GarminDb`，避免污染你使用者家目錄。
- GarminDB 會在指定的 `healthdata_dir` 下建立自己的資料結構與 SQLite 檔。
- 匯出器用的是「盡量相容 GarminDB schema」的策略：它會掃描 `.db` 檔與可辨識的日期/活動欄位，自動生成筆記。
- 如果你未來想加上睡眠分數、HRV、Body Battery、訓練準備度等專門模板，這個骨架可以再往下客製。

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
