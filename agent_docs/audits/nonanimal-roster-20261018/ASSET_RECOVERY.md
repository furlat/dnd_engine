# Recovered portrait and spell icon locations

2026-10-18. User-requested filesystem search and exact source comparison only.
No artwork imports, runtime mapping edits, resizing, packing or generation were
performed. Earlier generic statements that portrait/icon work remained pending
must be read with this recovered artwork inventory: most art already exists;
new native associations and selected delivery installation are still pending.

The updated handoff supplied later on 18 October adds all seven previously
missing zombie portraits and all five dedicated NPC/Unarmed icons. Matching
portrait artwork now exists for **all 148 admitted NPCs**. The combined delivery
now contains **190 icons and 19 portraits, 209 selected runtime files**. These
new additions have not yet been installed in the inspected Godot UI resources.

## NPC portraits

The original Windows source bank is:
`/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/banks/creature-portraits-bg1-2026-10-08`

Its manifest contains 229 portraits, and all 229 native preview files exist.
Matching literal `sourcePack` and `sourceVariant` to the current 148 admitted
NPC rows finds **141 matching portraits**. All 141 are also physically installed
in both `/home/tommaso/Dev/NDClient/.media/ui/portraits/192x256/` and
`/mnt/c/Users/tommaso/Documents/Dev/NDClientData/.media/ui/portraits/192x256/`.

- Twenty-five retained NPCs already have native `portrait:creature.*` resource
  assignments in all three inspected client resource documents.
- The other 116 matching portraits already have source artwork resource keys
  (for example `portrait:orcs_goblins--orc-02`), but the newly authored NPC IDs
  have not yet been associated with those existing resources.
- The seven former portrait gaps are HD ZombieRadioactive1/2/3 and top-down
  Zombie Radioactive01/02/03/04. The updated combined delivery now supplies
  their exact native portrait keys and authored names. Their source files are
  recorded in the CSV as `recovered_new_portrait_not_installed`. Together with
  the older bank this covers all 148 admitted NPCs. Their ordinary Zombie rules
  do not change because of the vendor's Radioactive label.

[All148 source rows and exact files](portrait_asset_recovery.csv) are preserved
as offline audit data. This identifies delivered source art; it does not claim
new visual acceptance or completion of sprite/rig/action authoring.

## Spell icons and additional summon portraits

The user supplied the complete combined handoff:
`/mnt/c/Users/tommaso/Documents/Codex/2026-10-15/bg3-36-spell-icons-20261015/outputs/combined/HANDOFF.html`

It includes **both batches:36+22=58 spells** and the NPC additions:190 new
48px RGBA icons and19 new192×256 portraits. All209 selected runtime files
exist. There are 57 new
spell-root drawings; Divine Smite reuses the existing reaction artwork. The
other133 new icons cover choices/forms, follow-up actions, creature techniques,
traits, temporary items, independent statuses and the NPC additions.

The complete selected old icon bank is:
`/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/banks/ui-icons-bg3-glyphs-2026-10-07`

It has 594 images for 620 UI keys (129 spell-family images in its manifest).
The installed client derivative is `ui/icons/smooth48/`; the original delivery
also retains smooth144 authoring files. Comparison against the current **181 roots in `SPELL_CONTENT_DECLARATIONS`** finds:

| Current spell roots | Existing artwork | Client status |
| --- | --- | --- |
| 124 | Exact keys in the older bank | Existing resource and installed image |
| 35 | New exact keys in combined `runtime/smooth48/` | Not installed in inspected client UI |
| 22 | Explicit `srd22.spell.*` artwork in combined delivery | Source semantic keys need association with current native spell IDs; not installed |
|**181** | **All 181 have recovered source artwork** | **57 new roots still need client integration** |

The 22 later delivery records explicitly lack native IDs. Their subjects match
the current implemented spell names, and every recorded artwork file exists.
For example current `spell.forcecage` has source drawing
`runtime/smooth48/srd22.spell.forcecage.png`. This report records that comparison;
it does not change descriptors or install a name-based runtime resolver.
[All 181 native spell roots and actual files](spell_icon_asset_recovery.csv)
record exact native IDs, icon keys, source artwork keys and current client status.

