# Player UI artwork handoff — 2026-10-06

For the human to forward. No other-chat communication is required.

## Current delivery status — October 6

The CIE28 pixel-icon delivery and both pixelated portrait deliveries are now
installed. The original missing-subject table below is historical: those 48
subjects are covered. Current icons are the delivered 28×28 RGBA pixels,
preserved without tinting or resampling; the earlier 64×64 request below no
longer describes the installed format. All ordinary registered spells now
resolve an icon, including Fly's explicitly shared delivered image.

The remaining declared icon gaps are Traverse Connector, the generic
Multiattack Runtime, Hit Save Rider, Keen Perception, Magic Resistance, Innate
Flight and Aegis Training. The test-only Test Bless fixture also has no image.
These are world-only, generic or passive subjects; they do not block the
Fighter/Sorcerer action bar. No missing key receives an invented artwork alias.
The current machine-readable inventory is in the ignored acceptance output's
`icon-coverage.json`; it is distinct from this original request.

Ground potions and other consumables still lack authored ground appearances.
Inventory icons exist, but a carried icon is not automatically a world sprite.
Native dropping and ownership work; floor-weapon pickup is exercised with a
Handaxe. This delivery does not claim visible/clickable ground potions. Their
ground-art assignment is a separate remaining content task, with no new art
or arbitrary runtime substitution introduced here.

The UI works with the recovered accepted icons while the replacement pixel pack is being prepared. Existing art is registered with its original key and immutable asset hash. Deliver replacements with an explicit manifest mapping every key to its file; I will update the authenticated index and copy production media through the current installer. Do not rename keys silently.

## Format

- Square RGBA images: 64×64 pixels preferred, readable at 42×42 and 32×32. Keep silhouettes inside the square; no baked labels.
- Pixel art with clean edges; no new weapon sprites, VFX or character sheets requested.
- PNG or lossless WebP. Preserve original authoring files separately.
- One manifest row per icon: exact icon key, source file, native dimensions, intended subject. Palette is part of the icon; the UI does not multiply its colours.

## Existing recovered set

515 authenticated icon keys are registered in `game/data/ui_media.json`; 13 unindexed recovered images are excluded. The existing direct feature and item mappings are in `game/data/ui_presentation.json`. The updated pixel pack can replace these resources without changing mechanical content or target selection. The 56 recovered portraits are usable; no new panel ornaments or portrait artwork is needed for this phase.

## Registered subjects with missing artwork

These are current public registered subjects whose specified icon is missing or has no binding. They are not a request to implement new mechanics. If the replacement batch already covers a subject, list it in the manifest. A missing image remains a labelled placeholder, not a fabricated runtime alias.

