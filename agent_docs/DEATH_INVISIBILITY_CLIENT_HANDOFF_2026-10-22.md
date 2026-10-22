# Death and invisibility — backend handoff, 22 October 2026

Implemented on feature/rules-checking, on top of bedc3d92dc; the repair commit
includes this handoff and its regression tests. No client files were changed. Public schema
18 and both SDK contracts are unchanged. Adopt a fresh backend export containing
these changes and start a new encounter; the existing bedc3d92dc pin and recorded
runs do not contain these repairs.

## Per-creature zero-HP policy

EncounterRosterMember now accepts `uses_death_saves`:

| Value | Outcome at zero HP |
| --- | --- |
| false | Immediate death through the existing death path. |
| true | Existing dying, stabilization and death-save rules, including the pre-existing massive-damage rule. |
| Omitted or null | Preserve the source creature/character default. |

This is an authored member setting, independent of AI/human controller and
faction name. Creator characters currently default true; authored monsters
generally default false. The override applies before composition/entity birth
and scenario starting damage. Omitted/null does not alter existing recipe digests;
explicit values participate in the normal digest. Recreate recipes normally
when changing the policy.

The blue members produced by combat_configuration explicitly set false. The
Gallery's source substitution via model_copy retains that setting, so its
fighter sentries die at zero despite being built through the character creator.
Other custom rosters can explicitly choose either policy for each member.

## Defeat is terminal for the losing side

Combat still ends when at most one faction has conscious combatants. A losing
seat now receives boundary.lifecycle=terminal, input_actor_uuid=null and
state_revision=null. Status exposes the final_cursor; the final operation remains
deliverable and acknowledgeable. Further HTTP choices/input is rejected through
the existing game_terminal path. The direct native-worker admission also rejects
defeated actors, rather than bypassing defeat through post-combat authorization.

A surviving party remains outside_encounter and keeps its existing recovery and
preparation actions. A downed player's conscious ally can preserve that recovery
state even when the ally belongs to another seat. Temporary conscious conditions
such as Stunned/Paralyzed/Incapacitated are not treated as unconsciousness.
This change does not turn every dying character into a corpse.

Both supplied Gallery runs actually left the player DYING, reason DAMAGE. The
Lightning Bolt applied 28 damage. Neither showed massive-damage instant death.
The old publication nevertheless reported outside_encounter after defeat, which
explains the downed character with no further turns progressing.

## Ordinary invisibility reveals before the damaging result

For the ordinary top-level cast path, an invisibility-breaking reveal now settles
before the simultaneous target effects. A post-reveal spell version retains
the caster identity before a lethal hit removes the victim's sight. Serialized
Lightning Bolt now contains the spell and attributed damage for surviving,
dying and immediately dead recipients. Native and public reveal occurrence
precedes damage/life transitions. Target damage remains grouped with its shared
damage roll. Unseen Fire Bolt advantage, canceled casts and persistent/maintained
Greater Invisibility behavior are covered by controls.
Nested casts inside an already-open outer simultaneous group retain that outer
settlement boundary; this repair does not redesign general nested settlement.

The completed SpellFact still follows its result events: completion reports the
result. Schedule presentation using the existing causal lineage/parent links
and pre-damage reveal, not a flat rule that animates roots only after their
children. In the lethal Lightning Bolt case source_position can remain null
under the existing disclosure rule; the public line area_geometry.origin and
the pre-damage caster contact contain the observed origin. Do not invent a
position or expose a source that actually remained invisible.

## Validation and cost

The combined selected suite passed 102 tests in 37.23 seconds, including actual
HTTP/native-worker defeat, final SSE delivery/acknowledgement, allied recovery,
post-victory preparation, zero-HP policy/source combinations, and serialized
invisibility outcomes. The reveal owner's overlapping focused batch passed 86.
See the [repair plan](plans/DEATH_INVISIBILITY_INVESTIGATION_2026-10-22.md) for
commands, the earlier test gaps and independent reviews. Godot animation is not
visually qualified by these backend tests.

Thirty-target Fireball native casts including sensory work, four samples per
condition: visible 141–201 ms before / 139–157 ms after; invisible 183–743 ms
before / 138–525 ms after. Samples are noisy; no speedup is claimed. The visible
control retains one sensory settlement. Breaking invisibility requires two:
one reveal and one shared damage result, with no per-target settlement. Startup,
discovery, transport and rendering are outside these timings.
