# Narrative fallback and authored motion review

2026-10-05. Independent source review of `presentation_text.py`, `presentation_timing.py`, `animation_types.py`, `animation_data.py`, authored root rig descriptions, and narrative tests. No production edits or test execution by this reviewer. Parent's test results remain separate evidence.

## Verdict

The bounded architecture is appropriate: finite fact fallbacks, existing projected logs, passive description fields on existing rig/clip records, phase-qualified occurrence identity, and a normalized read-only view of existing binder clocks. No spell-specific prose registry or new gameplay execution path was introduced. **Two concrete implementation corrections are required before bounded approval.** Full semantic/text-renderer completion is not established by this checkpoint.

## Required corrections

1. **Movement suppression is broader than its causal owner.** `fact_text` drops a MovementFact whenever any StepFact appears anywhere in `all_nodes`. A different actor's reaction movement, an unrelated grouped move, or even an uncommitted step suppresses the legitimate root fallback. Limit this to committed steps in that movement's own causal descendants, with matching actor. Do not infer ownership merely from actor identity across the whole head. A regression should include unrelated and rejected steps alongside a valid root move.
2. **Layer semantics can describe the wrong artwork.** `gesture_entries.describe` selects `meaning.layers[layer.category]` even for a `StudioActorLayer.sourceSheet` override. Graphics explicitly loads that override in place of the category's original sheet. Therefore an isolated replacement export may be described as the original Effect3 cage/skeleton or Magic wisps when its actual art differs. Original-sheet descriptions must be conditional on the original sheet being selected; an override needs its own explicit description or must omit the layer-specific sentence. Do not infer semantic equivalence from palette/category alone.

## Positive boundary checks

- Same-resolution DamageRequestFact log prevents duplicate applied-damage fallback; matching uses typed resolution identity, not strings or target equality.
- Canceled attacks/spells/actions are handled before successful-action wording.
- Condition refresh and INTERNAL facts stay silent; object removal wording does not invent smash/damage.
- Applied damage uses the actual result amount; HP-zero does not fabricate death.
- Selected body description is rig-local; missing fixed-rig description is omitted rather than borrowing humanoid semantics.
- `event_uuid + phase` preserves gesture/result without weakening native occurrence identity.
- Inspection marks retained unknown-current state as “Last known” and uses admitted map membership; it does not reconstruct neighboring cells.
- `presentation_milestones` exposes clocks, not a new scheduler or rewritten state reducer. Reconciliation remains distinguished from committed occurrence.

## Remaining semantic coverage — do not claim complete

- Attack fallback omits known hit/miss outcome; spell applications are always silent when unlogged, including any legitimate application whose only outcome is membership/suppression. This is conservative but incomplete.
- SpatialEffectStateFact considers only trap state/pressed changes. CREATED, REMOVED, TRANSFORMED and FOOTPRINT_CHANGED can have unchanged/null trap state and disappear from text. They need exact operation-driven dispositions, especially future surface transitions; no inferred rules are needed.
- ItemChargeFact and EquipmentFact currently have no fallback. Inspection lists visual gear but not controlled inventory quantities, charges, item-effect state, or active loadout designation. Saying “inspection covers these” would overstate implementation.
- ItemEffectChangeFact looks up floor objects only, so held items often become “An object”. Correctness is conservative, but owned-item names require existing permitted controlled-item state.
- Condition suppression/count/size/energy state is not described; inspection lists the condition name alone. A suppressed buff currently reads indistinguishably from an active one.
- Turn/round end edges remain silent. This can be an intentional compact-log choice but must be declared rather than counted as narrated coverage.
- Authored gestures describe the whole selected motion at its start. They do not yet provide phase-specific gather/release/recovery sentences, hand sockets, exact material colors, delivery descriptions, target impact, persistent layer lifetimes, or cancellation of future gesture clauses. These remain distinct from having a motion description attached.
- Gesture handling covers BoundChoreography actions/body actions; MotionTimeline legs are not described by selected movement rig/clip semantics here.
- Fallback name lookup uses the group's `before` state. This avoids latest-state leakage but newly disclosed/spawned/changed-name entities within the head use generic or stale labels. Complete per-commit descriptive identity requires the permitted state at that occurrence, not final state.
- The new `MotionDescription.layers` keys are string categories; completeness/override validation is not enforced by schema. Source observations alone do not establish all selected combinations have accurate runtime descriptions.

