# Current codebase integrity review — 2026-10-05

**Review only. No production or test implementation was changed.**

Reviewed committed HEAD `092e9daedaa7e0c65a54632b7085ab60ade642ca`, including existing code outside the latest changes. The initial working tree was clean. Evidence scripts and logs are preserved in [codebase-review-20261005](codebase-review-20261005/). Original execution outputs and exported schemas are under `.runtime/codebase-review-20261005/`.

## Assessment

The codebase has a sound retained-event/public-fact foundation, and current import-cycle and layer checks pass. It is not free of defects or duplication. Five concrete findings below concern native behavior, rendering composition, mutable publication or input validation; the remaining findings concern duplicated ownership, dependency direction and incomplete portable contracts.

The review does **not** justify a rewrite, another event system, a universal effect framework, or deleting systems simply because there are many files. Fix the concrete defects first and consolidate responsibilities into owners that already exist.

Scope: automated source inventory/exact-body comparison across 281 `dnd` Python files (154,764 lines) and 126 `game` files (34,551 lines), the existing architecture suite, and manual producer-to-consumer tracing of selected backend, client, AI, recording and authoring paths. Three independent review passes covered backend ECS/DAG, client anti-slop, and serialization/AI. This is a broad current-tree review, **not a claim that every line or every gameplay combination was exhaustively validated**. The paused server was inspected only to establish whether apparently duplicate code still has a consumer.

## Concrete findings

### F01 — P2: Shield can outlive its deadline while suppressed

**Owner:** `dnd/spells/abjuration.py:243–264`.

Shield's Turn Start Removal handler defaults to `runs_while_suppressed=False`. Antimagic Field suppresses the condition and its handlers, including its expiry. The buff has no independent finite duration supplying the missing deadline. If the field ends after that turn start, Shield becomes active again despite its deadline having passed.

**Reproduced:** install the ordinary ShieldBuff through `add_condition` (the same installation used by its reaction), cast actual Antimagic Field, start the shielded actor's turn, then end the field. Shield remains and reactivates. This probe does not exercise Shield reaction selection.

**Minimal correction:** allow this existing expiry handler to run while suppressed. Preserve its current TURN_START/EXECUTION semantics. Do not replace its clock with a new scheduler.

**Acceptance:** native suppression crossing the deadline, removal of the field, and no restored AC bonus or residual handler. Also retain the normal reaction/interception checks.

Evidence: `reproduce_spell_suppression.py` and `reproduce-spell-suppression.log`.

### F02 — P2: Guiding Bolt's spell mark is not classified as magical

**Owners:** `dnd/spells/evocation.py:2500–2517,2753–2764`; `dnd/core/base_conditions.py:712–714`; `dnd/spells/abjuration.py:3372–3374`.

The mark's class and actual construction omit `ConditionTag.MAGICAL`. Antimagic Field consults the existing magical-origin contract and therefore skips the mark. Its advantage remains active inside the field.

**Reproduced:** an actual deterministic Guiding Bolt hit followed by actual Antimagic Field reports `magical_origin=False` and active contributions inside the field.

**Minimal correction:** mark this spell-owned condition magical through the existing tag contract. Its existing modifier ownership already supports suppression. Do not add spell-name checks to Antimagic Field.

**Companion correction:** its separate expiry handler at `evocation.py:2587–2628` also does not run while suppressed. Correct that in the same change, so fixing the tag does not introduce Shield's stale-deadline behavior. The companion issue was demonstrated with forced suppression; it is not currently reachable through the field until the tag is fixed.

**Acceptance:** advantage suppressed inside the field; expiry still occurs at the correct caster boundary; exiting/ending the field after expiry cannot restore it; ordinary attack consumption still removes it.

Evidence: the native suppression reproduction above.

### F03 — P2: Cached body materials drop item-owned visual modifiers

**Owner:** `game/animation_draw.py:548–554,573–608`, especially line 589.

The normal render path passes item-owned condition modifiers into `item_material`. Barkskin/flowing film retain them. The cached Stoneskin/Petrified-style branch explicitly replaces them with an empty tuple before building the row. Cacheability is changing composition semantics.

