# Render authoring, typed contracts and ECS audit — 2026-09-23

## Scope and conclusion

This is a read-only review of the present rendering authoring surface, its consumers, and the original NeuroClient Studio format. It follows `RECOVERY_PLAN.md` and the global `bug-fix` skill. No production code or assets were changed. Importer ownership, complete presentation coverage, event scheduling, and XYZ geometry have parallel reviews; overlaps are identified below rather than treated as independent discoveries.

The code still has the intended basic architecture: passive recipe and rig records, shared compilers and samplers, and rendering driven by disclosed historical events and state. The new features do not require a return to per-spell or per-object classes. Several additions to Studio are necessary and sensible: explicit attachment bases, registered finite media, per-rig sockets and rest poses, device emission, condition lifetimes, and geometric media registration.

It would nevertheless be inaccurate to call the whole surface strictly typed, entirely authored in JSON, or directly executable in the old TypeScript client. The important weaknesses are inconsistent authoring boundaries, accepted fields whose consumers have narrower semantics, a reproduced mixed-track completion defect, and runtime draw semantics stored in an untyped diagnostic tuple. These are concrete cleanup targets. They do not justify a new universal animation framework or rewriting the approved output.

Findings below distinguish **reproduced defects in supported combinations**, **active ownership weaknesses**, and **dormant/unsupported fields**. A malformed-data example is not evidence that a current accepted asset is malformed. An unimplemented dormant field is not evidence that the corresponding currently approved spell is visually missing.

## Evidence and checks performed

Read the relevant authoring models, loaders, compilers, render consumers, presentation contract, and focused tests. Loaded `AnimationData` without loading the raster corpus, inspected selected recipe combinations, and performed data-only compiler/schema probes. This review did not run the full suite or recapture every approved clip.

The loaded catalog contained:

| Bound family | Count | Qualification |
| --- | ---: | --- |
| Spell/action drafts | 76 | Includes an action alias; the separate coverage command reports 75 selected spell bindings |
| Attack recipes | 5 | Weapon variants are additional data within recipes |
| Body-action recipes | 82 | Includes retained original content |
| Condition recipes | 144 | Not a claim that every optional track is executable |
| Condition-media bindings | 92 | Separate media lookup from condition behavior recipes |
| Projectile/finite-media assets | 346 | Asset metadata, not 346 distinct spells |
| Local projectile storage records | 324 | Storage adapters for selected media |
| World animations | 13 | Does not inventory every environment/device/portal bank |
| Maintained spatial bindings | 11 | Includes legacy, floor, clump and volume composition |
| Deposit bindings | 6 | Separate material variants |
| Device bindings | 2 | Separate from world-animation inventory |
| Portal bindings | 2 | Separate from world-animation inventory |

No currently selected draft combined `projectile` and `media`. All seven selected `area` records had `geometry.enabled = false` and `sprite = null`. Current rig validation already checks complete eight-facing body rows and per-frame socket arrays; it should not be described as wholly unvalidated.

## Findings

### 1. A valid projectile-plus-media recipe finishes before its finite media ends

**Reproduced latent execution defect; no currently selected recipe uses this combination.**

`StudioSpellDraft` accepts both `projectile` and `media` (`game/animation_types.py:430`). Cast media are rendered by the shared cast-media path. The direct/anchored compiler joins every finite media end into completion (`game/animation.py:1063`). The projectile compiler joins body, projectile and damage durations but omits `recipe.media` (`game/animation.py:1334` through `game/animation.py:1358`).

A data-only probe copied the selected Fire Bolt draft, added an existing Heal media track with `durationMs = 10000` and zero start offset, validated the resulting record, and compiled the same cast without a damage reaction:

| Quantity | Milliseconds |
| --- | ---: |
| Original Fire Bolt complete | 1582.395905111055 |
| Modified Fire Bolt complete | 1582.395905111055 |
| Authored media end, relative to cast start | 10583.333333333334 |

The accepted track therefore does not contribute to the transaction join and can be cut off when the cast is retired. This matters specifically because the desired growth model is composing shared tracks rather than adding spell-specific executors.

**Minimum correction:** use the same finite-media duration join in both compile paths. If the combination is intentionally unsupported, reject it explicitly at binding until supported. Do not create a third mixed-spell executor.

