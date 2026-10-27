#!/usr/bin/env python3
"""Run configured quality commands and emit bounded receipts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".harness" / "sensors" / "computational" / "gates.json"
RUNTIME = ROOT / ".harness" / "runtime"
ERROR_LINE = re.compile(r"(?i)(error|failed|failure|exception|traceback|assert|expected|fatal|\bE\d{3,}\b)")


def compact(text: str, limit: int = 40) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    selected = []
    seen = set()
    for line in lines:
        if ERROR_LINE.search(line) and line not in seen:
            selected.append(line[:500])
            seen.add(line)
            if len(selected) >= limit:
                break
    if not selected:
        selected = [line[:500] for line in lines[-min(limit, len(lines)):]]
    if len(lines) > len(selected) and limit > 0:
        marker = f"... {len(lines) - len(selected)} lines omitted; see log_path in the receipt"
        if len(selected) >= limit:
            selected[-1] = marker
        else:
            selected.append(marker)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", nargs="?", default="smoke")
    parser.add_argument("--max-lines", type=int, default=40)
    args = parser.parse_args()

    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
    if args.profile not in profiles:
        print(json.dumps({"status": "invalid", "profile": args.profile}, ensure_ascii=False))
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = RUNTIME / "logs" / stamp
    receipt_dir = RUNTIME / "receipts"
    log_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    final_code = 0

    commands = profiles[args.profile]
    if not commands:
        result = {"status": "skipped", "profile": args.profile, "reason": "no commands configured", "commands": []}
    else:
        for index, command in enumerate(commands, 1):
            process = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True)
            output = (process.stdout or "") + (process.stderr or "")
            log_path = log_dir / f"{index:02d}.log"
            log_path.write_text(output, encoding="utf-8")
            receipt = {
                "command": command,
                "exit_code": process.returncode,
                "summary": compact(output, args.max_lines),
                "full_log": str(log_path.relative_to(ROOT)).replace("\\", "/"),
            }
            receipts.append(receipt)
            if process.returncode != 0:
                final_code = process.returncode
                break
        result = {
            "status": "passed" if final_code == 0 else "failed",
            "profile": args.profile,
            "commands": receipts,
        }

    receipt_path = receipt_dir / f"{stamp}-{args.profile}.json"
    receipt_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["receipt"] = str(receipt_path.relative_to(ROOT)).replace("\\", "/")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return final_code


if __name__ == "__main__":
    raise SystemExit(main())
