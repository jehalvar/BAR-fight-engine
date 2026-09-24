# Deeper replay performance audit — 24 September 2026

The next useful changes remove repeated work while preserving the simulated
match. Raising the CPU target alone did not help the tested recording. This
follow-up traces the expensive regions identified by the existing profile and
finds narrower implementation candidates.

This is a source investigation, not a new benchmark. No engine changes, builds,
replay runs or production configuration changes were made for this follow-up.
Source references use fork commit `2fbc05c`, based on Recoil `2026.07.04`.
The fork is for BAR Fight's own use, with no upstream contributions planned.

## What the measurements establish

The previous complete 6:25 replay diagnostic measured these inclusive regions:

| Region | Seconds | What still needs separating |
| --- | ---: | --- |
| Simulation | 60.714 | Parent region, not total engine runtime |
| Feature pre-frame transforms | 10.746 | Piece snapshots versus object rotation conversion |
| Unit script engine tick | 9.248 | COB execution, animation sorting, arithmetic, traversal and callbacks |
| Path map updates | 8.286 | Sector updates, retessellation, path invalidation and scheduling |
| Unsynced update | 7.255 | Includes world preparation, of which uniform packing is only a subset |
| Draw | 5.332 | Rendering-side CPU work and callbacks |

Feature, script and path regions are inside Simulation; they must not be added
to it. Profiler overhead and overlapping worker timers prevent treating these
figures as predicted savings. Total engine wall time was 163.579 seconds, with
a deliberately cold archive cache. See the [profile and evidence](PROFILE_2026-09-24.md).

## 1. Cache feature rotation at the matrix write boundary

The previous audit proposed comparing unchanged matrix inputs. A narrower
design is now apparent: `CFeature` already owns a private `transMatrix[2]`
(`rts/Sim/Features/Feature.h:147`). Its two normal source write sites are
`SetTransform` (`Feature.h:85`) and `UpdateTransform` (`Feature.cpp:520`).

Add feature-specific rotation-cache validity, initially invalid. The existing
`preFrameTra.r` can hold the cached quaternion. Invalidate it on
every synced matrix write, and reset it on post-load. Recalculate with the
existing `CQuaternion::MakeFrom` only when the cache is invalid. Unsynced
draw-position updates must not invalidate it. This avoids the repeated matrix
return and matrix-to-quaternion calculation for unchanged features without
adding a nine-float comparison to each frame.
Set invalidation before any creation-frame `CondUpdatePrevTransform` call.

Continue saving every model piece's previous transform and copying the current
position at the same pre-frame boundary (`SolidObject.cpp:464`). A feature-only
method called by `FeatureHandler::UpdatePreFrame` can preserve the original base
implementation used by creation-frame `CondUpdatePrevTransform`. That base
method is nonvirtual: merely hiding it in `CFeature` would not cover both call
paths. Preserve the original default scale and all lazy piece evaluation.

Do not skip stationary features wholesale: Lua can move/spin features and change
their pieces outside the usual moving-feature queue. Do not move quaternion
evaluation earlier into setters without separately checking observable behavior.
Simulation sources compile into shared `engineSim`; a casual `HEADLESS` guard
there does not select a separate headless implementation.

Keep this distinct from the drawer's `Transform::FromMatrix` conversion: that
path extracts scale and normalizes matrix columns before converting rotation.
It is not bit-for-bit interchangeable with the simulation's direct `MakeFrom`.

Measure cache hit/miss counts and separate object rotation conversion from
piece snapshots. The whole 10.746-second region is not removable by this patch.

## 2. Reuse animation bookkeeping without changing animations

`rts/Sim/Units/Scripts/UnitScript.cpp:203` sorts each active script's animation
list on every tick. Its keys are piece, animation type and axis. A dirty flag
could retain that sorted order until adding an animation or removing one by
swap-and-pop changes it (`UnitScript.cpp:351,435`). Normal value updates need
not change the keys. Finished-animation removal at line 228 also swaps elements
through `VectorEraseIfAll`; it must mark ordering dirty. Deserialization and
callback-driven mutation also need coverage. Keep the dirty flag outside the
checksummed `AnimInfo`. Preserve the same comparator, checksum sequence and finish-callback
order; do not reorder animation execution as a side effect of an optimization.
Ordinary insertion searches for an existing key, but duplicate keys from restore
or unusual reentrancy require a fallback to the existing sort: `std::sort` is
unstable, so skipping it is not automatically equivalent for duplicate keys.

