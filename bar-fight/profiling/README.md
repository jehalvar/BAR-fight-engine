# Bounded optimized-engine diagnostic

These scripts preserve the existing experimental executable and frozen replay
runner. They do not reserve CPUs, change systemd state or publish captures.
Schedule them only after the official-versus-candidate matrix releases its
benchmark window. Do not run them alongside the timed matrix.

## Local retained-evidence audit

From the engine worktree, run:

```powershell
python bar-fight/profiling/audit_retained_startup.py --archive 'E:\BAR-Replay-Worker\engine-optimisations-20260924\full-evidence.tar.gz' --official-checksums 'E:\BAR-Replay-Worker\engine-fork-profile-20260924\result\official-sync-checksums.jsonl' --output bar-fight/profiling/retained-startup-summary.json
```

The archive is read without extracting or executing anything. The exact archive,
binary, replay and runner pins are in the scripts. Full raw logs remain outside
Git. The summary records every inspected member's hash.

## One later-window profile run

Use a new isolated experiment root, for example
`/var/lib/bar-replay-burst/optimized-profile-20260924`. Stage `run_profile.py` and
`profiler_widget.lua` as root-owned, non-writable harness files, recording their
hashes. Create a worker-owned `runs` parent; the individual output must not
exist. Use the existing reservation controller with a unique unit/control
directory, a restoration fallback armed before reservation, and `finally`
restoration. Verify worker PIDs and restart counts before and after. Never
restart active replays to obtain the slots.

The child must run as `bar-replay-burst`, reserved CPUs 30–31, `MemoryMax=6G`,
`MemorySwapMax=0`, `KillMode=control-group`, unit runtime at most 960 seconds,
runner total timeout 900 seconds and engine timeout 840 seconds. Invoke the
following argument vector through the controller, after replacing `ROOT` with
the new experiment directory:

```text
/usr/bin/python3 -B ROOT/harness/run_profile.py
--frozen-runner /var/lib/bar-replay-burst/engine-optimisations-20260924/harness/run_one.py
--source-dir /var/lib/bar-replay-burst/engine-short-target-20260924/benchmark/source
--replay /var/lib/bar-replay-burst/engine-short-target-20260924/benchmark/public_replays/2026-09-20_16-15-09-531_Supreme Isthmus v2.1_2026.07.04.sdfz
--assets-dir /var/lib/bar-replay-burst/assets
--output ROOT/runs/optimized151-profile
--experiment-root ROOT
--reference /var/lib/bar-replay-burst/engine-short-target-20260924/benchmark/runs/01-official75
--sync-reference /var/lib/bar-replay-burst/engine-short-target-20260924/benchmark/runs/01-official75
--widget /var/lib/bar-replay-burst/engine-short-target-20260924/benchmark/harness/checksum_widget.lua
--manifest /var/lib/bar-replay-burst/engine-optimisations-20260924/build/experimental-engine.json
--expected-manifest-sha256 f92c19779f42d2fbee651cca9c6f9d02cc0997d75dbbf05d6bcac1eb321449e3
--cache-source /var/lib/bar-replay-burst/engine-optimisations-20260924/benchmark/runs/00-cold-control-warmup
--expected-cache-source-sha256 529a08097336bbee28f785aff8438654e70524b2ba833be355bea66d741c9cda
--options 151 --cpus 30,31 --timeout 840 --total-timeout 900
```

This is an argv illustration; use structured subprocess arguments so the replay
path's spaces remain intact. Any changed immutable pin should stop the run and
be investigated, not be silently updated. The frozen runner only accepts the
one previously reviewed public 385-second recording. It cannot consume personal
replays or queue jobs. This diagnostic is excluded from latency averages even
if all checks pass.

Analyze completed evidence with:

```text
python analyse_profile.py ROOT/runs/optimized151-profile --output diagnostic-summary.json
```

The analyzer needs `audit_retained_startup.py` in its directory. Retain the
benchmark, validation and comparison receipts, every frame checksum, the full
profiler output, original logs, before/after cache metadata and controller
restoration receipts. Rerun the original exact comparison independently before
reporting the new attribution.

## Further startup attribution only if needed

The existing timer already bounds scan plus writing at about 0.233 seconds on
the warm case, so do not prioritize a cache-writer source patch. Map pathfinding
initialization is the larger measured startup target. The Lua observer begins
too late to profile the whole startup: use existing startup timers for coarse
attribution and a separately identified sampling diagnostic for source-level
attribution if those broad intervals are insufficient.

The host's root controller can run a low-frequency `perf record` around the
unprivileged child (`runuser -u bar-replay-burst -- ...`) without changing
`perf_event_paranoid=4`. Keep it in the same bounded service, keep perf output
outside the job's capture streams, filter the final report to the engine
process, retain lost-sample diagnostics, and explicitly exclude the sampled run
from speed comparisons. Determine supported event/call-stack settings first;
the existence of `/usr/bin/perf` does not prove every event is permitted.
Avoid tracing every syscall across a full replay merely to confirm a small
cache rewrite. No sampling command has been launched by this preparation.

Source changes remain contingent on the measurements. Cache invalidation and
map/path initialization must preserve every existing validation and synced
arithmetic operation. Compiler PGO/LTO remains an unmeasured later experiment.
