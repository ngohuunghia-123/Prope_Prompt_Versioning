#!/usr/bin/env python3
"""Backfill Codex user prompts for this repository from local transcripts."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _ai_log_env import PROJECT_ROOT, resolve_log_dir

VN_TZ = timezone(timedelta(hours=7))


def git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def normalized_path(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve())
    except (OSError, RuntimeError):
        return value


def timestamp_vn(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(VN_TZ).isoformat()
    except (TypeError, ValueError):
        return value


def read_jsonl(path: Path):
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def existing_keys(log_dir: Path) -> set[tuple]:
    paths = [log_dir / "session.jsonl"]
    archive = log_dir / "archive"
    if archive.is_dir():
        paths.extend(sorted(archive.glob("*.jsonl")))

    keys = set()
    for path in paths:
        for item in read_jsonl(path):
            if item.get("tool") == "codex" and item.get("event") == "UserPromptSubmit":
                keys.add((
                    item.get("session_id", ""),
                    item.get("turn_id", ""),
                    item.get("prompt", ""),
                ))
    return keys


def transcript_entries(path: Path, repo_root: str, defaults: dict) -> list[dict]:
    records = list(read_jsonl(path))
    if not records:
        return []

    meta = next((r.get("payload", {}) for r in records if r.get("type") == "session_meta"), {})
    related = normalized_path(meta.get("cwd", "")) == repo_root
    if not related:
        related = any(
            r.get("type") == "turn_context"
            and normalized_path(r.get("payload", {}).get("cwd", "")) == repo_root
            for r in records
        )
    if not related:
        return []

    session_id = meta.get("session_id") or meta.get("id", "")
    historical_git = meta.get("git") or {}
    current_turn = ""
    current_model = ""
    turn_models = {}
    entries = []

    def add_entry(timestamp: str, turn_id: str, model: str, prompt: str) -> None:
        prompt = prompt[:1000]
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        entries.append({
            "ts": timestamp_vn(timestamp),
            "tool": "codex",
            "event": "UserPromptSubmit",
            "entry_id": f"codex-{session_id}-{turn_id}-{digest}",
            "session_id": session_id,
            "model": model or defaults["model"],
            "repo": defaults["repo"],
            "branch": historical_git.get("branch") or defaults["branch"],
            "commit": (historical_git.get("commit_hash") or defaults["commit"])[:7],
            "student": defaults["student"],
            "prompt": prompt,
            "turn_id": turn_id,
            "transcript_path": str(path),
        })

    for record in records:
        payload = record.get("payload", {})
        if record.get("type") == "event_msg" and payload.get("type") == "task_started":
            current_turn = payload.get("turn_id", "")
        elif record.get("type") == "turn_context":
            current_turn = payload.get("turn_id", current_turn)
            current_model = payload.get("model", current_model)
            turn_models[current_turn] = current_model
        elif record.get("type") == "event_msg" and payload.get("type") == "user_message":
            prompt = payload.get("message", "")
            if not isinstance(prompt, str) or not prompt:
                continue
            add_entry(record.get("timestamp", ""), current_turn, current_model, prompt)

    # Newer Codex transcript versions no longer duplicate real user messages
    # as event_msg.user_message. Fall back to response_item user messages for
    # those files, excluding injected environment/skill context.
    if not entries:
        for record in records:
            payload = record.get("payload", {})
            if not (
                record.get("type") == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") == "user"
            ):
                continue
            meta = payload.get("internal_chat_message_metadata_passthrough") or {}
            turn_id = meta.get("turn_id", "")
            for content in payload.get("content") or []:
                prompt = content.get("text", "")
                if not isinstance(prompt, str) or not prompt:
                    continue
                if prompt.lstrip().startswith(("<environment_context>", "<skill>")):
                    continue
                add_entry(
                    record.get("timestamp", ""),
                    turn_id,
                    turn_models.get(turn_id, ""),
                    prompt,
                )
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codex_sessions = Path.home() / ".codex" / "sessions"
    if not codex_sessions.is_dir():
        print("[codex-log] No local Codex sessions directory found.", file=sys.stderr)
        return

    origin = git("remote", "get-url", "origin")
    repo = origin.rstrip("/").split("/")[-1].removesuffix(".git")
    defaults = {
        "model": "",
        "repo": repo or PROJECT_ROOT.name,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "--short", "HEAD"),
        "student": git("config", "user.email"),
    }

    log_dir = resolve_log_dir()
    known = existing_keys(log_dir)
    new_entries = []
    related_sessions = 0
    repo_root = normalized_path(str(PROJECT_ROOT))

    for transcript in sorted(codex_sessions.rglob("*.jsonl")):
        entries = transcript_entries(transcript, repo_root, defaults)
        if entries:
            related_sessions += 1
        for entry in entries:
            key = (entry["session_id"], entry["turn_id"], entry["prompt"])
            if key not in known:
                new_entries.append(entry)
                known.add(key)

    new_entries.sort(key=lambda item: item["ts"])
    if args.dry_run:
        print(f"[codex-log] {related_sessions} related session(s), {len(new_entries)} new prompt(s).")
        for entry in new_entries:
            preview = entry["prompt"].replace("\n", " ")[:100]
            print(f"  {entry['ts'][:19]}  {entry['session_id']}  {preview}")
        return

    if not new_entries:
        print(f"[codex-log] {related_sessions} related session(s), no new prompts.", file=sys.stderr)
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "session.jsonl").open("a", encoding="utf-8") as stream:
        for entry in new_entries:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(
        f"[codex-log] Added {len(new_entries)} prompt(s) from "
        f"{related_sessions} related session(s).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
