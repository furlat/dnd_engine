# Purchased fixed creature pack study — undead and enemies

**SRD-first revision authority (30 September 2026):** this report preserves
archive/visual evidence and earlier proposals. Proposed mechanics below,
including sections labelled “selected design”, are superseded by the
[full-SRD rematch](PACK_ROSTER_SRD_FIRST_UNDEAD_ENEMY_2026-09-30.md) and
[reconciled synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md).
Use SRD 5.1 first, 5.2 secondary adapted to 5.1, with explicit changes for
actual visible equipment. Earlier custom action/spell/gear choices are not
competing current selections. Later named visual reinspections in the rematch
also take precedence over the corresponding earlier observation.

**Final roster authority:** use the [focused completion](PACK_ROSTER_UNDEAD_ENEMY_COMPLETION_2026-09-30.md)
and [full synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md). The completion
adds relevant action strips for all 100 identities, selects native kit/action
proposals, corrects the Skeleton Warrior's longsword loadout, and distinguishes
firearm-like Enemy/Top-down Soldier art from melee HD Soldier art. The original
candidate/profile tables below retain the earlier provisional study.

Date: 2026-09-30. This is a read-only source-art inventory and evidence report for four original ZIP archives in `/mnt/c/Users/tommaso/Documents/assets/smallscale/`. Originals in `Downloads` were not counted again. Selected samples for private visual review are in `.runtime/pack-study-20260930/undead-enemies/`; the full source art remains in its original archives. This study imported nothing and changed no runtime, recipe, binding, or native content.

## Findings that affect NPC authoring

The archives offer fixed characters with authored clothing, armor, weapons, and sometimes attack trails already drawn into their frames. That is evidence about the character picture, not evidence for a creature's statistics, proficiency, attacks, spells, or selectable inventory. Keep the native NPC/equipment/ability content keyed by stable content identities and disclosed game facts. Let rendering select a fitting fixed rig or modular rig independently; neither gameplay nor item construction should depend on a source sprite name or clip label.

One fixed rig is currently installed: `smallscale.skeletonarcher05`, bound to `creature.skeleton_archer@1`. Its body sheets use the fixed 5Archer skeleton image, whose bow is baked into the body. It currently has six clips: `Idle`, `Run`, `TakeDamage`, `Die`, `Rolling`, and `Attack3` mapped to `QuickShot`; the last mapping is explicit in the rig data and is the only semantic use of that numbered clip for this fixed archer. The rig has one body slot and sources the Shadowless body. The corresponding `With shadow` sheets exist in the same archive, but this rig does not currently select a separate shadow layer. Its chosen 12 FPS, 128px cells, frame selection, support point, and anchor are installation choices; the archive does not supply FPS or pivot metadata. See [skeletonarcher05.json](../../game/data/rigs/skeletonarcher05.json).

Current presentation selection is explicit in the existing data: `bindings.json` sets `neuroclient.modular` as the root and includes only `creature.skeleton_warrior@1` in its modular creature refs; `skeletonarcher05.json` independently binds `creature.skeleton_archer@1` to fixed `5Archer` art. The modular warrior intentionally has `NakedBody2` and its authored armor-scraps, longsword, and shield loadout; the fixed `6Warrior` picture has a spear silhouette. Both are valid intentional presentations of their respective game identities. Their differences are not a defect and do not constrain canonical Skeleton loadouts: freely composed skeleton NPCs remain able to use the modular body and rich authored equipment, even when that would not fit `6Warrior` art. Existing Skeleton Archer content separately authors armor scraps, shortbow, two daggers, and Mark Target; these are facts about that authored creature, not a rule for another skeleton merely because an image depicts a bow. The fixed archer rig has one body slot and no registered shadow slot; it currently binds Shadowless sheets, although its archive also contains corresponding With shadow sheets and paired pixels suitable for further shadow-separation study.

## Archive inventory

Archive counts below include PNGs only and count each selected archive once.

| Archive | Source PNGs | Distinct named fixed families | Source organization |
| --- | ---: | ---: | --- |
| `2D HD Undead pack 1.zip` | 34,382 | 9 skeletons | 8 directional frame sequences per clip, plus Shadowless/With shadow sprite sheets |
| `2D HD Enemy pack 1 (1).zip` | 17,568 | 13 humanoid/elemental/animal families | 8 directional frame sequences per clip, plus Shadowless/With shadow sprite sheets |
| `2D HD Zombie pack 1 V1.1.zip` | 1,100 | 36 named zombie variants plus shared Acid/Blood effects | One 15-column by 8-row direction sheet per clip, with Shadowless and With shadow versions |
| `2D Zombie pack 2 - Top down v1.1.zip` | 2,160 | 42 named zombie variants | One 15-column by 8-row direction sheet per clip; combined shadow and a separate shadow strip are both provided |

The names and files below are the archive names as supplied, including their original numbering and capitalization. For all eight-way sheets, 1920x1024 PNGs resolve to 15 columns × 8 rows of 128px cells; some families' larger sheets resolve to 2880x1536 (15 × 8 cells of 192px). The HD archive frame sequences are organized by clip and direction (`E`, `SE`, `S`, `SW`, `W`, `NW`, `N`, `NE`) and numbered in 15 samples from 001 to 029 in steps of two. The numbering establishes sample order, not a source framerate. None of these four ZIPs supplies timing/pivot metadata in the inspected archive file list; source FPS, contact frames, per-direction pivot adjustments, and intended runtime playback rate therefore remain unknown. Do not treat the currently installed rig's 12 FPS as source FPS.

## Families and animation names

### Labeled idle contact evidence

