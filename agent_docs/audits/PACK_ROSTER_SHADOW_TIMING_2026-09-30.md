# Pack roster shadow and rig timing audit (2026-09-30)

Focused read-only evidence study for paired shadow sources and shared action
timing. The only generated pixels are private, deterministic probes under
`.runtime/pack-study-20260930/shadow-timing/`; no source archive, installed
asset, runtime binding or schema was changed.

## Shadow-source evidence

Both installed body-only rigs have authoritative complete alternatives in the
same source pack:

| Installed rig | Source archive and paired members | Sheet geometry |
| --- | --- | --- |
| `smallscale.greywolf` | `2D Animals mega Pack 1 V2.zip`: `Spritesheets/Shadowless/Grey Wolf/{Idle,Run,Attack1,Die}_Shadowless.png` paired with `Spritesheets/With shadow/Grey Wolf/{Idle,Run,Attack1,Die}.png` | 960×512, 64px cells, 15×8 |
| `smallscale.skeletonarcher05` | `2D HD Undead pack 1.zip`: `Spritesheets/Shadowless/5Archer/{Idle,Run,QuickShot,Die}_Shadowless.png` paired with `Spritesheets/With shadow/5Archer/{Idle,Run,QuickShot,Die}.png` | 1920×1024, 128px cells, 15×8 |

I read every pixel in all eight facing rows and all fifteen frames for those
four clips per rig. In every pair, the shadowless body pixels have alpha 255
where present; the full shadow atlas agrees exactly with those body pixels.
The source shadow appears only where the body sheet is transparent. I retained
the exact shadowless body and copied the source's full RGBA pixel at every
body-transparent position to an under-body shadow sheet. Compositing that
layer under the unchanged body reproduces the full with-shadow atlas with
**zero differing pixels** for all eight sheets. The private `pair_metrics.json`
records dimensions, coverage and zero-difference counts. This includes soft
shadow alpha and edge pixels: the extraction preserves their actual source
RGBA values instead of thresholding a black silhouette or making a hard mask.

This pair-specific result is stronger than a generic exterior-mask estimate:
there are no semi-transparent body-edge pixels in the tested body atlases, so
no hidden shadow must be inferred behind partially transparent body pixels.
The shadow itself does have varying alpha, and its exact source pixels are
preserved. It does not establish that every clip in either full pack has the
same registration or extraction properties; it establishes the listed eight
installed-coverage examples. The individual probe outputs (`*-body-shadowless`,
`*-shadow-exterior`, and `*-recomposed`) are diagnostic copies, not production
art.

Visual review of the full recomposed `Grey Wolf/Attack1` and
`5Archer/QuickShot` atlases confirmed all eight rows are occupied and maintain
their distinct facing/action sequence. The source pairs and numerical pixel
comparison carry the parity claim; viewing the black transparent canvas alone
is not used as proof of subtle shadow color.

### Prior NeuroClient method search

I searched the current `/home/tommaso/Dev/NeuroClient` source, its Git history,
the private installed-art records, and source references in the cleanup audit.
The located implementation models a separate `shadow` slot and applies an
authored layer alpha; `equipmentVisuals.ts` defaults it to category `Shadow`
and alpha `0.5`, and `AnimatedEntity.ts` applies the alpha. The prior records
call shadow alpha an explicit adaptation and note the preserved PNG alpha
residue. I did **not** find a precise source-color/alpha extraction algorithm
in those locations. That does not disprove the user's recollection; its exact
file or earlier source snapshot remains unidentified. The current paired-pack
method above does not need a guessed color key and preserves the source
RGBA exactly for these samples.

### Other owned packs' layer evidence

The Orc/Goblin and Demon study identifies vendor-separated body, shadow and
effect roots, with per-family/per-clip coverage; some effects are placeholders
and must be checked before use. These are the strongest already separated
tracks. The undead study finds complete Shadowless/With-shadow alternatives
for Undead, HD Enemy and HD Zombie. Top-down Zombie has matching body and
`Shadows/` sheets under its Shadowless tree plus a combined option. Keep a
selected body, shadow and any actual effect track independently bound where
the source provides them; preserve the combined atlas as source evidence, not
as a second shadow to draw. The five fixed rigs currently using separate
body/shadow are Goblin01, Orc01 and DemonBeast01–03. The two paired extractions
here establish concrete source coverage for GreyWolf and SkeletonArcher05
without installing it.

## Shared rig/action timing evidence

`BodyRig` owns `BodyClip` records with semantic clip id, source clip, frame
count, FPS and sheet binding, plus rig facing rows, slots, sockets and anchors.
`select_attack_profile` first chooses an `AttackVariant` from retained attack
facts. `bind_attack` then looks up its actor clip in the source rig and resolves
the selected variant's named frame anchors. A fixed rig can map a semantic
clip to a differently named vendor clip (Skeleton Archer semantic `Attack3`
maps to vendor `QuickShot`), but there is no presentation binding that chooses
a rig-compatible clip and anchor set for the already-selected action/profile.
Shared anchor frames can therefore remain an unsupported assumption when
another rig needs a different gesture or timing.

