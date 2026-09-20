# Graphics review: authored data, execution semantics and positioning

Date: 2026-09-20. Requested after the Ray of Frost/Ice Knife contact correction.

The practical next-work sequence is now the independently reviewed
[graphics cleanup plan](GRAPHICS_CLEANUP_PLAN_2026-09-20.md). It incorporates the
user's later clarification: preserve approved rendered output including current
post-processing, not raw JSON values, and derive coverage from initialization
and registries without hashes or asset audits.

## Verdict

The concern is substantiated. We have substantial reusable authoring data and
shared execution code, but **we cannot currently claim that these bundles will
work in NeuroClient with only paths or other small packaging adaptations**.
The user clarified that compatibility with an overly restrictive old schema is
not itself the design objective. Validator rejection measures adaptation work;
it does not establish that an extension is bad. Paged media, impact-only assets,
per-phase scales and spell palettes address real requirements. Each extension
must be judged by that requirement and its execution meaning.
We have extended its format without changing its declared version, accumulated
different attachment conventions, and sometimes described retaining a field as
if we had implemented it. Passing Python clips does not establish portability.

This is not evidence that every effect has become a separate Python spell
executor. The reviewed graphics owners select recipes, rigs and media through
data; spell-name branches are concentrated in offline authoring/import scripts
and demonstrations. Complete causal lineages, independent latest/history and
absolute-time playback remain present. Those foundations should be preserved.

The immediate design correction is to make coordinate ownership and authoring
ownership explicit. The user accepts properly tuned numerical placement that
remains stable: a comprehensive per-frame keypoint system is not required.
Existing measured keypoints can be used where warranted. A constant offset is
not a defect merely because it was hand tuned; conflicting transforms and
accidental cross-spell inheritance are the relevant problems.

## Scope and evidence

- Reviewed the working tree on `codex/recovery-design`, HEAD `7f77c57e79`.
  Existing uncommitted spell integration and the subsequent `liftY=-12` change
  are included. This review changes documentation only.
- Compared the actual NeuroClient checkout at
  `/home/tommaso/Dev/NeuroClient/app`, revision
  `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`, the imported baseline.
- Read event projection/reduction and choreography, actors/equipment/conditions,
  cast/projectile attachment and sampling, importers, scene/world drawing,
  depth/area masks, particles/residue, and the relevant tests and source oracles.
- Ran metadata-only inventory and the **real TypeScript validators** against
  current records. No encounter generation, media recapture, image scans or
  performance audit was needed. No full game/test suite was run for this review.
- Independent reviews: [anchors, formats and authoring](GRAPHICS_REVIEW_ANCHORS_AND_STUDIO_2026-09-20.md)
  and [timeline, reduction and ECS ownership](GRAPHICS_REVIEW_TIMELINE_AND_ECS_2026-09-20.md).
  Their source references provide the detailed evidence behind this report.

Source locations below refer to this working-tree snapshot, not a clean HEAD.
The review is an architectural assessment and concrete compatibility probe;
it does not claim exhaustive visual correctness of every existing asset.

## What “data driven and portable” must mean here

There are three separate requirements:

1. **Content authoring:** a weapon, spell, rig or prop selects existing behavior
   with passive records rather than requiring its own executor.
2. **Shared semantics:** both consumers agree what a release frame, body socket,
   media pivot, child join and world contact mean. Matching field names alone
   does not establish this.
3. **Renderer implementation:** Pygame and Pixi implement projection, sampling,
   compositing and drawing for those meanings. JSON cannot replace these
   algorithms, and backend mechanics must not acquire pixel-placement fields.

The intended ownership remains:

```text
native events -> permitted complete player lineages -> latest state
                                  |
                                  +-> historical state + authored recipes
                                      -> bound causal timeline
                                      -> absolute-time samples
                                      -> projection / media / composition
                                      -> Pygame drawing (or a future TS renderer)
```

Reduction is necessarily code that understands event facts. The original
NeuroClient also had code for reduction, leaf playback and child joins. We do
not need to author D&D rules, visibility, or an event interpreter in Studio.

## Inventory: substantial data, with a narrower implemented subset