The following private source-derived contact sheets show one matching Idle/Idle 1 pose for **all 9 Undead families, all 13 Enemy families, all 36 HD Zombie variants, and all 42 top-down Zombie variants**. We viewed every tile. They establish visible body/build, broad costume, color differences, and whether an object silhouette is evident in this chosen idle pose; they do not establish a held item in every direction/animation. `With shadow` / combined-shadow source art was selected where available. The full uncropped source family/animation sequences remain in the supplied ZIP files.

- [Undead family sheet: 9/9](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/undead-idle-contact.png)
- [Enemy family sheet: 13/13](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/enemy-idle-contact.png)
- [HD Zombie variants 1–18](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/hdz-idle-contact-01-18.png) and [19–36](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/hdz-idle-contact-19-36.png)
- [Top-down Zombie variants 1–18](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/top-idle-contact-01-18.png), [19–36](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/top-idle-contact-19-36.png), and [37–42](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/undead-enemies/idle-atlas/top-idle-contact-37-42.png)

Frame timings, contact timing, and action meaning have **not** been established for every catalogued clip. Only the five named attacks in Evidence Boundaries were visually inspected. Roster candidates below are flavor-design proposals, not certified or implemented NPC content. Gear confidence (`H/M/L`) reports how clear the gear silhouette is in the selected idle image; `U` means gear is not established from the reviewed idle image. A confident visual label still does not establish the native item/action to use.

### 2D HD Undead pack 1

All nine families have the common clips `180Turn`, `Attack1`, `Attack2`, `Attack3`, `AttackRun`, `BlockMid`, `BlockStart`, `CastSpell`, `CrouchIdle`, `CrouchRun`, `Die`, `FrontFlip`, `Idle`, `Idle2`, `Pummel`, `QuickShot`, `QuickSlide`, `Rolling`, `Run`, `RunBackwards`, `SittingChair`, `Special1`, `Special2`, `StrafeLeft`, `StrafeRight`, `TakeDamage`, `UnSheath`, and `Walk`. Additional clip availability differs as follows:

| Family name | Additional clip names |
| --- | --- |
| `1Brute` | `Slide`, `SlideEnd`, `SlideStart` |
| `2DeathLord` | `Slide`, `SlideEnd`, `SlideStart` |
| `3DarkKnight` | `Kick`, `Slide`, `SlideStart` |
| `4Berserker` | `Kick` |
| `5Archer` | `Kick`, `Slide`, `SlideEnd`, `SlideStart` |
| `6Warrior` | `Kick` |
| `7DarkArcher` | `Kick`, `Slide`, `SlideEnd`, `SlideStart` |
| `8Necromancer` | `Kick`, `Slide`, `SlideEnd`, `SlideStart` |
| `9Wizard` | `Kick`, `Slide`, `SlideEnd`, `SlideStart` |

Visual review confirms that the named family and its base weapon/costume are already combined into each sheet, not free equipment slots. In the reviewed samples, `5Archer` visibly carries its bow and has bow-oriented `QuickShot`; `2DeathLord` carries a large blade and its reviewed `Attack1` includes a large yellow-orange arc in the image sequence. That arc is visible pre-rendered attack art, not proof of a magical attack, damage type, or a separately targetable effect. The pack includes both Shadowless and With shadow sheet folders, each containing complete alternatives. Neither folder is itself an independently registered body/shadow pair.

### 2D HD Enemy pack 1

Families `1Hammer`, `2Shooter`, `3Footsoldier`, `4Assassin`, `5Bruiser`, `6Crusader`, `7Sniper`, `8Brawler`, `9Commander`, `10Caster`, `11Arcane elemental`, and `12Guard` each contain `Attack1`, `Attack2`, `Attack3`, `Attack4`, `Die`, `Idle`, `Idle2`, `Run`, `TakeDamage`, `Taunt`, and `Walk`. `13Shepard` has the common attacks, death, idles, run, damage, and walk plus `Howl` and `Sneak`, with no `Taunt`. Each clip is present for all eight directions. The spritesheet directory supplies both complete Shadowless and With shadow alternatives.

Visually reviewed `2Shooter` sheets retain their authored weapon and show distinctly different attacks; the reviewed `Attack3` contains a broad blue/red arc around the character. Treat that as an image-space baked trail in this clip, not a schema that the creature has a spell, a particular projectile, or an equipment-swappable attack. Other attack numbers have no generic melee/ranged meaning across these families. The names alone do not establish which attack to assign to an NPC action.

### 2D HD Zombie pack 1 V1.1

The archive has 36 character/color variants: `ZombieCop1`–`ZombieCop4`; `ZombieFemale1`–`ZombieFemale7`; `ZombieGeneral1`–`ZombieGeneral2`; `ZombieHulk1`–`ZombieHulk2`; `ZombieMale1`–`ZombieMale9`; `ZombieMonster1`–`ZombieMonster3`; `ZombieRadioactive1`–`ZombieRadioactive3`; and `ZombieSoldier1`–`ZombieSoldier6`.

Each variant has common sheets `Attack1`–`Attack5`, `CrouchRun`, `Die`, `Die2`, `Idle`, `Idle2`, `Run`, `TakeDamage`, `Taunt`, `WakeUp`, and `Walk`. Every variant has both complete Shadowless and With shadow sheet versions. Shared `Acid` and `Blood` folders each have real animation sheets numbered 1–5, also supplied as Shadowless/With shadow versions. Visual review of `Acid1` and `Blood1` shows animated green droplets and red blood flecks, respectively, not blank placeholders. Their exact gameplay interpretation and intended emitter/render registration are not supplied by these images. Reviewed zombie attacks show ordinary character poses; `Attack1` is not enough to assert weapon handling or a rules action.

