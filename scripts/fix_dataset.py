#!/usr/bin/env python3
"""
Universal dataset fixer for Multi-SWE-bench task instance JSONL files.

Handles:
1. Converting pretty-printed JSON to single-line JSONL
2. Recalculating p2p/f2p/s2p/n2p test categories from stored TestResults
3. Recalculating fixed_tests
4. Validating count fields match actual list lengths
"""

import json
import sys
from pathlib import Path


def build_status_map(test_result: dict) -> dict:
    m = {}
    for t in test_result.get("passed_tests", []):
        m[t] = "PASS"
    for t in test_result.get("failed_tests", []):
        m[t] = "FAIL"
    for t in test_result.get("skipped_tests", []):
        m[t] = "SKIP"
    return m


def make_test_obj(run_s, test_s, fix_s):
    return {"run": run_s, "test": test_s, "fix": fix_s}


def fix_entry(entry: dict) -> dict:
    run_map = build_status_map(entry.get("run_result", {}))
    test_map = build_status_map(entry.get("test_patch_result", {}))
    fix_map = build_status_map(entry.get("fix_patch_result", {}))

    all_tests = set(run_map) | set(test_map) | set(fix_map)

    fixed_tests = {}
    p2p = {}
    f2p = {}
    s2p = {}
    n2p = {}

    for name in all_tests:
        run_s = run_map.get(name, "NONE")
        test_s = test_map.get(name, "NONE")
        fix_s = fix_map.get(name, "NONE")
        obj = make_test_obj(run_s, test_s, fix_s)

        if test_s != "PASS" and fix_s == "PASS":
            fixed_tests[name] = obj

        if fix_s == "PASS":
            if test_s == "PASS":
                p2p[name] = obj
            elif test_s == "FAIL":
                f2p[name] = obj
            elif test_s == "SKIP":
                s2p[name] = obj
            else:  # NONE
                n2p[name] = obj

    entry["fixed_tests"] = fixed_tests
    entry["p2p_tests"] = p2p
    entry["f2p_tests"] = f2p
    entry["s2p_tests"] = s2p
    entry["n2p_tests"] = n2p

    for key in ("run_result", "test_patch_result", "fix_patch_result"):
        tr = entry.get(key, {})
        if not tr:
            continue
        passed = tr.get("passed_tests", [])
        failed = tr.get("failed_tests", [])
        skipped = tr.get("skipped_tests", [])
        if isinstance(passed, list):
            passed = list(dict.fromkeys(passed))
            tr["passed_tests"] = passed
        if isinstance(failed, list):
            failed = list(dict.fromkeys(failed))
            tr["failed_tests"] = failed
        if isinstance(skipped, list):
            skipped = list(dict.fromkeys(skipped))
            tr["skipped_tests"] = skipped
        tr["passed_count"] = len(passed)
        tr["failed_count"] = len(failed)
        tr["skipped_count"] = len(skipped)

    return entry


def fix_resolved_issues(entry: dict) -> dict:
    """Populate resolved_issues from title/body if empty."""
    ri = entry.get("resolved_issues", [])
    if not ri or len(ri) == 0:
        title = entry.get("title", "")
        body = entry.get("body", "")
        number = entry.get("number", "")
        if title or body:
            entry["resolved_issues"] = [
                {
                    "number": number,
                    "title": title or "No title",
                    "body": body or "",
                }
            ]
            print(
                f"  [{entry.get('instance_id', '?')}] Populated resolved_issues from title/body"
            )
    return entry


def load_entries(filepath: Path) -> list:
    """Load entries from a file that may be JSONL or pretty-printed JSON."""
    text = filepath.read_text(encoding="utf-8").strip()
    if not text:
        return []

    entries = []
    try:
        for line in text.splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries
    except json.JSONDecodeError:
        pass

    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        return [obj]
    except json.JSONDecodeError as e:
        print(f"ERROR: Cannot parse {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.jsonl> [output.jsonl]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path

    entries = load_entries(input_path)
    print(f"Loaded {len(entries)} entries from {input_path}")

    fixed_entries = []
    for i, entry in enumerate(entries):
        iid = entry.get("instance_id", f"entry_{i}")
        old_p2p = len(entry.get("p2p_tests", {}))
        old_f2p = len(entry.get("f2p_tests", {}))
        old_n2p = len(entry.get("n2p_tests", {}))

        entry = fix_entry(entry)
        entry = fix_resolved_issues(entry)

        new_p2p = len(entry["p2p_tests"])
        new_f2p = len(entry["f2p_tests"])
        new_n2p = len(entry["n2p_tests"])

        if old_p2p != new_p2p or old_f2p != new_f2p or old_n2p != new_n2p:
            print(
                f"  [{iid}] Fixed: p2p {old_p2p}->{new_p2p}, "
                f"f2p {old_f2p}->{new_f2p}, n2p {old_n2p}->{new_n2p}"
            )

        fixed_entries.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        for entry in fixed_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Wrote {len(fixed_entries)} entries to {output_path}")


if __name__ == "__main__":
    main()
