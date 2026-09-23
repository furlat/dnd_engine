# Liquid barrels — implementation and limits

**Historical one-cell result, superseded by the user's area correction.**
The user requested surrounding native coverage for all six contents and then
rejected square/stamped pools. Current work follows
[the area and authored-tile plan](LIQUID_BARREL_AREAS_2026-09-22.md).
Rounded persistent material tiles and spilling animation are still required;
the gallery below is not a current or approved visual completion.

The [reviewed plan](LIQUID_BARRELS_PLAN_2026-09-22.md) is implemented through the
existing destruction, spatial-condition and tile-residue owners. The same
barrel UUID remains as a wreck. Its spill is a descendant of
`ItemDestructionEvent`, uses the recorded previous placement, and survives
retirement of the wreck. Intact retirement and unplaced destruction do not
create a spill. Repeated destruction does not deposit again.

## Playable contents

All six entries are direct authored items named
`environment.blocker.<contents>_barrel`, where contents is `oil`, `water`,
`grease`, `poison`, `blood` or `dread_blood`. They share one liquid-barrel
composer and passive content profiles, the existing 12-HP barrel body and its
accepted intact/destruction banks. No subclass per liquid or separate damage
executor was introduced.

| Contents | Native aftermath | Current picture |
| --- | --- | --- |
| Oil | One-cell difficult terrain; existing ignition produces FireSurface. | Dark liquid through the shared liquid sampler. |
| Water | One-cell Wet membership with its existing resistances/vulnerabilities and material transforms. | Blue translucent liquid through the same sampler. |
| Grease | Permanent mundane ground grease, DC 10 Dexterity slip checks and difficult terrain. | Barrel/wreck and received conditions; **no Grease floor artwork**, explicitly deferred by the user. |
| Poison | Real 1d4 poison contact damage, honoring immunity. | Existing authored green poison material. |
| Blood | Native Bloodied tile residue at amount 5, mechanically inert. | Existing blood material as a pool; old injury shapes are retained when the pool adds more blood. |
| Dread blood | Existing DC 10 Wisdom fear and paid retreat rules. | Existing dread liquid material. |

These are **one-cell spills**, matching the original oil barrel. There is no
fluid spread/mixing model. Water/oil/grease retain the existing exclusive
ground-material arbitration; tile residues use their existing independent
memberships. Material colors and local pool appearance are presentation data,
while cells, conditions, amount and lifetime are native facts.

## Important connections and preserved behavior

Oil, Wet and Grease previously had no public spatial observation. They now opt
into the existing sensory protocol; their material replacements do likewise.
The shared observation method receives already observed cells and preserves
the established discovery rule. It does not expose other areas, hidden cells
or undisclosed anchors. The renderer consumes these recorded observations.

Ground media layer and creature contact reach are different. Barrel spills
explicitly admit ground contact. Oil/water ground transformations preserve that
reach; Steam retains its cloud policy. Jumping over a spill avoids its contact
effects; landing on it applies them.

Grease inherits the existing Prone policy: on the creature's own turn, enough
remaining movement pays for an immediate stand. The failed-save review cases
first walk a real detour to spend that movement, then remain Prone until the
normal turn-start handler pays to stand. No temporary exception or fabricated
fall was added for the videos. Spell Grease keeps its original magical defaults;
the barrel explicitly supplies mundane tags and permanent duration.

The native residue amount remains bounded by its existing cap. When some blood
has injury geometry and a later deposit adds unshaped quantity, the shared
renderer combines the retained geometry with an authored pool for the remaining
quantity. It does not manufacture injury events or change approved shaped
splatter output.

## Review material

[22 clips, two observers and four cameras per clip](http://127.0.0.1:8767/runs/20260921T231101Z-2f7c49/index.html)
cover six break-and-cross narratives, additional failed Grease/dread saves,
and poison/water/Grease jump-over then landing narratives. The capture contains
5,252 four-camera frames. Every action is native; rendering consumes saved
public packets after native execution has ended. The gallery's 22 cases pass
its lineage and playback checks. Oil, water and blood settled frames were
visually inspected in all four cameras; this is implementation review, not
user approval of new colors.

Tests also cover late observation, retirement, poison immunity/re-entry, Wet
ownership, ground transforms, bounded accumulation and removal/replacement of
floor pictures. Validation results are recorded below after the final runs.

## Deliberately unfinished

- Grease artwork is not imported, bound or copied. It belongs to the later
  accepted spell handoff, as the user instructed.
- Persistent FireSurface art is not installed. Ignition removes the oil picture
  and changes the real mechanics; it does not yet draw sustained flames. The
  Godot task received a queued handoff request. Burning grass also needs
  explicit combustible-terrain rules and is outside this barrel change.
- Existing independently owned adjacent dread tiles can reverse a retreat back
  and forth. Study reproduced a Misty Step into two neighboring dread tiles
  spending all movement in alternating retreats. One-cell barrel tests do not
  claim coherent multi-cell dread-pool behavior; that existing issue remains
  separately scoped.

## Validation

- Required anti-slop and anti-OOP/ECS plan reviews approved the composition with
  explicit ground-contact configuration. Independent native implementation
  review approved the resulting ownership/disclosure paths and caught the
  mixed shaped/unshaped blood presentation case.
- Public-only serialized replay: 17 passed, including all six late snapshots.
- Review gallery: 22/22 passed; HTTP serving verified at port 8767.
- Full engine plus maintained registry run: 1,430 passed and one registry
  expectation failure (the newly authored barrel IDs were missing from its
  expected family set). The corrected exact registry check plus all new native
  barrel cases then passed **57/57**. No engine behavior failure remained.
- Final liquid media plus existing blood surface/material/body replay selection:
  **59 passed**. A broader boundary/Ashen/prop selection passed **158**.
- Direct pixel comparison preserved **120/120** existing shaped-injury samples
  across materials, amounts, cameras and light treatments. Unshaped old residue
  stamps deliberately adopt the new pool fallback; this is not a claim that
  those fallback pictures are unchanged.
- Final `pyright dnd game devtools/animation_review`: **0 errors, 0 warnings**.
- Final maintained registry + public liquid replay + gallery regression run:
  **30 passed in 184.98 seconds**, including saved-input playback in a fresh
  process with native generation and content bootstrap unavailable.

Evidence and precise commands are retained in `.runtime/liquid-barrels-20260922/`,
including the native and presentation reviewer reports. Source stayed on the
current recovery branch; no commit or Grease artwork import was made.