### 2D Zombie pack 2 — Top down v1.1

There are 42 variants: `Zombie 01`–`Zombie 10`; `Zombie Cop 01`–`Zombie Cop 04`; `Zombie Decay 01`–`Zombie Decay 05`; `Zombie Fireman 01`–`Zombie Fireman 02`; `Zombie Radioactive 01`–`Zombie Radioactive 04`; `Zombie Soldier 01`–`Zombie Soldier 05`; `Zombie Swamp 01`–`Zombie Swamp 09`; and `Zombie Worker 01`–`Zombie Worker 03`.

The 40 standard variants (`Zombie 01`–`10`, `Zombie Cop 01`–`04`, `Zombie Decay 02`–`03` and `05`, both Firemen, all four Radioactive, all five Soldiers, all nine Swamp, and all three Worker variants) have `Attack 1`, `Attack 2`, `Attack Run 1`, `Bite`, `Crawl`, `Crouch bite`, `Die (Gore)`, `Die`, `Emerge`, `Idle 1`, `Idle 2`, `Run`, `Stand up 1`, `Stand up 2`, `TakeDamage`, `Taunt`, and `Walk`. Seven variants (`Zombie Cop 01`, `Zombie Cop 03`, `Zombie Cop 04`, `Zombie Soldier 01`, `Zombie Soldier 02`, `Zombie Soldier 04`, and `Zombie Soldier 05`) each add `Attack 3` and `Attack run 2`. `Zombie Decay 01` and `Zombie Decay 04` have instead the specialized clip set `Die (Gore)`, `Die`, `Emerge`, `Idle`, `Melee Uppercut`, `Run`, `TakeDamage 1`, `Zombie Bite 2`, `Zombie Scream 1`, `Zombie Stand 1`, `Zombie Stand 2`, `Zombie bite 1`, and `Zombie melee 1`.

For typical clips this archive includes both a combined `Zombies with shadow/<family>/<clip>.png` sheet and a separable pair: `Zombies Shadowless/<family>/<clip>.png` plus `Zombies Shadowless/<family>/Shadows/<clip>.png`. The separate shadow sheet is real visible-alpha art (the reviewed `Zombie Soldier 01/Attack 1` body and corresponding shadow are both 1920x1024 RGBA images with nonzero alpha coverage); the pair uses the same sheet dimensions and cell grid. Use the actual matching pair and verify registration whenever selecting the separate version. Preserve the combined option too: where an importer/runtime needs a fast fixed image, the archive's combined shadow output is legitimate source art, not a failed or missing layer. The reviewed Soldier Idle visibly carries a firearm; `Attack 1` visibly raises/uses a weapon, and the separately named `Bite` is a visibly different presentation. Those images still do not define a native weapon profile, firearm rules, or which attack action the NPC owns.


## Proposed one-to-one NPC flavor roster (design proposals only)

Each source variant below gets an individually named NPC proposal. Repeated colors/costumes share the group composition and ability policy in the second table rather than receiving duplicate mechanics. **Gear is an Idle-art observation, not an item grant or stat-block.** A viable RPG roster would first decide the actual creature identity, stats, native loadout, attacks, and campaign setting in game data; presentation can then select art that depicts those declared facts. The art can be selected or rejected independently of the canonical game content.

### Undead pack — nine NPC pitches

| Source variant | Proposed NPC name / role | Observed Idle dress or gear | Profile |
| --- | --- | --- | --- |
| `1Brute` | The Tombbreaker — skeletal bruiser | Broad, exposed bone and ragged dark coverings; no held weapon confidently visible (L). | `S-BRUTE` |
| `2DeathLord` | Lord Ashveil — armored grave lord | Enlarged close-up of the Idle pose shows dark armor/cape, a large angular shield (H), and a vertical orange-edged held weapon (M; item type uncertain). | `S-LORD` |
| `3DarkKnight` | The Gloam Knight — armored duelist | Dark armor silhouette; held gear/type not resolved (L). | `S-KNIGHT` |
| `4Berserker` | Redwake the Shattered — berserk undead | Ragged armor and red accent; weapon not resolved (L). | `S-RAGE` |
| `5Archer` | Gravesight — skeleton archer | Bow held by the fixed body (H); it is baked into the sprite. | `S-ARCHER` |
| `6Warrior` | Pikeward — skeletal spearman | Long spear/pole weapon at the side (M/H); no exact item identity. | `S-SPEAR` |
| `7DarkArcher` | The Black Fletch — dark skeleton archer | Bow silhouette (H); equipment beyond the bow is not established. | `S-ARCHER` |
| `8Necromancer` | The Violet Bell — undead spellcaster | Caster dress and a bright purple hand/effect (H); no separate held focus resolved. | `S-CASTER` |
| `9Wizard` | Candlebone — robed skeleton caster | Light/red robe and a vertical rod/staff-like silhouette (M); item type unverified. | `S-CASTER` |

### Enemy pack — thirteen NPC pitches

