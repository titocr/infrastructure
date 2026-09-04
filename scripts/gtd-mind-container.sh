#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/compose.gtd-mind.yaml"
APP_REPO="${GTD_MIND_APP_REPO:-/Users/titocr/code/gtd-ai}"
NATIVE_ROOT="${GTD_MIND_NATIVE_ROOT:-/Users/titocr/Library/Application Support/GTD AI}"
CONTAINER_ROOT="${GTD_MIND_CONTAINER_ROOT:-/Users/titocr/container-data/gtd-mind}"
CANDIDATE_PARENT="${GTD_MIND_CANDIDATE_PARENT:-/Users/titocr/container-data/gtd-mind-candidate}"
LAUNCH_AGENT="${GTD_MIND_LAUNCH_AGENT:-/Users/titocr/Library/LaunchAgents/com.titocr.gtd-ai.plist}"
NATIVE_DB="$NATIVE_ROOT/state/gtd-ai.sqlite"
NATIVE_ENV="$NATIVE_ROOT/config/gtd-ai.env"
PRODUCTION_DATA_ROOT="$CONTAINER_ROOT/state"
PRODUCTION_ENV_FILE="$CONTAINER_ROOT/config/gtd-mind.env"
STATE_FILE="$CONTAINER_ROOT/migration-state.env"
CANDIDATE_PORT="${GTD_MIND_CANDIDATE_PORT:-3100}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/gtd-mind-container.sh candidate <40-character-app-revision>
  scripts/gtd-mind-container.sh preflight <40-character-app-revision>
  scripts/gtd-mind-container.sh cutover <40-character-app-revision> --approve-production-cutover
  scripts/gtd-mind-container.sh rollback --approve-production-rollback

Candidate uses isolated data and no Todoist credentials. Cutover changes the live
LaunchAgent, port 3000, production database copy, and Tailscale Serve only with
the exact approval flag. Failed cutover checks restore the native service.
USAGE
}

