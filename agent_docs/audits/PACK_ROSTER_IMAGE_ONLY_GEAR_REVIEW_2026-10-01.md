# Root image-only gear and animation review

Date: 1 October2026. Reviewed personally by the root chat, without assigned weapons or Luna judgments as image authority. Scope: **180 non-animal variants:150 retained fantasy candidates and30 excluded modern variants**. The79 animals/dinosaurs remain unchanged and outside this review. No production artwork or gameplay changed.

Plan completed: inspect original idle facings and sampled action frames; record held objects, body protection and effects; declare SRD5.1 equipment/foundations separately; document optional mechanics; update the active gallery and mapping tables; perform anti-slop and anti-OOP/ECS self-reviews. These are author self-reviews, not independent approvals.

Human corrections preserved: Witchdoctor sword/shield and poison VFX; Berserker Longsword+Shortsword; Nomad axe/shield. Further action review corrects Assassin to two blades, DeathLord to sword+triangular shield, undead Wizard to empty hands with head antlers, Crusader to two-handed sword without shield, Orc01 to melee blade+shield and Orc12 to two curved blades. Paladin has a thin haft/head form; Mace is a declared representation, not a verified sword.

Inspection covers sampled poses, not every animation frame or hit-marker timing. Exact weapon subtypes, armor grades, creature identity, size, elemental damage and condition riders remain explicit design choices. Optional ability ideas do not silently change a selected source profile or its CR. All source traits remain unless a row explicitly removes/adapts them. Gear changes and extra abilities require later CR review and playtesting.

Source: [official SRD5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf). Only the two retained HD Enemy guns use [SRD5.2 equipment](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf), explicitly translated to5.1 loading/ammunition/action rules. Bow wielder upgrades and owned Devils provide stronger opponents; the existing level1–12 Devil teams and level5–12 Enemy teams remain proposals with conditional XP arithmetic.

Anti-slop self-review: checked180 unique source keys, all with actual source-image evidence and separate observation/item/rule/opportunity fields. Corrected anatomy mistaken for gear and VFX mistaken for items; withdrew inherited verification statements. No palette implies poison/fire/undead/flight. Exact item uncertainties are visible, and no repeated clip grants an extra action.

Anti-OOP/ECS self-review: only passive design data, evidence contacts and standalone HTML were changed. No engine classes, imports, type-dispatch, gameplay systems or generic feature framework were introduced.

The [150 individual authoring directions](PACK_ROSTER_INDIVIDUAL_AUTHORING_DIRECTIONS_2026-10-01.md) record the later human clarification: fixed Humanoids/skeletal characters are specials because modular sprites cover ordinary ones; fixed Goblin/Orc/Devil/Zombie packs cover core SRD creatures plus specials. New signatures remain proposed, not silently balanced.

## Per-variant observations and opportunities

### orcs_goblins / Goblin 01

**Observed:** one axe; shield not demonstrated; cloth/harness with exposed limbs.

**Chosen items:** Handaxe.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Handaxe +1, 1d6-1 slashing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-929425db7355-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-929425db7355-1.png).

### orcs_goblins / Goblin 02

**Observed:** empty hands; shield not demonstrated; purple robe.

**Chosen items:** No carried weapon.

**Animations/VFX:** Purple hand stream, orb, projecting burst and body-surrounding aura in Attack1–6. AttackRun keeps purple emission; Block is arm guard.

**Ability opportunities:** Use the selected spellcaster’s existing spells and their actual components, saves, concentration and slots. An aura/ward pose can present Shield/Mage Armor where available; it does not establish a permanent buff.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Deliberate ancestry/type adaptation: Small Goblinoid or Medium Orc Humanoid, retaining Mage ability scores rather than mixing source attack modifiers. No free racial bonus damage. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d1c54a5b3e62-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d1c54a5b3e62-1.png).

### orcs_goblins / Goblin 03

**Observed:** one bow; back quiver; shield not demonstrated; cloth/harness with exposed limbs.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Shortbow +4, 1d6+2 piercing; two hands, actual arrows; range80/320ft. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e3297820f656-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e3297820f656-1.png).

### orcs_goblins / Goblin 09

**Observed:** one bow; back quiver; shield not demonstrated; gray limb/body protection, red headgear.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Shortbow +4, 1d6+2 piercing; two hands, actual arrows; range80/320ft. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-948039c3fdda-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-948039c3fdda-1.png).

### orcs_goblins / Goblin 04

**Observed:** one curved sword; shield present; metal-looking helmet, shoulders and limbs.

**Chosen items:** Scimitar, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Scimitar +4, 1d6+2 slashing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ce0d29fb29b9-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ce0d29fb29b9-1.png).

### orcs_goblins / Goblin 05

**Observed:** one long pointed spear; shield not demonstrated; cloth/harness with exposed limbs.

**Chosen items:** Spear.

**Animations/VFX:** Long-haft thrust/sweep, overhead lift, leap/low attack and running lunge. Pole length does not establish10-ft reach.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Spear +1, 1d6-1 piercing (1d8-1 two-handed); reach5ft, thrown20/60ft. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9531f0b464bf-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9531f0b464bf-1.png).

### orcs_goblins / Goblin 10

**Observed:** one three-pronged trident; shield not demonstrated; gray limb/shoulder protection, red headgear.

**Chosen items:** Trident.

**Animations/VFX:** Long-haft thrust/sweep, overhead lift, leap/low attack and running lunge. Pole length does not establish10-ft reach.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Trident +1, 1d6-1 piercing (1d8-1 two-handed); reach5ft, thrown20/60ft. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6b85ffd23aab-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6b85ffd23aab-1.png).

### orcs_goblins / Goblin 06

**Observed:** one sword; shield present; gray body/limb protection and red helmet; gray shield.

**Chosen items:** Shortsword, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Shortsword +4, 1d6+2 piercing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bc130498295a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bc130498295a-1.png).

### orcs_goblins / Goblin 07

**Observed:** two independent short blades, one per hand; shield not demonstrated; shoulder protection and red headgear.

**Chosen items:** Shortsword, Dagger.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Shortsword +4, 1d6+2 piercing; Dagger +4, 1d4+2 piercing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-50fe4d5f84b9-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-50fe4d5f84b9-1.png).

### orcs_goblins / Goblin 13

**Observed:** one wooden club; shield not demonstrated; helmet/shoulder piece and waist covering.

**Chosen items:** Club.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Club +1, 1d4-1 bludgeoning. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a09db534ac3a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a09db534ac3a-1.png).

### orcs_goblins / Goblin 08

**Observed:** one crooked wooden staff; shield not demonstrated; red hood and dark robe.

**Chosen items:** Quarterstaff.

**Animations/VFX:** Wood staff with purple hand stream/orb and body-surrounding burst in Attack1–6; running emission, staff/arm guard.

**Ability opportunities:** Use the selected spellcaster’s existing spells and their actual components, saves, concentration and slots. An aura/ward pose can present Shield/Mage Armor where available; it does not establish a permanent buff.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Quarterstaff +2, 1d6-1 bludgeoning (1d8-1 two-handed). Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Deliberate ancestry/type adaptation: Small Goblinoid or Medium Orc Humanoid, retaining Mage ability scores rather than mixing source attack modifiers. No free racial bonus damage. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ae641e971b21-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ae641e971b21-1.png).

### orcs_goblins / Goblin 16

**Observed:** one sword; shield present; brown torso covering; wooden shield.

**Chosen items:** Shortsword, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Shortsword +4, 1d6+2 piercing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-58d86e2b3916-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-58d86e2b3916-1.png).

### orcs_goblins / Goblin 17

**Observed:** one curved sword and one bow held together; shield not demonstrated; metal shoulder piece, waist cloth.

**Chosen items:** Scimitar, Shortbow.

**Animations/VFX:** Sword swings while bow stays carried; Attack5 produces orange flame at forward hand. Block/RunAttack use carried equipment; no bow-shot animation established in sampled set.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Scimitar +4, 1d6+2 slashing; Shortbow +4, 1d6+2 piercing; two hands, actual arrows; range80/320ft. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-68421584bd5e-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-68421584bd5e-1.png).

### orcs_goblins / Goblin 11

**Observed:** one axe; mounted on tan quadruped; shield present; cloth/harness; wooden shield and saddle.

**Chosen items:** Handaxe, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Handaxe +1, 1d6-1 slashing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included. Mounted rider remains a Goblin; preserve a separately authored Worg mount candidate and5.1 mounted combat action/control rules. Mount type/size is a declared binding, not an animal audit. Rider Axe+Shield remain one-handed.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a085e824f8ac-0.png).

### orcs_goblins / Goblin 12

**Observed:** one axe; mounted on gray quadruped; shield present; metal shoulders and red headgear; shield and saddle.

**Chosen items:** Handaxe, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Handaxe +1, 1d6-1 slashing. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included. Mounted rider remains a Goblin; preserve a separately authored Worg mount candidate and5.1 mounted combat action/control rules. Mount type/size is a declared binding, not an animal audit. Rider Axe+Shield remain one-handed.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-cce79746413e-0.png).

### orcs_goblins / Goblin 14

**Observed:** one spiked mace/club; shield present; metal shoulders and helmet; wooden shield.

**Chosen items:** Mace, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Goblin block (source CR1/4, HP7) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Mace +1, 1d6-1 bludgeoning. No source Multiattack. Two Light blades permit ordinary bonus offhand attack without ability damage modifier; competes with Nimble Escape. Bow needs both hands: stow sword before firing. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-afbb73d270e3-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-afbb73d270e3-1.png).

### orcs_goblins / Goblin 15

**Observed:** two axes, one in each hand; shield not demonstrated; large dark metal-looking shoulder/body protection.

**Chosen items:** Handaxe, Handaxe.

**Animations/VFX:** Two axes alternate cuts and overhead attacks; Attack5 includes orange flame at forward hand. Large armor silhouette; no automatic size or area-hit rule.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Bugbear block (source CR1, HP27) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Handaxe +4, 2d6+2 slashing; Handaxe +4, 2d6+2 slashing. Keep source Brute/Surprise Attack; paired Light handaxes permit ordinary5.1 bonus offhand attack with no STR damage modifier (Brute adds one die), not automatic Multiattack. No Goblin Nimble Escape silently added. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-32986b4294bf-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-32986b4294bf-1.png).