| Source variant | Proposed NPC name / role | Observed Idle dress or gear | Profile |
| --- | --- | --- | --- |
| `1Hammer` | The Bellringer — heavy striker | Tall armored fighter with prominent long hammer (H). | `E-MARTIAL` |
| `2Shooter` | Blue Quarrel — ranged skirmisher | Compact ranged-weapon silhouette, likely bow/crossbow family (M; exact type unverified). | `E-RANGED` |
| `3Footsoldier` | Gateplate — shield foot soldier | Heavy shield and a short held weapon (H/M; weapon type unclear). | `E-SOLDIER` |
| `4Assassin` | The Blue Knife — infiltrator | Dark/blue hooded, slim silhouette; blade not resolved from Idle (L). | `E-INFILTRATOR` |
| `5Bruiser` | The Iron Shoulder — barehanded heavy | Broad, heavily built body and large hands; no handheld weapon apparent (H). | `E-BRUISER` |
| `6Crusader` | Reliquary — armored defender | Full blue armor, large shield, and other handheld gear (H for shield; weapon identity M). | `E-ELITE` |
| `7Sniper` | Far-Eye — ranged scout | Blue hood and long ranged-weapon-shaped object (M; bow, crossbow, and firearm are not distinguished by Idle). | `E-RANGED` |
| `8Brawler` | The Dockwall — unarmed close fighter | Very broad bare-handed body; no held weapon apparent (H). | `E-BRUISER` |
| `9Commander` | Magister Nine — commanding caster/leader | Dark blue clothing with bright magenta hand-mounted/glowing shapes (M; gear versus baked effect unknown). | `E-LEADER` |
| `10Caster` | Pale Ember — spellcaster | Robed figure with a pale blue glow near hands/upper body (M; focus not resolved). | `E-CASTER` |
| `11Arcane elemental` | Violet Static — living arcane force | Magenta glowing body/effect; no independent handheld gear (H). | `E-ELEMENTAL` |
| `12Guard` | Bronze Watch — guard | Gold-toned guard costume and an upright long object (L/M; weapon type uncertain). | `E-GUARD` |
| `13Shepard` | Hearth-Hound — canine scout | Quadruped brown-and-black dog in eight-direction Idle, with no worn/held gear apparent (H). | `E-HOUND` |

### HD Zombie pack — 36 individual names, recolors grouped by source family

| Source variant | Proposed NPC name / role | Observed Idle dress or gear | Profile |
| --- | --- | --- | --- |
| `ZombieCop1` | Deputy Ash — shambling constable | Blood-marked dark civilian/police-like clothing; insignia/weapon not resolved (L). | `Z-DEAD` |
| `ZombieCop2` | Whitecoat Vale — pale-shirt constable | Pale shirt and dark uniform details (M); no firearm established in this image. | `Z-DEAD` |
| `ZombieCop3` | The Last Beat — gray-shirt constable | Gray/dark clothing palette (L); no held gear established. | `Z-DEAD` |
| `ZombieCop4` | Blue Shield — armored constable | Clearly distinct dark-blue protective armor/uniform (H); held weapon not established. | `Z-DEAD` |
| `ZombieFemale1` | Marigold — amber-dressed walker | Amber/yellow top and dark lower clothing; no held gear visible (H). | `Z-DEAD` |
| `ZombieFemale2` | Ash-Blue June — pale blouse walker | Light blouse and muted-blue accents; no gear visible (H). | `Z-DEAD` |
| `ZombieFemale3` | Copper Jane — red-haired walker | Reddish hair and pale/dark civilian clothes; no gear visible (H). | `Z-DEAD` |
| `ZombieFemale4` | Fen Green — green-skirt walker | Pale-green top and dark-green lower clothing (H). | `Z-DEAD` |
| `ZombieFemale5` | Roseglass — mauve-clothed walker | Pale top, mauve accents; no held gear (H). | `Z-DEAD` |
| `ZombieFemale6` | Night Shift — dark-haired walker | Dark outfit and short dark hair; no gear visible (H). | `Z-DEAD` |
| `ZombieFemale7` | Deep Teal — teal-dressed walker | Teal clothing and dark hair; no gear visible (H). | `Z-DEAD` |
| `ZombieGeneral1` | The Brown General — undead officer | Brown military-style coat and head/shoulder distinction (M); rank-specific details not resolved. | `Z-DEAD` |
| `ZombieGeneral2` | The Black General — undead officer | Dark military-style coat, small red accent (M). | `Z-DEAD` |
| `ZombieHulk1` | Greenbulge — mutated heavy | Very large frame and bright green growth/glow (H); no held gear. | `Z-BULK` |
| `ZombieHulk2` | White Knuckle — mutated heavy | Very large pale frame with dark patches (H); no held gear. | `Z-BULK` |
| `ZombieMale1` | Olive Trousers — civilian dead | Dark jacket with olive lower clothing (H). | `Z-DEAD` |
| `ZombieMale2` | The White Shirt — civilian dead | Pale/white top with red damage and dark trousers (H). | `Z-DEAD` |
| `ZombieMale3` | Blue Sleeve — civilian dead | Pale upper clothing and blue trousers (H). | `Z-DEAD` |
| `ZombieMale4` | Poolside — civilian dead | Teal top and pale blue trousers (H). | `Z-DEAD` |
| `ZombieMale5` | Saffron Shirt — civilian dead | Yellow clothing (H); no held gear. | `Z-DEAD` |
| `ZombieMale6` | Nightcoat — civilian dead | Dark top and pale/green trousers (H). | `Z-DEAD` |
| `ZombieMale7` | Green Vest — civilian dead | Green/dark clothing (H). | `Z-DEAD` |
| `ZombieMale8` | Red Thread — civilian dead | Brown and dark-red clothing (H). | `Z-DEAD` |
| `ZombieMale9` | Rust Collar — civilian dead | Teal and brown clothing details (H); no held gear. | `Z-DEAD` |
| `ZombieMonster1` | The Narrow One — malformed dead | Slender pale body with tattered lower clothing (H); no gear visible. | `Z-MUTANT` |
| `ZombieMonster2` | Red Suture — malformed dead | Red head/body accent and dark lower clothing (H). | `Z-MUTANT` |
| `ZombieMonster3` | Heavy Pale — malformed brute | Stout pale upper body and blue trousers (H); no held weapon. | `Z-BULK` |
| `ZombieRadioactive1` | The Green Reactor — glowing mutant | Heavy pale frame with intense green torso glow (H). | `Z-GLOW` |
| `ZombieRadioactive2` | Thinlight — glowing mutant | Slender body with bright green edge glow (H). | `Z-GLOW` |
| `ZombieRadioactive3` | The Spill — glowing mutant | Pale/green-corroded body and edge glow (H). | `Z-GLOW` |
| `ZombieSoldier1` | Last Watch — fallen soldier | Dark brown military uniform (H); no weapon clear in selected Idle tile. | `Z-SOLDIER` |
| `ZombieSoldier2` | Helm Rust — fallen soldier | Muted olive/gray military dress (H). | `Z-SOLDIER` |
| `ZombieSoldier3` | Hooded Line — fallen soldier | Dark head/hood and military-colored outfit (M). | `Z-SOLDIER` |
| `ZombieSoldier4` | Cinder Company — fallen soldier | Dark uniform with pale/olive highlights (M). | `Z-SOLDIER` |
| `ZombieSoldier5` | Brass Button — fallen soldier | Olive/yellow uniform (H). | `Z-SOLDIER` |
| `ZombieSoldier6` | Coal Detail — fallen soldier | Dark gray/black uniform (H). | `Z-SOLDIER` |

