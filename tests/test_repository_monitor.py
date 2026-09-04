#!/usr/bin/env python3
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import repository_monitor as monitor  # noqa: E402


def git(path, *arguments):
    subprocess.run(["git", "-C", str(path), *arguments], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_repository(root, name="project"):
    repository = root / name
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "Test User")
    (repository / "README.md").write_text("initial\n")
    git(repository, "add", "README.md")
    git(repository, "commit", "-m", "initial")
    return repository


def execute(arguments):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        self_result = monitor.main(arguments)
    assert self_result == 0
    return json.loads(output.getvalue())


class RepositoryMonitorTest(unittest.TestCase):
    def test_discord_notifier_builds_a_payload_without_network_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "monitoring.env"
            settings.write_text('DISCORD_WEBHOOK_URL="https://discord.invalid/webhook"\n')
            settings.chmod(0o600)
            captured = root / "payload.json"
            curl = root / "fake-curl"
            curl.write_text("#!/usr/bin/env bash\ncat > \"$CAPTURED_PAYLOAD\"\n")
            curl.chmod(0o755)
            notifier = SCRIPTS / "send-repository-notification.sh"
            environment = {**os.environ, "SETTINGS_FILE": str(settings), "CURL_BIN": str(curl), "CAPTURED_PAYLOAD": str(captured)}
            subprocess.run([str(notifier)], input="hello Discord\n", text=True, check=True, env=environment)
            self.assertEqual(json.loads(captured.read_text()), {"content": "hello Discord"})

    def test_installer_generates_valid_launchagent_plists_without_loading_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "monitoring.env"
            settings.write_text('DISCORD_WEBHOOK_URL="https://discord.invalid/webhook"\n')
            settings.chmod(0o600)
            launchctl = root / "fake-launchctl"
            launchctl.write_text("#!/usr/bin/env bash\n[[ \"$1\" == print ]] && exit 1\nexit 0\n")
            launchctl.chmod(0o755)
            agents, logs = root / "agents", root / "logs"
            installer = SCRIPTS / "install-repository-monitor.sh"
            environment = {**os.environ, "SETTINGS_FILE": str(settings), "AGENT_DIR": str(agents), "LOG_DIR": str(logs), "LAUNCHCTL_BIN": str(launchctl)}
            subprocess.run([str(installer)], text=True, check=True, env=environment)
            plists = sorted(agents.glob("com.titocr.repository-monitor.*.plist"))
            self.assertEqual(len(plists), 3)
            for plist in plists:
                subprocess.run(["plutil", "-lint", str(plist)], check=True, stdout=subprocess.PIPE)
            self.assertIn("<integer>14400</integer>", (agents / "com.titocr.repository-monitor.scan.plist").read_text())

    def test_discovers_only_direct_repository_roots_including_worktrees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "code"
            root.mkdir()
            source = make_repository(root, "source")
            nested = source / "nested"
            nested.mkdir()
            make_repository(nested, "ignored-nested")
            (root / "not-a-repository").mkdir()
            worktree = root / "feature-worktree"
            git(source, "worktree", "add", "-b", "feature", str(worktree), "HEAD")
            self.assertEqual([path.name for path in monitor.discover_repositories(root)], ["feature-worktree", "source"])

    def test_uncommitted_timer_is_stable_when_file_counts_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, state_dir = Path(temporary) / "code", Path(temporary) / "state"
            root.mkdir()
            repository = make_repository(root)
            (repository / "README.md").write_text("changed\n")
            first = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--now", "2026-08-01T09:00:00Z"])
            (repository / "second.txt").write_text("another change\n")
            execute(["--code-root", str(root), "--state-dir", str(state_dir), "--now", "2026-08-01T12:00:00Z"])
            state = json.loads((state_dir / "state.json").read_text())
            key = f"{repository}::uncommitted"
            self.assertEqual(state["conditions"][key]["first_seen"], "2026-08-01T09:00:00Z")
            self.assertEqual(first["repositories"][0]["changes"]["tracked"], 1)

    def test_daily_digest_waits_for_grace_and_deduplicates_the_day(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, state_dir = Path(temporary) / "code", Path(temporary) / "state"
            root.mkdir()
            repository = make_repository(root)
            (repository / "README.md").write_text("changed\n")
            execute(["--code-root", str(root), "--state-dir", str(state_dir), "--now", "2026-08-01T09:00:00Z"])
            early = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "daily", "--now", "2026-08-02T08:00:00Z"])
            due = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "daily", "--now", "2026-08-02T10:00:00Z"])
            repeated = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "daily", "--now", "2026-08-02T11:00:00Z"])
            self.assertEqual(early["notifications"], [])
            self.assertEqual(len(due["notifications"]), 1)
            self.assertIn("uncommitted", due["notifications"][0]["message"])
            self.assertEqual(repeated["notifications"], [])

    def test_recovery_is_emitted_only_after_a_prior_alert(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, state_dir = Path(temporary) / "code", Path(temporary) / "state"
            root.mkdir()
            repository = make_repository(root)
            (repository / "README.md").write_text("changed\n")
            execute(["--code-root", str(root), "--state-dir", str(state_dir), "--now", "2026-08-01T09:00:00Z"])
            execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "daily", "--now", "2026-08-02T10:00:00Z"])
            git(repository, "checkout", "--", "README.md")
            recovered = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--now", "2026-08-02T14:00:00Z"])
            self.assertEqual(recovered["notifications"][0]["type"], "recovery")

    def test_fetch_failure_is_a_condition_without_claiming_current_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "code"
            root.mkdir()
            repository = make_repository(root)
            git(repository, "remote", "add", "origin", "https://example.invalid/repository.git")
            with patch.object(monitor, "fetch_remote", return_value=(False, "network unavailable")):
                inspected = monitor.inspect_repository(repository, {}, monitor.parse_time("2026-08-01T09:00:00Z"), monitor.dt.timedelta(hours=24))
            failures = [item for item in inspected["conditions"] if item["kind"] == "fetch_failed"]
            self.assertEqual(failures[0]["details"]["message"], "network unavailable")

    def test_prior_fetch_failure_remains_visible_until_a_new_fetch_is_due(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "code"
            root.mkdir()
            repository = make_repository(root)
            git(repository, "remote", "add", "origin", "https://example.invalid/repository.git")
            prior = {"last_fetch": {"attempted_at": "2026-08-01T09:00:00Z", "ok": False, "remote": "origin", "error": "network unavailable"}}
            inspected = monitor.inspect_repository(repository, prior, monitor.parse_time("2026-08-01T10:00:00Z"), monitor.dt.timedelta(hours=24))
            self.assertIn("fetch_failed", [item["kind"] for item in inspected["conditions"]])

    def test_weekly_summary_includes_clean_and_attention_repositories_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, state_dir = Path(temporary) / "code", Path(temporary) / "state"
            root.mkdir()
            clean = make_repository(root, "clean")
            dirty = make_repository(root, "dirty")
            (dirty / "README.md").write_text("changed\n")
            summary = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "weekly", "--now", "2026-08-01T09:00:00Z"])
            repeated = execute(["--code-root", str(root), "--state-dir", str(state_dir), "--action", "weekly", "--now", "2026-08-01T10:00:00Z"])
            self.assertIn("clean: attention — no upstream", summary["notifications"][0]["message"])
            self.assertIn("dirty: attention", summary["notifications"][0]["message"])
            self.assertEqual(repeated["notifications"], [])
