# Surface and elemental interaction inventory: native engine vs BG3 and DOS2

**Baseline date:** 2026-10-01. **Checkpoint update:** 2026-10-01, after `dnd/spatial/ignition.py` and its Fire Bolt/Burning Hands/Fireball contact producers appeared in the working tree; Wall of Fire ignition is part of the current lane checkpoint.  
**Scope:** read-only comparison of the current D&D 5e engine with surface systems in Baldur's Gate 3 and Divinity: Original Sin 2. BG3/DOS2 are inspiration comparisons only; their rules do not define this SRD 5.1 engine. This is an inventory, not an implementation plan.

## Executive finding

The engine has a real, typed, persistent spatial-condition model and several substantive surface behaviors: fire, water/wet, ice, electrified water, steam, burning web, oil, grease, web, poison gas, and tile-owned blood/poison/corrosive demonic/dread residues. Conditions compose with movement, creature occupancy, entry/turn triggers, light, obscurement, duration, event lineage, and (for authored spell zones) concentration. The transition handler can replace/remove exact intersecting cells.

The fire producer path has advanced at this checkpoint: `dnd/spatial/ignition.py` centralizes cell-contact `IGNITE` publication, and the working tree calls it from Fire Bolt, Burning Hands, Fireball, and Wall of Fire. Oil Barrel destroyed by fire also emits `IGNITE`. Web and Oil own `IGNITE` transition rows; Gust of Wind emits `DISPERSE`; Call Lightning storm emits `DOUSE`. Water/ice/electrified-water have `FREEZE`, `ELECTRIFY`, `VAPORIZE` rows, and fire can be doused, but no corresponding cold/lightning/fire-to-water producers were found in this snapshot. A caller can publish `SpatialEffectInteractionEvent` directly; that is distinct from a gameplay producer. No registered transition was found for blood/residue, poison/oil explosion damage, poison cloud ignition, smoke, or grease ignition.

Thus this code is much closer to BG3's small persistent-surface vocabulary than DOS2's broad, recursive surface/cloud graph. Fire ignition is now automatic for the named spell producers, but remaining elemental interactions and general damage-to-material mapping are incomplete. Existing transitions are authored D&D-derived behavior, not a license to import Larian rules.

## Evidence and classification

- **Implemented:** native runtime definition and applicable mechanical effects are present.
- **Transition only:** a live typed `SpatialEffectInteractionEvent` transforms it, but a normal gameplay producer may be absent.
- **Visual/record only:** visible spatial state or residue snapshot exists without an interaction/mechanical bridge.
- **Manual only:** a caller/test can publish the typed transition event; production gameplay does not automatically derive it from damage.
- **Absent:** no matching native owner/transition found in the inspected production code.

These labels are source observations, not claims that every possible gameplay combination was exhaustively simulated. The main owners inspected were `dnd/spatial/environmental_conditions.py`, `dnd/spatial/transitions.py`, `dnd/core/content/spatial_effect_definitions.py`, `dnd/types/spatial_effects.py`, `dnd/spells/conjuration.py`, `dnd/spells/evocation.py`, `dnd/content/items/environment_item_builders.py`, `dnd/residues.py`, and the focused engine tests. No full suite was run.

## Native surfaces and residues

