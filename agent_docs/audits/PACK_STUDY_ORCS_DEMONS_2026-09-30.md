# Orc, Goblin and Demon pack study

**SRD-first revision authority (30 September 2026):** this report preserves
archive/visual evidence and earlier proposals. Proposed mechanics below,
including sections labelled “selected design”, are superseded by the
[full-SRD rematch](PACK_ROSTER_SRD_FIRST_ORC_DEMON_2026-09-30.md) and
[reconciled synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md).
Use SRD 5.1 first, 5.2 secondary adapted to 5.1, with explicit changes for
actual visible equipment. Earlier custom action/spell/gear choices are not
competing current selections. Later named visual reinspections in the rematch
also take precedence over the corresponding earlier observation.

**Final roster authority:** use the [focused completion](PACK_ROSTER_ORC_DEMON_COMPLETION_2026-09-30.md)
and [full synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md). They correct
the initial small-contact gear readings, including mounted Goblin11/12, actual
bow users and armed demons, and select concrete native kit/action proposals.
The tables below retain the earlier study evidence and provisional pitches.

Date: 2026-09-30. This is a read-only source/content study. No production art was installed and no game code or native creature data was changed.

## Evidence scope

Reviewed both original ZIPs directly:

- `/mnt/c/Users/tommaso/Downloads/2D Orcs and Goblins - TopDown - V1.0.zip`
- `/mnt/c/Users/tommaso/Downloads/2D Demons - TopDown assetpack v1.1.zip`

Read the five existing rig definitions `game/data/rigs/goblin01.json`, `orc01.json` and `demonbeast01.json` through `demonbeast03.json`, and confirmed their referenced local body/shadow folders exist. Inspected full body sheets and contact images from extracted source frames. The only extracted media is study scratch in `.runtime/pack-study-20260930/orcs-demons/`; it is not a production installation.

The compact inventories are `orcs_goblins_variant_clip_inventory.json` and `demons_variant_clip_inventory.json` beside this report. They list every distinct family and exact clip filename in the `Combined` and separated-image roots, grouped by body/shadow/effect layer. Full per-file archive metadata was read in place; original pixels remain in the ZIPs. Contact sheets and selected sample sheets are private scratch, not report attachments.

## Directory inventory and installed coverage

The Orc/Goblin archive has 31 named families: Goblin 01–17, Orc 01–12, and Animal 1–2. Its `Combined/` folder contains merged sheets. The vendor-named `Seperate shadows and effects/` folder has corresponding body sheets and, by variant/clip where supplied, `Shadows/` and `Effects/` layers.

The Demon archive has 34 named families: Demon Beast 1–5, Demon Elite 1–6, Demon Spawn 1–13, and Imp 1–10. The first spawn folder is spelled `Demon spawn 1`; capitalization is inconsistent with 2–13. Its `Combined/` and `Spritesheets with seperated shadows and effects/` roots likewise provide merged and separated forms.

Only Goblin 01 and Orc 01 from the first archive are presently represented by the inspected fixed rigs. Only Demon Beast 1–3 from the second are represented. Thus the archive-only fixed choices include 16 other Goblins, 11 other Orcs, all 2 animals, Beast 4–5, all 6 Elites, all 13 Spawn, and all 10 Imps. This is source-directory coverage, not a claim that each uninstalled family is a desired game creature.

Both packs are PNG-only. Their archives contain no FPS, pivot, contact-frame, damage-frame, or event-marker metadata. These absences are significant: file names such as `Attack 3` are vendor labels, not native action IDs or proof of impact timing.

## Sheet geometry and shadows/effects

Representative separated body and shadow clips use 128-pixel cells, eight rows and fifteen columns (1920×1024). The rows visually correspond to the eight directions already used by the installed rigs. `Block.png` is shorter in time: Orc/Goblin source samples are commonly 768×1024 (6×8 cells), and Demon samples 896×1024 (7×8). Do not declare every clip to be fifteen frames based on the common sheet size. The sheet grid gives frame count, not source playback rate or action timing. Most named action sheets inspected use 15 columns; block sheets noted above use fewer.

The separated roots are the natural source for characters that must use pack shadows: body, shadow and visible effect are individual sheet roles rather than one flattened image. A sampled Demon Beast 1 Attack 1 body plus its separate effect sheet visibly produces the bright slash accent, so omitting effects can lose authored appearance. The `Combined/` version is also supplied; it is useful for source comparison but does not itself preserve separately controllable layers. Some separated effect exports are blank/near-blank placeholders; availability is per-clip and per-family, so use the inventory and pixel inspection before binding an effect layer. Goblin 01 Attack 1/2 effects are empty export placeholders, as already recorded in its rig provenance. A body-only clip can still contain baked weapon and costume pixels.

