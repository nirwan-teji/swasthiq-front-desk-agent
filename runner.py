#!/usr/bin/env python3
"""Replays conversation scripts against a running agent and writes the results.

The runner is deliberately dumb. It does not grade, it does not interpret, and it
does not know what a correct answer looks like. It posts each script to your
agent, validates that the response satisfies the contract in schema.md, and writes
one JSON file per run.

Usage
-----
    python3 runner.py                                   # all scripts in conversations/
    python3 runner.py --only cv_0011 cv_0014            # just these
    python3 runner.py --repeat 3                        # determinism check
    python3 runner.py --url http://localhost:8000/agent/run --out results/

Requires only the standard library. Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

TERMINAL_STATES = {
    "booked", "rescheduled", "cancelled", "escalated", "refused", "abandoned",
}
ESCALATION_REASONS = {
    "clinical_urgent", "medical_advice", "not_authorised",
    "ambiguous_patient", "out_of_scope",
}
REQUIRED_FIELDS = (
    "conversation_id", "tool_calls", "terminal_state",
    "escalation_reason", "patient_id", "appointment_id", "reply",
)


class ContractError(Exception):
    """The agent replied, but the reply does not satisfy schema.md."""


def load_scripts(directory: pathlib.Path, only: list[str] | None) -> list[dict]:
    scripts = []
    for path in sorted(directory.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            script = json.load(handle)
        script["_path"] = str(path)
        if only and script.get("id") not in only:
            continue
        scripts.append(script)
    if only:
        found = {s.get("id") for s in scripts}
        for wanted in only:
            if wanted not in found:
                print(f"  ! no script with id {wanted}", file=sys.stderr)
    return scripts


def call_agent(url: str, payload: dict, timeout: float) -> tuple[dict, int]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return json.loads(raw), elapsed_ms


def check_contract(result: dict, script: dict) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in result]
    if missing:
        raise ContractError(f"missing fields: {', '.join(missing)}")

    if result["conversation_id"] != script["id"]:
        raise ContractError(
            f"conversation_id {result['conversation_id']!r} does not match {script['id']!r}"
        )

    state = result["terminal_state"]
    if state not in TERMINAL_STATES:
        raise ContractError(f"terminal_state {state!r} is not one of {sorted(TERMINAL_STATES)}")

    reason = result["escalation_reason"]
    if state == "escalated":
        if reason not in ESCALATION_REASONS:
            raise ContractError(
                f"terminal_state is 'escalated' but escalation_reason is {reason!r}"
            )
    elif reason is not None:
        raise ContractError(
            f"escalation_reason must be null when terminal_state is {state!r}, got {reason!r}"
        )

    if not isinstance(result["tool_calls"], list):
        raise ContractError("tool_calls must be a list")
    for index, call in enumerate(result["tool_calls"]):
        if not isinstance(call, dict) or "name" not in call or "arguments" not in call:
            raise ContractError(f"tool_calls[{index}] needs 'name' and 'arguments'")

    if not isinstance(result["reply"], str):
        raise ContractError("reply must be a string")


def summarise(result: dict) -> str:
    """The fingerprint we compare across repeated runs."""
    names = [call["name"] for call in result["tool_calls"]]
    return f"{result['terminal_state']}/{result['escalation_reason']}/{','.join(sorted(set(names)))}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000/agent/run",
                        help="your agent endpoint (default: %(default)s)")
    parser.add_argument("--dir", default="conversations", type=pathlib.Path,
                        help="directory of conversation scripts (default: %(default)s)")
    parser.add_argument("--out", default="results", type=pathlib.Path,
                        help="where to write results (default: %(default)s)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="run each script this many times (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="per-request timeout in seconds (default: %(default)s)")
    parser.add_argument("--only", nargs="*", default=None, metavar="ID",
                        help="only run these conversation ids")
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"no such directory: {args.dir}", file=sys.stderr)
        return 2

    scripts = load_scripts(args.dir, args.only)
    if not scripts:
        print("nothing to run", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    fingerprints: dict[str, set[str]] = defaultdict(set)
    failures = 0

    print(f"{len(scripts)} script(s), {args.repeat} run(s) each, against {args.url}\n")

    for script in scripts:
        for run in range(1, args.repeat + 1):
            label = f"{script['id']} run {run}/{args.repeat}"
            payload = {
                "conversation_id": script["id"],
                "today": script.get("today", "2026-10-01"),
                "turns": script["turns"],
            }

            try:
                result, elapsed_ms = call_agent(args.url, payload, args.timeout)
            except urllib.error.HTTPError as error:
                print(f"  FAIL  {label}: HTTP {error.code} {error.reason}")
                failures += 1
                continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                print(f"  FAIL  {label}: {type(error).__name__}: {error}")
                failures += 1
                continue

            try:
                check_contract(result, script)
            except ContractError as error:
                print(f"  FAIL  {label}: contract: {error}")
                failures += 1
                continue

            result.setdefault("metrics", {})
            result["metrics"].setdefault("latency_ms", elapsed_ms)

            destination = args.out / f"{script['id']}.run{run}.json"
            with destination.open("w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, ensure_ascii=False)
                handle.write("\n")

            fingerprint = summarise(result)
            fingerprints[script["id"]].add(fingerprint)
            print(f"  ok    {label}: {fingerprint}  ({elapsed_ms} ms)")

    print()
    if args.repeat > 1:
        unstable = {cid: sorted(seen) for cid, seen in fingerprints.items() if len(seen) > 1}
        if unstable:
            print(f"NOT DETERMINISTIC across {args.repeat} runs:")
            for conversation_id, seen in unstable.items():
                print(f"  {conversation_id}")
                for fingerprint in seen:
                    print(f"      {fingerprint}")
        else:
            print(f"deterministic across {args.repeat} runs")

    print(f"\nresults in {args.out}/   failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
