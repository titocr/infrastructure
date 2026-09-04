#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

settings_file="${SETTINGS_FILE:-$HOME/.config/repository-monitoring/monitoring.env}"
if [[ ! -f "$settings_file" ]]; then
  echo "Missing repository-monitoring settings: $settings_file" >&2
  exit 1
fi
if [[ "$(stat -f '%u' "$settings_file")" != "$UID" || "$(stat -f '%OLp' "$settings_file")" != "600" ]]; then
  echo "Settings must be owned by this user and mode 600: $settings_file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$settings_file"
set +a
if [[ -z "${DISCORD_WEBHOOK_URL:-}" ]]; then
  echo "DISCORD_WEBHOOK_URL is required in $settings_file" >&2
  exit 1
fi

message="$(cat)"
if [[ -z "$message" ]]; then
  echo "Notification message is empty." >&2
  exit 1
fi

curl_bin="${CURL_BIN:-curl}"
jq -n --arg content "$message" '{content:$content}' | "$curl_bin" --fail --silent --show-error \
  --header 'Content-Type: application/json' --data-binary @- "$DISCORD_WEBHOOK_URL" >/dev/null
