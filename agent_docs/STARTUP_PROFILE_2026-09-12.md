# The eight-second smoke budget: measured profile

Measured September 12, 2026, on `codex/recovery-design` at `57fe2d6`.
Python 3.12.3, pygame-ce 2.5.8 / SDL 2.32.10, WSL, checkout and virtualenv
under `/mnt/c`. The user requested profiling before deciding what to change.
No production code, assets, test expectations or timing budgets were changed.

## What the failure measures

`tests/game/test_app_smoke.py::test_fresh_process_uses_the_same_public_entry`
times a whole fresh child process. That includes imports, SDL and assets,
native battlefield construction, startup/open/close capture and reduction,
twelve frames, application cleanup and interpreter exit. Its eight-second
assertion is separate from the subprocess's 90-second timeout.

This calls the older `game.app.run` map diagnostic. The current `python -m game`
entry runs the playable encounter through `game.encounter_play`. These numbers
are not a measurement of encounter startup or the animation gallery.

The supplied `frame_deltas=(0.1,)` bypasses the frame limiter; the supplied
`display_hold_seconds=0.0` removes the presentation hold. `asyncio.sleep(0)`
only yields. Post-settlement drawing through frame twelve is intentional:
the original vertical-seam plan also requires continued water/flame animation.
Stopping after three frames would measure different work.

## Unchanged-command results

All measurements ran serially. Each child used a fresh interpreter; filesystem
caches were not flushed, so these are not cold-disk measurements.

| Run | Whole process, seconds | Child user + system CPU, seconds | Result |
| --- | ---: | ---: | --- |
| Baseline 1 | 9.000 | 7.733 | Exit 0, settled |
| Baseline 2 | 8.897 | 7.575 | Exit 0, settled |
| Baseline 3 | 8.980 | 7.673 | Exit 0, settled |

Every run printed `E=42 R=42 D=42 terminals=3 settled=True` and passed the
assertion that `dnd.content_system.builtin` was absent. The median was 8.980s,
about 0.980s above the gate. This reproduces the timing failure without a
gameplay or settlement failure.

The final rerun of the existing pytest case also failed only its elapsed-time
assertion: 8.619s against 8.0s, with a successful child exit. The full pytest
invocation took 12.35s including collection; that is not the gated child time.

Two minimally instrumented import/run splits took 8.350s and 8.678s overall:
imports 3.603/3.705s; `run` 4.067/4.246s. This illustrates variation on this
host. Do not subtract stages from different invocations to manufacture a
breakdown.

## Where the time goes

Temporary wrappers timed existing owners without changing their arguments or
results. Three stage runs took 9.172s, 9.183s and 8.973s. All retained twelve
revision samples and the same settled cursors. The following **disjoint**
breakdown uses only the third run; it does not add nested profiler totals.

| Work | Seconds |
| --- | ---: |
| Import `game.app` and its dependencies | 3.897 |
| Native startup/open/close producer, including capture | 2.457 |
| Validate catalog JSON, paths and bindings | 0.948 |
| Decode 72 world assets and initialize surface cache | 0.439 |
| Draw all twelve frames | 0.348 |
| Reduce the three intervals | 0.0006 |
| Remaining application work, including SDL and cleanup | 0.126 |
| Process setup/exit and work outside the inner clocks | 0.757 |
| **Whole child process** | **8.973** |

Inside the producer, `build_battlefield` took 2.335s. All three captures together
took 0.049s. Inside drawing, water took 0.077s; this is already included in
the 0.348s. The first draw took 134ms, the second 30ms and subsequent draws
about 18–20ms. These dummy-driver frames do not establish interactive FPS.

Catalog validation used about 0.125s of CPU against 0.948s wall time; decoding
used about 0.114s against 0.439s. The call profile identifies filesystem work
in those paths. This is evidence of cost on this host, not a measured prediction
for another filesystem or machine.

A separate process-exit probe took 8.373s overall. `run` returned around 7.741s
after the inner clock began; the last registered exit callback ran at 7.747s.
Final generation-two GC then took 0.115s, collecting 33 objects. The rest of
the roughly 0.63s outside its import/run clocks remains process setup and
teardown overhead; it is not all GC or `pygame.quit` and was not decomposed
further. In the stage runs `pygame.quit` itself took only 27–31ms.