## Focused acceptance evidence still needed

Add concrete tests for the two corrections; preserve same-resolution/result-only damage checks and both observer projections. Also exercise canceled action, explicit spatial lifecycle with null trap states, summoned actor absent from before-state, and repeated identical text across distinct applications. Existing eight-direction artwork and whole-gallery visual acceptance are not asserted by this source-only review.

## Bounded re-review after corrections

Both original blockers are corrected in source: movement checks only uncanceled, committed, same-actor causal descendant steps; override `sourceSheet` layers no longer inherit original-sheet prose. Interrupted and canceled action gestures are omitted rather than claiming their complete sequence occurred. Attack outcomes, operation-driven spatial lifecycle text, controlled-item name lookup, quantity/charge inspection, active loadout and condition suppression/count descriptions close the corresponding earlier gaps partially or fully.

One newly introduced consistency correction remains: controlled-inventory inspection rows need the same `Last known:` prefix as their retained unseen owner. Currently the actor row is qualified but its separate `X carries item` rows assert a current fact. Reuse the existing visibility result; no new inference/system is required.

Subject to that small correction and focused regressions, the bounded fallback/description implementation is approved by source review. This does not certify per-phase gestures, override-material prose, complete item-effect descriptions, newly admitted per-commit names, movement clip semantics, all application-only outcomes, or full-plan portability. Previously listed limits remain except where explicitly closed above. No fresh test execution or visual acceptance was performed by this reviewer.

## Current correction acceptance and approved-plan completion blockers

Re-read current source after the next request. The remembered inventory prefix is now correct; inventory detail is optional, and default terrain/field summaries count cells while detailed inspection preserves their exact coordinates. Committed descendant matching and sourceSheet exclusions remain present. **The bounded corrections are approved by source review.** This approval is not contingent on inventing additional architecture.

The following are concrete remaining semantic gaps against the approved plan, rather than speculative new requirements:

1. **Resisted shove loses its outcome in fallback.** `ShoveFact.contest_success=False` currently says “attempts shoving”, indistinguishable from unknown (`None`). Plan §7 explicitly requires resisted shove outcomes independently of animation. Use distinct failed/succeeded/unknown wording and test all three values with no log.
2. **State-change semantics are inspection-only, not event occurrences.** `ConditionChangeFact.CONDITION_STATE_CHANGED` returns None. Inspection now identifies suppression, but the transcript cannot distinguish suppression onset, restoration, duplicate-count consumption or size change as witnessed transitions. Plan §5 explicitly distinguishes suppression, expiration, consumption and quiet reacquisition. Compare only committed permitted before/after values; do not narrate changes discovered merely through reacquisition as if their cause was witnessed. The six retained maps now export clocks in `text_replay`, but those clocks are not themselves occurrence prose or evidence of a native event.
3. **Per-occurrence participant identity is still group-before.** `bind_narrative` passes one `choreography.before`/`motion.before` to all fallback names. A creature created or newly disclosed during a nested head has no name there even when the actual event commit supplies it; renamed/changed objects can retain the wrong earlier label. Plan §4 requires participant values at the evidence cut. Reuse the bound committed public state/observations; never substitute final/latest state. Native projected logs already carry event-time wording and need no change.
4. **Effect semantics cover only selected original modular body accents.** The authored `MotionDescription` is consumed for selected body clips and original Magic/Effect layers. Delivery effects, attachment descriptions, condition markers, persistent field appearance, world transitions and fixed-rig actions without description remain unnamed visual behavior. Plan §4/§7 demands selected authored effect meaning and finite outcome semantics across the actual coverage denominator. Populate existing owner metadata only where real descriptions are needed; this is not permission to invent a parallel spell registry. SourceSheet omission is correct but leaves an explicit description gap for those selected exports.
5. **Body text has one whole-motion phase and motion legs have none.** `gesture_entries` only consumes BoundChoreography action/body entries and emits the complete authored body sequence at its start. `NarrativeEntry.phase` supports result/gesture only. This does not yet express the plan's witness attempt/release/contact/return relationships or interrupted prefixes, and selected MotionTimeline flight/window/step gestures are absent. Do not expand every frame into text: identify meaningful phases already supplied by the shared milestone owners; interrupted omitted gestures are currently conservative rather than complete.
6. **Unlogged application-only outcomes are suppressed wholesale.** Every SpellFact with application membership returns None, even if no damage/save/condition child supplies an outcome. This needs a corpus-backed disposition for the actual application variants: outcomes with real child coverage can stay silent, but granted suppression/membership-only outcomes cannot be counted as narrated merely because the spell family is handled. Preserve repeated application identity; do not add one sentence per technical node.
7. **Detailed authored text is not exposed in the live UI.** `encounter_play` renders `row.compact` only; `show_debug` toggles state inspection detail, not `NarrativeEntry.verbose/detailed`. Thus authored layer meanings stored only in `detailed` are exported but invisible in the live narrative panel. Provide an existing-panel detail selection if full user-facing text coverage is being claimed; no new UI framework is necessary. Inline-image evaluation remains a separate plan requirement, not a demand to add images indiscriminately.

