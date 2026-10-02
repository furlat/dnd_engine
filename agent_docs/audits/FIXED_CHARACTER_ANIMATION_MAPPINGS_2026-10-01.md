# Fixed-character animation mappings from inspected source sequences

This extends the [renderer integration handoff](FIXED_CHARACTER_RENDERER_INTEGRATION_2026-10-01.md) with concrete animation selections. The earlier catalog was geometry and filename discovery, not an animation mapping. The human explicitly requested the deeper asset pass. Root performed it personally; no Luna/delegated assessment was used. Animals and modern excluded variants remain excluded. Production implementation and dispatch remain outside this task.

## Evidence and exact coverage

The [per-character JSON](FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.json) contains 150 identities, 600 basic selections, 422 primary combat selections and 12 focused extra selections. Every selected member has exact ZIP path, decoded square cell dimensions, actual frame count, SHA-256 and available companion sheets. This is preparation data, not an accepted runtime schema or imported rig.

Root visually inspected every frame of primary combat, Run, TakeDamage and selected Die in direction row 0; all eight first-frame Idle poses were inspected. Every frame of basic and combat body sheets was checked computationally in all eight rows for meaningful alpha (>32). None of the selected body cells was empty at that threshold. This does not prove every facing's weapon/FX timing, cropping, sockets or contact. Detailed primary combat strips include rows 0 and 2, but row 2 is evidence available for follow-up, not a certified complete visual pass. Idle rows for 39 characters additionally byte-match all eight individually named vendor direction frames. For the other 111, E, SE, S, SW, W, NW, N, NE is a visual candidate order, not source-name proof.

Offline review: `.runtime/pack-study-20260930/integration-preparation/index.html`. The page is searchable by pack, character and equipment, with every mapping, full-frame evidence and unmapped-action list. Motion/basic generation scripts and source-inspection indexes are preserved beside it. Source images remain derived study artifacts; no production artwork was moved or registered.

Validation passed for all 150 identities and 1,034 selections: every selected
ZIP member and evidence image exists, every visible window fits its actual
frame count, and every runtime-approval flag remains false. An independent
pass re-decoded and checked source hashes/dimensions for 96 selections.
`mapping-validation.json` beside the review records these checks. Runtime
renderer tests were not needed for this source-data/documentation change.

## Findings that change bindings

- Goblin 03/09 and Orc 05 Attack 1 visibly release around frames 10–12; bow-equipped devils release at 8–9. Standard HD bows use a draw/release motion around 6–10, still needing precise synchronization. Their other Attack clips include melee bow swings, held aiming or jumping shots. Do not bind every numbered Attack to the same ranged recipe.
- Shooter and Sniper Attack1/2 have a muzzle plume at frame 10; Attack3 emits at frame 7. The visual firearm requires deliberate SRD-compatible authoring; a bow profile does not fit merely because both are ranged.
- Undead Warrior Attack2 is the clearest horizontal spear thrust. Imp 6 Attack1 is a spear thrust but Attack3 is kick-like. Enemy Guard has broad pole sweeps, and Attack4 combines an extended pole with a kick. A clean piercing-contact mapping for Guard remains unresolved.
- Hammer and Crusader Attack3 are preferred single heavy strikes; their first clips include broader spinning motions. Berserker's paired swords, repeated arcs and other spins need an authored ability/timeline, not invented extra native hits.
- Witchdoctor is a sword/shield combatant with green charge/poison-like emission. Attack1 and Attack2 support poisoned sword variants. Attack3 raises the shield; CastSpell is acrobatic sword/shield motion. Pummel contains green symbol/ring effects and Special2 has extensive green spinning arcs. None of these names establishes poison rules or spell delivery.
- Shaman's Pummel has a large circular fire sigil and Special2 has repeated fire rings. CastSpell is an acrobatic staff move, while Attack1/2 are clearer orb casting candidates. Knight Pummel is a shield/sword flourish, not a proven shield bash. Archer QuickShot holds aim with small hand/string motion; retain Attack1 as the clearer shot candidate.
- Goblin 11/12 TakeDamage is **six frames**, not fifteen. Rider and quadruped collapse in the same baked Die sequence. Independent mount/rider damage, death and dismount require a separate state/transition decision.
- Decay 01/04 remain severed-leg crawlers in Idle and Run. Map Run to crawl locomotion; do not manufacture a Prone condition from anatomy. Their selected Die becomes a pale bone/debris heap. HD zombie selected deaths include substantial bloody head/body effects.
- Shaman, Undead Wizard, Witchdoctor, Commander, Arcane Elemental, DeathKnight and Longbow have colored effects in selected locomotion and/or reaction/death clips. Visual effects during movement or taking damage are not native attack triggers. Alternative movement/layer authoring is required where a recurring emission contradicts the character's intended presentation.