### orcs_goblins / Orc 01

**Observed:** one curved blade used in melee swings; no bow draw/release demonstrated; shield present; spiked metal helmet and shoulders, red cloth.

**Chosen items:** Scimitar, Shield.

**Animations/VFX:** Curved blade swings while shield turns with guard arm; Block raises shield. No bow draw/release in Attack1–4 or RunAttack.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored and Shield, AC13; remove unpictured source weapons/actions. Scimitar +5, 1d6+3 slashing. No source Multiattack. Paired Light weapons permit ordinary bonus offhand attack without STR damage modifier; Mace is not Light so Mace+Handaxe does not qualify. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7afa95d6dc4c-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7afa95d6dc4c-1.png).

### orcs_goblins / Orc 02

**Observed:** one broad axe; shield not demonstrated; torso harness and wrist/leg guards.

**Chosen items:** Battleaxe.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Battleaxe +5, 1d8+3 slashing (1d10+3 two-handed). Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5d3e3944da0e-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5d3e3944da0e-1.png).

### orcs_goblins / Orc 03

**Observed:** one axe; shield not demonstrated; dark torso protection and gold shoulders/helmet.

**Chosen items:** Battleaxe.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Battleaxe +5, 1d8+3 slashing (1d10+3 two-handed). Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-210550d27777-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-210550d27777-1.png).

### orcs_goblins / Orc 09

**Observed:** one short broad sword/knife; shield not demonstrated; gray shoulder pieces, red cloth.

**Chosen items:** Shortsword.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Shortsword +5, 1d6+3 piercing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7094bd5fc91-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7094bd5fc91-1.png).

### orcs_goblins / Orc 11

**Observed:** one axe; shield present; brown torso protection; wooden shield.

**Chosen items:** Battleaxe, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored and Shield, AC13; remove unpictured source weapons/actions. Battleaxe +5, 1d8+3 slashing. No source Multiattack. Paired Light weapons permit ordinary bonus offhand attack without STR damage modifier; Mace is not Light so Mace+Handaxe does not qualify. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-fc583208c257-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-fc583208c257-1.png).

### orcs_goblins / Orc 04

**Observed:** one wooden club; shield not demonstrated; brown tunic, exposed limbs.

**Chosen items:** Club.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Club +5, 1d4+3 bludgeoning. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bf6382ee32f5-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bf6382ee32f5-1.png).

### orcs_goblins / Orc 05

**Observed:** one bow; back quiver; shield not demonstrated; orange robe/tunic and head covering.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Shortbow +3, 1d6+1 piercing; two hands, actual arrows; range80/320ft. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3314bc15e800-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3314bc15e800-1.png).

### orcs_goblins / Orc 06

**Observed:** one long staff/pole; shield not demonstrated; skull-like head/shoulder decoration and robe.

**Chosen items:** Quarterstaff.

**Animations/VFX:** Staff and purple hand stream, orb, projecting burst and body-surrounding aura in Attack1–6. Running emission; staff lifted in Block.

**Ability opportunities:** Use the selected spellcaster’s existing spells and their actual components, saves, concentration and slots. An aura/ward pose can present Shield/Mage Armor where available; it does not establish a permanent buff.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Quarterstaff +2, 1d6-1 bludgeoning (1d8-1 two-handed). Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Deliberate ancestry/type adaptation: Small Goblinoid or Medium Orc Humanoid, retaining Mage ability scores rather than mixing source attack modifiers. No free racial bonus damage. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5121e210b4ed-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5121e210b4ed-1.png).

### orcs_goblins / Orc 07

**Observed:** empty hands; shield not demonstrated; orange mantle/head covering and tunic.

**Chosen items:** No carried weapon.

**Animations/VFX:** Green hand streams/orbs and green aura in Attack1–6, but AttackRun uses purple particles. This variation prevents assuming all attacks cause poison.

**Ability opportunities:** Stock Mage spell options remain separate from green FX. Optional poison bolt would need an explicit spell/profile substitution; color does not add poisoned. Use one control concentration spell while allies pressure targets.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Deliberate ancestry/type adaptation: Small Goblinoid or Medium Orc Humanoid, retaining Mage ability scores rather than mixing source attack modifiers. No free racial bonus damage. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-44b7ebe88f88-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-44b7ebe88f88-1.png).

### orcs_goblins / Orc 08

**Observed:** one curved sword; shield present; spiked helmet, gray shoulders, red cloth.

**Chosen items:** Scimitar, Shield.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored and Shield, AC13; remove unpictured source weapons/actions. Scimitar +5, 1d6+3 slashing. No source Multiattack. Paired Light weapons permit ordinary bonus offhand attack without STR damage modifier; Mace is not Light so Mace+Handaxe does not qualify. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7c4a26cf35a4-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7c4a26cf35a4-1.png).

### orcs_goblins / Orc 10

**Observed:** one spiked mace and one axe held together; shield not demonstrated; gray shoulder protection, brown waist covering.

**Chosen items:** Mace, Handaxe.

**Animations/VFX:** Mace and axe alternate swings; Attack5 is a kick-like pose. No extra attack or magical burst granted by the fifth animation.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Mace +5, 1d6+3 bludgeoning; Handaxe +5, 1d6+3 slashing. No source Multiattack. Paired Light weapons permit ordinary bonus offhand attack without STR damage modifier; Mace is not Light so Mace+Handaxe does not qualify. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-96ebdb31f6cb-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-96ebdb31f6cb-1.png).

### orcs_goblins / Orc 12

**Observed:** two long dark curved blades moved separately in melee swings; no bow draw demonstrated; shield not demonstrated; spiked helmet, large gray shoulders, red cloth.

**Chosen items:** Scimitar, Scimitar.

**Animations/VFX:** Two long dark curved blades sweep/thrust separately in Attack1–5; Block and running attack keep blades. Initial bow interpretation withdrawn after action review.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Orc block (source CR1/2, HP15) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Scimitar +5, 1d6+3 slashing; Scimitar +5, 1d6+3 slashing. No source Multiattack. Paired Light weapons permit ordinary bonus offhand attack without STR damage modifier; Mace is not Light so Mace+Handaxe does not qualify. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/orcs_goblins-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-orcs_goblins-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d8032d2f4092-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d8032d2f4092-1.png).

### demons / Demon Beast 1

**Observed:** paired forearm blade-like appendages; shield not demonstrated; horns, exposed red body; dark/gold plates.

**Chosen items:** authored intrinsic blades.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C01 Thornback Devil; 3 / +2; Medium; 16/14/16/8/12/10; 17, half plate; 67 (9d8+27); 30 ft; Two Claws, +5, 1d8+3 slashing each. Spined Body: a creature grappling it takes 1d4 piercing at the start of this devil's turn. Shoulder armor is equipment; spines are anatomy.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9b89ec0cc5f2-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9b89ec0cc5f2-1.png).

### demons / Demon Spawn 6

**Observed:** one bow; shield not demonstrated; dark tunic and back quiver.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks. Explode/Explode Copy has a red gore cloud; no arrow element established.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C16 Bow Harrier Devil; 1 / +2; Medium; 12/16/12/10/12/10; 14, leather; 27 (5d8+5); 30 ft; Two Shortbow attacks, +5, range 80/320 ft, 1d6+3 piercing each. Carries arrows and the bow; no stock crossbow, shield or invisible melee sidearm.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f047051cdaa8-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f047051cdaa8-1.png).

### demons / Demon Beast 2

**Observed:** paired forearm blade-like appendages; shield not demonstrated; horns, exposed red body; dark/gold plates.

**Chosen items:** authored intrinsic blades.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C02 Hookclaw Devil; 4 / +2; Medium; 16/16/18/10/12/12; 15, natural 12+DEX; 102 (12d8+48); 30 ft; Two Hook Claws, +5, reach 10 ft, 2d6+3 slashing each. May replace one with an ordinary grapple, Athletics +5; only targets within 5 ft may be grappled. A grapple occupies one claw; afterward Multiattack uses the free claw twice, never a held claw.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-dc8c714278e0-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-dc8c714278e0-1.png).

### demons / Demon Spawn 12

**Observed:** one short blade; shield present; pale body/limb protection, helmet; pale shield.

**Chosen items:** Shortsword, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C22 Bulwark Devil; 4 / +2; Medium; 18/12/18/10/12/12; 18, half plate and shield; 85 (10d8+40); 30 ft; Two Shortsword attacks, +6 using STR, 1d6+4 piercing plus 1d6 necrotic each. Infernal Weapons; Shield Cover. A real shield soldier, with no adopted Dretch cloud or Demon subtype.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7adfb8fd69e9-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7adfb8fd69e9-1.png).

### demons / Demon Beast 3

**Observed:** long finger/claw hands, no held weapon; shield not demonstrated; spiked dark shoulder/body protection.

**Chosen items:** authored claws.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C03 Ironhide Devil; 5 / +3; Medium; 18/12/20/10/14/12; 16, half plate; 123 (13d8+65); 30 ft; Two Claws, +7, 2d6+4 slashing each. Magic Resistance. Athletics +7 for ordinary grapples/shoves. Its role is the durable melee screen; no invisible shield or stench.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-98f50ba58701-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-98f50ba58701-1.png).

### demons / Demon Beast 4

**Observed:** claw hands, no held weapon; shield not demonstrated; red body, horns and bat-like wings.

**Chosen items:** authored claws.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction. Winged body is visible; fly speed and flight animation binding are separate decisions.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C04 Fellwing Devil; 6 / +3; Large; 20/14/20/12/14/14; 16, natural 14+DEX; 136 (13d10+65); 30 ft; fly 50 ft; Two Claws, +8, 2d8+5 slashing each, and one Gore, +8, 2d6+5 piercing. Magic Resistance; body attacks magical. No vulture beak, spores or demon-excluding screech.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8de058a760e3-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8de058a760e3-1.png).

### demons / Demon Elite 3

**Observed:** one large dark blade-like form in hand; shield not demonstrated; spiked gray body/limb protection and dark wings.

