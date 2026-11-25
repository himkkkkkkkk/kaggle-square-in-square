"""Minimal DeepSeek-guided evolution of search/algorithm.py."""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALGORITHM = ROOT / "search/algorithm.py"
INCUMBENTS = ROOT / "search/incumbents.json"
EVOLUTION = ROOT / "evolution"
BEST = EVOLUTION / "best_algorithm.py"
BEST_LAYOUTS = EVOLUTION / "best_layouts.json"
HISTORY = EVOLUTION / "history.jsonl"
WEIGHTS = ROOT / "weights.json"
PER_N_BUDGET = 10
SYSTEM_PROMPT = """You evolve Python algorithms for the Squares in Squares geometry task.
For every n in puzzles.json, place n non-overlapping unit squares in the smallest possible
axis-aligned square container. Each output square is [x, y, angle]: its center coordinates
and rotation in radians. Container side length is the largest span of all rotated vertices.

The algorithm runs as search/algorithm.py and must write search/result.json as
{n_string: [[x, y, angle], ...]}. It can resume from its own search/incumbents.json and
must save the best valid layout per n back to that file. Only search/ is writable.
Missing or invalid layouts
receive a grid penalty. Fitness is the normalized weighted mean of
(algorithm_side - aim_side) 
/ aim_side; lower is better and negative means improvement.
puzzles.json contains only the public n values. record.json and aim.json are private
evaluator data, are masked in the sandbox, and must not be read or reconstructed. Feedback
contains fitness gaps, never target layouts. The independent seed starts from a grid and
uses shrink-shake-relax with L-BFGS-B. Preserve a valid incumbent for every n and certify
every candidate. Each invocation receives one n in sys.argv[1] and has a hard 10-second
wall-clock budget; do not add resource loops or change that budget. Preserve other n values
when updating incumbents. Do not embed layout data in the source.
After each search round, an n without a retained strict side-length improvement has its
weight multiplied by 1.01; retained improvement resets its weight to 1. Never edit weights.
Improve the actual search rather than the evaluator or reported score. Return only the
complete replacement Python source, without Markdown fences."""


def extract_source(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines[1:]).strip()
    return text + "\n"


def validate_source(source: str) -> None:
    compile(source, str(ALGORITHM), "exec")


def improved_sizes(previous: dict, candidate: dict) -> set[int]:
    old = {item["n"]: item for item in previous["results"]}
    return {
        item["n"]
        for item in candidate["results"]
        if item["valid"]
        and item["side_length"] < old[item["n"]]["side_length"] - 1e-12
    }


def advance_weights(weights: dict, improved: set[int]) -> dict:
    return {
        key: 1.0 if int(key) in improved else float(weight) * 1.01
        for key, weight in weights.items()
    }


def reweight_report(report: dict, weights: dict) -> dict:
    results = []
    total = 0.0
    total_weight = 0.0
    for item in report["results"]:
        weight = float(weights[str(item["n"])])
        updated = {**item, "weight": weight}
        results.append(updated)
        total += weight * item["gap"]
        total_weight += weight
    return {**report, "total_score": total / total_weight, "results": results}


def print_source_diff(old: str, new: str) -> None:
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "best", "candidate", lineterm=""))
    print("[candidate] source diff (first 200 lines):", flush=True)
    print("\n".join(lines[:201]) if lines else "  no source change", flush=True)


def print_report(report: dict, previous: dict | None = None) -> None:
    print(
        f"[score] total={report['total_score']:.12f} valid={report['valid_puzzles']}/{report['puzzle_count']}",
        flush=True,
    )
    if report.get("stopped_early"):
        print(f"[score] partial run: timeout_n={report['timeout_n']} skipped_n={report['skipped_n']}", flush=True)
    worst = sorted(report["results"], key=lambda item: item["gap"] * item["weight"], reverse=True)[:5]
    for item in worst:
        print(
            f"  n={item['n']} gap={item['gap']:.9g} side={item['side_length']:.9g} "
            f"target={item['target_side_length']:.9g} valid={item['valid']} reason={item['reason']}",
            flush=True,
        )
    if previous:
        old = {item["n"]: item["gap"] for item in previous["results"]}
        changes = sorted(report["results"], key=lambda item: abs(item["gap"] - old[item["n"]]), reverse=True)[:5]
        print("[score] largest gap changes (candidate - best):", flush=True)
        for item in changes:
            print(f"  n={item['n']} delta={item['gap'] - old[item['n']]:+.9g}", flush=True)