| Surface/material | Creation/collision source and native behavior | Interaction coverage and gaps |
|---|---|---|
| Fire surface | `FireSurface`: ground layer; 3 rounds by default; bright light; 2d4 fire on entry and turn start; hazard filtering; removes/douses affected cells on a DOUSE interaction. | Supported fire spells now emit IGNITE into resolved cells; Call Lightning storm emits DOUSE. No ordinary water/cold dousing producer observed. Fire created by Oil/Web transition is a real native condition. |
| Water / wet surface | `WetSurface`: permanent ground surface, wet membership on occupants. Liquid barrel spills create water with source geometry. | Transition rows freeze to ice, electrify to electrified water, or vaporize to steam. Fire spells now emit IGNITE (not VAPORIZE); no cold/lightning producer for FREEZE/ELECTRIFY was found. |
| Ice | `IceSurface`: permanent ground, difficult terrain, Dexterity DC 10 slip/prone checks on appearance, entry, and turn end (first-per-turn rules). | VAPORIZE produces steam. No automatic fire-melt producer or ice-to-water reversion timer. |
| Electrified water | `ElectrifiedWater`: wet ground, 1d4 lightning on appearance/entry/turn start, first-per-turn controls. | FREEZE to ice and VAPORIZE to steam. No ordinary lightning emitter to create this state was found. |
| Steam | `SteamCloud`: 2 rounds; cloud layer; wet and heavy optical obscurement. | No registered DISPERSE or electrify transition found for this condition. No generic fire+water producer found. It is an actual cloud distinction, not just a surface flag. |
| Oil | `OilSurface`: permanent ground layer, difficult terrain; barrel destruction spills it. Fire Bolt, Burning Hands, Fireball, and Wall of Fire now emit exact-contact/cell IGNITE events. | IGNITE replaces affected cells with FireSurface. No oil explosion damage, smoke secondary, or residual burning spread found. BG3 Oil documentation describes conversion to Fire; its separate Oil of Combustion creature coating has explicit area damage. |
| Grease | The native Grease spell is concentration-owned; difficult terrain and Dexterity slip checks on appearance/entry/turn end. This is the game's authored implementation of the SRD spell, not evidence that SRD defines Larian-style surface ignition. Mundane grease barrels also use a grease zone route. | No grease transition row or grease-specific ignition. Do not infer that SRD Grease must ignite. |
| Web | SRD Web: concentration-owned 20-foot cube, difficult terrain, restraint saves/escape, anchored/layered lifecycle and spatial sensory disclosure. | Has an IGNITE→BurningWeb transition row. Supported fire spells now emit IGNITE over their resolved cells; this is an automatic route for those emitters, while arbitrary fire damage outside them still does not imply a generic damage-to-material reaction. BurningWeb lasts 1 round, triggers turn-start fire damage (through FireSurface inheritance), and can be DOUSEd. It is cell-local, not DOS2-style spreading/exploding web. |
| Blood | Ordinary blood is tile-owned residue and visual world state; body releases deposit it. It has no general movement hazard. BG3-style surface is not represented as one transformable surface owner. | No cold/electric/wash/ignite transition over blood residue. DOS2 electrified/frozen/bloodified/contaminated blood has no equivalent. |
| Corrosive demonic blood / dread blood | Authored residues with 1d4 acid entry damage, or DC 10 Wisdom fear/retreat on entry respectively. | Material-specific entry mechanics exist, but no elemental surface transitions. They are tile residue profiles, not `SpatialCondition` ground surfaces. |
| Poison residue | Tile-owned poison residue deals 1d4 poison on entry. Poison gas traps separately own cloud conditions, with moderate DISPERSE threshold. | No fire ignition/explosion/secondary-fire transition found for poison ground residue. Poison cloud dispersal is a native transition-only feature; no fire interaction found. |
| Bone fragments / ash | Tile-owned residue, visual/material state. | No elemental transitions. |
| Other native clouds | Fog Cloud and similar conditions use `CLOUD` layer and optical obscuration. Cloudkill has a strong-wind removal transition; Fog Cloud, Stinking Cloud, and gas traps have authored wind-dispersal behaviors. | Cloud-specific wind interactions exist, but no general cloud conversion graph or fire/poison/smoke cloud system. Gust of Wind is the production emitter for strong DISPERSE; Call Lightning's storm is a production DOUSE emitter. |

### Creation, collision, and world model details

`SpatialEffectLayer` separates `GROUND_SURFACE`, `CLOUD`, and `FIELD`; occupancy policy includes exclusive transforming vs overlapping. `SpatialEffectInteractionOperation` has `IGNITE`, `DOUSE`, `FREEZE`, `ELECTRIFY`, `VAPORIZE`, and `DISPERSE`. An authored transition chooses exact intersecting cells and can remove, replace, or replace while creating a secondary; intensity thresholds and delayed retirement are supported. The handler is indexed by condition footprint and event type/phase.

Native surface conditions also participate in actual world mechanics rather than only drawing: ground conditions can add difficult terrain, filter occupancy layers, trigger on appearance/entry/turn start/end, deal typed damage or apply saves/conditions, alter light, add wet membership, or optically obscure vision. Their durations and removal follow condition lifecycle. Spell-created zones can be concentration-linked. `MaterialDepositSource` persists original barrel origin/radius/deposit UUID through partial transformation and observation, while actual remaining footprint remains separately tracked.

This does **not** imply support for every Larian-like channel: the inspected material interactions are 2D cell sets in these event contracts; they do not define DOS2's high-ground damage/range rules or an independent volumetric surface/cloud simulation. Existing LOS, movement, occupancy, and light are engine/world services consumed by authored conditions, not universal properties of every surface.

## Producer audit: a transition row is not proof of automatic gameplay

At this checkpoint, production emitters found are:

1. `dnd/spatial/ignition.py`: publishes one typed `IGNITE` for the supplied contact cells. Calls now exist for Fire Bolt, Burning Hands, Fireball, and Wall of Fire. The helper intentionally operates on exact resolved cells; material owners decide whether those cells transform.
2. `LiquidBarrel._on_destroy`: oil barrel destroyed by fire emits `IGNITE`.
3. `WebZone` and `OilSurface`: own `IGNITE` transition rows; web becomes one-round BurningWeb, oil becomes FireSurface.
4. Gust of Wind emits strong `DISPERSE`; Call Lightning storm emits strong `DOUSE`.

