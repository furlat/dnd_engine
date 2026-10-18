# Independent anti-slop review

2026-10-18. Reviewed the proposed remaining-nonanimal authoring plan, the full
180-row CSV and copied zombie triage in this worktree at base
`454fae33fbacf55d7b77bf94feff250175d3dccf`. Read-only source inspection and
document checks; no gameplay checks or visual playback were run.

Status: **planning approved after correction and independent rereview**. No
remaining anti-slop blocker was found in the revised plan. The explicit Phase 0
kit decisions and eight clothing holds remain decisions, not implemented or
reviewer-approved character selections.

## Resolved findings from the first pass

1. **Account for the retained Gladiator Shield Bash.** The higher-tier Enemy
   draft retains it in the Gladiator foundation and explicitly on
   `enemy / 3Footsoldier` (Gateplate): +7, 2d4+4 Bludgeoning and DC15 Strength
   or Prone for a Medium-or-smaller target. No Shield Bash owner was found in
   current `dnd` source. G05 replaces the custom Shield Escort signature with
   Protection; it does not explicitly delete this retained foundation action.
   The revised plan adds A10 to its capability list, sequence, acceptance and
   Footsoldier inventory row. Larger targets still take bash damage; only the
   prone rider has the size limit. Actual shield ownership and Multiattack
   placement are explicit. Other shield-bearing Gladiator adaptations are
   checked during kit completion rather than receiving it automatically.

2. **Name the conflicting trained-unarmed proposals.** The higher-tier draft's
   P foundation removes Brute and Parry, selects Martial Guard (10+DEX+CON)
   and three Fist attacks at 2d6+4. Its older table rows still describe 3d4+4
   strikes as an extension of Brute. The image-only review repeats the older
   3d4+4 proposals, with Half plate AC17 for Bruiser and unarmored AC12 for
   Brawler. The revised plan names the conflict and proposes the coherent P
   foundation for explicit human disposition before adoption. Conditional A11
   identifies existing unarmed data and ArmorClassFormulaCandidate ownership
   and the no-shield eligibility qualification; it adds no PC class grant or
   AC subsystem. Brute is not stacked onto trained Fist dice. Native Shove and
   deferred Grapple remain later controlling decisions.

## Resolved source and timing improvements

- The source section now links the authored Devil and higher-tier Enemy drafts
  for their numeric foundations rather than relying on the shorter cards.
- Phase 3 now describes playback rates/contact clocks as authored timing choices
  calibrated from inspected frames and explicitly states that PNG sheets do not
  establish vendor FPS. Generic gallery 12 FPS remains distinct from gameplay.

## Scope and accounting findings

- The CSV has 180 unique `(pack, source_variant)` rows and preserves all 150
  original card ordinals exactly once. All referenced card/image-review files
  and line positions resolve. All relative plan links resolve.
- Counts are correct: 102 nonzombie candidates plus 46 visually adaptable
  zombies, eight clothing holds, 24 modern exclusions; 123 candidates lack an
  individual fixed mapping, with five additional older mapped kits to reconcile.
- All seven newly considered Radioactive rows require cards and do not acquire
  poison/radiation/acid mechanics. The triage's three-facing idle-only limits
  and lack of final human admission are correctly retained.
- Current Goblins, riders/Pistol, existing canonical demon identities and
  Skeleton Archer are preserved pending explicit source-row reconciliation.
  The retired G78 Storm Arrow is correctly replaced with an ordinary bow kit.
- The plan correctly preserves current spell/item implementations rather than
  reviving old task modules, the held-light Produce Flame contract, ammunition,
  focus/tool/mount simulation, Grapple, legendary work or color-derived powers.
- Full roster delivery remains explicit; representative mechanics checks do not
  replace it. Mechanics, creature composition and current-client presentation
  have separate completion evidence. No bulk asset reimport, manifest-recovery
  prerequisite, new framework, arbitrary speed target or checksum process is
  added.