def summary(report: dict) -> dict:
    results = sorted(report["results"], key=lambda item: item["gap"] * item["weight"], reverse=True)
    worst = [
        {key: item[key] for key in ("n", "valid", "gap", "weight", "reason")}
        for item in results[:20]
    ]
    return {
        "total_score": report["total_score"],
        "valid_puzzles": report["valid_puzzles"],
        "puzzle_count": report["puzzle_count"],
        "worst_weighted_gaps": worst,
    }


def request_source(source: str, report: dict, history: list[dict], model: str, review: bool = False) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    task = (
        "Review and simplify the algorithm while preserving its search behavior and the per-n contract. "
        "Remove unused imports, dead code, duplicated helpers, redundant comments and unnecessary abstractions. "
        "Do not add features or merely rename everything. The regression score must not get worse and the "
        "replacement must have fewer source lines. Return only complete Python source."
        if review
        else "Improve the current algorithm using its measured fitness and recent failures."
    )
    prompt = {
        "task": task,
        "current_source": source,
        "current_score": summary(report),
        "recent_attempts": history[-3:],
    }
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt)},
            ],
        }
    ).encode()
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    print(
        f"[llm] kind={'review' if review else 'search'} POST {base_url}/chat/completions model={model} "
        f"source_chars={len(source)} best_score={report['total_score']:.12f}",
        flush=True,
    )
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    ca_file = os.environ.get("SSL_CERT_FILE")
    system_ca = Path("/etc/ssl/certs/ca-certificates.crt")
    if ca_file is None and system_ca.exists():
        ca_file = str(system_ca)
    try:
        with urllib.request.urlopen(request, timeout=120, context=ssl.create_default_context(cafile=ca_file)) as response:
            payload = json.load(response)
        print(f"[llm] HTTP {response.status} usage={payload.get('usage', {})}", flush=True)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"DeepSeek HTTP {error.code}: {detail}") from error
    source = extract_source(payload["choices"][0]["message"]["content"])
    print(f"[llm] received {len(source)} chars, {len(source.splitlines())} source lines", flush=True)
    return source


def run_command(command: list[str], timeout: int) -> tuple[bool, str, bool]:
    print(f"[run] timeout={timeout}s command={' '.join(command)}", flush=True)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
        ok = process.returncode == 0
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        output = f"timeout after {timeout}s\n{output}"
        ok = False
    print(f"[run] ok={ok} exit={process.returncode} elapsed={time.monotonic() - started:.2f}s", flush=True)
    if output.strip():
        print(output.rstrip(), flush=True)
    return ok, output, timed_out