No corresponding production elemental emitter was found for `FREEZE`, `ELECTRIFY`, or `VAPORIZE`; existing water/ice/electrified-water/steam rows remain callable through a typed event and tested, but are not reached by the normal cold/lightning/fire spells in the inspected path. No generic attack/damage resolver emits a material event merely from a damage type. No transition was found for blood residue, poison/oil explosions, poison cloud ignition, or smoke. The tests that publish transition events prove handler behavior, not an additional automatic producer.

## Explicit comparison with Baldur's Gate 3

BG3's community wiki describes a wider surface catalogue and specific damage-driven transformations: water exposed to lightning becomes Electrified Water, cold becomes Ice, and contact with a fire surface creates Steam Cloud; ice hit by fire becomes water; liquid blood can freeze; Oil becomes Fire, while Oil of Combustion and unstable blood have separate explosion behavior; Grease causes prone/difficult terrain; fire surfaces deal Burning damage. The engine shares several surface names and effects (fire, water/wet, ice, electrified water, steam, oil, grease, web), plus web ignition and barrel-created oil. It does not currently match automatic BG3 damage exposure, explosive coatings/blood, broad authored liquids, or BG3's other bespoke surfaces (acid, deep water, hellfire, plant growth, mud, lava, smokepowder, etc.).

BG3 also separates clouds from ground surfaces in its own surface/cloud vocabulary; the native engine has separate cloud layer and heavy/light obscurement contracts, but only selected authored cloud transformations/dissipation. BG3's wiki notes a gameplay bug where a newly created surface may not affect an occupant already standing there; this engine has explicit appearance/entry trigger kinds, so that BG3 quirk should not be copied as a design target.

These are comparative observations only. BG3 is built on 5e but applies its own implementation and balance choices; it is not an authority for SRD 5.1 behavior. In particular, native Wet does implement fire resistance and cold/lightning vulnerability, while the BG3 Wet condition also prevents Burning and has special replacement interactions with Chilled/Frozen. Native Wet does not copy every BG3 status rule.

## Explicit comparison with Divinity: Original Sin 2

DOS2 is a much broader authored elemental system. Larian's DOS2 press sheet explicitly advertises surfaces being frozen, turned into clouds, blown up, burned, or energized, and surfaces being blessed/cursed. Larian's Divinity Engine scripting API documents transform operations: Ignite (oil/poison), Electrify (water/blood), Melt/Freeze (water/blood), Condense/Vaporize (cloud/ground), Bloodify (water→blood), and Contaminate (water/blood→poison). Its surface type index also names `SurfaceOil`, `SurfaceBlood`, `SurfaceFireCloud`, `SurfaceWaterCloud`, and `SurfacePoisonCloud` among the available types. This is stronger evidence of type/operation vocabulary than community summaries, but does not by itself prove every pairing or combat consequence; it describes tooling/API capability, not every encounter-specific rule.

Established DOS2 field documentation additionally describes fire, water, electrified water, blood, poison, oil, lava, source, ice; fire + poison/oil explosion; wet/fire removal; ice melting/freezing; blood electrification/freezing; clouds such as poison, steam, static, smoke; and cursed/blessed variants. Current engine coverage is much narrower: no poison/oil blast, smoke, static cloud, blood manipulation, cloud condensation, bless/curse, lava/source surface, or recursive chain reactions. DOS2's AP/armor/resistance/status system and height-based combat are also structurally different from this D&D action economy, HP, elevation, and rules model, so “same name” does not imply same mechanic.

## Prioritized coverage gaps (inventory only)

Priority reflects the size of the comparison gap, not a recommendation or implementation order. This table does not authorize importing either game's rules.