**Chosen items:** authored blade/claw attack; held-versus-anatomical unresolved.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction. Winged body is visible; fly speed and flight animation binding are separate decisions.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C08 Wing Regent Devil; 12 / +4; Large; 22/14/22/18/16/20; 17, half plate; 207 (18d10+108); 30 ft; fly 60 ft; Three Claws, +10, 2d8+6 slashing plus 2d6 necrotic each; magical body attacks. Magic Resistance, Devil's Sight/darkvision 120 ft, Legendary Resistance 2/day. Innate Slow 1/day and Counterspell 3/day, DC17. Two legendary actions per round, regained at its turn: Reposition costs 1 and moves half speed with normal opportunity attacks; Claw costs 2 and makes one Claw. Each is taken at the end of another creature's turn, and none while incapacitated. A proper upper-tier boss, not a renamed Vrock.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-aa3df84eec3d-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-aa3df84eec3d-1.png).

### demons / Demon Beast 5

**Observed:** claw hands, no held weapon; shield not demonstrated; red body, horns and bat-like wings.

**Chosen items:** authored claws.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction. Winged body is visible; fly speed and flight animation binding are separate decisions.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C05 Huntsman Wing Devil; 4 / +2; Medium; 18/16/18/12/14/12; 16, natural 13+DEX; 93 (11d8+44); 30 ft; fly 40 ft; Two Claws, +6, 2d6+4 slashing each. Devil's Sight, darkvision 120 ft. No free Flyby: disengaging still costs its action, and normal movement can provoke.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-048e6d6865b7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-048e6d6865b7-1.png).

### demons / Demon Elite 1

**Observed:** two curved glowing blades, one per hand; shield not demonstrated; dark head/shoulder protection and brown trousers.

**Chosen items:** Scimitar, Scimitar.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C06 Oathblade Devil; 6 / +3; Medium; 18/18/18/14/14/16; 17, half plate; 119 (14d8+56); 30 ft; Three Scimitar attacks across its two blades, +7, 1d6+4 slashing plus 1d6 necrotic each. Infernal Weapons, Magic Resistance; Blade Parry +3. No off-hand bonus attack added.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1c51ab737db3-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1c51ab737db3-1.png).

### demons / Demon Elite 2

**Observed:** one large double-headed axe; shield not demonstrated; dark metal-looking body/limb protection.

**Chosen items:** Greataxe.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C07 Blade Marshal Devil; 7 / +3; Medium; 20/12/20/14/14/16; 18, plate; 142 (15d8+75); 30 ft; Three Greataxe attacks, +8, 1d12+5 slashing plus 1d6 necrotic each. Infernal Weapons, Magic Resistance; Blade Parry +3. Innate Command 3/day, DC14. One two-handed axe, no shield; its orders use a real spell action rather than free ally turns.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8fdb756ad9a1-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8fdb756ad9a1-1.png).

### demons / Demon Spawn 7

**Observed:** one dark bow; shield not demonstrated; dark body/limb protection, headgear and back quiver.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks. Explode/Explode Copy has a red gore cloud; no arrow element established.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C17 Night Archer Devil; 2 / +2; Medium; 12/18/14/12/14/12; 16, studded leather; 52 (8d8+16); 30 ft; Two Shortbow attacks, +6, range 80/320 ft, 1d6+4 piercing each. Devil's Sight, darkvision 120 ft. An armored archer, not the earlier mace/shield proposal.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d3f7c6c1682c-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d3f7c6c1682c-1.png).

### demons / Demon Elite 4

**Observed:** one long three-pronged trident; shield not demonstrated; dark helmet/shoulders and large back spikes.

**Chosen items:** Trident.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C09 Trident Warden Devil; 5 / +3; Medium; 18/14/18/12/14/14; 17, half plate; 110 (13d8+52); 30 ft; Two Trident attacks, +7, reach 5 ft, 1d6+4 piercing (1d8+4 two-handed) plus 1d6 necrotic each. Infernal Weapons, Magic Resistance. Ordinary opportunity attacks when a target leaves reach; entering reach does not grant a free attack. No unobserved Beard or infernal-wound trait.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3d7a7ff0e102-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3d7a7ff0e102-1.png).

### demons / Demon Elite 5

**Observed:** one straight broad sword; shield present; pale helmet/body/limb protection; large pale shield.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C10 Oath Captain Devil; 8 / +3; Medium; 20/12/20/16/16/18; 20, plate and shield; 152 (16d8+80); 30 ft; Three Longsword attacks, +8, 1d8+5 slashing plus 1d6 necrotic each. Infernal Weapons, Magic Resistance; Shield Cover. Innate Bless 3/day and Dispel Magic 1/day, DC15. Bless remains an action, concentration and three targets; it is not a passive Leadership aura. Free the sword hand for somatic casting.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0f6db97299d7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0f6db97299d7-1.png).

### demons / Demon Elite 6

**Observed:** one broad crescent-headed axe; shield present; dark helmet/body/limb protection; large dark shield.

**Chosen items:** Battleaxe, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C11 Gate Tyrant Devil; 10 / +4; Medium; 22/12/22/12/14/18; 20, plate and shield; 199 (19d8+114); 30 ft; Three Battleaxe attacks, +10, 1d8+6 slashing plus 2d6 necrotic each. Infernal Weapons, Magic Resistance; Blade Parry +3. May replace one attack with ordinary Shove, Athletics +10. Innate Thunderwave at 3rd spell level 3/day and Dispel Magic 1/day, DC16, instead of Multiattack; free the axe hand for somatic casting. It has no oversized two-handed axe while a shield is held.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-10cdaff8e0e0-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-10cdaff8e0e0-1.png).

### demons / Demon spawn 1

**Observed:** one short staff/wand with glowing tip; shield not demonstrated; dark tunic and hood.

**Chosen items:** Wand (focus; no melee staff attack).

**Animations/VFX:** Attack1–4 hand/focus projectile charges; Attack5/6 large aura or ground-circle effect, running emission and arm/staff guard.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C12 Ash Scribe Devil; 2 / +2; Medium; 8/14/14/14/12/16; 12, unarmored; 45 (7d8+14); 30 ft; Two Bolts, +5, 2d6 force each; no melee staff attack is selected for the short wand. Innate Web 3/day, Grease 3/day, Bless 1/day, DC13. Casting a spell replaces its Bolt action.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-17e57196c084-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-17e57196c084-1.png).

### demons / Demon Spawn 8

**Observed:** one long orb-tipped staff; shield not demonstrated; dark robe and pale horn/head decoration.

**Chosen items:** Quarterstaff.

**Animations/VFX:** Attack1–4 hand/focus projectile charges; Attack5/6 large aura or ground-circle effect, running emission and arm/staff guard.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C18 Night Notary Devil; 4 / +2; Medium; 10/14/16/16/14/18; 12, unarmored; 90 (12d8+36); 30 ft; Two Bolts, +6, 3d6 force each; or Quarterstaff +2, 1d6 bludgeoning (1d8 two-handed). Magic Resistance; Devil's Sight/darkvision 120 ft. Innate Darkness 3/day, Web 3/day, Slow 1/day, Counterspell 1/day, DC14. Each concentration spell competes with the others; no simultaneous Darkness+Web from this caster.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a2b90df66405-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a2b90df66405-1.png).

### demons / Demon Spawn 10

**Observed:** one bow; shield not demonstrated; pale armor-like covering, helmet and quiver.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks. Explode/Explode Copy has a red gore cloud; no arrow element established.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C20 Ivory Marksman Devil; 3 / +2; Medium; 12/18/16/12/14/12; 17, half plate; 90 (12d8+36); 30 ft; Two Longbow attacks, +6, range 150/600 ft, 1d8+4 piercing plus 1d6 necrotic each. Infernal Weapons. An armored bow user, not the earlier Mage proposal.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-194c32eb9238-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-194c32eb9238-1.png).

### demons / Demon Spawn 13

**Observed:** one axe and one straight sword, both held; shield not demonstrated; shoulder harness and waist cloth.

**Chosen items:** Handaxe, Longsword.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C23 Tollbreaker Devil; 3 / +2; Medium; 18/14/16/10/12/10; 14, studded leather; 90 (12d8+36); 30 ft; One Handaxe +6, 1d6+4 slashing, and one Longsword +6, 1d8+4 slashing in Multiattack; each adds 1d6 necrotic through Infernal Weapons. May replace one attack with ordinary Shove, Athletics +6. Axe and straight sword are both held; the Longsword cannot be used two-handed while the axe is held. No Mage spell list.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-2590637c8baf-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-2590637c8baf-1.png).

### demons / Demon Spawn 2

**Observed:** one spiked mace; shield not demonstrated; dark shoulder piece and waist covering.

**Chosen items:** Mace.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C13 Debt Collector Devil; 1 / +2; Medium; 14/14/14/10/10/10; 14, studded leather; 39 (6d8+12); 30 ft; Two attacks with its one Mace +4, 1d6+2 bludgeoning each. A single spiked mace is observed; there is no second club. No Spy or Sneak Attack chassis.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-aa9f5048eb12-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-aa9f5048eb12-1.png).

### demons / Demon Spawn 5

**Observed:** two curved swords, one per hand; shield not demonstrated; dark body/limb protection and hood.

**Chosen items:** Scimitar, Scimitar.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C15 Contract Cutter Devil; 2 / +2; Medium; 12/16/14/12/12/12; 15, studded leather; 45 (7d8+14); 30 ft; Two Scimitar attacks, +5, 1d6+3 slashing each. Blade Parry +2. Two curved blades remain two real possessions, without a third bonus attack.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f9eb8341082c-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f9eb8341082c-1.png).

### demons / Demon Spawn 3

**Observed:** one scythe-like long pole with curved blade; shield not demonstrated; red body and bat-like wings.

**Chosen items:** Sickle (scaled scythe presentation; reach 5 ft).

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction. Winged body is visible; fly speed and flight animation binding are separate decisions.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** Full SRD5.1 Imp retained, including Sting, Invisibility and Shapechanger. Scythe art represented by chosen Sickle +0, 1d4−2 slashing (minimum0), reach5ft; AC13. This representation is an explicit compromise; no Heavy weapon or10-ft reach. Tiny-scale and alternate-form rig bindings remain unresolved.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ef39f63d875a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ef39f63d875a-1.png).

### demons / Demon Spawn 4

