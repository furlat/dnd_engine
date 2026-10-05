# Narrative seam proposal — independent anti-slop review

2026-10-05. Source/plan review before implementation. No production edits.

## Decision

**Approve reuse of existing observer-projected combat-log wording as a narrative input, with the timing/ownership requirements below.** It avoids a duplicate per-spell/per-action wording registry. It does not by itself implement all authored gesture/effect descriptions or solve semantic occurrence timing.

Evidence: `game/presentation.py:_retained_event` calls `project_combat_log` and normalizes the detached result. `dnd/subjective_combat_log.py` filters nested entries and sanitizes names/positions with event-time grants. `game/player_projection.py:_action_log` additionally sanitizes foreign resource conversion wording. `PlayerNode.combat_log` is therefore the correct received source; never obtain an unprojected engine log or rebuild names from final encounter state.

The current `encounter_play._log_lines` emits compact text after completion and deduplicates by string. Replacing that use with occurrence-based output is justified: two real identical attacks must not collapse because their text is identical.

## Minimal integration

1. Add a passive occurrence record in the planned presentation type owner: native evidence key, local/absolute time ownership, text payload or finite semantic template, and explicit phase. Do not add a new event queue. Binding produces records; text formatting and UI consume them.
2. Reuse the projected log's compact wording when it states the occurrence being emitted. Preserve verbose/detailed payload as evidence gated at the same or a later safe milestone, not independently available at declaration. Renderer-specific markup conversion belongs in the text/UI adapter; never interpolate received names as trusted HTML.
3. Derive dates from existing exact commits and bound owner anchors. Native node lookup stays separate from reduced-node copies, because some state commits deliberately contain `replace(event, fact=None)` while still owning world-update evidence.
4. Fill only legitimate missing factual outcomes with finite typed-fact handlers (condition change, heal, damage, state-only actions etc.). This is a dispatch by received fact variant, not a registry keyed by spell name. Keep state inspection separate from witnessed occurrences.
5. Traverse existing nested timelines with offsets. Dedup by native event/version/application/phase as appropriate, never string text, target UUID or enclosing group. Reconciliation folds are not occurrence sources.
6. Seeking rebuilds the prefix; forward playback admits zero-time heads explicitly and returns newly crossed occurrences. One shared presentation cursor remains authoritative.

## Timing blockers to avoid

**A state commit is not a universal log timestamp.** Attack/action roots may not be folded in `state_commits` at all. `_has_standalone_state` only admits selected state families, and `DamageResultFact` folds at its actual HP boundary. Body-only or log-only events still need an explicit occurrence disposition using the existing bound action/attempt/response timing. Do not silently omit them or give them the first convenient child timestamp.

**Upstream logs are generated at event completion and can summarize descendants.** `format_attack_compact` includes total damage; `CombatLogEntry.sub_entries` may contain saves, damage and other child logs. An attack summary saying “hits for 7” cannot be shown at release, or before every applied packet it summarizes. Use the exact native resolution ownership and the latest required outcome milestone for that summary. The absence of a graphical body does not authorize earlier information disclosure.

**Do not recursively emit sub_entries and individual PlayerNode logs.** They can describe the same native outcome, and subentries do not provide an adequate independent event identity. Prefer each actual projected node's own entry. If a root's log tree is the only disclosed wording, treat it as a summary gated by the native outcomes it represents; do not invent child identities from list offsets or infer causality from matching strings.

**There must be an explicit no-log outcome policy.** A save success does not imply zero damage; a request does not prove application; canceled parent does not erase surviving child outcomes; lack of a visible attacker must stay unknown. Use typed received facts, not prose parsing, to determine those semantics.

## Required focused examples

- A/B/A repeated applications and two identical attacks: all distinct occurrences retained.
- Lethal attack: no aggregate damage/death detail before its native HP/life commitment.
- A root with no state commit and a zero-duration body action: neither silently lost.
- Hidden-source damage: projected wording remains anonymous after later revelation.
- Parent summary plus individually logged children: no duplicate outcome caused by recursive log traversal.
- Movement reactions: local nested times shifted once; root reconciliation emits no children again.
- Forward/seek/initial-zero-boundary parity and names pinned to event-time evidence.

No new gameplay fields are required merely to reuse these existing log entries. If a particular aggregate lacks sufficient causal timing references, expose that as an exact missing provenance case rather than inventing a heuristic. Authored visual semantics (gesture, emitted layer, formation/clearance) still require the plan's data descriptors later; upstream combat logs cannot replace them.