fail() {
  echo "Error: $*" >&2
  return 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_revision() {
  local revision="$1"
  [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || fail "revision must be a full 40-character commit"
  git -C "$APP_REPO" cat-file -e "$revision^{commit}" 2>/dev/null || fail "unknown revision"
}

short_revision() {
  git -C "$APP_REPO" rev-parse --short=12 "$1"
}

image_for() {
  printf 'gtd-mind:%s' "$(short_revision "$1")"
}

candidate_root_for() {
  printf '%s/%s' "$CANDIDATE_PARENT" "$(short_revision "$1")"
}

compose_candidate() {
  local revision="$1"
  GTD_MIND_IMAGE="$(image_for "$revision")" \
  GTD_MIND_CANDIDATE_PORT="$CANDIDATE_PORT" \
  GTD_MIND_CANDIDATE_DATA_ROOT="$(candidate_root_for "$revision")" \
    docker compose -f "$COMPOSE_FILE" --profile candidate "${@:2}"
}

compose_production() {
  local image="$1"
  GTD_MIND_IMAGE="$image" \
  GTD_MIND_PRODUCTION_ENV_FILE="$PRODUCTION_ENV_FILE" \
  GTD_MIND_PRODUCTION_DATA_ROOT="$PRODUCTION_DATA_ROOT" \
  GTD_MIND_CANDIDATE_DATA_ROOT="$CANDIDATE_PARENT/unused" \
    docker compose -f "$COMPOSE_FILE" --profile production "${@:2}"
}

wait_ready() {
  local url="$1"
  local attempts="${2:-30}"
  local response
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if response="$(curl --fail --silent --show-error "$url" 2>/dev/null)" &&
      [[ "$response" == *'"status":"ready"'* ]] &&
      [[ "$response" == *'"database":"ok"'* ]]; then
      return 0
    fi
    sleep 1
  done
  fail "readiness did not succeed: $url"
}

wait_listener_closed() {
  local port="$1"
  local attempts="${2:-30}"
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  fail "listener did not close on port $port"
}

stop_native_service() {
  local domain="gui/$(id -u)"
  launchctl bootout "$domain" "$LAUNCH_AGENT" || launchctl unload -w "$LAUNCH_AGENT"
  for attempt in 1 2 3 4 5; do
    if ! launchctl print "$domain/com.titocr.gtd-ai" >/dev/null 2>&1; then
      wait_listener_closed 3000
      return 0
    fi
    sleep 1
  done
  fail "native LaunchAgent remained registered after stop"
}

start_native_service() {
  local domain="gui/$(id -u)"
  launchctl bootstrap "$domain" "$LAUNCH_AGENT" || launchctl load -w "$LAUNCH_AGENT" || true
  wait_ready http://127.0.0.1:3000/api/health/ready 30
  launchctl print "$domain/com.titocr.gtd-ai" | grep -q 'state = running'
}

require_response_contains() {
  local url="$1"
  local expected="$2"
  local label="$3"
  local response
  response="$(curl --silent --show-error "$url")" || fail "$label request failed"
  [[ "$response" == *"$expected"* ]] || {
    echo "$label response: $response" >&2
    fail "$label response did not contain expected content"
  }
}

sqlite_check() {
  local database="$1"
  local integrity
  local foreign_keys
  integrity="$(sqlite3 "$database" 'PRAGMA integrity_check;')"
  [[ "$integrity" == "ok" ]] || fail "SQLite integrity check failed: $database"
  foreign_keys="$(sqlite3 "$database" 'PRAGMA foreign_key_check;')"
  [[ -z "$foreign_keys" ]] || fail "SQLite foreign-key check failed: $database"
}

validate_current_tailscale_route() {
  tailscale serve status --json | python3 -c '
import json, sys
config = json.load(sys.stdin)
proxies = [
    handler.get("Proxy")
    for site in config.get("Web", {}).values()
    for handler in site.get("Handlers", {}).values()
]
expected_tcp = {"443": {"HTTPS": True}}
if config.get("TCP") != expected_tcp or proxies != ["http://127.0.0.1:3000"]:
    raise SystemExit("expected the single GTD Mind HTTPS Serve route")
'
}

build_exact_image() {
  local revision="$1"
  local image
  local context
  image="$(image_for "$revision")"
  context="$(mktemp -d /private/tmp/gtd-mind-build.XXXXXX)"
  git -C "$APP_REPO" archive "$revision" | tar -x -C "$context"
  docker build --platform linux/arm64 --label "org.opencontainers.image.revision=$revision" \
    --tag "$image" "$context"
  docker image inspect "$image" --format '{{.Id}}' >/dev/null
  echo "$image"
}

candidate() {
  local revision="$1"
  local root
  local image
  local origin="http://127.0.0.1:$CANDIDATE_PORT"
  local backup
  root="$(candidate_root_for "$revision")"
  mkdir -p "$root"
  chmod 700 "$CANDIDATE_PARENT" "$root"
  image="$(build_exact_image "$revision" | tail -1)"

  compose_candidate "$revision" up --detach --force-recreate candidate
  wait_ready "$origin/api/health/ready"
  curl --fail --silent --show-error "$origin/" >/dev/null
  curl --fail --silent --show-error "$origin/api/session" | grep -q '"source":"local"'

  local rejected_status
  rejected_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --request POST "$origin/api/work-items" \
    --header 'Content-Type: application/json' \
    --header 'Origin: http://not-loopback.invalid' \
    --header "Idempotency-Key: candidate-rejected-$(short_revision "$revision")" \
    --data '{"title":"Synthetic rejected candidate item"}')"
  [[ "$rejected_status" == "403" ]] || fail "wrong-origin mutation was not rejected"

  curl --fail --silent --show-error --request POST "$origin/api/work-items" \
    --header 'Content-Type: application/json' \
    --header "Origin: $origin" \
    --header "Idempotency-Key: candidate-persistence-$(short_revision "$revision")" \
    --data '{"title":"Synthetic container persistence check"}' >/dev/null

  compose_candidate "$revision" restart candidate
  wait_ready "$origin/api/health/ready"
  curl --fail --silent --show-error "$origin/api/inbox" | grep -q 'Synthetic container persistence check'

  backup="$root/candidate-backup.sqlite"
  sqlite3 "$root/gtd-ai.sqlite" ".backup '$backup'"
  chmod 600 "$backup"
  sqlite_check "$backup"
  sqlite3 "$backup" "select title from work_items where title='Synthetic container persistence check';" |
    grep -q 'Synthetic container persistence check'

  docker image inspect "$image" \
    --format 'candidate image={{.Id}} architecture={{.Architecture}} size={{.Size}} user={{.Config.User}}'
  echo "Candidate ready at $origin using $image and $root"
}

migration_count_from_revision() {
  git -C "$APP_REPO" show "$1:apps/server/drizzle/meta/_journal.json" |
    python3 -c 'import json,sys; print(len(json.load(sys.stdin)["entries"]))'
}

migration_count_from_release() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["migrationCount"])' "$1"
}