The same function constructs a fresh breadth-first `std::deque` of piece and
parent-transform pairs every tick (`UnitScript.cpp:232`). A reusable per-worker
buffer can preserve the existing traversal while avoiding repeated queue
allocation. Removing copied parent transforms is a separate candidate that
requires proving equivalent parent reads and root handling.

Do not replace traversal with the model's flat piece array: synced Lua can
reparent pieces without reordering that array (`LuaSyncedCtrl.cpp:3809`). Do not
disable animation: piece state affects gameplay, collision, Lua and weapon
behavior. `UnitScriptEngine.cpp:138` already parallelizes animation calculations
and handles finished-animation callbacks and aggregation of per-script checksums
in a deterministic serial phase. Per-animation checksums are computed inside
the parallel animation loop.

Instrument sorting, queue allocation, piece visits and actual transform work
separately. The measured 9.248 seconds covers much more than these candidates.

## 3. Stop inspecting other movement layers' paths repeatedly

When a sector requires retessellation, `PathManager.cpp:750` invokes
`PathCache::MarkDeadPaths`. That function walks all `IPath` entities and rejects
paths of other movement layers only inside the loop
(`rts/Sim/Path/QTPFS/PathCache.cpp:50,114–127`). This repeats for each affected
sector and movement layer.

A candidate is one frame-local path snapshot partitioned by movement layer,
built before the parallel map-update phase. Preserve the original registry
order within each layer, sector processing order, intersection tests and dirty
records. Each sector then checks only its own layer's paths. Start with a
temporary snapshot rather than a persistent index with many lifecycle hooks.

The current worker phase records dirty paths, with registry mutation/dirty
application after the barrier (`PathManager.cpp:832,842`). Confirm that lifecycle
boundary, including background tasks, before implementing the snapshot.
Count scanned paths, other-layer rejections, affected sectors and bounding-box
rejections, and time invalidation separately. Snapshot construction has a cost
and can lose on frames with little work.

Map updates already deduplicate dirty sectors and avoid some unchanged work.
Reducing their update frequency or sharing a map-only path cache could change
movement and combat. Preserve path decisions and their exact frame timing.

A secondary candidate is overlapping footprint reduction in `NodeLayer.cpp:137`:
the non-submersible path repeatedly scans neighboring cells to determine whether
a structure blocks a footprint. An exact integer prefix-sum or sliding reduction
could reuse these results, preserving step-of-two sampling, inclusive endpoints
and map-edge clamping. Keep the center-dependent submersible branch unchanged.
Measure this separately from collision-grid filling before attempting it.

## 4. Remove narrowly proven unused graphics preparation

The previous candidate still stands: guard `UpdateObjectUniforms` in headless
builds at `rts/Rendering/Common/ModelDrawerData.h:230`. It packs records for a
GPU buffer that is not created with headless GL capabilities. Preserve object
lifetime, user-defined Lua uniforms, draw flags/positions, transforms and
callbacks. This is a small initial patch with a clear boundary, but its expected
saving is unmeasured and only a fraction of the drawer totals.

The deeper trace found three additional graphics bookkeeping candidates:

- `ModelUniformsUploader::Update` reaches a null-buffer path which clears the
  entire dirty vector every draw (`ModelsDataUploader.cpp:47,348`;
  `UpdateList.cpp:17`). A headless early return can avoid that reset alongside
  the uniform-packing guard. Keep storage and Lua custom-uniform APIs intact.
- Every transform allocation calls `UpdateList::Resize`, which marks the whole
  growing storage dirty (`ModelsMemStorage.cpp:119`; `UpdateList.h:43`). Repeated
  equal-sized allocations therefore cause quadratic cumulative dirty-byte
  writes. Headless transform uploading already returns immediately
  (`ModelsDataUploader.cpp:200`). Suppressing this unused upload bookkeeping
  could reduce loading work; do not remove CPU transforms or valid offsets.
  This growth pattern is source evidence, not measured runtime dominance.
- `UpdateObjectTrasform` mixes GPU staging with lazy piece evaluation and
  `ResetWasUpdated`, which also resets interpolation state. A later patch could
  keep the once-per-frame gate, draw eligibility, piece evaluation and reset
  conditions while omitting only GPU staging. Deleting the whole function would
  discard shared state changes (`ModelDrawerData.h:159–199`).

These render-side files compile for the headless target with `HEADLESS`, so
narrow guards here are effective. Do not change shared dirty-list semantics
globally without proving buffer resize, reuse and rotation behavior.

