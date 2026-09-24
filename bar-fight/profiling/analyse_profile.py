"""Validate profiler observations and rank inclusive regions; never infer speedup."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from audit_retained_startup import require, startup


def analyse_profiler(source, final_frame, options=None):
    snapshots, records, meta, ending = {}, {}, None, None
    current_phase = None
    for line in source.splitlines():
        row = json.loads(line)
        require(ending is None, "Profiler data continues after ending")
        if row["kind"] == "meta":
            require(meta is None and not snapshots, "Duplicate/late profiler metadata")
            meta = row
        elif row["kind"] == "snapshot":
            require(meta is not None and row["phase"] not in snapshots, "Duplicate/early snapshot")
            current_phase = row["phase"]
            require(current_phase in ("frame0", "game_over", "shutdown"), "Unknown snapshot phase")
            snapshots[current_phase] = row
            records[current_phase] = {}
        elif row["kind"] == "record":
            require(current_phase is not None and row["phase"] == current_phase, "Out-of-phase record")
            require(row["name"] not in records[current_phase], "Duplicate profiler name")
            require(type(row["total_ms"]) in (int, float) and math.isfinite(row["total_ms"])
                    and row["total_ms"] >= 0, "Invalid profiler total")
            records[current_phase][row["name"]] = row["total_ms"]
        elif row["kind"] == "end":
            ending = row
        else:
            raise ValueError("Unknown profiler record")
    require(meta and meta["diagnostic_not_timing_ab"] is True and meta["command"] == "debug 1 0",
            "Not the supported diagnostic")
    require(ending and ending["baseline_frame0"] is True, "Missing ending/frame-zero baseline")
    require(ending["game_over_frame"] == ending["last_frame"] == final_frame, "Profiler GameOver mismatch")
    expected_phases = ["frame0", "game_over", "shutdown"] if options is not None else ["frame0", "shutdown"]
    require(list(snapshots) == expected_phases, "Missing/unordered profiler phases")
    if options is not None:
        require(meta.get("schema") == 2 and meta.get("options") == options, "Wrong profiler options/schema")
    require(snapshots["frame0"]["frame"] == 0, "Wrong baseline frame")
    for phase in expected_phases[1:]:
        require(snapshots[phase]["frame"] == final_frame, "Wrong final phase frame")
    require(all(snapshots[phase]["names"] == len(rows) for phase, rows in records.items()), "Incomplete snapshot")
    rankings = {}
    intervals = [("frame0", "shutdown")]
    if "game_over" in snapshots:
        intervals += [("frame0", "game_over"), ("game_over", "shutdown")]
    for begin, end in intervals:
        require(records[begin].keys() <= records[end].keys(), "Profiler names disappeared")
        ranking = [dict(name=name, elapsed_ms=total - records[begin].get(name, 0))
                   for name, total in records[end].items()]
        require(all(row["elapsed_ms"] >= 0 for row in ranking), "Profiler totals regressed")
        rankings[begin + "_to_" + end] = sorted(ranking, key=lambda row: row["elapsed_ms"], reverse=True)
    return dict(meta=meta, snapshots=snapshots, ending=ending, rankings=rankings)


def analyse_run(directory):
    benchmark = json.loads((directory / "benchmark.json").read_text())
    diagnostic = json.loads((directory / "profile-diagnostic.json").read_text())
    require(benchmark["options"] == 151 and benchmark["valid_capture"] is True
            and benchmark["equivalent"] is True and benchmark["errors"] == []
            and benchmark["production_validation_unchanged"] is True
            and benchmark["checksum_evidence"]["exact_match"] is True
            and benchmark["footer"]["status"] == "matched", "Replay did not pass the complete frozen harness")
    require(diagnostic["diagnostic_not_timing_ab"] is True
            and diagnostic["performance_claim_allowed"] is False, "Missing diagnostic label")
    source = (directory / "LuaUI/fork-profiler.jsonl").read_bytes()
    result = analyse_profiler(source.decode(), int(benchmark["end"]["frame"]), options=151)
    result.update(schema=1, kind="optimized_profiler_attribution_not_timing_ab", benchmark=benchmark,
        diagnostic=diagnostic, startup=startup((directory / "infolog.txt").read_text()),
        cache_observation=json.loads((directory / "profile-cache-observation.json").read_text()),
        profiler_sha256=hashlib.sha256(source).hexdigest(),
        limitations="Full profiler instrumentation adds overhead. Nested/MT/Lua buckets overlap; do not sum them. Snapshots taken within callbacks omit still-open outer scopes until they close. GameOver-to-Shutdown includes the final open Sim scope plus teardown, not just teardown. Frame-zero-to-Shutdown matches the earlier diagnostic window. Name discovery is periodically refreshed; rare late first-use buckets may be absent. No engine latency or fleet-throughput claim is valid from this run.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyse_run(args.run_directory)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["rankings"]["frame0_to_shutdown"][:20], indent=2))


if __name__ == "__main__":
    main()