**Observed:** one broad straight sword; shield present; dark body/limb protection and helmet; dark shield.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C14 Wardblade Devil; 2 / +2; Medium; 16/12/14/10/12/10; 17, scale mail and shield; 52 (8d8+16); 30 ft; Two Longsword attacks, +5, 1d8+3 slashing each. Shield Cover. Two-handed sword damage is unavailable while the shield is held.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7c436df99411-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7c436df99411-1.png).

### demons / Demon Spawn 9

**Observed:** one curved sword; shield present; dark torso covering and hood; gray shield.

**Chosen items:** Scimitar, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C19 Gate Guard Devil; 2 / +2; Medium; 12/16/16/10/12/10; 17, studded leather and shield; 75 (10d8+30); 30 ft; Two Scimitar attacks, +5, 1d6+3 slashing each. Shield Cover. The blade and shield are visible; exact armor subtype is a chosen representation rather than a pixel measurement.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6d502f29b8aa-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6d502f29b8aa-1.png).

### demons / Demon Spawn 11

**Observed:** one orb-tipped short staff/wand; shield not demonstrated; pale helmet and body/limb protection.

**Chosen items:** Wand (focus; no melee staff attack).

**Animations/VFX:** Attack1–4 hand/focus projectile charges; Attack5/6 large aura or ground-circle effect, running emission and arm/staff guard.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C21 Bastion Magus Devil; 3 / +2; Medium; 12/14/16/14/12/16; 17, half plate; 75 (10d8+30); 30 ft; Two Bolts, +5, 2d6 force each; no melee staff attack is selected for the short orb wand. Innate Bless 3/day, Web 3/day and Shield 3/day, DC13. Shield uses its reaction, not a carried shield. No Thug/Berserker chassis or bare-fist assumption.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5fd12377e45a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5fd12377e45a-1.png).

### demons / Imp 1

**Observed:** one axe; shield present; waist covering; brown shield and bat-like wings.

**Chosen items:** Handaxe, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction. Winged body is visible; fly speed and flight animation binding are separate decisions.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** Full SRD5.1 Imp including Sting, Invisibility and Shapechanger retained. Add proficient Handaxe +0, 1d6−2 slashing (minimum0), Shield normal-form AC15. STR6 prevents using DEX on Handaxe; original tiny-scale/alternate-form gear bindings remain unresolved.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-86f6d9af9d77-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-86f6d9af9d77-1.png).

### demons / Imp 2

**Observed:** one wooden club; shield not demonstrated; dark shoulder/harness pieces and waist cloth.

**Chosen items:** Club.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C24 Club Mote Devil; 1/8 / +2; Small; 10/14/10/8/10/8; 12, unarmored; 7 (2d6); 25 ft; Club +2, 1d4 bludgeoning. One attack or an ordinary Help action. No flying, poisoned sting or shapechanging.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ccaced2ba746-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ccaced2ba746-1.png).

### demons / Imp 3

**Observed:** one curved sword; shield not demonstrated; gray helmet/body/limb protection and purple wings.

**Chosen items:** Scimitar.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C25 Standard Mote Devil; 1/4 / +2; Small; 10/14/12/10/10/12; 13, leather; 13 (3d6+3); 25 ft; Scimitar +4, 1d6+2 slashing. Can use ordinary Help while close to the target. Back-mounted wing/standard classification remains unresolved; this proposal grants no fly speed or aura from that silhouette.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-89be8c972e78-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-89be8c972e78-1.png).

### demons / Imp 4

**Observed:** one short curved blade; shield not demonstrated; dark shoulder/torso covering and waist cloth.

**Chosen items:** Dagger.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C26 Needle Mote Devil; 1/8 / +2; Small; 10/14/10/8/10/8; 12, unarmored; 7 (2d6); 25 ft; Dagger +4, 1d4+2 piercing; thrown 20/60 ft consumes that carried dagger. One attack; no automatic return or ammunition duplication.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5043e25bea9f-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5043e25bea9f-1.png).

### demons / Imp 5

**Observed:** empty hands; shield not demonstrated; exposed red body, no worn armor established.

**Chosen items:** authored claw.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C27 Claw Mote Devil; 1/8 / +2; Small; 12/12/10/6/10/6; 11, unarmored; 7 (2d6); 25 ft; Authored intrinsic Claw +3, 1d4+1 slashing. No carried weapon; the creature design explicitly chooses a claw body attack, not a humanoid's removed weapon dice.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b3dbd13af397-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b3dbd13af397-1.png).

### demons / Imp 7

**Observed:** one bow; shield not demonstrated; dark body/limb covering, hood and back quiver.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks. Explode/Explode Copy has a red gore cloud; no arrow element established.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C29 Bow Mote Devil; 1/4 / +2; Small; 10/14/12/10/12/10; 13, leather; 18 (4d6+4); 25 ft; Shortbow +4, range 80/320 ft, 1d6+2 piercing; one attack, actual arrows. No wings, fly speed, shield or canonical Imp abilities.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a37df91302cb-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a37df91302cb-1.png).

### demons / Imp 10

**Observed:** two blade-like hand weapons; shield not demonstrated; pale body/limb protection and helmet.

**Chosen items:** Shortsword, Dagger.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C32 Twinhaft Mote Devil; 1/2 / +2; Small; 12/14/14/10/10/10; 16, scale mail; 27 (5d6+10); 25 ft; One Shortsword +4, 1d6+2 piercing, and one Dagger +4, 1d4+2 piercing in its authored Multiattack. Two blade forms are observed; exact second subtype remains a choice. No magical weapon or spell inferred from pale highlights.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-15c7964eb4bb-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-15c7964eb4bb-1.png).

### demons / Imp 6

**Observed:** one pointed spear/polearm; shield not demonstrated; dark body/limb covering and helmet.

**Chosen items:** Spear.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C28 Spear Mote Devil; 1/8 / +2; Small; 12/12/12/8/10/8; 12, leather; 9 (2d6+2); 25 ft; Spear +3, reach 5 ft, 1d6+1 piercing (1d8+1 two-handed), thrown 20/60 ft. No shield. A spear does not grant 10-ft reach.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7d747f1b2179-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7d747f1b2179-1.png).

### demons / Imp 8

**Observed:** one curved sword; shield present; dark body/limb protection and helmet; brown round shield.

**Chosen items:** Scimitar, Shield.

**Animations/VFX:** Attack1–4 cuts, thrust/chop or claw sweep; bright curved hit trails, guard pose and running attack. Explode/Explode Copy shows a red gore cloud on destruction.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C30 Buckler Mote Devil; 1/2 / +2; Small; 12/14/14/10/10/10; 15, leather and shield; 27 (5d6+10); 25 ft; Scimitar +4, 1d6+2 slashing; one attack. Shield Cover. The small round shield uses the ordinary shield +2, not a new buckler equipment system.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-945fa52aca18-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-945fa52aca18-1.png).

### demons / Imp 9

**Observed:** one long wooden staff and one short blade, both held; shield not demonstrated; dark torso covering and waist cloth.

**Chosen items:** Quarterstaff, Dagger.

**Animations/VFX:** Attack1–4 hand/focus projectile charges; Attack5/6 large aura or ground-circle effect, running emission and arm/staff guard.

**Ability opportunities:** Use this Devil’s independently authored attack/cast/guard action. Gore explosion is a death presentation unless an explicit radius, save, damage, timing and ally targeting are authored; it supplies no free death damage.

**Rules revision:** C31 Rod Mote Devil; 1/2 / +2; Small; 8/14/12/12/10/14; 12, unarmored; 18 (4d6+4); 25 ft; One Bolt +4, 1d6 force; or Quarterstaff +1, 1d6−1 bludgeoning (1d8−1 two-handed, minimum 0). Innate Grease 3/day and Bane 1/day, DC12. Also carries Dagger +4, 1d4+2 piercing, as an alternative action. Both are held; two-handed staff use requires freeing the dagger hand. For somatic casting stow one item; orange FX does not require fire damage.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/demons-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-demons-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eb0eedf98c7b-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eb0eedf98c7b-1.png).

### undead / 1Brute

**Observed:** one large straight sword; shield not demonstrated; skeletal body, shoulder/waist coverings.

**Chosen items:** Greatsword.

**Animations/VFX:** Broad white sword cleaves, running cut and overhead drop; QuickShot shows a full circular white sweep, Special1 a wide cleave. CastSpell is a jump pose.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Greatsword +7, 3d6+4 slashing. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Explicit owned type adaptation to Undead, poison immunity and immunity to poisoned/exhaustion; actions/HP remain source foundation. No Lich legendary actions, paralyzing touch, phylactery or CR21 claim. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-da6c05b0f55e-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-da6c05b0f55e-1.png).

### undead / 2DeathLord

**Observed:** one flaming straight sword and large triangular shield; shield present; dark body/limb protection and cloak.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Yellow/orange flaming sword cuts and fire ring; triangular shield remains attached in guard poses. QuickShot is a yellow/orange orbit around body; Special1/2 fiery sword sweeps.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Wight block (source CR3, HP45) except these declared changes: choose Plate and Shield, AC20; remove unpictured source weapons/actions. Longsword +4, 1d8+2 slashing. Explicit adapted Multiattack: two attacks with selected melee weapon or two selected bow attacks; one melee weapon attack may be replaced by stock Life Drain, +4,1d6+2 necrotic, DC13 CON max-HP reduction, source duration/zombie creation limits retained. Remove unpictured stock Longbow/Longsword. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-48d4b74b08c1-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-48d4b74b08c1-1.png).

### undead / 3DarkKnight

**Observed:** one straight sword; shield present; dark body/limb protection and helmet.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Sword and shield with yellow/orange sweeps, running slash and overhead cut. CastSpell/Pummel/QuickShot/Special1/2 are strong fire-like blade arcs, not a projectile weapon.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Wight block (source CR3, HP45) except these declared changes: choose Half plate and Shield, AC19; remove unpictured source weapons/actions. Longsword +4, 1d8+2 slashing. Explicit adapted Multiattack: two attacks with selected melee weapon or two selected bow attacks; one melee weapon attack may be replaced by stock Life Drain, +4,1d6+2 necrotic, DC13 CON max-HP reduction, source duration/zombie creation limits retained. Remove unpictured stock Longbow/Longsword. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b59e73b6cc44-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b59e73b6cc44-1.png).

### undead / 4Berserker

**Observed:** one long-hafted axe; shield not demonstrated; skeletal body with red straps/cloth.

