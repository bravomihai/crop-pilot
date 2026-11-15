import "./load-env.mjs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = fileURLToPath(new URL(
  process.platform === "win32"
    ? "../services/engine/.venv/Scripts/python.exe"
    : "../services/engine/.venv/bin/python",
  import.meta.url,
));
const child = spawn(python, [
  "-m", "uvicorn", "fieldshift.api:app",
  "--app-dir", "services/engine", "--reload", "--reload-dir", "services/engine", "--port", "8000",
], { cwd: root, stdio: "inherit" });
child.once("error", () => {
  console.error("Could not start Python. Run: uv sync --project services/engine --frozen --extra dev");
  process.exitCode = 1;
});
child.once("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => child.kill(signal));
}
