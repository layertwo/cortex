#!/usr/bin/env python3
"""
Pre-commit hook: reject logger.* calls that pass banned PII fields.

Enforces the zero-knowledge logging policy (issue #47). Scans staged Python files for
``logger.<method>(..., user_id=...)`` and ``logger.<method>(..., **{"user_id": ...})``
patterns and fails if any banned field name appears as a kwarg or dict key.

Usage (pre-commit local hook):
    python scripts/check_banned_log_fields.py [file1 file2 ...]

Exit 0 = clean, exit 1 = violations found.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BANNED_FIELDS = {
    "user_id",
    "s3_key",
    "object_key",
    "request_context",
    "principalId",
    "item_user_id",
    "collection_user_id",
}

LOGGER_METHODS = {"info", "warning", "error", "debug", "exception", "critical"}


def _extract_kwargs(call: ast.Call) -> set[str]:
    names: set[str] = set()
    for kw in call.keywords:
        if kw.arg is not None:
            names.add(kw.arg)
        elif isinstance(kw.value, ast.Dict):
            for key in kw.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names.add(key.value)
    return names


def _find_logger_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in LOGGER_METHODS:
            if isinstance(func.value, ast.Name) and func.value.id in ("logger", "_logger"):
                yield node


def check_file(path: Path) -> list[str]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations: list[str] = []
    for call in _find_logger_calls(tree):
        kwargs = _extract_kwargs(call)
        leaked = kwargs & BANNED_FIELDS
        if leaked:
            violations.append(
                f"  {path}:{call.lineno}: logger.{call.func.attr}(...) "
                f"leaks {sorted(leaked)}"
            )
    return violations


def main(argv: list[str]) -> int:
    files = [Path(f) for f in argv[1:]] if len(argv) > 1 else list(Path("src").rglob("*.py"))
    files = [f for f in files if f.suffix == ".py" and "generated" not in f.parts]

    all_violations: list[str] = []
    for f in files:
        all_violations.extend(check_file(f))

    if all_violations:
        print("Banned PII log fields detected (see zero-knowledge logging policy):", file=sys.stderr)
        for v in all_violations:
            print(v, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))