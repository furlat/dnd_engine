# Fixed-character renderer integration preparation

**Deeper source inspection:** the [reviewed animation mapping study](FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.md)
and [150-character mapping JSON](FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.json)
now supply 600 basic selections, 422 primary combat selections and 12 focused
extra clips with exact ZIP members, dimensions, hashes, visual timing windows
and full-frame evidence. This architecture document and the initial catalog
alone were not an actual animation-mapping pass. The deeper pass also establishes
that some Shadowless exports omit attack trails or major FX; selecting them
cannot be treated as simply removing shadow. See the study's exact review
coverage and remaining calibration holds before implementation.

Requested scope: inspect modular versus whole-character rendering, prepare
data for the retained fixed-art roster, and identify how registration and basic
action binding can scale. This pass adds an offline catalog tool and preparation
data. It does not import artwork, register new creatures, or change gameplay or
renderer behavior. Animals and excluded modern variants remain outside scope.

## Human direction and implementation ownership

The user's 1 October clarification controls the next production work:

> Most of the renderer is constructed around the original modular spritesheets.
> We need a unified way to project that into these asset packs through data.
> Then constrain actions and weapons so the authored characters fit the visuals.

**Implementation belongs to the main production thread.** This art-led chat,
`01a0f3b4-277a-7fa0-9356-d1c9de5527b8`, owns source inspection, character design,
catalog preparation and this handoff. It does not own implementation of the
renderer changes, runtime schemas, imports or native content registration.
The main production thread's ID has not been specified in this instruction;
the user explicitly instructed **do not send the handoff to production when
done because that thread is busy**. Keep this handoff in the repository for
later pickup. Do not message, wake, create a task in, or dispatch work to the
production thread as part of completing this documentation.

The goal is a unified data-driven projection, not merely enough filename
aliases to make fixed sheets enter a modular animation pipeline. The existing
modular rig becomes one explicitly described visual family under that contract.
Preserve its accepted behavior while removing implicit dependencies on its
cell size, frame count, action numbering, layers, sockets and timing wherever
those assumptions govern other families.

## Target projection contract for the production handoff

The following are required meanings, not a prescribed new JSON schema or
request to replace the existing typed records. Reuse `BodyRig`, `BodyClip`,
appearance, action recipes, retained facts and the common compositor wherever
they already represent them.

| Authored data | Meaning across modular and fixed families |
| --- | --- |
| Visual family and appearance identity | Select a stable, disclosed body/outfit independently of mechanical species and cosmetic palette |
| Sheet layout | Exact cells, frame counts, direction mapping, source members and available layers |
| Registration and scale | Support pivot, torso/rest anchors, optional action sockets and deliberate visual scale |
| Action semantics | Describe the actual movement, strike, shot, cast, reaction or state; map it to that family's source clips |
| Temporal markers | Action-specific speed, contact/release, recovery and settlement using the selected clip's actual clock |
| Layer and VFX policy | Which effects are baked, independent or intentionally absent; separate ground shadow from body elevation |
| Supported visual states | Depicted weapons/hands/shields, loadout transitions, resting/condition states and explicit coverage gaps |

The desired flow is:

```text
native content and declared action
  -> retained observer-admitted identity, equipment, action and state facts
  -> authored visual family / appearance selection
  -> shared semantic action resolver + family-specific presentation data
  -> selected clip, layers, timing, sockets and registration
  -> existing timeline sampling and common world composition
```

Vendor `Attack1` or the modular `Attack3` vocabulary may remain local clip keys,
but neither is a universal meaning for slash, bow release or spellcasting.
Data projects a semantic action to the actual clip; a source filename must not
decide native rules. Resolver output must stay coherent across source motion,
projectile release, target response, recovery, shadows and condition attachment.
Selection uses recorded facts, not live inventory or whatever files happen to
be installed during historical playback.

## Content constraints follow visual authoring

After the family capabilities are understood, deliberately author each fixed
character's permitted loadout, attacks, spell choices and special abilities to
fit its inspected visuals. These are native content choices made before play,
not renderer filters that hide legal actions or change rules after an event.