The HD Zombie contact sheet indicates many source rows are palette or outfit-color variants of the same portrait silhouette, rather than evidence for 36 separate rulesets. The word `Soldier` does not show a clear firearm in the selected Idle tile. Keep that inventory and the Acid/Blood visual sheets available as explicit art choices; do not assume they create firearm proficiency or corrosive/blood combat abilities.

### Top-down Zombie pack — 42 individual names, costume variants grouped by source family

| Source variant | Proposed NPC name / role | Observed Idle dress or gear | Profile |
| --- | --- | --- | --- |
| `Zombie 01` | Corner Walker — civilian dead | Dark jacket over teal clothing; no held weapon apparent (H). | `Z-DEAD` |
| `Zombie 02` | Viridian Scour — changed dead | Pale body, green/purple upper-body mutation (H). | `Z-GLOW` |
| `Zombie 03` | White Collar — civilian dead | Dark blue clothing and pale hair/head; no held item visible (H). | `Z-DEAD` |
| `Zombie 04` | Barefoot Red — civilian dead | Ragged pale/black and red clothing; no weapon visible (H). | `Z-DEAD` |
| `Zombie 05` | The Lab Runner — civilian dead | White, coat-like clothes with pale head (M; no medical occupation inferred). | `Z-DEAD` |
| `Zombie 06` | Gold Fringe — civilian dead | Yellow hair/head and gray clothes (H). | `Z-DEAD` |
| `Zombie 07` | The Shroud — robed dead | Long gray/pale outer clothing (H); no weapon visible. | `Z-DEAD` |
| `Zombie 08` | Acid Bloom — changed dead | Green/yellow body effect and gray outfit (H). | `Z-GLOW` |
| `Zombie 09` | Violet Stitch — changed dead | Purple/yellow head and upper-body accents (H). | `Z-GLOW` |
| `Zombie 10` | The Iron Stranger — civilian dead | Gray outfit with red accents; no distinct item established (L). | `Z-DEAD` |
| `Zombie Cop 01` | Night Patrol — undead officer | Dark-blue uniform, light belt/accents; no specific held weapon resolved (M). | `Z-SECURITY` |
| `Zombie Cop 02` | The Pale Patrol — undead officer | Blue police clothing and pale head; item not resolved (M). | `Z-SECURITY` |
| `Zombie Cop 03` | Amber Siren — undead officer | Bright yellow/gold outer clothing with red accents (H); weapon not resolved. | `Z-SECURITY` |
| `Zombie Cop 04` | Whitewall — undead officer | Blue/white uniform and outer garment (H); weapon not resolved. | `Z-SECURITY` |
| `Zombie Decay 01` | Undercrypt One — downed corpse | Distinct prone/collapsed idle and pale/red decay palette (H). | `Z-EMERGE` |
| `Zombie Decay 02` | Funeral Suit — decayed dead | Upright white/red clothing and brown hair (H). | `Z-DEAD` |
| `Zombie Decay 03` | Wine-Stain Walker — decayed dead | Pale and red/purple clothing details (H). | `Z-DEAD` |
| `Zombie Decay 04` | Undercrypt Four — downed corpse | Prone/collapsed idle with a different palette from Decay 01 (H). | `Z-EMERGE` |
| `Zombie Decay 05` | The Mossed Coat — decayed dead | Pale head with green/olive clothing (H). | `Z-DEAD` |
| `Zombie Fireman 01` | Flashover — undead responder | Bright yellow/red protective responder uniform (H); tool not resolved. | `Z-DEAD` |
| `Zombie Fireman 02` | Backdraft — undead responder | Same protective-service silhouette in a related palette (H); tool not resolved. | `Z-DEAD` |
| `Zombie Radioactive 01` | Reactor Hiss — glowing dead | High-visibility bright green body/limb glow (H). | `Z-GLOW` |
| `Zombie Radioactive 02` | Greenflare Two — glowing dead | Strong green head/arm effect (H). | `Z-GLOW` |
| `Zombie Radioactive 03` | Wastelight — glowing dead | Green body glow with pale/gray clothing (H). | `Z-GLOW` |
| `Zombie Radioactive 04` | Last Warning — glowing dead | White/green irradiated look and darker torso (H). | `Z-GLOW` |
| `Zombie Soldier 01` | Trench Echo — fallen soldier | Olive/tan military clothes; long firearm-shaped object is visible (M/H); exact weapon not established. | `Z-SOLDIER-GUN` |
| `Zombie Soldier 02` | Khaki Warden — fallen soldier | Tan/olive military uniform; possible held long weapon is less clear in this Idle sample (M). | `Z-SOLDIER-GUN` |
| `Zombie Soldier 03` | Brass March — fallen soldier | Yellow/olive uniform and tactical clothing (M); weapon not established from Idle. | `Z-SOLDIER` |
| `Zombie Soldier 04` | Cinder March — fallen soldier | Tan/olive military clothing with green effect/detail (M); weapon not resolved. | `Z-SOLDIER` |
| `Zombie Soldier 05` | Green Beret — fallen soldier | Dark green/red military clothing; weapon not resolved (M). | `Z-SOLDIER` |
| `Zombie Swamp 01` | Reed Stalker — bog dead | Dark green/black and swamp-toned ragged clothes; no gear visible (H). | `Z-DEAD` |
| `Zombie Swamp 02` | Fen Wader — bog dead | Green, red, and brown costume (H); no handheld item visible. | `Z-DEAD` |
| `Zombie Swamp 03` | Eelgrass — bog dead | Teal/blue-green outer clothing (H). | `Z-DEAD` |
| `Zombie Swamp 04` | Mudroot — bog dead | Low, hunched palette of brown/green (H). | `Z-DEAD` |
| `Zombie Swamp 05` | The Mirelight — bog dead | Muted green/red outer clothing (H); no gear. | `Z-DEAD` |
| `Zombie Swamp 06` | Rotwater — bog dead | Pale outfit with violet/green accents (H). | `Z-DEAD` |
| `Zombie Swamp 07` | Black Reed — bog dead | Green and dark-blue outer clothing (H). | `Z-DEAD` |
| `Zombie Swamp 08` | Pale Moss — bog dead | Pale body with gray/green and purple accents (H). | `Z-DEAD` |
| `Zombie Swamp 09` | Siltstep — bog dead | Brown/green clothes, low hunched pose (H). | `Z-DEAD` |
| `Zombie Worker 01` | Shift Bell — dead laborer | Yellow upper/headwear and blue work clothes (H); tool not resolved. | `Z-DEAD` |
| `Zombie Worker 02` | The Foreman — dead laborer | Brown/yellow workwear and hat (M); no tool confirmed. | `Z-DEAD` |
| `Zombie Worker 03` | Blue Overall — dead laborer | Pale upper body and blue work clothes (H); no tool confirmed. | `Z-DEAD` |

