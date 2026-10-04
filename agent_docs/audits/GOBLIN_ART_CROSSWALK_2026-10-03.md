# Goblin original-art and accepted-item crosswalk

Date: 2026-10-03. Evidence appendix for the final-phase plan; no runtime registry,
creature definitions, gameplay rules or artwork are introduced here. The current
human request includes all 17 original Goblin variants. Mounted 11/12 remain a
human decision. Goblin 17's old ranged item match is explicitly corrected below.

## Sources and status

- Original archive: `/mnt/c/Users/tommaso/Downloads/2D Orcs and Goblins - TopDown - V1.0.zip`
  (348,119,526 bytes). Read only; no media imported in this review.
- [Full original filename inventory](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/orcs_goblins_variant_clip_inventory.json>). This names all available banks,
  including optional banks not selected by the seven-clip handoff sample.
- [Item-first handoff v2](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/handoff-v2.json>): all 17 source identities, selected body clips,
  paired-layer metadata, sampled motion semantics and evidence pages. Its old
  `recommendations_only_not_human_approved`/rule-proposal text is historical;
  it must not override the later item receipt and ability dispositions.
- [Complete item/material receipt](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/items-roster-20261002/complete-item-materials-handoff.json>): the exact `character_records`
  rows copied below. **84 possession placements, 36 distinct (native reference,
  visual variant) selections.** These are frozen old receipt values, not a claim
  that every visual classification remains correct. Goblin 17 Shortbow is wrong.
- [Approved ability dispositions](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/ROSTER_ABILITY_DISPOSITIONS_2026-10-02.md>):
  G01–G07, using handoff row ordinals rather than Goblin numbers. Earlier custom
  signatures, speculative +1 weapons and earlier flavor labels do not supersede it.
- [Source-first September 30 review](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/PACK_ROSTER_SRD_FIRST_ORC_DEMON_2026-09-30.md>)
  preserves the observed ordinary cuts, caster gestures and Goblin 15/17 forward-hand
  flame. Its old rules proposals are not newly approved by citing its pixel evidence.

Current installation: [Goblin 01 binding](</mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/rigs/goblin01.json>)
uses `smallscale.goblin01` and canonical `creature.goblin`; it registers Idle,
Run, TakeDamage, Die, Rolling and Attack1/2. No Goblin 02–17 rig binding is installed
at this checkpoint. The final plan owns their admission and the canonical Goblin
scale correction; this appendix does not alter either.

**Native recipes and visual variants are distinct.** The receipt's
`native_reference` identifies the existing item definition; `variant` selects its
appearance, and `null` means the base/default selection. `roster.*`, color-like
variant strings and receipt `recommendation.*` IDs are not new mechanical item
identities. The 113 admitted appearance records across the full roster are not
113 new native item recipes. Existing owners are
[authored native definitions](</mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/authored_item_definitions.py>),
[ordinary roster item definitions](</mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/content/items/roster_item_definitions.py>),
[visual variant parameters](</mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/items/visual_variants.py>),
[appearance ledger](</mnt/c/users/tommaso/documents/dev/dnd_engine/content_data/ledgers/neuroclient_authored_item_visuals.json>)
and [held/ground bindings](</mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/item_appearances.json>).
Character construction must resolve the actual native recipe and apply its selected
appearance through those existing owners; an appearance-ledger row alone does not
register a character or prove native recipe admission. Do not duplicate mechanics
or create per-NPC item families. Selected immutable variants follow section3 of
the Goblin plan, deduplicated by base and variant in the existing item definitions;
the current possession grant builds by item_id. The visual-parameter type alone
is not a wired grant path. Never substitute a different item for a missing recipe.

## Exact member convention and frame evidence

Archive member prefix **P** is exactly
`2D Orcs and Goblins - TopDown - V1.0/Seperate shadows and effects/` (vendor spelling).
For each literal variant name and literal filename below:

- Body member = `P` + `Goblin NN/` + filename.
- Matching shadow member = `P` + `Goblin NN/Shadows/` + the same filename.
- Listed effect member = `P` + `Goblin NN/Effects/` + filename.
- Combined witness = `2D Orcs and Goblins - TopDown - V1.0/Combined/Goblin NN/` + filename.