## Layer evidence is part of each mapping

Knight's With shadow Melee contains white weapon trails that the Shadowless export removes. MeleeSpin has the same distinction. Witchdoctor and Shaman paired Pummel/Special2/CastSpell also show larger symbols, rings or arcs in combined exports. Shadowless can preserve some baked magic while omitting substantial surrounding effects. Therefore choosing it is not simply removing ground shadow. Preserve exact paired sources and decide explicitly which presentation is retained; do not assume pixel subtraction gives independent, correctly composited FX.

Orc/Goblin and Devil families supply independent Effects members matched by exact action and geometry; their primary inspection contact sheets composite those with the separated body. HD paired body/combined exports may lack an independent equivalent. Companion availability is recorded, not proof of layer interchangeability. The offline catalog now recognizes the Top zombie directory `Zombies with shadow` as combined instead of treating it as a second shadowless body.

## Production pickup sequence and review roles

1. Consume the selections as authored semantic evidence, preserving exact source-member identity and hashes. Keep unmapped optional clips out of automatic binding.
2. Inspect remaining facings for each chosen clip and asymmetric loadout, choose body/FX/shadow sources and measure support/torso anchors and any contact/projectile sockets. Preserve common world registration during cropping and scale.
3. Author FPS deliberately. Establish native contact, release, recovery and settlement against actual action timelines. The JSON records visible active windows, **not certified hit/release frames**; all exact markers remain null. Vendor numbers such as Idle12/16Bit are not frame count or FPS evidence.
4. Apply character loadout/action constraints during explicit native content authoring. Keep canonical SRD 5.1 monsters distinguishable from variants; fixed humanoid/skeleton art is for specials while Goblin/Orc/Devil/Zombie families also cover base monsters. Do not hide already legal recorded actions at playback.
5. Integrate through the unified family projection described in the architecture handoff. Prove modular and fixed rigs retain equivalent event replay and world composition behavior.
6. **Anti-slop review:** reject name-based semantics, unsupported timing claims, erased effects, generic weak-NPC substitutions, and 'all animations reviewed' claims beyond the evidence scope. **Anti-OOP review:** retain typed data and ECS/system composition; no per-pack entity classes, exception dispatch ladder, late imports, dynamic attribute/type checks or parallel renderer stacks. Root performed these review roles for this preparation; production repeats them on implementation.

Remaining deliberate holds: FPS, support/torso/socket calibration, all-facing action review, event synchronization, combined-export FX policy, mount transitions, and complete optional/condition-state coverage. Zero rigs are runtime approved by this document. No production thread was contacted.

## Per-character primary selections

Windows below are zero-based visible motion/FX windows in row 0, not native contact markers. Basic and alternate mappings, exact source paths, independent FX availability, constraints and further clips are in JSON and the review page.