Cast recipes own `actionClip` and `releaseFrame`; `compile_cast` resolves that
clip in the caster rig and applies the release frame using that clip's FPS.
Generic `ContentActionRecipe` actions have an actor clip and named anchors.
These paths provide the semantic recipe/profile identity and selected rig clip
needed by a shared presentation adapter, but no per-rig overrides. Current
anchor names include action_start, release, contact/impact/effect, prepare,
recover and complete in their respective recipe types. They are not
interchangeable, and `end` is not an existing `BodyClip` marker contract.

The source sheets show why action labels cannot supply timing: archives give
sample order and dimensions, but no FPS, loop declaration, pivot, release or
contact markers. Two concrete frame-count exceptions are already established:

* Orc/Goblin `Block` sheets are 6 frames (768×1024 at 128px cells); Demon
  `Block` sheets are 7 (896×1024). They must not inherit the usual 15-frame
  duration.
* Character-pack Knight, Paladin and DeathKnight `CastSpell` sheets have 16
  frames. Existing `BodyFrame` anchors are constrained to 0–14, so a marker
  for the sixteenth sampled frame cannot currently be represented by that
  anchor type. The clip's `frames` field itself can express 16.

There is no declared source FPS for these packs. The installed 12 FPS values
remain local authored choices and should not be back-described as vendor
timing. `game.animation.body_duration` owns the current body duration contract:
`(clip.frames - 1) * 1000 / (clip.fps * speed)`. Action marker time is
`frame * 1000 / (fps * speed)`. Preserve these equations; do not replace them
with `frames / fps` or add a one-past-end body marker. The final sampled index
is the current animation end boundary by design.

### Candidate boundary for independent ECS review

Do not add markers to `BodyClip` alone: one body clip may be reused by
different actions with distinct release/contact moments, and one semantic
action may need another rig-specific clip. Preserve the current semantic
selectors, then resolve a presentation binding keyed by the actor rig plus the
already-selected action identity. For attacks, that identity includes the
owning attack recipe and `AttackVariant.id`; casts and generic actions use
their existing recipe/content identity. The passive binding could supply an
optional rig-compatible semantic clip and partial overrides for that selected
action's named anchors. Missing overrides retain the recipe-authored choices.

Use one resolver mechanism after the existing selectors, while keeping each
source record authoritative: `AttackVariant.anchors`, cast `actionClip` /
`releaseFrame`, and generic action recipe anchors. Do not assume one `contact`
marker applies to all actions using a clip, and do not introduce an
unobserved common set of phases. The specific typed key, record placement,
and whether clip selection and marker overrides should share one record remain
unresolved design choices. A marker index representation also needs to allow
valid frame 15 for the 16-frame Character-pack casts; current `BodyFrame` only
allows 0–14. Validate any choice against the selected clip's actual frames
while preserving the existing `(frames - 1) / fps` duration and `frame / fps`
anchor semantics.

This is a candidate boundary for independent anti-OOP/ECS review, not an
approved schema design. Marker placement remains manual art review: the sheets
prove motion order, not D&D impact or release time. Review action+rig pairs
across all eight facings, record chosen sampled frames and rationale, and
compare timing against the existing causal event timeline. Keep missing
ranged/cast art an explicit media gap.

## Scope and review checks

The source/fact boundary remains: native content owns stable NPC identity,
rules and allowed equipment/action facts; frontend presentation resolves those
facts to a rig and its typed body/action records. Source filenames, media
availability, contact-sheet indices and renderer execution do not enter native
content identity. Saved-event playback remains based on retained causal
lineages, never live-state queries for historical rendering.

Anti-slop check: the pixel equality result is limited to the eight named pairs,
not a claim about all packs or timing. No clip label is treated as a combat
event, and 12 FPS remains an authored adaptation. Anti-OOP/ECS check: the
candidate is passive presentation data keyed by resolved rig and already
selected semantic action/profile, followed by a shared resolver. It adds no
creature subclass, framework, runtime archive scan, media fact, or rules
executor. An independent ECS review is required before choosing a schema or
writing an implementation plan.

## Additional mounted-art observation

Goblin 11 and Goblin 12 `Idle 1` atlases in the private Orc/Goblin study output
visibly show riders on tan and gray quadrupeds, respectively. Separate Animal
1/2 samples resemble those mounts, but I have not established clip-by-clip
rider/mount registration. A narrow D&D source search found no mounted-creature
or rider/mount action composer; NeuroClient's modular `Mount1`–`Mount5` gear
categories do not establish native mounted rules or fixed-rig composition.
The subsequent [Orc/Goblin completion](PACK_ROSTER_ORC_DEMON_COMPLETION_2026-09-30.md)
reviews the mounted Attack/AttackRun/Run/Die strips and selects separate Goblin
rider and wolf-like steed proposals with real spear gear and a proposed steed
Bite. Those are authored choices; independent rider/mount registration remains
unestablished. Mounted playback capability remains unimplemented; do not imply
an existing native rider/steed relationship or substitute a renderer-only
association for one.