### 2. DrawCommand has an active, untyped semantic protocol disguised as evidence

**Active architecture weakness, independently confirmed; no wrong current pixel is attributed solely to it.**

`DrawCommand.evidence` is `tuple[object, ...]` (`game/draw_commands.py:17`), but it is not only optional diagnostic output:

- `game/app.py:362` uses indices 0 and 6 to separate live device and wreck commands.
- `game/app.py:367` uses index 1 as a world position for deposit visibility/lighting, then reconstructs the tuple.
- `game/app.py:1141` casts indices 8 and 9 into device facing and frame.
- `game/portal_draw.py:117` uses indices 6 and 0 to identify actor bodies, shadows and copies for real portal hiding/clipping.
- `game/animation_draw.py:845` and `game/animation_draw.py:890` also depend on ownership/role for bounds and feedback.

These contracts bypass typing even though the surrounding records are passive and typed. Changing a diagnostic tuple layout can change rendering behavior. Turning evidence collection off does not remove this protocol.

**Minimum correction:** add named passive command semantics for role, owner and relevant world contact; carry optional typed device pose where needed. Derive serialized diagnostic evidence separately. Preserve the compositional `DrawCommand`; this does not call for actor/device/deposit subclasses. Parent review owns the combined recommendation.

### 3. Storage schemas accept missing or contradictory storage sources

**Reproduced authoring-boundary gap; current installed assets were not found malformed.**

`ProjectileFrameLayer` exposes four optional alternatives (`pattern`, `pages`, `partsByFacing`, `parts`) without requiring one (`game/animation_types.py:531`). `ProjectileFrameStorage` similarly allows empty layers and no surface packet, or both (`game/animation_types.py:559`). `PackedSurfaceFrames` allows neither pattern nor components, an empty frame list, and unrestricted bounds (`game/animation_types.py:564`).

Schema probes accepted:

```json
{"blendMode": "normal"}
```

as a `ProjectileFrameLayer`, and a `PackedSurfaceFrames` record with `frameIndices: []`, `bounds: [1, -1]`, positive vertical scale and no storage source.

The consumer has a definite precedence: surface packets, then parts, then pages, then a pattern assertion (`game/projectile_media.py:203`, `game/projectile_media.py:229`, `game/projectile_media.py:248`). It indexes frame/facing arrays and formats packet paths only during sampling. Thus the declared type permits configurations whose failure occurs later, or whose competing source is silently ignored.

**Minimum correction:** constrain the actual mutually exclusive storage alternatives and cheap in-memory relationships at the existing parse/import boundary. This can be a small discriminated record or validators on the existing records. Do not scan raster folders, hash files, or add per-frame validation. Cross-asset frame-domain checks, where needed, belong in the explicit content binding/import test surface.

Some facing maps intentionally allow partial overrides, such as optional per-facing anchors. Others are indexed as complete maps. Do not impose eight required keys on every `FacingMap`; distinguish full maps from override maps at their real consumers. `BodyRig.validate_layout` already does this for body rows and pose sockets (`game/animation_types.py:640`).

### 4. Environment, device, portal and condition-media catalogs have weaker boundaries than Studio

**Active consistency/maintainability weakness; not a demonstrated current output regression.**

Studio and condition recipe records use strict Pydantic models, forbidden extra fields, frozen values, and finite numeric constraints. Several other equally important authoring files go from raw dictionaries into frozen dataclasses:

| Boundary | Evidence | Consequence |
| --- | --- | --- |
| General asset/world binding catalog | `game/assets.py:98`, `game/asset_types.py:9` | Casts and broad dictionaries carry source fields into rendering without the Studio constraints |
| World transition animation | `game/world_animation.py:48` | Raw rows construct frame/state maps, save hops, projectile and depth records |
| Environment art | `game/environment_art.py:112` | Frame/timing/pose/marker fields are copied from dictionaries; optional fields silently default |
| Cannon/device art | `game/device_art.py:61` | Camera/pitch/yaw/muzzle structures are positional; `DevicePitch.muzzle_pixels` and `forward_screen` are bare `tuple` at lines 17–18 |
| Portal art | `game/portal_art.py:59` | Aperture literals and positive timing/frame counts are annotations only; raw dictionaries construct records |
| Condition media | `game/condition_media.py:49` | Mode, basis, fade and sustain timing can bypass the stricter condition-recipe surface |

