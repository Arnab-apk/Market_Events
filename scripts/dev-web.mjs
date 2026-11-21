import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, delimiter, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const venv = join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.MARKET_EVENTS_PYTHON || (existsSync(venv) ? venv : "python3");
const next = join(root, "web/node_modules/next/dist/bin/next");
if (!existsSync(next)) {
  console.error("Install the frontend first: npm --prefix web install");
  process.exit(1);
}
const environment = {
  ...process.env,
  PYTHONPATH: [join(root, "src"), process.env.PYTHONPATH].filter(Boolean).join(delimiter),
  MARKET_EVENTS_ROOT: root,
  MARKET_EVENTS_API_URL: "http://127.0.0.1:8000",
};
// `npm run dev -- --stage` serves the production build (no Next dev overlay, no HMR) and
// disables API hot reload so edits elsewhere cannot restart it mid-demo.
// MARKET_EVENTS_API_RELOAD=0 disables API hot reload on its own.
const stage = process.argv.includes("--stage");
const reload = !stage && process.env.MARKET_EVENTS_API_RELOAD !== "0";
if (stage && !existsSync(join(root, "web/.next/BUILD_ID"))) {
  console.log("Stage mode: building the website first…");
  const build = spawnSync(process.execPath, [next, "build"], { cwd: join(root, "web"), env: { ...process.env }, stdio: "inherit", windowsHide: true });
  if (build.status !== 0) process.exit(build.status || 1);
}
const services = [
  {
    name: "api",
    command: python,
    args: ["-m", "uvicorn", "market_events.api:app", "--host", "127.0.0.1", "--port", "8000",
      ...(reload ? ["--reload", "--reload-dir", join(root, "src")] : [])],
    cwd: root,
  },
  {
    name: "web",
    command: process.execPath,
    args: [next, stage ? "start" : "dev", "--hostname", "127.0.0.1", "--port", "3000"],
    cwd: join(root, "web"),
  },
];

// A crashed service is restarted (bounded) instead of tearing the whole stack down,
// so a transient import error during an edit does not end a live demo.
const MAX_RESTARTS = 5, WINDOW_MS = 60_000;
let stopping = false;
const running = new Map();
function start(service) {
  const child = spawn(service.command, service.args,
    { cwd: service.cwd, env: environment, stdio: "inherit", windowsHide: true });
  running.set(service.name, child);
  child.on("error", error => { console.error(`[${service.name}] ${error.message}`); stop(1); });
  child.on("exit", code => {
    running.delete(service.name);
    if (stopping) return;
    const now = Date.now();
    service.restarts = (service.restarts || []).filter(time => now - time < WINDOW_MS);
    if (service.restarts.length >= MAX_RESTARTS) {
      console.error(`[${service.name}] exited ${MAX_RESTARTS} times within a minute; stopping.`);
      stop(code || 1);
      return;
    }
    service.restarts.push(now);
    console.error(`[${service.name}] exited with code ${code}; restarting in 1s…`);
    setTimeout(() => { if (!stopping) start(service); }, 1000);
  });
}
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of running.values()) child.kill();
  process.exitCode = code;
}
for (const service of services) start(service);
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
console.log(`Market Events website: http://127.0.0.1:3000 (${stage ? "stage: production build" : "development"}; API reload ${reload ? "on" : "off"})`);
