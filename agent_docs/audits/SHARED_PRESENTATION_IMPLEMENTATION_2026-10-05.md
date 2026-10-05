# Shared presentation implementation and acceptance

**Later user decision, October 5:** the narrative feature has been removed.
Narrative/text UI, fallback outcome formatting, transcript export/schema and
narrative-only tests described below are historical. The existing combat log
is restored; shared graphical binding, timing evidence and catalog work remain.

2026-10-05. **Implementation complete; final validation and independent source reviews passed.** Implements the
[approved plan](../SHARED_PRESENTATION_AND_TEXT_RENDERER_PLAN_2026-10-05.md).

## Delivered structure

| Plan lane | Implementation and evidence |
|---|---|
| A: full mappings | The original 1,367-row/24-family inventory, 53 catalog fields and concrete schema-fit receipts remain the denominator. Enumerated source coverage is not pixel approval. |
| B: evidence | Existing choreography/motion retain exact state commits, native application identities and discarded nested group provenance. Review trace v2 includes omitted cue families and shared narrative. |
| C: materials | One effective palette selection drives layer loading and cache identity; exact swaps, original-sheet overrides and accepted geometry are preserved. |
| D: timing | `timing_evidence.py` records operands/results at existing producer equations. `presentation_timing.py` projects them without scheduling playback again. Cast, attack, AreaReach, body/equipment, interruption, movement, standalone damage/life, portal and condition owners are covered. |
| E/F: actions and motion | Existing native grouping/reducer remains authoritative. Facts/logs narrate outcomes independently of body selection. Phases resolve their own observer snapshot; hidden dwell and canceled gestures do not invent visible movement. |
| G: retained/world | `presentation_retained.py` composes the six original lifetime owners. Retained snapshots carry admission identity because reacquisition can recreate a local table. World updates remain atomic. Known-state inspection is separate from witnessed occurrences. |
| H: catalog | `presentation_export.py` exports the actual typed effective catalog. Logical IDs stay unchanged; actual filesystem paths become package-relative. No alternate spell registry or executable JSON language. |
| I: text/UI | `presentation_text.py` uses finite public-fact/log and selected-motion descriptions; `text_replay.py` consumes saved permitted sequences without Pygame. F4 cycles Scene/Split/Narrative; F3 selects detailed inspection; wheel scrolls text. |
| J: consolidation | Pure bindings no longer import raster modules. Drawing moved to bounded adapter modules. Production JSON Schemas, authoring instructions, independent reviews and final test evidence accompany this report. |

The new draw modules (`concentration_draw`, `stationary_draw`,
`spatial_response_draw`, `mechanism_projectile_draw`) separate existing graphics
functions from pure binding. `scene_actors` and `wall_profile` isolate shared
selection/math. These are extracted responsibilities, not extra executors.

No gameplay rule, new artwork, surface chemistry, AI architecture or networking
implementation belongs to this change. Backend diffs already present from the
earlier condition work are not claimed as renderer features.