Frozen passive dataclasses are appropriate runtime values. The problem is not that they are dataclasses or that decoding exists. It is that schema constraints and typo handling differ arbitrarily between authored families, despite all of them being part of the portable presentation contract.

**Minimum correction:** type the small source documents at their existing loading boundary and give camera/muzzle arrays meaningful tuple aliases. Preserve one-time decoding and lazy raster loading. Avoid a generic schema registry or a second round of source validation on every render/startup.

### 5. The accepted Studio vocabulary is larger than the executed vocabulary

**Mostly retained/dormant source compatibility, with an authoring clarity gap.**

The legacy `StudioArea` geometry, sprite and phase fields remain typed (`game/animation_types.py:290`–359). Current runtime uses area presence to require a ground target (`game/animation.py:1156`) and consumes `area.surfaceReveal` (`game/choreography.py:761`), but does not execute the retained area geometry/sprite and shape/explosion phase representation.

Current Fireball, Sleep, Web, Burning Hands, Thunderwave, Gust of Wind and Ice Knife secondary-burst records all have area geometry disabled and no area sprite. Their actual visual output is provided by projectile/finite/maintained media. Some retained area phase numbers are nonzero despite not being the execution clock. They should not be offered as effective authoring controls for those spells.

Other unsupported routes are more explicit: projectile geometry variants, alternate travel assets, palette swaps, optional-media omission policy, cast equipment and death media are rejected or diagnosed by their compilers (`game/animation.py:1160` onward). `game/condition_animation.py:78` reports unsupported equipment modifiers and appearance layers. The five observed partial condition recipes are Dragon Wings and four weapon coats. These are known capability gaps, not silent evidence that all conditions are broken.

The earlier concern about recovery being unused is no longer true: recovery duration is joined in both direct and projectile compilation (`game/animation.py:1071`, `game/animation.py:1353`), and body actions have their own join. Jump's single-cycle airtime behavior should not be reopened on that basis. Potion optional media were deliberately deferred by the user; that is accepted scope, not a new blocker.

**Minimum correction:** make the executable subset explicit at selection/coverage time, including ignored non-neutral fields. Keep historical reference records intact. Do not implement dormant controls simply because the old schema contains them, or remove the working media implementation to restore an obsolete shape representation.

### 6. The same media-track type is accepted by consumers with different capabilities

**Latent authoring ambiguity; inspected current contact records fit the narrower consumer.**

`SpatialMediaBinding.contactMedia` accepts a complete `StudioMediaTrack` (`game/animation_types.py:1252`). `game/spatial_contact_media.py:90` converts it into a stationary cue at an observed ground contact. `game/stationary_media.py:35` consumes its asset, frame timing, facing, scale, alpha and depth, but does not apply the cast consumer's attachment selection, actor scaling, body/world offsets, emission points or target-vector orientation. There is no actor attachment context in that cue with which to apply several of those fields.

The current Grease ground-entry and Spike Growth damage contact rows are ground-authored, so this does not establish a present misplacement. It does mean that a type-valid body-attached contact track does not have the semantics its type suggests.

Movement/body-release media similarly share `MovementMediaTrack`, while their consumers support different subsets (`game/motion_media.py:26`, `game/action_media.py`). Some unsupported action combinations are rejected; locomotion conversion selects a subset of fields.

**Minimum correction:** constrain accepted combinations at the consumer boundary, or factor only a common finite-media core from attachment-specific fields. Avoid duplicating the full media schema or adding a universal attachment resolver with speculative contexts.

### 7. TypeScript reuse requires the local contract and shared execution semantics

**Important portability fact, not a reason to reject necessary extensions.**

Original NeuroClient `PersistedStudioSpellDraft` declares cast/projectile/area/damage/condition (`/home/tommaso/Dev/NeuroClient/app/src/render/spellAuthoring/types.ts:147`), and the original file accepts `neuroclient.spellStudioDrafts` version 6 (`types.ts:354`). Its Studio serializer reconstructs those exact fields (`app/src/ui/spellStudio/serialize.ts:22`): a naive round trip through that editor would omit local top-level `media`, `contact` and `childAttack`. Original validation also reconstructs the v6 file rather than supporting local `effectDrafts`.

