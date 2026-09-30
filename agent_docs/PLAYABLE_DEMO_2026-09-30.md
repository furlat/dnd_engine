# Playable demo — September 30

The user prioritizes getting a game into players' hands. This unit delivers one
local, replayable encounter through the existing Pygame application. It does not
wait for more spells, windows, multi-Z or a release/quest framework.

## Playable slice

One spellblade enters a small occupied storehouse. The player can open and loot
a supply chest, use a lever or the door directly to enter the guarded room,
navigate and break existing furniture, and fight two native Goblins using melee
or the premade's spells. Native encounter completion ends the demo; the chest is
available before combat ends, not a promised post-combat interaction.

Use one human-controlled hero deliberately: the current application renders one
observer, while the older two-hero skirmish can offer the second hero's targets
outside that observer's view. Party viewpoint switching is a separate task;
this demo must not union senses or leak hidden enemies.

## Existing owners and bounded changes

1. Add one small battlefield definition/builder and one ordinary encounter
   recipe to the existing scenario catalog. Use current premade/content recipes,
   item builders, cold world publication, NativeAIController and action discovery.
   No map-specific runtime rules or scripted damage/outcomes.
2. Expose the encounter in `python -m game --encounter ...`. Preserve the existing
   default skirmish/reference routes. Give the demo a concise objective/control
   hint; a player must be able to find move, interaction, attack and spell actions.
3. Show encounter completion only after its recorded history settles. Derive
   survivor/defeat text from retained player facts, not a renderer query into
   live entities. Allow retry through normal session teardown/composition.
4. Play through actual discovered actions: chest, lever/door, movement, spell,
   native enemy turns, final encounter event. Verify the same SDL frame pump
   settles its historical state with no presentation gaps. Check a losing run
   and fresh retry as well. Fix only observed blockers to this slice.
5. Inspect actual displayed frames at multiple camera corners and document the
   exact launch command and controls. Keep art private. This is a local playable
   demo, not a public distribution containing licensed media.

## Acceptance boundary

Input is normal mouse/keyboard selection or the existing test callback returning
the same discovered action/target indices. Output is native event lineages,
subjective historical state and displayed Pygame frames. No fake review-only
state, screenshot-derived gameplay, mandatory VFX work or new visual test system.

Existing tests already prove native fight completion, paused-history independence
and the workshop lever. Extend those boundaries for the integrated room rather
than replacing them. The cloud/window design remains separately recorded; door
closure does not retract an established cloud. Multi-Z remains deferred.

## Review and progress

Anti-slop: `cloud_backend_review`. ECS/anti-OOP: `interiors_backend_review`.
Both initial reviews identify existing scenario composition as sufficient and
the one-observer / post-combat-input constraints above. Final scope review and
implementation evidence will be recorded here.