These formulas specify exact members, not fuzzy aliases. All **341 body/shadow
pairs** across the 17 variants were checked against the archive for matching
geometry: 128 × 128 cells and eight rows, E, SE, S, SW, W, NW, N, NE. Ordinary
banks are 1920 × 1024: 15 frames, indices 0–14. Exceptions:

| Original bank | Variants | Geometry / count |
| --- | --- | --- |
| `Block.png` | 01–04, 06–09, 13–17 | 768 × 1024; 6 frames, 0–5 |
| `Attack 4.png` | 02, 08 | 1024 × 1024; 8 frames, 0–7, including paired effects |
| `Take Damage.png` | 11, 12 | 768 × 1024; 6 frames, 0–5 |

The PNG-only vendor source declares **no FPS or support pivots**. Existing Goblin
01's 12 FPS and origin 41 are explicit project adaptations, not vendor facts or
an automatic value for every new clip. Select each rig's support/depth registration
from its actual body/shadow. In particular, the six-frame mounted hit cannot use
root frame 7/14 feedback markers.

For unmounted rows, common candidate mapping is Idle → the exact Idle filename,
movement → `Run.png` (ordinary grounded movement), hit → `TakeDamage 1.png`, death
→ `Die 1.png`. Source `Die 1` final frame 14 is the inspected nonblank resting
candidate for the existing Prone entry/held/rest/reversed-exit system. It needs
per-rig ground registration; source `Die 2` remains a separately named alternative,
not an interchangeable fallback. Mounted rows instead have `Idle 1`, `Take Damage`
and `Die`, with both rider and steed baked through the entire motion. Their Prone
and mount behavior cannot be invented from those pictures.

## Shared action and effect evidence

All windows below are **zero-based observed source windows**, not certified native
contact/release markers. The handoff's exact `contact_frame` and
`projectile_release_frame` fields are still null. The existing canonical Goblin
binding has its own authored markers; that does not certify every new rig.

| Family | Source semantics / sampled windows | Effect ownership and status |
| --- | --- | --- |
| Melee: 01, 04, 06, 07, 13–17 | `Attack 1`: cross-body sweep, 6–9; `Attack 2`: overhead/downward cut, 5–8; `Attack 3`: jumping cut, 6–8. Weapon shape follows each fixed body. `Attack 4` is a separate leaping/impact motion. | Effects/Attack 1–3 and Run Attack contain only alpha 0–1, so no visible extra slash is required. Attack 4 has a real separate impact-effect bank (row E visible >32 at 9–13). Do not derive an extra area hit, damage packet or transferable enchantment. |
| Pole: 05, 10 | `Attack 1`: thrust, 4–7; `Attack 2`: downward thrust, 5–8; `Attack 3`: leaping thrust, 6–8. | No Effects directory/banks. Spear/Trident remain actual inventory items; long art does not increase reach. |
| Caster: 02, 08 | `Attack 1`: channel, initial flash 1 and stream 3–12; `Attack 2/3`: orb-like release around 6; `Attack 4`: eight-frame held casting motion; `Attack 5/6`: ward/aura-like motions; `Attack Run`: moving cast bank. | All named attacks have separate visible effects. These are actor/cast/condition cues, not proof that the staff grants Web or elemental damage. Native prepared spells own their shared target effects. No physical Quarterstaff strike is established by these casting clips. |
| Archer: 03, 09 | `Attack 1`: real bow draw through about 10 and observed release around 11; `Attack 2`: bow used as a melee prop, 5–8; `Attack 3`: aim/hold without a proven shot. | Separate effects exist only for Attack 1/4 (E visible >32 at 10–13). One native shot remains one shot even if the art has several flashes. Attack 2/3 are not interchangeable shooting recipes. |
| Mounted: 11, 12 | Three rider weapon attacks plus two moving attacks; entire rider/steed remains one source composite. | No separate effect banks. Ordinary gear remains distinct from the depicted mount. Pending human mount decision; no independent mount clock, target or attack added here. |
| Extra `Attack 5`: 15, 17 | Forward-hand pointing/discharge; existing source review describes orange flame. Goblin 17 keeps its scimitar in the opposite hand. | Visible fire/smoke effect at E frames 5–10; not an arrow. No native Fire power, firearm item, second attack or ranged permission follows from the sheet alone. Goblin 17 item correction is awaiting the human. |