This review qualifies planning scope and source consistency only. Its current
approval does not certify implementation, balance, exhaustive runtime behavior
or current Godot playback. The final rereview checked the revised capability,
ownership, Phase 0/1, presentation, acceptance and review sections, the updated
Footsoldier/Bruiser/Brawler inventory rows, the current unarmed/AC owner, and
all revised relative links. No gameplay tests were run for this document-only
delivery.

## Implementation scope rereview — mechanics branch

2026-10-18. This addendum reviews implementation on
`codex/npc-abilities-mechanics`, integration base `5779fecb60f0d65e5b9c70070ed190a17e0f930b`.
It is separate from the planning approval above. The current human request
selects shared abilities and mechanics first, with particular attention to
correct state ownership and unnecessary event publication. It does not select
bulk character recipes, artwork, client work or the unresolved trained-unarmed
kit. This reviewer independently inspected the other implementers' damage,
defense and coating changes. This reviewer implemented Help, Assassinate and
Shield Bash; their tests below are verification evidence, not a claim of
independent review of the reviewer's own code.

**Result: the inspected implementation stays within the selected mechanics
scope, with the explicit limits below.**

- Evasion and spell resistance resolve in the existing health preview and
  affinity owner. Incoming save ability/result/fraction and packet spell origin
  are carried directly; neither trait reconstructs a save or casts a second
  damage executor. Spell resistance and matching type resistance halve once;
  immunity remains authoritative. Inspection of DEX/half-damage delivery sites
  found the remaining sites without save metadata were object recipients, for
  which creature Evasion is inapplicable. Persistent spell surfaces retain their
  spell origin rather than inferring it from their damage type or caster name.
- Fortitude uses the existing pre-commit incoming packet, explicit critical
  provenance and the same post-defense preview used by damage commitment.
  Brute uses the actual weapon die. Parry, Leadership, silence/hearing and
  spell-reaction costs remain in their existing feature, sensory, area and
  resource owners. No creature subclass, separate action bus, NPC rules DSL,
  world scan on each hit or new public event family was introduced.
- Assassin poison is a finite owned dose applied to a real weapon through the
  existing coating owner: DC15 Constitution, 7d6 Poison, half on success,
  separately saved and without critical doubling or a Poisoned condition.
  Its default ten-round coating duration reuses the current native coating
  adaptation. That default does not settle each future Assassin's poison
  possession count, lifetime choice or complete kit, and supplies no unlimited
  poison or ammunition subsystem. The striking item UUID selects its handler;
  unrelated weapons do not search inventories or previous events for a coating.
- Assassinate reads the exact encounter's opening-turn and live surprise facts;
  first-turn start and first-turn completion have distinct meanings. Sneak
  Attack now receives the final attack's advantage directly on its existing
  damage-roll fact rather than retrieving a parent event and probing attributes.
  Help uses an exact enemy/ally selection and owned temporary grant; previews
  publish no events, a rolled miss consumes the grant, and the existing
  restorative AllyHelp remains available. These are bounded owner reads and
  normal effect/removal events, not additional per-trait publication streams.
- Shield Bash retains the actual equipped Shield UUID and uses the native Attack
  roll/damage pipeline. It does not convert every shield into a Weapon or fake
  an intrinsic attack. Its 2d4+4 baseline excludes an extra Brute die; only the
  Prone rider is size-gated. Existing Multiattack substitutes at most one hit
  within its three-attack/action budget. Native switch-on-attack stance behavior
  is preserved. The current AI target-effect profile cannot express the size
  gate, so this size-limited rider is conservatively omitted from that profile;
  ordinary damage discovery and gameplay size checks are exercised. This is an
  explicit limitation, not a new AI schema project.
- Conditional A11 remains held for the human's trained-Fist/Martial Guard kit
  decision. Existing creature identities, visual holds, excluded modern zombies,
  roster accounting, kit reconciliation and presentation work remain outside
  this implementation approval. No provisional CR or roster/client completion
  is certified here.