**Reproduced:** a valid weapon opacity modifier changes ordinary rendering to transparent; with the Stoneskin ramp, modifier-on and modifier-off images become byte-identical. This isolates a renderer defect using synthetic admitted data; it is not a claim that a complete native Shillelagh/Stoneskin scene was captured. Shillelagh is a shipped consumer of this item-modifier channel (`game/data/condition-recipes.json:10404–10426`).

**Minimal correction:** keep the static body ramp cache, but preserve item-modifier ownership and dynamic timing when composing equipment. Do not include a continuously changing clock in an unbounded cache or silently drop the modifier.

**Acceptance:** combined Stoneskin/Shillelagh at multiple dates, correct glint behavior and removal of either effect, with existing alpha, shadow and cache-bound checks retained.

Evidence: `reproduce_material_modifier.py`, `material-modifier.log`.

### F04 — P2: Published AI worlds alias mutable retained knowledge

**Owners:** `dnd/ai/runtime/state_projection.py:109–118`; `dnd/ai/contracts/observation.py:141–284`; policy handoff at `dnd/ai/runtime/assignment.py:278–280`.

Publication copies dictionaries while claiming their fact values are immutable. The observation models are mutable Pydantic models with nested mutable collections. A policy receiving the published world can mutate retained AI knowledge, and earlier published worlds share those same values.

**Reproduced:** changing the public entity's HP and appending a condition changes retained knowledge to `999 ['fake']`. This establishes an ownership defect; it does not establish that an existing policy currently performs those mutations.

**Minimal correction:** detach mutable observation values at the existing publication boundary, or make those existing value contracts recursively immutable. Freezing only the outer world object is insufficient. Choose one approach; do not create another world model.

**Acceptance:** attempted mutations cannot change retained knowledge or a previously published world; actual new observed events still produce the next world correctly.

Evidence: `reproduce_ai_boundaries.py`, `reproduce-ai-boundaries.log`.

### F05 — P3: Compact action-source target indices admit negative indices

**Owner:** `dnd/ai/contracts/control.py:816–833`; compare executable-row validation at `327–334`.

The source decoder indexes the target catalog directly. `target_option_indices=[-1]` selects the last target rather than rejecting the input. The parallel executable-row path already enforces nonnegative indices.

**Reproduced:** validation succeeds and resolves the last catalog target. The normal encoder emits valid indices; this is a malformed cold-input validation defect, not a demonstrated native producer failure.

**Minimal correction:** enforce the existing nonnegative/in-range index contract in this decoder, sharing validation where appropriate.

**Acceptance:** reject negative/out-of-range indices and retain valid compact round trips.

Evidence: the AI boundary reproduction above.

## Duplicated ownership and structural debt

### F06 — P2: Live playback and recording duplicate presentation admission

**Owners:** `game/encounter_play.py:301–340` and `devtools/animation_review/record.py:374–432`.

Both bind motion/choreography, load media, register six lifetime families, build feedback/motion tracks and retain body history. Sharing the final frame sampler does not remove this duplicated preparation. A new lifetime can work in one entry point and be omitted in the other, weakening the recorder as evidence for the actual game. No current mismatch is claimed.

**Minimal correction:** an ordinary shared function for the existing admission sequence and passive returned values. Keep recorder pacing/assertions separate. No new playback manager, scheduler or queue.

**Related duplicate:** `game/body_history.py:44–54` manually recurses through nested movement/reaction timelines, whereas `game/choreography.py:2060` already owns `walk_bound_timelines`. Reuse the traversal; retain body-cut policy locally.

**Acceptance:** run the same retained multi-head history through live and recorder entry points at identical presentation dates; compare states and commands. Include reaction nesting, removal, teleport/visibility cuts and persistent media.

### F07 — P2: Deadline implementations have diverged

**Owners:** `dnd/spells/evocation.py:2028–2066,2587–2628`; `dnd/spells/conjuration.py:1079–1107`; Shield above.

The shared source-turn helper handles suppression, current-turn identity, and dead/departed-source cleanup. Other expiry handlers independently implement subsets. F01/F02 show this is more than cosmetic duplication.

