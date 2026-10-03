# Cleanup implementation: event and rendering review

**Disposition: REQUEST CHANGES.** Review dated October 3, 2026. This is an
independent implementation review, not a repeat approval of the cleanup design.
The typed current-record path is substantially improved, but the legacy migration
can invent a wrong result owner, and an undisclosed owner still bypasses the new
damage-state timing path. The presentation schema export is also incomplete for
the approved portability boundary.

## Reviewed state and boundary

Baseline and unchanged HEAD: `981079bc0208dbb23f3ccc927347eef77fef4c30`.
The reviewed implementation is the uncommitted working tree, including new
`dnd/types/event_facts.py`, `game/export_schema.py` and
`game/world_binding_types.py`. No production or test files were edited by this
review. The only written artifact is this audit.

Read the repository instructions, current recovery requirements, test guide,
cleanup plan and previous event/render contract review. The cleanup plan SHA256
is `6fc466f87c66b5398af39655d27abbf7614389c19f548f851cd847f0edc34f58`.

Snapshot identity:

- SHA256 of `git -c core.safecrlf=false diff --binary
  981079bc0208dbb23f3ccc927347eef77fef4c30 -- dnd game`:
  `7b783bbb4f67d3944f73c10a7fc847ae42a34c43e42bee0b3ece99134153a3e3`.
- SHA256 of the sorted manifest of **377** current Python files under `dnd` and
  `game`, including untracked files: `544cfdc6453c03d5d00a855764398cc631f930901e34b6e55ca8f8cc063f7270`.
  Manifest rows are `SHA256(raw file bytes)`, two spaces, repository-relative
  POSIX path and newline, sorted by path. `__pycache__` is excluded.
- These hashes identify the implementation inspected; they do not imply manual
  inspection of every function in those 377 files.

The traced path is native resolution creation and sensory publication -> native
capture/compatibility -> permitted public facts -> causal index and reduction ->
attack/cast/standalone damage binding -> choreography -> sampling and persistent
media registration. Import/schema checks and exact instance-owner links were
included. Artwork and the paused server were not modified or audited for runtime
correctness.

## Findings

### ER1 — P1: legacy migration silently assigns callback retaliation to the incoming attack

**Introduced migration defect.** Locations:
`game/event_record.py:196–203` and `game/recording_compat.py:79–94`.

Both migration paths treat an immediate Attack/Spell parent as sufficient proof
that a damage request belongs to that action's resolution. It is not sufficient:
Fire Shield's real callback creates its retaliation request directly under the
incoming attack. The current producer correctly supplies an independent resolution
in `dnd/spells/evocation.py:5266–5268`. The baseline already had the same direct
parent relationship at `dnd/spells/roster_support.py:312–313`, without the new
resolution field.

Independent reproduction used the ordinary `FireShield` cast and native `Attack`
from the roster-support test setup with fixed dice `(15, 2, 3, 4)`. After capture,
each retained native payload was encoded, only the newly added `resolution_ref`
was omitted to exercise its legacy contract, and the payload was decoded and
passed to `upgrade_recorded_resolutions`. Output:

```text
retaliation original_is_incoming_attack False migrated_is_incoming_attack True owner_preserved False
attack damage original_is_incoming_attack True migrated_is_incoming_attack True owner_preserved True
```

This is not the malformed-parent case covered by
`test_ambiguous_legacy_callback_reports_the_exact_missing_owner`. It is an actual
historical parent shape. The migration returns success and changes the semantic
owner. The current attack binder then indexes retaliation together with the hit;
its different-recipient guard at `game/attack.py:301–302` rejects that combined
result set. The incorrect migration is reproduced; this downstream binder
consequence is established by source, not a separately rendered clip.

**Correction:** migrate only when retained evidence proves resolution membership.
Where old effective-handler/provenance records identify callback ownership, use
that evidence at the archive boundary. Where the accepted record cannot prove
the distinction, report the precise ambiguity and retain the original. An
Attack/Spell immediate parent must not be a universal ownership fallback. Apply
the same policy to native and public version-1 inputs; do not fix this with an
attacker/recipient reversal guess or a Fire Shield presentation special case.

### ER2 — P2: an unknown causal owner bypasses the compiled HP commit time

**Existing early-commit behavior left outside the new repair, with a new
ownership-dependent scheduling branch.** Locations:
`game/choreography.py:870–877`, `913–916`, `1070–1075`, and `1434–1437`.

`bind_damage` correctly supports a disclosed damage request/result whose
`resolution_ref` is absent, using their explicit parent relation. It returns
the bound result nodes and the authored damage timing. Choreography nevertheless
fills `result_placements` only when the request has a non-null resolution.
Unknown-owner results therefore fall back to the injury-start clock. The sampled
normal-HP override partly conceals the early commit; temporary HP is not included
in that override and becomes visibly stale relative to the shared HP/number
milestone.

Independent reproduction used genuine native events, followed by public JSON
encode/decode after closing/resetting the engine:

1. In `battlefield.visibility_doorway_closed`, put the observer at `(5, 7)` with
   40 normal HP and 5 temporary HP, and an undisclosed actor at `(8, 4)`.
2. Create an ordinary native `ActionEvent` for the undisclosed actor, advance it
   through execution/effect, and call the public recipient
   `receive_damage(7, DamageType.FORCE, source_entity_uuid=hidden.uuid,
   parent_event=effect.uuid)`. Complete and capture the action. The public root
   does not disclose the action fact, and both damage references are `None`.
