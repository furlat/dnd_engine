# Call Lightning: approved BG3 behavior

The human requested the BG3 version on October 3. This supersedes the earlier
proposal to retain 120-foot range and a five-foot radius.

Scope correction: backend only. The visual bindings, preview work and associated
game tests added in this task were unauthorized and have been reverted at the
human's request. This document does not approve any artwork. Backend work remains
stopped; the rollback does not authorize further implementation or validation.

## Contract

- Initial cast: one action and a level-three-or-higher spell slot; immediate
  lightning strike at a selected visible position.
- Range: 60 feet. Blast radius: BG3's displayed seven feet (two metres), using
  the engine's existing five-foot grid occupancy rules.
- Each occupant, including allies, makes a Dexterity save against the originating
  caster's spell DC; 3d10 lightning, half on success, plus 1d10 per slot level
  above third. Repeat casts retain that slot level and spellcasting source.
- Ten caster turns of concentration. An admitted caster-owned timed effect owns
  the repeat action; expiration, concentration loss/replacement and death remove
  that grant through existing condition ownership.
- Repeating costs one action and no spell slot. It is a spell activation, as in
  BG3, so shared spell restrictions, protection and presentation apply.
- Caster movement is ordinary movement. Every strike selects its own current
  visible position within range. No persistent damage zone, moving cloud,
  weather bonus, overhead-clearance requirement, or automatic turn/entry damage.
- Existing Haste, Action Surge, Slow and attack budgets remain authoritative.
  Extra Attack, offhand and Frenzy grants do not become lightning strikes.
- Visuals and artwork integration are outside this task.

Sources: https://bg3.wiki/wiki/Call_Lightning and
https://bg3.wiki/wiki/Activate_Call_Lightning (checked October 3).
The documented BG3 multiclass DC bug is not copied: retain the originating
spellcasting source. The existing discrete grid remains; no sub-tile positioning
or AoE-engine redesign is included.

## Implementation

1. Add public native acceptance cases for range, initial/repeat costs, upcasting,
   retargeting after movement, skipped turns, expiry and concentration removal.
   Exercise existing action-budget variants without changing their policies.
2. Keep both existing content identities. Use the existing slotless SpellAction
   support for the granted activation and a single local lightning/save function
   for both initial and repeat outcomes. Record normal typed spell events,
   geometry, save facts and damage ancestry; do not add another event family.
3. Admit a ten-turn concentration child before granting the repeat action and
   before initial damage, through the existing target-application hook. This
   makes self-damage obey concentration/death cleanup. Reuse the existing marker
   and duration clock; an optional exact action UUID removes only its owned grant.
   Repeat validation checks the admitted marker UUID, invalidating stale actions.
   Both casts validate point visibility/range before costs, including direct calls.
4. Update backend catalog facts and provenance for the changed contract.
5. Verify native spell behavior, concentration ownership and existing action
   budgets. Record actual results without claiming graphical acceptance.

## Review and completion

Anti-slop reviewer: check minimal scope, shared damage/event path and no duplicate
runtime ownership. ECS/anti-OOP reviewer: check condition ownership, import DAG,
typed events and unchanged action-economy rules. Cross-chat communication is now
prohibited by the human; this document does not authorize further agent contact.

Completion concerns native acceptance and resolved scoped reviewer findings.
No visual integration, previews, asset import or publication belongs here.

## Results

Plan reviewed independently: anti-slop approved; ECS approved with explicit
selected-point validation and admission-before-damage corrections (incorporated).
Initial public regression run: six failures demonstrate old range, missing expiry,
replacement losing the grant, and repeat activation/discovery differences.
Backend edits remain uncommitted. Broader validation was interrupted when the
human stopped work. All graphics/preview edits from this task were subsequently
reverted, and its generated preview gallery and screenshots were removed.
