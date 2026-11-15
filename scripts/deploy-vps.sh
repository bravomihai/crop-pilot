#!/usr/bin/env bash
# Streamed from the verified GitHub checkout. Production migrations are manual.
# Parse the complete function before executing; child commands cannot consume stdin.
main() {
  set -Eeuo pipefail
  stage=preflight
  on_error() {
    local code=$?
    printf 'ERROR: CropPilot stage %s failed (exit %s). See infra/deploy/README.md.\n' "$stage" "$code" >&2
    exit "$code"
  }
  trap on_error ERR
  fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
  [[ $# == 3 ]] || fail 'Usage: deploy-vps.sh CHECKOUT FULL_COMMIT_SHA verify|deploy'
  repo_path=$1
  sha=$2
  mode=$3
  [[ $repo_path == /* && $repo_path != / ]] || fail 'Expected an absolute checkout path'
  [[ $sha =~ ^[0-9a-f]{40}$ ]] || fail 'Expected a full commit SHA'
  [[ $mode == verify || $mode == deploy ]] || fail 'Expected verify or deploy'
  for command in git docker flock timeout python3; do
    command -v "$command" > /dev/null || fail "Missing required command: $command"
  done
  cd -- "$repo_path"
  [[ $(pwd -P) == "$(git rev-parse --show-toplevel)" ]] || fail 'VPS_PATH must be the repository root'
  if [[ $mode == deploy ]]; then
    exec 9> "$(git rev-parse --absolute-git-dir)/croppilot-deploy.lock"
    flock --exclusive --wait 60 9 || fail 'Another deployment holds the lock'
  fi
  [[ $(git symbolic-ref --short HEAD) == main ]] || fail 'The VPS checkout must be on main'
  [[ -z $(git status --porcelain --untracked-files=normal) ]] || fail 'Resolve local changes before deploying'
  [[ -s .env ]] || fail 'The server .env is missing or empty'
  if git ls-files --error-unmatch .env > /dev/null 2>&1; then
    fail 'The production .env must be untracked'
  fi
  docker compose version > /dev/null
  export DEPLOYMENT_SHA
  DEPLOYMENT_SHA=$(git rev-parse HEAD)
  configure_compose() {
    [[ -f compose.yaml && -f infra/compose.vps.yaml ]] || fail 'Missing VPS Compose configuration'
    compose=(docker compose --project-name croppilot --project-directory "$PWD" --env-file "$PWD/.env"
      -f "$PWD/compose.yaml" -f "$PWD/infra/compose.vps.yaml")
    "${compose[@]}" config --quiet
  }
  configure_compose
  healthy() {
    local service=$1 container state
    container=$("${compose[@]}" ps --all --quiet "$service")
    [[ -n $container && $container != *$'\n'* ]] || fail "Expected one existing $service container"
    state=$(docker inspect --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")
    if [[ $service == gateway || $service == cache-maintenance ]]; then
      [[ $state == running/ || $state == running/healthy ]] || fail "$service is not running"
    else
      [[ $state == running/healthy ]] || fail "$service is not healthy"
    fi
  }
  # Initial provisioning is performed once by the administrator, outside Actions.
  healthy postgres
  if [[ $mode == verify ]]; then
    for service in engine web gateway cache-maintenance; do healthy "$service"; done
    python3 infra/check-local.py --url http://127.0.0.1:18080
    printf 'CROPPILOT_VPS_COMPLETE %s %s\n' "$mode" "$sha"
    exit 0
  fi
  stage=fetch
  GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15' \
    git fetch --quiet --no-tags origin refs/heads/main
  [[ $(git rev-parse FETCH_HEAD) == "$sha" ]] || fail 'main advanced; deploy its latest successful CI run'
  git merge-base --is-ancestor HEAD "$sha" || fail 'The checkout cannot fast-forward to this commit'
  if git cat-file -e "$sha:.env" 2> /dev/null; then
    fail 'The target commit tracks .env'
  fi
  previous_sha=$(git rev-parse HEAD)
  printf 'Updating %s to tested commit %s. Previous commit: %s\n' "$repo_path" "$sha" "$previous_sha"
  git merge --ff-only "$sha"
  DEPLOYMENT_SHA=$sha
  configure_compose
  healthy postgres
  stage=build
  "${compose[@]}" build --pull migrate engine web
  stage='migration-status'
  printf 'Checking migrations without applying production schema changes.\n'
  if ! "${compose[@]}" run --rm --no-deps migrate \
    pnpm --filter @croppilot/web exec prisma migrate status > /dev/null 2>&1; then
    fail 'Migration status is not clean. Review and apply migrations manually under the deployment lock, then rerun.'
  fi
  stage='service-update'
  "${compose[@]}" up -d --no-deps --no-build --pull never --wait --wait-timeout 180 \
    engine web gateway cache-maintenance
  stage=health
  for service in postgres engine web gateway cache-maintenance; do healthy "$service"; done
  for service in engine web; do
    container=$("${compose[@]}" ps --all --quiet "$service")
    image_ref=$(docker inspect --format '{{.Config.Image}}' "$container")
    expected=$(docker image inspect --format '{{.Id}}' "$image_ref")
    actual=$(docker inspect --format '{{.Image}}' "$container")
    [[ $actual == "$expected" ]] || fail "$service is not running the image just built"
  done
  python3 infra/check-local.py --url http://127.0.0.1:18080
  printf 'CROPPILOT_VPS_COMPLETE %s %s\n' "$mode" "$sha"
}

main "$@" < /dev/null