These are loaded metadata counts, **not counts of fully supported animations**.
The animation inventory explicitly included all seven packaged rig files.

| Inventory | Count | What the count actually establishes |
| --- | ---: | --- |
| Spell/effect draft keys | 15 | Fourteen spell identities plus the Ice Knife burst child recipe |
| Attack / shove recipes | 5 / 1 | Shared action recipes, with local authored attack variants |
| Body-action recipes / local aliases | 81 / 12 | Imported action rows and selected runtime bindings, not 81 validated effects |
| Condition recipes | 141 | Membership/presentation records; some populated layer features are unsupported |
| Body rigs | 8 | Modular root plus goblin, orc, wolf, skeleton and three demons |
| Projectile asset records / storage overrides | 31 / 10 | Metadata includes assets not selected for shipped playback |
| Action-media assets / body-release materials | 10 / 4 | Strip/particle assets and material-specific authoring |
| World image resources | 214 | Pivots, dimensions, scale and local resource identities |
| Prop bindings / ground-device bindings | 5 / 3 | Levers, torches, chest, and three spike-trap variants |

A percentage of “data-driven lines” would obscure the issue. A large data file
can still require an unsupported interpreter, and a small shared sampler can
correctly serve hundreds of records.

| Area | Authored data now | What must accompany it in TS |
| --- | --- | --- |
| Modular and packaged actors | Layer categories, facing rows, frame counts, semantic clip maps, origins and body anchors | Rig resolution and composition; the resolved Python item-variant ledger also needs export or its existing TS equivalent |
| Attacks and equipment | Clip/rate/contact choices, weapon-specific and damage-type variants, recorded active gear | Variant matching, contact dispatch and slot composition; current weapon-selection extension is incompatible with old TS |
| Spells/projectiles | Original drafts plus local sockets, phase timing, registration, palettes and paged-media bindings | Explicit support for local additions and agreed attachment transforms |
| Walk/jump/OA/forced movement | Imported context parameters and selected rig clips | Causal movement composition, jump launch reactions, one body cycle per flight, interrupted sub-tile position |
| Conditions and body-only actions | Membership recipes, body/color/alpha/feedback, action anchors | Existing supported subset plus missing equipment/appearance layers and selected media tracks |
| Props and traps | Real observed state, per-pose pictures, finite transitions and end frames | Current finite state-field bindings and contact timing; these are local world data, not Studio spell JSON |
| Terrain, stairs, walls and area effects | Asset pivots, face data, stair supports and world bindings | New height/depth and wall-contact algorithms; old client depth code is not equivalent |
| Blood/bones and other residues | Native receiving regions/amounts, particle targets, kernels, families and palettes | Particle sampling and a currently Python-authored procedural floor material |
| Water and UI feedback | Water parameters and feedback styles | Shared material/math implementation and ordinary renderer/UI layout code |

## Finding 1: the current bundles are an undeclared Studio dialect

The files still say `schema: neuroclient.spellStudioDrafts`, `version: 6`.
Running NeuroClient's actual validator gives:

- All eight baseline materialized drafts validate.
- Of the nine approved combat spells, **seven current recipes reject**:
  Acid Splash, Guiding Bolt, Eldritch Blast, Fireball, Ray of Frost, Ice Knife
  and Chill Touch. New socket/body-anchor or phase fields are outside that
  client's accepted format.
- Fire Bolt and Magic Missile validate, but that does not imply equal visuals.
  Isolated probes show `sourceSheet`, `hitFlash.palette`, `cast.enabled` and
  `holdReleaseForVolley` can pass their containing validation while the original
  runtime does not consume them.
- The new ice asset records reject `anchorsByFacing`; an impact-only Fireball
  asset also contradicts the old requirement for a travel phase.
- Importing the current attack variant table rejects a duplicate match: old TS
  drops `sourceItemIds`, so the morningstar-specific match collapses into the
  piercing fallback's match. The current weapon table is not directly reusable
  there either.

Source owners: `game/animation_types.py`, `game/animation_data.py`, local
`game/data/{spell_recovery,ice_spells,codexfx}` bundles, and the actual TS
validators/consumers identified in the independent format review.