Portable catalog version/fingerprint and retained milestones are now present in `text_replay`/`presentation_export`; the older review's absence of those fields is superseded. Those exports are useful evidence but do not resolve the semantic gaps above. No new production changes or fresh test results are claimed by this reviewer.

## Event-cut and application audit follow-up

Source re-review confirms distinct true/false/unknown shove wording, F3 selecting detailed occurrence text, and fallback participants resolved from their bound commit snapshot. Condition state-transition prose is gated on an actual ConditionChangeFact and its prior committed state; mere sensory reacquisition does not fabricate that event. These corrections address the corresponding earlier bounded findings. Parent reports a native suppression/restoration probe; this reviewer did not rerun it.

All 348 archived permitted inputs were rescanned for every unlogged SpellFact and descendant, with exact results saved in `unlogged-spell-application-audit.json`. There are **five per-view nodes**, all canceled:

- `globe-fireball-edge` and `globe-fireball-edge--target` each contain the same two distinct applications: event `efe123ab-a171-4420-a32b-f10ea43d10e6` / application `70ae14b1-432f-54c2-b67f-2b0191204ae0`, and event `d11bc6d8-11c6-408f-b9d3-0b066e21d353` / application `d2f12e59-079a-596c-8f0a-adc1de29c171`. Every node has one explicit suppression, no descendants and no attack outcome.
- `goblin-08-spell-reactions` contains one canceled root spell (`e9ca1254-a366-4767-a376-04ae83ac36b2`), no application membership, no suppression and no descendants.

Therefore the earlier generic concern about ordinary application-only outcomes is **not demonstrated in this corpus** and must not justify speculative registries or invented templates. The concrete remaining defect is narrower: current top-level canceled handling formats the two suppressed Fireball applications as “Caster: Fireball is canceled.” That implies canceling the entire cast, twice, although these records identify only individual applications. Use finite application-specific blocked/suppressed wording, disclosing only its granted target/position and not inventing the suppression provider's name. Root cancellation keeps current wording. Preserve both application identities and their event-time dates; do not collapse them by common spell name.

Remaining semantic work after that correction is the documented selected effect/rig descriptions and meaningful motion/phase coverage, plus the broader plan's evidence acceptance. Do not characterize the canceled-application corpus as an unknown general backend defect.

## Current phased-motion / E–H follow-up

Suppressed-application wording, exact-source-sheet description guard, and body preparation/release/recovery corrections are reviewed in `remaining-selected-description-work.md`. That report replaces broad “all effects need descriptions” concerns with a finite list: reuse existing projectile/action-media display names and public state labels; possible new metadata only for selected unnamed ParticleMediaAsset, direct condition sheets, and unnamed replacement actor-layer sheets. Fixed-rig motion descriptions fit the existing BodyClip field. No blanket new registry or per-spell prose fields are warranted.