def grid_layout(n: int) -> list[list[float]]:
    width = math.isqrt(n - 1) + 1
    return [[i % width + 0.5, i // width + 0.5, 0.0] for i in range(n)]


def evaluate_candidate(score_timeout: int, puzzle_sizes: list[int] | None = None) -> tuple[dict | None, str]:
    result_path = ROOT / "search/result.json"
    score_path = ROOT / "search/score.json"
    result_path.unlink(missing_ok=True)
    score_path.unlink(missing_ok=True)
    puzzles = sorted(puzzle_sizes or json.loads((ROOT / "puzzles.json").read_text()))
    starting = json.loads(INCUMBENTS.read_text()) if INCUMBENTS.exists() else {}
    layouts = {}
    outputs = []
    timeout_n = None
    skipped = []
    for index, n in enumerate(puzzles):
        result_path.unlink(missing_ok=True)
        print(f"[budget] n={n} hard_limit={PER_N_BUDGET}s", flush=True)
        ok, output, timed_out = run_command([sys.executable, str(ROOT / "run_search.py"), str(n)], PER_N_BUDGET)
        outputs.append(output)
        if timed_out:
            timeout_n = n
            remaining = puzzles[index:]
            skipped = remaining[1:]
            current = json.loads(INCUMBENTS.read_text()) if INCUMBENTS.exists() else {}
            for size in remaining:
                key = str(size)
                if key in starting:
                    current[key] = starting[key]
                    layouts[key] = starting[key]
                else:
                    current.pop(key, None)
                    layouts[key] = grid_layout(size)
            INCUMBENTS.write_text(json.dumps(current))
            message = f"[timeout] n={n}; restored it and skipped larger n={skipped}; scoring partial progress"
            print(message, flush=True)
            outputs.append(message)
            break
        if not ok:
            return None, "\n".join(outputs)
        fragment = json.loads(result_path.read_text())
        if set(fragment) != {str(n)}:
            return None, f"n={n} returned wrong result keys: {list(fragment)}"
        layouts.update(fragment)
    result_path.write_text(json.dumps(layouts))
    ok, score_output, _ = run_command(
        [sys.executable, str(ROOT / "evaluator.py"), "--output", str(score_path)],
        score_timeout,
    )
    outputs.append(score_output)
    if not ok:
        return None, "\n".join(outputs)
    report = json.loads(score_path.read_text())
    report.update({"stopped_early": timeout_n is not None, "timeout_n": timeout_n, "skipped_n": skipped})
    score_path.write_text(json.dumps(report, indent=2) + "\n")
    return report, "\n".join(outputs)


def execute_source(source: str, path: Path, best_report: dict, score_timeout: int) -> tuple[dict, str]:
    path.write_text(source)
    print(f"[candidate] saved to {path}", flush=True)
    print_source_diff(ALGORITHM.read_text(), source)
    validate_source(source)
    print("[compile] syntax OK; installing candidate", flush=True)
    ALGORITHM.write_text(source)
    report, output = evaluate_candidate(score_timeout)
    if report is None:
        raise RuntimeError(output[-4000:])
    print_report(report, best_report)
    return report, output


def append_history(event: dict) -> None:
    with HISTORY.open("a") as file:
        file.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=600, help="seconds allowed for final scoring")
    arguments = parser.parse_args()
    if not ALGORITHM.exists():
        parser.error("search/algorithm.py is missing")

    print(
        f"[setup] model={arguments.model} iterations={arguments.iterations} "
        f"per_n_budget={PER_N_BUDGET}s score_timeout={arguments.timeout}s algorithm={ALGORITHM}",
        flush=True,
    )
    EVOLUTION.mkdir(exist_ok=True)
    (EVOLUTION / "candidates").mkdir(exist_ok=True)
    run_id = str(time.time_ns())
    best_source = ALGORITHM.read_text()
    if BEST_LAYOUTS.exists():
        INCUMBENTS.write_bytes(BEST_LAYOUTS.read_bytes())
        print(f"[setup] restored previous layouts from {BEST_LAYOUTS}", flush=True)
    best_report, output = evaluate_candidate(arguments.timeout)
    if best_report is None or not INCUMBENTS.exists():
        raise RuntimeError(f"initial algorithm failed or did not write incumbents:\n{output}")
    BEST.write_text(best_source)
    BEST_LAYOUTS.write_bytes(INCUMBENTS.read_bytes())
    print_report(best_report)
    best_score = best_report["total_score"]
    history = [{"iteration": 0, "score": best_score, "valid": best_report["valid_puzzles"]}]
    append_history({"run_id": run_id, **history[0]})
    print(f"initial score={best_score:.12f}", flush=True)

    for iteration in range(1, arguments.iterations + 1):
        started = time.monotonic()
        print(f"\n{'=' * 24} iteration {iteration}/{arguments.iterations} {'=' * 24}", flush=True)
        candidate_path = EVOLUTION / "candidates" / f"{run_id}-{iteration:04d}.py"
        try:
            candidate_source = request_source(best_source, best_report, history, arguments.model)
            report, output = execute_source(candidate_source, candidate_path, best_report, arguments.timeout)
        except Exception as error:
            report = None
            output = str(error)
            print(f"[candidate] failed: {error}", flush=True)

        accepted = report is not None and report["total_score"] < best_score
        retained = improved_sizes(best_report, report) if accepted else set()
        if accepted:
            best_source = candidate_source
            best_report = report
            best_score = report["total_score"]
            BEST.write_text(best_source)
            BEST_LAYOUTS.write_bytes(INCUMBENTS.read_bytes())
        else:
            ALGORITHM.write_text(best_source)
            INCUMBENTS.write_bytes(BEST_LAYOUTS.read_bytes())
        event = {
            "run_id": run_id,
            "iteration": iteration,
            "kind": "search",
            "candidate": str(candidate_path.relative_to(ROOT)),
            "accepted": accepted,
            "retained_improvements": sorted(retained),
            "stopped_early": report.get("stopped_early", False) if report else False,
            "timeout_n": report.get("timeout_n") if report else None,
            "skipped_n": report.get("skipped_n", []) if report else [],
            "score": report["total_score"] if report else None,
            "valid": report["valid_puzzles"] if report else 0,
            "feedback": "" if report else output[-4000:],
        }
        history.append(event)
        append_history(event)
        reason = (
            "strict score improvement"
            if accepted
            else f"candidate did not improve best_score={best_score:.12f}"
            if report
            else "candidate failed; see error above"
        )
        print(
            f"[decision] accepted={accepted} reason={reason}; restored={'no' if accepted else 'yes'} "
            f"elapsed={time.monotonic() - started:.2f}s",
            flush=True,
        )

        weights = advance_weights(json.loads(WEIGHTS.read_text()), retained)
        WEIGHTS.write_text(json.dumps(weights, indent=2) + "\n")
        best_report = reweight_report(best_report, weights)
        best_score = best_report["total_score"]
        above_one = sum(weight > 1.0 for weight in weights.values())
        print(
            f"[weights] retained_improvements={sorted(retained)} reset={len(retained)} "
            f"above_one={above_one} max={max(weights.values()):.6f}",
            flush=True,
        )

        if iteration % 5 == 0:
            print(f"\n{'=' * 24} code review after iteration {iteration} {'=' * 24}", flush=True)
            review_path = EVOLUTION / "candidates" / f"{run_id}-review-{iteration:04d}.py"
            try:
                review_source = request_source(best_source, best_report, history, arguments.model, review=True)
                review_report, review_output = execute_source(
                    review_source, review_path, best_report, arguments.timeout
                )
            except Exception as error:
                review_report = None
                review_output = str(error)
                print(f"[review] failed: {error}", flush=True)

            old_lines = len(best_source.splitlines())
            new_lines = len(review_source.splitlines()) if review_report else old_lines
            review_accepted = (
                review_report is not None
                and new_lines < old_lines
                and review_report["total_score"] <= best_score + 1e-12
                and review_report["valid_puzzles"] >= best_report["valid_puzzles"]
            )
            if review_accepted:
                best_source = review_source
                best_report = review_report
                best_score = review_report["total_score"]
                BEST.write_text(best_source)
                BEST_LAYOUTS.write_bytes(INCUMBENTS.read_bytes())
            else:
                ALGORITHM.write_text(best_source)
                INCUMBENTS.write_bytes(BEST_LAYOUTS.read_bytes())
            review_event = {
                "run_id": run_id,
                "iteration": iteration,
                "kind": "review",
                "candidate": str(review_path.relative_to(ROOT)),
                "accepted": review_accepted,
                "stopped_early": review_report.get("stopped_early", False) if review_report else False,
                "timeout_n": review_report.get("timeout_n") if review_report else None,
                "score": review_report["total_score"] if review_report else None,
                "valid": review_report["valid_puzzles"] if review_report else 0,
                "lines_before": old_lines,
                "lines_after": new_lines,
                "feedback": "" if review_report else review_output[-4000:],
            }
            history.append(review_event)
            append_history(review_event)
            print(
                f"[review] accepted={review_accepted} lines={old_lines}->{new_lines} "
                f"score={review_event['score']} best={best_score:.12f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