**Implication:** the values remain useful authored content, but copying them
into the unchanged editor/client either fails or changes behavior. Calling them
“the original schema” hides work that a port really needs. Adding more aliases
or merely changing the version number would not implement that work.

## Finding 2: positioning has more than one owner

The relevant chain is `game/animation.py:350`, `:528`, `:540`, followed by
`game/animation_draw.py:450`:

- Legacy sprite delivery incorporates rig-root padding and canvas-center
  registration. Geometry delivery has a different anchor-basis path.
- New body targets use `rig.body_anchor`; new per-facing asset registration
  bypasses part of the old center compensation.
- Source sockets override another anchor path and currently live in spell
  recipes as measured frame-pixel coordinates, although they describe a
  particular actor animation.
- Recipe-local `liftY`, forward offsets and media offsets remain additional
  placement controls around those paths.

This can produce a good local picture, but it makes it difficult to answer
“where is the actual body contact?” without tracing the selected asset and
recipe through multiple transformations.

The latest example is explicit: `devtools/import_ice_spells.py:119` puts
`liftY=-12` on Ray and the incoming Ice Knife recipe, after copying the ground
burst. That solved the reviewed picture with a per-recipe correction. It did
not establish a common upper-torso attachment. The older Fire Bolt appearance
is also affected by its canvas registration; it is not an anatomical oracle.

The modular body anchor is `(64,72)` in a 128-pixel cell with ground-origin
offset 41. Its interpreted contact is 15 source-sheet pixels above support,
before actor and camera scaling.
The wolf has a different cell and anchor. A shared numerical recipe correction
is not proof of anatomically equivalent contact across those rigs. This is a
contract/coverage finding, not a claim that we observed every rig fail.

The clean distinction is:

| Authored fact | Correct owner | Is manual authoring itself a problem? |
| --- | --- | --- |
| Feet/support position within a character sheet | Rig registration | No; the art needs registration |
| Hand position through a particular clip/facing | Rig/clip socket data | No; measured per-frame positions can be appropriate |
| Projectile tip or impact origin in a transparent cell | That media asset's registration | No; padding must not masquerade as world geometry |
| “This delivery contacts the torso” | Recipe selects a semantic attachment defined by the rig | No; intentional target selection is content |
| A temporary upward nudge because the selected path appears too low | Currently a spell recipe/importer | It is a compensation until its relation to the socket and media pivot is demonstrated |
| Height, camera rotation, world support and trajectory | Shared projection/sampling | Code is required, with consistent units and order |

Do not infer sockets automatically from opaque pixels or move pixel coordinates
into native damage events. Use the alignment data already available, with a
clear owner. A genuine artistic offset can remain when its purpose is explicit;
we should remove duplicated correction, not forbid art direction.

## Finding 3: importers have become authoring programs

Offline conversion is legitimate and keeps Godot/Bun/source scans out of game
startup. But it is currently doing more than exporting one authored contract:

- `devtools/import_spell_recovery.py:82` clones another spell and authors colors,
  timing, sockets and delivery changes. Fireball copies sockets from `drafts[1]`
  at `:139`, depending on another spell's position in the generated list.
- `devtools/import_ice_spells.py:32` starts from the current Guiding Bolt record,
  inheriting its cast/socket choices before overriding selected values.
- `devtools/bake_spell_palettes.py:67` reads and rewrites the generated recipes
  and bindings as another authoring pass. Original baseline rows are kept
  separate, which is useful, but reproducing final content now depends on the
  sequence of these passes.

These are not per-spell branches in the frame loop. The issue is **where the
authoritative choices live** and whether a later import silently restores old
choices or inherits unrelated ones. The delivered art manifest, importer code,
generated recipe and later palette pass do not currently form one obvious
authoring boundary.

A correction should identify an authoritative record for each choice and make
converters consume it. It does not require another build system or another
configuration language. Intentional shared cast/rig data should be referred to
as such instead of copied indirectly through an unrelated spell/list index.

## Finding 4: retaining a Studio row is not implementing its tracks

The ECS review distinguishes populated gaps from dormant possibilities:

| Existing field/content | Current behavior | Assessment |
| --- | --- | --- |
| Four condition weapon-coating modifiers and Dragon Wings appearance layer | Loaded; reported unsupported by `condition_animation.py:88` | Real populated presentation coverage gap |
| Greater Invisibility, Haste and Healing potion action-media tracks | Loaded; reported unbound by `body_action.py:108` | Omission explicitly accepted by user; drinking/body contact already works; no restoration task |
| Walk/jump optional media and recovery | Typed legacy fields; empty media and disabled recovery | Inactive extras, not a current missing animation or implementation task; walking/jumping already play |
| Actor-only spell caster layers | Reported unbound when enabled | Shared capability gap, dormant for the current five actor-only spell recipes |
| Attack hidden slots/media and non-bolt projectiles | Explicitly rejected | Bounded support; current attack overrides do not select those unsupported features |
| Original area `phases`, `geometry` and `sprite` controls | Accepted but not sampled by the selected cast path; ground effects currently use projectile impact timing/media and the local `surfaceReveal` | Shared-semantics gap; editing original area phase duration does not control this path |

Existing reporting is preferable to pretending an unsupported track played.
Do not turn the dormant rows into urgent invented bugs. Likewise, loaded 141
condition recipes are not proof that all 141 presentations are complete.

**Potion clarification after the user's follow-up:** the prior recovery status
already records that the original strip was absent from the reference checkout
and that the user explicitly deferred this VFX work. The recipe uses `Taunt`,
hides weapon/glow/offhand, and presents the native effect at frame 8; those
features work. Its additional nine-frame `Effect2/Special1` strip is not played.
The local True Seeing potion aliases that original drinking recipe and inherits
the same omitted strip. The user subsequently confirmed this omission is
acceptable: potion/source VFX restoration is not pending work. The current
focus is on the target side of spells. This is not a broken drinking action
or condition mechanic. Weapon-coat
modifiers are specifically tints/saturation/brightness on equipment slots;
their absence must not be exaggerated into missing animated flame effects.

**Jump clarification:** ordinary walk/jump playback is implemented, including
height-aware trajectory, one body cycle fitted to airtime and prelaunch jump
reactions. `walkMedia`/`jumpMedia` describe extra effect layers;
`walkRecovery`/`jumpRecovery` describe an optional additional body animation
after movement. Their empty/disabled values do not remove landing or any part
of the implemented jump. Do not turn these inactive legacy fields into a task.

A direct-damage cardinality limit also exists in attack/application binding.
No new native failure was demonstrated here; it belongs in the support boundary,
not in a speculative emergency mechanics rewrite. See the ECS review for the
precise distinction from working nested and volley applications.

## Finding 5: floor materials and new scene behavior require an actual port

### Residue

The native receiving regions and amounts are not replaced by visual particle
guesses. `game/particle_media.py:53` drives particles toward the actual retained
regions, and `game/residue_media.py:33` shares landing templates with the floor.
That is a useful boundary to preserve.

But the final blood look is not wholly authored in those JSON records.
`game/surface_residue.py:255` hardcodes the procedural density/noise, threshold,
wet highlights and default blood color arithmetic. JSON supplies targets,
kernels and optional counterpart palettes, not the entire material. Ash texture
construction has similar code-owned appearance in `:80` and `:146`.

This is a small software material implementation, not evidence of fake native
tile state. To reproduce its look in TS we need the material semantics as well
as its parameters. Decide which values are intentional artist controls and
which are fixed algorithm details; do not dump every constant into JSON.
Water already has a useful precedent: shared material inputs and a frozen
source oracle for the implementation (`tests/game/test_water.py:54`).

### Terrain, height and occlusion

`game/projection.py:220` derives painter order from physical contacts and roles.
`game/area_media.py:92` partitions an area picture between ground and reachable
wall faces. It is shared area composition, not a Fireball-name special case.
These algorithms are valid renderer responsibilities.

They are also new behavior absent from the old flat depth helper in
`NeuroClient/app/src/render/worldDepth.ts:20`. That helper has no equivalent
height input. Copying world-bindings JSON alone cannot reproduce the new scene.
The area implementation uses boundary geometry and sprite masks at the impact
height; it is not a general volumetric depth renderer.