| Pack / character | Inspected equipment | Primary source → semantic candidate | Visible window |
| --- | --- | --- | --- |
| orcs_goblins / Goblin 01 | one axe | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 02 | empty hands | Attack 1 → cast.channel | [3, 12] |
| orcs_goblins / Goblin 03 | one bow; back quiver | Attack 1 → bow.shot | [10, 12] |
| orcs_goblins / Goblin 09 | one bow; back quiver | Attack 1 → bow.shot | [10, 12] |
| orcs_goblins / Goblin 04 | one curved sword | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 05 | one long pointed spear | Attack 1 → weapon.pole_thrust | [4, 7] |
| orcs_goblins / Goblin 10 | one three-pronged trident | Attack 1 → weapon.pole_thrust | [4, 7] |
| orcs_goblins / Goblin 06 | one sword | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 07 | two independent short blades, one per hand | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 13 | one wooden club | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 08 | one crooked wooden staff | Attack 1 → cast.channel | [3, 12] |
| orcs_goblins / Goblin 16 | one sword | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 17 | one curved sword and one bow held together | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 11 | one axe; mounted on tan quadruped | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 12 | one axe; mounted on gray quadruped | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 14 | one spiked mace/club | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Goblin 15 | two axes, one in each hand | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 01 | one curved blade used in melee swings; no bow draw/release demonstrated | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 02 | one broad axe | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 03 | one axe | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 09 | one short broad sword/knife | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 11 | one axe | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 04 | one wooden club | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 05 | one bow; back quiver | Attack 1 → bow.shot | [10, 12] |
| orcs_goblins / Orc 06 | one long staff/pole | Attack 1 → cast.channel | [3, 12] |
| orcs_goblins / Orc 07 | empty hands | Attack 1 → cast.channel | [3, 12] |
| orcs_goblins / Orc 08 | one curved sword | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 10 | one spiked mace and one axe held together | Attack 1 → weapon.melee_sweep | [6, 9] |
| orcs_goblins / Orc 12 | two long dark curved blades moved separately in melee swings; no bow draw demonstrated | Attack 1 → weapon.melee_sweep | [6, 9] |
| demons / Demon Beast 1 | paired forearm blade-like appendages | Attack 1 → natural.strike | [5, 7] |
| demons / Demon Spawn 6 | one bow | Attack 1 → bow.shot | [8, 9] |
| demons / Demon Beast 2 | paired forearm blade-like appendages | Attack 1 → natural.strike | [5, 7] |
| demons / Demon Spawn 12 | one short blade | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Beast 3 | long finger/claw hands, no held weapon | Attack 1 → natural.strike | [5, 7] |
| demons / Demon Beast 4 | claw hands, no held weapon | Attack 1 → natural.strike | [5, 7] |
| demons / Demon Elite 3 | one large dark blade-like form in hand | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Beast 5 | claw hands, no held weapon | Attack 1 → natural.strike | [5, 7] |
| demons / Demon Elite 1 | two curved glowing blades, one per hand | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Elite 2 | one large double-headed axe | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 7 | one dark bow | Attack 1 → bow.shot | [8, 9] |
| demons / Demon Elite 4 | one long three-pronged trident | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Elite 5 | one straight broad sword | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Elite 6 | one broad crescent-headed axe | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon spawn 1 | one short staff/wand with glowing tip | Attack 1 → cast.channel | [4, 9] |
| demons / Demon Spawn 8 | one long orb-tipped staff | Attack 1 → cast.channel | [4, 9] |
| demons / Demon Spawn 10 | one bow | Attack 1 → bow.shot | [8, 9] |
| demons / Demon Spawn 13 | one axe and one straight sword, both held | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 2 | one spiked mace | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 5 | two curved swords, one per hand | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 3 | one scythe-like long pole with curved blade | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 4 | one broad straight sword | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 9 | one curved sword | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Demon Spawn 11 | one orb-tipped short staff/wand | Attack 1 → cast.channel | [4, 9] |
| demons / Imp 1 | one axe | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 2 | one wooden club | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 3 | one curved sword | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 4 | one short curved blade | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 5 | empty hands | Attack 1 → natural.strike | [5, 7] |
| demons / Imp 7 | one bow | Attack 1 → bow.shot | [8, 9] |
| demons / Imp 10 | two blade-like hand weapons | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 6 | one pointed spear/polearm | Attack 1 → weapon.spear_thrust | [4, 7] |
| demons / Imp 8 | one curved sword; shield | Attack 1 → weapon.melee_sweep | [5, 7] |
| demons / Imp 9 | one long wooden staff and one short blade, both held | Attack 1 → cast.channel | [4, 9] |
| undead / 1Brute | one large straight sword | Attack1 → weapon.cleave | [8, 10] |
| undead / 2DeathLord | one flaming straight sword and large triangular shield | Attack1 → weapon.sword_cut | [8, 10] |
| undead / 3DarkKnight | one straight sword | Attack1 → weapon.sword_cut | [7, 9] |
| undead / 4Berserker | one long-hafted axe | Attack1 → weapon.axe_cut | [7, 8] |
| undead / 5Archer | one bow; back quiver | Attack1 → bow.shot | [6, 10] |
| undead / 6Warrior | one pointed spear; shield | Attack2 → weapon.spear_thrust | [7, 10] |
| undead / 7DarkArcher | one bow; back quiver | Attack1 → bow.shot | [6, 10] |
| undead / 8Necromancer | empty hands in sampled poses | Attack1 → cast.orb | [6, 9] |
| undead / 9Wizard | empty hands; branching head antlers, no carried staff | Attack1 → cast.orb | [6, 9] |
| enemy / 1Hammer | one large two-handed hammer | Attack3 → weapon.hammer_slam | [7, 10] |
| enemy / 2Shooter | one long firearm-like barrel; back canister | Attack1 → firearm.shot | [10, 10] |
| enemy / 3Footsoldier | one straight sword; shield | Attack1 → weapon.sword_thrust | [5, 9] |
| enemy / 4Assassin | two straight short blades, one in each hand | Attack1 → weapon.paired_blade_cut | [7, 9] |
| enemy / 5Bruiser | fists with large gauntlets | Attack1 → unarmed.punch | [7, 9] |
| enemy / 6Crusader | one large two-handed straight sword | Attack3 → weapon.sword_chop | [8, 12] |
| enemy / 7Sniper | one long firearm-like barrel | Attack1 → firearm.shot | [10, 10] |
| enemy / 8Brawler | fists with gloves/gauntlets | Attack1 → unarmed.punch | [7, 9] |
| enemy / 9Commander | empty hands in sampled poses | Attack1 → cast.channel | [4, 11] |
| enemy / 10Caster | one long wooden staff | Attack1 → cast.staff_orb | [5, 8] |
| enemy / 11Arcane elemental | empty hands; particle-covered humanoid outline | Attack1 → cast.orb | [6, 9] |
| enemy / 12Guard | one long pointed spear/polearm | Attack1 → weapon.pole_sweep | [5, 10] |
| hdz / ZombieFemale1 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale2 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale3 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale4 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale5 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale6 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieFemale7 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieHulk1 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieHulk2 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale1 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale2 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale3 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale4 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale5 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale6 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale7 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale8 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMale9 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMonster1 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMonster2 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| hdz / ZombieMonster3 | empty hands; reaching/slapping attack | Attack1 → natural.slam | [6, 8] |
| top / Zombie 01 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 02 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 03 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 04 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 05 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 06 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 07 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 08 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 09 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie 10 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Decay 01 | no held weapon; low crawling/reaching body | Melee Uppercut → natural.crawl_uppercut | [3, 7] |
| top / Zombie Decay 02 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Decay 03 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Decay 04 | no held weapon; low crawling/reaching body | Melee Uppercut → natural.crawl_uppercut | [3, 7] |
| top / Zombie Decay 05 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 01 | one straight sword | Attack 1 → weapon.zombie_swing | [5, 7] |
| top / Zombie Swamp 02 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 03 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 04 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 05 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 06 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 07 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 08 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Swamp 09 | two short blades, one broad and one narrow | Attack 1 → weapon.zombie_swing | [5, 7] |
| top / Zombie Worker 01 | one red hooked crowbar-like tool | Attack 1 → weapon.zombie_swing | [5, 7] |
| top / Zombie Worker 02 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| top / Zombie Worker 03 | empty hands; reaching/slapping attack | Attack 1 → natural.slam | [5, 7] |
| barbarian / 1Ogre | one broad curved cleaver/blade | Attack1 → weapon.cleaver_cut | [5, 8] |
| barbarian / 2Golem | one large broad dark sword/cleaver | Attack1 → weapon.fire_cleave | [7, 10] |
| barbarian / 3Nomad | one axe; shield | Attack1 → weapon.axe_cut | [6, 8] |
| barbarian / 4Berserker | longsword and shortsword, both held | Attack1 → weapon.paired_sword_cut | [7, 10] |
| barbarian / 5BarbArcher | one bow; arrows/quiver at back | Attack1 → bow.shot | [6, 10] |
| barbarian / 6Barbarian | one long-hafted axe/polearm with broad metal head | Attack1 → weapon.axe_cut | [5, 8] |
| barbarian / 7BowMan | one bow; arrows/quiver at back | Attack1 → bow.shot | [6, 10] |
| barbarian / 8Witchdoctor | one straight sword; shield | Attack1 → weapon.poison_sword_cut | [7, 9] |
| barbarian / 9Shaman | one long wooden staff with crooked/bulbous end | Attack1 → cast.orb | [6, 9] |
| character / 1Knight | one straight sword; shield | Melee → weapon.sword_cut | [5, 9] |
| character / 2Archer | one bow; back quiver | Attack1 → bow.shot | [6, 10] |
| character / 3Wizard | empty hands in sampled poses | Attack1 → cast.orb | [6, 9] |
| character / 4Paladin | one long thin haft with a pale rounded/spiked head; no sword blade resolved; shield | Melee → weapon.hafted_weapon_cut | [3, 8] |
| character / 5CamoArcher | one bow; back quiver | Attack1 → bow.shot | [6, 10] |
| character / 6Mage | empty hands in sampled poses | Attack1 → cast.channel | [5, 9] |
| character / 7DeathKnight | one straight sword; shield | Melee → weapon.sword_cut | [2, 8] |
| character / 8DarkLord | empty hands in sampled poses | Attack1 → cast.orb | [6, 9] |
| character / 9Longbow | one bow; back quiver | Attack1 → bow.shot | [6, 10] |