### Shared proposed content/composition profiles

These are starting points in the *existing* creature/item/ability owners, not new abstractions or completed definitions. A profile does not automatically grant visually suggested items or abilities: an author chooses actual native facts and a campaign context first. Stable per-NPC names above are flavor identities; repeated profile means shared mechanics are an intentional design option.

| Profile | Existing native candidate and candidate loadout | Signature (existing reuse versus an explicit NEW design option) |
| --- | --- | --- |
| `S-BRUTE` | Project `creature.skeleton`; its current authored loadout is a skeleton with shortsword and shortbow. If choosing hand-to-hand, author a suitable loadout/identity explicitly. | Existing skeleton undead facts/body response; no new ability inferred from broad build. Optional NEW shove only if creature design actually wants it. |
| `S-LORD` | Project `creature.skeleton_warrior` is a closer native candidate because its disclosed loadout already includes a shield; its shortsword/acid flask or another confirmed weapon is still distinct from the Idle art's unresolved orange-edged object. Author the true possession in game data, then use the fixed image only when that kit fits; otherwise keep the richer loadout on the modular skeleton body. | Existing fighter actions. Optional NEW leadership aura only with a decided native rule. No item type, magical property, or splash effect follows from color pixels. |
| `S-KNIGHT` | `creature.skeleton_warrior` is a candidate chassis, with equipment authored to match its chosen art. `creature.knight` is an SRD comparison for martial role, not an undead identity. | Existing `Parry`-capable system if explicitly included; no automatic parry or divine trait from dark armor. |
| `S-RAGE` | `creature.skeleton` project composition; use an actual authored weapon if needed. `creature.berserker` offers a martial-role comparison. | Existing `Reckless Attack` can be reused if selected; the `Berserker` art label alone does not grant it. |
| `S-ARCHER` | Project `creature.skeleton_archer` (armor scraps, shortbow, two daggers) is an exact native archer candidate. It currently has fixed `5Archer` art; choose other artwork or modular silhouette independently. | Existing Mark Target is available only because this specific native creature declares it. A bow on `7DarkArcher` does not inherit Mark Target automatically. |
| `S-SPEAR` | Project `creature.skeleton` or `creature.skeleton_warrior` composition with a spear expressly selected in its native item loadout. `6Warrior`'s spear picture does not override the modular warrior's intentional longsword+shield content. | Existing ordinary weapon actions. No distinct spear special inferred. |
| `S-CASTER` | Project `creature.skeleton_warlock` is the candidate native role; its authored spellcasting, staff, and shield reaction are richer content than the 8Necromancer/9Wizard Idle sheets prove. Add only the spells/items independently selected for that NPC. | Existing declared `Eldritch Blast`, `Burning Hands`, `Thunderwave`, `Necrotic Bless`, and Shield-reaction content available through this variant; no spell follows from a purple glow. |
| `E-MARTIAL` | Existing SRD `creature.veteran` / `creature.knight` candidates for trained heavy weapon users; choose a hammer item only after its identity/type is confirmed. | Existing multiattack/parry where that authored statblock has it. |
| `E-RANGED` | `creature.bandit` or `creature.scout` as native role candidates; existing crossbow/bow loadouts fit a verified fantasy bow silhouette. | Existing ranged weapon attacks only. If the long item proves modern firearm, see `Z-SOLDIER-GUN`; no firearm rule inferred here. |
| `E-SOLDIER` | `creature.hobgoblin` or `creature.guard` candidate; disclose actual shield and weapon as native possessions. | Existing Guard/Hobgoblin martial abilities only if their chosen game content has them. |
| `E-INFILTRATOR` | Existing SRD `creature.spy` candidate when stealth/shortsword/hand-crossbow gear fits the authored NPC. | Existing Cunning Action/Sneak Attack available to the Spy composition; Idle image does not prove either. |
| `E-BRUISER` | Existing `creature.bugbear`, `creature.thug`, or other authored bruiser composition; choose item/unarmed/natural attack based on the NPC's actual intended block. | Existing Brute property only in the game definition that grants it. Do not invent natural claws. |
| `E-ELITE` | Existing `creature.knight` candidate; disclose the shield and confirmed weapon natively. | Existing Brave/Leadership/Parry/Multiattack if selected in that content; armor art alone grants none. |
| `E-LEADER` | `creature.bandit_captain` is an existing native command role to adapt only if the actual humanoid identity/gear fit. | Existing Leadership/Multiattack systems are candidates; glowing magenta art is no spell/ability claim. |
| `E-CASTER` | Existing `creature.mage` or `creature.cult_fanatic` candidate; author actual spell and item facts. | Existing spellcasting/reaction content as explicitly included. No per-clip Attack-number inference. |
| `E-ELEMENTAL` | No exact stock elemental NPC in the reviewed creature roster. Proposal: one project-authored arcane creature composition in existing factory/native-action ownership; presentation uses its luminous art independently. | Optional NEW shared “arcane discharge” action if game design wants it; not implied by `Attack3` or pink pixels. No new framework. |
| `E-GUARD` | Existing `creature.guard` candidate, subject to resolving the long object and native loadout. | Existing attack/reaction behavior only; no mechanics inferred from label. |
| `E-HOUND` | Existing SRD `creature.wolf` candidate fits the visibly four-legged canine. | Existing wolf bite and Pack Tactics can be selected under native wolf rules. `Howl`/`Sneak` labels remain animation availability, not new mechanics. |
| `Z-DEAD` | Existing SRD `creature.zombie`: authored zombie slam plus undead traits (including Undead Fortitude); only the content author selects its real body/loadout. | Reuse native zombie slam and Undead Fortitude. Visual palette is cosmetic; no per-color ability. |
| `Z-BULK` | Existing `creature.zombie` candidate; `creature.ogre_zombie` is a role comparison only if the native size/loadout genuinely fits. Do not auto-apply its morningstar, CR, or statistics from big pixels. | Existing Undead Fortitude. Any extra HP/size/multiattack is a separate explicit NEW creature design. |
| `Z-GLOW` | Existing `creature.zombie` baseline plus independently designed optional mutation flavor. | Undead Fortitude reuse. Optional NEW shared irradiated aura/area action only if approved and authored as native mechanics; green pixels alone are cosmetic. |
| `Z-MUTANT` | Existing `creature.zombie` composition if undead humanoid facts fit. `creature.ghoul` is a comparison only if its paralysis/claw/bite rules are deliberately adopted. | Reuse zombie trait by default. Optional NEW shared mutation feature after game design; no mutation/stat change is inferred. |
| `Z-SOLDIER` | Existing `creature.zombie` baseline with native melee natural attack; this pack's selected Idle poses do not establish firearms. If a firearm is a wanted setting, author an equipment/action explicitly first. | Reuse zombie slam/Undead Fortitude. No ranged attacks from the word Soldier. |
| `Z-EMERGE` | Existing `creature.zombie`; select one of its authored, non-identical Decay variants as appearance. | Existing zombie traits. Optional NEW ambush/start-state rules require explicit design; `Emerge` alone is presentation. |
| `Z-SECURITY` | Existing `creature.zombie` baseline; police costume is not a declaration of gun possession. | Reuse zombie slam/Undead Fortitude; firearm profile, if desired, is a campaign/content addition. |
| `Z-SOLDIER-GUN` | The reviewed Top-down `Zombie Soldier 01` clearly has a long firearm-shaped object; the exact model/action is not certain, and other variant Idle tiles are less clear. Existing SRD Zombie is a creature baseline only; a matching one-to-one ranged NPC needs an optional modern setting weapon/item/action authoring decision. Current native content search found no standard firearm possession/action. An existing `environment.arcane_machine_gun` belongs to environment devices and is not a creature gun loadout. | Keep ordinary zombie slam if designing melee behavior. Ranged firearm attack is a **NEW optional campaign mechanic/item**; do not silently reuse arcane machine gun, shortbow, or shooter Attack clip. |