**Chosen items:** Greataxe.

**Animations/VFX:** Long-haft axe cleaves and running leap. Kick has red/orange spinning ring; QuickShot/Special1 red flame fans; CastSpell white axe sweep. No bow.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Berserker block (source CR2, HP67) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Greataxe +5, 1d12+3 slashing. Explicit owned type adaptation to Undead, poison immunity and immunity to poisoned/exhaustion; actions/HP remain source foundation. No Lich legendary actions, paralyzing touch, phylactery or CR21 claim. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-464f02e66381-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-464f02e66381-1.png).

### undead / 5Archer

**Observed:** one bow; back quiver; shield not demonstrated; skeletal body and waist/leg coverings.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Wight block (source CR3, HP45) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Shortbow +4, 1d6+2 piercing; two hands, actual arrows; range80/320ft. Explicit adapted Multiattack: two attacks with selected melee weapon or two selected bow attacks; one melee weapon attack may be replaced by stock Life Drain, +4,1d6+2 necrotic, DC13 CON max-HP reduction, source duration/zombie creation limits retained. Remove unpictured stock Longbow/Longsword. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ae4d901a5909-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ae4d901a5909-1.png).

### undead / 6Warrior

**Observed:** one pointed spear; shield present; skeletal body and waist/leg coverings.

**Chosen items:** Spear, Shield.

**Animations/VFX:** Spear thrusts and chops, shield raised for blocking and pummel; specials are low spear-ready poses. No longsword demonstrated.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Wight block (source CR3, HP45) except these declared changes: choose Unarmored and Shield, AC14; remove unpictured source weapons/actions. Spear +4, 1d6+2 piercing; reach5ft, thrown20/60ft. Explicit adapted Multiattack: two attacks with selected melee weapon or two selected bow attacks; one melee weapon attack may be replaced by stock Life Drain, +4,1d6+2 necrotic, DC13 CON max-HP reduction, source duration/zombie creation limits retained. Remove unpictured stock Longbow/Longsword. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1aa11d3f929a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1aa11d3f929a-1.png).

### undead / 7DarkArcher

**Observed:** one bow; back quiver; shield not demonstrated; dark skeletal body/coverings.

**Chosen items:** Shortbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Wight block (source CR3, HP45) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Shortbow +4, 1d6+2 piercing; two hands, actual arrows; range80/320ft. Explicit adapted Multiattack: two attacks with selected melee weapon or two selected bow attacks; one melee weapon attack may be replaced by stock Life Drain, +4,1d6+2 necrotic, DC13 CON max-HP reduction, source duration/zombie creation limits retained. Remove unpictured stock Longbow/Longsword. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f6c877ae5f06-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f6c877ae5f06-1.png).

### undead / 8Necromancer

**Observed:** empty hands in sampled poses; shield not demonstrated; dark skeletal body and purple hood/cloth.

**Chosen items:** No carried weapon.

**Animations/VFX:** Magenta/purple hand orbs, forward streams and body-wrapping arc. Special1 is a vertical purple burst around torso; Special2 a forward stream. No held weapon.

**Ability opportunities:** Optional authored undead Mage variant may exchange one prepared3rd-level spell for Animate Dead; full costs/control limits remain. Magenta stream can present a legal existing ranged spell. Do not claim full Lich identity from robes/bones.

**Rules revision:** Retain complete SRD5.1 Archmage block (source CR12, HP99) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Explicit owned type adaptation to Undead, poison immunity and immunity to poisoned/exhaustion; actions/HP remain source foundation. No Lich legendary actions, paralyzing touch, phylactery or CR21 claim. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-00907c0569e2-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-00907c0569e2-1.png).

### undead / 9Wizard

**Observed:** empty hands; branching head antlers, no carried staff; shield not demonstrated; skeletal body and red cloth.

**Chosen items:** No carried weapon.

**Animations/VFX:** Empty-hand flame orbs, forward streams and Attack3 ground ring/embers. Special1 rising orange column; Special2 forward flame stream. Branching object is head antlers.

**Ability opportunities:** Use an explicitly adapted undead Mage, with stock Fire Bolt/Fireball and normal slots/concentration. Flame column is presentation, not automatic immunity or ongoing damage. No staff attack.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Explicit owned type adaptation to Undead, poison immunity and immunity to poisoned/exhaustion; actions/HP remain source foundation. No Lich legendary actions, paralyzing touch, phylactery or CR21 claim. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-undead-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-331c82110ee3-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-331c82110ee3-1.png).

### enemy / 1Hammer

**Observed:** one large two-handed hammer; shield not demonstrated; brown body/limb protection, head covering.

**Chosen items:** Maul.

**Animations/VFX:** Attack1–4 include horizontal hammer sweeps, overhead windup and downward strike; no magical burst established.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Half plate, AC17; remove unpictured source weapons/actions. Maul +7, 3d6+4 bludgeoning. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-aa233a9b00ae-0.png).

### enemy / 2Shooter

**Observed:** one long firearm-like barrel; back canister; shield not demonstrated; brown body covering and helmet.

**Chosen items:** Musket (5.2 item converted to 5.1).

**Animations/VFX:** Aims long gun; Attack3/4 violet plume at muzzle. Back canister present; projectile delivery visible, poison versus arcane payload is a design choice.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Assassin block (source CR8, HP78) except these declared changes: choose Half plate, AC17; remove unpictured source weapons/actions. Retain Assassinate, Evasion, poison resistance and once-per-turn4d6 Sneak Attack. Musket converted from5.2 equipment: +6, 1d12+3 piercing, range40/120ft, loading/two-handed/ammunition under5.1; one gunshot per action, plus source DC15 CON7d6 poison/half with actual poison. Remove unseen Shortsword/Light Crossbow; no two-shot Multiattack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-da81fa876c28-0.png).

### enemy / 3Footsoldier

**Observed:** one straight sword; shield present; helmet, body and limb protection.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Sword cuts in Attack1/2, shield-forward bash-like pose in Attack3 and further weapon strike in Attack4.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Plate and Shield, AC20; remove unpictured source weapons/actions. Longsword +7, 2d8+4 slashing. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Shield Bash +7, 2d4+4 bludgeoning, DC15 STR prone for Medium-or-smaller remains. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-588b187e6406-0.png).

### enemy / 4Assassin

**Observed:** two straight short blades, one in each hand; shield not demonstrated; hood, torso/limb covering.

**Chosen items:** Shortsword, Shortsword.

**Animations/VFX:** Two short blades in all-facing idle and Attack1–4 slash/thrust poses, with white arcs. Taunt holds blades outward; no firearm demonstrated.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Assassin block (source CR8, HP78) except these declared changes: choose Studded leather, AC15; remove unpictured source weapons/actions. Shortsword +6, 1d6+3 piercing; Shortsword +6, 1d6+3 piercing. Retain Assassinate, Evasion, poison resistance and once-per-turn4d6 Sneak Attack. Two Shortsword attacks, each +6, 1d6+3 piercing plus DC15 CON7d6 poison/half, sourced poison supplies. Remove unseen Light Crossbow. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-850c4a22d1a0-0.png).

### enemy / 5Bruiser

**Observed:** fists with large gauntlets; shield not demonstrated; torso/limb protection and gauntlets.

**Chosen items:** authored gauntlet strike.

**Animations/VFX:** Armored/gauntleted punches; orange/gold charge around fist in Attack1, straight jab in Attack2, sparks in Attack3 and large charged strike in Attack4.

**Ability opportunities:** Optional charged punch: replace one attack with a declared recharge5–6 strike, adding2d6 force and DC15 STR push5ft on hit; no stun inferred. Preserve action cost; recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Half plate, AC17; remove unpictured source weapons/actions. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Explicit authored trained strike replaces weapon attacks: +7,3d4+4 bludgeoning, three strikes in Multiattack. This is an owned extension of Brute to trained unarmed strikes, not ordinary5.1 unarmed damage. Remove Parry (no held melee weapon). Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-954ac3b5971b-0.png).

### enemy / 6Crusader

**Observed:** one large two-handed straight sword; shield not demonstrated; heavy body/limb protection, cloak.

**Chosen items:** Greatsword.

**Animations/VFX:** Large two-handed sword cleaves, low sweep and overhead attack across Attack1–4; both hands use weapon, no shield demonstrated.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Knight block (source CR3, HP52) except these declared changes: choose Plate, AC18; remove unpictured source weapons/actions. Greatsword +5, 2d6+3 slashing. Source Multiattack: two attacks with selected weapon; retain Brave, Leadership and Parry +2 (reaction, melee weapon in hand). Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c35d58481eed-0.png).

### enemy / 7Sniper

**Observed:** one long firearm-like barrel; shield not demonstrated; blue headgear, torso covering, exposed arms.

**Chosen items:** Musket (5.2 item converted to 5.1).

**Animations/VFX:** Long-gun aim/recoil; Attack3/4 red/orange muzzle plume. No automatic ignition or poisoned condition.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Assassin block (source CR8, HP78) except these declared changes: choose Studded leather, AC15; remove unpictured source weapons/actions. Retain Assassinate, Evasion, poison resistance and once-per-turn4d6 Sneak Attack. Musket converted from5.2 equipment: +6, 1d12+3 piercing, range40/120ft, loading/two-handed/ammunition under5.1; one gunshot per action, plus source DC15 CON7d6 poison/half with actual poison. Remove unseen Shortsword/Light Crossbow; no two-shot Multiattack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7177b4036146-0.png).

### enemy / 8Brawler

**Observed:** fists with gloves/gauntlets; shield not demonstrated; shirt, suspenders and trousers.

**Chosen items:** authored trained unarmed strike.

**Animations/VFX:** Gloved fists jab/hook across Attack1–4, with guarded stance; no held melee weapon.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Explicit authored trained strike replaces weapon attacks: +7,3d4+4 bludgeoning, three strikes in Multiattack. This is an owned extension of Brute to trained unarmed strikes, not ordinary5.1 unarmed damage. Remove Parry (no held melee weapon). Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4f01c97005b7-0.png).

### enemy / 9Commander

**Observed:** empty hands in sampled poses; shield not demonstrated; blue uniform and headgear.

**Chosen items:** No carried weapon.