Startup presents another candidate. `rts/Map/SMF/SMFGroundTextures.cpp:117`
allocates tile bytes, opens SMT files at line 145 and reads tile payloads at
line 174. The constructor then assembles square textures even with headless
GL stubs. The existing `HEADLESS` guard covers texture recompression, not all
of that loading/preparation.

The narrow first texture candidate is skipping temporary square buffers and CPU
tile copying before the stub upload (`SMFGroundTextures.cpp:619–624`). Preserve
square metadata and Lua texture API validation/return values. Broader payload
removal must handle persistent, streaming and Lua-requested extraction paths.

The retained diagnostic log has 4.413 seconds between the "Loading Map Tiles"
and "Loading Square Textures" messages. This interval is not a pure function
timer or a promised saving. A graphics-free tile path needs to preserve file
validation, metadata and Lua-visible behavior. `CFileHandler` loads the entire
archive member when opened (`FileHandler.cpp:92–103`), so header-only reads through
that constructor still pay archive extraction. Investigate it separately from
uniform packing. Tile assembly here is block copying, not DXT decompression.

## 5. Consider an explicit offline replay scheduler

A larger option is a mode restricted to headless local replay analysis that
feeds a bounded number of recorded frames ahead, then services the existing
client, callbacks and output. It would retain every game frame and recorded
command while decoupling throughput from viewer pacing.

Today the replay reader waits for replay time (`DemoReader.cpp:125`), the server
advances that clock from wall time and speed while holding it when the client
is a second behind (`GameServer.cpp:808`), and the client has a draw-related time
budget (`rts/Net/NetCommands.cpp:245`). Additional server speed limits and
headless sleep were described in the [first audit](SOURCE_AUDIT.md).

Two useful exclusions from this deeper pass:

- The local host already returns before applying the network smoothing buffer
  (`NetCommands.cpp:169`); disabling that setting is not a general host fix.
- At the requested 60x speed, the per-frame headless sleep is positive only when
  the measured frame takes less than about 0.556 ms (`Game.cpp:1811`). Its maximum
  requested sleep is about 0.278 ms per frame at that setting. Actual scheduler
  oversleep and how often this occurs need measurement.

Do not use the old skip route as a shortcut. `Game::StartSkip` is disabled with
a desync warning (`Game.cpp:2014`), and server `SkipTo`/`SendDemoData` change sync
bookkeeping. An offline mode must preserve recorded order, all frame checksums,
real GameOver, LuaUI collection, bounded queues, cancellation and final flushing.
This is a larger architectural experiment, not the first patch to deploy.

First add aggregate counters for queue-empty time, budget exits with pending
frames, replay-clock holds, binding speed caps and actual sleep. Avoid per-frame
logging and shared server-thread use of the existing profiler recursion map.
Those counters determine whether scheduling is worth changing at all.

## Startup and throughput controls

Production already seeds validated archive caches. Give each experimental
binary its own correctly identified warm cache for steady-state comparisons;
measure cold starts separately. Never count the earlier custom cold-cache
disadvantage against the official warm-cache control as a new optimization.

A persistent worker process is possible research, but existing `SpringApp::Reload`
destroys the game, Lua, network and much simulation state (`SpringApp.cpp:758`).
It does not automatically make replay startup free. Proving reset completeness,
bounded memory and identical second/subsequent replay results is more involved
than removing specific redundant work from fresh-process jobs.

## Recommended experiment order

1. Establish matched warm-cache controls and add only the counters needed to
   isolate the proposed costs. Keep diagnostic runs separate from timing runs.
2. Test the narrow headless uniform-packing/reset guards as small changes, then
   unused transform-upload dirty bookkeeping separately.
3. Test the feature rotation cache, then reusable animation queue and conditional
   sorting as separate changes.
4. Test per-layer path snapshots if measured invalidation cost justifies them.
5. Investigate headless texture startup and offline scheduling as separate work.

For each change, use complete short public replays, compare every frame checksum,
all three captured streams, GameOver and footer statistics, and repeat candidate
and control with the same binary base, assets, collector, CPU budget and cache
conditions. Measure engine wall time, loading, simulation and CPU-seconds.
Evaluate completed replays per hour at a fixed worker count before a fleet
rollout: using more threads for one replay can reduce overall throughput.

There is no defensible percentage speedup yet. These are concrete places to
test, and the validation distinguishes faster execution from changed data.
OpenAI Codex assisted with this source investigation and documentation.
