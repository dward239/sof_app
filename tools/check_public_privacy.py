#!/usr/bin/env python3
"""Check current public repository text for inadvertent personal/workstation data.

This is a limited prevention check, not Git-history or binary secret scanning.
No sensitive matched values are printed into CI logs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "build", "dist",
    ".tox", ".nox", "node_modules", ".bundle",
}
SCAN_SUFFIXES = {
    ".md", ".txt", ".py", ".ps1", ".bat", ".cmd", ".cpp", ".c", ".h",
    ".hpp", ".toml", ".yml", ".yaml", ".json", ".csv", ".spec",
    ".ini", ".cfg", ".sh", ".rst", ".xml", ".gradle",
}
SCAN_NAMES = {".gitignore", ".gitattributes", ".env.example", "Makefile", "Dockerfile"}
MAX_BYTES = 2_000_000

PATTERNS = {
    "Windows user-profile path": re.compile(
        r"\b[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][\w .-]+",
        re.IGNORECASE,
    ),
    "Unix/macOS user-home path": re.compile(
        r"/(?:Users|home)/[A-Za-z0-9._-]+(?:/|$)",
    ),
    "Windows volume identifier": re.compile(
        r"volume serial number is\s+[A-F0-9-]+", re.IGNORECASE,
    ),
    "personal/non-noreply email address": re.compile(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    ),
    "potential API token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}"
        r"|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,})\b",
    ),
    "private key marker": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "computer hostname": re.compile(
        r"\b(?:DESKTOP|LAPTOP)-[A-Z0-9]{5,}\b", re.IGNORECASE,
    ),
}

def should_scan(path: Path) -> bool:
    if path == SELF or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
        return False
    if path.suffix.lower() not in SCAN_SUFFIXES and path.name not in SCAN_NAMES:
        return False
    try:
        return path.stat().st_size <= MAX_BYTES
    except OSError:
        return False

def main() -> int:
    findings = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or not should_scan(path):
            continue
        relative = path.relative_to(ROOT)
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for label, expression in PATTERNS.items():
                if label == "personal/non-noreply email address":
                    for match in expression.finditer(line):
                        if not match.group().lower().endswith("@users.noreply.github.com"):
                            findings.append((relative, line_number, label))
                elif expression.search(line):
                    findings.append((relative, line_number, label))
    if findings:
        for relative, line_number, label in findings:
            print(f"{relative}:{line_number}: {label} detected (value withheld)")
        print(f"Privacy check failed: {len(findings)} findings.")
        return 1
    print("Privacy check passed for current repository text.")
    print("Note: Git metadata, history, binaries and release assets are out of scope.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
