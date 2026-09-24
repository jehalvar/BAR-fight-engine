"""Audit retained mask-151 runs without extracting or executing archive contents."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import tarfile

ARCHIVE_SHA256 = "a73bebb0252ff5869cb6f0297e02915b0a8c15abb31a3e6db46b20e286c94265"
ENGINE_SHA256 = "c7e4d27047f9fb1dc33b98ba9a69ca418b2e979953c7d03a9ac35c4b3274347a"
REPLAY_SHA256 = "12e42ae02c08aada80770034a1446f27c469751f9d978d3640acdaf8175d8669"
LABELS = ("13-repeat-options-151", "15-repeat-options-151")
STREAMS = ("telemetry.jsonl", "team-stats.jsonl", "unit-observations.jsonl")
PREFIX = "benchmark/runs/"
STAMP = re.compile(r'^\[t=(\d+):(\d+):(\d+\.\d+)\](?:\[f=[^\]]+\])? (.*)$')
TIMER = re.compile(r'^\[~ScopedOnceTimer\]\[(.+)\] (\d+)ms$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def finite_json(source):
    def reject(value):
        raise ValueError("Non-finite JSON: " + value)
    return json.loads(source, parse_constant=reject)


def exact(left, right):
    """Keep numeric values/types and row/array order; ignore object key order."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
    return left == right


def checksum_rows(source):
    rows = [finite_json(line) for line in source.splitlines()]
    checksums = [(row["frame"], row["checksum"]) for row in rows if row["kind"] == "checksum"]
    require([frame for frame, _ in checksums] == list(range(11415)), "Incomplete checksum frames")
    require(all(re.fullmatch(r"[0-9a-f]{8}", value) for _, value in checksums), "Malformed checksum")
    require(any(value != "00000000" for _, value in checksums), "Dummy checksums")
    require(rows[0]["kind"] == "meta" and rows[0]["has_sync_checksums"] is True, "Missing sync support")
    endings = [row for row in rows if row["kind"] == "end"]
    gameovers = [row for row in rows if row["kind"] == "game_over"]
    require(len(endings) == len(gameovers) == 1 and rows[-1] == endings[0], "Invalid checksum ending")
    require(endings[0]["last_frame"] == endings[0]["game_over_frame"] == gameovers[0]["frame"] == 11414,
            "GameOver differs from checksum stream")
    require(endings[0]["rows"] == len(checksums), "Incorrect checksum count")
    return checksums


def startup(log):
    messages, timers, frame_zero, pfs = [], {}, [], []
    for line in log.splitlines():
        match = STAMP.match(line)
        if not match:
            continue
        seconds = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
        text = match[4]
        if text == "REPLAY_TELEMETRY_FRAME 0":
            frame_zero.append(seconds)
        timer = TIMER.match(text)
        if timer:
            timers.setdefault(timer[1], []).append(int(timer[2]) / 1000)
        load = re.fullmatch(r'\[LoadScreen::SetLoadMessage\] text="(.*)"', text)
        if load:
            messages.append({"seconds": seconds, "message": load[1]})
            final = re.fullmatch(r'\[LoadFinalize\] finalized PFS \((\d+)ms, checksum ([0-9a-f]{8})\)', load[1])
            if final:
                pfs.append({"reported_seconds": int(final[1]) / 1000, "checksum": final[2]})
    require(len(frame_zero) == len(pfs) == 1, "Ambiguous startup boundary/PFS timer")

    def once(name):
        values = [row["seconds"] for row in messages if row["message"] == name]
        require(len(values) == 1, "Missing or repeated loading stage: " + name)
        return values[0]

    def timer(name):
        require(len(timers.get(name, [])) == 1, "Missing or repeated timer: " + name)
        return timers[name][0]

    intervals = [dict(start=a["message"], end=b["message"], seconds=b["seconds"] - a["seconds"])
                 for a, b in zip(messages, messages[1:])]
    values = dict(loading_seconds=frame_zero[0],
        scan_including_write_seconds=timer("CArchiveScanner::ScanAllDirs"),
        load_map_seconds=timer("Game::LoadMap"),
        tile_stage_interval_seconds=once("Loading Square Textures") - once("Loading Map Tiles"),
        square_stage_interval_seconds=once("Creating GrassDrawer") - once("Loading Square Textures"),
        pfs_finalize_reported_seconds=pfs[0]["reported_seconds"],
        lua_rules_stage_interval_seconds=once("Loading LuaGaia") - once("Loading LuaRules"),
        lua_ui_to_frame_zero_seconds=frame_zero[0] - once("Loading LuaUI"))
    require(all(math.isfinite(value) and value >= 0 for value in values.values()), "Invalid startup timing")
    return dict(values=values, pfs_checksum=pfs[0]["checksum"], load_message_intervals=intervals)