The current fixed rigs already demonstrate reuse of the right rendering data: explicit body/shadow categories, clip-to-source-clip mapping, frame count, chosen FPS, facing rows, ground/body anchors and death rest anchors. Reuse those concepts and the existing attack-profile mapping. Do not introduce a pack-wide executor or treat archive clip labels as rules.

## Installed rig facts and limits

| Rig | Stable content reference | Current semantic clips | Local choice |
| --- | --- | --- | --- |
| `smallscale.goblin01` | `content.neurodragon:creature:creature.goblin@1` | Idle, TakeDamage, Die, Run, Rolling, Attack1, Attack2 | Goblin 01 separated body/shadow; 15 frames per listed clip at chosen 12 FPS; two shared root slash layers for the two attacks |
| `smallscale.orc01` | `content.srd_5_1_cc:creature:creature.orc@1` | Idle, TakeDamage, Die, Run, Rolling, Attack1, Attack2 | Orc 01 separated body/shadow; 15 frames per listed clip at chosen 12 FPS |
| `smallscale.demonbeast01` | `content.srd_5_1_cc:creature:creature.dretch@1` | Idle, Run, TakeDamage, Die, Rolling, Attack1, Attack2, Attack5, Attack6 | Demon Beast 1 separated body/shadow; `Attack5` maps to vendor Attack 3; `Attack6` aliases Attack 1 |
| `smallscale.demonbeast02` | `content.neurodragon:creature:creature.corrosive_demon@1` | same nine keys as Beast 1 | Demon Beast 2; Attack5→Attack3 and Attack6→Attack1 |
| `smallscale.demonbeast03` | `content.neurodragon:creature:creature.dread_demon@1` | same nine keys as Beast 1 | Demon Beast 3; Attack5→Attack3 and Attack6→Attack1 |

Every FPS value above is the current selected execution clock, **not vendor timing**. For all five rigs the JSON chooses 12 FPS and 128×128 cells; Goblin/Orc ground offset is 41 px and Demon Beast is 45 px. The Demon Beast 1 JSON describes its art as a reviewed visual adaptation for Dretch, not a vendor Dretch identification. Demon Beast 2/3 similarly bind project-defined creature identities; the vendor labels only say “Demon Beast.”

Current content identities and appearance data are separate concerns. Keep NPC rules, possessions, natural attacks and custom abilities authored in the existing native content/equipment owners. Keep rig selection and animation mapping in presentation data bound from stable, disclosed identity facts. A visible sword, bow, horn gesture or slash is visual evidence only; it must not silently create a weapon, attack statistic or ability. Likewise, when a native actor has an item the fixed picture cannot depict, preserve the real loadout and expose the presentation mismatch; do not pretend the weapon changed or rewrite SRD facts to suit an image.

## Visual findings by candidate family

These are image observations, not official vendor role names:

- **Goblin 01 (installed):** green, lightly equipped goblin with a visibly baked hand weapon. The inspected Attack 1–4 sheets show axe-like melee swings; Attack 3/4 include an airborne/leaping axe strike. No inspected Goblin 01 clip established a bow shot. This confirms that Goblin 01 Attack 3 is not a safe semantic mapping for a native bow attack. The existing Goblin rig maps only Attack 1/2 and uses shared slash overlays; its provenance already notes that the native Goblin has scimitar/shield/shortbow possessions while those possessions are not independently swap-rendered on the fixed body. Exact correspondence between each baked pixel and each native possession remains limited by its small scale.
- **Goblin 02 (source-only):** robed/caster-like body without a visible hand weapon. Attack 5/6 have substantial separate pink-white effects sheets, visually supporting spell-like actions. The sheets do not identify a spell, damage, range, saving throw, or release frame. This is the strongest caster-style visual candidate inspected; a custom ability still needs an explicit native owner.
- **Goblin 03 (source-only):** bow is visible in its fixed body. Attack 1/2 show bow-drawing/release-like poses; the direction rows are complete. This is the clearest genuine archer candidate in this pack and is a better visual fit for a native archer loadout than Goblin 01. A visible projectile and exact release/contact frame were not established by the body sheet; the inspected Effects directory has only Attack 1 and Attack 4 sheets, so Attack 2 does not have a separate effect sheet there.
- **Goblin 04/06/14 (source-only):** visibly shield-bearing or shield-and-weapon presentations, making them better candidates for a shielded fixed look than Goblin 01. Exact weapon classification at contact-sheet scale is uncertain.
- **Goblin 05/10 (source-only):** elongated weapon reads as a spear/polearm, not a bow. Goblin 10 Attack 1 visibly uses the long weapon through the sequence.
- **Other Goblin/Orc variants:** contact-sheet review confirms substantially different body silhouettes, outfits, palette and baked gear; some are armored/brute presentations. Do not interpret each palette/body variant as a different rules creature. A few idle exports use names like `Idle 1 16bit.png`, and some families have 6-attack, attack-run, alternate-death, block, taunt, backflip, slide, crouch or strafe clips. The inventory is the complete authoritative filename listing; all those clip semantics and many individual weapon identities have not been frame-by-frame classified here.
- **Demon Beast 1–5:** five visibly distinct red demon-beast designs in source; the installed 1–3 are three of these. Attack sheets include body poses plus per-clip effects in the separated root. Existing attack aliases (Attack6→Attack1) are authored mappings, not evidence that the same gesture is mechanically suitable for every natural attack.
- **Demon Elite 1–6, Spawn 1–13, Imp 1–10:** all source-only in the inspected fixed rig set. Contact sheet shows distinct armored, horned, winged and smaller demon/imp silhouettes. Exact canon/species mapping is unresolved from vendor labels and pictures alone.