**Animations/VFX:** Empty-hand magenta orb, circular sweep and forward curved trail; Attack4 is a handstand/kick-like motion. No carried quarterstaff.

**Ability opportunities:** Use full Archmage spell limits for magenta effects; handstand is presentation for ordinary movement/unarmed action, not teleport or bonus attack.

**Rules revision:** Retain complete SRD5.1 Archmage block (source CR12, HP99) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a3712762200d-0.png).

### enemy / 10Caster

**Observed:** one long wooden staff; shield not demonstrated; dark blue robe.

**Chosen items:** Quarterstaff.

**Animations/VFX:** Staff/hand magenta burst, swirl, charging pose and staff-downward emission in Attack1–4.

**Ability opportunities:** Use the selected spellcaster’s existing spells and their actual components, saves, concentration and slots. An aura/ward pose can present Shield/Mage Armor where available; it does not establish a permanent buff.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Quarterstaff +2, 1d6-1 bludgeoning (1d8-1 two-handed). Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-da1b31d6e705-0.png).

### enemy / 11Arcane elemental

**Observed:** empty hands; particle-covered humanoid outline; shield not demonstrated; no separate worn armor established.

**Chosen items:** No carried weapon.

**Animations/VFX:** Particle-covered humanoid emits magenta orb and wide swirl; a hopping/spinning motion accompanies another strike. No silhouette evidence for continuous flight/invisibility.

**Ability opportunities:** Use its authored short cone and bolt profile. Particle motion can present its movement; flight, invisibility and immunity require separately declared traits.

**Rules revision:** Authored Arcane Sentinel E01, target CR6 provisional; HP119; AC16; two Slams +6, 2d8+3; rechargeable 15-ft cone, DC15, 6d6 force. Authored defenses; not the Shadow profile.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-86b0482c7960-0.png).

### enemy / 12Guard

**Observed:** one long pointed spear/polearm; shield not demonstrated; torso covering and arm guards.

**Chosen items:** Spear.

**Animations/VFX:** Long spear performs horizontal/low/overhead sweeps and running/spinning lunge; no shield block item.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Half plate, AC17; remove unpictured source weapons/actions. Spear +7, 2d6+4 piercing (2d8+4 two-handed); reach5ft, thrown20/60ft. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-enemy-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a2d727d8fb49-0.png).

### hdz / ZombieCop1

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-de13e45ba87b-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-de13e45ba87b-1.png).

### hdz / ZombieCop2

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-449cc5d68f67-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-449cc5d68f67-1.png).

### hdz / ZombieCop3

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-22fd69d56ccd-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-22fd69d56ccd-1.png).

### hdz / ZombieCop4

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-cef103c707fd-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-cef103c707fd-1.png).

### hdz / ZombieFemale1

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-24d870b01194-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-24d870b01194-1.png).

### hdz / ZombieFemale2

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8a966923ee64-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8a966923ee64-1.png).

### hdz / ZombieFemale3

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-22b900f04453-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-22b900f04453-1.png).

### hdz / ZombieFemale4

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6a9ba25fdea7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6a9ba25fdea7-1.png).

### hdz / ZombieFemale5

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e9d5a6694c64-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e9d5a6694c64-1.png).

### hdz / ZombieFemale6

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4e2034b90f60-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4e2034b90f60-1.png).

### hdz / ZombieFemale7

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0b433c7126ac-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0b433c7126ac-1.png).

### hdz / ZombieGeneral1

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a0f39cee470e-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a0f39cee470e-1.png).

### hdz / ZombieGeneral2

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7fbd52320d7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7fbd52320d7-1.png).

### hdz / ZombieHulk1

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; oversized body, waist cloth/harness.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames. Oversized arms/body give a heavy slam silhouette; Hulk1 has green growths, Hulk2 pale exposed body.

**Ability opportunities:** Heavy slam and ordinary contested Shove can create a frontline role for stronger zombies. A slam does not gain automatic prone/stun; any on-hit save rider must be authored and CR recalculated.

**Rules revision:** Large scene size is a choice. Retain Ogre Zombie HP85, AC8, STR19 and Undead Fortitude; remove unseen Morningstar. Authored heavy Slam +6,2d8+4 bludgeoning replaces its attack. Crushing hold: action, one Slam; after hit target DC14 STR or grappled (escape DC14 using an action). One held target, speed0 only; one hand occupied. Subsequent Slam uses free arm; no automatic restrained. Original core Ogre Zombie defenses, senses and Undead Fortitude remain.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9c236cebf93a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9c236cebf93a-1.png).

### hdz / ZombieHulk2

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; oversized body, waist cloth/harness.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames. Oversized arms/body give a heavy slam silhouette; Hulk1 has green growths, Hulk2 pale exposed body.

**Ability opportunities:** Heavy slam and ordinary contested Shove can create a frontline role for stronger zombies. A slam does not gain automatic prone/stun; any on-hit save rider must be authored and CR recalculated.

**Rules revision:** Large scene size is a choice. Retain Ogre Zombie HP85, AC8, STR19 and Undead Fortitude; remove unseen Morningstar. Authored heavy Slam +6,2d8+4 bludgeoning replaces its attack. Crushing hold: action, one Slam; after hit target DC14 STR or grappled (escape DC14 using an action). One held target, speed0 only; one hand occupied. Subsequent Slam uses free arm; no automatic restrained. Original core Ogre Zombie defenses, senses and Undead Fortitude remain.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0a3bfc647458-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0a3bfc647458-1.png).

### hdz / ZombieMale1

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c1db645e0d54-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c1db645e0d54-1.png).

### hdz / ZombieMale2

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c38e8cfbbc4e-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c38e8cfbbc4e-1.png).

### hdz / ZombieMale3

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e8681e68e43c-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e8681e68e43c-1.png).

### hdz / ZombieMale4

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c3438c8bef3f-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c3438c8bef3f-1.png).

### hdz / ZombieMale5

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bc2a4c1a92eb-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bc2a4c1a92eb-1.png).

### hdz / ZombieMale6

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c73ce953dec0-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c73ce953dec0-1.png).

### hdz / ZombieMale7

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-399a86385dec-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-399a86385dec-1.png).

### hdz / ZombieMale8

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f833dc71e0fc-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f833dc71e0fc-1.png).

### hdz / ZombieMale9

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5d0d5e3dd843-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5d0d5e3dd843-1.png).

### hdz / ZombieMonster1

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; deformed exposed body, shorts/waist cloth.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7d552a1713f-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a7d552a1713f-1.png).

### hdz / ZombieMonster2

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; deformed exposed body, shorts/waist cloth.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-78daf1b65bb4-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-78daf1b65bb4-1.png).

### hdz / ZombieMonster3

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; deformed exposed body, shorts/waist cloth.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Large scene size is a choice. Retain Ogre Zombie HP85, AC8, STR19 and Undead Fortitude; remove unseen Morningstar. Authored heavy Slam +6,2d8+4 bludgeoning replaces its attack. Crushing hold: action, one Slam; after hit target DC14 STR or grappled (escape DC14 using an action). One held target, speed0 only; one hand occupied. Subsequent Slam uses free arm; no automatic restrained. Original core Ogre Zombie defenses, senses and Undead Fortitude remain.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5aac3cf85e7a-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5aac3cf85e7a-1.png).

### hdz / ZombieRadioactive1

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-709afd534c7f-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-709afd534c7f-1.png).

### hdz / ZombieRadioactive2

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b499d0750376-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b499d0750376-1.png).

### hdz / ZombieRadioactive3

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-62ba34945e29-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-62ba34945e29-1.png).

### hdz / ZombieSoldier1

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-abe6c3f3d0a3-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-abe6c3f3d0a3-1.png).

### hdz / ZombieSoldier2

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bd68531c05d5-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bd68531c05d5-1.png).

### hdz / ZombieSoldier3

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; long gun-like object on back, not held in sampled attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b74c971cea7b-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b74c971cea7b-1.png).

### hdz / ZombieSoldier4

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e5cc6c6da523-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e5cc6c6da523-1.png).

### hdz / ZombieSoldier5

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b6c799a22899-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b6c799a22899-1.png).

### hdz / ZombieSoldier6

**Excluded modern variant.** **Observed:** empty hands; reaching/slapping attack; shield not demonstrated; modern uniform; some headgear/vests, no shield.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 reaching strikes; Attack3 deep forward/downward lean; Attack4 raised arm; Attack5 low forward lunge; Die2 collapse. No hand-held item in sampled attack frames.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-hdz-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-96ff859f1461-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-96ff859f1461-1.png).

### top / Zombie 01

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b0620acb22a9-0.png).

### top / Zombie 02

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c6b95ada3478-0.png).

### top / Zombie 03

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6b8f62153135-0.png).

### top / Zombie 04

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4e666f2c218f-0.png).

### top / Zombie 05

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6e377d4417bb-0.png).

### top / Zombie 06

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7705da41cd6f-0.png).

### top / Zombie 07

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eebed9a90b63-0.png).

### top / Zombie 08

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-55cae943ecdf-0.png).

### top / Zombie 09

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-14dc68151d15-0.png).

### top / Zombie 10

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d5376f6e4275-0.png).

### top / Zombie Cop 01

**Excluded modern variant.** **Observed:** one short firearm/pistol; shield not demonstrated; blue modern uniform and cap.

**Chosen items:** Pistol (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d88b929ae955-0.png).

### top / Zombie Cop 02

**Excluded modern variant.** **Observed:** one brown club/baton; shield not demonstrated; blue modern uniform and cap.

**Chosen items:** Club (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-b78de20845ee-0.png).

### top / Zombie Cop 03

**Excluded modern variant.** **Observed:** knife visible in melee poses; short firearm appears in shooting clips; shield not demonstrated; red shirt, brown vest and broad yellow hat.

**Chosen items:** Dagger (excluded), Pistol (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a8c89a1f3408-0.png).

### top / Zombie Cop 04

**Excluded modern variant.** **Observed:** one short firearm/pistol; shield not demonstrated; white shirt, dark vest and blue cap.

**Chosen items:** Pistol (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-21c37d775a80-0.png).

### top / Zombie Decay 01

**Observed:** no held weapon; low crawling/reaching body; shield not demonstrated; severely damaged body with missing/lowered legs.

**Chosen items:** No carried weapon.

