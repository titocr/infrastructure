#!/usr/bin/env python3
"""Read-only Git hygiene monitoring for the direct children of a code root."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


STATE_FILE_NAME = "state.json"
SNAPSHOT_FILE_NAME = "current.json"
DEFAULT_CODE_ROOT = Path("/Users/titocr/code")
DEFAULT_STATE_DIR = Path.home() / "Library/Application Support/Repository Monitoring"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso_time(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(repository: Path, *args: str) -> Tuple[bool, str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip() or result.stdout.strip() or f"git exited {result.returncode}"


def discover_repositories(code_root: Path) -> List[Path]:
    """Return only direct children that Git identifies as working trees."""
    if not code_root.is_dir():
        return []
    repositories = []
    for candidate in sorted(code_root.iterdir(), key=lambda path: path.name.lower()):
        if not candidate.is_dir() or candidate.name.startswith("."):
            continue
        ok, top_level = run_git(candidate, "rev-parse", "--show-toplevel")
        if ok and Path(top_level).resolve() == candidate.resolve():
            repositories.append(candidate)
    return repositories


def status_counts(repository: Path) -> Tuple[bool, Dict[str, int], str]:
    ok, output = run_git(repository, "status", "--porcelain=v1", "-z")
    if not ok:
        return False, {}, output
    counts = {"tracked": 0, "staged": 0, "modified": 0, "untracked": 0}
    entries = output.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if entry.startswith("??"):
            counts["untracked"] += 1
            continue
        if len(entry) < 2:
            continue
        counts["tracked"] += 1
        if entry[0] != " ":
            counts["staged"] += 1
        if entry[1] != " ":
            counts["modified"] += 1
        # In -z porcelain v1, rename and copy records have a second path item.
        if entry[0] in "RC" or entry[1] in "RC":
            index += 1
    return True, counts, ""


def branch_status(repository: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ok, branch = run_git(repository, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not ok:
        return None, "detached HEAD"
    upstream_ok, upstream = run_git(repository, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if not upstream_ok:
        return {"branch": branch, "upstream": None, "ahead": 0, "behind": 0}, "no upstream"
    count_ok, counts = run_git(repository, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    if not count_ok:
        return None, counts
    try:
        behind, ahead = (int(value) for value in counts.split())
    except ValueError:
        return None, f"unexpected rev-list count: {counts}"
    return {"branch": branch, "upstream": upstream, "ahead": ahead, "behind": behind}, None


def configured_remote(repository: Path, upstream: Optional[str]) -> Optional[str]:
    if upstream and "/" in upstream:
        return upstream.split("/", 1)[0]
    ok, remote = run_git(repository, "remote")
    if not ok:
        return None
    remotes = [line for line in remote.splitlines() if line]
    return "origin" if "origin" in remotes else (remotes[0] if remotes else None)


def should_fetch(repo_state: Dict[str, Any], now: dt.datetime, interval: dt.timedelta) -> bool:
    last_fetch = repo_state.get("last_fetch", {}).get("attempted_at")
    if not last_fetch:
        return True
    try:
        return now - parse_time(last_fetch) >= interval
    except ValueError:
        return True


def fetch_remote(repository: Path, remote: str) -> Tuple[bool, str]:
    return run_git(repository, "fetch", "--quiet", "--prune", remote)


def condition(kind: str, details: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "details": details}


def inspect_repository(repository: Path, repo_state: Dict[str, Any], now: dt.datetime,
                       fetch_interval: dt.timedelta) -> Dict[str, Any]:
    name = repository.name
    result: Dict[str, Any] = {"name": name, "path": str(repository), "conditions": []}
    status_ok, counts, status_error = status_counts(repository)
    if not status_ok:
        result["conditions"].append(condition("git_error", {"message": status_error}))
        return result
    result["changes"] = counts
    if counts["tracked"]:
        result["conditions"].append(condition("uncommitted", counts))
    if counts["untracked"]:
        result["conditions"].append(condition("untracked", {"count": counts["untracked"]}))

    branch, branch_error = branch_status(repository)
    if branch is None:
        result["conditions"].append(condition("git_error", {"message": branch_error or "branch status unavailable"}))
        return result
    result["branch"] = branch
    remote = configured_remote(repository, branch.get("upstream"))
    if remote and should_fetch(repo_state, now, fetch_interval):
        fetched, fetch_error = fetch_remote(repository, remote)
        result["fetch"] = {"attempted_at": iso_time(now), "ok": fetched, "remote": remote}
        if not fetched:
            result["fetch"]["error"] = fetch_error
            result["conditions"].append(condition("fetch_failed", {"remote": remote, "message": fetch_error}))
        else:
            branch, branch_error = branch_status(repository)
            if branch is not None:
                result["branch"] = branch
    elif repo_state.get("last_fetch"):
        result["fetch"] = repo_state["last_fetch"]
        if not result["fetch"].get("ok", True):
            result["conditions"].append(condition("fetch_failed", {
                "remote": result["fetch"].get("remote", remote or "unknown"),
                "message": result["fetch"].get("error", "previous fetch failed"),
            }))

    branch = result["branch"]
    if not branch.get("upstream"):
        result["conditions"].append(condition("no_upstream", {"branch": branch["branch"]}))
    elif branch["ahead"] or branch["behind"]:
        sync = "diverged" if branch["ahead"] and branch["behind"] else ("ahead" if branch["ahead"] else "behind")
        result["conditions"].append(condition("branch_sync", {
            "status": sync, "branch": branch["branch"], "upstream": branch["upstream"],
            "ahead": branch["ahead"], "behind": branch["behind"],
        }))
    return result


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with path.open() as handle:
            loaded = json.load(handle)
        return loaded if isinstance(loaded, dict) else default
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic_write(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def describe_condition(item: Dict[str, Any]) -> str:
    kind, details = item["kind"], item["details"]
    if kind == "uncommitted":
        return f"uncommitted: {details['tracked']} tracked ({details['staged']} staged, {details['modified']} modified)"
    if kind == "untracked":
        return f"untracked: {details['count']} file(s)"
    if kind == "branch_sync":
        return f"{details['status']}: {details['ahead']} ahead, {details['behind']} behind ({details['branch']})"
    if kind == "no_upstream":
        return f"no upstream ({details['branch']})"
    if kind == "fetch_failed":
        return f"fetch failed ({details['remote']}): {details['message']}"
    return f"Git error: {details['message']}"


def condition_key(repository: Dict[str, Any], item: Dict[str, Any]) -> str:
    return f"{repository['path']}::{item['kind']}"


def age_text(first_seen: str, now: dt.datetime) -> str:
    age = max(dt.timedelta(), now - parse_time(first_seen))
    days, seconds = age.days, age.seconds
    hours = seconds // 3600
    return f"{days}d {hours}h" if days else f"{hours}h"


def update_state(snapshot: Dict[str, Any], state: Dict[str, Any], now: dt.datetime,
                 action: str, grace: dt.timedelta) -> List[Dict[str, str]]:
    previous = state.setdefault("conditions", {})
    current_keys = set()
    notifications: List[Dict[str, str]] = []
    for repository in snapshot["repositories"]:
        for item in repository["conditions"]:
            key = condition_key(repository, item)
            current_keys.add(key)
            prior = previous.get(key, {})
            item["first_seen"] = prior.get("first_seen", iso_time(now))
            item["last_seen"] = iso_time(now)
            item["alerted"] = bool(prior.get("alerted", False))
            previous[key] = {**item, "repository": repository["name"], "path": repository["path"]}

    for key in list(previous):
        if key in current_keys:
            continue
        resolved = previous.pop(key)
        if resolved.get("alerted"):
            notifications.append({
                "type": "recovery",
                "message": f"✅ RECOVERED — Repository hygiene — Mac Studio\n• {resolved['repository']}: {describe_condition(resolved)}",
            })

    if action == "daily" and state.get("last_daily_digest_date") != now.date().isoformat():
        due = []
        for key, item in previous.items():
            if now - parse_time(item["first_seen"]) >= grace:
                item["alerted"] = True
                due.append(item)
        if due:
            lines = [f"• {item['repository']} — {describe_condition(item)} — {age_text(item['first_seen'], now)}" for item in due]
            notifications.append({
                "type": "daily_digest",
                "message": "⚠️ ATTENTION — Repository hygiene — Mac Studio\n" + "\n".join(lines),
            })
            state["last_daily_digest_date"] = now.date().isoformat()
    elif action == "weekly":
        week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
        if state.get("last_weekly_summary") == week_key:
            state["updated_at"] = iso_time(now)
            state["conditions"] = previous
            return notifications
        lines = []
        for repository in snapshot["repositories"]:
            if repository["conditions"]:
                summary = "; ".join(describe_condition(item) for item in repository["conditions"])
                lines.append(f"• {repository['name']}: attention — {summary}")
            else:
                lines.append(f"• {repository['name']}: clean")
        notifications.append({
            "type": "weekly_summary",
            "message": "📋 WEEKLY SUMMARY — Repository hygiene — Mac Studio\n" + "\n".join(lines or ["• No repositories discovered"]),
        })
        state["last_weekly_summary"] = week_key

    state["updated_at"] = iso_time(now)
    state["conditions"] = previous
    return notifications


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=DEFAULT_CODE_ROOT)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--action", choices=("scan", "daily", "weekly"), default="scan")
    parser.add_argument("--fetch-interval-hours", type=int, default=24)
    parser.add_argument("--grace-hours", type=int, default=24)
    parser.add_argument("--now", help="UTC ISO timestamp; intended for tests")
    args = parser.parse_args(argv)
    now = parse_time(args.now) if args.now else utc_now()
    code_root, state_dir = args.code_root.expanduser(), args.state_dir.expanduser()
    state = load_json(state_dir / STATE_FILE_NAME, {"version": 1, "conditions": {}, "repositories": {}})
    repositories = []
    for repository in discover_repositories(code_root):
        prior = state.setdefault("repositories", {}).get(str(repository), {})
        inspected = inspect_repository(repository, prior, now, dt.timedelta(hours=args.fetch_interval_hours))
        repositories.append(inspected)
        if "fetch" in inspected:
            state["repositories"][str(repository)] = {"last_fetch": inspected["fetch"]}
    snapshot = {"generated_at": iso_time(now), "code_root": str(code_root), "repositories": repositories}
    notifications = update_state(snapshot, state, now, args.action, dt.timedelta(hours=args.grace_hours))
    snapshot["notifications"] = notifications
    atomic_write(state_dir / STATE_FILE_NAME, state)
    atomic_write(state_dir / SNAPSHOT_FILE_NAME, snapshot)
    json.dump(snapshot, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