## Practical authoring implications

For a native Goblin with canonical melee and bow equipment, Goblin 03 is the inspected visual candidate with an actual baked bow; Goblin 01 is the currently installed fixed selection and does not supply that bow action. For a native caster-style project NPC, Goblin 02 has cast-like movement and authored FX, but neither the ability nor its mechanics can be inferred from those sheets. Keep both conclusions in presentation/content mapping only: preserve a stable creature identity and native equipment/ability facts, and map those facts to an available rig and its observed actions.

The small clip inventory is not a replacement for per-action frame review. Contact/release moments, looping versus one-shot behavior, duration in seconds, and how a selected clip aligns with existing attack/projectile schedules remain unresolved because the source contains no timing markers or declared clock. Any selected speed and timing must be an explicit reviewed execution choice, just as 12 FPS is in the current rigs.

## Proposed flavor roster: one proposal per art family

The names below are creative placeholders for content-authoring discussion. They are not existing entities or imported data. The contact-sheet pass visually covered every listed idle family; action-specific evidence is noted separately above. Equipment descriptions say what the idle art appears to carry; bracketed uncertainty means the small contact sheet cannot settle the item. The foundation and ability column names existing native compositions only as starting points. A future author still has to author stats, actual item IDs and abilities explicitly, and confirm the visible loadout agrees. `Reuse` means keep an existing rule/composition; it does not mean these proposal entries have been implemented.

