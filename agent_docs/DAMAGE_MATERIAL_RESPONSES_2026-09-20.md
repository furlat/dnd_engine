# Damage-type material responses — design and artwork scope

## September 21 — delivered blood-only integration

The user authorized the delivered `BLOOD-ONLY-HANDOFF.md` in the environment
art worktree after the trap/portal slice. ECS study reconfirmed the existing
High56 templates and organic field already implement the approved fluid base.
Reuse them. Port blood-specific `material.js` styling through a small JSON
response table and shared absolute particle/landing/melt sampling. Do not port
the lab's spell scaffolding, mutable particle store or changed receiving reach.

The previously reviewed factual primary/secondary damage selection is needed
for partly immune and mixed packets. Retain it in BodyReleaseResult; regions,
amounts, hazard identities and approved physical patterns remain unchanged.
This delivered table affects normal blood only. Other body materials retain
their approved media until their own authoring arrives.

Cold pieces melt into their existing kernels, using fractional fresh-contribution
weights; flight, floor reveal and cue completion share that schedule. Secondary
vapor is emitted from a droplet's past position, never the actor or a guessed
impact burst. Color/noise stays inside actual blood alpha. The lab's permanent
acid/poison/radiant recoloring cannot persist without native material state;
here it is a finite treatment of the new contribution, settling to the existing
red field. Earlier accumulated blood remains untouched. This follows the
reviewed state reconstruction contract below, not an unrecorded renderer history.

The original anti-slop/ECS reviews below remain applicable; the September 21
ECS handoff study specifically confirmed these limits and reuse points.

The user wants distinct injury effects across **all thirteen damage types**,
including physical damage delivered by spells. The previous correction restored
spell releases but routed every nonphysical injury through the same blunt
family. A 6% color blend cannot create the requested variation.

This document is a proposed next chunk, not a claim of implemented behavior.
Existing approved spell delivery, body contacts, weapon patterns and material
art remain the baseline. The queued four-spell integration is separate work.

## What varies, and what remains the creature's material

An injury has a material (blood, bone, corrosive/dread blood), receiving geometry,
and damage. The material owns its palette and persistent residue semantics.
Damage influences emission shape, timing, fragment character and finite secondary
effects. Spell color remains a very light accent, not the material's new color.

Use the existing native body-response handler, serialized releases, Studio media
tracks and absolute-time particle sampler. No per-spell injury implementation,
particle entities, fluid simulator or secondary event queue.

## Complete response vocabulary

These are proposed art directions, not new damage rules or conditions.

| Damage type | Material motion / silhouette | Finite secondary detail | Receiving-floor intent |
| --- | --- | --- | --- |
| Acid | Uneven clinging droplets, a short ragged spill; bone has etched-looking chips | Sparse fizz and short vapor wisps | Local irregular splat; retains the creature's residue identity, never turns ordinary blood into an acid hazard |
| Bludgeoning | Existing short broad burst, heavy drops / chunky chips | Existing impact detail | Preserve approved blunt footprint and accumulation |
| Cold | Brittle clumps / small angular frozen-looking fragments with sparse fine pieces | Restrained frost edges and cold mist | Compact deposition of the same material; no persistent ice tiles or freeze rules |
| Fire | Fine spray mixed with a few heavier droplets; dry material sheds fine fragments | Brief steam/smoke for liquids, sparse ember/dust detail for bone | Local spill in its original material; no automatic ash conversion or ignition |
| Force | Fast, heavy outward spray, strong separation and large visible splats / chips | A brief pressure kick if needed; no mandatory colored cloud | Fuller/broader proposed spread must come from native receiving regions |
| Lightning | Abrupt, short irregular burst with narrow flicks / splinters | Brief fine crackle, then a little vapor for liquids | Compact uneven splats; no conductive-floor mechanic |
| Necrotic | Slower heavy drops/clots; bone sheds dry crumbly fragments | Sparse fading dust or a dark wisp | A local heavy deposit, with the original material's settled palette |
| Piercing | Existing narrow directed jet / needle-like fragments | Existing critical quantity treatment | Preserve approved piercing footprint; includes spells such as Ice Knife's piercing hit |
| Poison | Sparse viscous drips and small low splashes; bone receives subtle pitting/dust treatment | A few bubbles or restrained wisps where suitable | Small local deposit; poison damage does not make normal blood poisonous or green |
| Psychic | Very restrained downward seep / a few falling chips | Usually none; existing spell impact already communicates the magic | Small local residue rather than an explosive splash; no invented external impact direction |
| Radiant | Fine sharp spray / bright-edged flecks, settling quickly | Brief warm glints that disappear | Local material deposit; blood remains dark red and bone remains ivory |
| Slashing | Existing lateral fan, streaks and split lobes / sheared chips | Existing critical quantity treatment | Preserve approved slashing footprint |
| Thunder | A broad, low radial burst with chunkier debris than lightning | Brief pressure/dust motion | Broad proposed native footprint; no invented creature knockback |

