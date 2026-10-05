# Producer timing evidence implementation checkpoint

2026-10-05. This is an implementation receipt, not independent approval or full acceptance.

The existing calculation owners now retain passive equations for cast/attack release, launch, contact, damage start, HP callback/reentry, AreaReach and destruction floors; body/equipment joins; reaction alignment and interrupted prefixes; child sequencing; motion cursor spans/dwells/jump anticipation/recovery; prior injury admission, spatial response/sweep contact selection, life-body completion and departure floors. Existing clocks remain calculated in their original binders. `TimingEvidence` validates already-computed results; it does not schedule playback.

Exact application identities remain on repeated A/B/A delivery references and interruption travel candidates. A canceled action exports prefix evidence only, without the full action's HP/contact outputs. Fractional cutoff evidence uses two endpoints and a fraction so translating both endpoints preserves the equation. Reaction body evidence is translated alongside its existing cue clocks.

Movement records preserve native contributor identities, public nested groups, and authored hidden-boundary dwell. They do not infer hidden distance. Resolved movement durations retain distance, speed, authored duration/clamp and remaining-fraction measurements. Those measurements document the existing geometry calculation rather than introducing an expression interpreter. Flight trajectory sampling, curve interpolation, sprite modulo, opacity and marker carousel remain deterministic sampling code.

`bound_action_dependencies` retains cast, attack, body, equipment, condition transition, damage and entity lifecycle tables, including groups that have no drawable duration. Motion owns its table separately. Retained snapshot tables carry an optional admission UUID to distinguish updates without merging local producer indices across snapshots. External admission clocks are explicitly measured inputs, not invented graph edges.

Validation so far: 72 focused cast/attack/breach/evidence tests passed before this final extension; 44 body/equipment/interruption/evidence tests passed before motion extension. Scoped production Pyright passed. Final native interruption/movement/breach/evidence run passed 39 tests; a separate fresh run with new native movement/interruption dependency assertions passed 25 tests. Independent final source review remains in progress. Production edits frozen after final life-completion evidence annotation. Parent owns full-suite and corpus acceptance.

## Portal first-arrival correction

The full-suite portal boundary test exposed an actual ordering bug: the binder explicitly selected the arrival observer's first received actor snapshot at portal emergence, but the later generic observation floor moved that same snapshot to its ground-consequence commit. The arrival contact was drawable while the displayed actor map still lacked the actor.

The correction records the exact `(observation event UUID, actor UUID)` admitted by the existing endpoint selection and preserves its portal arrival clock through final observation dating. It retains the received already-injured HP unchanged, does not reveal an undisclosed departure, and does not advance other actors' observations sharing the same event. Duplicate registration of that exact arrival snapshot is removed. Ordinary observation cause floors remain intact. The existing portal regression's visibility/HP assertions are unchanged.

## Shield of Faith authoring correction

Support replay found a stale formation lead after the spell's cast motion changed: Attack5 release frame 7 is 583.333ms, but both recipient tracks still used a -666.667ms release offset. The start validator correctly rejected the resulting -83.333ms media start.

The final data-only correction uses the existing contact clock for these two recipient tracks, preserving their -666.667ms formation lead, with contact.delayMs=83.333ms. The current body releases at 583.333ms, the formation begins at zero, and application remains at media age 666.667ms (frame21 at32FPS). This preserves formation/application alignment instead of merely making the start nonnegative. No guard or runtime equation was relaxed. An audit of 32 negative-offset tracks under current modular motion assignments found no other negative baseline starts.

Final Shield of Faith validation: **43 passed** (entire support replay and animation volley files), including a new native-recipient assertion that Shield membership starts exactly at contact while the two tracks sample source frame21. This caught and removed an accidental duplicate condition delay during editing; the final diff changes only the two track clock fields and the contact delay. Production data frozen after that passing rerun.

Command: `PYTHONPATH=. UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest tests/game/test_support_replay.py tests/game/test_animation_volley.py -q` — **43 passed in 14.49s**. Negative-lead audit used the loaded catalog's `resolve_cast_recipe` and `body_clip` for the modular caster, evaluating each negative-offset track against its selected release/contact baseline: **32 tracks inspected, zero negative starts after correction**. This is a modular-assignment audit, not a claim about every alternative creature rig.