The native facts named above are candidates for authored composition, not claims every source variant is an SRD monster. A production NPC roster may share a few mechanics over many palette/wardrobe variants and can deliberately depart from SRD rules when labeled project-authored; each choice needs its own native identity/equipment and disclosed presentation. This table does not restrict a rich modular `NakedBody2` skeleton loadout to what any particular fixed family image depicts.

## Practical semantic guidance

Map native facts to existing semantic presentation opportunities only after the creature's native content declares those facts. A disclosed weapon attack could choose a clip whose viewed body action fits that weapon; a natural bite can use a visibly matching bite track; injury, death, and travel can use matching damage/death/walk/run tracks. Block, Kick, Pummel, Sneak, Howl, Crawl, Emerge, Stand up, WakeUp, Taunt, Crouch, Roll, Slide, UnSheath, CastSpell, or a baked attack trail are available *visual capabilities* where present. The filenames do not, by themselves, create a D&D ability, action economy, spell, special movement mode, vulnerability, equipment proficiency, or exact contact timing. `Special1`/`Special2` likewise remain unevaluated motions unless a particular character's frames are inspected and an authored native action requests an appropriate visual.

Evidence for positive semantic matches must include the frames themselves, the matching family/direction, and the source/installed mapping. Do not generalize `Attack1` through `Attack5` across these unrelated rigs, or infer an equipment contract from a baked fixed-character body. In particular, the currently installed Skeleton Archer's `Attack3` maps specifically to its source `QuickShot`, and that per-rig exception does not make every `Attack3` a ranged attack.

