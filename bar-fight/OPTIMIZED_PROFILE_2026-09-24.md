# Optimized mask-151 profile — 24 September 2026

The completed bounded diagnostic confirms that archive scan/cache rewriting is
a small remaining startup cost for this replay. Path initialization remains a
substantial startup region. Simulation attribution identifies script/animation,
path-map updates, feature pre-frame work and movement as larger regions for
further source-level investigation. No new engine optimization was selected or
implemented, and no PGO/LTO or fleet-throughput claim follows from this profile.

## Scope and independent correctness proof

The coordinating task ran one diagnostic after all 42 latency-matrix cases and
restoration completed. It used the retained mask-151 executable
`c7e4d27047f9fb1dc33b98ba9a69ca418b2e979953c7d03a9ac35c4b3274347a`,
the same 385-second public Supreme Isthmus replay, two reserved CPUs and the
pinned unchanged collector/validator/runner. The raw evidence is retained at
`E:\BAR-Replay-Worker\optimized-profile-20260924`; the committed
`profiling/optimized-profile-summary.json` records its hashes and compact results.

An independent local audit invoked no engine and made no host configuration
change. It checked source and observer pins, reparsed the original replay bytes,
reran the unchanged production validator, and obtained an exactly equal complete
capture report. It independently matched the original official75 capture:

| Guard | Result |
| --- | --- |
| Ordered telemetry records | 28 exact matches |
| Ordered team-stat records | 434 exact matches |
| Ordered observation records | 2,815 exact matches |
| Every-frame checksums | All 11,415 frames, 0 through 11,414, exact |
| Real capture GameOver | Frame 11,414 |
| Fresh footer corroboration | 112 metrics, 16 teams, zero mismatches |
| Controller cleanup | Exit 0, no cleanup errors; all 20 affinities restored |
| Worker continuity | Before/after records exactly equal; PIDs and restart counts unchanged |

The original controller configuration SHA is
`f68058ffab45b3b1eeb809abe9ff342e76318138a76f0938f8f891cf80b3bd14`.
The diagnostic engine wall time was 97.549 seconds. Instrumentation affects the
run, so that number is excluded from latency averages and speedup calculations.

## Startup observations

| Region | Seconds | Accounting |
| --- | ---: | --- |
| Process initialization through frame zero | 36.074 | Existing collector log boundary |
| Archive scan including cache writing | 0.232 | Inclusive ScanAllDirs timer |
| Game::LoadMap | 1.670 | Inclusive function timer |
| Map tiles → square textures | 4.370 | Load-message interval |
| Square textures → grass drawer | 0.311 | Load-message interval |
| Pathfinding finalization | 9.428 | Existing PFS finalization timer |
| LuaRules → LuaGaia | 5.089 | Load-message interval |
| LuaUI → frame zero | 9.555 | Broad remaining startup tail |

The cache retained identical 4,242,221-byte content and SHA
`39fab61dcb2fbc1910d7e7803a98f96d4a3472520d96106cec74fc2fa2588999`,
on the same inode, while both mtime and ctime changed. Combined with the source's
unconditional dirty scan path, this corroborates a real rewrite. It does not
measure writing separately. The complete scan/write region is only 0.64% of
startup here and excludes earlier cache reading. A cache-writer change therefore
remains lower priority than the larger measured regions.

PFS initialized 43 node layers using two threads, preserving path checksum
`76174e00`. No reusable persisted path cache was present: only ArchiveCache22.lua
and CACHEDIR.TAG existed. PathManager::Load unconditionally initializes layers;
its comments reject map/mod-only cache identity because Lua has already changed
initialization state. The disabled map/mod hash mixing does not remove node-tree
checksums. This is evidence for further attribution, not permission to reuse
path state or replace deterministic arithmetic.

## Simulation attribution

The following inclusive deltas end at the actual GameOver callback. Nested,
worker, main-thread and Lua regions overlap and must not be summed.

| Profiler region | Seconds |
| --- | ---: |
| Sim | 55.511 |
| ThreadPool::AddTask | 21.585 |
| ThreadPool::WaitFor | 19.780 |
| ThreadPool::RunTask | 18.911 |
| Lua::Callins::Synced | 9.208 |
| Sim::Script | 9.157 |
| CUnitScriptEngine::Tick | 8.959 |
| Sim::Path | 9.045 |
| Sim::Path::MapUpdates | 8.189 |
| Sim::GameFrame | 7.655 |
| Sim::Features::UpdatePreFrame | 7.620 |
| Sim::Unit::MoveType | 7.009 |
| Lua::Callins::Unsynced | 4.163 |
| Sim::Unit::Update | 3.356 |
| Sim::Unit::SlowUpdate | 2.103 |
| Misc::Profiler::AddTime | 1.936 |

These regions map to actual remaining code paths: UnitScriptEngine::Tick covers
COB work, parallel animation ticks, ordered completion/checksum work and deferred
call-ins; PathManager::Update includes map-damage layer updates and dirty-path
processing; FeatureHandler::UpdatePreFrame still visits active features under
the rotation-cache option. The thread-pool numbers overlap their callers and
workers; they do not establish removable waiting or a thread-count benefit.
Narrow source sampling or aggregate subregion timers would be required to choose
a change safely. No additional profiling execution is part of this audit.

## Boundary correction and limitations

The raw observer recorded GameOver at frame 11,414 and Shutdown at frame 11,425.
The analyzer's original equality requirement was incorrect: the engine processed
11 post-GameOver frames while the independent production collector and checksum
observer correctly stopped at GameOver. The local analysis now verifies these
two boundaries separately and records the extra frames explicitly. Four focused
tests cover the valid tail, changed GameOver, regressing Shutdown and conflicting
Shutdown/end records. No raw evidence, widget, capture guard or runner was changed.

Sim from frame zero through Shutdown is 55.612 seconds; the GameOver-to-Shutdown
delta is 0.101 seconds. That tail includes the still-open outer Sim scope, the
11 extra frames and teardown. A callback can snapshot its enclosing scope before
that scope closes. This prevents exact accounting identities between bucket
sums and wall time. Profiler name discovery is periodically refreshed and can
omit rare newly introduced names. Earlier pre-optimization profiles used another
executable and must not be subtracted to infer saved costs.

OpenAI Codex assisted with source tracing, independent evidence checks, the
analysis-only boundary correction and this report. Work remains in the owner's
BAR Fight fork; no upstream contribution was made.