def audit(archive_path, official_checksum_path):
    require(digest(archive_path.read_bytes()) == ARCHIVE_SHA256, "Archive differs from retained evidence")
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        require(len(set(names)) == len(names), "Duplicate archive member")
        inventory = finite_json(archive.extractfile("full-evidence-inventory.json").read())
        inspected = {}

        def read(name):
            member = archive.getmember(name)
            require(member.isfile() and name in inventory, "Missing/non-file inventory member")
            data = archive.extractfile(member).read()
            info = dict(size=len(data), sha256=digest(data))
            require(info == inventory[name], "Archive inventory mismatch: " + name)
            inspected[name] = info
            return data

        reference = PREFIX + "00-cold-control-warmup/"
        reference_streams = {name: [finite_json(line) for line in read(reference + "LuaUI/" + name).splitlines()]
                             for name in STREAMS}
        official_bytes = official_checksum_path.read_bytes()
        official_checksums = checksum_rows(official_bytes)
        runs = []
        for label in LABELS:
            prefix = PREFIX + label + "/"
            benchmark = finite_json(read(prefix + "benchmark.json"))
            require(benchmark["options"] == 151 and benchmark["valid_capture"] is True
                    and benchmark["equivalent"] is True and benchmark["exit_code"] == 0
                    and benchmark["errors"] == [] and benchmark["production_validation_unchanged"] is True,
                    "Retained run did not pass all guards")
            require(benchmark["engine"]["executable_sha256"] == ENGINE_SHA256
                    and benchmark["replay_sha256"] == REPLAY_SHA256, "Unexpected binary/replay")
            require(benchmark["end"]["reason"] == "game_over" and benchmark["end"]["frame"] == 11414,
                    "No real recorded GameOver")
            footer = benchmark["footer"]
            require(footer["status"] == "matched" and footer["metrics_compared"] == 112
                    and footer["teams_compared"] == 16 and not footer["mismatches"], "Footer receipt failed")
            counts = {}
            for name in STREAMS:
                candidate = [finite_json(line) for line in read(prefix + "LuaUI/" + name).splitlines()]
                require(exact(candidate, reference_streams[name]), "Captured stream differs: " + name)
                counts[name] = len(candidate)
            require(checksum_rows(read(prefix + "LuaUI/benchmark-sync-checksums.jsonl")) == official_checksums,
                    "Checksum sequence differs from independently retained official stream")
            seed = finite_json(read(prefix + "experiment-cache-seed.json"))
            after = finite_json(read(prefix + "experiment-cache-result.json"))
            require(seed["status"] == after["seeded"] == "experiment_warm"
                    and seed["files_before"] == after["files_after"], "Archive cache bytes changed")
            phases = startup(read(prefix + "infolog.txt").decode())
            require(phases["values"]["loading_seconds"] == benchmark["phases"]["loading_seconds"],
                    "Frame-zero marker disagrees with benchmark")
            runs.append(dict(label=label, **phases, engine_wall_seconds=benchmark["engine_wall_seconds"],
                exact_stream_rows_against_warmup=counts, exact_checksum_rows_against_official=len(official_checksums),
                unchanged_cache_files=seed["files_before"], footer_receipt=footer))
    means = {key: statistics.mean(run["values"][key] for run in runs) for key in runs[0]["values"]}
    return dict(schema=1, kind="retained_optimized_startup_attribution", archive_sha256=ARCHIVE_SHA256,
        official_checksum_file_sha256=digest(official_bytes), runs=runs, arithmetic_means=means,
        scan_including_write_fraction_of_loading=means["scan_including_write_seconds"] / means["loading_seconds"],
        scope="Two mask-151 repeats of one 385-second public replay. Direct stream comparison is against the retained validated cold warmup; direct every-frame checksum comparison is against the separately retained official stream. Footer is a verified retained receipt, not a new validator run.",
        limitations="Load-message intervals can include overlapping model/path worker activity. Function timers are inclusive and rounded to milliseconds. ScanAllDirs includes directory scanning and cache writing, but excludes earlier ReadCacheData. Byte equality alone does not prove no rewrite. No timings here establish recoverable savings.",
        inspected_archive_members=inspected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--official-checksums", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = audit(args.archive, args.official_checksums)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("arithmetic_means", "scan_including_write_fraction_of_loading")}, indent=2))


if __name__ == "__main__":
    main()