| Kind | Subject | Required icon key |
|---|---|---|
| action | Toggle Lever (`action.environment.control_lever.toggle`) | `action.environment.control_lever.toggle` |
| action | Slip free of jaws (`action.environment.escape_jaw.acrobatics`) | `action.environment.escape_jaw.acrobatics` |
| action | Force jaws open (`action.environment.escape_jaw.athletics`) | `action.environment.escape_jaw.athletics` |
| action | Close Chest (`action.environment.storage_chest.close`) | `action.environment.storage_chest.close` |
| action | Open Chest (`action.environment.storage_chest.open`) | `action.environment.storage_chest.open` |
| action | Ember Quiver (`action.item.ember_quiver`) | `action.item.ember_quiver` |
| action | Dismiss Summon (`action.summon.dismiss`) | `action.summon.dismiss` |
| condition | Basic Poison (`condition.consumable.weapon_coat.basic_poison`) | `condition.consumable.weapon_coat.basic_poison` |
| condition | Jaw restraint (`condition.environment.jaw_restrained`) | `condition.environment.jaw_restrained` |
| condition | Summon Control (`condition.summon_control`) | `condition.summon_control` |
| condition | Summoned (`condition.summoned`) | `condition.summoned` |
| condition | Tile Residue (`condition.tile.residue`) | `condition.tile.residue` |
| spell | Conjure Fiend (`spell.conjure_fiend`) | `spell.conjure_fiend` |
| spell | Ice Knife (`spell.ice_knife`) | `spell.ice_knife` |
| action | Innate Invisibility (`action.monster.innate_invisibility`) | `action.monster.innate_invisibility` |
| action | Life Drain (`action.monster.wight.life_drain`) | `action.monster.wight.life_drain` |
| action | Dismiss Fire Shield (`action.spell.fire_shield.dismiss`) | `action.spell.fire_shield.dismiss` |
| condition | Barkskin (`condition.spell.barkskin`) | `condition.spell.barkskin` |
| condition | Eyebite Casting (`condition.spell.eyebite.casting`) | `condition.spell.eyebite.casting` |
| condition | Fire Shield (`condition.spell.fire_shield`) | `condition.spell.fire_shield` |
| condition | Fly (`condition.spell.fly`) | `condition.spell.fly` |
| condition | Harm (`condition.spell.harm`) | `condition.spell.harm` |
| condition | Longstrider (`condition.spell.longstrider`) | `condition.spell.longstrider` |
| condition | Shillelagh (`condition.spell.shillelagh`) | `condition.spell.shillelagh` |
| condition | Sunbeam Blindness (`condition.spell.sunbeam.blinded`) | `condition.spell.sunbeam.blinded` |
| condition | Sunbeam (`condition.spell.sunbeam`) | `condition.spell.sunbeam` |
| condition | Wall of Fire (`condition.spell.wall_of_fire.zone`) | `condition.spell.wall_of_fire.zone` |
| condition | Wall of Force (`condition.spell.wall_of_force.zone`) | `condition.spell.wall_of_force.zone` |
| condition | Frigid Air (`condition.spell.wall_of_ice.frigid_air`) | `condition.spell.wall_of_ice.frigid_air` |
| condition | Wall of Ice (`condition.spell.wall_of_ice.zone`) | `condition.spell.wall_of_ice.zone` |
| condition | Wall of Stone (`condition.spell.wall_of_stone.zone`) | `condition.spell.wall_of_stone.zone` |
| condition | Wall of Thorns (`condition.spell.wall_of_thorns.zone`) | `condition.spell.wall_of_thorns.zone` |
| condition | Wind Wall (`condition.spell.wind_wall.zone`) | `condition.spell.wind_wall.zone` |
| condition | Life Drain (`condition.wight.life_drain`) | `condition.wight.life_drain` |
| spell | Barkskin (`spell.barkskin`) | `spell.barkskin` |
| spell | Conjure Animals (`spell.conjure_animals`) | `spell.conjure_animals` |
| spell | Conjure Fey (`spell.conjure_fey`) | `spell.conjure_fey` |
| spell | Fire Shield (`spell.fire_shield`) | `spell.fire_shield` |
| spell | Longstrider (`spell.longstrider`) | `spell.longstrider` |
| spell | Produce Flame (`spell.produce_flame`) | `spell.produce_flame` |
| spell | Shillelagh (`spell.shillelagh`) | `spell.shillelagh` |
| spell | Wall of Fire (`spell.wall_of_fire`) | `spell.wall_of_fire` |
| spell | Wall of Force (`spell.wall_of_force`) | `spell.wall_of_force` |
| spell | Wall of Ice (`spell.wall_of_ice`) | `spell.wall_of_ice` |
| spell | Wall of Stone (`spell.wall_of_stone`) | `spell.wall_of_stone` |
| spell | Wall of Thorns (`spell.wall_of_thorns`) | `spell.wall_of_thorns` |
| spell | Wind Wall (`spell.wind_wall`) | `spell.wind_wall` |
| action | Attack (`action.attack`) | `action.attack` |

## Direct equipment substitutions

Current direct item rows explicitly reuse old weapon or equipment-slot icons where exact variants do not exist. Those substitutions are disclosed in `ui_presentation.json`. No additional weapon artwork is authorized; a UI icon can be shared across material/enchantment variants, with the original native description and effects shown in the tooltip. Environmental props use the world sprite and action verb, not an actionbar inventory button.

## Pixelated Blender skin — updated human preference

Create a small shared skin with subtle physical depth instead of code-drawn panel chrome. Text remains live antialiased text at display resolution, never baked into the images. Use a shallow charcoal slab, restrained warm edge lighting and slight bevels. Avoid large decorative fantasy corners, luminous borders, strong drop shadows and broad gradients that compete with the battlefield.

| Resource | Native canvas | Fixed inset | States |
|---|---|---|---|
| Panel | 64×64 RGBA | 8 px on each edge | normal |
| Square action slot / portrait frame | 48×48 RGBA | 6 px | normal, hover, selected, disabled |
| Button | 64×32 RGBA | 6 px | normal, hover, pressed, disabled |
| Tooltip | 64×64 RGBA | 6 px | normal |

Deliver a `.blend` source, transparent PNGs and exact state/resource mapping. Render orthographically from above, with lighting giving shallow bevel depth. Pixelate the artwork once at the target native size; UI scales keep fixed corners and tile/stretch only designated edge/centre regions. Border-free interiors must allow native icon art and readable text to sit cleanly. Gold denotes selection; disabled frames are subdued but labels stay readable. No text, icon, number or interactive hitbox is part of these images. A nine-slice skin changes decoration; widget geometry and input remain in the same shared UI functions.