preflight() {
  local revision="$1"
  local image
  local current_release
  local candidate_count
  local current_count
  require_revision "$revision"
  image="$(image_for "$revision")"
  docker image inspect "$image" >/dev/null 2>&1 || fail "candidate image is missing: $image"
  wait_ready "http://127.0.0.1:$CANDIDATE_PORT/api/health/ready" 3
  curl --fail --silent --show-error http://127.0.0.1:3000/api/health/ready >/dev/null
  launchctl print "gui/$(id -u)/com.titocr.gtd-ai" | grep -q 'state = running'
  validate_current_tailscale_route
  [[ -f "$NATIVE_DB" ]] || fail "native database is missing"
  [[ -f "$NATIVE_ENV" ]] || fail "native environment is missing"
  [[ "$(stat -f '%Lp' "$NATIVE_ENV")" == "600" ]] || fail "native environment must have mode 0600"
  sqlite_check "$NATIVE_DB"
  current_release="$(readlink "$NATIVE_ROOT/current")"
  candidate_count="$(migration_count_from_revision "$revision")"
  current_count="$(migration_count_from_release "$current_release/release.json")"
  [[ "$candidate_count" == "$current_count" ]] ||
    fail "migration count differs ($current_count -> $candidate_count); combine no schema change with cutover"
  echo "Preflight passed for $image with migration count $candidate_count"
}

restore_native_after_failed_cutover() {
  local serve_config="$1"
  local image="$2"
  set +e
  echo "Failed-cutover listener diagnostic:" >&2
  lsof -nP -iTCP:3000 -sTCP:LISTEN >&2
  echo "Failed-cutover container session diagnostic:" >&2
  docker exec gtd-mind-production-1 node -e \
    "fetch('http://127.0.0.1:3000/api/session').then(r => r.text()).then(console.log)" >&2
  compose_production "$image" down
  start_native_service
  tailscale serve --bg 3000
  set -e
}

