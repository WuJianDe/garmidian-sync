import { execFileSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const apiPort = "8765";

const pythonExe = existsSync(path.join(projectRoot, ".venv", "Scripts", "python.exe"))
  ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
  : "python";

function runCommand(command, args) {
  return execFileSync(command, args, {
    cwd: projectRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
}

function listListeningPids(port) {
  const output = runCommand("netstat", ["-ano", "-p", "TCP"]);
  const pids = new Set();
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || !line.includes("LISTENING")) continue;
    const parts = line.split(/\s+/);
    if (parts.length < 5) continue;
    const localAddress = parts[1] || "";
    const state = parts[3] || "";
    const pid = parts[4] || "";
    if (state !== "LISTENING") continue;
    if (!localAddress.endsWith(`:${port}`)) continue;
    if (/^\d+$/.test(pid)) {
      pids.add(pid);
    }
  }
  return [...pids];
}

function processNameForPid(pid) {
  const output = runCommand("tasklist", ["/FI", `PID eq ${pid}`, "/FO", "CSV", "/NH"]).trim();
  if (!output || output.startsWith("INFO:")) {
    return "";
  }
  const match = output.match(/^"([^"]+)"/);
  return match ? match[1].toLowerCase() : "";
}

function cleanupStalePythonApis(port) {
  try {
    const pids = listListeningPids(port);
    const stalePythonPids = pids.filter((pid) => processNameForPid(pid).startsWith("python"));
    if (!stalePythonPids.length) {
      return;
    }
    console.log(`[api] 清理舊的 Python API：${stalePythonPids.join(", ")}`);
    runCommand("taskkill", ["/PID", ...stalePythonPids, "/F"]);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[api] 無法自動清理舊 API，將直接繼續啟動：${message}`);
  }
}

cleanupStalePythonApis(apiPort);

const args = [
  "-m",
  "src.garmin_obsidian_sync.webapp",
  "--config",
  "config.local.json",
  "--host",
  "127.0.0.1",
  "--port",
  apiPort,
  "--no-browser",
];

const child = spawn(pythonExe, args, {
  cwd: projectRoot,
  stdio: "inherit",
  shell: false,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