Force and thunder may share motion machinery while authoring different patterns:
force can read as a strong directed impulse, thunder as a broad pressure burst.
Cold should look like frozen material breaking, not a bag of bright blue cubes
that replaces the body material. Fire's steam is finite injury detail; changing
the actual state of blood already on a tile is a separate gameplay feature.

## Material application

- **Blood:** retain approved High56 dark-red identity. Change motion/fragment
  character and add sparse accents; do not replace it with spell-colored liquid.
- **Bone:** retain ivory/tan chips. Cold emphasizes brittle shards, heat dry dust
  and ember flecks, force heavier fragments. Do not show wet splashing from a
  skeleton merely because the blood response uses it.
- **Corrosive demonic blood:** preserve its olive/chartreuse identity and native
  acid-entry behavior. The incoming damage type does not redefine that hazard.
- **Dread blood:** preserve its dark wine identity and existing fear-entry rule.
  Incoming radiant damage does not turn it into a holy ground effect.
- **Poison-fluid art:** reuse the same authoring conventions in preview if useful;
  it remains art-only until a real creature profile is separately authored.
- **No body-response trait:** no blood or material burst is manufactured.

We need complete mappings, not a full spritesheet for each material × damage ×
critical × camera. Existing material art plus shared response parameters and a
small set of reusable secondary media should cover most combinations. Author
material exceptions only where the appearance actually requires one.

## Native and presentation ownership

1. Admission stays at positive resolved normal-HP injury. Miss, immunity and
   temporary-HP-only damage do not manufacture material.
2. Native regions continue to determine actual receiving tiles, supports and
   blocked paths. Force/thunder expansion or smaller psychic/cold footprints
   belong here, as ordinary authored damage-to-geometry choices in the existing
   body profile. These footprint changes remain explicit proposals until chosen.
   Initial motion/detail comparisons can use the existing regions. Enlarging a
   corrosive/dread footprint enlarges a real acid/fear hazard, so appearance
   approval alone must not silently change those areas. Art never enlarges a
   persistent footprint on its own.
3. Persistent marks remain reconstructible from tile state alone. Keep current
   material templates and retained ellipses/contributions for the first chunk.
   Vary airborne shape, motion and transient overlays without secretly selecting
   new permanent stamp art based on an injury that late observers never saw.
   Baseline depositing particle IDs, targets and kernels remain identical;
   airborne fragment shapes and explicitly non-depositing detail may vary.
4. Resolve one landing schedule for the selected response and share it between
   particle sampling, floor reveal and finite cue completion. The cue must
   include its latest landing; changing flight duration alone is insufficient.
   A slower frozen fragment cannot deposit its mark on the old blunt clock.
5. Keep motion samples and media in world/normalized region coordinates. Render
   all cameras from the same source and targets; retain wall clipping and actual
   material destinations. Ephemeral vapor dissipates and contributes no floor
   residue. Material pieces land at their recorded destinations.
6. Native events contain material, damage and receiving geometry only. Palette,
   particle count, sprites, source-frame ranges and playback rates stay in
   presentation data. A TS renderer should consume these passive values through
   the same contract, without a Python-only behavior tree.

## Mixed packets and repeated applications

The current player damage fact carries the packet's primary type. That can be
wrong for response selection when the primary component was immune. Native
resolution already records each component's post-affinity damage.

Proposed bounded rule:

- Keep exactly one material release per resolved damage packet.
- Preserve the strongest positive physical component's existing geometry when
  present, as in the preceding fix. A larger fire rider must not turn a dagger
  wound into a radial explosion.