The local contract correctly identifies `dnd.spellStudioDrafts` version 2 and documents the need for a future TS adapter (`game/data/PRESENTATION_CONTRACT.md:3`). The original schema is still consumed through explicit source conversion (`game/authoring_conversion.py`). Rig/body anchor bases, source sheets, palette treatment, condition body poses/scaling/copies, device muzzles and registered XYZ media are real new capabilities, not automatically illegitimate deviations.

One inconsistency remains: local extended condition recipes still use `neuroclient.conditionPresentationRecipes` version 12 (`game/condition_types.py:274`) while adding fields the original condition renderer does not execute. The local contract explains these additions, but a future adapter must distinguish the extension rather than treating version 12 as proof of equivalent semantics.

Reusable now:

- Content references, authored recipe values, original clip/rig identities and mappings.
- Image/frame banks and recorded registration, sockets, camera/facing data, timing and palettes.
- Native/public event records and lineage data, independently of the render executor.

Work required for a faithful TS client:

- Consume the documented local schemas without dropping extension fields.
- Port shared timeline composition, historical attachments and condition/media clocks.
- Port the common media decoding/compositing, camera/depth and geometric clipping semantics.
- Reproduce small deterministic selection and material algorithms where exact visual matching matters.

JSON reuse is therefore substantial; executor reuse is conceptual and must be implemented in TS. It is not a matter of feeding new JSON to the unchanged old editor/renderer. This does not require Python gameplay objects on the client.

## Field-family ownership inventory

| Family | Authoring owner and main consumer | Assessment / smallest sensible boundary |
| --- | --- | --- |
| Cast body, release, equipment, recovery | Selected Studio bundle; `animation.py`, body sampling | Shared recipe ownership is appropriate; preserve approved timings and make duration joins common |
| Projectile trajectory, source/target anchors, direction/palette | Studio draft plus projectile asset metadata; `animation.py`, `animation_draw.py` | Explicit authored registration is necessary; changing representation must preserve effective output |
| Finite media, contact and child attacks | Local Studio v2; `cast_media.py`, compiler/binder | Necessary extensions; mixed-track completion and per-consumer capability gaps need closing |
| Interruptions | `interruptions.json`; typed `InterruptionPresentation`, `interruption.py` | Native phase/outcome/economy selects passive timing policy; retain this separation, not spell-name cancellation handlers |
| Weapon attack choices | Attack recipes/profiles; shared attack compiler | Weapon-specific overrides with damage-type defaults are authored data; preserve selection order rather than scattering tests in renderer |
| Body actions and locomotion | Content-action recipes and movement-media JSON | Semantic clips and timeline fields are portable; clarify narrower track consumers |
| Rigs, equipment layers, pose sockets | Root bindings and per-rig JSON; animation-data binding/body sampler | Mostly well constrained passive data; small inherited appearance policies remain Python code |
| Condition body/visual changes | Original plus local condition recipes and overrides; condition reducer/sampler | New poses, transitions, copies, distortion and scale are justified; explicitly diagnose retained unsupported equipment/appearance tracks |
| Condition finite/maintained media | `condition-media.json`; `condition_media.py`, layer renderer | Lifetime clocks are shared, but source document needs the same clear type boundary as condition recipes |
| World states and transition markers | World bindings/environment art; `world_animation.py`, app compositor | State selection is backend-driven; art owns finite transition markers; keep these distinct from native physics timing |
| Device launch and destruction | `spell_devices.json`; device sampler and existing cast input | Muzzle/pitch/yaw fields are necessary. Type nested arrays and preserve operator vs device ownership |
| Portal transfer and aperture | `portals.json`; shared portal timeline/draw | Aperture, opening/fall/emergence are legitimate portal presentation data; no new backend teleport policy is called for |
| Maintained areas | `SpatialMediaBinding`; `spatial_media_draw.py` | Native observed footprint/lifetime remains authority; legacy/floor/clump/volume are rendering compositions, not four gameplay rules |
| Deposits/liquids | Deposit variants and particle/material records; deposit/residue drawing | Native deposited material/footprint remains authority; variants and particle geometry are visual data; procedural material details still require porting |
| Packed RGBA/XYZ | Projectile asset/storage metadata; registered-media decoder and shared volume compositor | Component order, origins, facing, position scale and ownership are necessary. Strengthen storage alternatives without new file audits |
| Draw commands | Passive `DrawCommand`; common compositor | Correct architectural unit, but actual role/ownership/contact semantics must leave the diagnostic tuple |