### Goblins

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Goblin 01 | Ashhook | Green light fighter; axe-like baked weapon (observed), no clear bow | Existing Goblin; reuse Nimble Escape (Hide/Disengage) | Palette/armor variation only; same rules |
| Goblin 02 | Wispbinder | Purple robe, bare hands; separate pink-white cast-like FX on Attacks 5/6 (observed) | Existing Goblin Caster; reuse its authored spellcasting/actions | Do not add elite stats from glow alone |
| Goblin 03 | Reedshot | Bow held and drawn in Attack 1/2 (observed); projectile/release timing uncertain | Existing Goblin Archer; reuse shortbow loadout and current native actions | Optional archer sergeant with unchanged rules |
| Goblin 04 | Buckler Rat | Round buckler and small hand weapon (observed shield; weapon uncertain) | Existing Goblin; reuse Nimble Escape | Palette/armor variation only |
| Goblin 05 | Longpoint | Very long spear/polearm (observed) | Existing Goblin; author actual spear equipment; reuse Nimble Escape | Optional guard tint, no new ability |
| Goblin 06 | Ironhide | Heavy gray armor and broad shield (observed); hand weapon uncertain | Existing Goblin; author matching shield/weapon items; reuse Nimble Escape | Good armored elite look; same rules unless separately designed |
| Goblin 07 | Briarling | Green light fighter; no item reliably resolved | Existing Goblin; keep canonical loadout only if visual fit is acceptable; reuse Nimble Escape | No special treatment required |
| Goblin 08 | Redcap | Hooded red/brown outfit; no clear hand weapon | Existing Goblin; reuse Nimble Escape: Hide as flavor | Optional stealth palette, no added stealth mechanic |
| Goblin 09 | Quicktail | Small green fighter; possible hand-held bow/tool too small to resolve | Existing Goblin; reuse Nimble Escape; do not call an archer without attack-sheet confirmation | Palette variation only |
| Goblin 10 | Spearline | Long straight polearm/spear is visible through Attack 1 (observed) | Existing Goblin; author spear item; reuse Nimble Escape | Optional patrol leader palette |
| Goblin 11 | Saffron Guard | Ochre/yellow body, bulky pack or shield-like shape at back; exact gear uncertain | Existing Goblin; reuse Nimble Escape; loadout requires clearer frames | Could serve as elite visual, with no implied new trait |
| Goblin 12 | Ashplate | Gray/pale armored figure; weapon not resolved at contact-sheet scale | Existing Goblin; reuse Nimble Escape; inspect loadout before authoring gear | Palette/armor variation only |
| Goblin 13 | Thornrunner | Green light fighter; no clear weapon | Existing Goblin; reuse Nimble Escape | Palette variation only |
| Goblin 14 | Buckler Hex | Green/white figure with circular shield and small hand object (shield observed; weapon uncertain) | Existing Goblin; author actual shield/weapon; reuse Nimble Escape | Optional shield guard look; no new reaction inferred |
| Goblin 15 | Gloomplate | Broad dark armored silhouette; weapon uncertain | Existing Goblin; reuse Nimble Escape; preserve actual authored equipment separately | Strong elite silhouette; same mechanics by default |
| Goblin 16 | Mossbreaker | Large green/brute silhouette; no weapon resolved | Existing Goblin; reuse Nimble Escape; treat size as art until rules say otherwise | Optional brute palette, no size/stat inference |
| Goblin 17 | Gutterknife | Green hooded/light fighter; small hand weapon possible but uncertain | Existing Goblin; reuse Nimble Escape; loadout uncertain | Palette variation only |

### Orcs

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Orc 01 | Iron Cask | Broad dark/red plate armor, no weapon confidently resolved | Existing SRD Orc; reuse Aggressive and its authored axe/javelin facts only if appearance mapping fits | Armor recolor as elite presentation; no stat change by default |
| Orc 02 | Rededge | Green fighter with a broad light-colored blade (observed blade; exact type uncertain) | Existing SRD Orc; reuse Aggressive; ensure actual item choice matches blade art | Palette/armor variation only |
| Orc 03 | Yellowtusk | Green/yellow heavy fighter with a hand weapon (observed; type uncertain) | Existing SRD Orc; reuse Aggressive | Optional brighter elite palette |
| Orc 04 | Bristlejaw | Stocky bare/rough-skinned fighter; no weapon resolved | Existing SRD Orc; reuse Aggressive; avoid portraying unarmed rules unless authored | No elite treatment needed |
| Orc 05 | Longspike | Long straight weapon visible (observed polearm-like; exact type uncertain) | Existing SRD Orc; reuse Aggressive; author a matching actual item if selected | Optional sentry palette |
| Orc 06 | Frostmane | Pale/white-haired armored silhouette with shield-like object (uncertain) | Existing SRD Orc; reuse Aggressive; loadout needs a larger attack frame | Could be frost-themed elite coloration only |
| Orc 07 | Brassbrow | Gold/yellow head and green body; no weapon resolved | Existing SRD Orc; reuse Aggressive | Palette variant, no additional rule |
| Orc 08 | Blackplate | Dark heavy armor with shield-like side silhouette (observed armor; shield uncertain) | Existing SRD Orc; reuse Aggressive; fit equipment after inspection | Good elite visual, unchanged rules by default |
| Orc 09 | Redblade | Red/gray armor and long sword-like blade (observed blade; precise type uncertain) | Existing SRD Orc; reuse Aggressive; authored weapon should match the blade | Palette/armor variation only |
| Orc 10 | Mudrunner | Green forward-leaning fighter; hand weapon appears short but uncertain | Existing SRD Orc; reuse Aggressive | Optional raider palette |
| Orc 11 | Greenfang | Green armored fighter with long pale blade (observed; precise type uncertain) | Existing SRD Orc; reuse Aggressive | Palette/armor variation only |
| Orc 12 | Ironjaw | Broad dark/red plate and horned helmet; no held weapon resolved | Existing SRD Orc; reuse Aggressive; keep canonical equipment factual even if fixed pose obscures it | Strong elite look, no implied command power |