| Priority / area | Current engine coverage at checkpoint | BG3 / DOS2 comparison and remaining gap |
|---|---|---|
| P1 — Fire contact producers | Fire Bolt, Burning Hands, Fireball, Wall of Fire now publish exact-cell `IGNITE`; oil barrel fire destruction does too. Oil and Web transition. | BG3 fire damage ignites Oil into a Fire surface; its Oil surface interaction is replacement, while separate Oil of Combustion on creatures can explode for area damage. DOS2 Ignite includes oil/poison and can explode. Native explosion/secondary damage graph absent. |
| P1 — Water + fire / ice melting | WetSurface supports `VAPORIZE`→SteamCloud; FireSurface supports DOUSE. No ordinary fire-to-water emitter observed. Ice has `VAPORIZE`→SteamCloud, no melt-to-water operation. | BG3 water + fire surface → Steam Cloud; ice + fire → Water; water + cold → Ice. DOS2 API includes Vaporize and Melt. Native ice-to-water reversal is absent; current Ice-to-Steam should not be mistaken for BG3 melting. |
| P1 — Cold and lightning surfaces | Water has `FREEZE` and `ELECTRIFY` rows; no normal producer observed. Electrified water can freeze/vaporize. | BG3 cold freezes water and blood; lightning electrifies water. DOS2 additionally freezes/electrifies both water and blood. Blood surface transforms absent natively. |
| P2 — Ground material catalogue | Water, fire, ice, electrified water, oil, custom Grease, web; blood/poison/demonic/dread as tile residues. | BG3 adds many bespoke surfaces; DOS2 has oil, poison, water, blood, fire, ice, lava/source and blessed/cursed variants. No comprehensive native material palette or universal mixing rules. |
| P2 — Clouds | SteamCloud, Fog Cloud, Cloudkill, Stinking Cloud, gas traps and other spell-owned clouds use cloud layer/obscurement; selected wind dispersal. | DOS2 has poison, steam, static and smoke clouds; cloud/ground condensation and vaporization API. BG3 has steam and spell clouds. No native smoke/static cloud, cloud ignition, electrification, or general condensation. |
| P1 — Creature elemental statuses | Native `Wet` is real and modifies fire resistance plus cold/lightning vulnerability. Poisoned and Prone exist; FireSurface deals typed damage, Ice can cause Prone, ElectrifiedWater deals lightning. No general Burning, Chilled, Frozen, or Shocked condition was found in core condition definitions. | BG3 Wet also blocks Burning; Chilled/Wet can yield Frozen; Shocked disables reactions and affects Dexterity checks; Electrified Water applies Electrocuted. DOS2 statuses gate through armor and combine Wet/Chilled/Shocked into Frozen/Stunned; surfaces apply Burning/Poisoned. Those status conversion chains are absent. |
| P3 — Grease/web and concentration | Grease is a native concentration-owned authored D&D spell zone; Web is concentration-owned, anchored/layered and can burn by explicit interaction. | BG3 Grease is a surface and flammable; DOS2 oil is flammable. These do not establish that the D&D Grease spell must ignite. Web burn is only partial comparison; no general spreading/combustion graph. |
| P2 — Residues | Blood and several poison/bone/ash/demonic residues have tile-owned mechanics or visual state; demonic blood and poison can damage on entry, dread blood can impose fear. | BG3 blood is a surface that freezes; DOS2 blood electrifies/freezes and can be contaminated/bloodified. Native residues are not transformable ground-surface owners. |

## Source strength and references

**Primary sources:**

- Larian, [Divinity: Original Sin 2 press sheet](https://cdn.uc.assets.prezly.com/c4229b32-6bb0-41ba-bd0a-1034fd8d01da/-/inline/no/dos2-pr-fact-sheet.pdf), p. 4: surface manipulation and bless/curse overview.
- Larian Divinity Engine Wiki, [TransformSurfaceAtPosition](https://docs.larian.game/Osiris/API/TransformSurfaceAtPosition): official scripting transform operation list for DOS2.
- Larian Divinity Engine Wiki, [Scripting surface types](https://docs.larian.game/Scripting_surface_types): official surface type API reference.

**Established community documentation (secondary; mechanics may reflect game-version changes):**

- BG3 community wiki, [Surface](https://bg3.wiki/wiki/Surface): catalogue and listed elemental interactions.
- BG3 community wiki, [Oil](https://bg3.wiki/wiki/Oil): Oil surface turns to Fire on fire damage; distinguishes this from creature-applied Oil of Combustion.
- BG3 community wiki, [Wet](https://bg3.wiki/wiki/Wet_%28Condition%29), [Chilled](https://bg3.wiki/wiki/Chilled_%28Condition%29), and [Shocked](https://bg3.wiki/wiki/Shocked_%28Condition%29): creature status effects and conversions.
- BG3 community wiki, [Water (surface)](https://bg3.wiki/wiki/Water_%28Surface%29): water creation, two-turn transformations, and cleanup notes.
- BG3 community wiki, [Cold Damage — surfaces](https://bg3.wiki/wiki/Cold_Damage#Surfaces): ice/water/steam and cold surface interactions.
- DOS2 GameFAQs guide, [Environmental Effects (Fields)](https://gamefaqs.gamespot.com/pc/179840-divinity-original-sin-ii/faqs/75293/environmental-effects-fields): practical surface causes/removals, secondary source.
- Divinity Wiki, [Environmental Effects (Original Sin 2)](https://divinity.fandom.com/wiki/Environmental_Effects_%28Original_Sin_2%29): practical descriptions of spreading, explosions and clouds, secondary source.
- GameFAQs DOS2 guide, [Environmental Effects](https://gamefaqs.gamespot.com/ps4/236378-divinity-original-sin-ii-definitive-edition/faqs/81674/introduction): surface interactions and status effects, secondary source.