Spell hues are not rules. Decorative trails remain cosmetic; any actual item-owned
power must be supplied by the item definition and survive ordinary transfer through
existing item ownership. Nothing in these 84 Goblin possession rows declares a new
magical weapon. Fixed-sheet gear remains baked into the actor picture; the existing
human deferral of fixed-holder gear-removal artwork still applies. The accepted
modular held/ground appearance is useful for real inventory/loot, but it cannot
magically erase that item from a baked Goblin body.

## Per-variant evidence and exact frozen possession rows

Every section lists all available body filenames, with matching shadow filenames
by the convention above. It is an inventory, not a demand to import every bank.
`pN` below expands to the section's exact character key plus `.pN`; `null` is the
actual JSON null value. Category, native reference, appearance variant and slot
are copied without reinterpretation from `character_records`. Two equal weapon
rows are two possessions, not accidental duplicates. Source-page positions are
zero-based. Old flavor labels remain only to locate the historical record.

### Goblin 01 — Ashhook, axe skirmisher

Character `929425db7355`; roster row **1**; receipt status `mapped`. Existing canonical Goblin art. Source baseline Goblin; approved G01: ordinary attack and Nimble Escape. Depicted Handaxe.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 0](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-929425db7355-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-929425db7355-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-929425db7355-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.21ae119f8607` | `body_armor` |
| `p1` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p2` | Handaxe | `content.srd_5_1_cc:item:weapon.handaxe@1` | `null` | `weapon_melee_main` |

### Goblin 02 — Wispbinder, caster-flavored trickster

Character `d1c54a5b3e62`; roster row **2**; receipt status `mapped`. Caster family. Earlier source benchmark Mage; approved G02 retains existing Web through ordinary casting. Empty hands in the accepted possession receipt; no weapon inferred from spell color.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Attack 6.png`, `Attack Run.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle 1.png`, `Roll 1.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Attack 6.png`, `Attack Run.png`.

Existing selected source semantics: `Attack 1.png` → `cast.channel`; `Attack 2.png` → `cast.orb`; `Attack 3.png` → `cast.orb`.

Visual witnesses: [source page, position 1](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-d1c54a5b3e62-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-d1c54a5b3e62-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-d1c54a5b3e62-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Robes | `content.neurodragon:item:apparel.robes@1` | `roster.ac36c74adec6` | `body_armor` |
| `p1` | Leather Shoes | `content.neurodragon:item:apparel.leather_shoes@1` | `b0000007` | `boots` |

### Goblin 03 — Reedshot, archer

Character `e3297820f656`; roster row **3**; receipt status `mapped`. Archer family. Source baseline Goblin; G01 ordinary Shortbow attack and Nimble Escape. Its bow-shot source is materially different from the melee-looking Attack 2/3.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle 1 16bit.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 4.png`.

Existing selected source semantics: `Attack 1.png` → `bow.shot`; `Attack 2.png` → `bow.melee_swing`; `Attack 3.png` → `bow.aim_hold`.

Visual witnesses: [source page, position 2](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-e3297820f656-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-e3297820f656-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-e3297820f656-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.21ae119f8607` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.44e704af2cf6` | `helmet` |
| `p2` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p3` | Quiver | `content.neurodragon:item:gear.quiver@1` | `roster.6c39094102d0` | `backpack` |
| `p4` | Shortbow | `content.srd_5_1_cc:item:weapon.shortbow@1` | `a0000007` | `weapon_ranged_main` |

### Goblin 04 — Buckler Rat, shield duelist

Character `ce0d29fb29b9`; roster row **5**; receipt status `mapped`. Shield melee family. Source baseline Goblin; G01 ordinary Scimitar attack and Nimble Escape. A shield does not by itself grant Protection.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 4](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ce0d29fb29b9-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ce0d29fb29b9-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ce0d29fb29b9-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.8ab959786f2a` | `body_armor` |
| `p1` | Iron Helmet | `content.neurodragon:item:apparel.iron_helmet@1` | `roster.6b64ee00bd15` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Scimitar | `content.srd_5_1_cc:item:weapon.scimitar@1` | `null` | `weapon_melee_main` |
| `p4` | Wooden Shield | `content.neurodragon:item:shield.wooden@1` | `90000006` | `weapon_melee_off` |

### Goblin 05 — Longpoint, spear skirmisher

Character `9531f0b464bf`; roster row **6**; receipt status `mapped`. Pole family. Source baseline Goblin; G01 ordinary Spear attack and Nimble Escape. No increased reach inferred from the long shaft.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: **none**.

Existing selected source semantics: `Attack 1.png` → `weapon.pole_thrust`; `Attack 2.png` → `weapon.pole_downthrust`; `Attack 3.png` → `weapon.pole_jumping_thrust`.

Visual witnesses: [source page, position 5](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-9531f0b464bf-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-9531f0b464bf-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-9531f0b464bf-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.16dea1f65105` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.828192008429` | `helmet` |
| `p2` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p3` | Spear | `content.srd_5_1_cc:item:weapon.spear@1` | `null` | `weapon_melee_main` |

### Goblin 06 — Ironhide, shield guard

Character `bc130498295a`; roster row **8**; receipt status `mapped`. Shield melee family. Approved G05 selects existing Protection, superseding the earlier custom Shield Escort proposal. Actual main item is Shortsword.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 7](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-bc130498295a-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-bc130498295a-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-bc130498295a-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.f8d0f71d39aa` | `body_armor` |
| `p1` | Iron Helmet | `content.neurodragon:item:apparel.iron_helmet@1` | `roster.6b64ee00bd15` | `helmet` |
| `p2` | Gauntlets | `content.neurodragon:item:apparel.gauntlets@1` | `g0000009` | `gauntlets` |
| `p3` | Armored Boots | `content.neurodragon:item:apparel.armored_boots@1` | `b000000d` | `boots` |
| `p4` | Shortsword | `content.srd_5_1_cc:item:weapon.shortsword@1` | `null` | `weapon_melee_main` |
| `p5` | Shield | `content.srd_5_1_cc:item:shield.shield@1` | `a000000a` | `weapon_melee_off` |

### Goblin 07 — Briarling, dual-knife skirmisher

Character `50fe4d5f84b9`; roster row **9**; receipt status `mapped`. Two-weapon melee family. Approved G06 uses ordinary authored two-weapon Multiattack, removing the proposed NoReactions rider. Exact items are Shortsword and offhand Dagger.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 8](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-50fe4d5f84b9-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-50fe4d5f84b9-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-50fe4d5f84b9-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.f8d0f71d39aa` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.7d8178761a23` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p4` | Shortsword | `content.srd_5_1_cc:item:weapon.shortsword@1` | `null` | `weapon_melee_main` |
| `p5` | Off-hand Dagger | `content.srd_5_1_cc:item:weapon.dagger@1` | `null` | `weapon_melee_off` |

### Goblin 08 — Redcap, empty-hand trickster

Character `ae641e971b21`; roster row **11**; receipt status `mapped`. Caster family. Earlier source benchmark Mage; G02 existing Web. Historical identity says empty-hand, but the current receipt and source show Quarterstaff. Casting clips do not establish a physical staff strike.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Attack 6.png`, `Attack Run.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Attack 6.png`, `Attack Run.png`.

Existing selected source semantics: `Attack 1.png` → `cast.channel`; `Attack 2.png` → `cast.orb`; `Attack 3.png` → `cast.orb`.

Visual witnesses: [source page, position 0](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ae641e971b21-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ae641e971b21-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-ae641e971b21-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Robes | `content.neurodragon:item:apparel.robes@1` | `roster.51a81ec5104c` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.828192008429` | `helmet` |
| `p2` | Leather Shoes | `content.neurodragon:item:apparel.leather_shoes@1` | `b0000007` | `boots` |
| `p3` | Quarterstaff | `content.srd_5_1_cc:item:weapon.quarterstaff@1` | `a0000005` | `weapon_melee_main` |

### Goblin 09 — Quicktail, bow raider

Character `948039c3fdda`; roster row **4**; receipt status `mapped`. Archer family. G03 defers Disrupting Shot; use ordinary attacks from the actual Shortbow. No no-reactions rider, magical +1 bonus or extra shot inferred from the source.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle 1 16bit.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 4.png`.

Existing selected source semantics: `Attack 1.png` → `bow.shot`; `Attack 2.png` → `bow.melee_swing`; `Attack 3.png` → `bow.aim_hold`.

Visual witnesses: [source page, position 3](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-948039c3fdda-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-948039c3fdda-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-948039c3fdda-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.f8d0f71d39aa` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.7d8178761a23` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000008` | `boots` |
| `p4` | Quiver | `content.neurodragon:item:gear.quiver@1` | `roster.6c39094102d0` | `backpack` |
| `p5` | Shortbow | `content.srd_5_1_cc:item:weapon.shortbow@1` | `20000002` | `weapon_ranged_main` |

### Goblin 10 — Spearline, patrol lancer

Character `6b85ffd23aab`; roster row **7**; receipt status `mapped`. Pole family. G04 defers custom entry-reach Brace; preserve ordinary opportunity attacks. Current item is Trident, superseding the old spear label.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left.png`, `Strafe Right.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: **none**.

Existing selected source semantics: `Attack 1.png` → `weapon.pole_thrust`; `Attack 2.png` → `weapon.pole_downthrust`; `Attack 3.png` → `weapon.pole_jumping_thrust`.

Visual witnesses: [source page, position 6](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-6b85ffd23aab-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-6b85ffd23aab-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-6b85ffd23aab-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.5b5b6ba7ea35` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.7d8178761a23` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000008` | `boots` |
| `p4` | Trident | `content.srd_5_1_cc:item:weapon.trident@1` | `null` | `weapon_melee_main` |

### Goblin 11 — Packtrail, mounted courier/scout

Character `a085e824f8ac`; roster row **14**; receipt status `mapped`. Mounted composite: rider and tan quadruped are baked together. G05 had selected Protection for the rider proposal; this does not resolve the human-pending mounted representation. No separate mount mechanics authored here.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack Run 1.png`, `Attack Run 2.png`, `Backwards Run.png`, `Crouch walk.png`, `Die.png`, `Eating.png`, `Idle 1.png`, `Run.png`, `Take Damage.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: **none**.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 3](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a085e824f8ac-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a085e824f8ac-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a085e824f8ac-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.16dea1f65105` | `body_armor` |
| `p1` | Saddle and Tack | `content.neurodragon:item:gear.saddle@1` | `null` | `null` |
| `p2` | Handaxe | `content.srd_5_1_cc:item:weapon.handaxe@1` | `null` | `weapon_melee_main` |
| `p3` | Wooden Shield | `content.neurodragon:item:shield.wooden@1` | `90000006` | `weapon_melee_off` |

### Goblin 12 — Ashhide, mounted shield scout

Character `cce79746413e`; roster row **15**; receipt status `mapped`. Mounted composite: rider and gray quadruped are baked together. The same G05/mounted limitation applies. Saddle inventory is not evidence of an implemented rider relation.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack Run 1.png`, `Attack Run 2.png`, `Backwards Run.png`, `Crouch walk.png`, `Die.png`, `Eating.png`, `Idle 1.png`, `Run.png`, `Take Damage.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: **none**.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 4](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-cce79746413e-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-cce79746413e-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-cce79746413e-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.f8d0f71d39aa` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.7d8178761a23` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Saddle and Tack | `content.neurodragon:item:gear.saddle@1` | `null` | `null` |
| `p4` | Handaxe | `content.srd_5_1_cc:item:weapon.handaxe@1` | `null` | `weapon_melee_main` |
| `p5` | Shield | `content.srd_5_1_cc:item:shield.shield@1` | `a000000a` | `weapon_melee_off` |

### Goblin 13 — Thornrunner, knife skirmisher

Character `a09db534ac3a`; roster row **10**; receipt status `mapped`. Club melee family. G07 selects normal attack plus separately chosen native Shove, not a free on-hit push. Historical knife label is stale; current item is Club.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 9](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-01.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a09db534ac3a-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a09db534ac3a-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-a09db534ac3a-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.3b03cd4905fa` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.44e704af2cf6` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Club | `content.srd_5_1_cc:item:weapon.club@1` | `null` | `weapon_melee_main` |

### Goblin 14 — Buckler Hex, shield fighter

Character `afbb73d270e3`; roster row **16**; receipt status `mapped`. Shield melee family. G05 existing Protection. Current item is Morningstar, superseding earlier generic mace wording; use its native item behavior, not a new signature.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 5](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-afbb73d270e3-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-afbb73d270e3-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-afbb73d270e3-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.8ab959786f2a` | `body_armor` |
| `p1` | Iron Helmet | `content.neurodragon:item:apparel.iron_helmet@1` | `roster.6b64ee00bd15` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Armored Boots | `content.neurodragon:item:apparel.armored_boots@1` | `b000000d` | `boots` |
| `p4` | Morningstar | `content.srd_5_1_cc:item:weapon.morningstar@1` | `null` | `weapon_melee_main` |
| `p5` | Wooden Shield | `content.neurodragon:item:shield.wooden@1` | `90000006` | `weapon_melee_off` |

### Goblin 15 — Gloomplate, armored bruiser

Character `32986b4294bf`; roster row **17**; receipt status `mapped`. Two-Handaxe melee family. The existing source proposal uses a Bugbear benchmark; approved G06 selects ordinary two-weapon Multiattack. Do not silently add Goblin Nimble Escape or infer size/AC from the armor silhouette. Its source Attack 5 flame is not a native Fire grant.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 6](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-32986b4294bf-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-32986b4294bf-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-32986b4294bf-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Armor Scraps | `content.neurodragon:item:armor.armor_scraps@1` | `roster.d6b6c79a6d59` | `body_armor` |
| `p1` | Iron Helmet | `content.neurodragon:item:apparel.iron_helmet@1` | `h000000a` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p4` | Handaxe | `content.srd_5_1_cc:item:weapon.handaxe@1` | `null` | `weapon_melee_main` |
| `p5` | Off-hand Handaxe | `content.srd_5_1_cc:item:weapon.handaxe@1` | `null` | `weapon_melee_off` |

### Goblin 16 — Mossbreaker, unarmed brawler

Character `58d86e2b3916`; roster row **12**; receipt status `mapped`. Shield melee family. Source baseline Goblin; G01 ordinary Shortsword attack and Nimble Escape. Historical unarmed label is stale; both sword and shield are listed in the current receipt.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 1](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-58d86e2b3916-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-58d86e2b3916-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-58d86e2b3916-2.png>).

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.21ae119f8607` | `body_armor` |
| `p1` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p2` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p3` | Shortsword | `content.srd_5_1_cc:item:weapon.shortsword@1` | `null` | `weapon_melee_main` |
| `p4` | Wooden Shield | `content.neurodragon:item:shield.wooden@1` | `90000006` | `weapon_melee_off` |

### Goblin 17 — Gutterknife, light raider

Character `68421584bd5e`; roster row **13**; receipt status `mapped`. Mixed held props. Ordinary scimitar cuts are clear. The frozen Shortbow selection is MISCLASSIFIED: Attack 5 points and discharges a muzzle-like orange flash while the scimitar remains in the other hand; neither Attack 4 nor Attack 5 draws/releases a bow. Root has asked the human whether to correct the prop to an ordinary Pistol or defer ranged use. No item/rule/art correction is authorized by this appendix; G03 custom Disrupting Shot remains deferred.

Body + matching shadow filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `BackFlip 1.png`, `Block.png`, `Crouch walk.png`, `Crouch.png`, `Die 1.png`, `Die 2.png`, `Idle.png`, `Roll 1.png`, `Run Attack.png`, `Run Backwards.png`, `Run.png`, `Slide 1.png`, `Strafe Left 1.png`, `Strafe Right 1.png`, `TakeDamage 1.png`, `Taunt.png`, `Walk.png`.

Separate effect filenames: `Attack 1.png`, `Attack 2.png`, `Attack 3.png`, `Attack 4.png`, `Attack 5.png`, `Run Attack.png`.

Existing selected source semantics: `Attack 1.png` → `weapon.melee_sweep`; `Attack 2.png` → `weapon.melee_chop`; `Attack 3.png` → `weapon.jumping_cut`.

Visual witnesses: [source page, position 2](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/source-02.png>); [Attack 1 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-68421584bd5e-0.png>), [Attack 2 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-68421584bd5e-1.png>), [Attack 3 strip](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/integration-preparation/artist-review-20261002/assets/evidence/motion-68421584bd5e-2.png>).

Additional direct source inspection: [Attack 4 complete sheet](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/orcs-demons/orcs_goblins/Goblin_17/Attack 4.png>); [Attack 5 complete sheet](</mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/orcs-demons/orcs_goblins/Goblin_17/Attack 5.png>). The former is a leaping scimitar cut (airborne 3–7, follow-through 8–11); the latter points the other held prop at 3–7 and raises/retracts it at 8–12. Paired `Effects/Attack 5.png` supplies the orange flash/smoke. Neither shows a bow draw or arrow release. Temporary enlarged original-pixel witnesses: [body frames](</tmp/goblin17-attacks4-5-source-inspection.png>); [paired effects](</tmp/goblin17-attacks4-5-effects-inspection.png>). No source pixels were altered. **Shortbow below is a frozen incorrect receipt match, not an approved final art mapping.**

| Possession | Category | Exact native reference | Appearance variant | Native slot |
| --- | --- | --- | --- | --- |
| `p0` | Common Clothes | `content.neurodragon:item:apparel.common_clothes@1` | `roster.21ae119f8607` | `body_armor` |
| `p1` | Cloth Hood | `content.neurodragon:item:apparel.cloth_hood@1` | `roster.44e704af2cf6` | `helmet` |
| `p2` | Bracers | `content.neurodragon:item:apparel.bracers@1` | `g0000003` | `gauntlets` |
| `p3` | Leather Boots | `content.neurodragon:item:apparel.leather_boots@1` | `b0000009` | `boots` |
| `p4` | Quiver | `content.neurodragon:item:gear.quiver@1` | `roster.6c39094102d0` | `backpack` |
| `p5` | Scimitar | `content.srd_5_1_cc:item:weapon.scimitar@1` | `null` | `weapon_melee_main` |
| `p6` | Shortbow **MISCLASSIFIED** | `content.srd_5_1_cc:item:weapon.shortbow@1` | `null` | `weapon_ranged_main` |

## Bounded review and remaining decisions

This pass reread all 17 handoff records, all 84 current receipt placements, the
original filename inventory and approved G01–G07 dispositions; it checked all 341
body/shadow pair dimensions directly and re-used the saved source and selected
motion witnesses. Separate-effect alpha was checked for every Goblin effect bank.
Goblin 17 Attack 4/5 and their effects received the additional targeted pixel
inspection described above. This is not an all-frame/all-direction semantic
certification or a native-game recording. No test run is claimed for a document
change, and no import, gallery recording or gameplay change occurred.

The final plan must distinguish its actual implementation choices from this source
evidence: exact native recipe/appearance admission, selected attack markers and
per-rig support registration, the human decision for mounted 11/12, and the human
correction for 17's misclassified ranged prop. No additional ability system or
per-species executor is justified by these sheets. Independent anti-slop and
anti-OOP/ECS reviewers review the parent plan; this appendix is their linked
source inventory, not a separate implementation authorization.

Pinned evidence SHA-256:

- Handoff v2: `fb25c343932523a684e2ea03db9aa287dfd73fc311cfb685867f6b5f9e5e9b8c`.
- Complete item/material receipt: `09c863abc8d7f39767c4ebb01b1b5dcb98a743d37ae5d655efdf1317c3ca1329`.
- Original filename inventory: `5bb5b92ebe87396a5290ffe10759ee724cbca7bbabf6e88b9d18ebf530df9d5e`.
