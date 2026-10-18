# 58-spell handler ownership review

Date: 2026-10-15. Worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`; implementation HEAD `a1349f52e8b`, branch `codex/spells-rank-one-two`.

Status: complete source review of **36 lower-level roots + 22 higher-level roots = 58 spells**, including **all 12 higher-level summoned bodies**. Two independent reviewers covered the two batches; the primary agent checked the reported coupling sites. No production repairs or new gameplay tests were performed. This is a fresh ownership review; the earlier [anti-slop qualification](SPELL_58_ANTISLOP_REVIEW_2026-10-15.md) did not establish this criterion.

## Result

**Yes, the implemented batch contains examples of the mistake the human identified.** Four spell implementation sites contain foreign-effect coupling: Destroy Water enumerates foreign surface classes; Searing Smite checks Wet by name; Disintegrate implements Resilient Sphere's destruction; Heal implements Feeblemind's cure. The last two also introduced effect-specific flags into BaseCondition. Their behavior belongs to the reacting effect's own handlers and native admission/interaction facts.

Three additional identity-coupling sites occur inside otherwise owned handlers/actions: Forcecage's two-spell teleport allowlist, the summoned Burning effect's Wet-name guard, and Winter's Breath's Burning display-name test. Aura of Life's maximum-HP protection needs a separate native coverage review: its capability is neutral, but enforcement currently depends on Life Drain remembering a check.

The remaining spells mostly compose their own effects and install their own handlers correctly. Generic ECS capability data enforced at the authoritative shared action/item/encounter owner is not itself the same error. The reports below distinguish those contracts from confirmed foreign-owner leakage rather than recommending a new event system for every boolean.

## Repair inventory and regression behavior

These are review recommendations for a corrective batch, not production changes made by this audit. Preserve selected gameplay rules while moving ownership; do not introduce new spell exceptions or a general element/condition framework.

| Finding | Current owner / coupling | Intended owner and boundary | Regression behavior |
| --- | --- | --- | --- |
| L36-01 | Destroy Water directly enumerates/mutates five surface implementations. | Spell publishes one native remove-water/drying spatial interaction; each eligible surface owns its transition/partial-footprint handling. | Partial/whole overlap, independent overlapping sources, unchanged neighbor cells/non-water surfaces, native transition rejection. |
| L36-02 | Searing Smite Burn rejects `"Wet"` by display name. | Active Wet owns admission against a separate declared already-Wet incompatibility fact; burn owns its damage/save and existing ending triggers. | Immediate hit/fire still resolve on Wet; no retained burn; new Wet removes burn; inactive/suppressed Wet and independent sources; Glyph Sleep keeps its existing rule. |
| H1 | Disintegrate implements Sphere destruction through `destroyed_by_disintegrate`. | Sphere owns incoming Disintegrate application and exact self-removal/consumption. | Sphere destroyed, occupant unharmed, accepted cast still paid, vetoed self-removal, ordinary creatures/objects unchanged. |
| H2 | Heal scans `cured_by_heal` for Feeblemind. | Feeblemind owns accepted Heal application cure with exact native provenance. | Full-HP and injured recipients cured; rejected Heal does not cure; ordinary healing does not cure; unrelated Greater Restoration behavior unchanged. |
| H7 | Forcecage handler exempts only Misty Step and Dimension Door. | Same owned cage/escape handlers consume factual magical-transfer capability. | Existing teleports still reach paid CHA escape test; ordinary cross-boundary spells blocked; another authored native transfer needs no cage-specific name entry. |
| H8a | Summoned Burning rejects `"Wet"` by display name. | Same active-Wet incompatibility admission as L36-02, without treating every Wet-ending effect as admission-blocked. | Fire Elemental/Myrmidon immediate damage retained; already-Wet no burn; new Wet removes burn; inactive/suppressed owner does not veto. |
| H8b | Winter's Breath recognizes Burning by presentation label. | Own technique consumes a stable typed burning fact and native admitted removal; retains its specific save/Brittle rule. | Cooling removes only qualifying owned active effects; failed save plus prior burn grants Brittle; ordinary cold damage gains no new rider; relabeling presentation does not change behavior. |
| H3 follow-up | Aura of Life protection checks appear in initial and repeated Life Drain reduction. | Aura-owned protection at one factual maximum-HP-reduction admission boundary, including additions to an existing reduction. | Initial/repeated reduction prevented, existing reduction retained, suppression/removal restores eligibility, another legitimate reduction producer follows the same native admission. |

The summon helper `owns_fact` at `dnd/monsters/spell_summon_actions.py:166` also falls back to condition names beside semantic/immunity identities. Its use for Healing Vapours' Poisoned switch and Multiattack prerequisites is each action's own authored rule; it is not another foreign-owner feature implementation. Prefer the existing stable semantic identity when cleaning the narrower H8 identity coupling, without changing those action rules.

The [Cleric/Paladin/Wizard plan](plans/CLERIC_PALADIN_WIZARD_IMPLEMENTATION_PLAN_2026-10-15.md) has been revised so Sculpt, Potent, Empowered, Overchannel and Life healing behavior are their own handlers. Missing native event payloads may carry factual dice/save/source data; individual spells do not compute those class features. The human subsequently explicitly authorized integrating this entire corrective batch as the first phase of the class plan; see its section10.0 and implementation record.

## Lower-level batch: complete review and 36-root coverage

## Result and interpretation

All 36 approved roots were inspected, including their retained effects, shared hit-rider code, created items, surface recipes, summon bodies and native integration. Two concrete foreign-effect coupling sites were found: Destroy Water enumerates other surface implementations, and Searing Smite directly asks for the foreign `Wet` display name. The other 34 roots do not contain the same confirmed foreign-feature detection. This does **not** certify every mechanic or every possible interaction.

A spell creating its own effect, installing its own modifiers/handlers, composing an ordinary native action/item/summon, querying a generic condition immunity, or invoking native healing/movement is not by itself a violation. Own-type checks for an exact retained owner are also legitimate. The future Wizard feature plan is different: individual spell code must not contain `if Empowered Evocation`, `if Overchannel` or `if Potent Cantrip` branches.

## Actionable findings

### L36-01 — P2: Destroy Water owns a list of other surface implementations

`dnd/spells/transmutation.py:2469`–`:2478`, `CreateOrDestroyWater._finalize_aoe`:

The destroy branch enumerates `(WetSurface, ElectrifiedWater, IceSurface, SteamCloud, SimpleToxinSurface)`, computes their remaining footprints and invokes `change_footprint`/`deactivate` directly. The spell knows five concrete foreign surface owners. A new water-bearing surface will not react without another edit to Destroy Water, and the interaction bypasses the existing surface transition dispatch boundary.

Replace this with one native `SpatialEffectInteractionEvent` carrying selected cells and a clear drying/remove-water operation. Each eligible surface owns its existing `bind_spatial_interactions` transition for that operation, using normal partial-footprint removal/admission. Destroy Water publishes the operation and never enumerates surface classes. Existing model: `dnd/spatial/ignition.py:38`, `dnd/spatial/environmental_conditions.py` transition definitions, and Plant Growth's owned ignition handler at `dnd/spells/transmutation.py:2358`.

Acceptance: partial overlap, overlapping water/electrified/ice/steam/toxin sources, unaffected neighboring cells and non-water surfaces, vetoed transition, and a new authored water-bearing source that responds without a Destroy Water edit. Preserve the previously selected native water policy; this is ownership relocation, not a new element system.

### L36-02 — P2: Searing Smite probes the foreign Wet display name during application

`dnd/spells/evocation.py:5612`–`:5613`, `SearingSmiteEffect._apply`:

The burn rejects itself using `"Wet" in target.active_conditions`. This couples it to another condition's display name rather than the active Wet contribution/admission rule. The same burn already declares `ConditionRemovalTrigger.WET_APPLICATION` at `:5608`; new Wet applications already process that generic capability at `dnd/spatial/environmental_conditions.py:443`–`:449`.

Have the active Wet owner install a native `ConditionApplicationEvent` handler that rejects incoming effects declaring a separate generic incompatibility/admission fact (for example `blocked_while_wet`). Keep `WET_APPLICATION` as an ending trigger: it does not by itself mean an already-Wet recipient cannot receive the effect. Otherwise this repair would also reject Glyph Sleep on an already-Wet creature, which is a different, unapproved rule. Wet's own initial application can still clear already-present effects declaring the ending trigger through native removal. Searing Smite only declares its incompatibility and owns its turn/save/damage handler; it does not recognize Wet by name. No Searing Smite identity check belongs in Wet.

Acceptance: already-Wet target receives the physical hit and immediate fire damage but retains no burn; a subsequently applied Wet effect removes burn; independent overlapping Wet sources; suppressed/inactive Wet does not act merely because an index entry remains; no extra slot/refund policy is introduced.

## Shared boundaries checked separately

- `dnd/spells/hit_effects.py:25` and `:301` query the existing generic `SpellProtectionRegistry` for native Globe/Antimagic contact policy. They do not import or recognize concrete Globe/Antimagic spell classes. This is centralized native policy reuse, rather than the confirmed foreign-type whitelist above, but future component-admission work should consolidate producer-side protection gates in the owning protection handlers. Do not report these calls as an Evocation/class hardcode or redesign protection incidentally.
- `dnd/spells/spell_utils.py:140` publishes generic attack damage finalization for successful spell attacks. It has no class predicates. Coverage is incomplete for save/automatic damage; this is a missing common event contract, not evidence that those spells currently contain Evoker rules.
- `dnd/conditions.py:3033` selects curable roots by declared condition/immunity identities and source creature type, then uses native removal preparation. Heroism/Protection/Calm author their own cure lists. They do not enumerate concrete foreign spell classes. The human explicitly selected clearing existing control; do not call that initial spell behavior an architecture mistake.
- `dnd/conditions.py:2975` represents reveal using a generic invisibility-suppression contribution and owned light. It preserves underlying Invisibility instead of deleting a foreign spell.
- `dnd/actions.py`, `dnd/entity.py` and `dnd/blocks/equipment.py` use generic `SpellWeaponProfile` data for Flame Blade. There are no FlameBlade-class/name branches in those native owners.
- Spiritual Weapon/Flaming Sphere composition in `dnd/summoning/system.py:168` onward selects their own authored body/parameters and owners. Flaming Sphere's trail/contact/aura changes are owned event handlers. This is the requested summon composer, not another feature detecting those spells in the damage system.

## Complete coverage: 36/36 roots

"No confirmed coupling" below refers only to this audit's foreign-feature/handler-ownership question. Spell root references are current source lines; listed effect/auxiliary owners were read as well.

| # | Spell and entry | Retained/auxiliary owner checked | Finding |
| --- | --- | --- | --- |
| 1 | Dancing Lights — `dnd/spells/evocation.py:5754` | DancingLightsEffect, MoveDancingLights; own light movement/lifetime | No confirmed coupling; own exact-owner checks and native light API. |
| 2 | Sorcerous Burst — `dnd/spells/evocation.py:5449` | Bounded exploding dice and generic damage delivery | No confirmed coupling; casting-source modifier is its own authored dice cap. |
| 3 | Spare the Dying — `dnd/spells/necromancy.py:2607` | Native life-state validation/stabilize | No confirmed coupling; no raw HP/life-state mutation. |
| 4 | Starry Wisp — `dnd/spells/evocation.py:5405` | StarryWispEffect, Revealed, source-turn expiry | No confirmed coupling; generic suppression contribution, not Invisibility removal. |
| 5 | Vicious Mockery — `dnd/spells/enchantment.py:2009` | MockedEffect consumes next actual attack via handler | No confirmed coupling; successful-save early return is a missing future Potent boundary, not a current class branch. |
| 6 | Animal Friendship — `dnd/spells/enchantment.py:2087` | AnimalFriendshipEffect allied-damage handler and native Charmed transform | No confirmed coupling; owns its damage-break rule. |
| 7 | Chromatic Orb — `dnd/spells/evocation.py:5961` | place_spell_surface, native elemental interactions | No confirmed coupling; choosing its own authored patch is ordinary composition. |
| 8 | Create or Destroy Water — `dnd/spells/transmutation.py:2406` | RainWetEffect, Wet leases, create/destroy footprint paths | **L36-01**: concrete foreign surface whitelist/direct mutation. |
| 9 | Dissonant Whispers — `dnd/spells/enchantment.py:2161` | DissonantFearEffect own modifiers/deadline | No confirmed coupling; separate fear identity with declared immunity compatibility. |
| 10 | Divine Favor — `dnd/spells/evocation.py:5579` | DivineFavorEffect installs generic hit-rider handler | No confirmed coupling; rider observes native hits. |
| 11 | Divine Smite — `dnd/spells/reaction_spell_content.py:114` | LearnedDivineSmiteHandler and shared per-slot handlers in `dnd/classes/paladin.py` | No confirmed foreign coupling; class-vs-spell entitlement/provenance integration defect already recorded for actual Paladin work. |
| 12 | Ensnaring Strike — `dnd/spells/conjuration.py:5152` | AttackBackedSpell, EnsnaringStrikeEffect, Help capability | No confirmed coupling; spell-weapon exclusion uses generic attack profile, not Flame Blade identity. |
| 13 | Faerie Fire — `dnd/spells/evocation.py:5530` | FaerieFireEffect and Revealed | No confirmed coupling; generic reveal/advantage contributions. |
| 14 | Goodberry — `dnd/spells/transmutation.py:2623` | GoodberryBatch, CreatedItemsLifetime, GoodberryItem/EatGoodberry | No confirmed coupling; own native item charges/healing/retirement. |
| 15 | Heroism — `dnd/spells/enchantment.py:2345` | HeroismEffect refresh handler and generic prepared control removal | No confirmed coupling; own temp-HP grant identity protects independent grants. |
| 16 | Hex — `dnd/spells/enchantment.py:2497` | HexQuarry, HexEffect, QuarrySustain/ReapplyQuarry, install_hit_rider | No confirmed coupling; hit handler, source-owned quarry, ordinary check modifiers. |
| 17 | Hideous Laughter — `dnd/spells/enchantment.py:2262` | HideousLaughterEffect recovery handler and shared incapacitation transform | No confirmed coupling; owned damage/turn saves. |
| 18 | Hunter's Mark — `dnd/spells/divination.py:446` | HuntersMarkEffect/Quarry, shared reapply and hit handler | No confirmed coupling; own quarry and weapon-source eligibility. |
| 19 | Protection from Evil and Good — `dnd/spells/abjuration.py:3677` | Source-type contextual attack/immunity contributions and prepared cure | No confirmed coupling; own authored protection/cure rule with generic native metadata. |
| 20 | Ray of Sickness — `dnd/spells/necromancy.py:2643` | RayOfSicknessPoison, shared Poisoned transform and expiry handler | No confirmed coupling; own separate poison save/rider. |
| 21 | Searing Smite — `dnd/spells/evocation.py:5640` | AttackBackedSpell and SearingSmiteEffect | **L36-02**: direct foreign Wet-name probe. Its own save/burn handler is otherwise appropriately owned. |
| 22 | Acid Arrow — `dnd/spells/evocation.py:6073` | AcidArrowEffect delayed-damage handler, own acid patch | No confirmed coupling; native elemental patches and own delayed tick. |
| 23 | Branding Smite — `dnd/spells/evocation.py:5665` | AttackBackedSpell, BrandingSmiteEffect/Revealed | No confirmed coupling; generic reveal, no foreign Invisibility deletion. |
| 24 | Calm Emotions — `dnd/spells/enchantment.py:2406` | CalmedEffect exact cure/admission immunity sources | No confirmed coupling; own authored charm/fear/rage cure list, no concrete Rage class probing. |
| 25 | Dragon's Breath — `dnd/spells/transmutation.py:2563` | DragonsBreathEffect, ExhaleDragonsBreath, elemental-contact dispatcher | No confirmed coupling; retained caster/source and native surface events. |
| 26 | Flame Blade — `dnd/spells/evocation.py:6148` | FlameBladeItem/Lifetime, generic SpellWeaponProfile, native Attack integration | No confirmed coupling; own created-weapon custody/lifetime and generic spell-weapon data. |
| 27 | Flaming Sphere — `dnd/spells/summoning.py:133` | FlamingSphereAura/Zone/Ram, sphere body and summon system | No confirmed coupling; own movement/fire-contact handlers, native summon lifecycle. |
| 28 | Magic Weapon — `dnd/spells/transmutation.py:2291` | MagicWeaponEffect contextual strongest-own-source modifiers | No confirmed coupling; own-source arbitration, no Shillelagh/FlameBlade class probe. |
| 29 | Moonbeam — `dnd/spells/evocation.py:5920` | MoonbeamEffect/Zone/MoveMoonbeam; owned exposure handlers | No confirmed coupling; relocating its own field is not a creature-movement workaround. |
| 30 | Pass without Trace — `dnd/spells/abjuration.py:3808` | Membership, shared bonus and native moving area | No confirmed coupling; own-membership/source arbitration. |
| 31 | Phantasmal Force — `dnd/spells/illusion.py:1524` | PhantasmalForceEffect damage/turn handler and native resolution data | No confirmed coupling; adapts its own damage type from generic actual component facts. |
| 32 | Spiritual Weapon — `dnd/spells/summoning.py:122` | SpiritualWeaponStrike/body/owner and native summoning | No confirmed coupling; own body composition and native natural attack. |
| 33 | Glyph of Warding — `dnd/spells/abjuration.py:3974` | Glyph owner/zone, sleep/removal handlers, native forced movement and elemental events | No confirmed coupling; own detonation uses ForcedMovementEvent/commit_forced_movement, not raw target position. |
| 34 | Plant Growth — `dnd/spells/transmutation.py:2363` | PlantGrowthZone walking-cost data and owned ignite transition | No confirmed coupling; already the correct event-owned surface interaction model. |
| 35 | Revivify — `dnd/spells/necromancy.py:2826` | Native prepare/commit revival and PortalTransferEvent | No confirmed coupling; composes its own recovery/placement through native admitted APIs, not raw health/position writes. |
| 36 | Vampiric Touch — `dnd/spells/necromancy.py:2787` | VampiricTouchEffect/Strike, own post-resolution healing callback | No confirmed foreign coupling; callback owns its own drain from native component resolution. It is not a Life-feature branch. |

## Required repair to the proposed class plan

Empowered Evocation/Overchannel/Potent/Sculpt must be class-owned handlers on shared native events. Current `TakeDamageEvent` is too late/incomplete for raw dice adjustment: several producers supply only amounts, and save damage may already be halved. Correct generic event payloads must retain raw typed damage rolls/specifications and save-reduction policy before applying reductions. Potent also needs a generic save-damage application boundary because successful save branches currently return before creating damage. Consumers may migrate to a generic, class-agnostic damage/save contract; they must not learn the names or conditions of those Wizard features.

Healing origin, exact casting ability, ritual entitlement and cast-cost modes are generic data/authority changes. Their consumers must not test Life Domain or Wizard subclasses. Disciple/Blessed/Supreme remain their owning handlers; rituals/free variants follow one generic cost contract with author-owned entitlement data. Preview must apply the same pure eligibility/modifier policy without dispatching gameplay effects or spending resources.

## Higher-level batch: complete review, 22-root and 12-body coverage

## Criterion

A spell/action may implement its own targeting, save, damage, healing, explicitly authored cure, prerequisite consumption and owned condition composition. A condition may install native modifiers and its own EventHandlers. These are not inherently hardcoding errors. The mistake is making a different spell/trait inspect an effect-specific flag/identity and implement that effect's reaction, or scattering a nonnumeric effect's rule across native owners instead of an owned handler/normal component contribution. Existing handler filters on exact authored identities can be legitimate; a general capability implemented as a short list of unrelated spell names is a different concern.

## Confirmed foreign-owner leakage

### H1 — Resilient Sphere destruction implemented inside Disintegrate (P2 architecture)

- `dnd/spells/transmutation.py:1026–1034`: Disintegrate scans the target's conditions for `destroyed_by_disintegrate`, removes the found condition, and changes its damage resolution into enclosure destruction.
- `dnd/core/base_conditions.py:564`: introduces the spell-specific flag into every condition.
- `dnd/spells/evocation.py:6347`: ResilientSphereEffect supplies it.

Move the enclosure's incoming-Disintegrate rule into a Sphere-owned handler/admission contribution. It should remove its own exact lease and consume/redirect that target application without causing creature damage or treating an ordinary prevented hit as a refunded cast. Disintegrate still owns ordinary object destruction and its own ray mechanics. Sphere already has a boundary EventHandler; its Disintegrate exception can be handled there with an explicit consumed-application result. No foreign scan is needed.

### H2 — Feeblemind cure implemented inside HealSpell (P2 architecture)

- `dnd/spells/evocation.py:4949–4951`: HealSpell loops target conditions for `cured_by_heal` and removes them.
- `dnd/core/base_conditions.py:567`: spell-specific cure flag.
- `dnd/spells/enchantment.py:2664`: FeeblemindEffect supplies it.

Feeblemind should own a handler reacting to an actually accepted eligible Heal application with exact native spell provenance. Use the spell application boundary, not merely positive HP restoration: a full-HP recipient can still receive a curative Heal. Greater Restoration's pre-existing category-based cure is its own spell behavior and does not need Feeblemind-specific branching. Do not remove generic restoration categories merely to eliminate this particular leak.

## Follow-up: neutral capability contracts and handler coverage

These are not automatically violations. They use effect-neutral ECS capability data rather than named foreign spell/class checks. The question is whether the capability is enforced at a complete authoritative native owner or copied into specific producers.

### H3 — Aura of Life maximum-HP protection distributed into the enemy drain trait (P2 coverage/ownership follow-up)

- `dnd/monsters/traits.py:1619` and `:1633`: initial LifeDrainReduction and later `add_reduction` consult `health.prevents_maximum_reduction()`.
- `dnd/blocks/health.py:718–721`: scans all active conditions for the Aura-provided capability flag.
- `dnd/core/base_conditions.py:559`: capability introduced for this behavior.
- `dnd/spells/abjuration.py:4021`: AuraOfLifeBenefit supplies it.

The neutral protection capability can be legitimate ECS data, but only the LifeDrain producer currently checks it. Its initial condition already passes native CONDITION_APPLICATION admission, while an additional reduction mutates an existing modifier directly. Prefer Aura owning a recipient handler rejecting a typed maximum-HP reduction admission, or one native maximum-HP owner enforcing the neutral capability for every producer. Initial condition application and additional reduction of an existing LifeDrain condition must both pass the same factual native boundary. If no generic modifier/reduction request exists, add that request at the max-HP owner; keep the protection predicate in the Aura handler. Do not clamp all negative max-HP modifiers, erase existing reduction or require every new draining monster to remember this special guard.

## Neutral native capability checks: not confirmed foreign-owner leakage

### H4 — Foresight surprise prevention via BaseBlock/Encounter capability (follow-up, not a confirmed violation)

`dnd/spells/divination.py:472` supplies `prevents_surprise`; `dnd/core/base_block.py:675–677` scans conditions; `dnd/encounter.py:741` and `:834` branch before reaction debit and skipped turn. No spell name is hardcoded. Surprise is resolved at the correct native Encounter owner and this effect-neutral query can be legitimate ECS capability composition. If a handler path is preferred, add one generic surprise-resolution/admission boundary with a Foresight-owned immunity handler; do not declare a functional cross-spell bug solely from the flag. Both first-round consequences must consume the same actual resolved surprise fact. The existing numerical advantage contributions are proper owned modifiers.

### H5 — Irresistible Dance action-channel denial via Entity capability (no confirmed violation)

`dnd/spells/enchantment.py:2593` sets `blocked_action_channels`; `dnd/entity.py:4011–4013` scans conditions and rejects action channels. This is generic capability data, not a named-spell exception. Its consumer is the shared native action-channel gate. Reusing the existing ActionEconomy restricted/channel contribution owner may reduce parallel restriction contracts if it expresses the rule, but neither a data contribution nor shared eligibility query is itself improper class logic in another spell. Preserve BA/reactions. Its speed/advantage modifiers and end-save handler are correctly owned.

### H6 — Sphere/Feeblemind outward/cast/item denial via native capabilities (no confirmed violation)

- `dnd/core/base_actions.py:1363–1366`: generic nonspell physical contact restriction by `blocks_external_contact`.
- `dnd/core/base_actions.py:2098–2107`: `blocks_outward_actions` scan and spellcasting gate.
- `dnd/core/base_block.py:671–673`: `blocks_spellcasting` scan.
- `dnd/blocks/base_item.py:1389–1391`: `blocks_magic_item_activation` scan.

No literal Sphere/Feeblemind class appears in these generic queries. These are effect-neutral agency/contact/spellcasting capabilities consumed by the correct shared action/item owner, so they are not confirmed foreign-owner leakage. The class plan should reuse an existing native capability if appropriate, rather than requiring a new event for every static restriction. If a handler-based admission hook replaces them, discovery must ask the same predicate without mutating/dispatching gameplay consequences. Sphere's existing damage/forced-movement/instant-death/healing/spell boundary handler is already the correct pattern.

## Smaller hardcoded identities in otherwise owned behavior

### H7 — Forcecage's teleport name allowlist (confirmed P2 identity hardcoding)

`dnd/spells/wall_constructions.py:863` exempts only `misty_step` and `dimension_door` from the sealed-box spell boundary. The handler is properly owned by Forcecage, and its `PortalTransferEvent` escape handler is also correct. The exception should be a factual magical-transfer capability, so another native teleport does not require editing Forcecage. Its exact `disintegrate` check at `:865` is an explicitly named destruction interaction inside the correct owner, not the same foreign-owner mistake as H1.

### H8 — Summon Burning/Winter status identities (P2 identity coupling; not all own-action predicates are ownership mistakes)

- `dnd/monsters/spell_summon_actions.py:270`: Burning's `_apply` rejects literal `"Wet"` present in active conditions. Native Wet already owns WET_APPLICATION cleanup in `dnd/spatial/environmental_conditions.py:444–449`. Its active owner should also reject incoming effects declaring a separate already-Wet incompatibility fact, as in L36-02. Do not use the ending trigger alone as an admission veto: that would also prevent Glyph Sleep on already-Wet recipients and change an unrelated rule.
- `dnd/monsters/spell_summon_actions.py:971–982`: Winter's Breath finds effects by `get_display_name() == "Burning"`, removes them and applies Brittle on a failed save. This is the technique's own explicitly authored cooling/Brittle behavior, not a change inside the unrelated Burning spell; nevertheless, use a typed burning/extinguishable identity and an owned admitted technique handler rather than a display label. Do not replace this with global Cold immunity or let generic cold damage gain Winter's special Brittle rider.

## Complete 22-root coverage

| Root | Actual inspected runtime | Result under this criterion |
| --- | --- | --- |
| Aura of Life | `abjuration.py:4018–4093`; life-drain/native Health changes | H3 follow-up: neutral protection contract is enforced only in the LifeDrain producer. Start-turn recovery handler and owned resistance/membership are proper. |
| Charm Monster | `enchantment.py:2530–2587`; AnimalFriendship/Charmed native behavior | Own combat save modifier, charm composition and inherited damage-break handler; no confirmed foreign-owner leakage. |
| Phantasmal Killer | `illusion.py:1557–1627` | Own recovery/damage/expiry handlers and same-effect strongest-overlap choice; no confirmed foreign-owner leakage. |
| Resilient Sphere | `evocation.py:6341–6425`; Disintegrate/BaseAction branches | H1 confirmed. H6 neutral capabilities are not automatically wrong; existing source-owned boundary handler is proper. |
| Vitriolic Sphere | `evocation.py:6197–6262` | Own initial damage/save and residue turn handler; no confirmed foreign-owner leakage. |
| Antilife Shell | `abjuration.py:4301–4370` | Own native spatial crossing/relocation behavior and generic magic suppression query; no foreign spell-name branch. |
| Conjure Elemental | `summoning.py:142–148`; native summon lifecycle; 8 bodies below | Own summon recipes/leases. H8 in fire/water techniques; other riders use owned handlers. |
| Dispel Evil and Good | `abjuration.py:4205–4300` | Own defensive modifiers and granted Break Enchantment's explicit source-type/charm/fear cure; proper own-action behavior. |
| Summon Dragon | `summoning.py:156–175`; cadence/resistance body conditions | Own source-scaled body recipe, native Multiattack, owned free-Breath event handler and resistance lease; no confirmed foreign-owner leakage. |
| Blade Barrier | `evocation.py:6301–6340`; `wall_fields.py:381–420` | Own formation/entry/turn contact events and authored native damage data; no confirmed foreign-owner leakage. |
| Flesh to Stone | `transmutation.py:2677–2765`; Petrified native modifiers | Own staged-save handler and owned Petrified composition; proper. Petrified poison immunity is in Petrified's own component grants. |
| Freezing Sphere | `evocation.py:6668–6751`; `items/spell_payloads.py` | Own launch/portable delivery, item lifetime/end handlers and generic protection/spatial access; no confirmed foreign-owner leakage. |
| Irresistible Dance | `enchantment.py:2588–2657`; Entity action-channel scan | H5 neutral shared agency capability, not confirmed foreign-owner leakage. Owned recovery/speed/save/attack modifiers are proper. |
| Planar Ally | `summoning.py:149–155`; Deva/Djinni/Cambion recipes below | Own summon recipe/lifetime; no confirmed foreign-owner leakage. Draining Kiss's exact own Charm Person prerequisite is intentional own-ability behavior. |
| Arcane Sword | `evocation.py:6426–6667` | Own retained anchor and granted strike/move actions with exact lifetime/ability/DC; no confirmed foreign-owner leakage. |
| Delayed Blast Fireball | `evocation.py:6752+`; `items/spell_payloads.py` | Own bead lifetime/turn growth, touch-save and detonation ending handlers; no confirmed foreign-owner leakage. |
| Forcecage | `wall_constructions.py:785+` | H7 literal teleport allowlist inside otherwise correct owned boundary/escape handlers. |
| Feeblemind | `enchantment.py:2658+`; Heal/item/native admission changes | H2 confirmed. H6 neutral capability gates are not confirmed foreign-owner leakage. Fixed score component contributions are proper. |
| Holy Aura | `abjuration.py:4094–4204` | Owned modifiers/light and incoming melee-hit blindness handler; no confirmed foreign-owner leakage. |
| Foresight | `divination.py:469+`; BaseBlock/Encounter changes | H4 effect-neutral native surprise capability; optional admission follow-up, not confirmed foreign-spell hardcoding. Advantage modifiers and same-caster lifetime composition are proper. |
| Power Word Heal | `evocation.py:6263–6300`; `reactions.py:112+` | Own authored cure and generic StandOffer; recipient's persistent stand-preference handler owns the reaction. Correct pattern. |
| Weird | `illusion.py:1628+`; Frightened | Own fear/recovery/damage/expiry handlers and same-effect overlap; no confirmed foreign-owner leakage. |

## Complete 12-body coverage

The actual constructors are in `dnd/monsters/high_level_spell_summons.py`; techniques and passive owners are in `dnd/monsters/spell_summon_actions.py`.

| Body | Checked mechanics | Result |
| --- | --- | --- |
| Air Elemental | Multiattack status bonus, Shocked, Gushing Air, Primordial Gales, Warp | Bonus is installed by ElementalMultiattackBonus's own DamageRollResult handler; statuses own modifiers/expiry. Proper. |
| Earth Elemental | Multiattack/Prone bonus, Soil-Clogged Slam, Seismic Strike, Trembling Legs, Mud | Own technique save/rider composition and owned bonus/status handlers. Proper. |
| Fire Elemental | Multiattack/Burning bonus, Smouldering Touch, Cinderous Swipe, fire patch | Bonus uses owned handler; H8 Wet guard in shared Burning. |
| Water Elemental | Multiattack/Chilled bonus, fixed Water Slam component, Winter's Breath, Brittle/ice | Native fixed-component hit handler is proper; H8 display-label predicate/cooling branch. |
| Air Myrmidon | Electrified Flail packet/stun, Tenacity, Raging Vortex/Silence, Invisibility, Warp | Owned strike and miss handlers, own concentration/area/invisibility composition; no confirmed foreign-owner leakage. |
| Earth Myrmidon | Grounded Thunder/Prone, Sludgy Sling/Mud, Burrow/arrival, Muck to Metal | Own action/condition composition and admitted costs; no confirmed foreign-owner leakage. |
| Fire Myrmidon | Scorching Strike, Swipe, Immolation/Haste/lethargy, own Hellish Rebuke | H8 shared Burning guard. Immolation composes existing Haste correctly; no Immolation branch added inside Haste. |
| Water Myrmidon | Hiemal Strike/Chilled, Explosive Icicle, Healing Vapours/Wet | Own strike handler. Poisoned->poison versus healing is this action's declared behavior, not a Poisoned change inside generic healing. `owns_fact` name fallback is identity coupling but not foreign-owner mechanics. |
| Deva | Angelic weapons, Concussive Smash/Dazed, native Revivify, Help | Own native feature/action/resource composition; no confirmed foreign-owner leakage. |
| Djinni | Native Thunderwave/Misty Step, Sweetplum Gales restraint fields | Own area/membership handlers and native spell grants; no confirmed foreign-owner leakage. |
| Cambion | Native Charm Person/Scorching Ray, Draining Kiss | Kiss intentionally consumes this exact caster's Charm Person as its own prerequisite/rule. Exact source check is appropriate, not an unrelated spell implementation knowing about Cambions. |
| Draconic Spirit | Rends, free Breath cadence, caster resistance | Cadence condition owns the accepted Multiattack/END/CANCEL handlers and free action; resistance owner follows body lifetime. Proper. |

## Prioritization and limits

First fix H1/H2, which place explicit effect-specific reactions in other spell owners, and H7's foreign-teleport allowlist. H3 needs a bounded producer-coverage/native-owner review because its neutral capability currently relies on LifeDrain-specific guards; it is not a literal Aura-of-Life identity branch. H4/H5/H6 are effect-neutral ECS capabilities at shared native owners and are not classified as confirmed violations. H8 concerns narrower status identity coupling in otherwise owned summon behavior.

No runtime defect is asserted merely because an `_apply` composes a spell's own damage/cure or an actual condition grants a modifier. No full-feature acceptance is inferred from source review. Suggested regressions are the existing gameplay interactions (Disintegrate/Sphere, Heal/full-HP Feeblemind, initial/repeated LifeDrain/Aura, Foresight surprised reaction+turn, Dance with Haste/BA/reaction, Sphere contact and magic-item denial), augmented by the same behavior with owning handler disabled/removed and by another producer of the same generic native fact. The prior 58-spell audit did not establish this handler-ownership criterion.


## Corrective implementation status

The human integrated this complete inventory into phase1 of the class plan. Repairs are implemented, including the additional existing Harm producer of maximum-HP loss. Both reviewers approved the implementation after412 affected gameplay/transport/recording tests passed. Details and the separate legacy architecture diagnostics are in class-plan section16. The earlier report above remains the source audit of implementation HEAD before these corrective edits.