cutover() {
  local revision="$1"
  local approval="${2:-}"
  [[ "$approval" == "--approve-production-cutover" ]] ||
    fail "cutover requires --approve-production-cutover"
  preflight "$revision"

  local image
  local timestamp
  local backup
  local serve_config
  image="$(image_for "$revision")"
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="$NATIVE_ROOT/backups/gtd-ai-pre-container-$timestamp.sqlite"
  serve_config="$NATIVE_ROOT/backups/tailscale-serve-pre-container-$timestamp.json"

  mkdir -p "$PRODUCTION_DATA_ROOT" "$(dirname "$PRODUCTION_ENV_FILE")"
  chmod 700 "$CONTAINER_ROOT" "$PRODUCTION_DATA_ROOT" "$(dirname "$PRODUCTION_ENV_FILE")"
  tailscale serve status --json >"$serve_config"
  chmod 600 "$serve_config"

  local cutover_started=0
  trap 'trap - ERR; if [[ "$cutover_started" == "1" ]]; then restore_native_after_failed_cutover "$serve_config" "$image"; fi' ERR
  cutover_started=1
  tailscale serve reset
  if tailscale serve status --json | grep -q 'http://127.0.0.1:3000'; then
    fail "Tailscale Serve still routes to production port"
  fi
  stop_native_service
  echo "Native listener released port 3000."
  sqlite3 "$NATIVE_DB" ".backup '$backup'"
  chmod 600 "$backup"
  sqlite_check "$backup"
  sqlite3 "$backup" ".backup '$PRODUCTION_DATA_ROOT/gtd-ai.sqlite'"
  chmod 600 "$PRODUCTION_DATA_ROOT/gtd-ai.sqlite"
  cp "$NATIVE_ENV" "$PRODUCTION_ENV_FILE"
  chmod 600 "$PRODUCTION_ENV_FILE"

  compose_production "$image" up --detach --force-recreate production
  wait_ready http://127.0.0.1:3000/api/health/ready
  echo "Production readiness passed."
  curl --fail --silent --show-error http://127.0.0.1:3000/ >/dev/null
  echo "Production web root passed."
  require_response_contains http://127.0.0.1:3000/api/session '"source":"local"' \
    "production session"
  echo "Production local-owner session passed."
  require_response_contains http://127.0.0.1:3000/api/sync-health '"provider":"todoist"' \
    "production sync health"
  echo "Production sync health passed."
  compose_production "$image" restart production
  wait_ready http://127.0.0.1:3000/api/health/ready
  sqlite_check "$PRODUCTION_DATA_ROOT/gtd-ai.sqlite"

  {
    printf 'GTD_MIND_IMAGE=%q\n' "$image"
    printf 'GTD_MIND_REVISION=%q\n' "$revision"
    printf 'GTD_MIND_PRE_CUTOVER_BACKUP=%q\n' "$backup"
    printf 'GTD_MIND_TAILSCALE_CONFIG=%q\n' "$serve_config"
    printf 'GTD_MIND_CUTOVER_AT=%q\n' "$timestamp"
  } >"$STATE_FILE"
  chmod 600 "$STATE_FILE"
  cutover_started=0
  trap - ERR
  echo "Cutover complete. GTD Mind is Mac-local at http://127.0.0.1:3000"
}

rollback() {
  local approval="${1:-}"
  [[ "$approval" == "--approve-production-rollback" ]] ||
    fail "rollback requires --approve-production-rollback"
  [[ -f "$STATE_FILE" ]] || fail "migration state is missing"
  # shellcheck disable=SC1090
  source "$STATE_FILE"
  local transfer="$NATIVE_ROOT/backups/gtd-ai-pre-native-rollback-$(date -u +%Y%m%dT%H%M%SZ).sqlite"
  compose_production "$GTD_MIND_IMAGE" down
  sqlite3 "$PRODUCTION_DATA_ROOT/gtd-ai.sqlite" ".backup '$transfer'"
  chmod 600 "$transfer"
  sqlite_check "$transfer"
  sqlite3 "$transfer" ".backup '$NATIVE_DB'"
  chmod 600 "$NATIVE_DB"
  start_native_service
  tailscale serve --bg 3000
  echo "Native GTD Mind restored with container data transferred back."
}

for command in docker git curl sqlite3 python3 lsof launchctl tailscale; do
  require_command "$command"
done

case "${1:-}" in
  candidate)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    require_revision "$2"
    candidate "$2"
    ;;
  preflight)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    preflight "$2"
    ;;
  cutover)
    [[ $# -eq 3 ]] || { usage; exit 2; }
    require_revision "$2"
    cutover "$2" "$3"
    ;;
  rollback)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    rollback "$2"
    ;;
  *)
    usage
    exit 2
    ;;
esac
