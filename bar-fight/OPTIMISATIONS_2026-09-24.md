# Short replay optimisation experiment — 24 September 2026

The implemented combination reduced mean engine wall time from **119.050 to
99.548 seconds (16.38% less time)** in two candidate/control repeat pairs on one
385-second public Supreme Isthmus v2.1 replay. The simulation interval fell from
77.949 to 60.100 seconds; child CPU time fell from 171.393 to 142.773 seconds.
These are same-executable controls with the options disabled versus enabled.
This is not a measured fleet-wide gain over the installed official engine.

Tested source: `34a33cbed1edc4642595f34f47892b211f674705`, based on
`de69361239d8c8b1012dba3f5aa3122954ea4da3` (`2026.07.04`).
Executable SHA-256:
`c7e4d27047f9fb1dc33b98ba9a69ca418b2e979953c7d03a9ac35c4b3274347a`.

`ReplayPerformanceOptions` defaults to **0**. Its stable per-game mask activates
only in headless local replay. The test covered each independent bit:

| Bit | Candidate | In repeated combination |
| ---: | --- | --- |
| 1 | Skip unused model uniforms | Yes |
| 2 | Skip transform-upload dirty bookkeeping | Yes |
| 4 | Cache feature rotations | Yes |
| 8 | Reuse animation BFS queue | No |
| 16 | Cache animation key order | Yes |
| 32 | Partition path scans per movement layer | No |
| 64 | Skip headless texture-square assembly | No |
| 128 | Bounded offline replay packet scheduling | Yes |

The repeated mask was **151**. Offline scheduling requires SYNCCHECK and keeps
normal frame processing, bounded packet queues, checksum comparisons and
collector/unsynced updates. It changes pacing without skipping frames. The
CPU-target setting remained 0.75, but the offline mode deliberately changes the
processing budget and sleep policy; actual CPU utilisation is not fixed at 75%.

All **17** complete runs matched all three capture streams, every one of the
11,415 real simulation-frame checksums, and 112 footer statistics across 16
teams. One cold warmup supplied a verified private cache copy for each timed
run. Only the four actual repeat-stage runs form the primary timing comparison.
Screening controls drifted from 110.543 to 120.556 seconds, so small individual
effects remain inconclusive; the result validates the combination on this case.

All twenty production worker affinities were restored with unchanged PIDs and
restart counts. No production engine was replaced. Options remain disabled by
default pending broader short-replay coverage. This does not establish late-game
performance, and no medium/long games were used.

[Full report, harness and retained receipts](https://github.com/jehalvar/BAR-fight/blob/main/tools/replay_analyser/deploy/experiments/engine-optimisations-20260924/RESULTS.md).

OpenAI Codex assisted with implementation, review, testing and reporting. This
work targets the owner's BAR Fight fork; no upstream contribution was submitted.
