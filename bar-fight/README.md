# BAR Fight replay analysis fork

This branch provides a versioned place to investigate engine costs while
reproducing the original match and keeping every captured measurement.

## Ownership and purpose

The owner confirmed on 24 September 2026 that this fork is for BAR Fight's own
replay analysis. Develop and publish changes in `jehalvar/BAR-fight-engine`;
there are no plans to contribute them upstream. Do not submit upstream pull
requests, issues or discussions for this work unless the owner explicitly
changes that instruction. Upstream remains a source for reference and updates.

AI-assisted development is part of this fork's workflow. The retained upstream
`AI_POLICY.md` describes outside contributions to Recoil; it does not add an
upstream-submission requirement to work in this fork. Preserve the engine's
licensing, attribution and replay correctness checks.

## Base and current implementation

- Upstream: `beyond-all-reason/RecoilEngine`.
- Base tag: `2026.07.04`.
- Base commit: `de69361239d8c8b1012dba3f5aa3122954ea4da3`.
- Working branch: `bar-fight/replay-2026.07.04`.
- Previously tested engine change: the headless replay-only
  `ReplayCpuUsageTarget` option, default 0.75 and bounded to 0.75–0.95.
  It applies only when `SpeedControl=2` and a demo is playing.
- Eight additional experiments are controlled by the `ReplayPerformanceOptions`
  bit mask (default **0**, all disabled). They activate only in a headless,
  local replay. They cover uniform packing, transform upload bookkeeping,
  feature rotation caching, animation queues/order, path scan partitioning,
  map texture assembly, and offline replay packet scheduling.
- Production still uses its separately installed official engine. This fork
  does not install itself or change replay-worker configuration.

The same source change was compiled in a separate source-build experiment.
Eight complete runs of one 6:25 public replay matched all captured streams,
11,415 per-frame checksums and 112 footer measurements. Raising the target alone
did not improve processing time. This is compatibility evidence for that
experiment, not a speed claim or a validation of every future fork commit.

[Full CPU-target experiment and receipts](https://github.com/jehalvar/BAR-fight/blob/b98b826/tools/replay_analyser/deploy/engine-short-target-results-20260924.md).

## Direction

Use [the source audit](SOURCE_AUDIT.md) to choose changes based on observed cost.
First distinguish simulation work, unsynced presentation work, loading, and
pacing delays. Change one thing at a time. The initial diagnostic uses the
existing engine profiler; a profile-enabled run is not an unbiased speed
benchmark because measuring adds overhead.

The completed [short diagnostic](PROFILE_2026-09-24.md) identifies feature
pre-frame transform work as a priority for investigation. The narrow presentation
candidate is skipping GPU uniform packing that cannot be uploaded in headless
mode. Archive-cache maintenance and replay pacing are separate candidates.
Their proposed implementations and limits are in the audit.

The [deeper source investigation](DEEP_REPLAY_AUDIT_2026-09-24.md) follows these
regions into feature cache invalidation, animation bookkeeping, path invalidation,
headless texture loading and an optional offline replay scheduler. Its candidate
designs are now implemented behind independent switches. The bounded experiment
uses one short public replay, same-executable controls and exact capture/checksum
comparisons. See [the experiment harness](https://github.com/jehalvar/BAR-fight/tree/main/tools/replay_analyser/deploy/experiments/engine-optimisations-20260924)
for methodology and retained results. These options remain experimental and off
by default; implementation alone does not establish a speedup.

The completed [optimisation experiment](OPTIMISATIONS_2026-09-24.md) found a
16.38% mean wall-time reduction for mask 151 in two repeated pairs on one short
public replay. All 17 complete runs retained the same captured data and frame
checksums. Small individual effects were inconclusive, and production was not
changed. This is narrow experimental evidence, not a fleet-wide speed claim.

The subsequent [six-replay installed-official comparison](https://github.com/jehalvar/BAR-fight/blob/ce6a4de/tools/replay_analyser/deploy/experiments/short-official-20260924/RESULTS.md)
completed six official reference warmups and 36 counterbalanced timed runs on
public Supreme Isthmus v2.1 games lasting 194–631 seconds. All captures passed
full validation; the 36 timed runs exactly matched their official reference
streams and every-frame checksums. Mask 128 reduced summed replay-mean engine
wall time by 11.39%, and mask 151 by 13.72% (14.51% less CPU). Those are comparisons
against the installed official executable, with two timed repeats per treatment
and matched private warm-cache bytes. They do not establish fleet throughput or
long-game performance, and production routing remains official.

The completed [optimized profile](OPTIMIZED_PROFILE_2026-09-24.md) rechecks the
remaining mask-151 startup and simulation costs. Independent raw streams,
every-frame checksums and footer validation passed. Archive scan/cache rewriting
took 0.232 seconds; path initialization remained a much larger region. The
diagnostic is excluded from latency comparisons and selects no new source change.

## Replay compatibility and build identity

Keep the base release, fork revision, exact patch set, toolchain, executable
SHA-256, native version strings and collector SHA-256 with every result.
Never overwrite the official engine install or label an experimental executable
as an official release.

A Git checkout containing fork commits normally produces a development version
string. Verify its native `--version` and `--sync-version`; do not rewrite capture
metadata or bypass a mismatch to make the validator accept it. The existing
source-build harness accepts only explicitly pinned experimental provenance.
Each recorded engine version needs its own matching base and validation.

Preserve synced floating-point settings, frame order, replay error detection,
LuaUI collection, and real GameOver. Keep archive identity/checksum validation.
Do not skip simulation frames, substitute pathfinding, or disable LuaUI.

## Validation procedure

1. Build an isolated headless executable using the pinned upstream toolchain;
   retain `STREFLOP` and synchronization checks. Record build provenance.
2. Run the official control and same-build control on the same complete short
   public replay, with identical collector, inputs, thread count and CPU budget.
3. Compare the three captured JSONL streams by values, types, fields and ordered
   records; ignore only JSON whitespace and object-key ordering.
4. Compare every real simulation-frame checksum through GameOver, plus the
   unchanged production validator and all available replay footer statistics.
5. Repeat the control and candidate. Report loading, simulation interval, total
   wall time and child CPU time separately, with cache conditions and all failed
   attempts. A short-game result does not establish late-game fleet throughput.
6. Restore temporary CPU reservations and retain evidence. Production rollout
   is a separate operation after a demonstrated benefit and appropriate coverage.

The present investigation stays on short replay inputs. It does not silently
extend the workload to medium or long games.

## Attribution and upstream

OpenAI Codex assisted with the source audit, experimental scheduling patch,
profiling tooling and reports. Recoil remains the upstream project; its original
licensing and attribution are preserved. No issue, discussion or pull request
has been submitted to upstream as part of this work, and none is planned.