**Animations/VFX:** Severed-leg body stays low and reaches upward/forward in Melee Uppercut and Zombie melee1; useful crawl presentation, no ordinary standing run attack.

**Ability opportunities:** Crawling infiltrator: explicit chosen crawl speed and body clearance can enable approach through low gaps. Crawling art does not automatically impose prone. Grapple uses normal contested action; no free restraint.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0b46e1e86a94-0.png).

### top / Zombie Decay 02

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-8f9b156f1641-0.png).

### top / Zombie Decay 03

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-98cd61ea38a2-0.png).

### top / Zombie Decay 04

**Observed:** no held weapon; low crawling/reaching body; shield not demonstrated; severely damaged body with missing/lowered legs.

**Chosen items:** No carried weapon.

**Animations/VFX:** Severed-leg body stays low and reaches upward/forward in Melee Uppercut and Zombie melee1; useful crawl presentation, no ordinary standing run attack.

**Ability opportunities:** Crawling infiltrator: explicit chosen crawl speed and body clearance can enable approach through low gaps. Crawling art does not automatically impose prone. Grapple uses normal contested action; no free restraint.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-02.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-c449dcabec24-0.png).

### top / Zombie Decay 05

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-7de964fc5614-0.png).

### top / Zombie Fireman 01

**Excluded modern variant.** **Observed:** empty hands; shield not demonstrated; yellow protective suit and red helmet.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-5fe0b234de64-0.png).

### top / Zombie Fireman 02

**Excluded modern variant.** **Observed:** one axe; shield not demonstrated; yellow protective suit and gray head.

**Chosen items:** Battleaxe (excluded).

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3d4547870847-0.png).

### top / Zombie Radioactive 01

**Excluded modern variant.** **Observed:** empty hands; shield not demonstrated; decayed body and torn trousers.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-15f3b8db928c-0.png).

### top / Zombie Radioactive 02

**Excluded modern variant.** **Observed:** empty hands; shield not demonstrated; decayed body and torn trousers.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1f2b09a5f736-0.png).

### top / Zombie Radioactive 03

**Excluded modern variant.** **Observed:** empty hands; shield not demonstrated; decayed body and torn trousers.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-03.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-18920c1319b3-0.png).

### top / Zombie Radioactive 04

**Excluded modern variant.** **Observed:** empty hands; shield not demonstrated; decayed body and torn trousers.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established. Green glow/specks/growths are visible; exclusion remains.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a14fa3ffb8c1-0.png).

### top / Zombie Soldier 01

**Excluded modern variant.** **Observed:** one long firearm; shield not demonstrated; modern uniform and helmet/headgear.

**Chosen items:** Musket (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eb773e48544d-0.png).

### top / Zombie Soldier 02

**Excluded modern variant.** **Observed:** one long firearm; shield not demonstrated; modern uniform and helmet/headgear.

**Chosen items:** Musket (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-d3edc1eb6a0d-0.png).

### top / Zombie Soldier 03

**Excluded modern variant.** **Observed:** one long red-brown club/bat; shield not demonstrated; yellow modern uniform.

**Chosen items:** Club (excluded).

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-39905641a007-0.png).

### top / Zombie Soldier 04

**Excluded modern variant.** **Observed:** one long firearm-like implement and back pack; shield not demonstrated; yellow protective/modern suit and headgear.

**Chosen items:** Musket (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-f0dc8910a8a1-0.png).

### top / Zombie Soldier 05

**Excluded modern variant.** **Observed:** one long firearm; shield not demonstrated; modern uniform and helmet/headgear.

**Chosen items:** Musket (excluded).

**Animations/VFX:** Melee swings plus Attack3/Attack run2 muzzle discharge. Modern firearm clips remain excluded; no fantasy weapon substituted silently.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Excluded from fantasy encounters. Observations are retained for provenance; no active creature/loadout conversion.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-04.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ecb6e5c5ae83-0.png).

### top / Zombie Swamp 01

**Observed:** one straight sword; shield not demonstrated; green torn body/limb covering and boots.

**Chosen items:** Shortsword.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Shortsword +3, 1d6+1 piercing. Use one carried-item attack instead of Slam: STR13 gives +1 damage, +3 attack if item proficiency deliberately granted. Improvised crowbar uses +1 attack and1d4+1 bludgeoning without proficiency. No source Multiattack for paired blades. Retain Undead Fortitude. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4fb374fa1ccc-0.png).

### top / Zombie Swamp 02

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-07.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1e7ce708d0cf-0.png).

### top / Zombie Swamp 03

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6c3869ece6fc-0.png).

### top / Zombie Swamp 04

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-58f6bcbfebae-0.png).

### top / Zombie Swamp 05

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-1f5032ab3f34-0.png).

### top / Zombie Swamp 06

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-08.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-05.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-bf1475534c0b-0.png).

### top / Zombie Swamp 07

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-09.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-67e70144f794-0.png).

### top / Zombie Swamp 08

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-09.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-e0a3538fa533-0.png).

### top / Zombie Swamp 09

**Observed:** two short blades, one broad and one narrow; shield not demonstrated; green torn torso covering and trousers.

**Chosen items:** Shortsword, Dagger.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Shortsword +3, 1d6+1 piercing; Dagger +3, 1d4+1 piercing. Use one carried-item attack instead of Slam: STR13 gives +1 damage, +3 attack if item proficiency deliberately granted. Improvised crowbar uses +1 attack and1d4+1 bludgeoning without proficiency. No source Multiattack for paired blades. Retain Undead Fortitude. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-09.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-96d6b174fff6-0.png).

### top / Zombie Worker 01

**Observed:** one red hooked crowbar-like tool; shield not demonstrated; orange vest, yellow hardhat and blue trousers.

**Chosen items:** improvised crowbar (1d4 bludgeoning, no assumed proficiency).

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Use one carried-item attack instead of Slam: STR13 gives +1 damage, +3 attack if item proficiency deliberately granted. Improvised crowbar uses +1 attack and1d4+1 bludgeoning without proficiency. No source Multiattack for paired blades. Retain Undead Fortitude. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-09.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-3992d90bd2bd-0.png).

### top / Zombie Worker 02

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-10.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-222b920b55e5-0.png).

### top / Zombie Worker 03

**Observed:** empty hands; reaching/slapping attack; shield not demonstrated; torn clothing and exposed decayed body.

**Chosen items:** No carried weapon.

**Animations/VFX:** Attack1/2 overhead and cross-body swipes; Attack Run1 forward moving swipe. Carried object stays visible where present; no separate spell or elemental emission established.

**Ability opportunities:** Slam and ordinary grapple are useful melee presentations. Grapple costs an action and contested check; movement becomes0, without automatic restrained/paralyzed/poisoned. Do not give every palette variant a new condition.

**Rules revision:** Retain complete SRD5.1 Zombie block (source CR1/4, HP22) except these declared changes: choose Unarmored, AC8; remove unpictured source weapons/actions. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/top-zoom-10.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-top-06.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-456d797ac6de-0.png).

### barbarian / 1Ogre

**Observed:** one broad curved cleaver/blade; shield not demonstrated; bare torso, wrist guards and cloth trousers.

**Chosen items:** Scimitar.

**Animations/VFX:** Broad blade chops, running lunge and overhead chop. Pummel/Special2 show a gray circular ripple; CastSpell is a jump pose, not demonstrated spellcasting.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Ogre block (source CR2, HP59) except these declared changes: choose Unarmored, AC9; remove unpictured source weapons/actions. Scimitar +6, 1d6+4 slashing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0a7a42797e23-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0a7a42797e23-1.png).

### barbarian / 2Golem

**Observed:** one large broad dark sword/cleaver; shield not demonstrated; helmet, substantial metal-looking body and limb protection.

**Chosen items:** Greatsword.

**Animations/VFX:** Attack sweeps carry orange flame arcs. Pummel has a bright fire ring; Special1/2 broad white blade arcs. CastSpell jumps; QuickShot shows foot sparks, not a bow.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Plate, AC18; remove unpictured source weapons/actions. Greatsword +7, 3d6+4 slashing. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Remove Shield Bash. Visible armor and blade do not establish Stone Golem anatomy; use an armored Humanoid fighter proposal, not Construct traits inferred from the vendor name. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9f74ed954ba8-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-9f74ed954ba8-1.png).

### barbarian / 3Nomad

**Observed:** one axe; shield present; helmet, covered torso and limb guards.

**Chosen items:** Battleaxe, Shield.

**Animations/VFX:** Axe chops and shield guard; Kick contains an orange/white spinning ring, Special1 a broad white cleave. No spear thrust demonstrated.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Bandit Captain block (source CR2, HP65) except these declared changes: choose Scale mail and Shield, AC18; remove unpictured source weapons/actions. Battleaxe +4, 1d8+2 slashing. Explicit adapted Multiattack: two attacks with the one selected melee weapon; remove stock third Dagger attack. Keep source Parry +2. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-00f4f56fe5e4-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-00f4f56fe5e4-1.png).

### barbarian / 4Berserker

**Observed:** longsword and shortsword, both held; shield not demonstrated; bare torso, harness and trousers.

**Chosen items:** Longsword, Shortsword.

**Animations/VFX:** Both swords move in sweeping cuts and running leap. Kick has a fiery spinning ring; Special1/2 broad blade sweeps. CastSpell/QuickShot are sword clips.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Veteran block (source CR3, HP58) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Longsword +5, 1d8+3 slashing; Shortsword +5, 1d6+3 piercing. Keep source Multiattack: two Longsword attacks and one Shortsword attack while both drawn; no extra bonus attack. Longsword is not Light; ordinary two-weapon fighting is unavailable for this pairing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-30d52aed93bd-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-30d52aed93bd-1.png).

### barbarian / 5BarbArcher

**Observed:** one bow; arrows/quiver at back; shield not demonstrated; cloth and torso harness, exposed arms.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Veteran block (source CR3, HP58) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Longbow +3, 1d8+1 piercing; two hands, actual arrows; range150/600ft. Explicit adapted Multiattack: two Longbow attacks, replacing the source melee-only sequence. No hidden sword or shield. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ba5be1537799-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ba5be1537799-1.png).

### barbarian / 6Barbarian

**Observed:** one long-hafted axe/polearm with broad metal head; shield not demonstrated; bare torso and trousers.

