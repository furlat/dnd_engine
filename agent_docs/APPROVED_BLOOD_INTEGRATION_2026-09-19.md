# Approved blood integration

**September 20 successor:** the user requested deeper gameplay geometry planning
before further implementation. The independently reviewed
[material-release plan](BODY_RELEASE_IMPLEMENTATION_PLAN_2026-09-20.md) now owns
that work and its dispatched asset handoff. The pending-neighbor-question wording
below records the earlier implementation checkpoint; do not reopen it as a fresh
blocker or treat this earlier art integration plan as the current specification.

The user approved the current `blood-fluid` artwork for integration. Source:
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/blood-fluid/APPROVED-PRODUCTION.md`
and `approved/manifest.json`. This supersedes the earlier candidate status and
the rejected stacked whole-burst/filled-tile approaches. The source handoff is
art data; its demo controls, provisional 420ms hit time and review zoom are not
gameplay rules.

## Contract and bounded work

1. Import the approved canonical droplet data and palette. Use the review's
   selected 96-droplet appearance without inventing an HP-to-volume rule.
   Each droplet is sampled from absolute elapsed time and sorted by its world
   ground depth, using existing projection and painter commands. Rotation of
   the camera changes projection only. Source data remains portable JSON.
2. Retain NeuroStudio's media track and injury anchor. Its `particles` role is
   existing vocabulary, but the raster-only asset representation needs a small
   explicit particle-data extension. Preserve sprite strips for bone/demonic
   profiles. No mutable particle simulation, new clock or per-spell executor.
3. Record ordinary blood accumulation on the existing native tile condition:
   one unit per qualifying release, capped at five, matching the approved
   20%-per-hit visual progression. Preserve condition identity and handlers.
   Other materials retain current behavior. Publish the actual tile after-value
   through the existing spatial-event contract, without path recomputation.
4. Bind the approved irregular floor material to recorded amount. Later observers
   must see the same current pool without receiving or replaying old injuries.
   Landed marks must persist, and saturation must not repeatedly darken them.
5. Generate real gameplay clips for repeated hits, departure, bloodied spikes,
   hidden injury/later discovery and both subjective perspectives, all four
   cameras. Test native amount/state, saved replay, particle ordering/seek and
   actual composed pixels. Preserve unrelated Fireball fixes.

The approved preview crosses several tiles, whereas current native deposition
owns only the injured creature's tile. A clarification is pending about whether
neighboring splashed tiles should now also become Bloodied. Do not silently add
renderer-only persistent state or pretend a nine-tile-wide field fits one tile.
Particle/media work and the existing-tile amount contract can proceed independently;
the persistent footprint integration depends on that answer.

## Reviews

Anti-slop: `spell_data`; ECS/anti-OOP: `ashen_native`. Independent study recommends
passive coefficient data plus absolute sampling rather than a matrix of baked
camera/direction/amount/frame sprites. Both identify recorded amount as necessary
for repeat hits and late-observer replay. Keep the approved repeated pattern stable;
randomizing a new field on every hit would defeat its five-hit cap. Exact directional
persistent fields also need explicit retained semantic state rather than reconstructing
hidden attacks. No per-droplet art values belong in backend events.

The ECS review identifies the existing full `SPATIAL_TILE_CHANGED` after-value
as the publication path. Its mechanics-specific helper requests path recalculation,
so use a narrow state-only publication entry point for this inert material change.

## Implementation checkpoint

Native amount and portable particle sampling are implemented. Blood keeps its
condition UUID and handlers, records amounts `1,2,3,4,5,5,5`, and emits no redundant
tile update at saturation. Every qualifying injury still retains its release.
Each actual increase publishes a fresh full tile after-value through a committed
spatial child of that injury; empty sensory hints leave traversal and visibility
revisions untouched. The independent ECS implementation review found no blockers.

The approved 96 coefficient records are local JSON. The existing action-media
cue owns their contact time and lifetime; each sample is calculated directly from
elapsed time. Disclosed source and held target contacts provide strike direction,
without querying native actors. The unknown-source fallback is canonical artwork,
not inferred hidden attacker data. Droplets produce independent painter commands
using their ground XY depth and visual height. Bone and demonic strips retain
their existing path.

Native/replay checks pass, including seven real discovered attacks with both
subjective recordings and teardown before replay. Particle checks cover a single
birth/landing per droplet, repeatable seeking, rotated strike direction, lifted
historical contact and four-camera drawing. An actual native-attack frame was
inspected in all four cameras at `.runtime/blood-integration-review/airborne-four-cameras.png`.
That image explicitly uses the previous floor artwork; it is not evidence of
completed persistent-floor integration. Focused production Pyright reports zero
errors or warnings.

The independent particle review verified all 96 coefficient records against the
approved source and confirmed palette, tail math, absolute sampling and painter
depth. Its selected track uses forward motion, source palette and world origin;
unsupported reverse/tint/screen-offset controls now report a binding gap instead
of being silently ignored. One concrete landing issue belongs to the pending
floor work: a held body lift translates the authored trajectory but its exported
life is a flat-ground crossing time. Compute landing against retained support
when connecting deposits; do not mistake that translated endpoint for ground or
introduce a separate collision simulation.

**Pending:** the neighboring-tile gameplay choice remains unanswered. Production
still selects the previous blood media, so the partial work cannot ship as a
complete approved appearance. Continue with the recorded footprint and organic
floor binding after that answer, then enable the media and generate paired clips.
Do not reopen the already-passing amount/particle work or claim the old static
floor mark is the approved accumulating pool.