- Start with SRD 5.1; use 5.2 only with explicit 5.1 adaptation. A changed
  weapon, omitted source attack, changed spell selection or additional ability
  is an expressly recorded authored variant and needs balance review. It is
  not an unchanged canonical SRD match.
- Fixed humanoids and skeletal characters serve special roles because modular
  humanoids/skeletons cover ordinary freely equipped bodies. Fixed Goblin,
  Orc, Devil and Zombie packs also need base SRD faction coverage alongside
  authored elites. Preserve this distinction when selecting pilot imports.
- The Witchdoctor uses its sword/shield and poison presentation; the inspected
  Berserker uses its long/short sword pair; the Nomad uses its axe/shield.
  These corrections supersede assigned-weapon labels. A motion can support a
  deliberately authored ability, but colored pixels alone do not supply its
  damage, saving throw, condition or action cost.
- Do not grant a bow attack to an axe-only fixed character merely because
  canonical source content has a bow. Author a declared matching loadout variant,
  choose a genuine bow-capable family, or retain modular presentation for that
  canonical loadout. Do not silently edit the global SRD creature definition.
- Baked gear limits authoring freedom. Dynamic disarm, looting, shield loss,
  equipment replacement and imposed conditions still need an explicit production
  policy and visual coverage. Removing an authored equipment-switch action
  does not prevent an opponent from disarming the character. Do not disable
  native rules or leave misleading pixels without reporting the unresolved state.
- Unsupported capabilities remain explicit in authoring/review. The production
  owner must decide how they are presented; an Idle fallback is not certification
  that an action is visually supported.

The offline catalog is an input to this authoring process. It must not become
a second native rules registry or a runtime mechanism that generates powers
from asset names. The main production thread should resolve the existing
one-content-reference/one-rig limitation as part of stable appearance selection,
without requiring a new mechanical species for every art variant.

## Finding

The Pygame renderer already supports fixed sheets through the same `BodyRig`
sampling/composition path as modular characters. Seven fixed bindings exist in
`game/data/rigs/`; the retained roster is not generally registered or authored
for those runtime contracts. The architecture is usable. The action/profile,
appearance-selection and capability boundaries need work before a bulk import.

“None of these sprites can be used” is too broad: selected fixed Goblin, Orc,
Demon Beast, Skeleton Archer and Grey Wolf rigs already demonstrate the route.
Their registration does not establish full action coverage or fidelity to every
native creature loadout. The 150 character catalog is a new authoring backlog,
not a claim that every candidate is new or runtime-ready.

## Modular versus fixed rendering

| Concern | Modular root | Fixed character |
| --- | --- | --- |
| Rig metadata | Root `RigTables` converted to `BodyRig` | Typed binding JSON supplies `BodyRig` |
| Appearance | Body/head/beard and visible equipment facts select categories | One baked category per appearance slot; body, optionally separate shadow/effect layers |
| Clip names | Existing root semantic names | Semantic key maps to explicit vendor `source_clip` and sheet URLs |
| Geometry | Root cell dimensions and rows | Per-rig cell dimensions, verified facing rows and per-clip frame count/FPS |
| Composition | Multiple slots | Usually fewer slots; same sampler/drawer |
| Support/body placement | Authored ground origin and attachment points | Same fields, measured for each visual family |
| Equipment changes | Retained visible loadout changes layers | Baked weapon remains in pixels; alternate state requires actual supporting art |
| Identity selection | No creature ref selects the root; authored root refs can also select it | Exact creature content ref resolves to one registered rig |

Owners inspected:

- `game/animation_types.py:669`: passive `BodyClip`/`BodyRig` records.
- `game/animation_data.py:70`: `resolve_actor_layers`; the non-root branch
  ignores modular equipment composition and authors shadow alpha as 0.5.
- `game/animation_data.py:205`: root conversion; `:227` additional rig/resource
  and creature-reference registration, with duplicate rejection.
- `game/combat.py:66`: actor rig selection from retained disclosed creature
  identity; an unbound content identity raises rather than silently guessing.