## Source-supported causes

The full `cProfile` run took 12.089s, including 11.386s inside the profiler and
22.4 million calls. That overhead is substantial. The following values rank
work and establish call counts; they are **not uninstrumented savings**.

1. **Imports construct many Pydantic models and load broad engine dependencies.**
   The profile records 587 model-construction calls, with 3.108s cumulative
   time under profiling. Import-time tracing independently measured `game.app`
   at 3.897s. The battlefield catalog's 0.980s includes authored item builders
   at 0.919s, environment builders at 0.590s and spell items at 0.541s. Those
   times overlap. Real chest/cannon scenarios use these builders; several eager
   routes reach spell modules. No single unused import was established.
2. **The 64-by-64 map constructs native movement-cost data for every tile.**
   The 4,096 `set_tile` calls lead to 16,384 `ModifiableValue.create` calls from
   `Tile.create`: walking, flying, swimming and burrowing. Each cost owns its
   static/contextual channels and base numerical modifier, with constraints
   added where needed. These are rule data, not emitted per-tile lineages;
   construction already suppresses tile events. Tile creation takes 3.187s
   under profiling, including 1.534s in those cost-graph factories.
3. **Catalog path validation repeats invariant filesystem work.**
   `game/assets.py::_contained_asset_path` resolves both the candidate and the
   identical `ASSET_ROOT` for each of 72 resources. The profile records 145
   `Path.resolve` calls overall; the 72 containment-helper calls take 0.778s
   under profiling. Root resolution alone is only part of that total.
4. **A native validator does repeated work even for incoming values.**
   `StaticValue.validate_value_source_corresponds_to_modifiers_target` constructs
   three lists before testing `is_outgoing_modifier` inside the loop. It runs
   66,000 times and takes 0.516s cumulative under profiling. This is a concrete
   candidate to measure while preserving outgoing/self-target validation;
   it does not justify replacing native value graphs with integers or shared
   mutable objects.

The selected diagnostic does not load Studio animation recipes or execute the
body-action/media lane. Its asynchronous scheduling and interval reducer are
not the source of the missing second.

## What follows from this measurement

The smallest candidate for a subsequent fix is resolving the asset root once
per catalog load, retaining each candidate's canonical resolution, containment,
file and dimension checks. Measure the actual saving with the unchanged smoke
command before claiming it solves the gate. The outgoing-value validator is
another bounded candidate if more work is needed. Import restructuring or a
different tile representation would be a larger design decision; this profile
does not establish a need for either.

Anti-slop review independently traced the tile/value ownership, event suppression
and original eight-second requirement. Anti-OOP review independently traced the
catalog/import boundaries and confirmed the repeated root resolution. Both
reviewers kept profiling serial and distinguished nested profile totals from
real elapsed time. No optimization was implemented in this profiling unit.

## Reproduction and raw evidence

From the repository root, the exact child workload is:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -c '
import sys
from game.app import run
run(frame_deltas=(0.1,), display_hold_seconds=0.0,
    max_frames=12, window_size=(960, 540))
assert "dnd.content_system.builtin" not in sys.modules
'
```

The original pytest case provides the parent wall-clock assertion. Add
`-X importtime` before `-c` for import tracing. The local diagnostic directory
`.runtime/startup-profile/` contains:

- `measure.py`, `measurements.json`: serial baselines, split timings, exact
  command arguments, stdout and return codes.
- `smoke.prof`, `cprofile-report.txt`, `importtime.stderr.txt`: raw call and
  import profiles. Read binary statistics with Python's `pstats`.
- `stages.py`, `stages-{1,2,3}.json`, `stage-processes.json`: wrapper source,
  individual wall/CPU spans and enclosing process measurements.
- `exit_probe.py`, `exit-process.json`, `final-gc.jsonl`: ordinary interpreter
  exit observations, without bypassing shutdown.
- `focused-test.txt`: final rerun of the existing timing assertion.

The raw diagnostics are ignored local artifacts. This document preserves the
measured conclusion in versioned documentation without adding runtime profiling
machinery or binary profiles to the codebase.