Current four-camera replay evidence: three cases, 66 passing recorder checks,
zero reported gaps, using the existing public inputs. Sampled frames reviewed:
Magic Missile impacts at 1.5s, flight at 2.5s, Wall of Fire at 2s, plus actual
Scene/Split/Narrative screenshots. These samples do not certify every frame.
The local [review page](http://127.0.0.1:8768/shared-presentation-20261005/index.html)
links the recordings and all successful headless transcripts.

## Deliberate contract boundaries

This is a portable catalog, causal evidence and narrative boundary, not a
TypeScript renderer. Geometry, sampling, pixel occlusion and existing family
binders remain pure/functional Python where appropriate. A future client must
port those operators; exported data does not execute them.

Timing validation checks each producer table's dependency order, finite values,
operand references, equations and offsets. Measured external anchors remain
explicit. It does not claim a second globally closed scheduling graph. Both
reviewers preferred preserving the one existing scheduling path over adding a
redundant interpreter. The plan's provisional global-graph language is resolved
by this explicit boundary.

Semantic descriptions use public names and selected phase/attachment meaning.
Technical asset IDs/build names are not translated into invented art descriptions.
Unlabelled fixed-rig motions and replacement sheets remain intentionally silent
about their geometry. Gameplay outcomes still appear. Some archived public packets already contain
anonymous combat-log wording (for example repeated “Unknown gains Bloodied”
entries with distinct native UUIDs). Those received logs remain unchanged; the
client does not infer missing actors or merge distinct occurrences. See the
[selected-owner dispositions](rendering-readiness-20261005/selected-owner-semantic-dispositions.md).

## Validation record

- Current permitted-packet corpus: 300 successful strict JSON replay round trips,
  with Pygame imports explicitly rejected. Two additional historical packets
  reference deliberately removed Produce Flame hurl; four current replacement
  inputs are included in the successful set. This is semantic/timing replay, not
  fresh pixel validation of 300 clips. Final rerun after the selected-media descriptions has the same result.
- Scoped final timing/narrative/lifecycle run: 48 passed. Phase-local disclosure
  correction: complete narrative file, 17 passed.
- Complete game/review-tool typing: **zero errors, zero warnings** after the
  final consumers and passive-import corrections.
- Engine/architecture/AI/progression/packaging complete run: 3,136 passed, one
  schema-export contract failure. Updating the expected 16 schemas to 18 exposed
  an unnecessary import of native event machinery through passive reexports.
  Those imports now point to their existing passive owners; the corrected cold
  schema/headless pair passed two checks. A stronger shared-import guard also
  passed, rejecting native execution imports. Complete architecture rerun: **83 passed**.
- Full game coverage: **3,653 tests**, executed as a completed 1,010-test file
  prefix and three remaining partitions. Partition results were 1,014 passed / 5
  failed, 782 passed / 1 failed, and 822 passed / 19 failed. All **25 failures are
  closed**: 20 stale Fear/Hold/Web/Slow assertions omitted accepted overhead
  markers; one portal observation timing defect; four Shield of Faith authoring
  cases. Complete affected-file reruns passed **85 checks** (16 Fear/Hold,
  10 Web, 5 Slow, 11 portal, 43 support/volley). Marker repairs preserve exact
  body-layer checks and independently check their head markers. The serial
  invocation was interrupted only after the completed file prefix; the boundary
  file was rerun in a partition. These are combined coverage evidence, not a
  claimed single clean invocation. Exact selections and counts are in
  `.runtime/shared-presentation-20261005/test-shards.json` and `validation.json`.
  The affected narrative/UI files also passed 22 checks.
- The suite exposed a real portal visibility regression: a first-arrival
  observation was delayed to the later ground-consequence commit. The exact
  received actor snapshot now appears at the already-authorized portal arrival
  clock, with its received HP unchanged. All **11 portal tests passed**, retaining
  the original boundary assertions; independent ECS review approved the fix.
- Shield of Faith retained an old formation lead after its body assignment
  changed. Existing contact-clock authoring now keeps formation at time zero,
  hand release at 583.333 ms, and application at 666.667 ms / media frame 21.
  Condition delay remains zero. All 32 negative-offset tracks under current
  modular assignments were checked: no other negative baseline starts remain.
  Both independent reviewers accepted this bounded data correction.
- Final logs, source hashes and the machine-readable run/repair record are saved
  under `.runtime/shared-presentation-20261005/validation-logs/`,
  `source-snapshot.json` and `validation.json`. Final `git diff --check` is clean.
- Actual Scene/Split/Narrative captures are in
  `.runtime/shared-presentation-20261005/ui-final/`.

Final source review receipts:
[anti-slop](rendering-readiness-20261005/final-implementation-antislop-review.md),
[ECS/DAG/disclosure](rendering-readiness-20261005/final-shared-presentation-ecs-review.md).
The passive prior-HP label and phase-time visibility findings were corrected.
Finite selected-media descriptions, stable nested-cue identities and direct passive imports have also received independent review. The final [portal/support anti-slop receipt](rendering-readiness-20261005/final-portal-support-antislop-review.md) and appended ECS receipt close the last suite findings.

Historical 298-clip and 50-clip galleries remain historical. Full source coverage,
headless replay, regression checks and sampled actual UI captures are separate
evidence claims. No commit was requested.