**Chosen items:** Greataxe.

**Animations/VFX:** Melee cuts/chops, raised windup, lower swing, guard and running lunge. Equipment remains attached to the corresponding hands; no independent magical emission established in these samples.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Berserker block (source CR2, HP67) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Greataxe +5, 1d12+3 slashing. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-929c866ebe6d-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-929c866ebe6d-1.png).

### barbarian / 7BowMan

**Observed:** one bow; arrows/quiver at back; shield not demonstrated; covered torso, helmet and limb protection.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Veteran block (source CR3, HP58) except these declared changes: choose Half plate, AC16; remove unpictured source weapons/actions. Longbow +3, 1d8+1 piercing; two hands, actual arrows; range150/600ft. Explicit adapted Multiattack: two Longbow attacks, replacing the source melee-only sequence. No hidden sword or shield. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ee375a98cece-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ee375a98cece-1.png).

### barbarian / 8Witchdoctor

**Observed:** one straight sword; shield present; mask/helmet, red cloth and exposed limbs.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Green blade trails on Attack1–3 and running cut. Pummel shows a ring of green droplets/orbs; Special2 a broad green spinning sweep. Kick mixes orange/green sparks. User identifies poison VFX.

**Ability opportunities:** Poison Blade: on one sword hit per turn add 1d6 poison; target DC12 CON or poisoned until end of its next turn (repeat save there ends it). Authored addition; poisoned means disadvantage on attacks and ability checks, not saves. Green ring could present a separate recharge-5–6, action, 10-ft-radius burst, DC12 CON, 2d6 poison/half; it replaces Multiattack and affects allies too. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Bandit Captain block (source CR2, HP65) except these declared changes: choose Leather and Shield, AC16; remove unpictured source weapons/actions. Longsword +4, 1d8+2 slashing. Explicit adapted Multiattack: two attacks with the one selected melee weapon; remove stock third Dagger attack. Keep source Parry +2. Poison-style melee art uses the separate optional Poison Blade proposal, not Shillelagh (which cannot target a sword). Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6bbb248c8804-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6bbb248c8804-1.png).

### barbarian / 9Shaman

**Observed:** one long wooden staff with crooked/bulbous end; shield not demonstrated; bone-like exposed body, shoulder covering and waist cloth.

**Chosen items:** Quarterstaff.

**Animations/VFX:** Staff/hand flame streams, Attack3 yellow ring and red rune circle. Pummel is a large yellow sunburst; Special1 rising flame, Special2 red/yellow spinning rings.

**Ability opportunities:** Use stock Druid Produce Flame for a hand flame and Thunderwave for a short burst with its actual thunder damage/push. Optional fire sunburst: action, recharge5–6, creatures within10ft DC12 DEX, 2d6 fire/half; no persistent aura. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Druid block (source CR2, HP27) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Quarterstaff +2, 1d6 bludgeoning (1d8 two-handed). Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-barbarian-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eaa50dc377a1-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-eaa50dc377a1-1.png).

### character / 1Knight

**Observed:** one straight sword; shield present; metal body and limb protection, helmet.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Melee/Melee2 white sword sweeps; MeleeRun lunge and MeleeSpin circular swing. ShieldBlock and Pummel use shield guard/bash poses; Special1 overhead drop, Special2 held guard.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Knight block (source CR3, HP52) except these declared changes: choose Plate and Shield, AC20; remove unpictured source weapons/actions. Longsword +5, 1d8+3 slashing. Source Multiattack: two attacks with selected weapon; retain Brave, Leadership and Parry +2 (reaction, melee weapon in hand). Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4a7840a537f7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-4a7840a537f7-1.png).

### character / 2Archer

**Observed:** one bow; back quiver; shield not demonstrated; brown torso covering, exposed arms and legs.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release in attack variants, running/crouched firing pose and guarded bow-arm stance. Multiple clips give presentation choices, not extra attacks.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Veteran block (source CR3, HP58) except these declared changes: choose Unarmored, AC11; remove unpictured source weapons/actions. Longbow +3, 1d8+1 piercing; two hands, actual arrows; range150/600ft. Explicit adapted Multiattack: two Longbow attacks, replacing the source melee-only sequence. No hidden sword or shield. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-55c3ea42baa2-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-55c3ea42baa2-1.png).

### character / 3Wizard

**Observed:** empty hands in sampled poses; shield not demonstrated; brown robe, red belt.

**Chosen items:** No carried weapon.

**Animations/VFX:** Flame orbs in hands, stream/sweep and self-surrounding fire in Attack3. CastSpell downward flames; Special1 golden orbit/rune pattern; Special2 forward fire burst.

**Ability opportunities:** Stock Mage Fire Bolt/Fireball are usable fire presentation hooks with their actual attack/save, range and slots. Golden orbit can present Mage Armor or Shield without granting an aura.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a18e96e6af15-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a18e96e6af15-1.png).

### character / 4Paladin

**Observed:** one long thin haft with a pale rounded/spiked head; no sword blade resolved; shield present; gold metal-looking helmet, body and limb protection.

**Chosen items:** Mace, Shield.

**Animations/VFX:** Gold/white attack sweeps around the hafted weapon; shield-block and pummel poses. Special1 overhead slam with bright trail; Special2 ready stance. Attack FX obscures the head, so mace is a proposal.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Knight block (source CR3, HP52) except these declared changes: choose Plate and Shield, AC20; remove unpictured source weapons/actions. Mace +5, 1d6+3 bludgeoning. Source Multiattack: two attacks with selected weapon; retain Brave, Leadership and Parry +2 (reaction, melee weapon in hand). Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a882d92b8643-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-a882d92b8643-1.png).

### character / 5CamoArcher

**Observed:** one bow; back quiver; shield not demonstrated; green body covering and headgear.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release and running/crouched shots; large white branching/arrow-like streaks accompany Attack1–3 and Special1. QuickShot is a draw/release pose, not an extra action.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Assassin block (source CR8, HP78) except these declared changes: choose Studded leather (chosen grade), AC15; remove unpictured source weapons/actions. Longbow +6, 1d8+3 piercing; two hands, actual arrows; range150/600ft. Retain Assassinate, Evasion, poison resistance and once-per-turn4d6 Sneak Attack. Adapted Multiattack: two Longbow attacks, each with the source DC15 CON7d6 poison/half and actual poison supplies. This replaces the melee-only source Multiattack and requires CR recalculation. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0c8b280c3690-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-0c8b280c3690-1.png).

### character / 6Mage

**Observed:** empty hands in sampled poses; shield not demonstrated; blue robe.

**Chosen items:** No carried weapon.

**Animations/VFX:** Cyan/blue hand orbs, streams, body-surrounding surge and curved trails; Special1 broad white/cyan orbit; Special2 forward burst. Cold versus force remains a rules choice.

**Ability opportunities:** Stock Mage Ice Storm can present cyan cold fragments but retains cold+bludgeoning damage and its area/difficult-terrain rules. Shield can use the orbit; no automatic freeze or paralysis.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-00.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-83587dd3eae8-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-83587dd3eae8-1.png).

### character / 7DeathKnight

**Observed:** one straight sword; shield present; dark metal helmet, body and limb protection.

**Chosen items:** Longsword, Shield.

**Animations/VFX:** Purple weapon arcs, running cut and spinning sweep. ShieldBlockStart/Pummel pulse purple around shield; Special1 descending cut, Special2 charged guard. Color does not establish undead identity.

**Ability opportunities:** Block can present ordinary Dodge or a source Parry where actually available. Sweeps can present source Multiattack. Optional cleave: action, recharge5–6, one melee attack each against up to2 adjacent creatures; replaces Multiattack, no free movement or automatic hit. Recalculate CR.

**Rules revision:** Retain complete SRD5.1 Gladiator block (source CR5, HP112) except these declared changes: choose Plate and Shield, AC20; remove unpictured source weapons/actions. Longsword +7, 2d8+4 slashing. Retain three selected melee attacks (or source two ranged if equipped). Brute adds one weapon die; retain Parry +3 only for a held melee weapon. Shield Bash +7, 2d4+4 bludgeoning, DC15 STR prone for Medium-or-smaller remains. Shield don/doff costs one action; it does not coexist with a two-handed attack. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ad8defebd1f2-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-ad8defebd1f2-1.png).

### character / 8DarkLord

**Observed:** empty hands in sampled poses; shield not demonstrated; dark robe and belt.

**Chosen items:** No carried weapon.

**Animations/VFX:** Magenta/white hand streams, body-surrounding surge and curved trails; Special1 orbit around body, Special2 forward burst. No held staff and no demonstrated invisibility.

**Ability opportunities:** Stock Mage Magic Missile and Shield can use magenta projectile/ward presentation while retaining force damage and reaction cost. Hold Person requires its legal humanoid target, WIS save, slots and concentration.

**Rules revision:** Retain complete SRD5.1 Mage block (source CR6, HP40) except these declared changes: choose Unarmored, AC12; remove unpictured source weapons/actions. Retain full source spell list, spell slots, casting ability/DC, concentration and components; remove weapon action only where no item is chosen. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6fab27b36b7c-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-6fab27b36b7c-1.png).

### character / 9Longbow

**Observed:** one bow; back quiver; shield not demonstrated; pale metal-looking body and limb protection.

**Chosen items:** Longbow.

**Animations/VFX:** Bow draw/release and crouched/running shots, with blue sparks around bow/body. Special1 shows blue charge; Special2 ready bow. No electrical condition follows from blue pixels.

**Ability opportunities:** Use declared bow attacks and normal movement; QuickShot/running clips do not waive loading, ammunition or action costs. Optional charged shot must replace a normal attack, with explicit damage/save and a new CR review.

**Rules revision:** Retain complete SRD5.1 Veteran block (source CR3, HP58) except these declared changes: choose Half plate, AC16; remove unpictured source weapons/actions. Longbow +3, 1d8+1 piercing; two hands, actual arrows; range150/600ft. Explicit adapted Multiattack: two Longbow attacks, replacing the source melee-only sequence. No hidden sword or shield. Changed CR remains provisional; optional ability ideas are not already included.

**Evidence:** [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/animation-character-01.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-069933319fa7-0.png), [view](/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/pack-study-20260930/srd-first/illustration-comparison/root-gear-review-20261001/actions-069933319fa7-1.png).