3. Use the full default animation data, with the existing admitted
   `DamageContext.numberFrame` set to the valid frame `3`. Bind and sample the
   public lineage. No native result or causal relation is changed for rendering.

Observed output, with no presentation gaps:

```text
DamageTiming(start_ms=0.0, end_ms=1166.6666666666667,
             hp_ms=250.0, flash_ms=0.0, number_ms=250.0)
before:                      normal_hp=40 temporary_hp=5
compiled state at 0 ms:       normal_hp=38 temporary_hp=0
sample at 0 ms:               normal_hp=40 temporary_hp=0
sample at 249.999 ms:         normal_hp=40 temporary_hp=0
sample at 250 ms:             normal_hp=38 temporary_hp=0
```

The expected state before the 250 ms commit is `(40, 5)`, and at that commit it
is `(38, 0)`. Retiming the admitted damage recipe must not make one disclosed HP
pool commit early because the cause is private. Baseline choreography committed
applied facts at its generic effect clock too; this review does **not** attribute
the original early-HP design to this cleanup. The cleanup specifically promised
one placement for displayed committed state, and the new path does not cover
this supported privacy case.

**Correction:** register the timing against `standalone_damage.results` even when
its cause is unknown. Bind result identity and timing through the already proven
request/result relationship; no invented resolution reference is needed. Use
that same placement for the complete committed HP state and feedback. Verify
temporary as well as normal HP before/at the milestone, with current saved public
bytes and an undisclosed cause.

### ER3 — P2: schema export omits admitted data needed to reproduce semantic cue timing

**Incomplete new portability implementation.** Location:
`game/export_schema.py:19–21`; relevant consumers are
`game/animation_data.py:276–297` and `429–440`.

The exporter emits only `PlayerSequence`, `StudioDraftFile` and
`WorldBindingsSource`. An independent inspection of all three generated schemas'
`$defs` found these actual admitted types absent:

```text
DamageContext, DeathContext, AttackRecipe, VoluntaryMovementContext,
ConditionRecipe, BodyRig, RigTables
```

For example, standalone injury and ordinary attacks use `DamageContext.numberFrame`,
`bodyPlaybackSpeed` and rig clip timing to determine the HP milestone. These are
not optional draft fields: the loader validates them separately and the compiler
uses them when the spell draft provides no override. The export therefore cannot
describe the complete admitted input for the supposedly portable fact -> cue
contract. A TypeScript consumer would still need to recover additional Python
admission contracts by hand. This is a missing deliverable from cleanup step 6e,
not evidence that current Python rendering has stopped working.

**Correction:** export the existing passive, admitted schemas for the selected
action/context/rig/condition vocabulary and their binding documents, or a schema
manifest that references those actual owners. Keep a single definition of each
type and the current authoring language. Do not export Pygame draw commands,
duplicate runtime caches, or add a replacement presentation protocol.

## Improvements verified and remaining limits

- `game/attack.py` and `game/combat.py` now select ordered results by typed
  resolution, independent of whether a descendant has an art binding. The old
  one-applied-packet restriction is removed. The application match in
  `_bound_damage_timing` uses the resolution reference, not recipient identity
  and floating-point arrival equality.
- The public damage union discriminates request/result stages and committed
  damage requires both HP after-values. Application membership is an all-or-none
  passive record. Current native Fire Shield and later field exposure producers
  explicitly create independent resolutions; the ER1 problem is compatibility.
- Spatial membership producers name an actual published commit version, and
  reduction uses that version's index while retaining protection from nested
  movement overwrite. The previous first-version inference remains in the
  historical migration where that was the producer's established contract.
- The old formation-specific synthetic sensory-node splitting is removed.
  Native field installation now publishes before appearance damage. The focused
  straight/ring formation tests pass. This does not prove every coalesced sensory
  mutation: `_observed_commit` still reduces its source-version references to one
  lineage milestone, and this review did not reproduce every observation cause.
- Construction membership uses `construction_owner_uuid`; concentration
  admission uses the slot's `cast_lineage_uuid`. The four persistent-media
  policies share `walk_bound_timelines` and accumulated offsets. They remain
  separate policies, without moving native gameplay into the renderer.
- A fresh-process import of `game.export_schema` loaded none of
  `dnd.core.events`, `dnd.core.base_object`, `dnd.entity`, `dnd.actions`, `pygame`
  or `server`. The export's clean dependency boundary is real; ER3 concerns its
  coverage.

Independent test command:

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m pytest \
  tests/game/test_resolution_contract.py tests/game/test_wall_heat_presentation.py \
  -q --disable-warnings
```

Result: **15 passed in 22.94 seconds** with Python 3.13.12, sources on WSL
`/mnt/c`, and the full default authored bundles. The small native/replay probes
above ran through the same environment using stdin scripts. One first attempt
at the Fire Shield probe omitted the required `weapon_slot` argument and was
corrected before the reported result; that setup error is not a product finding.

The implementation's seven acceptance clips represent three scenes. They are
useful regression evidence, not comprehensive acceptance of callback migration,
unknown causes, repeated applications, coalesced observations or all lifetime
owners. No full suite or new gallery was run by this reviewer. The parent is
separately reproducing the original-only wall-media loader mismatch; this audit
does not classify that baseline fixture failure as a new runtime defect.

Implementation approval remains withheld until ER1–ER3 are corrected and verified
at their stated boundaries. Passing focused current-record clips does not close
the unsafe historical migration or the omitted privacy/timing path.