**Minimal correction:** reuse the existing source-turn helper through an appropriate existing shared spell module where deadlines match. Preserve phase differences (Shield's EXECUTION timing) explicitly. Audit remaining expiry handlers against those semantics before consolidation.

**Do not consolidate unrelated clocks:** summoning's world-interval deduplication in `dnd/summoning/conditions.py:45–49` has different semantics and is not an unnecessary duplicate.

### F08 — P2: Weakly typed condition contribution contracts hide invalid results

**Owners:** `dnd/core/base_conditions.py:685–710`; `dnd/actions.py:2055–2076`; `dnd/monsters/traits.py:700–716,887–892`.

Condition hooks accept/return `Any`; action consumers recover types with `isinstance` and silently discard mismatched results. This disguises a missing shared passive contract rather than validating a declared union. The adjacent target-effect profile loop also lacks the `contributions_active()` gate used by bonus-damage discovery.

**Minimal correction:** move the existing passive profile/input definitions to an appropriate neutral owner and type the existing contribution interface. Apply the same suppression gate to both profile readers. No reflective registry or new effect language.

**Evidence limit:** the omitted suppression gate is a verified code inconsistency; no presently authored magical hit-save rider encounter was reproduced. Do not market it as an observed game failure.

### F09 — P2/P3: Entity/component boundaries still contain implicit policy

**Owners:** `dnd/entity.py:5387–7846`; `dnd/actions_functional.py:252–268`; `dnd/core/base_block.py:398–418`.

Entity owns action discovery, target/path policy and filtering, while the functional module delegates back into it. BaseBlock automatically discovers child blocks/values by reflecting over field shapes; a direct field and the same object inside a collection have different implicit ownership treatment.

**Correction direction, not an immediate rewrite:** incrementally extract pure discovery queries with explicit passive inputs, and make component composition explicit through existing indexes. Keep public behavior stable. Moving discovery wholesale into `actions_functional` and calling it back from Entity would introduce an import cycle; that is not an acceptable shortcut.

A narrow duplicate can be removed independently: `dnd/blocks/abilities.py:305–333` has a reflected UUID-to-field lookup alongside an existing direct block-index lookup.

### F10 — P3: Existing utility/composer logic is copied

- `dnd/spells/evocation.py:97–122` duplicates `dnd/spells/spell_utils.py:15–40` exactly. Reuse the existing LOS helper; no new abstraction.
- `_apply_lucky` is duplicated in `dnd/content/characters/barbarian_grants.py:241`, `fighter_grants.py:266`, and `sorcerer_grants.py:320`. The shared Lucky processor already exists. Share only the grant composition, passing the distinct source/binding provenance explicitly.

These are maintenance risks, not demonstrated behavior differences. The AST duplicate receipt also contains harmless shared signatures/abstract bodies; those are not blanket deletion candidates.

### F11 — P2: Schema export does not cover all currently admitted presentation data

**Owners:** `game/export_schema.py:22–30`; `game/animation_data.py:545,563,609–611`; `tests/architecture/test_presentation_schema_export.py:15`.

The 16 exported roots and all their definitions omit current production contracts including ConditionMediaDocument, ProjectileStorage, AuthoredProjectileAsset, ContentActionRecipe, MovementPresentation and InterruptionPresentation.

This matters for the proposed TypeScript client: movement actionPlaybackRates/referenceSpeedFeet and condition media fade/sequence/removal timing are consumed at runtime but absent from the exported input vocabulary. Exporting a recipe's asset reference does not export the referred media contract.

**Minimal correction:** export the existing separately admitted models/bindings, and validate representative real documents against them. Replace the fixed schema-count assertion with actual contract coverage. No second schema language. This is incomplete portability work, not a Python gameplay failure, and the earlier explicitly named schema additions were implemented.

Evidence: `inspect_schema_coverage.py`, `schema-coverage.log`, `exported-schemas/`.

### F12 — P3: Paused-server projection remains a parallel semantic owner

**Owners:** native `dnd/ai/runtime/knowledge_reduction.py:29–73` / `world_projection.py:27–120`, versus `subjective_projection.py:170–284,454–625`; consumer `server/agent_runtime/observation_journal.py:29–38,462`.

Remembered-entity stripping, health/condition/affinity projection, and tile/object projection are implemented twice. The native object path includes contact_passage/supported_by_uuid; the live-registry path's allowlist does not.

The latter still has a paused-server consumer, so it is not proven dead code. Keep native recorded facts authoritative. Explicitly retire or adapt the old consumer only when server work enters scope; do not revive it for this cleanup.

**Optional dependency debt:** native recording/projection imports CounterspellReactionEvent from executable `dnd.spells.abjuration` (`game/event_record.py:25`, `presentation.py:15`, `player_projection.py:13`). A passive event owner would be cleaner, preserving the wire discriminator. Native replay intentionally uses whitelisted event classes in passive mode, so this is not a proven replay side effect or a public cold-client blocker.

### F13 — P3: Historical evidence is coupled to mutable current state

Architecture run: **80 passed, 2 failed**.

- `test_manifest_shape_counts_ordering_and_authority`: evidence manifest refers to the absent root file `DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md`.
- `test_current_and_accepted_artifact_hashes_are_exact`: `current.icon_bindings` pins `1b2dfb4c…` but `content_data/ledgers/content_icon_bindings.json` now hashes to `a44f3546…`.

**Minimal correction:** separate immutable historical receipts (pinned Git objects or preserved artifacts) from current semantic checks; repair the historical plan reference. Reconcile the icon changes explicitly instead of blindly updating a hash or weakening assertions. Neither failure demonstrates broken imported art or a gameplay failure.

## Verified healthy boundaries

- Current import-cycle, function-local import and dependency-direction architecture checks passed. Do not claim the import DAG is generally broken.
- Native event recording uses a closed type registry and passive replay context; unknown types/incomplete records are rejected.
- Capture strips executable value graphs; committed condition state is used rather than a live condition lookup during cold projection.
- Versioned public facts carry explicit discriminators. Legacy damage ownership is rejected when ambiguous rather than guessed.
- Cold replay checks preserve registries and retained state after engine reset.
- Multiple concrete media samplers are not automatically duplicate systems: sheets, XYZ surfaces, depth-bearing volumes and connector geometry have different input semantics. No evidence here warrants deleting them wholesale.

## Verification and limits

Separate runs (overlap exists; do not sum as unique coverage):

| Run | Result |
| --- | --- |
| Full existing `tests/architecture` | 80 passed, 2 evidence failures described in F13 |
| `test_recorded_history`, `test_control_spell_replay`, `test_cantrip_replay` | 81 passed |
| `test_recorded_history`, `test_presentation_boundary` | 61 passed |
| `test_passive_event_replay` | 4 passed |
| Native Shield/Guiding Bolt/Antimagic probe | Defects reproduced; runtime reset in finally |
| AI publication/index probe | Both defects reproduced |
| Material composition probe | Modifier loss reproduced |
| Exported schema inventory | Missing contracts confirmed across roots and `$defs` |

This was not a full engine/client regression run or a visual review of every combination. Probes intentionally demonstrate defects and are not claimed as passing acceptance tests. No implementation fixes were made.

## Recommended cleanup order, pending implementation approval

1. Fix F01–F05 in their current owners, with narrow behavior regressions. Include Guiding Bolt's expiry companion with its magical tag.
2. Consolidate matching deadlines and live/recorder admission (F06–F07), preserving clocks and checking the same history through both entry points.
3. Complete existing portable schemas and type contribution boundaries (F08/F11).
4. Remove exact utility/composer duplication and address small explicit-composition opportunities (F09–F10). Keep any larger Entity extraction as a separately bounded change.
5. Repair evidence maintenance (F13). Keep the paused server outside this work (F12).

Independent review input: backend ECS/DAG, client anti-slop, serialization/AI. The parent review checked source references, evidence receipts and priorities, rejected the cyclic Entity-wrapper proposal, and retained qualifications about synthetic renderer inputs and the paused server. These are reviewed findings and cleanup proposals, not approval of an implementation that has not happened.

Final report review: backend ECS reviewer approved F01/F02/F07–F10 and the cleanup order; client anti-slop reviewer approved F03/F06/F11 and the qualified Counterspell dependency note. One schema-test line citation was corrected. Serialization/AI findings and replay results are supported by the separate reproducible receipts.
