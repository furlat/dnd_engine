# Initial narrative implementation — independent review

2026-10-05. Read-only review of `game/presentation_text.py` before CLI/UI integration. No production edits.

## Disposition: one timing correction required before integration

The implementation uses projected native logs directly, does not recursively traverse log subentries, does not execute gameplay, and keeps a pure seek function. Native UUID rather than text dedup preserves repeated equal descriptions. Existing timeline traversal supplies nested offsets and root reconciliation is treated as a fallback rather than a second occurrence source. These are appropriate bounded choices.

### Required correction: undated descendants bypass aggregate outcome floor

`outcome_date` defaults a node's own missing date to head completion, but defaults a descendant's missing date to zero. A root assigned an early release/contact date can therefore expose verbose/detailed wording describing an unplaced child before that child's own narrative entry, whose date falls back to completion. This contradicts the function's promise to wait for all disclosed outcomes summarized by a parent.

For unresolved outcome children, either attach their exact existing milestone or conservatively use the same completion fallback as their standalone entry. Do not infer timing by prose parsing. Add a regression containing an early-dated root with a later/unplaced disclosed result/log child; the root's aggregate details must not appear before the child is admitted. It is acceptable for the initial seam to be conservative while exact semantic milestones remain incomplete, but document that conservatism rather than claiming precise all-action timing.

### Inspection caveat

`describe_known_state` iterates retained actors and objects, including remembered ones. The strings currently read like current facts (“name: HP; life”, “object at position”). They must be labeled as known/last observed when no current visual/contact authority exists, or be restricted to current observations with a separate remembered section. A remembered location is not a live location. Filtering INTERNAL conditions is correct but does not solve temporal interpretation. Avoid exposing this helper as current scene inspection before that distinction is explicit.

## Scope of positive assessment

- Strings come from exact projected node logs rather than later actor-name lookup.
- Cancellation does not blindly discard surviving child logs.
- Current lookup does not introduce spell-specific text tables or a new runtime queue.
- `narrative_at` can admit time-zero entries and behaves deterministically on seek.
- Missing-log outcomes, authored gesture/effect descriptions, full state inspection and complete family semantics remain deliberately unfinished. Do not describe this first log adapter as the finished text renderer.
- Existing lethal-result tests are relevant but cannot detect the undated-child case because applied damage already has a commit date.

No broad architecture rewrite is requested by this review; close the timing edge and constrain inspection wording before connecting the seam to player-facing UI.

## Correction and integration review

**Approve the bounded projected-log narrative seam.** The undated factual/log descendant fallback now floors aggregate wording at completion; the new regression removes result commits from a real bound cast and verifies the parent cannot reveal its aggregate early. Unseen retained actors/objects receive a `Last known` prefix. Both initial findings are closed.

The Pygame adapter consumes the same `presentation_ms` and bound records as scene playback. F4 changes layout mode without generating a new encounter or re-running rules. The old `_log_lines` text-value dedup is removed. The headless exporter accepts a decoded public player sequence, reuses shared grouping/binding, retains condition activation ownership and samples final body placement for subsequent heads. No native input reconstruction or graphic resource loading is introduced. Parent-reported eight focused checks include native perspectives, seek and subprocess import rejection; this reviewer did not independently rerun those tests.

### Exact remaining coverage gaps in current code

1. `bind_narrative` emits only nodes with `combat_log is not None`. Every legitimate public fact without a log remains absent: applied packets, condition/item membership edges, object state changes and other variants require an explicit emitted/state-only/technical disposition. No-log coverage must be measured rather than assumed.
2. There is no authored gesture/effect description metadata consumed here. Output does not yet describe selected clips, Magic/Effect layers, release gestures, spatial formation or clearance. Upstream log text is an outcome source, not that authoring layer.
3. The current date lookup has exact commits plus attack contact/cast release, body effect and equipment completion. It has no explicit narrative-specific phase for attempts versus release versus each application. Aggregate descendant flooring can conservatively delay wording until completion. This is safe fallback timing, not the plan's final authored milestone contract.
4. Dedup is event UUID only. The present seam emits one log per retained node, so that is adequate for its current unit. Future multiple phases from one node need explicit phase/application identity; adding them without extending the identity would suppress real occurrences.
5. `describe_known_state` currently covers actor HP/life/condition names and object names/positions only. It omits terrain, tile facets, light/visibility, connectors, visible equipment, object open/lit/engaged/integrity state, fields, surfaces/deposits and concentration/item ownership. It correctly avoids fabricating their occurrences but does not fulfill full state inspection yet.
6. `text_replay` retains condition clocks needed for binding, but does not emit semantic lifecycle descriptions from all six retained maps. Quiet acquisition, suppression, consumption, partial retirement, absence/return and initial state remain separate upcoming coverage work.
7. Pygame narrative currently presents compact lines and the limited inspection list. Verbose/detailed expansion and optional images are not surfaced, and the wrapping implementation collapses embedded line breaks. These are UI capabilities still absent, not proof of wrong shared evidence.
8. Saved text output has no declared portable schema version/catalog provenance yet. The new records are an internal seam, not the final future-client interchange format.
9. Current tests establish selected lethal-result/zero-time/dedup/headless behavior. A/B/A, nested movement/reaction offsets, hidden-source later revelation, child-only/canceled roots and lifetime/state-only semantics still need their dedicated coverage receipts before claiming full narrative equivalence.

The seam can be retained while those planned layers are built. It must not be presented as completing the user's full rendering/schema/text plan.