- `game/animation_draw.py:242`: row loading; `:534` common composition and placement.
- `game/encounter_play.py:111`: existing encounter selects binding JSON files.
- `devtools/import_fixed_rig.py`: selected-member import, source hashes,
  dimensions and contained destinations. Reuse this importer after authoring.

The root/non-root appearance branch is an existing limitation, not a reason to
introduce a separate renderer class or a per-pack action executor.

The separate TypeScript NeuroClient reference is less general at the sheet
slicing boundary: `app/src/render/SpriteAssetRegistry.ts:29` uses shared
`CELL_W`, `CELL_H`, `SHEET_COLS` and `FACING_ROW` for its ordinary directional
rig loader. `PresentationAssetService` owns loading/readiness, but delegates
that slice to the registry. `AnimatedEntity` composes modular categories with
bottom-center anchors. Its directional-strip helper derives columns but still
uses shared cells/rows. The Python typed per-rig path is the maintained game
integration target; the catalog does not make arbitrary 192px/vendor-layout
sheets compatible with that separate TypeScript loader.

## Scaling and anchoring

Current placement is data-driven. In source pixels, support is
`(cell_width / 2, cell_height - origin_y_from_ground)`. `body_anchor` is a
separate attachment point; death/rest anchors and optional per-frame pose sockets
have distinct purposes. Alpha bounds and the bottom edge are not substitutes
for measured support registration.

Drawing scale is `appearance.visual_scale * condition.scale *
(TILE_WIDTH / root_tile_width) * camera.zoom`; an independently authored
`visual_scale_x` can stretch width. For fixed characters prefer uniform scaling
unless a deliberate distortion is authored. Mechanical creature size must not
automatically select pixel scaling or occupied cells.

For example, the Ogre Idle sheet is 2880×1536, with 192×192 cells, 15 columns,
and verified E/SE/S/SW/W/NW/N/NE rows. Its authored support pivot and FPS are
absent from the vendor metadata and still require documented visual authoring.
Existing modular Ogre placeholder multipliers do not calibrate this fixed art.

The live Python drawer has a ground-origin offset beyond bottom-center. The
earlier consultation's Pixi `anchor(0.5,1)` described the TypeScript modular
convention; it did not establish the fixed Ogre's support pivot.

## Boundaries that prevent automatic bulk readiness

1. **Attack selection is shared, without rig criteria.** `AttackProfileMatch`
   and `select_attack_profile` match attack facts, items, delivery and outcome,
   but not the actor rig. Different vendor swings can therefore inherit the
   same contact frame and VFX recipe after a name alias. That is not proof of
   correct motion or timing.
2. **Missing action behavior is uneven.** `game/attack.py:252` can display Idle
   with a media gap for a missing projectile body, retaining root timing; a
   missing melee clip returns no bound attack timeline. Other body consumers
   use strict clip resolution. Do not treat diagnostic fallback as supported art.
3. **Short clips are real.** `BodyClip.frames` is variable while many authored
   marker fields use `BodyFrame` 0–14. A six-frame Block cannot accept a shared
   marker at frame 7. Extend marker range only if an actual selected long clip
   requires it; validate all chosen markers against the selected clip now.
4. **One creature reference selects one rig.** Duplicate creature mappings are
   rejected. Do not bind every Orc variant to the same core Orc reference or
   invent mechanical species for cosmetic palette selection. Current appearance
   has scale and modular categories, but no general fixed-variant selector.
   Native special creatures can use their real authored identities; cosmetic
   choices need a retained, disclosed appearance identity before playback.
5. **Baked loadouts constrain state changes.** Disarm, bow/sword switching,
   dropped gear, shield removal and unarmed actions need art-state coverage.
   Hiding modular weapon slots cannot erase a weapon baked into the body sheet.
6. **Shadows and built-in VFX need explicit layer policy.** Do not combine a
   vendor combined shadow with another ground shadow or apply an assumed opacity
   twice. Color/effect pixels do not grant a native damage type or condition.
7. **Runtime slice validation is incomplete on its own.** The row loader uses
   declared geometry to take subsurfaces; it does not reject every oversized
   source sheet. The existing importer verifies exact selected dimensions.
   Offline coverage also needs meaningful/blank-frame and layer checks.
