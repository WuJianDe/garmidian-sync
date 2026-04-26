import { spawn } from "node:child_process";
import { existsSync, watch } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

const pythonExe = existsSync(path.join(projectRoot, ".venv", "Scripts", "python.exe"))
  ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
  : "python";

const pythonArgs = [
  "-m",
  "src.garmin_obsidian_sync.webapp",
  "--config",
  "config.local.json",
  "--host",
  "127.0.0.1",
  "--port",
  "8765",
  "--no-browser",
];

let child = null;
let shuttingDown = false;
let restartTimer = null;

function startApi() {
  child = spawn(pythonExe, pythonArgs, {
    cwd: projectRoot,
    stdio: "inherit",
    shell: false,
  });

  child.on("exit", (code, signal) => {
    if (shuttingDown) {
      process.exit(code ?? 0);
      return;
    }
    if (signal) {
      scheduleRestart(`API 因訊號 ${signal} 結束`);
      return;
    }
    if ((code ?? 0) !== 0) {
      scheduleRestart(`API 意外結束，退出碼 ${code ?? 0}`);
    }
  });
}

function stopApi() {
  if (!child || child.killed) {
    return;
  }
  child.kill();
}

function scheduleRestart(reason) {
  if (shuttingDown) {
    return;
  }
  if (restartTimer) {
    clearTimeout(restartTimer);
  }
  console.log(`[api-dev] ${reason}，準備重新啟動...`);
  restartTimer = setTimeout(() => {
    restartTimer = null;
    stopApi();
    setTimeout(() => {
      if (!shuttingDown) {
        startApi();
      }
    }, 250);
  }, 150);
}

function watchTarget(targetPath, label) {
  if (!existsSync(targetPath)) {
    return;
  }
  watch(targetPath, { recursive: true }, (_eventType, filename) => {
    if (!filename) {
      return;
    }
    const changed = String(filename);
    if (changed.includes("__pycache__")) {
      return;
    }
    console.log(`[api-dev] 偵測到 ${label} 變更：${changed}`);
    scheduleRestart(`${label} 已更新`);
  });
}

process.on("SIGINT", () => {
  shuttingDown = true;
  if (restartTimer) {
    clearTimeout(restartTimer);
  }
  stopApi();
  setTimeout(() => process.exit(0), 200);
});

process.on("SIGTERM", () => {
  shuttingDown = true;
  if (restartTimer) {
    clearTimeout(restartTimer);
  }
  stopApi();
  setTimeout(() => process.exit(0), 200);
});

watchTarget(path.join(projectRoot, "src", "garmin_obsidian_sync"), "Python 後端");
watchTarget(path.join(projectRoot, "api"), "API 啟動腳本");

console.log("[api-dev] 啟動 API 開發模式：http://127.0.0.1:8765/");
startApi();
