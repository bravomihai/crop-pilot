import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const script = fileURLToPath(new URL("./deploy-vps.sh", import.meta.url));
function fixture(t) {
  const root = mkdtempSync(path.join(tmpdir(), "croppilot-deploy-test-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const repo = path.join(root, "vps"), writer = path.join(root, "writer");
  const remote = path.join(root, "origin.git"), bin = path.join(root, "bin");
  mkdirSync(repo); mkdirSync(bin);
  const git = (cwd, ...args) => {
    const result = spawnSync("git", args, { cwd, encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    return result.stdout.trim();
  };
  git(root, "init", "--bare", "--initial-branch=main", remote);
  git(repo, "init", "--initial-branch=main");
  git(repo, "config", "user.email", "ci@example.invalid");
  git(repo, "config", "user.name", "CI fixture");
  mkdirSync(path.join(repo, "infra"));
  writeFileSync(path.join(repo, ".gitignore"), ".env\n");
  writeFileSync(path.join(repo, "compose.yaml"), "services: {}\n");
  writeFileSync(path.join(repo, "infra/compose.vps.yaml"), "services: {}\n");
  writeFileSync(path.join(repo, "infra/check-local.py"), "print('fixture connectivity passed')\n");
  writeFileSync(path.join(repo, ".env"), "POSTGRES_PASSWORD=ci-only-fixture\n");
  git(repo, "add", "."); git(repo, "commit", "-m", "initial");
  git(repo, "remote", "add", "origin", remote); git(repo, "push", "-u", "origin", "main");
  const initial = git(repo, "rev-parse", "HEAD");
  git(root, "clone", remote, writer);
  git(writer, "config", "user.email", "ci@example.invalid");
  git(writer, "config", "user.name", "CI fixture");
  writeFileSync(path.join(writer, "README.md"), "new revision\n");
  git(writer, "add", "."); git(writer, "commit", "-m", "next"); git(writer, "push", "origin", "main");
  const next = git(writer, "rev-parse", "HEAD");
  const log = path.join(root, "docker.jsonl");
  writeFileSync(path.join(bin, "docker"), `#!/usr/bin/env node
const fs=require('node:fs');const a=process.argv.slice(2);
fs.appendFileSync(process.env.DOCKER_LOG,JSON.stringify(a)+'\\n');
if(a[0]==='compose'&&a.includes('ps')) console.log(a.at(-1)+'-id');
else if(a[0]==='compose'&&a.includes('run')&&process.env.FAIL_MIGRATIONS==='1') process.exit(1);
else if(a[0]==='inspect') {
  const f=a[a.indexOf('--format')+1];
  console.log(f.includes('.State.')?'running/healthy':f.includes('.Config.Image')?'croppilot-fixture:production':'sha256:built');
} else if(a[0]==='image'&&a[1]==='inspect') console.log('sha256:built');
`, { mode: 0o755 });
  const run = (sha, mode = "deploy", extra = {}) => spawnSync("bash", [script, repo, sha, mode], {
    encoding: "utf8", env: { ...process.env, PATH: bin + path.delimiter + process.env.PATH, DOCKER_LOG: log, ...extra },
  });
  const calls = () => readFileSync(log, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse);
  return { repo, writer, git, initial, next, run, calls };
}

test("verify checks existing health without fetching, building, or updating", (t) => {
  const f = fixture(t), result = f.run(f.next, "verify");
  assert.equal(result.status, 0, result.stderr);
  assert.equal(f.git(f.repo, "rev-parse", "HEAD"), f.initial);
  assert.ok(f.calls().every(a => !a.some(x => ["build", "run", "up", "down"].includes(x))));
});
test("deploy fast-forwards to the tested SHA and checks migrations without applying them", (t) => {
  const f = fixture(t), result = f.run(f.next);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(f.git(f.repo, "rev-parse", "HEAD"), f.next);
  const calls = f.calls(), migration = calls.find(a => a.includes("run"));
  assert.deepEqual(migration.slice(-3), ["prisma", "migrate", "status"]);
  const update = calls.find(a => a.includes("up"));
  assert.ok(update.includes("--no-deps"));
  assert.deepEqual(update.slice(-4), ["engine", "web", "gateway", "cache-maintenance"]);
  assert.match(result.stdout, new RegExp("CROPPILOT_VPS_COMPLETE deploy " + f.next));
  assert.ok(calls.every(a => !a.includes("down") && !a.includes("db:deploy")));
});
test("a stale Actions commit is rejected before build or source update", (t) => {
  const f = fixture(t), result = f.run(f.initial);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /main advanced/);
  assert.equal(f.git(f.repo, "rev-parse", "HEAD"), f.initial);
  assert.ok(f.calls().every(a => !a.includes("build") && !a.includes("up")));
});
test("pending or failed migrations prevent service replacement", (t) => {
  const f = fixture(t), result = f.run(f.next, "deploy", { FAIL_MIGRATIONS: "1" });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Migration status is not clean/);
  assert.ok(f.calls().some(a => a.includes("build")));
  assert.ok(f.calls().every(a => !a.includes("up")));
});
test("local edits are preserved and prevent deployment", (t) => {
  const f = fixture(t);
  writeFileSync(path.join(f.repo, "compose.yaml"), "local configuration\n");
  const result = f.run(f.next);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Resolve local changes/);
  assert.equal(readFileSync(path.join(f.repo, "compose.yaml"), "utf8"), "local configuration\n");
  assert.equal(f.git(f.repo, "rev-parse", "HEAD"), f.initial);
});
