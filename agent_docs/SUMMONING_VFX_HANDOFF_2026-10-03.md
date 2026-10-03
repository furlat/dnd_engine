# Summoning — VFX production handoff

Date: 2026-10-03. Prepared at the human's request for **the human to deliver**.
No artist or other chat has been contacted. This is the bounded visual delivery
for the [approved summoning plan](SUMMONING_BACKEND_PLAN_2026-10-03.md), not a
request to redesign creatures, spells, animation playback or backend rules.

## What is already being implemented

Three spells summon one selected creature at one selected ground position:
Conjure Animals, Conjure Fey and our authored Conjure Fiend. Higher slots unlock
stronger forms, not more simultaneous bodies per cast. The same canonical
creature can exist normally or be summoned; it uses its ordinary body artwork,
movement, attacks and conditions in both cases.

The batch has 24 bodies: Wolf, Hound, Boar, Stag, Jaguar, Bison, Ostrich, Brown
Bear, Lion, Tiger, Polar Bear, Rhinoceros, Blue Raptor, Stegosaurus, Elephant,
Triceratops, Mammoth, Raptor, Dretch, Corrosive Demon, Dread Demon, Claw Mote
Devil, Huntsman Wing Devil and Fellwing Devil. The vendor T-Rex sheet is used
as **Raptor at its original appearance scale**, not as an enlarged T-Rex.

Animals use their ordinary appearance. Fey reuse the eighteen beast bodies with
an existing blue palette replacement and translucent body material. Fiends use
the six demon/devil bodies. Separate original shadows and ordinary action
bindings are engine integration work, not a commission for new body art.

## Required delivery

Produce a small reusable effect family. Reuse suitable accepted effects where
possible. No separate program or set of particles for every creature.

| ID | Effect | Required phases and behavior |
| --- | --- | --- |
| S1 | Caster conjuration accent | A short accent for Animals, Fey and Fiend, ideally one shared effect with authored material variants. Align its release marker with the ordinary caster gesture. Existing shared Special1 body gestures are already bound; do not replace character animation sheets. |
| S2 | Arrival at selected position | Finite arrival with an explicit **body reveal** marker and a finite settling tail. Provide animal/natural, blue spirit and fiend variants where visually useful. The creature should become readable at reveal, before its first visible action. Provide separately compositable rear/front layers if the effect surrounds the body. |
| S3 | Summon departure | Finite dissolution with an explicit **body disappearance** marker and finite tail. Reuse the same family/material variants. It must work on a surviving dismissal/expiry as well as a defeated summon; departure does not leave a corpse by default. Do not bake a particular creature into the effect. |

S2/S3 are the missing lifecycle presentation. S1 is a decorative addition to an
already functioning caster gesture. These effects must fit both a small devil
and the larger existing beast silhouettes without masking the whole battlefield.
Deliver at least clearly documented small/ordinary/large support dimensions or
an explicitly supported scale range; do not compensate by stretching body art.

### Optional, after the required effects

- **S4: Fey halo.** A restrained blue spirit accent, shared across bodies. The
  blue/translucent body already exists; no replacement blue sheets. Keep the
  original shadow neutral. Avoid a large opaque ring obscuring neighboring units.
- **S5: Fey control break.** One brief bond-release accent. Losing concentration
  makes this same Fey creature hostile while it remains alive until expiry.
  Its HP, body, position, remaining lifetime and spirit appearance are retained.
  This is not a despawn followed by a hostile respawn, and needs no permanent
  hostile aura.

Do not hold the core delivery for S4/S5. No new body sheets, attack art, item art,
undead, familiar, elemental or unrelated spell work is requested here.

## Native facts the integration will consume

These are existing implementation contracts, provided to prevent visual rules
from drifting. The artist does not need to change them.

- Cast: the ordinary spell/cast lineage and recorded release. No new summon
  damage event or spell-specific animation executor.
- Arrival: `EntityCreatedEvent.summon_origin` identifies the summon, original
  cast lineage and `manifestation` (`natural`, `fey_spirit`, `fiend`). An ordinary
  birth without this origin does not receive summon particles.
