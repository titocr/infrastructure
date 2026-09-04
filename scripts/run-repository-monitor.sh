#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
action="${1:-scan}"
case "$action" in scan|daily|weekly) ;; *) echo "Usage: $0 {scan|daily|weekly}" >&2; exit 64;; esac

result_file="$(mktemp "${TMPDIR:-/tmp}/repository-monitor.XXXXXX")"
trap 'rm -f "$result_file"' EXIT
python3 "$repository_root/scripts/check-repositories.py" --action "$action" >"$result_file"

while IFS= read -r encoded; do
  printf '%s' "$encoded" | base64 -D | "$repository_root/scripts/send-repository-notification.sh"
done < <(jq -r '.notifications[]? | .message | @base64' "$result_file")
