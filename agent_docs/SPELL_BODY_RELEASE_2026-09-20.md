# Spell injuries and creature material

User contract: damaging spells should release the target's material too. Any
spell-color influence must be very light; blood, bone and other materials keep
their identity. Preserve approved spell trajectories, anchors and timing.

## Findings

`dnd/body_responses.py` already subscribes to resolved `DamageAppliedEvent`,
independently of weapon identity. Its default profile admits only the three
physical damage types. Current engine tests explicitly freeze that restriction.
Newer spell review scenarios also construct bare humanoid entities without the
body-response trait that authored player builds and goblins already install.
The presentation path already consumes serialized release regions, deposits and
the causal spell contact; it does not need a second blood executor.

## Bounded change

1. Allow positive normal-HP injury of any damage type through the existing
   configured body response. Preserve immunity and temporary-HP-only exclusions,
   one release per resolved packet, material identity and receiving geometry.
   The strongest positive physical component retains its pattern even under a
   larger elemental rider; wholly nonphysical damage uses the existing
   compact blunt pattern. No spell identity enters native residue logic.
2. Compose the existing blood trait on humanoids in damaging-spell review
   fixtures. Do not give arbitrary entities or objects a default material.
3. Add one optional authored `spellTintStrength` to existing action media tracks,
   zero by default, 0.06 on body-release bindings. The owning spell's existing
   primary color blends into airborne particle colors once at binding time.
   No spell owner means original colors. Floor marks retain their material
   palette; no color or rendering instructions enter native events.
4. Verify real native hits, misses/saves, immunity/temp HP, mixed packets and
   each material; then serialized subjective replay, contact timing, colors,
   floor persistence and four-camera rendering. Reuse existing clip extraction.

Test boundary: native damage/real cast input → recorded release and native
residue; JSON replay → one particle burst at contact and material-colored floor.
Spell motion, weapon patterns, Sleep transitions and visibility remain regression
references. No new assets or per-spell branches are needed.

## Design reviews

- Anti-slop: GO. Preserve physical patterns in mixed packets; implemented and tested.
- ECS / anti-OOP: GO. Native ownership, DTOs, subjective filtering and import DAG
  are unchanged. The palette overlay is cue-local and never mutates material data.
  True Strike child weapon attacks retain their original material palette; they
  own weapon presentation, not the direct-cast palette overlay.

## Result

Implemented through the existing body-response handler and action-strip binder.

- 245 focused native/presentation tests pass; selected typechecks report zero errors.
- The native material matrix covers all 13 damage types across blood, bones,
  corrosive blood and dread blood, plus immunity, temporary HP and mixed packets.
- Real spell casts survive serialized subjective replay with one release per
  applied injury at its delivery contact. Misses/no-damage saves remain clean.
- Existing corrosive crossing tests now explicitly include the non-immune
  donor’s acid injury and new material release after entering its own pool.
- [18 clips, both observers and four cameras](http://127.0.0.1:8767/runs/20260920T212905Z-501f57/index.html)
  pass without gaps: Fire Bolt, Ray of Frost, Eldritch Blast, Acid Splash, Sacred
  Flame, Shocking Grasp, Poison Spray, Burning Hands and Thunderwave.
- Inspected Ray of Frost impact and settled floor frames. The transient blend
  remains subtle; the floor keeps its original blood color.

No new art, assets, spell-specific executors, source audits or palette mutations.
Old saved inputs remain unchanged; those lacking native releases cannot invent
blood during replay. This gallery records fresh real gameplay once.