8. **Native actions need coverage beyond attacks.** Movement, dodge/roll,
   cast/recovery, reactions, damage/death, prone/rest, equipment transitions and
   selected authored specials all consume body clips. Alias availability alone
   does not certify those event-driven schedules.

## Prepared data

`devtools/catalog_fixed_rigs.py` reads the reviewed roster and original ZIP
headers. It writes an offline catalog, not a runtime binding schema. It records
all source sheet members per character, layer role candidates, exact PNG sizes,
bit depth/color type, candidate cell/frame geometry, observed gear/VFX, basic
alias candidates and explicit missing authoring fields.

The generated catalog is
`.runtime/pack-study-20260930/integration-preparation/fixed-character-catalog.json`.
It covers **150 characters and 8,787 sheet members** across eight packs. Under
the declared eight-square-row hypothesis, cells are 128 or 192 pixels and clips
have 6, 7, 8, 10 or 15 columns. Direction order and meaningful frame coverage
remain verification tasks; headers alone do not prove them.

All 150 have candidates for Idle, Run, TakeDamage and Die after seven explicit
vendor-name exceptions. 62 lack the conservative Rolling/Roll 1 name alias.
This is a name-coverage finding, not evidence that those characters cannot dodge.
No attacks, spells or specials are auto-approved. `CastSpell` on the reviewed
Ogre is a jumping pose, illustrating why filename semantics cannot be trusted.

Rebuild with:

```bash
uv run --no-sync python devtools/catalog_fixed_rigs.py \
  --review .runtime/pack-study-20260930/srd-first/illustration-comparison/metadata.json \
  --archive-dir /mnt/c/Users/tommaso/Downloads \
  --output .runtime/pack-study-20260930/integration-preparation/fixed-character-catalog.json
```

## Integration sequence

1. Generate this catalog offline. Review simple aliases once per family, then
   record character-specific exceptions. Do not scan ZIPs during game startup.
2. Measure support/body/rest anchors, choose source FPS and uniform scale,
   verify row order and select exact body/shadow/effect members. Retain originals.
3. Author stable native creature identities and separate observed appearance
   choices. Reuse existing content-to-rig binding for actual native identities.
4. Add the smallest shared per-rig action presentation data needed to select
   clip, speed, contact/release markers, sockets and effect policy before timeline
   compilation. Keep mechanics/events unchanged and apply the same resolution
   contract to relevant attack, cast and body-action consumers. This is proposed
   runtime work, not implemented by this preparation pass.
5. Generate explicit `BodyRig`/`BodyClip` binding JSON and resource/provenance
   tables from reviewed data; use the existing importer and private art pipeline.
6. Verify a fixed melee actor, genuine archer, caster and natural-attack actor
   against real recorded native events in four camera quadrants. Include hit,
   miss, critical, damage/death, conditions and unsupported gear-state reporting;
   retain modular actors as regressions before expanding the batch.

## Anti-slop and anti-OOP review

Review roles are included here as required by the repository. The author performs
both reviews because the user requested personal work and revoked delegation.

- **Anti-slop reviewer:** source headers establish file geometry only. Alias
  candidates are not approved actions; nullable pivots/FPS/markers do not become
  invented defaults. Counts include alternate combined/layer sheets, not 8,787
  distinct playable animations. No new readiness or balance claim is made.
  The unified projection is an implementation handoff, not an implemented
  resolver. Native content constraints must be explicit adaptations; unresolved
  dynamic gear/condition states cannot be hidden by restricting authored actions.
- **Anti-OOP reviewer:** preparation is a flat offline CLI and JSON records.
  Existing passive rig records, shared compositor, event facts and importer stay
  the owners. No entity subclass, per-pack renderer, action executor or second
  gameplay registry is introduced.
  Unified projection means shared semantic resolution with family-specific
  passive data, preserving historical observer facts and existing system owners.

Validation evidence is recorded beside the generated catalog. No production
engine, renderer, registration or media files were changed in this pass.