### Animals

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Animal 1 | Slatepack Wolf | Gray wolf; no gear; natural bite (family action names include Attack 1–3, exact bite contact unclear) | Existing SRD Wolf; reuse its native bite/pack behavior | Wolf palette variant only |
| Animal 2 | Goldpack Wolf | Same wolf silhouette in gold palette; no gear | Existing SRD Wolf; same mechanics as Animal 1; no new ability | Color-only variant, not a separate species or elite stat block |

### Demon Beasts

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Demon Beast 1 | Cindermaw | Lean red spined demon; no handheld gear, claws apparent | Existing Dretch-derived demon; reuse bite/claws. Existing Dretch rig is already an explicitly reviewed visual adaptation, not a vendor species ID | Base visual; do not label elite |
| Demon Beast 2 | Hookshade | Lean red/black demon with long hooked limbs; no handheld gear | Existing Corrosive Demon / Dretch composition is a starting point; reuse current corrosive-blood rule only if that identity is selected, otherwise plain Dretch actions | Potential elite tint only, no new stats |
| Demon Beast 3 | Ironmask | Stocky armored red demon; gauntlet/weapon-like hands (uncertain) | Existing Dread Demon / Dretch composition is a starting point; reuse existing dread-blood rule only when deliberately choosing that native identity | Armored elite appearance; no inferred armor class |
| Demon Beast 4 | Emberwing | Red winged/spined silhouette; natural claws likely, flight action not established by idle | Dretch-derived project demon; reuse bite/claws; flight remains an explicit design decision | Possible winged elite color, no automatic flight rule |
| Demon Beast 5 | Redthorn | Red horned/spined quadruped-like pose; no gear; natural claws likely | Dretch-derived project demon; reuse natural attacks, validate body/action poses first | Base variant; no new rule |

### Demon Elites

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Demon Elite 1 | Giltbrand | Red/black armored humanoid with bright arm/weapon accents (gear uncertain) | Project demon over Dretch as a low-tier start; reuse bite/claws or existing corrosive/dread variant only by deliberate content choice | Family is already named Elite; visual label grants no mechanics |
| Demon Elite 2 | Obsidian Bulwark | Broad dark heavy armor, large shield-like shape (observed armor; shield uncertain) | Project demon over an explicitly authored foundation; reuse natural attacks; no safe SRD equivalent inferred from art | Elite appearance; any NEW defensive rule needs separate design approval |
| Demon Elite 3 | Whitehorn | Tall horned, pale-maned demon with long limbs; no held weapon clear | Dretch-derived project demon only if intended power is small; reuse claws/bite | Elite label only; do not infer size or stats |
| Demon Elite 4 | Chainfang | Red/black armor and long weapon-like silhouette (observed; type uncertain) | Dretch-derived custom identity; reuse natural attacks unless actual weapon is selected in native loadout | Optional elite palette; no weapon inferred from clip number |
| Demon Elite 5 | Pallid Hexer | Small pale skull-faced robed/armored figure, raised hand object and shield-like shape (uncertain) | Project demon caster is not currently established by this art alone; reuse an existing authored spell action only if one is assigned, otherwise no new ability | Elite appearance only; no spell inferred from gesture |
| Demon Elite 6 | Nightwall | Heavy dark plate, large shield and raised axe/hammer-like object (visible, exact hand weapon uncertain) | Project demon over an authored foundation; reuse Dretch natural attacks only if that matches chosen identity | Optional new named **Guarding Stance** is a NEW proposed rule, not implemented; do not copy it to recolors |

