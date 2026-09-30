# Independent anti-slop review: art-led NPC roster

**Historical review snapshot:** this approval applies to the earlier art/composition
study. It does not approve the subsequent SRD-first rematch. The
[reconciled synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md) identifies the
current tables and fresh review records.

Date: 30 September 2026  
Review target: [art-led NPC roster synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md), its five focused completion supplements, and the three original pack studies.  
Review type: independent content/evidence review; no code, tests, imports, or production data changed.

## Status

**Approved at the requested study/design scope.** I completed the focused reread after the armor corrections. The previously missing fixed-art armor rows now name actual worn possessions or explicitly select passive intrinsic defense. The 259-row design and its evidence limits meet the art-led proposal objective. This approval does not certify implementation readiness, mechanical balance, art binding compatibility, or production support, and does not approve an implementation plan.

The row arithmetic and joins are coherent: Orc/Goblin/Demon 65; Undead/Enemy/HD Zombie/Top-down Zombie 100; Animals/Barbarian/Character 73; dinosaurs 21; total 259. The source matrix's nine ZIP family totals 238 and the dinosaur RAR adds 21. The master identifies entries by archive plus literal family name, which distinguishes repeated names such as Crocodile in the animal and dinosaur packs. The source lists are not additional variant counts for paired shadow sheets, alternate directions, effects, or duplicate archives.

## Findings

### Resolved — synthesis completion ledger

The final synthesis links the 65 Orc/Demon, 100 Undead/Enemy, and 94 Animals/Dinosaurs/fixed-humanoid tables and records the 259 total. Its completion record includes both independent study/design approvals and distinguishes them from future implementation work. It also clearly says the completion tables take precedence over earlier source studies where proposals differ.

### Resolved — firearm proposals

The revised Undead/Enemy supplement selects one shared design: a two-handed carried long gun firing a physical piercing projectile through the existing ranged weapon Attack pipeline, then distinguishes carbine, precision rifle, and service-rifle roles. It names the new item/action content required and leaves exact statistics, reloads, ammunition, balance, and playability checks for future authoring. The synthesis correctly says these are completed design concepts with an implementation gap. This satisfies the study objective without pretending that a firearm system exists.

### Resolved — concrete kits and actions

The Undead/Enemy supplement adds a selected-design table that resolves prior conditional skeletal loadouts, spell choices, the firearm concept, Zombie Fireman axe, and radioactive-discharge proposal. The Orc/Demon completion explicitly states that each row selects a concrete item/action even where art leaves subtype uncertain; its Dretch-derived entries remove incompatible intrinsic items and Multiattack. The animal/dinosaur completion selects an attack for each row, five half-plate possession proposals for the visibly armored dinosaurs, and explicit spells for the fixed humanoid casters. These authored choices are separated from observed pixels.

### Resolved — Select native armor for clearly armored fixed-art identities

The Orc/Demon report now assigns `armor.plate` to Goblin 15, Orc 12, Demon Elite 2/5/6 and Demon Spawn 7, while explicitly replacing competing inherited armor grants. It treats Demon Beast 3 as no worn garment, with authored passive intrinsic AC and armor grants stripped. The Undead supplement assigns `armor.half_plate` to `3DarkKnight` and retains `armor.armor_scraps` for DeathLord. The fixed Character report assigns worn `armor.half_plate` to Knight, Paladin and DeathKnight, marks the subtype as a conservative content choice, and preserves baked pixels while suppressing only duplicate overlays. Those choices resolve the finding without equating every costume with armor. Their stated later wearability and AC-composition checks remain appropriate implementation limits.

### P2 — Keep melee-action labels and natural-attack proposals semantically exact

The native audit establishes `NaturalAttack` as an action template whose stats/range need authored facts; Dretch's intrinsic Bite/Claws are item grants, and its Multiattack is separate. Where an empty-handed humanoid uses the engine's ordinary unarmed attack, say so. Where anatomy supplies a claw/fang/horn proposal, name `NaturalAttack` and make clear it is a content choice. Do not let “unarmed” imply claws or count Dretch intrinsic attacks after they are explicitly removed. The current Dretch guidance is otherwise sound and warns against treating Dretch as a universal demon.

### P2 — Preserve bounded source and timing claims

The supplements distinguish sampled motion from native semantics. Undead/Enemy action strips are sampled in one facing; the dinosaur and animal tables describe chosen 15-frame East-facing sequences; source archives declare no FPS/contact markers. Attack/Spit/Howl/CastSpell labels and effects do not prove hit timing, spell, damage type, fear, flight, poison, or Multiattack. Retain those limits in the synthesis.

The dinosaur clarification now treats Toxic Spit as a proposed, unverified content candidate. It states that `NaturalAttack`'s default `MELEE_MAIN` proxy flows into outcome/event data, while discovery, ranged execution/delivery/presentation, and slot-sensitive compatibility remain unverified. It makes no executable-support claim. The tested Grey Wolf and fixed Skeleton Archer shadow recompositions establish exact RGBA parity for only the eight listed clip pairs, not their full packs.

## Supported conclusions

- The 259 count is supported by the nine ZIP family totals plus the 21-variant dinosaur RAR; the completion tables cover 65 + 100 + 94 art identities.
- The modular humanoid and modular `NakedBody2` skeleton routes remain distinct from the fixed Undead pack. `creature.skeleton_warrior` maps to the modular route, while fixed Skeleton Archer has its own rig.
- The canonical Goblin remains unchanged; bow-only art variants remove the canonical Goblin Archer's scimitar and offhand dagger. The completion report correctly records its actual shortbow + scimitar + offhand dagger kit.
- The studies distinguish real carried item definitions from natural attacks, and distinguish both from baked visual equipment/effects.
- Mounted Goblin composites remain two proposed identities with explicit limitations: no existing mount composer and no independent movement, targeting, dismount, or death presentation.
- The recovery constraints are preserved: stable native identity and permitted appearance/equipment/action facts select frontend presentation; source filenames/media readiness do not become native rules; historical rendering uses retained causal lineages rather than live state.
- No implementation, production import, new NPC framework, or global legacy cleanup is authorized by this study.

## Final disposition

The roster is approved at the requested study/design scope. Its traceable proposals cover all 259 fixed art variants and distinguish observed art from selected game mechanics, native foundations from custom content, and current support from future authoring. Balance, firearm implementation, Toxic Spit compatibility, mounted-rider capability, armor wearability/AC composition, production binding, and per-rig timing markers remain later design or implementation work. No anti-OOP/ECS finding is made by this review.