- The primary causal type is the strongest positive physical component when
  present, otherwise the strongest positive nonphysical component. Ties retain
  recorded component order. This continues the established physical geometry
  rule while distinguishing a pure fire injury from a blunt physical injury.
- A physical primary may carry one secondary causal type: the largest positive
  post-affinity nonphysical rider. Pure nonphysical packets use one full response,
  not a stack of all components. Fully prevented components select neither.
- If these facts are not already available at the public release boundary, retain
  optional primary and secondary damage types with that existing release.
  `pattern="blunt"` alone cannot distinguish fire from bludgeoning+fire. No
  full component protocol or mitigation amounts are needed. Do not encode a
  VFX-profile ID, infer from spell names, or change the existing release
  visibility/disclosure rules.
- A small elemental rider gets a restrained secondary accent; it does not
  replace the physical burst. Initial scope does not stack every rider's VFX.
- Distinct applied packets in a spell lineage stay distinct: Ice Knife piercing
  then cold burst, separate Eldritch Blast hits, and simultaneous area recipients
  retain their existing contact times and native amounts.
- Criticals use the existing flag and bounded extra transient detail. They do
  not silently multiply deposited amounts or create new hazards.

During implementation, verify that the selected factual type is sufficient for
the agreed authoring. Do not add a broad new injury-component protocol in advance.

## Artwork and implementation order

1. Obtain anti-slop and ECS reviews of this plan and the companion art brief.
2. Queue the art brief with the existing material-art task, preserving its current
   user-directed work. Root owns game integration and requests new renders only
   where the existing assets cannot express the response.
3. Review all thirteen directions together on the same subject, same scale,
   camera, lighting and hit strength. Start detailed production with cold/fire/
   force, then complete the remaining mappings in the same shared vocabulary.
4. Implement the smallest selected response data and sampler extensions after
   the export contract is concrete. Keep transient overlay selection separate
   from native material/geometry. Reuse original templates for persistent marks.
5. Capture real gameplay examples across all damage types. Use maintained native
   spells where available; label a diagnostic native-damage fixture explicitly
   when a suitable maintained spell is unavailable. Do not pretend fixture
   damage is an implemented spell. Add no fake events to make a visual pass.

## Acceptance surface

- Every DamageType has an explicit authored response, including the three
  physical types. A small initialization/registry or test assertion can check
  table coverage. No source hashes, asset rescans or startup audits.
- All four actual body materials retain identity for every damage type; a
  no-trait creature produces none. JSON replay works after engine teardown.
- Real hit / miss / immunity / temporary HP / reduced damage; mixed weapon-rider
  packets; repeated packets; criticals; lethal and resting-body contacts.
- Native receiving regions and visible residue agree, including walls, elevated
  support, saturation and a late observer. No vapor-owned ground state.
- Particle flight and floor growth share contact/landing times, including after
  seeking backward or replaying without a live engine.
- Existing gallery: same actors, positions and source/target registration; both
  subjective perspectives and four cameras per recording. Avoid a Cartesian
  video explosion: cover all types on blood, representative contrasting types
  on skeletons and demons, and the full material/type matrix in fast tests.
- Compare timing and scene cost with the current shared release path. No per-hit
  asset loading or particle simulation state.

## Review / dispatch status

- Anti-slop review: GO with two incorporated clarifications: factual primary /
  optional secondary types distinguish mixed blunt hits, and changed native
  footprints remain proposals rather than silently expanded hazards.
- ECS / anti-OOP review: GO with incorporated amendments: the same factual
  type pair, unchanged deposition IDs/targets/kernels, and one landing schedule
  shared by flight, floor reveal and cue completion. Packet-level normal-HP
  admission stays intact; no per-component temporary-HP allocation is invented.
- Artwork brief: sent to existing material-art task
  `01a0b501-8a27-7413-ba24-4a36e5b140d2`, requested after its current
  user-directed environment-art corrections. Receipt confirmed: queued behind
  door/wall fit, interior partition trim and furnished prefab validation. The
  producer will preserve High56 exports and deposition contracts; artwork has
  not started and delivery remains pending.
- Implementation: not started; current approved gameplay output remains intact.