Reviewer-run verification: 90 tests passed in 3.63s across the new Help,
Assassinate and Shield Bash scenarios plus existing Sneak Attack, natural-source,
window-access, inventory/equipment, spell-damage and object-attack regressions.
The creation-declaration suite plus Shield Bash scenarios passed 21 tests in
5.28s after declaring HelpAttack in the summon forms that use standard action
composition. These checks use native registered actions, authoritative state
and public event evidence; they are not exhaustive performance or client tests.

The coordinator separately compared a clean source archive of `5779fecb` in the
same environment. Existing failures were reproduced there: IceStormTerrain's
environment-step expiry; four dependency-boundary checks involving absent
legacy game/server modules and existing safe-leaf imports; and the empty-position
Fireball discovery case. Those failures are recorded as baseline limitations,
not silently fixed or represented as passing by this branch. The implementation
ledger owns the exact batch commands and final aggregate results.

### Independent final reaction/source-origin rereview

Reviewed the plan-adherence agent's final changes to `reaction_costs.py` and the
four origin-carrying lines in `environmental_conditions.py`, together with their
native gameplay tests. No correctness, ownership or publication blocker was
found in these additions. Reaction selection reads the actor's exact learned
spell sources and owned daily resource; commitment rechecks that source and
atomically pays the existing reaction/resource costs. An exhausted finite source
cannot use unrelated slots, while an actually learned class source can supply
the ordinary fallback. Refusal/source loss admits no payment. These reads stay
within the relevant actor/spell records and introduce no history replay, world
scan or new event family. Fire and electrified-water packets now carry their
surface owner's existing origin into both typed damage and incoming damage;
ordinary environmental damage remains ordinary when that origin is absent.

Independent rerun: `test_innate_reaction_spell_costs.py` and
`test_spell_surface_damage_origin.py`: **14 passed in 0.72s** in the isolated
mechanics environment. The test-only grants on an existing Fellwing body do not
author a new Devil kit. The final broader counts, reproduced base failures and
five passing performance/oracle controls are recorded in
[MECHANICS_IMPLEMENTATION.md](MECHANICS_IMPLEMENTATION.md). This rereview does
not change the held A11/poison-kit decisions or certify roster/client completion.

### Human clarification rereview — Monk damage reference and poison

2026-10-18. Reviewed the updated plan's clarification, A11 row, Phase0/1 and
acceptance checks, the implementation ledger, the local Monk table and the
existing Equipment unarmed fields. **Approved as a bounded authoring-direction
correction; no engine change is needed.**

The human has rejected the old oversized fist recommendations and selected the
SRD5.1 Monk Martial Arts damage reference: one d4 at levels1–4, d6 at5–10, d8
at11–16 and d10 at17–20. Earlier review language describing a pending choice
between2d6 and3d4 is historical and superseded. The current plan removes those
active recommendations and requires an explicit per-NPC training tier, ability
modifier and attack budget. Existing unarmed data supports every listed die.
It grants no Monk class, Ki, Flurry, extra Brute dice or scaling helper, and does
not silently choose either the old CON-based Martial Guard or Monk WIS-based AC.
Defenses and final character numbers remain separate kit authoring work.

The poison clarification correctly treats the two lifetime options as variants
of the same Assassin Poison definition and DC15/7d6/half-save payload. It does
not create two items. Existing Basic Poison remains a genuinely different
DC10/1d4/zero-on-save payload. The current ten-round Assassin coating default
remains in place pending explicit kit lifetime and possession counts. Historical
source drafts and earlier reviews are preserved, without becoming active grants
again. This documentation correction does not claim completed NPC kits or
additional gameplay/performance validation.
## Independent native authoring review, 2026-10-18