- Departure: the recorded terminal spatial release carries an exact
  `TerminalOwnerRelease` and cause (`expired`, `dismissed`, `defeated`,
  `sustain_lost`, `closed`). `closed` is lifecycle cleanup; shutdown/reset must
  stay silent. Visibility/contact loss alone is not a departure effect.
- Fey control break: the recorded faction change with its causal control-loss
  lineage. The existing summoned identity stays present. Ordinary unrelated
  faction changes do not automatically use this accent.

Animals and Fiends disappear when existence-sustaining concentration is lost.
Fey lose control instead; they disappear when their remaining duration ends or
they are defeated. A controlled summon can be dismissed. Effects illustrate
these outcomes; their clocks never determine native existence or faction.

Hidden births/departures stay hidden. Reacquiring an already present creature
must not replay its birth; seeking history must reproduce the recorded sequence.
A failed/vetoed cast has no arrival. Replacing a previous summon must be able to
show the old departure and the distinct new arrival without confusing identities.

The current lightweight player facts retain manifestation, presence and faction;
the full birth origin and terminal cause are retained in the recorded native
events. When binding these later effects, expose only the additional typed
provenance that the selected cues need. Do not infer a cause from missing pixels,
actor names, elapsed time or live backend lookups.

## Export contract

Use the established production handoff/export conventions. Include:

1. Full source project/export, provenance and an inventory with hashes. Keep
   originals separate from selected production frames; no direct installation
   into this engine checkout is requested by this brief.
2. Transparent RGBA, exact source FPS and timestamps, finite phase lengths,
   frame counts, explicit release/reveal/disappearance markers and loop range
   only for optional S4. Prefer the existing 32 FPS production cadence while
   preserving the source clock and any denser original export.
3. Exact ground pivot, crop offsets, world support dimensions and supported
   scale range. Preserve registration across all phases and both layer banks.
   Gameplay uses 5-foot cells; review projection uses 128×64 diamond supports
   at pixel scale 1. Do not apply character-rig scale to already registered VFX.
4. Four camera views, or an explicitly documented camera-relative/billboard
   reuse policy that remains convincing in all four views. Include required
   facing banks where the chosen effect is direction-dependent.
5. Separate front/back layers where needed, with explicit depth/shadow policy.
   Ground contact stays on the ground. If the selected technique requires
   XYZ/ownership companions for correct occlusion, deliver and retain them
   intact, including Y; do not discard coordinates during packing.
6. Explicit alpha/material policy and any palette/region masks used for family
   variants. Body coloring is **palette replacement**, not multiply tint.
   Effect glow must not recolor or brighten the creature's shadow.
7. A concise manifest/README mapping each asset to S1–S5, phases and markers,
   with any limitations. Mark candidates separately from approved selections.

## Review examples for the delivery

- Natural Wolf arrival and dismissal; large Mammoth arrival/expiry.
- Blue Fey beast arrival and control break while the same creature stays.
- Fiend arrival and defeat departure, with original body shadows preserved.
- Arrival followed by movement/attack: particles/reveal finish in causal order.
- Near a solid wall: correct layer/occlusion behavior, no effect revealed
  through an unseen region. Compare all four cameras.

Final acceptance will use the engine's ordinary native-event four-camera video
gallery after integration. Source-only previews are useful for authoring but
are not a substitute for that check.

## References

- [Visual gaps and ordinary action-mapping obligations](SUMMONING_VISUALS_ADDENDUM_2026-10-03.md)
- [Implementation checkpoint and validation](SUMMONING_IMPLEMENTATION_2026-10-03.md)
- Existing caster bindings: `game/data/summoning_spells/`
- Passive origin/cause types: `dnd/types/summoning.py`
- Original-art and installation policy: [ASSETS.md](../ASSETS.md)

The human decides which delivery is accepted. Asset receipt and runtime binding
are separate steps; this handoff does not authorize automatic replacement of
accepted production art.