Some scene support is intentionally finite: `game/app.py:147` matches the
three-support Earth stair shape; wall/door drawing recognizes particular
material/structure combinations; `game/assets.py:44` binds prop changes through
`is_open` or `is_engaged`. Asset registration is data, but adding a fundamentally
new structure/state channel can still require a shared renderer capability.
Do not advertise a universal world-object authoring system or build one merely
because this review found finite support.

## What the existing tests do and do not prove

`tests/game/test_animation.py:31` and `test_magic_missile_timing.py:20` deliberately
load `authored_bundles=()` and compare to the actual original queue's retained
oracle. This is valuable evidence for the baseline timing contract. It does
not cover the extended spell dialect, new palettes or all new placement paths.

New Python tests and four-camera clips establish useful current behavior,
native replay and selected media coverage. A no-gap gallery does not establish
cross-runtime equivalence, anatomical correctness or editor round-tripping.
The successful local reviews of the `-12` patch established its bounded effect;
they were not a review of the entire attachment design.

Do not add runtime source hashes, filesystem audits or event regeneration to
address this. Authoring compatibility can be checked offline on selected
metadata. The user's deferred video-pixel comparison idea remains deferred.

## Proposed next work, in order

This is a design proposal following the requested review, **not an implemented
refactor**. Both anti-slop and anti-OOP reviewers approved the sequence; their
scope and corrections are recorded below.

1. **Resolve contact ownership with stable authored values.** Trace representative
   old and new media through support -> actor attachment -> media pivot.
   Specify units, scale and rotation order once. Reuse the existing tuned values
   and alignment records; this does not require full rig/clip keypoint tracks.
   Use measured animation keypoints selectively if a demonstrated case needs
   them. Preserve approved appearance and remove only demonstrated duplicate or
   conflicting corrections, rather than treating all manual tuning as suspect.
2. **Make the extended contract honest.** Separate unchanged Studio fields from
   the finite additions we actually use. For each addition, identify its Python
   meaning and TS/editor adaptation. Use explicit version/extension handling;
   accepting unknown fields is not support. Keep original source data intact.
   No parallel replacement Studio schema or universal track interpreter.
3. **Give authoring choices one owner.** Remove accidental cross-spell inheritance
   and positional dependencies from the affected importers. Keep media packaging
   separate from decisions about cast/body/contact/palette behavior. Retain
   ordinary offline exports; do not introduce a source-auditing runtime.
4. **Prove that bounded contract across representations.** Use existing recorded
   player lineages and small reference cases comparing contact points, phase
   frames, selected layers and causal boundaries. Include modular and packaged
   rigs, four camera corners, different heights/scales and noncanonical angles.
   Preserve launch-time jump reactions, one jump cycle, independent progression,
   historical gear and interrupted corpse positions. This is not a new pixel
   regression platform or another 200-spell implementation project.
   Selected offline TS/schema checks are sufficient for this bounded correction;
   bringing up or porting the whole old client is not a prerequisite.
5. **Resume existing capability work with honest coverage.** The already-populated
   condition layers are concrete candidates. Potion/source VFX omissions are
   accepted; inactive walk/jump extras create no task. Reuse the current shared
   composers for selected work. Define material/depth equivalence when porting those
   renderers, without blocking this bounded attachment correction on every shader.

Success means a new compatible rig/asset uses its own registration and the
shared contract without requiring another spell-specific alignment repair.
It does not mean every possible future art pack or mechanic is already supported.

## Review status

Both reviewers independently approved this consolidated assessment and proposed
sequence on September 20:

- **Anti-slop/format:** verified the actual validator results and attachment
  distinctions. Requested two clarifications, now incorporated: name the rig
  anchor's units as source-sheet pixels, and list the original area's unconsumed
  controls rather than implying full area-schema execution.
- **Anti-OOP/ECS:** independently recounted the inventory and confirmed that
  the sequence preserves causal playback and the user-corrected jump/history
  behavior. Requested the explicit offline-check scope in step 4, now included.

No runtime refactor, asset change or new framework was implemented. This report
and the recovery-plan entry are the handoff for selecting the bounded correction.
