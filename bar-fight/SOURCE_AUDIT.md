# Source audit: useful next experiments

The absence of a gain from changing the CPU target does not show that the engine
cannot be improved. It shows that increasing this scheduling target alone did
not help the tested short replay. The next experiments should remove work or
measure the other limits that determine when simulation frames advance.

All source references below use the pinned upstream base
`de69361239d8c8b1012dba3f5aa3122954ea4da3`. Candidates have not been deployed.

## Measured priority: feature pre-frame transforms

The [completed diagnostic](PROFILE_2026-09-24.md) measured 10.746 seconds in
`Sim::Features::UpdatePreFrame`, inside a 60.714-second `Sim` region. That is
17.7% of the instrumented Sim bucket, not 17.7% of engine runtime and not a
promised saving. This region deserves investigation ahead of broad compiler
tuning or more CPU-target trials.

`FeatureHandler.cpp:189–195` walks **all active features**, rather than only
moving/updating features. Each `CSolidObject::UpdatePrevFrameTransform`
(`SolidObject.cpp:464–470`) saves every model piece's previous transform and
reconstructs a quaternion from the current transform matrix before copying the
position. A candidate is change-aware reuse of the quaternion when its exact
matrix inputs are unchanged, retaining piece snapshots and translation.

A blanket skip is unsafe. `SavePrevModelSpaceTransform` forces lazy model-space
matrix evaluation; those matrices are also read through synced Lua. Lua can move,
rotate or alter pieces on features outside the normal moving-feature queue.
`IsMoving`, zero speed or update-queue membership alone are insufficient guards.
These files compile into shared `engineSim`, so a local `#ifdef HEADLESS` in the
simulation library would not automatically create a headless-only change.

The next experiment needs exact cache invalidation, creation/forced-move/spin/
piece-change coverage and complete replay comparisons. No transform shortcut
has been applied in this branch.

## 1. Avoid GPU uniform packing in headless mode

`CGame::Draw` still calls `UpdateUnsynced`, which updates the world, units and
features. `CModelDrawerDataBase<T>::UpdateCommon` calls `UpdateObjectUniforms`
for each object. That performs an object-map lookup, marks an upload entry dirty,
and copies drawing flags, ID, team, position, speed and health into GPU-facing
storage. Headless GL4 support is false, so the model-uniform uploader never
creates its GPU buffer and its update returns without uploading those records.

Relevant source:

- `rts/Game/Game.cpp:1418,1436`: world update and draw/update entry points.
- `rts/Rendering/Common/ModelDrawerData.h:204–230`: packing and call site.
- `rts/Rendering/Models/ModelsMemStorage.cpp:97–102`: lookup and dirty tracking.
- `rts/Rendering/ModelsDataUploader.cpp:47–49,329–332`: unsupported buffer paths.
- `rts/lib/headlessStubs/gladstub.cpp:40,52,55`: disabled GL capabilities.

Minimal candidate around the existing call:

```cpp
#ifndef HEADLESS
	UpdateObjectUniforms(o);
#endif
```

This is a proposed source change, not an applied optimisation in this branch.
Retain object allocation/deallocation, Lua's separate user-defined uniforms,
draw positions, draw flags, transforms, every existing Lua callback and draw
buffer flushing. `UpdateObjectTrasform` touches lazy transform state used by
other code and must not be removed casually. Do not use a broad `Draw()` early
return: the function also services callbacks and buffer cleanup.

The expected importance is modest and unmeasured: one lookup and record update
per unit/feature per draw iteration disappears. A profiler bucket containing
this work is an upper bound on opportunity, not the saving from this specific
change. Compilation and exact replay comparisons are still required.

## 2. Avoid rewriting a genuinely unchanged archive cache

`ArchiveScanner.cpp:476` marks every scan dirty, even when the existing path and
mtime validation accepts all archives. `ScanAllDirs` immediately calls the cache
writer at line 467. `WriteCacheData` sorts/rebuilds metadata, can spend up to one
second pruning a large pool cache, then serializes all pool hashes again.