### Demon Spawn

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Demon spawn 1 | Ashling | Small red/black humanoid, hand-held bright object (weapon uncertain) | Project small demon over Dretch as starting point; reuse bite/claws; no object-specific mechanic inferred | Palette variation only |
| Demon Spawn 2 | Cinder Knife | Red/black slim humanoid with small blade-like object (uncertain) | Dretch-derived project demon; reuse natural attacks unless actual item is authored | Optional elite recolor only |
| Demon Spawn 3 | Thornwing | Red winged demon with long appendages; no visible equipment | Dretch-derived project demon; reuse claws/bite; flight is a NEW design question, not established by idle | Palette variation only |
| Demon Spawn 4 | Ashguard | Armored red/black humanoid, sword and shield are visible in Combined sheet | Project small demon; native equipment should match fixed sword/shield; reuse existing Dretch foundation only if its stats fit | Can recolor as an elite guard with no new mechanics |
| Demon Spawn 5 | Needle Imp | Thin red humanoid with narrow weapon-like shape (uncertain) | Dretch-derived project demon; reuse claws/bite | Palette variation only |
| Demon Spawn 6 | Coalstep | Small red/black humanoid; gear not resolved | Dretch-derived project demon; reuse existing natural attacks | Palette variation only |
| Demon Spawn 7 | Platelet | Dark/gray armored small demon, shield-like shapes possible (uncertain) | Dretch-derived project demon; reuse bite/claws | Optional guard elite palette |
| Demon Spawn 8 | Veilmaw | Broad, dark hooded silhouette with robe-like body; no gear resolved | Project demon foundation needs explicit authoring; reuse existing Dretch actions if stats fit | Palette variation only |
| Demon Spawn 9 | Knifeshade | Crouched dark red humanoid, small weapon-like object (uncertain) | Dretch-derived project demon; reuse natural attacks, do not infer stealth rules | Palette variation only |
| Demon Spawn 10 | Ashen Scribe | Gray-robed mask-like figure; hands/items unclear | Dretch-derived project demon; gestures need action-sheet inspection before caster identity | Optional elite recolor, no spell added |
| Demon Spawn 11 | Brimstone Knuckle | Gray/black bulky demon with a bright fist/hand detail (observed accent; weapon uncertain) | Dretch-derived project demon; reuse claws/bite | Could be an elite tint; no special damage type from color |
| Demon Spawn 12 | Starling Fiend | Red spined, star-like silhouette; no held gear resolved | Dretch-derived project demon; reuse natural attacks | Palette variation only |
| Demon Spawn 13 | Redveil | Red/black long-robed figure; no held item resolved | Project demon foundation; reuse existing Dretch actions only if fit; no spell inferred from robe | Possible elite cloak palette, unchanged rules |

### Imps

| Source art | Proposed NPC | Visible look / proposed loadout | Native foundation and ability flavor | Optional elite use |
| --- | --- | --- | --- | --- |
| Imp 1 | Ember Pip | Tiny red horned, winged body; no gear | Project tiny demon over Dretch only as starting point; reuse natural attacks; no flight mechanics inferred | Palette variation only |
| Imp 2 | Coal Pip | Tiny red/black body, equipment unclear | Dretch-derived project demon; reuse bite/claws | Palette variation only |
| Imp 3 | Crown Spark | Tiny red figure with tall head/crown shape; no weapon resolved | Dretch-derived project demon; reuse natural attacks | Palette variation only |
| Imp 4 | Furnace Mote | Tiny red body, no clear equipment | Dretch-derived project demon; reuse natural attacks | Palette variation only |
| Imp 5 | Cinder Mite | Tiny red figure; no gear resolved | Dretch-derived project demon; reuse natural attacks | Palette variation only |
| Imp 6 | Sootknife | Tiny red/black figure with narrow held shape possible (uncertain) | Dretch-derived project demon; reuse natural attacks until loadout is resolved | Palette variation only |
| Imp 7 | Ashwing Pip | Tiny red/black, wing-like silhouette | Dretch-derived project demon; reuse bite/claws; flight requires explicit authoring | Optional wing color only |
| Imp 8 | Buckler Mote | Tiny dark/red figure with circular shield-like object (observed, weapon uncertain) | Dretch-derived project demon; author equipment only if supported natively and visually | Potential guard recolor, no extra defense by implication |
| Imp 9 | Needle Pip | Tiny red figure with long thin weapon-like shape (uncertain) | Dretch-derived project demon; reuse natural attacks unless native weapon selected | Palette variation only |
| Imp 10 | Little Spark | Tiny bright red demon with spined silhouette; no gear resolved | Dretch-derived project demon; reuse natural attacks | Palette variation only |

The Orc/Goblin and Demon numbered variants are palette, gear, silhouette and clip families, not evidence of separate canonical species. This roster intentionally proposes a one-to-one *presentation/content naming* path while sharing native foundations and abilities wherever art does not justify a new mechanic. Distinct item loadouts are only suggested where the art clearly supports them. A fixed outfit cannot truthfully depict an arbitrary later equipment change; that limitation belongs in its presentation capability, while native possessions remain authoritative. Source archive labels do not establish canon species names, challenge rating, attributes, damage dice, flight, spell lists or item mechanics.

Timing remains unresolved for all proposals: full idle coverage does not identify attack startup, contact, recovery, loop/one-shot intent, projectile release, or seconds-per-clip. Before binding any candidate, inspect the chosen action sheets, separate shadow/effect layers and actual dimensions. The current 12 FPS is a chosen local sample rate, not a source fact.
