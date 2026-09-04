#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
settings_file="${SETTINGS_FILE:-$HOME/.config/repository-monitoring/monitoring.env}"
agent_dir="${AGENT_DIR:-$HOME/Library/LaunchAgents}"
log_dir="${LOG_DIR:-$HOME/Library/Logs/repository-monitoring}"
launchctl_bin="${LAUNCHCTL_BIN:-launchctl}"

if [[ ! -f "$settings_file" ]]; then
  echo "Create settings first: $settings_file" >&2
  exit 1
fi
if [[ "$(stat -f '%u' "$settings_file")" != "$UID" || "$(stat -f '%OLp' "$settings_file")" != "600" ]]; then
  echo "Settings must be owned by this user and mode 600: $settings_file" >&2
  exit 1
fi
mkdir -p "$agent_dir" "$log_dir"

install_agent() {
  local label="$1" schedule="$2" plist="$agent_dir/$1.plist"
  cat >"$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array><string>$repository_root/scripts/run-repository-monitor.sh</string><string>$schedule</string></array>
  <key>WorkingDirectory</key><string>$repository_root</string>
  <key>StandardOutPath</key><string>$log_dir/$schedule.out.log</string>
  <key>StandardErrorPath</key><string>$log_dir/$schedule.err.log</string>
PLIST
  if [[ "$schedule" == "scan" ]]; then
    cat >>"$plist" <<PLIST
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>14400</integer>
PLIST
  elif [[ "$schedule" == "daily" ]]; then
    cat >>"$plist" <<PLIST
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
PLIST
  else
    cat >>"$plist" <<PLIST
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>6</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>15</integer></dict>
PLIST
  fi
  printf '</dict></plist>\n' >>"$plist"
  plutil -lint "$plist" >/dev/null
  if "$launchctl_bin" print "gui/$UID/$label" >/dev/null 2>&1; then
    "$launchctl_bin" bootout "gui/$UID/$label"
  fi
  "$launchctl_bin" bootstrap "gui/$UID" "$plist"
}

install_agent com.titocr.repository-monitor.scan scan
install_agent com.titocr.repository-monitor.daily daily
install_agent com.titocr.repository-monitor.weekly weekly
echo "Installed repository monitoring: scan every 4 hours, daily at 09:00, weekly Saturday at 09:15."