The retained official seed is about 4.2 MB. Its reuse is already implemented in
BAR Fight: engine/release/game/map/root identity, exact hashes, private writable
job copies and publication locking are preserved. Seed reuse itself is not a
new fork optimisation.

A candidate would distinguish "seen in this scan" from "persisted content
changed", while still running all archive checks. Correct handling must include
removed archives, replaced archives, changed paths/metadata, broken-archive
transitions, new checksums and cache-format changes. Keep bounded pool cleanup
on meaningful changes or explicit maintenance. Simply removing `isDirty=true`
would be incorrect. Measure serialization time before assigning this priority.

The previous experiment deliberately gave each custom run a fresh private
archive cache. Its roughly 46-second startup disadvantage against official
cache-hit controls is not evidence of a 46-second saving available to production.

## 3. Measure replay pacing before changing more scheduling limits

The CPU target is only one limit:

- `GameServer.cpp:954–961` independently caps speed using average simulation
  frame time and `1 - MinSimDrawBalance` (default 0.15). This applies in headless
  builds too.
- `GameServer.cpp:803–808` holds the replay clock when the local simulation is
  at least 30 frames behind. Demo playback returns through `SendDemoData` before
  the ordinary non-replay frame-production loop.
- `NetCommands.cpp:245` sets the client processing budget from draw time and
  the same balance, clamped between 5 ms and `1000 / MinDrawFPS`.
- `Game.cpp:1809–1819` can sleep after a headless simulation frame. This sleep
  is outside the `Sim` profiler bucket and average simulation-frame time.

Existing logs do not prove which limit bound. A diagnostic patch should
aggregate host-cap bindings, CPU-target reductions, replay-clock-held time,
client budget exits with backlog, zero-frame iterations and actual sleep time.
Use thread-owned counters and emit once at shutdown. Do not add shared
`SCOPED_TIMER` bookkeeping to the server thread: its recursion map is not
thread-safe. Do not perform extra queue scans with
`GetNumQueuedSimFrameMessages`, which also processes ping/progress messages.

## 4. Lower-priority opportunities

- Archive checksumming stable-sorts filenames at `ArchiveScanner.cpp:1055–1064`
  before combining filename and content SHA-512 hashes using XOR. The final
  combination is order-independent. Removing just the sort is a candidate for
  cold-cache checksumming, preserving every file hash and ignore rule. It is
  unlikely to matter for already warm replay jobs; validate archive types and
  error behavior before using it.
- Publishing a verified byte-identical seed could skip an unnecessary copy and
  fsync transaction under the existing publication lock. This is worker
  orchestration work, outside the child-engine timing and outside this fork.
- Compiler PGO/LTO is a later experiment. The official build already uses `-O3`;
  a different build label alone is not evidence of faster execution.

Do not cache pathfinding only by map name or archive checksum. Lua initialization
and game options can change terrain/blocking before pathing is initialized
(`QTPFS/PathManager.cpp:432–443` and `Game.cpp:705`). Reusing state without all of
those inputs could simulate a different match.

## Measurement method

The engine's existing `debug 1 0` command enables detailed profiler buckets while
keeping the profile drawer disabled. Read raw totals with
`Spring.GetProfilerTimeRecord(name, false)` at frame zero and shutdown. The
automatic printed summary uses cached data refreshed roughly once a second and
can omit the final interval. A profile-enabled run adds overhead and must not be
used as an unbiased candidate/control speed benchmark.

Interpret buckets as inclusive: `Sim` contains nested unit, pathing, projectile,
LOS, script and Lua work. `Update` means `UpdateUnsynced`, not `CGame::Update`.
`Draw` excludes that update and the preceding RmlGui update. Lua timing overlaps
other buckets, and worker-thread totals can overlap main-thread wall time.
Never add these overlapping numbers to manufacture a larger opportunity.

The completed diagnostic kept the production collector unchanged, matched all
three captured streams and all 11,415 frame checksums, and used only the prior
6:25 public replay. See the [diagnostic report](PROFILE_2026-09-24.md) and its raw
evidence for measured totals and interpretation limits.
