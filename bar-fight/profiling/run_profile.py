"""Add only diagnostic observation to the pinned, unchanged mask-151 replay harness.

Use inside a separately bounded unprivileged diagnostic service with two reserved
CPUs. This adapter does not reserve CPUs, claim queue jobs or publish captures.
All existing identity/cache/validator/stream/checksum/footer guards still run.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
EXPECTED_RUNNER_SHA256 = "5e78a524fec4dffcbd0419b083f092b04e865801c1ad214ad797c3c13a5b33a6"
EXPECTED_ENGINE_SHA256 = "c7e4d27047f9fb1dc33b98ba9a69ca418b2e979953c7d03a9ac35c4b3274347a"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cache_inventory(directory):
    inventory = []
    for path in sorted((directory / "cache").glob("ArchiveCache*.lua")):
        info = path.lstat()
        require(path.is_file() and not path.is_symlink() and info.st_nlink == 1,
                "Cache observation requires ordinary private files")
        inventory.append(dict(name=path.name, size=info.st_size, sha256=digest(path),
                              inode=info.st_ino, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns))
    require(inventory, "Expected a private seeded archive cache")
    return inventory


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--frozen-runner", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("--options", type=int, required=True)
    probe.add_argument("--output", type=Path, required=True)
    probe.add_argument("--manifest", type=Path, required=True)
    probe.add_argument("--cache-source", type=Path, required=True)
    profile_args, _ = probe.parse_known_args(remaining)
    require(profile_args.options == 151, "This diagnostic is restricted to optimized mask 151")
    require(digest(args.frozen_runner) == EXPECTED_RUNNER_SHA256, "Frozen harness pin mismatch")
    spec = importlib.util.spec_from_file_location("frozen_run_one", args.frozen_runner)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    harness.immutable(args.frozen_runner)
    manifest = json.loads(harness.immutable(profile_args.manifest).read_text())
    require(manifest.get("executable_sha256") == EXPECTED_ENGINE_SHA256,
            "Profile must use the retained optimized executable")
    original_add = harness.add_checksum_widget
    widget = harness.immutable(Path(__file__).with_name("profiler_widget.lua"))
    widget_digest = digest(widget)
    observed = {}

    def add_widgets(directory, widget_path, options):
        checksum_digest = original_add(directory, widget_path, options)
        destination = directory / "LuaUI/Widgets/dbg_fork_profiler.lua"
        require(not destination.exists(), "Profiler widget already exists")
        destination.write_bytes(widget.read_bytes())
        for short in ("BAR", "BYAR"):
            path = directory / "LuaUI/Config" / (short + ".lua")
            if not path.exists():
                path = directory / "LuaUI/Configs" / (short + ".lua")
            source = path.read_text()
            anchor = '["Replay Benchmark Sync Checksums"]=1'
            require(source.count(anchor) == 1, "Unexpected checksum widget configuration")
            path.write_text(source.replace(anchor, anchor + ',["Replay Fork Profiler"]=1', 1))
        require(digest(directory / "LuaUI/Widgets/dbg_benchmark_sync_checksums.lua") == checksum_digest,
                "Checksum observer changed")
        require(digest(destination) == widget_digest, "Profiler copy changed")
        observed["cache_before"] = cache_inventory(directory)
        # A separate marker prevents this diagnostic being mistaken for a timing A/B.
        (directory / "profile-diagnostic.json").write_text(json.dumps(dict(schema=1,
            diagnostic_not_timing_ab=True, performance_claim_allowed=False,
            runner_sha256=EXPECTED_RUNNER_SHA256, adapter_sha256=digest(__file__),
            profiler_widget_sha256=widget_digest, **observed), indent=2) + "\n")
        return checksum_digest

    harness.add_checksum_widget = add_widgets
    sys.argv = [str(args.frozen_runner), *remaining]
    harness.main()
    directory = profile_args.output.resolve()
    observed["cache_after"] = cache_inventory(directory)
    before = {row["name"]: row for row in observed["cache_before"]}
    after = {row["name"]: row for row in observed["cache_after"]}
    require(before.keys() == after.keys(), "Private cache inventory changed")
    observed["files"] = [dict(name=name,
        content_identical=all(before[name][key] == after[name][key] for key in ("size", "sha256")),
        metadata_changed=any(before[name][key] != after[name][key] for key in ("inode", "mtime_ns", "ctime_ns")))
        for name in before]
    observed["interpretation"] = "Changed timestamps with identical bytes corroborate cache rewrite; no isolated writer duration is measured."
    (directory / "profile-cache-observation.json").write_text(json.dumps(observed, indent=2) + "\n")
    require(digest(widget) == widget_digest and digest(args.frozen_runner) == EXPECTED_RUNNER_SHA256,
            "Profiler inputs changed during the run")


if __name__ == "__main__":
    main()
