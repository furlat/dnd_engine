# Authoring coverage and migration disposition

Companion to [the new server/client/Studio plan](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md).
2026-10-07. Planning inventory, not implemented editor coverage.

Every row below has one canonical source owner. Studio edits that source and the
same exporter/compiler resolves it for gameplay and preview. It must not serialize
the effective merged catalog back over the original documents. Generated package
paths, storage offsets and source provenance are read-only in normal authoring.
Art registration editing is an explicit asset/rig inspector, not pixel editing.

## All 53 AnimationData fields

The counts in the selected-content index describe effective identities, including
aliases; they are not independent executable spells. Actual nested fields/types
are recorded in the source inventory. Implementation must show each editable field
round-trips through load/edit/save/reload, including fields untouched by an edit.

| Field | Studio disposition | Source family / production destination |
|---|---|---|
| interruptions | Edit reaction/cancel timing and media | interruptions.json; causal compiler + R08/R17/R20 |
| devices | Edit registered device presentation | spell_devices.json; R03/R08 |
| device_wrecks | Edit wreck selection/registration | device-art registrations; R03 |
| drafts | Edit complete spell/effect recipes | selected spell-studio-drafts.json; R04/R06/R08–R20 |
| attack_recipes | Edit attack selection/media/contacts | attack-profiles.json; R04–R08/R17 |
| shove_recipes | Edit attempt/displacement presentation | action recipes; R16/R17 |
| body_action_recipes | Edit ordinary gesture/layers/timing | action recipes; R04/R17 |
| body_action_bindings | Edit exact content-to-recipe binding | selected action bindings; compiler |
| condition_recipes | Edit pose/body/marker/media/lifecycle | condition-recipes/overrides; R04/R14 |
| condition_media | Registration inspector | condition-media.json; R07/R14 |
| projectile_assets | Registration/phase inspector, source provenance read-only | projectile-assets.json; R07–R09 |
| projectile_storage | Derived read-only storage addresses | packer/bindings; resource adapter |
| media_root | Tool-local read-only; replaced by release URL base in client | export/manifest |
| rig | Edit root rig tables through source rig inspector | root rig source; R04 |
| resources | Derived read-only URL/source mappings | bindings and packed manifests; R07 |
| root_rig | Edit validated default rig reference | root bindings; R04 |
| rigs | Edit clip/pose/socket/slot registration | rigs/*.json; R04/R05 |
| creature_rigs | Edit exact creature-to-rig binding | creature rig registrations; R04 |
| damage_context | Edit reaction/body/flash/feedback/media | actionContextPresentation; R17 |
| healing_context | Edit healing presentation | actionContextPresentation; R17 |
| death_save_context | Edit actual result feedback | actionContextPresentation; R17 |
| life_state_context | Edit dying/stable/recovery poses | life-state-poses/context; R04/R17 |
| death_context | Edit death/remains/disintegration presentation | actionContextPresentation; R04/R17 |
| equipment_context | Edit body/media/visual commit boundary | actionContextPresentation; R05 |
| movement_context | Edit gait/flight/jump/landing tracks | movement/context source; R04/R16 |
| movement_reaction_context | Edit reaction holds and release behavior | action context; R16/R20 |
| forced_movement_context | Edit displacement/landing feedback | action context; R16/R17 |
| forced_movement_profile | Edit presentation curve/facing/recovery | action context; R16 |
| shove_feedback | Edit explicit native outcome feedback | action context; R17 |
| number_style | Edit readable floating-number style | feedback context; R17 |
| badge_style | Edit status/feedback style | feedback context; R17 |
| dart_style | Edit supported geometric projectile style | existing source context; R08, only selected consumers |
| bolt_style | Edit supported geometric projectile style | existing source context; R08, only selected consumers |
| vfx_source_hues | Inspect source-conversion metadata; not automatic tint fallback | conversion sources; explicit palette policy R06 |
| context_source_json | Read-only source/provenance; excluded from executable bundle | exporter |
| world_animations | Edit transitions/frame ranges/state mappings | world bindings/animation source; R02/R03 |
| spatial_media | Edit phases/geometry/contact/removal commits | world/bundle bindings; R09/R12/R19 |
| action_media_assets | Registration/particle source inspector | action-media assets; R07/R13 |
| body_release_media | Edit releases attached to actual body events | movement/residue media; R13/R18 |
| relocation_actions | Edit explicit presentation alias classification | source action bindings; R16 |
| portals | Edit endpoint art/timing/registration | portal/dimension-door bindings; R16 |
| blood_responses | Edit actual response-to-media selection | authored blood source; R17/R18 |
| action_playback_rates | Edit explicit body rates; preview source vs effective | movement-media/action source; R04/R20 |
| action_deliveries | Edit reference to owned draft, not copied draft | bundle bindings; compiler |
| movement_reference_speed_feet | Edit animation reference only; never native speed | movement-media/context; R16 |
| deposit_media | Edit footprint/reveal/material tracks | world bindings; R18 |
| concentration_media | Edit retained spatial manifestation | world/bundle bindings; R15 |
| construction_media | Edit material/phases/sections/commit offsets | construction bindings; R12 |
| body_materials | Edit manifestation material | summon/body source; R06/R17 |
| entity_lifecycle_media | Edit summon/departure/hostility visual phases | summon lifecycle source; R17 |
| item_attachments | Edit item-owned attached media | item visual source; R05/R15 |
| action_materials | Edit finite body/hand/recipient material tracks | authored action material source; R06 |
| action_intakes | Edit selected intake/pull presentation | action-media source; R13 |

Current effective selections include 149 spell/effect draft keys, five attack
recipes, 85 body action recipes, 160 condition recipes, 44 rigs, 1,112 projectile
asset records and 1,090 storage records. These counts describe the current loaded
catalog and may share underlying pictures or behavior. The selected-content JSON
lists every key; no requirement to create 1,112 new shaders follows from this.

## World catalog outside AnimationData

`AssetCatalog` is another current input: merely porting AnimationData would omit
world art/materials. Its 15 fields have the following disposition:

| Field | Disposition |
|---|---|
| world_source | Edit typed WorldBindingsSource below |
| resources | Inspect derived AssetDocument resource registrations |
| bindings | Derived view of world_source; never a second editable copy |
| flame_frames, flame_fps | Edit source torch animation registration/rate |
| water | Edit source water material parameters; GPU R18 |
| props | Derived from world_source.props; edit that source |
| spatial_effects | Derived from matching world-source field |
| spatial_tethers | Derived tether registration inside spatial_effects |
| spatial_residue_overlays | Edit source spatial residue bindings |
| residue_particles | Edit source emitter/media parameters |
| residue_ground | Edit source residue-to-ground media mappings |
| residue_surfaces | Edit source receiving-surface material parameters |
| residue_wall_faces | Edit source wall-face registration/projection |
| liquid_surfaces | Edit existing liquid material parameters; no new chemistry |

WorldBindingsSource fields: schema_version is read-only version metadata. `terrain`,
`terrain_cliff`, `terrain_stairs`, `stone_wall_straight`, `stone_wall_corner`,
`wood_wall_straight`, `wood_wall_corner`, `stone_door_frame`, `wood_door_closed`,
`wood_door_open`, `props`, `treatments`, `spatial_effects`, `residue_wall_faces`,
`residue_particles`, `residue_ground`, `residue_surfaces`, `liquid_surfaces`,
`spatial_media`, `concentration_media`, `construction_media`, `deposit_media` are
source-editable structured references/parameters. Where AnimationData consumes
one of them it is the same source document and edit, not an additional owner.

AssetDocument fields: schema_version is version metadata; resources and animations
use the registration inspector; water uses the world material inspector. Importing
new binary artwork remains the existing explicit private pipeline. Browser editing
does not overwrite original source images or embed binary media in JSON.

`EnvironmentDocument` (`environment_art.json`) is independently exported too:
version is read-only; banks, doors, traps, wrecks and props have registration and
transition inspectors. Bank crop/pivot/rows/frame-count/uneven-sample-times/depth
planes, state/release frames, door pose offsets, prop destruction variants,
selection/aperture masks and passage points must survive export/edit/reload. Packed
addresses are derived; authored geometry/registration is editable with validation.
`WaterSource` in AssetDocument is the canonical material input; do not recover its
values from opaque runtime dictionaries. No second environment source is generated
from the old NeuroClient world store.

## UI data and native content

`ui_media.json` and `ui_presentation.json` remain the accepted icon/portrait/choice
presentation sources. Edit their visual bindings with validation. Native content
IDs/names/descriptions/available actions/item statistics and recorded combat-log
math are read-only in visual Studio. It does not become a character/rule editor.
Include `ui_skin.json` resources/insets/state variants, UI choice records and fonts
in the versioned presentation release. Their source metadata can be edited with
validation; gameplay HUD layout is browser view code, not another JSON UI engine.
NeuroClient was more advanced but incomplete: the human did not approve wholesale
reuse. Evaluate components against current requirements as specified in the main
plan. Revised icons/portraits are supplied separately; stable bindings and release
revisions admit those assets without making asset replacement the whole UI task.
This does not reinstate rejected bulky chrome: only selected accepted resources
are used by the minimal UI. The pygame skin drawing function is not ported into
the browser views automatically.

The engine content manifest is delivered as static versioned metadata, not sent in
each event. Existing item visual ledgers outside game/data (notably
`content_data/ledgers/neuroclient_authored_item_visuals.json`) remain their current
canonical source and must be included in the export source map. Do not silently
substitute the old NeuroClient generated equipment/palette files.

## Concrete Studio interaction

Choose a content recipe, choose a real recorded action/fixture, inspect the compiled
timeline and preview it. Select a body/media/material track to edit its typed fields.
Display source FPS, effective body/playback speed and measured render FPS separately.
Show rig socket positions at release/contact and path tangents for projectiles.
Allow toggling layers for diagnosis; toggles are preview controls unless explicitly
saved as authored enablement. Compare baseline/candidate at equal presentation time.

Condition editor must exercise application, retained sustain, multiple owners,
suppression and last-owner removal. Item editor must exercise held, dropped and
re-equipped states. World editor must exercise formation/destruction/clearance and
four cameras. These are shared runtime states/tracks, not bespoke preview actors.
No modification of a visual parameter can alter a native damage roll or action cost.

## Validation is more than generated JSON Schema

Structural TS validators generated from JSON Schema cannot execute Python
`model_validator`/`field_validator` methods. Inventory them explicitly in the
[semantic validator ledger](audits/neuroclient-server-20261007/semantic-validator-ledger.csv),
then add loader-level cross-document rules from animation_data/authoring_conversion.
The ledger includes all decorated source validators as a denominator, not a claim
that each belongs to frontend authoring. Boundary compatibility conversions are
one-time decode operations, not per-frame fallbacks.

Port the needed presentation semantic checks as pure TS functions used by both
live bundle admission and Studio candidate compilation. Examples include mutually
exclusive directed/arc/projectile owners, source sockets/contact requirements,
removal-gated targets, texture-dependent body-ramp parameters, bank frame/camera
agreement and world construction geometry registration. Each check has shared
accepted/rejected fixtures consumed by canonical Python validation and TS.
Tool save runs canonical Python source-set validation too. Generated structural
schema passing alone never certifies that a recipe is executable or coherent.

The completion matrix adds per row: source document/JSON pointer, editor control,
compiled destination, save-round-trip case, live/Studio parity case, performance
case where applicable and reviewer receipt. Do not mark fields complete based solely
on their being printed in a read-only JSON inspector.
