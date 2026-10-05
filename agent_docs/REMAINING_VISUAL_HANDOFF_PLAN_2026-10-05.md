# Remaining visual handoff — non-surface integration

User request: integrate the remaining handoff, excluding surfaces and their transitions.
Source: output/weapon-vfx/visual-gaps-review-2026-10-04/REMAINING_HANDOFF.md
in the artist's 1aac worktree. The user's instruction authorizes this intake despite
older preview acceptance flags. Do not message the artist or other chats.

## Boundary

Existing action/condition events in, original delivered visual components out.
No new gameplay rules, damage, healing, saves, durations, action costs, or conditions.
Exclude Steam, Wet, ice and every surface/elemental transition. Frightened is also
excluded: the user separately assigned its new overhead cue to the artist.
Do not import actors, weapons, floors or the preview's seven-second schedule.

## Integration sequence and modules

1. Verify and preserve selected seven glyph banks using `devtools.media_delivery`;
   use an offline importer, existing projectile registrations/storage and condition
   media. Retain source hashes, pivots, straight alpha and32FPS. No runtime loader
   scan or new rendering registry. Private source/production copies must agree.
2. Author condition-owned overhead cues in existing condition recipes/media:
   Skeleton Archer Marked, Field Focus, Life Drain maximum-HP reduction,
   Leadership, No Reactions, Guiding Bolt mark and Chill Touch. Use actual
   registered definitions and existing head attachment. Keep bottom above head,
   readable at ordinary zoom, for modular and fixed rigs. Condition owner UUID
   governs onset, hold and removal; saves/misses must not create marks.
3. Jaw restraint reuses the installed Restrained cue. True Seeing potion uses the
   existing drink route and shared True Seeing condition; inspect existing head
   registration for both potion and spell, correcting shared data only if needed.
4. Inspect existing ordinary action routes for Leadership, mark designation,
   Field Focus, Divine Eminence, Wight Life Drain and Ember Quiver. Add ordinary
   authored delivery recipes/aliases and existing finite contact/hand components
   where missing. Use measured motion sockets/keypoints, actual event times and
   hit/save/miss branches. Never turn designation into an arrow attack, Life Drain
   into healing, Field Focus into a ground object, or Ember into a spell replacing
   the physical arrow. Weapon coating uses existing equipped-frame material data.
5. User decisions supersede the original human fixtures: remove Grappled from
   backend and presentation; request an overhead Exhaustion marker, not a pose.
   Frightened and Exhaustion art remain external dependencies documented for the
   human to forward. No actor deformation or paired grapple system.

## Verification and review

Test through native action/condition projection and real replay: applied/rejected,
failed/successful save, real damage contact, mark consumption, movement, expiry,
and no remaining cue after owner removal. Existing backend is authoritative.
Include modular and fixed-size creatures, all four camera views and ordinary zoom.
Record compact standard engine clips using real floor tiles and existing capture
pipeline, not artist encounter captures. Inspect actual pixels, not only metadata.

Independent anti-slop reviewer checks scope, re-use, semantic/art fidelity and
ordinary-zoom evidence. Independent anti-OOP/ECS reviewer checks passive authored
data, event ownership, no duplicated rules/state and import DAG. Review plan
before integration and final source/evidence after it. No source release declared
complete solely from preview validation. Document actual blockers, not vague todos.

## User correction — remove Grappled entirely

Remove the core Grappled condition, its standard registry entry, presentation and
icon binding, plus Freedom of Movement immunity/escape references. No active
attack or creature uses Grappled in production. Restrained stays intact for webs,
traps and other restraints. Update existing tests to keep their remaining coverage
and mark archived grapple coverage as deliberately retired. No grapple animation
or paired-pose subsystem will be added. Exhaustion requires a separately authored overhead marker.

## Exhaustion decision and ownership findings

User rejected fatigue pose work: Exhaustion needs an overhead marker, like the
new Frightened marker. Both are artist follow-ups; do not implement body distortion.
Chill Touch's named condition is a caster-side lifetime tracker. Its target-owned
NoHealing child (`condition.spell.no_healing`) must own the bone-hand mark, so the
mark appears on the victim and retires when its actual healing block retires.
Leadership requires native spatial membership, not a fabricated actor condition.

## User addition — complete debuff marker audit and non-overlap

Inventory every registered condition and trait with a harmful active state, not
only this handoff. Distinguish victim manifestations from caster trackers, area
owners and passive attack traits. Record head symbols, body-only effects, missing
symbols, and shared-child coverage. Do not generate new gameplay conditions or
ask for duplicate artwork for every spell wrapper. Surface-owned states stay in
the inventory but are deferred from this integration.

Proposed presentation contract: add optional `markerGroup` to existing
ConditionLayer data (default null). Only authored overhead status marks opt in;
head-attached sensory eyes, body effects and finite impacts are not automatically
markers. Rear/front banks of one symbol use the same semantic group. After existing lifetime sampling, select one currently renderable marker group per creature
for a 1.8-second slot in stable priority/group order using the supplied presentation
clock. Duplicate same-state owners do not create duplicate slots. All marker owners
and their true animation ages remain intact while not selected. All unmarked body
layers continue. Removal cannot leave a stale selected cue; retired markers never
compete with still-active markers. Seek/camera changes cannot restart the playlist.
No queue object, backend event, observer state mutation or new renderer registry.

Tests: two/three marks cycle without overlap; front/back stay paired; body layers
continue; same marker from two owners is one slot and survives one owner removal;
last-owner removal clears; appearance input order, camera and seek do not change
selection for the same time; zero/one mark remains unchanged. Native multi-condition
clip validates ordinary-zoom positioning and lifecycle. Anti-slop and ECS reviewers
must review this addition before implementation.

Implementation detail after review: the pure selector lives in condition_sampling,
called by the compositor with the existing absolute appearance clock and actual
activity/life state. This prevents hidden/action-ineligible symbols taking an empty
slot. Removal age already exists on resolved media, so no retired-state field or
queue was added. Final outgoing fades are retained when no live symbols remain.

## Current checkpoint

Implemented: Grappled removal; seven original glyph banks privately preserved and
installed; six target/self-owned condition marks and shared jaw cue authored;
all192 registered identities inventoried; generic markerGroup selection with stable
absolute timing, no queue or backend state. Exhaustion/Frightened deferred for
new overhead artwork. No other custom conditions were introduced.

Pending handoff work: native action preparation/contact for Divine Eminence and
Wight Life Drain, Leadership spatially-owned leader/recipient pennants, Mark Target
and Field Focus action gestures, shared True Seeing registration review, Ember
physical-arrow wake/contact. These are not declared finished by the marker clips.

Current evidence: `.runtime/remaining-handoff-20261005/`; seven native lifecycle
clips captured, then marker size reduced after direct visual inspection. Earlier
run is not final acceptance; the final-size render remains pending.

Tests: Grappled affected engine/manual/architecture run156passed with one unchanged
manual Dashing-removal assertion failing (60feet retained versus30expected); no
Dashing implementation changed. Document/discuss separately rather than silently
changing unrelated movement rules. Focused marker cycle5passed; larger marker
regression run pending.

Latest user rejected an unidentified nonpixelated/made-up effect. Clarification is
pending; do not guess which visual or backend mechanic they want removed.