## Installed versus source-only

- **Installed fixed art:** only the six selected `SkeletonArcher05` body sheets named above from Undead family `5Archer`; no other family/clip from these four packs was found in the installed assets or public rig catalog for this study.
- **Already installed but different system:** the modular `NakedBody2` root rig and item-driven skeleton warrior equipment. This data lives under the existing NeuroClient modular tables and normal native item loadouts; it is not source art imported from these four archives.
- **Source-only in these packs:** all other 8 Undead families, all 13 Enemy families, all Zombie pack 1 variants and Acid/Blood effect sheets, and all Zombie pack 2 variants, clips, combined shadows, and separate shadow sheets.
- No other matching rig definitions were found under `game/data/rigs`. Current fixed skeleton archer provenance and constraints are authored directly in `skeletonarcher05.json`.

## Evidence boundaries

Archive enumeration established PNG counts, exact names, direction paths, clip availability, and the archive's paired-folder conventions. Individually labeled, one-pose Idle contact samples for **all 100 named variants** were inspected across the four generated private sheets. Five attack clips were separately viewed: Undead `5Archer`/`Attack3`, Undead `2DeathLord`/`Attack1`, Enemy `2Shooter`/`Attack3`, HD Zombie `ZombieSoldier1`/`Attack1`, and Top-down Zombie `Zombie Soldier 01`/`Attack 1`. Two representative source sheets were viewed from the shared Acid/Blood effect families; the Idle sheet and a body/shadow pair for Top-down Zombie Soldier 01 were also viewed. Idle inspection supports broad costume/gear silhouettes for every roster row, not all-direction certainty or all-motion semantics. The full inventory lists every source clip, but this is not visual adjudication of all clips or all tens of thousands of frames. Matching-pair alpha occupancy was decoded for that top-down Zombie Soldier `Attack 1` body/shadow pair. FPS, pivots, contact timing, exact native item/action correspondence, and action meaning beyond the five sampled attacks remain unverified. All NPC names, role mappings, content candidates, and any NEW feature labels above are explicit design proposals only; no rules are implemented or inferred from artwork.

## Independent anti-OOP/ECS review of the parent synthesis

**Assessment of `agent_docs/PACKED_CREATURE_CONTENT_STUDY_2026-09-30.md`: APPROVE its architectural direction, with the following bounded cautions for the content-design handoff.** I reviewed the synthesis as written alongside its current game/content/presentation owners; this approves the separation and reuse described, not any new rules or production implementation.

- **Shared owners are well chosen.** `bestiary_content.py`/`bestiary.py` and `srd_roster.py` own native creature composition and behavior; `authored_item_builders.py` plus `item_loadouts.py` own real possessions; existing behavior declarations/traits own shared actions. Rendering already has `AnimationData.creature_rigs`, `BodyRig`/`BodyClip`, and `AttackVariant`; use those at the presentation boundary. ECS entity/block/action data remain native truth; no per-sprite entity subclass or per-pack executor is indicated.
- **The native/presentation boundary is correctly retained.** A source costume is not a native item grant. Preserve real possessions, natural attacks, faction, stats and declared mechanics in the native composition, then let presentation select an inspected fixed body or the existing modular layers from a stable disclosed content identity/appearance. No renderer should branch through a live mutable `Entity`, read private inventory to infer a look, or add a source PNG/clip name to gameplay events. Retained event facts and existing replay ownership are sufficient for presentation to interpret old actions.
- **Skeleton clarification is accurately supported by live bindings.** Current modular binding selects `creature.skeleton_warrior@1` on `NakedBody2`; independent `skeletonarcher05.json` maps `creature.skeleton_archer@1` to fixed `5Archer`. Do not make the fixed archer/spear/body set a canonical limit on the modular skeleton's authored loadout.
- **Any rig-specific clip/timing override should stay declarative and narrowly shared.** The synthesis correctly sees a potential gap between semantic attack profiles and fixed-rig clips/anchors. If implementation proves a shared need, put the `(stable creature identity, disclosed attack facts) -> presentation clip/anchors/socket choice` selection in the existing presentation-owned typed animation data/resolver. Do not add `if skeleton/goblin/zombie` branches to `game/combat.py` or action/effect systems; do not create one custom attack executor, actor subclass, timing clock, or required event field for each art family. Preserve semantic root timing and report unsupported/fallback art honestly.
- **The authoring route does not call for an NPC framework.** Flavor variants can reuse a small number of real native creature/item/action compositions. Distinct appearance-only variants need appearance/presentation selections; genuine mechanical departures may receive stable project content identities through the existing declaration/factory path. The proposed names/candidates/NEW ability ideas in this study remain design choices, with firearm rules requiring explicit optional setting content rather than adaptation into a bow or environmental gun.

No blocker to the parent synthesis's ECS direction was found. The remaining design risk is multiplying rig-specific attack selectors too early; wait for specific inspected clip/contact mismatches and encode only a repeated presentation need through existing typed data. This review does not certify the other pack study evidence, overall NPC roster, shadow registration, numerical combat values, or animation contact timing.