The plan-adherence reviewer independently inspected the four new family modules,
the shared possession/casting admission changes, the current source cards and
later dispositions, and the family authoring evidence. The human's subsequent
instruction authorizes native authoring in this worktree. Earlier statements
above that bulk recipes or the trained strike choice remain unselected describe
the earlier mechanics-only request.

**Result: source selection and native coverage approved.** This review does not
certify encounter balance, sprites, current-client playback or the static icon
ledger. Final gameplay batch results belong to the implementation record.

- Independently compared `native_authoring.csv` with `roster_inventory.csv`:
  all 180 source rows, their order and every original column are preserved.
  There are 123 new recipes, 20 retained accepted recipes, five explicitly
  reconciled existing recipes, eight visual holds and 24 modern exclusions.
  Exactly 148 distinct selected creature references exist; held/excluded rows
  have none. A separate AST-to-inventory comparison found exactly all 123
  previously unmapped candidate identities, without missing, unexpected or
  duplicated recipe keys. The new family counts are 28 fiends, 41 humanoids,
  eight undead champions/casters and 46 zombies.
- The existing 17 Goblins, six fiend/demon identities, canonical Orc and
  Skeleton Archer retain their identities. The three Demon Beast proposals
  do not overwrite Dretch, Corrosive Demon or Dread Demon. Canonical Orc01's
  source equipment and Skeleton Archer's Skeleton foundation remain disclosed
  departures from the older individual proposals. They are not duplicate new
  recipes or claims of completed sprite reconciliation.
- All 46 admitted zombie rows match the visual triage. Only Hulk1, Hulk2 and
  Monster3 select the heavy body. The five selected Athletics grants, two
  speed15 crawlers and two armed Swamp variants match the later dispositions.
  Seven Radioactive variants have explicit native names/kits and ordinary
  Zombie rules; their palettes grant no new damage or immunity. No held or
  modern worker row was admitted to supply a missing tool kit.
- The humanoid kits preserve the stronger foundations and actual possessions.
  Both fist fighters explicitly select the level11 damage reference,
  1d8+STR4 for each of three attacks, with separate AC17/AC12 equipment
  decisions and no Brute or weapon Parry. Four Assassin variants own finite
  three-dose stacks, apply poison through its real action and retain 4d6
  Sneak Attack, Assassinate and Evasion. Gateplate retains Protection and
  Parry with one reaction budget. The later Greater Psychic Longsword belongs
  to Character7; it is not downgraded to the ordinary psychic sword.
- Fiend casting uses actual Eldritch Blast at selected levels5/11/5/1 and
  finite per-spell native resources. It does not preserve obsolete free Bolt
  Multiattacks. Psychic weapons replace old inferred necrotic riders; only
  the Regent's selected intrinsic claws retain their own necrotic packet.
  Armed Imps omit Sting/Shapechanger, and Regent legendary work stays deferred.
  The separately paid native bonus offhand attack is explicitly disclosed as
  an adaptation, including the older C15 prohibition; Multiattack itself adds
  no free extra strike.
- Source review caught and the authors corrected missing Bonewheel Parry,
  Undead Archmage expertise/languages, Pikeward's weapon-specific Life Drain
  selection, Dark Archer equipment, Footsoldier Protection and the stronger
  ritual sword. Unsupported spells, understanding-only speech, silver-qualified
  physical resistance and other native limitations are disclosed rather than
  replaced by invented rules. The caster kits do not start with free Mage
  Armor/Stoneskin. Deferred ammo, loading, focus/tool/mount, Grapple and custom
  signature systems remain deferred.

Independent existing inventory/icon qualification ran in the task's isolated
`npc-mechanics-venv`: **10 passed, two failed in2.57s**. Both failures are the
same static icon-ledger closure failures on clean base5779, where the same
files produced **10 passed, two failed in2.47s**. The clean export's omitted
offline importer script was restored from that exact base before comparison.
No icon/artwork scope was added to conceal this existing limitation.
