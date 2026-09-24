# Remaining optimized replay costs — 24 September 2026

This follow-up audits existing measurements for **mask 151** before choosing
another engine source change. It also prepares a bounded diagnostic using the
same executable. No optimization, compiler change, production worker change,
or new replay simulation was performed for the retained-evidence audit.

The two repeated optimized runs of the same 385-second public Supreme Isthmus
v2.1 replay have the following mean startup measurements:

| Region | Seconds | Evidence and accounting |
| --- | ---: | --- |
| Process initialization through frame zero | 36.671 | Existing collector log marker |
| Archive directory scan, including cache writing | 0.233 | `CArchiveScanner::ScanAllDirs` timer |
| `Game::LoadMap` | 1.720 | Existing inclusive function timer |
| Loading map tiles → loading square textures | 4.501 | Load-message interval, not an isolated function timer |
| Loading square textures → creating grass drawer | 0.378 | Load-message interval, not an isolated function timer |
| Pathfinding finalization | 9.812 | `QTPFS::PathManager::Finalize` returned timer |
| Loading LuaRules → loading LuaGaia | 5.035 | Load-message interval |
| Loading LuaUI → frame zero | 9.631 | Broad tail; includes further initialization after LuaUI |

The two pathfinding timers were 10.292 and 9.331 seconds, with identical
`76174e00` path checksums. These measurements describe wall intervals under the
previous two-CPU experiment. They do not establish function CPU cost or savings;
parallel loading activity and nested timers must not be added indiscriminately.

## Archive cache: real repeated work, low priority on this case

`ArchiveScanner.cpp:476` unconditionally sets `isDirty` for scanning. The existing
`ScanAllDirs` timer surrounds both `ScanDirs` and `WriteCacheData`
(`ArchiveScanner.cpp:463–467`). Its measured 0.230–0.236 seconds therefore bounds
the scan-plus-write opportunity in these runs: the mean is 0.64% of startup,
approximately 0.23% of their 99.548-second mean engine wall time. It excludes
the earlier `ReadCacheData`, so it is not a bound on all archive-cache work.

Both private caches began and ended at exactly 4,242,221 bytes with SHA-256
`39fab61dcb2fbc1910d7e7803a98f96d4a3472520d96106cec74fc2fa2588999`.
Identical bytes do not prove that no rewrite occurred. The prepared diagnostic
records mtime, ctime, inode and byte hashes around the run to corroborate
rewriting separately from content change. It does not claim an isolated writer
duration. Warm-cache seeding was already implemented; none of these numbers is
a gain from introducing it.

A correct no-change writer optimization would still need removed/replaced
archives, changed metadata, broken-archive transitions, new checksums, pool
cleanup and cache-version behavior. That complexity is not presently justified
by this measured small opportunity. No dirty-flag shortcut was applied.

## Map initialization: justified next attribution target

Pathfinding finalization is a substantial measured phase. `Finalize` calls
`pmLoadScreen.Show(&PathManager::Load, this)` at `PathManager.cpp:278–290`.
`Load` includes archive checksums, node-layer initialization and checksumming.
`InitNodeLayersThreaded` populates layers and invokes `UpdateNodeLayer` across
roots. `NodeLayer::Update` contains collision filling, per-cell footprint scans,
speed modifier/bin calculations and tree updates. The broad phase timer cannot
say which component dominates. CPU sampling or narrow per-thread aggregate
timers must separate those components before selecting a source optimization.

The tile-loading interval also warrants attribution. The active mask 151 does
not include the texture-square-assembly experiment (bit 64). Tile file opening
through `CFileHandler` can load/extract an entire archive member before the
subsequent reads; the 4.501-second interval is not evidence that an equivalent
amount of unnecessary copying can be removed. Preserve file/format validation,
metadata, Lua texture behavior and any persistent/streaming extraction paths.

Do not persist initialized path state using only the map name or archive hash.
Initialization includes game movement definitions, mod options, features,
blocking and later Lua changes; `Game.cpp` calls `PostFinalizeRefresh` after Lua
initialization. Continue preserving deterministic arithmetic, exact frame order
and all 15-second movement/construction measurements.

## Simulation profile: previous attribution cannot be reused as current

The earlier 60.714-second Sim profile used the pre-optimization executable and
enabled detailed profiling. Mask 151 changes feature rotation, animation order
bookkeeping, headless presentation bookkeeping and scheduling. Its remaining
hotspots require a new profile; subtracting old buckets from the new elapsed
time would produce unsupported conclusions.

The prepared adapter adds a separate observer to the unchanged pinned runner.
It observes raw profiler totals at frame zero, real GameOver and Shutdown, and
keeps the three production capture streams and every-frame checksum observer
unchanged. All original source, native version, manifest, private-cache,
GameOver, footer and exact stream/checksum guards still execute. The separate
diagnostic marker explicitly excludes the run from latency comparisons.

Raw buckets are inclusive. Main/worker intervals overlap. Callback snapshots
can occur while an outer Sim timer is open; GameOver-to-Shutdown therefore
includes the final outstanding Sim scope as well as teardown. The primary
frame-zero-to-Shutdown window matches the earlier diagnostic. Rare new names
can be absent because profiler name discovery refreshes periodically.

## Reproducibility and current execution status

`profiling/audit_retained_startup.py` verifies the immutable evidence archive
SHA-256 and every inspected member against its inventory, compares all three
raw ordered streams to the validated warmup, and compares every frame checksum
directly to the independently retained official stream. Both candidates have
28 telemetry, 434 team-stat and 2,815 observation records, plus 11,415 checksum
frames. Existing footer receipts corroborate 112 metrics across 16 teams. The
audit does not rerun the production validator or infer a fresh official timing
comparison. Its full output is `profiling/retained-startup-summary.json`.

The general profiler analyzer reproduced all 83 region deltas in the prior
diagnostic and rejected four malformed evidence variants: missing ending,
wrong final frame, duplicate metadata and non-finite totals. Python syntax
checks passed. The new observer itself still needs the bounded real replay run;
the scheduling instructions are in `profiling/README.md`.

Read-only host inspection confirmed that `perf` and `strace` are installed.
`perf_event_paranoid=4` restricts unprivileged sampling; use a root diagnostic
controller if sampling is needed, without changing the sysctl or worker users.
The existing optimized executable is approximately 768 MiB, so retain binary
identity and budget profiler output/memory before collecting call stacks.

No PGO/LTO gain is established. No source optimization was selected from this
audit. OpenAI Codex assisted with source tracing, evidence analysis, the
diagnostic adapter and this report. Work remains in the owner's private-purpose
fork with no upstream contribution.