The full SpellCatalog composition has six further rows outside that declaration
inventory: Thaumaturgy, Aegis Spark, Hellish Rebuke, Shield, Counterspell and
Divine Smite. The first five have exact older-bank icons. Divine Smite has the
combined handoff's explicit existing-art reuse, `reaction.divine-smite`; its
`spell.divine_smite` resource association remains pending. Thus all187 complete
composition rows also have recovered artwork. The181-row CSV deliberately
covers the declaration inventory rather than silently mixing the two scopes.

The12 summon portraits are Air/Earth/Fire/Water Elementals, the corresponding
four Myrmidons, Deva, Djinni, Cambion and Draconic Spirit. They belong to the
summon delivery, rather than the148 nonanimal source queue. The other seven new
portraits are Fallow One/Two/Three and Marshglass One/Two/Three/Four, with exact
native `creature.zombie_*_radioactive_*` keys. Follow-up actions,
status/choice identities and summon portrait/rig associations still need
comparison with current native owners before integration; existing handoff
binding proposals are historical inputs, not current runtime certification.

## Actual client locations

Current Godot project:
`/mnt/c/Users/tommaso/Documents/Dev/NDClientGodot`

`project.godot` selects its own `authoring/` and the external Windows media root:
`/mnt/c/Users/tommaso/Documents/Dev/NDClientData/.media`

Older web client:
`/home/tommaso/Dev/NDClient`

All three inspected resource documents (Godot, Windows NDClientData and Linux
NDClient) contain 1286 records: 620 icon keys and 666 portrait keys, including
five premade aliases. The Linux and Windows media trees each contain 594 old
icon PNGs and 661 portrait PNGs. The new 57 spell-root resources are absent in
those inspected resource documents. This is an inventory/read check, not a
new running-client or image-style acceptance test.

The same-task plan guard independently verified all141 portrait matches, all987
source-format images for those portraits, the116 existing source choices in
all three resource documents, all197 combined runtime files, and the exact
names/keys of all22 later spell subjects. It also identified and checked the
six composition-only spell rows above. No additional root drawing gap was found.

## New NPC ability icons, updated delivery

The first check found four new NPC mechanics without dedicated drawings and
the older Unarmed/Fist gap. The updated handoff now supplies all five. Native
descriptor keys match the four ability drawings exactly; `item.unarmed` is a
UI artwork key for the existing Unarmed selection, not a new native item.

| Ability | Native icon key |
| --- | --- |
| Assassinate | `trait.assassinate` |
| Evasion | `trait.evasion` |
| Spell Damage Resistance | `trait.spell_damage_resistance` |
| Shield Bash | `action.monster.shield_bash` |
| Unarmed / Fist | `item.unarmed` for `common.unarmed.presentation.icon_key` |

All five files are under the combined delivery's `runtime/smooth48/`, named
by those exact artwork keys. The seven new portraits are under
`runtime/portraits192x256/`, named by their exact native portrait keys. All12
new files have verified PNG dimensions and color types: five48×48 RGBA icons
and seven192×256 RGB portraits. The seven labels/IDs match our native roster,
and none of these12 resources is yet present in the inspected Godot UI map.

Help Attack also lacks its exact `action.help_attack` resource. The combined
delivery already contains `action.ally_help` artwork; reuse of that shared Help
glyph is available as an explicit presentation choice. Assassin Poison's new
condition key lacks an assignment; the existing Weapon Coat item drawing is
available for reuse. These are reuse proposals, not applied runtime mappings.

Brute, Parry, Leadership, Leadership Aura, Undead Fortitude, Protection and Magic
Resistance already resolve to existing bank art and installed resources. No
replacement drawings are needed merely because a new NPC uses them.

The current client's `common.unarmed.presentation.icon_key` remains null until
integration assigns the newly delivered `item.unarmed` artwork. It is relevant
to the two trained fist fighters. No Monk class or progression was added by the
NPC batch. Source proposal: `sources/npc-gap/binding-proposal.json`; the source
proposal and delivered artwork do not by themselves apply client changes.

Independent PNG-header inspection confirms the combined delivery contains
exactly 185 RGBA 48×48 icons and 12 RGB 192×256 portraits. The six existing
icon resources used by the broader composition also resolve to actual files
under Godot's configured Windows media root. The combined manifest records
`humanAccepted: false` for all 197 new assets: recovered availability is not
new human visual acceptance, native association or runtime playback validation.