Five overlapping frame storage/registration surfaces currently exist: static `AssetSpec` plus frame-id world animations; environment atlases; camera/yaw/pitch device sheets; portal pages/hatch strips; and projectile/finite RGBA/XYZ storage. Their lifetimes and attachment data differ for real reasons. Their repeated frame/pivot/page bookkeeping does not necessarily need separate implementations forever.

Consolidation should be restricted to common registered-frame sampling/storage where it pays for itself. A device still needs muzzle data, a portal still needs an aperture, and destruction still needs its selected state transition. Merging these into a single enormous asset record would hide those real distinctions.

## Python policy that is not authored JSON

Data-driven does not mean every arithmetic operation must become data. Shared geometric interpolation, palette application, deterministic variation and raster composition belong in shared code. The porting boundary should describe them honestly.

- Blood/residue detail types select procedural shading and colors in `game/blood_draw.py` and `game/surface_residue.py:415`. Parent review is identifying which values are authored choices that should have one data owner. This is not evidence of native damage being synthesized by a renderer. No universal shader language is proposed.
- `game/residue_media.py:65` selects a landing template from geometric input, and `game/deposit_draw.py:32` selects a deterministic variant from UUID. TS needs the same selection semantics for exact matching, even with identical JSON.
- `game/spell_palette.py` contains a palette transformation algorithm in addition to authored colors/parameters. Some constants are implementation, not missing per-spell fields.
- `game/animation_draw.py:399` retains modular helmet/hair policy for Head5/Head8, and its Magic3 handling near line 207 retains source-specific appearance behavior. These should be documented or moved into small rig metadata when that policy is deliberately changed. They are inherited visual identity rules, not evidence that each spell gained a custom executor.
- Equipment visual binding derives from the native authored item-visual ledger in `game/animation_data.py:70`. A TS client should consume that portable ledger/binding data; it should not call Python native entity registries.

The parent audit also reproduced importer-driven reauthoring in `devtools/import_aoe_surfaces.py:75`: import reruns can overwrite selected placement/scale choices. That violates the stated single-owner rule more directly than the presence of a numerical tuning value. Its concrete reproduction and correction belong in the parent synthesis.

## Things this review does not recommend reopening

- Keep completed-lineage scheduling and independent event/render clocks. No batching change is required by these findings.
- Keep native gameplay/public projection as authority for surfaces, destruction, visibility, conditions and device ownership.
- Keep approved Fire Bolt placement and all approved output; a common schema is not permission to normalize its final pixel result.
- Keep per-rig mappings instead of per-creature renderer classes.
- Keep optional media and unsupported dormant reference records explicitly scoped. Their presence is not a demand to author everything now.
- Do not replace the current renderer, create a generic shader DSL, add content hashes, inspect source trees at startup, or eagerly load/validate the whole image corpus.

## Minimum cleanup order for the combined plan

This is a recommendation to the parent review, not an implementation change made here.

1. Restore unambiguous ownership of authored values. Fix importer overwrites first so subsequent refactoring cannot silently restore old choices.
2. Correct the reproduced finite-media completion omission with one shared join and a meaningful mixed-track test.
3. Replace the active positional `evidence` protocol with named passive draw semantics, preserving the existing composer and diagnostic output.
4. Constrain storage alternatives and type the remaining small authoring documents at their existing parse boundaries. Validate data relationships, not file provenance.
5. Make support reporting reflect the actual selected field/consumer surface, including dormant area controls and narrower contact-media semantics. Parent coverage audit owns the complete registry inventory.
6. Document/version the TS extension contract consistently, and consolidate repeated registration code only as touched by these concrete corrections.

Each correction should preserve the same saved event inputs and approved visual behavior. Use focused output comparisons where a shared path changes; a new visual testing framework is not required to perform this cleanup.
