# Cleric, Paladin and Wizard implementation plan

Date: 2026-10-15. Worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`, branch `codex/spells-rank-one-two`, studied at commit `a1349f52e8b`.

Status: implemented and qualified on2026-10-16 in this worktree. Both independent reviewers approved the expanded complete plan before production edits and approved the completed implementation. All eight phases, including the first spell-ownership repair phase, are delivered. Section16 records execution evidence and unrelated legacy test diagnostics; the [Godot handoff](../CLERIC_PALADIN_WIZARD_GODOT_HANDOFF_2026-10-16.md) describes the usable contracts. Section13 records agent-selected defaults within the human-authorized implementation, not invented prior human decisions.

## 1. Requested outcome and accumulated decisions

Implement playable Cleric/Life Domain, Paladin/Oath of Devotion, and Wizard/School of Evocation through character level 20, through the same direct build/progression path as Fighter, Barbarian and Sorcerer. Include class creation, level-up/removal, multiclassing, prepared spells, spellbook learning, native actions/conditions/resources, player/server/SDK evidence and meaningful interaction tests.

The human explicitly added Wizard during this study, then requested copying BG3's rules and waived gold costs for spellbook learning. Scrolls must expose **Cast** and **Learn Spell** through their existing item-use path. The earlier constraints remain: reuse existing systems, no NDClient work, and spell identities must belong to SRD 5.1 or 5.2. BG3 is an adaptation reference, not permission to add its entire spell or subclass catalog.

Use documented BG3 behavior wherever it exists, then SRD 5.1 for features above BG3's level cap, then SRD 5.2 only for eligible additional spell identities. Do not copy reported BG3 bugs. Three subclasses are in scope; Ranger, other domains/oaths/schools, additional feats, graphics, economy, new campaign services, and the unimplemented SRD spell backlog are separate work.

Read before implementation: [AGENTS.md](../../AGENTS.md), [RECOVERY_PLAN.md](../../RECOVERY_PLAN.md), [HOW_TO_TEST.MD](../../HOW_TO_TEST.MD), the completed spell plans, [58-spell gameplay review](../SPELL_58_ANTISLOP_REVIEW_2026-10-15.md) and fresh [58-spell handler ownership review](../SPELL_58_HANDLER_OWNERSHIP_REVIEW_2026-10-15.md). The old [character progression plan](SINGLE_PLAYER_PROFILE_AND_CHARACTER_PROGRESSION_PLAN_2026-07-26.md) explains ownership intent; its obsolete server/directory paths are not implementation instructions for the current runtime.

## 2. What the existing classes actually do

| Concern | Current implementation | Extension for this work |
| --- | --- | --- |
| Passive identities and choices | `dnd/types/character_progression.py`: closed class/subclass enums; ordered `AppliedClassLevel`, `ClassChoiceSelection`, `PreparedSpellSelection`. | Add three classes and their three subclasses, keeping plain typed data. |
| Authored level rules | `dnd/content/characters/class_definitions.py`: frozen definition/resolved dataclasses, exact choice validation, first-class versus multiclass proficiencies, ASI/Lucky and ordered levels. | Add three concrete families in this owner. No runtime spell imports here. |
| Runtime grants | `fighter_grants.py`, `barbarian_grants.py`, `sorcerer_grants.py`: stable UUID contributions, direct component calls, typed receipts, rollback and exact cleanup. | Add `cleric_grants.py`, `paladin_grants.py`, `wizard_grants.py` with matching concrete receipt types. |
| Build composition | `builds.py`: pure validation, one `prepare_character`/`create_character` path, origin then levels then ordinary holdings. | Extend exhaustive class dispatch, source-specific preparations, Wizard book inputs and sample builds. |
| Level mutation | `progression.py`: authoritative ordered ledger, level events, total-level proficiency, failed-operation restoration and active-child cleanup. | Extend all apply/remove/change-fact branches. Replace `else -> Sorcerer` assumptions with explicit cases. |
| Spell authority | `SpellcastingBlock.sources`: exact source UUID, provider, ability, class level/rank, ritual policy. Learned reactions have shared handler/per-source ownership. | Preserve WIS/CHA/INT sources separately, including two versions of the same spell. |
| Normal slots | `ActionEconomy` owns **one shared aggregate**. Sorcerer grants currently install/remove a Sorcerer-only full-caster table. `core/progression.py` already computes full/half shared slots. | Reconcile one aggregate from all eligible classes. Migrate Sorcerer's writer/receipt assumptions as part of the same change. |
| Preparation | `builds.py` accepts only a Sorcerer preparation row, as metadata; it does not reconcile a prepared caster's available templates. | Implement real prepared entitlements for these three classes. Preserve Sorcerer's known-caster behavior. |
| Spellbook | No playable Wizard or active spellbook owner exists. | Add plain book state and concrete Wizard composition; separate level-learned choices from permanently scribed entries. |
| Scrolls | `_direct_scroll` builds `SpellGrantingItem`; `get_use_actions` already handles `SpellAction` and ordinary `BaseAction` templates. Native finite charges handle stacks/retirement. | Add explicit scribing metadata and one ordinary Learn action. Keep Cast and its identity/cost behavior. |
| Presentation/transport | `dnd/player/content_composition.py` enumerates the three existing class tables; player facts already include class levels, resources and exact action provenance. | Include new definitions/actions and only necessary book/preparation facts; regenerate engine-owned SDK contracts when the wire changes. |

The passive `durable_characters.py` island and `server_obsolete` are not the current class creation path. Do not revive them, add another materializer, build a class-manager hierarchy, introduce a contribution interpreter, or import concrete classes/spells into Entity/core leaves.

### Handler ownership guardrail

All cross-effect behavior is installed by its owning feature as native EventHandlers. Spell and condition setup remains data composition: create the effect, native modifiers and its own handlers. No spell/condition gains `if Wizard`, `if Sculpt`, `if Potent`, `if Empowered`, `if Overchannel`, or implements another effect's reaction by probing its identity/flag. An owning handler can recognize an explicitly named rules interaction, such as Sphere reacting to Disintegrate; the foreign producer must not implement that reaction. Shared engine changes may expose missing factual data/events, cost policies and exact source resolution, not dispatch class mechanics. The same rule applies to healing bonuses, aura control interactions, rituals and free-cast features.

The fresh 58-spell ownership audit found existing foreign-effect coupling in Destroy Water, Searing Smite, Disintegrate/Sphere and Heal/Feeblemind, plus narrower teleport/status identity coupling and a maximum-HP admission coverage concern. The human has now explicitly included all these repairs as phase1 of this class plan. Complete and validate them before starting class implementation. Do not copy their existing coupling into new class features.

Dependency direction is concrete grants/builds/progression -> shared spellcasting composition -> cold definitions + native Entity/actions/catalog. The shared helper never imports its concrete grant callers. Scroll action -> low book data/helper is a separate downward edge; its Wizard-grant-owned handler installs cantrip entitlements.

### Concrete file ownership

- Existing cold data: `dnd/types/character_progression.py`, `dnd/types/character_receipts.py`, `dnd/content/characters/class_definitions.py`, `build_types.py`.
- Existing composition: `builds.py`, `progression.py`, `premades.py`, `dnd/player/content_composition.py` and current builtin content declarations.
- New concrete grant owners: `dnd/content/characters/{cleric,paladin,wizard}_grants.py`.
- Runtime features: new `dnd/classes/cleric.py`, new `dnd/classes/wizard.py`, extend existing `dnd/classes/paladin.py`. A small `dnd/classes/divine.py` may hold the shared Turned effect and its flee/action rules because Cleric and Devotion both deliver it.
- Bounded shared composition helpers: `dnd/content/characters/spellcasting_grants.py` for aggregate slots and exact prepared entitlement reconciliation. Split it only if actual import direction or size warrants it.
- Spellbook eligibility/mutation data must live below item actions, independently of the runtime spell catalog. Do not let `items/spell_items.py -> character grants -> spell catalog -> items` create a cycle. An authored spell-list leaf and one narrow spellbook-changed event are sufficient if an event is needed for cantrip installation/capture.
- Existing mechanics extended only where required: `SpellcastingBlock`, spell execution/effect provenance, healing helpers/events, spell target resolution, native damage resolution, item actions/consumption and player capture/reduction.

## 3. Shared class foundation and spell preparation

### 3.1 Class tables, entry and receipts

Author the complete level tables before granting behavior. Each concrete resolved row declares only what that level adds or replaces. Each receipt stores exact handles to the owners it touched: hit dice, proficiencies, ASIs, features, actions/handlers, named resources, casting source, prepared entitlement changes, and active class-feature roots. Use deterministic per-class/per-source UUID namespaces, not display-name matching.

Cleric: d8, WIS/CHA saves, two class skills, simple weapons, light/medium armor and shields; Life grants heavy armor. Paladin: d10, WIS/CHA saves, two class skills, armor/shields and simple/martial weapons. Wizard: d6, INT/WIS saves, two skills, BG3's dagger/quarterstaff/light-crossbow proficiencies; no armor. Multiclass entry grants only the corresponding added-class proficiencies, not first-class saving throws, skill choices or starting equipment. Wizard grants none on multiclass entry. Reuse ordinary item loadouts for starting gear.

Use current native hit-die maximum at character level one and average thereafter, total-level proficiency and retrospective CON handling. Preserve the creator's point-buy/origin/feat rules; the existing ASI/Lucky choice remains the supported feat surface, not the whole BG3 feat catalog.

Follow BG3 subclass timing for these classes: Life at Cleric 1, Devotion at Paladin 1, Evocation at Wizard 2. Devotion's SRD-eligible active oath options/spells begin at 3; do not fill its first level by silently adding the BG3-only Holy Rebuke feature. Include the timing difference in descriptions/tests.

The existing engine enforces SRD multiclass ability prerequisites. Whether the human's BG3 instruction also removes that general creator rule is a separate explicit decision in section 13; do not leave different enforcement in cold builds and live progression.

### Level-by-level delivery table

All levels also update native HP, total proficiency, class source level and the relevant slot table. Wizard adds two class-level book choices at every level after1. Blank entries mean no new named feature, not omitted spell/HP progression.

| Level | Cleric / Life | Paladin / Devotion | Wizard / Evocation |
| --- | --- | --- | --- |
| 1 | WIS Spellcasting,3 cantrips,Life/heavy armor,Disciple,domain pair | Devotion selection,Oath pool,Divine Sense,Lay Hands3 | INT Spellcasting,3 cantrips,6 book spells,Recovery1,scroll learning |
| 2 | Divinity1,Turn Undead,Preserve Life | CHA Spellcasting,style,Divine Smite | Evocation,Savant,Sculpt |
| 3 | Domain pair | Divine Health,Sacred Weapon,Turn Unholy,oath pair | Recovery2 |
| 4 | ASI,cantrip4 | ASI,Lay Hands4 | ASI,cantrip4 |
| 5 | Destroy Undead4d6,domain pair | Extra Attack,oath pair | Recovery3 |
| 6 | Divinity2,Blessed Healer | Protection aura | Potent Cantrip |
| 7 | Domain pair | Devotion aura | Recovery4 |
| 8 | ASI,Divine Strike1d8 | ASI | ASI |
| 9 | Domain pair | Oath pair | Recovery5 |
| 10 | Cantrip5,Divine Intervention | Courage aura,Lay Hands5 | Cantrip5,Empowered Evocation |
| 11 | — | Improved Divine Smite | Recovery6 |
| 12 | ASI | ASI | ASI |
| 13 | — | SRD oath pair | Recovery7 |
| 14 | Divine Strike2d8 | Cleansing Touch | Overchannel |
| 15 | — | Purity of Spirit | Recovery8 |
| 16 | ASI | ASI | ASI |
| 17 | Supreme Healing | Flame Strike;Commune named unavailable gap | Recovery9 |
| 18 | Divinity3 | Three passive aura radii30ft | Spell Mastery |
| 19 | ASI | ASI | ASI,Recovery10 |
| 20 | No extra BG3 Intervention use | Holy Nimbus | Signature Spells |

### 3.2 One shared slot owner

Collect each eligible class contribution: Cleric/Wizard/Sorcerer full caster from 1; Paladin half caster from 2; Fighter/Barbarian noncaster. Compute slots with existing `effective_spellcaster_level`, explicitly selecting the BG3/SRD5.1 half-caster round-down multiclass policy rather than inheriting the helper's SRD5.2 default. A sole Paladin still uses its own table equivalence (`ceil(level/2)`); Paladin 1 contributes nothing.

One stable aggregate owner is updated through exact remove-before-set using the existing capacity APIs, with rollback of the prior receipt: the setter rejects changing capacities under the same UUID. No checksum-derived identities or second slot ledger are needed. Preserve spent slot cost modifiers and converted extra slots; adding/removing a class must not refill slots. Existing Sorcerer receipts may no longer assert that a Sorcerer-level UUID owns the entire table. Update its apply/remove/rollback together with the new aggregate reconciliation. Source action UUIDs must include the exact class casting source so identical Cleric/Paladin/Wizard spells coexist.

Own class progression rank remains distinct from shared slot rank. Cleric/Paladin level-up/preparation limits use their own class. **BG3 Wizard scribing/preparation additionally uses shared slot capacity**; do not overwrite `SpellcastingSource.maximum_spell_rank` with that larger value. Clarify that field's own-class ceiling description, and validate the Wizard book access at the prepared/scribing boundary. Capacity, not unspent slots, controls eligibility.

Cantrip damage scales with total character level. Source level still controls class choices/features. Audit the current Sorcerer template-level updates so a new multiclass level does not leave another source's cantrip scaling stale.

### 3.3 Prepared entitlements

Use existing `PreparedSpellSelection` source IDs: `class.cleric.spellcasting`, `class.paladin.spellcasting`, `class.wizard.spellcasting`. Limits: `max(1, Cleric level + WIS mod)`, `max(1, floor(Paladin level/2) + CHA mod)`, `max(1, Wizard level + INT mod)`. Cantrips are always available and use no leveled preparation capacity. Domain/oath/signature spells are always prepared outside the selected-spell budget.

BG3 permits changing preparation outside combat without a long rest or prayer timer. Implement an ordinary native preparation operation guarded by authoritative encounter state; use it in build composition and out-of-combat callers. Do not fabricate a campaign gateway or NDClient screen. If the current player/server boundary needs a minimal command/fact to make the delivered operation usable, add that exact operation, with authority checks and SDK generation, instead of resurrecting the old directory API.

Validate the complete requested replacement before mutation: source exists, correct class list/book, rank, uniqueness and capacity. Union selected + always-prepared without duplication. Install/remove exact-source action templates and reaction-spell leases; preserve other classes' copies and toggle preferences. Reject stale commands/invalid rows without changing actions, slots, book or resources.

Unpreparing removes future casting entitlement; it does **not** end an already cast Bless, Haste, concentration or summon. Active spell ownership survives losing a template. Class-feature root cleanup on actual level removal is a distinct existing lifecycle operation. Source removal must not accidentally unregister another source's Shield/Counterspell or the shared learned-Smite handler.

Ability changes alter preparation capacity. Reevaluate through the same validation/reconciliation owner; do not silently discard arbitrary prepared spells. Section 13 records the bounded recommendation for a temporary ability reduction that makes an existing list over capacity.

### 3.4 BG3 rituals

BG3 ritual-free casting is a property of an eligible accessible spell, not a Cleric/Wizard-only feature. Apply it to known Sorcerer spells and Paladin oath Silence as well. Existing `ritual_policy=NONE` must not veto the selected BG3 behavior.

Ritual policy enums currently exist as metadata; slot-free ritual execution does not. Implement BG3's prepared-spell rule: an eligible prepared ritual costs no spell slot outside combat/turn-based encounter mode, with normal spell action costs and effects. In combat it costs a slot. Wizard does not get the SRD's unprepared-book ritual exception under this BG3 profile.

Use an explicit authored ritual eligibility set from documented BG3 behavior, intersected with installed SRD spells. Current relevant roots include Longstrider, Jump/Enhance Leap, Feather Fall and Silence. Do not infer ritual status from spell names or treat every utility spell as a ritual. Extend existing metadata and cost/admission paths; retain spell base/effective rank even when no slot is paid. Do not charge zero slots by pretending the spell is a cantrip. Revalidate the combat gate at commitment, not just discovery.

## 4. Wizard spellbook and scroll learning

### 4.1 Book state and free level-up choices

Wizard 1 chooses three cantrips and six level-one spells. Each further Wizard level adds two leveled spells; additional chosen cantrips arrive at 4 and 10. Class-level choices remain capped by the Wizard table even in a multiclass build. Use explicit level choices and grant receipts, following Sorcerer's reversible learned-spell pattern without its spells-known replacement rule.

Keep permanently scribed spell IDs as plain character data independent of class-level receipts. The effective Wizard book unions the current level-learned spells with scribed entries. Removing Wizard removes casting/preparation/recovery/features but preserves scribed knowledge; taking Wizard again restores access subject to current slots. Level-learned choices disappear when their level is removed. Overlap is deduplicated; rebuilding a Wizard with an already scribed spell must not require consuming another scroll or make six first-level choices impossible.

Carry scribed data explicitly through `CharacterBuild` and native actor capture/rebuild inputs. No active durable campaign character store exists here, so do not promise that creating a fresh untouched build automatically remembers another session. The same boundary applies to permanent Divine Intervention usage (section 9).

Scribed leveled spells do not auto-prepare and do not use preparation slots until selected. BG3 permits transcribing an actual Fire Bolt scroll: authored scribed cantrips become always-available INT-based Wizard cantrips, outside the normal 3/4/5 level-choice allowance and leveled preparation budget. Do not ban all rank-zero scrolls or invent scrolls for unavailable cantrips.

### 4.2 Exact scroll changes

Current seven scroll builders: Fireball, Magic Missile, Hold Person, Mage Armor, Spike Growth, Fire Bolt and Invisibility. They share `SpellGrantingItem` with rings/wands/wearables and item-private effects. Add an explicit optional scribing spell identity authored by `_direct_scroll`; only those actual scrolls expose Learn. Do not use item-name/prefix matching or assume all `SpellGrantingItem` instances are scrolls.

Append one `LearnSpellFromScroll` ordinary `BaseAction` alongside Cast. Native use-action cloning already supplies exact item UUID, presentation snapshot, user and charge cost. Preserve Cast as the first existing use. Learn uses no gold, no spell slot, no casting roll and no spell effect; it is a spellbook operation, not a Counterspell target. Use the normal item accessibility/agency rules. Do not invent a separate learn-scroll command or transaction manager.

Eligibility: an active Wizard source; exact authored scroll identity on the admitted Wizard list; not already in that Wizard's effective book; sufficient shared slot capacity for a leveled spell; legal item custody/use and remaining charge. A spell known through Sorcerer is still learnable into the Wizard book. An upcast Fireball scroll teaches base Fireball, not a permanent higher-rank spell. Spike Growth remains castable from its scroll but is not learnable by Wizard.

Consume exactly one scroll through existing finite-charge admission. Capture the taught identity before charge commitment: the last-charge path retires the item before `_apply`. Revalidate Wizard/book/rank eligibility at the final admitted boundary so a stale Learn after another Learn/Cast/transfer cannot spend a scroll without gaining knowledge. Commit one book change and one native charge use; do not call `consume_charge` a second time. Publication exceptions after an accepted commit must not permit replaying the same item use.

The item's Learn action must not import the high-level grant/reconciliation module. A dependency-safe book mutation and a narrow native spellbook-change fact let the already installed Wizard composition handler create a learned-cantrip template and let player capture expose book changes. Leveled spells remain book-only until preparation. Include book and prepared entitlement state in current actor snapshots if consumers need it; no UI work.

## 5. Shared divine mechanics and magic classification

Create one shared **Turned** runtime condition/action helper, used by Cleric and Devotion. Reuse Eyebite's path evaluation and native Dash/escape/Dodge/action restrictions, but do not inherit its Frightened child, attack disadvantage, 60-foot expiration or repeat-save rules. BG3 Turned lasts three recipient turns, breaks on actual damage, denies reactions, forces retreat and restricts actions. Eligibility checks the target's ability to see the source; all qualifying creatures in range can be affected, including friendly undead.

Use a separate exact Turned immunity identity and saving-throw cause. Fear immunity/FEAR-save advantage must not automatically apply. Existing Frightened or Turned from another source must keep independent ownership; movement restrictions must not force illegal terrain/wall crossings. Escape-restricting effects, blocked paths and no legal retreat need real action tests. Dodge fallback is an explicit SRD safety fallback when fully blocked, not a claimed documented BG3 rule.

Follow BG3 separate `channel_divinity` and `channel_oath` pools; no accidental shared-SRD pool in a Cleric/Paladin multiclass. Cleric uses 1 at 2, 2 at 6 and SRD extension 3 at 18 per short/long rest; Devotion one Oath charge per short/long rest. Use max-capacity contributions and preserve spending across level upgrades.

Keep class effects and spells distinct. An action can be magical without being a spell. Use native ACTION effect origin for class actions; Counterspell/Globe must not treat them as rank-one spells. Mark actual magical contributions explicitly and apply existing Antimagic decisions to them; do not give every class feature a MAGICAL tag just because it belongs to a divine caster. Structural proficiencies/ASI/styles/Extra Attack and ordinary save auras need no spell wrapper. Purity of Spirit explicitly duplicates a spell effect and needs appropriate magical suppression but no spell-slot/Counterspell entitlement. Divine Intervention can use the existing DEITY exception when its divine origin is deliberately declared. No Globe/Antimagic redesign is planned.

## 6. Cleric and Life Domain: feature implementation and acceptance

All rows include removal/rollback through the Cleric receipt, preservation of independent owners, and native action discovery/profile metadata where applicable.

| Feature and level | Runtime plan and references | Required setup and assertions |
| --- | --- | --- |
| Spellcasting, 1 onward | Full WIS source; shared preparation, rituals and slots from section 3. Three cantrips initially, fourth at 4, fifth at 10. | Build real Cleric1/3/5/11/17/20. Exact ranks, spell count, WIS DC/healing, total-level cantrip scale. Reject foreign/unimplemented spells. |
| Divine Domain, 1 | Require Life in authored subclass choice; direct features/spell pairs, not a generic domain runtime. | Wrong/late/missing subclass choices fail pure validation without runtime leakage. |
| Channel Divinity, 2/6/18 | Native resource and concrete Turn Undead/Preserve Life costs. | Spend one option then the other; pool shared between Cleric options, separate from Oath. SR/LR recovery; level upgrade/removal retains used charges. |
| Turn Undead, 2 | Thirty-foot WIS-save burst and shared three-turn Turned condition. | Undead at boundary/outside, friendly undead, blind target, ordinary foe, failed/successful save, fear immunity, actual Turned immunity, escape/Dash/Dodge/no reactions, expiry and damage break. |
| ASI, 4/8/12/16/19 | Existing exact ability/feat grants, same supported Lucky option. | +2 or +1/+1 limits, cap20, duplicate feat rejection, WIS changes update DC/prep; rollback preserves HP/slots and other class modifiers. |
| Destroy Undead, 5 | BG3 4d6 radiant on successfully turned targets, not CR-based instant destruction. No invented post-12 CR upgrade mixed into this profile. | Deterministic 4d6, successful saves/immune targets no bonus, radiant resistance, death cleanup. Own damage resolves before arming the newly applied Turned damage-break rule; subsequent external damage breaks it. |
| Divine Intervention, 10 | Four bounded variants in section 9, one permanent use. BG3 replaces SRD chance/GM selection/seven-day cooldown; level20 grants no extra use under this profile. | All branch, usage, respec, rejection and ownership cases in section 9. |
| Domain Spells, 1/3/5/7/9 | BG3 pairs in table below, always prepared outside budget. | Every pair available at exact level, duplicate selected/domain entitlement only once per source, survives preparation replacement, lost at correct level removal. |
| Bonus Proficiency, 1 | Exact heavy-armor proficiency source, not a permanent label condition. | Heavy armor usable with Life; remove source without removing Paladin/origin proficiency. |
| Disciple of Life, 1 | Existing HealEvent interception: add 2 + effective spell rank to qualifying spell healing from this caster. Repair exact source/provenance seam in section 10. | Cure Wounds/Healing Word and mass heals at multiple slots; fixed Heal; no potion/Lay Hands/Preserve Life/Goodberry-item recursive bonus. Original spell source/ability retained. |
| Preserve Life, 2 | BG3 thirty-foot allied burst healing 3 × total character level per eligible ally; Action + one Divinity. Native healing/cure profiles. | Cleric2 versus Cleric2/Fighter4 gives6 versus18 each; full-HP cap; no undead/construct; correct allies/range; blocked healing; no Life-spell bonuses. |
| Blessed Healer, 6 | BG3 heals caster 2 + spell rank for each other qualifying recipient actually healed. No per-cast dedup ledger. Trigger from committed heal result, mark its own heal nonspell. | Multi-target heals grant per-other-recipient self healing; self-only, zero/blocked healing and class/item heals do not trigger. No recursion with Disciple, Beacon or another Cleric. |
| Divine Strike, 8/14 | Weapon-hit radiant packet, 1d8 then2d8, once on own turn. Native hit-rider/Smite packets and turn resource. Toggle/automatic policy fits existing handler controls. | Critical doubles dice; first/second eligible weapon hit, ranged weapon, unarmed/spell exclusion, reaction attack off own turn, coexistence with Divine Smite/Hunter's Mark, exact shared allowance. |
| Supreme Healing, 17 | Maximize this caster's actual spell-healing dice, preserving flat modifiers; Beacon of Hope is the reference, not a copied recipient-wide buff. | Cure/mass heals, upcasts, Beacon overlap (no duplicate maximization), nonspell potion/hit-die exclusions, fixed Heal unchanged, chosen ongoing-heal behavior. |

| Cleric level | BG3 Life domain pair | Difference from SRD 5.1 |
| --- | --- | --- |
| 1 | Bless; Cure Wounds | Same. |
| 3 | Aid; Lesser Restoration | Aid replaces Spiritual Weapon; Spiritual Weapon remains available as an ordinary Cleric preparation. |
| 5 | Revivify; Beacon of Hope | Same pair. |
| 7 | Guardian of Faith; Death Ward | Same pair. |
| 9 | Greater Restoration; Mass Cure Wounds | Greater Restoration replaces Raise Dead. |

## 7. Paladin and Devotion: feature implementation and acceptance

| Feature and level | Runtime plan and references | Required setup and assertions |
| --- | --- | --- |
| Divine Sense, 1 | BG3 BA, one/SR, two-turn attack advantage against Celestial/Fiend/Undead. Native contextual advantage. | Eligible/other creature, attack/spell-attack where applicable, ordinary disadvantage cancellation, duration, SR recovery; no invented terrain detection. |
| Lay on Hands, 1 onward | BG3 three variants: lesser heals2 × Paladin level for1 charge, greater4 × level for2, cure removes eligible disease/poison for2. Action/touch; charges3 at1,4 at4,5 at10/LR. Keep5 beyond12 rather than inventing more BG3 upgrades. | All modes, charge costs, class versus total-level scaling, zero-charge rejection, range, undead/construct exclusions, disease-tagged effects, no removal of unrelated poison damage traits, no Life spell bonuses. |
| Fighting Style, 2 | Reuse Fighter predicates/processors for four eligible styles, with Paladin bindings/receipts. | Defense armor gate, Dueling/offhand eligibility, GWF die replacement/critical interactions and Protection shield/range/reaction. Reject selecting an already owned equivalent Fighter style. |
| Spellcasting, 2 onward | Half-caster CHA source, preparation and shared slots. No automatic cantrips or extra ritual entitlement; BG3 ritual-flagged prepared Silence still casts slot-free outside combat, just as an entitled Sorcerer ritual does. | Paladin1 has no casting source/slots; Paladin2 onward own rank/prep; shared high slots upcast low Paladin spells without preparing high Paladin spells early. |
| Divine Smite, 2 | Reuse shared automatic slot toggles, fixing typed class versus learned-spell entitlements (section 10). | Five toggle ranks share one on-hit decision; highest enabled affordable use, misses/unarmed/ranged/spell exclusions, crit and fiend/undead extra die, shared slots. Class + learned entitlement never double fires; removing one preserves the other. Rage/Globe/AM distinctions. |
| Divine Health, 3 | Exact disease-tagged condition admission guard, owned by class feature; native immunity/condition lifecycle. | Native disease rejected; Poisoned not conflated; origin immunity survives removal; suppression behavior matches declared magical classification. |
| ASI, 4/8/12/16/19 | Existing owned ASI/Lucky rules. | CHA updates attacks/prep/aura values without duplicate modifier installation; cap20 and cleanup. |
| Extra Attack, 5 | Native `AttackMultiplicityGrant` total2. | Two attacks; Fighter5/Paladin5 remains2; Fighter11 stronger3 wins; removal falls back correctly. Does not turn every action/spell into multiple attacks. |
| Aura of Protection, 6/18 | Native moving self/friendly membership; max(1, current CHA mod) save bonus. Ten-foot radius then30 at18. Strongest same aura wins; other save buffs still stack normally. | Edge/range/movement/teleport, every save including death saves, conscious gate, temporary CHA change, two Paladins with different CHA and winner leaving, class removal and zero leftovers. |
| Aura of Courage, 10/18 | Same moving membership with exact fear immunity, radius10 then30. Existing-control policy in section 13. | New fear denied; existing fear handled by selected policy; Turned unaffected; conscious/death/recovery/overlap and re-entry. |
| Improved Divine Smite, 11 | Every eligible melee weapon hit adds1d8 radiant, with native packet identity independent of slot Smite. | All hits versus once-per-turn rider, crit2d8, no spell/unarmed/ranged, class Smite combined exactly once, immunity/resistance and removal. |
| Cleansing Touch, 14 | Action/touch willing target/self; max(1, CHA mod)/LR. Select one recipient-local spell effect graph by exact UUID/origin. Reuse prepared removal APIs; no new Dispel Magic spell required. | Bless/Slow multi-recipient cleanup leaves other recipients; Haste ending consequence; Hold/control parents; no removal of class features/items/nonspell poisons; rejected/stale removal no payment. Area membership eligibility explicitly bounded below. |
| Sacred Oath / Channel Oath | Devotion selected at1 by BG3; native separate one-charge Oath pool; Sacred Weapon and Turn Unholy at3. | Pure selection validation; class progression clean through20; no Holy Rebuke or Oathbreaker subsystem. |
| Oath Spells, 3/5/9/13/17 | BG3 available pairs then SRD high-level fallback, table below. | Always-prepared exceptions and source duplicates; report missing Commune honestly. |
| Sacred Weapon, 3 | Action/Oath charge, exact weapon buff10 turns; current wielder CHA attack bonus, magical weapon and native light, per BG3. Use exact item ownership and Magic Weapon/Continual Flame references. | Weapon swaps, handoff/current holder CHA, no bonus to another weapon, magic weapon coexistence, duration, original grant removal, item destruction, AM suppression and restored light/bonuses. |
| Turn the Unholy, 3 | Shared Turned against fiends/undead,30ft, WIS using exact Paladin CHA source; Oath cost. | Same control tests as Cleric; Celestial excluded; Cleric WIS does not override CHA; no Destroy Undead damage just because owner also has Cleric5. |
| Aura of Devotion, 7/18 | Moving charm immunity,10ft then30, conscious gate. Existing-control policy in section13. | Charmed and spell-specific charm parents, source types, independent immunity sources, two auras and class/source departure. |
| Purity of Spirit, 15 | Permanent owned equivalent of Protection from Evil and Good's target defenses, no concentration/action/slot. Reuse source-type predicates and immunity contributions; spell purge adaptation is not automatically rerun every tick. | Relevant creature types only, attack disadvantage, charm/fear defense, overlaps with the spell, AM resume, class removal preserves actual spell. No possession simulation. |
| Holy Nimbus, 20 | Action,1/LR,10 turns; bright30/dim60 moving light, enemies at start take10 radiant; owner's saves against fiend/undead **spells** have advantage. | Start versus entry cadence, ally immunity, light radius, moving caster, source-type/spell filter, ordinary fiend weapon poison save unaffected, Radiant resistance, duration and rest. |

Aura implementation uses `MembershipAreaCondition`/`SpatialConditionMembershipSource` directly. Pass Without Trace/Aura of Life are behavioral references, not parent classes carrying spell identity/magic defaults. Reevaluate source consciousness, life state, faction, movement, suppression where relevant, radius and dynamic CHA. Strongest-winner fallback must survive suppressed/removed providers; Heroes' Feast and Magic Weapon overlap tests are useful references.

Cleansing Touch lists directly recipient-applied spell roots/branches whose exact removal actually ends that spell on that creature. Do not offer a field's transient membership child if its zone would immediately recreate it. Do not end the remote caster's entire Concentrating root to clear one Bless/Slow recipient. A real spell-area cancellation service is outside this feature; record unsupported area-only effects instead of falsely displaying success. Preflight the complete selected removal and normal ending consequences before spending its charge.

| Paladin level | Oath pair | Source |
| --- | --- | --- |
| 3 | Protection from Evil and Good; Sanctuary | BG3/SRD. |
| 5 | Lesser Restoration; Silence | BG3 substitutes Silence for Zone of Truth. |
| 9 | Remove Curse; Beacon of Hope | BG3 substitutes Remove Curse for Dispel Magic. |
| 13 | Freedom of Movement; Guardian of Faith | SRD beyond BG3 cap. |
| 17 | Flame Strike; **Commune unavailable** | SRD; Commune is absent and requires RP answers. See section13. |

## 8. Wizard and Evocation: feature implementation and acceptance

| Feature and level | Runtime plan and references | Required setup and assertions |
| --- | --- | --- |
| Spellcasting/book,1 onward | INT full caster; level choices, scribed knowledge, preparation and BG3 rituals from sections3–4. | Wizard1/2/3/5/11/17/20, exact level choice counts, prepared capacity, shared-slot scribing exception, lost Wizard access with retained book, source-specific INT and total-level cantrips. |
| Arcane Recovery,1 onward | BG3 out-of-combat Action; LONG_REST recovery budget ceil(Wizard level/2), each recovered slot costs its rank, no rank6+. Reuse native slot-cost recovery, not slot capacity growth or SP conversion. | Recover mixed ranks within budget; partial expenditure persists; no overfill/currently-full rank/no budget/no combat; Wizard level not total level; slots shared with other classes; short rest does not refresh budget. |
| Arcane Tradition,2 | Require Evocation exact choice. | None before2; wrong subclass rejected; own school features/remove events. |
| ASI,4/8/12/16/19 | Existing choices and INT modifiers. | Prep capacity and damage feature values follow INT; cap20/Lucky duplicate/receipt cleanup. |
| Evocation Savant,2 | Descriptive feature only: learning is free by human instruction, so there is no cost to discount. | Learning costs zero for every school and spends only the scroll. No dummy gold resource, fake bonus or extra spells. |
| Sculpt Spells,2 | A source-owned handler cancels only an allied qualifying AoE recipient application at native EXECUTION before the spell runs; no ally save or rider occurs. Single-target Evocations are unaffected. Retained field contacts use the equivalent generic application admission, and preview queries the same passive predicate. | Fireball/Cone/Lightning with allied caster/ally/enemy, enemy save normal, an already ally-targetable single-target Fire Bolt remains legal; Magic Missile keeps its existing enemy-only targeting, other-school Acid Splash unaffected, persistent Wall of Fire spell contact, environment surface boundary below. |
| Potent Cantrip,6 | Save-based cantrips deal half damage on a successful save, across source/school; no extra rider on success. A class-owned handler changes the native successful-save damage fraction from zero to half while preserving save success and failure-only rider exclusion. | Acid Splash, Poison Spray, Sacred Flame, Vicious Mockery; saved damage floor after spell modifiers; Vicious Mockery disadvantage not applied on save; Fire Bolt/Ray Frost misses remain0; multi-target independent saves; immunity/resistance. |
| Empowered Evocation,10 | BG3 INT bonus to each Evocation damage instance from this actor, including other class sources, cantrips and native scroll casts. Keep the actual casting source's DC/ability. A class-owned handler modifies native raw damage packets before save reduction and affinities, as specified in section10. | Magic Missile each dart, Scorching Ray each hit not miss, Ice Storm components, Cleric Guiding Bolt source WIS + separate INT damage, scroll Cast, no bonus on ordinary weapon/rider/environment damage; coexistence with Sorcerer affinity without changing its once/cast cadence. |
| Overchannel,14 | SRD fallback: opt into a class-owned damage-dice maximizer handler for a Wizard-source spell of effective rank1–5; first use/LR no recoil, later use n costs n d12 necrotic per rank, starting n=2. Preserve accepted cast choice for retained spell damage. | First/second/third uses, real successful long rest resets; rejected rest/DI bounded recovery do not; class removal/re-add before and after rest; multi-ray/target only one recoil, upcast rank6 rejected, cantrip/other-class cast excluded, non-Evocation Wizard damage included, ongoing own spell ticks, countered/rejected cast policy, Necrotic resistance/immunity bypass with native death/concentration. |
| Spell Mastery,18 | Choose one rank1 and one rank2 Wizard-book spell. Prepared base-rank cast can skip slot; upcasts remain paid. Reuse one source spell template's typed cast variant/cost mode. | Base free at zero remaining slots, unprepared unavailable, other class copy remains paid, upcast paid, learned reaction spell eligible through shared source-aware reaction cost rules, choices supplied through the existing level-choice path; later reselection needs the SRD eight-hour study rule or an explicit bounded adaptation, rather than an invented BG3 level18 rule. |
| Signature Spells,20 | Two distinct rank3 book spells, always prepared outside budget, each one free base-rank cast/SR. Native independent named resources and cast variants. | Two separate charges, ordinary paid casting remains available, no free upcast, SR/LR reset, overlap with selected/book knowledge, reaction spell case, removal and re-add preserve current rest expenditure policy. |

Sculpt Spells protects from the actor's qualifying spell applications, not from every fire/cold/environmental hazard on the map. Ordinary secondary surfaces are independent native environmental effects and remain dangerous unless they retain explicit qualifying spell-application provenance. Persistent actual spell fields retain caster/school identity and apply Sculpt at their contacts. This boundary must be tested and described; do not create blanket fire immunity or spoof automatic-save events.

Overchannel and the two capstones have no BG3 level14/18/20 implementation to copy. Their source restrictions and cadence must remain explicit SRD fallback behavior, not speculative BG3 features. The use counter survives same-character class removal/re-add until actual recovery. Recoil ignores the specified resistance/immunity through a narrow typed affinity policy; do not subtract HP directly, change Necrotic to another type, or temporarily remove defenses. Preserve temporary HP, concentration, survival/death and factual damage events.

## 9. Divine Intervention: four finite native actions

BG3's menu container is free; **each actual branch costs an Action**. Offer four action variants/facets using existing discovery, with one shared permanent use at Cleric10. Do not implement a GM prompt, percentile success roll or seven-day calendar.

### 9.1 Shared permanent usage

Add a plain neutral `permanent_feature_uses` value to build/runtime character state, keyed by exact semantic feature ID, with Divine Intervention as its delivered consumer. No lifecycle manager, global UUID ledger or class-dispatch method on Entity. A NEVER-recharging resource still supplies normal affordability; initialize it spent if the permanent value is present. Removing/readding Cleric never clears that value. Commit it with the accepted native action's cost/effect admission, not during discovery/preview. Rest, revival and Opulent Revival cannot restore it.

Current direct builds do not supply automatic durable campaign identity. Explicit rebuild/import must carry this value and scribed book state. Tests must reconstruct from captured values, not claim persistence because the original Python object survived. Adding a new character database/service is outside scope. If a caller starts a completely fresh character without that state, this implementation cannot infer prior adventure use; document the boundary.

### 9.2 Sunder the Heretical

Action/self-centered50ft; enemies make WIS save against exact Cleric source,8d10 radiant, half on success. Use existing save burst/damage delivery and DEITY effect origin. No concentration or spell slot. Test deterministic normal/saved damage, resistance, allies, radius, one-time spending, AM/deity exception and rejected invocation.

### 9.3 Opulent Revival

Action/self-centered60ft. Intact dead allied player companions revive at half of **their own** maximum HP, using native prepared revival and legal placement. Living allies regain HP and expended slots/rest-based resources. Reuse Revivify's eligibility/placement and native recovery owners. Disintegrated remains stay ineligible.

Do not call `Entity.on_long_rest()` blindly: it resets action economy, expires until-rest conditions/items, processes equipment and reduces exhaustion. Recommended bounded adaptation restores HP/slots/rest-recharging resources but preserves current actions/BA/reactions, world time, concentration, existing spell/item durations, exhaustion and NEVER usage. It does not resurrect the dead and then immediately heal them to full. Preserve exactly half-HP revival for dead recipients and full recovery for living recipients. This deliberate bounded departure is a decision in section13.

Admission evaluates actual eligible recipients/placements first; one blocked corpse must not trigger silent item creation or restore the Intervention use. Resolve per-recipient failure explicitly like existing multi-target effects; reject/no-cost only when the invocation itself has no admissible effect. Test mixed living/dead/blocked allies, current action spent, resources including Oath/Divinity/Lucky/Arcane Recovery, slots, intact versus destroyed remains and no refreshed permanent use.

### 9.4 Arm Thy Servant

Action creates a permanent ordinary item, using authored weapon builders and inventory/equipment admission. BG3 Devotee's Mace is +3, simple one-handed d6 bludgeoning plus1d8 radiant, with a BA/LR ten-turn1d4 healing aura. Plan this one bounded profile as the reward; its healing aura is an item action, not a newly invented non-SRD spell. Reuse additional damage packets, item resources, native moving membership and healing.

Auto-equip through native equipment admission if legal; otherwise retain in inventory, with explicit result. Item survives original caster death, class removal, transfer and long rest. The healing action follows current wielder and item charge ownership, uses nonspell healing and does not activate Life spell bonuses. Do not use `CreatedItemsLifetime`. Test inventory admission/rejection, auto-equip conflict, transferable stats/charge, crit extra radiant die and continued ownership after removing Cleric. This is the actual BG3 branch output covered by the requested BG3 rules; it needs no additional permission merely because the item is new engine content.

### 9.5 Golden Generosity

Action creates one ordinary native container on a legal nearby tile with a bounded explicit reward recipe. Recommend four greater healing potions (4d4+4 each) and one copy each of the already implemented Haste, Greater Invisibility and True Seeing potions. This is a **proposed adaptation** of BG3's food/elixir loot, not a claim that its loot table is implemented. Parameterize the existing healing-potion builder for the one new potion profile. No camp-supply, food, money or random loot subsystem.

Use normal container/inventory/world-object admission; no temporary spell-item lifetime. Test actual contents/counts/uses, blocked placement/no-charge behavior, ordinary pickup/transfer and persistence across class removal/rest. If the human prefers the complete BG3 food/elixir table, list its missing item content as additional work before implementation; do not substitute unspecified rewards silently.

## 10. Necessary shared correctness seams

### 10.0 First phase: repair the implemented spell batch

Read the [complete 58-spell ownership review](../SPELL_58_HANDLER_OWNERSHIP_REVIEW_2026-10-15.md). Scope includes every confirmed foreign-owner/identity site and the Aura of Life admission coverage defect, including summon-body helpers; neutral shared ECS capability flags are retained where they already belong to the authoritative native owner. This phase preserves approved spell mechanics and repairs ownership, not a new protection/element/condition framework.

| Repair | Files / proper owner | Implementation and acceptance |
| --- | --- | --- |
| Destroy Water | `spells/transmutation.py`, `spatial/environmental_conditions.py`, native spatial interactions | Publish one factual drying/remove-water interaction. Water-bearing surfaces own their normal partial-footprint removal/transition handlers; remove the spell's concrete surface whitelist. Exercise partial/full/overlapping Wet, electrified, ice, steam and toxin coverage, non-water neighbors and vetoed native removal. |
| Searing Smite and summon Burning versus Wet | `spells/evocation.py`, `monsters/spell_summon_actions.py`, active Wet owner | Declare a separate generic already-Wet incompatibility fact on burns; active Wet installs admission handler. Preserve WET_APPLICATION as an ending trigger, not an admission veto for every marked condition. Already-Wet receives immediate hit/damage without retained burn; newly Wet clears burns; suppressed/independent Wet sources and existing Glyph Sleep behavior remain correct. |
| Resilient Sphere / Disintegrate | Sphere's `evocation.py` owned boundary handler, remove foreign branch in `transmutation.py` and `BaseCondition` flag | Sphere handles the accepted Disintegrate application, removes its exact lease and consumes/redirects the application so occupant remains unharmed and accepted costs remain spent. Test full dispatch, native removal rejection, ordinary creature/object Disintegrate and missing/suppressed Sphere. |
| Feeblemind / Heal | Feeblemind's `enchantment.py` handler, remove foreign branch in `evocation.py` and `BaseCondition` flag | Cure on actually accepted Heal application with exact provenance, including full-HP targets; ordinary healing/rejected Heal do not cure. Preserve Heal's own authored blinded/deafened cures and Greater Restoration categories. |
| Forcecage magical transfer | Existing owned handler in `wall_constructions.py`, factual native spell/transfer metadata | Replace Misty Step/Dimension Door ID allowlist with generic magical-transfer facts. Keep paid CHA escape at PortalTransfer admission and sealed ordinary spell boundary. Exercise both current spells and a generic native transfer consumer without editing the cage. |
| Winter's Breath and summon status helper | `monsters/spell_summon_actions.py` | Replace presentation-name predicates with stable native status identities; own cooling/removal and failed-save Brittle remain technique-specific. Remove name fallback from `owns_fact` where typed identity is available; preserve Healing Vapours' Poisoned switch and Multiattack prerequisites. Test label-independent active statuses, suppressed status, save/Brittle outcomes and ordinary cold damage exclusion. |
| Aura of Life maximum-HP protection | Aura-owned recipient handler, generic max-HP reduction admission, Life Drain request producers | Initial and repeated Life Drain reductions plus the existing HarmSource producer go through one typed factual native admission before modifier mutation. Aura rejects new reductions without erasing existing loss; no Aura predicate in Life Drain. Test initial/repeated reductions, existing loss, suppression/removal, another native reduction request and ordinary max-HP bonuses. |

Before editing, run the existing relevant spell/condition/summon lanes as the baseline. Add focused observable regression cases through normal spells/actions/native admissions; no source-text assertions or tests of private call sequences. Run the combined affected spell lane after the repairs. Anti-slop and anti-OOP reviewers approve the resulting ownership and outcomes before phase2. If further instances of the same error are discovered in this finite batch, repair and record them here; do not broaden into unrelated existing-spell redesign.

### 10.1 Healing and source attribution

`evocation.py::_get_spellcasting_ability_modifier` currently reads the block-wide ability; `_create_healing` never receives the action's exact source. Update those existing helpers/callers so Cleric/Wizard/Paladin/Sorcerer copies retain WIS/INT/CHA correctly. Fixed/no-ability healing stays fixed.

Carry immutable actual spell origin/source and effective rank at the existing `HealRollResultEvent` and `HealEvent` boundaries, propagated by direct healing and retained spell conditions. Do not match `spell_name` or walk old event history to discover what healed. Keep ordinary potion/hit-die/class healing explicitly nonspell. Regenerate's current ongoing tick defaults spell rank to0; repair that provenance rather than letting a missing number accidentally choose the Life-feature rule.

Recommended Life profile: Disciple modifies each qualifying spell heal; Blessed triggers per other recipient actually healed, including retained spell healing; Supreme maximizes qualifying spell dice. Class/item healing has no spell level and cannot recursively trigger these passives. Vampiric Touch heals from its own actual damage; test and state whether that spell healing receives Life bonuses without changing the damage used for its base half-heal.

### 10.2 Class and learned Divine Smite

Current `paladin.py` infers class entitlement from `entity.uuid`; an exact new receipt UUID alone would look spell-only. It also always stamps spell origin and checks Globe at rank1. Replace that inference with a small typed entitlement origin, while preserving the shared per-slot handlers/toggles and current automatic acceptance policy. Class Smite may operate under Rage as allowed by its non-cast nature, is magical for AM, and is not blocked by ordinary Globe as a spell. A learned-spell-only entitlement retains spell restrictions. If both are present, choose an eligible class entitlement once; no duplicate rider or slot payment. This is an integration repair, not a rewrite of Smite or the protection system.

### 10.3 Handler architecture: recipient, damage and save events

**Human correction: all class behavior belongs in its own handlers.** The earlier draft proposed inserting spell-damage adjustment helpers into individual spell roll paths; that proposal is withdrawn. Do not add Wizard/class-feature branches to Fireball, Magic Missile, cantrips, spell conditions, `Damage.get_dice`, Entity or generic delivery helpers. Spells supply their ordinary authored dice/target/save data; the class grant installs handlers and owns their exact removal. A condition may compose its own modifiers/handlers, but another effect's rules must not be hardcoded inside it.

Concrete handler placement:

- **Sculpt:** source-owned handler on the existing per-recipient ActionEvent/SpellEvent EXECUTION published by `BaseAction._apply_target_batch`. Cancel only the allied qualifying AoE application before `_apply`; the rest of the cast proceeds. A generic area-contact application event supports retained fields. This is a small recipient handler, not a new spell pipeline or blanket immunity.
- **Empowered Evocation:** source-owned raw spell-damage handler adds current INT to each qualifying damage instance, before save reduction/affinities. The handler filters immutable authored spell school/origin; another class's casting source/DC stays unchanged. It does not use Sorcerer's once-per-cast affinity claim.
- **Overchannel:** source-owned handler maximizes the original spell dice for an accepted selected cast, and a separate accepted-cast handler accounts for use/recoil once. Retained effects carry factual cast identity, so later damage reaches the same handler. Neither the spell nor its condition checks for Overchannel.
- **Potent:** source-owned native save-damage/application handler sees the actual successful save and authored damage expression, changes only its success damage fraction from0 to1/2, and preserves success/rider semantics. A save without ordinary damage must still reach this generic decision boundary; do not flip success to failure or maintain a four-cantrip feature switch.

`TakeDamageEvent` already offers a shared pre-HP handler boundary, but its current payload alone is insufficient for exact pre-save dice changes: some callers pass only a total, and some have already halved it. Likewise successful-save cantrips currently return without a damage event. Add missing **class-agnostic** raw packet/damage-expression, save-outcome/fraction and immutable source facts at the native roll/application boundary. Reuse the existing result-event replacement contract where it fits. If a producer must migrate to publish the factual native contract, that change must contain no feature test or class-specific computation. A value after halving cannot be reverse-engineered into raw dice.

Required event coverage audit: Magic Missile darts; rays/spell attacks; Fireball/Lightning Bolt/Cone/Shatter/Thunderwave; Ice Storm's mixed components; all qualifying retained fields and portable/delayed casts; and every school of rank1–5 Wizard damage for Overchannel. The four currently installed save cantrips are coverage cases, not a dispatch table for Potent. Instrument a shared boundary once, with these concrete consumers proving it is reached.

Damage handlers receive exact component kind, caster/source, school/base/effective rank, cast/application identity, actual raw rolls or declared expression, and save policy. They cannot accidentally include nested weapon attacks, Smite/mark riders, unrelated retaliation, item-private Acid Flask or environmental surface damage because those retain their own factual origin. Preserve Sorcerer affinity's independent cadence and flat-before-half ordering. Preview queries the same pure eligibility/modification functions with detached factual data; it never runs a mutating live cast or spends a use.

Overchannel use accounting is a plain integer on the existing SpellcastingBlock, incremented by the Wizard-owned handler once per qualifying committed cast. There is currently no SpellcastingBlock rest hook or native rest-completion event: Entity.on_long_rest directly restores its blocks. Publish one bounded generic successful-rest completion fact there, only after actual recovery succeeds, and let the Wizard-owned recovery handler reset the counter. Do not add an Overchannel reset branch to Entity or SpellcastingBlock. No arbitrary huge finite resource represents unlimited later uses. Removing/readding a class before actual recovery must not reset it; retained character-state recovery must also observe a real rest during class absence, without retaining active Wizard damage bonuses. Recoil uses an explicit per-packet affinity bypass through existing damage resolution while preserving HP/tempHP/death/concentration events. Mastery/Signature free casts still qualify; paying a slot is not eligibility.

### 10.4 Free spell variants and reaction spells

Ritual, Mastery and Signature are cost policies on a real source-owned spell cast. Preserve base/effective rank, spell identity, targeting, Counterspell, concentration and school passives. Free base-rank casts remain spells; paid upcasts remain available. Learned reaction ownership currently supports source-specific costs, but Counterspell still directly consumes ordinary slots whereas Hellish Rebuke reads fixed-use facts. Correct that concrete Counterspell selection path and extend the same exact contract for free base-rank Shield/Counterspell rather than install duplicate reaction handlers or automatically remove every slot cost.

## 11. Implementation sequence and review gates

1. **Repair all wrong spell ownership first.** Follow section10.0 and the full58-spell audit, including Wet/summon identities and Aura of Life admission. Record selected defaults and baseline; assign a plan-adherence subagent throughout implementation, plus anti-slop and anti-OOP reviewers. Complete meaningful regressions and independent review of this phase before class code.
2. **Deliver class chassis and aggregate slots.** Add identities/cold tables/receipts/dispatch, three minimal real builds, all level rows, one slot writer and Sorcerer migration. Prove creation, multiclass level/remove and rollback before adding dozens of class actions.
3. **Deliver real preparation/book/scroll workflow.** Source-aware lists, limits, entitlements, BG3 rituals, level book choices, free scribing and Cast/Learn item uses. Prove a real Wizard learns Fireball, prepares it and casts it through choices/server; Cleric and Paladin prepare/cast Cure Wounds with different abilities. Include high-rank Wizard multiclass scribing and retained knowledge.
4. **Deliver shared Turned and Cleric/Life.** Resources, turning/damage, all healing passives and owned domain spells. Repair exact healing provenance with its consumers. Validate affected existing healing/spell tests.
5. **Deliver Paladin/Devotion.** Styles/Extra Attack/native Smite integration, Lay Hands/disease immunity, moving auras, Sacred Weapon/Turn Unholy, Purity/Nimbus and recipient-local Cleansing Touch. Validate previous Smite/weapon/aura/control cases.
6. **Deliver Evocation and high-level Wizard.** Bounded damage/save hooks, Sculpt/Potent/Empowered, Arcane Recovery and SRD Overchannel/Mastery/Signature. Audit every qualifying damage path, not just Fireball. Review the actual spell call-site inventory with anti-slop.
7. **Deliver Intervention branches and permanent state.** Implement all selected explicit reward/recovery policies. Prove class removal/re-add and captured rebuild do not refresh usage or erase scribed knowledge/rewards. This phase may be developed after core classes without blocking their earlier tests; do not mark the complete Cleric done while selected branches remain absent.
8. **Close public path and validation.** Complete builtin descriptors, native choices/profiles/facts, server capture/reduction/replay and generated engine-owned SDKs. Provide one thin deterministic player smoke per class plus Cast/Learn scroll and important multiclass behavior. Write the Godot-facing backend handoff; no NDClient changes.

At each phase, use existing public gameplay/progression boundaries and native ownership. Prefer shared mechanics with delivered consumers over duplicate spell/class pipelines. Stop expanding scope when an issue belongs to a separate spell/world backlog; name it honestly in this plan. Independent reviewers must inspect final behavior and deletion/ownership gaps, not merely count tests.

## 12. Validation matrix

Read HOW_TO_TEST.MD before authoring tests. Use deterministic `fixed_dice_faces`, small maps, real builds/grants, native action discovery/dispatch and explicit HP/resource/condition outcomes. Reuse current progression fixtures and `tests/engine/support.py`; do not prove features by private-helper calls, registry counts alone, production tables as expected values, artificial class flags or source text assertions.

| Test owner / proposed file | Meaningful acceptance |
| --- | --- |
| `tests/progression/test_direct_{cleric,paladin,wizard}_progression.py` | Independent expected1–20 tables, exact choices and first/multiclass grants, HP/ASI/cantrip counts, source ability/rank, upgrade/remove/reapply, active roots and rejected grants. |
| Existing `test_direct_character_{builds,progression}.py` | All six classes via real build path, invalid subclass/choice/source, class events, rollback, current creator policy and total level20. |
| `tests/progression/test_prepared_spellcasting.py` | Budgets, always prepared unions, source duplicates, reaction ownership, BG3 out-of-combat swaps, stale/invalid replacements, ongoing effects surviving unprepare, dynamic ability capacity. |
| `tests/progression/test_multiclass_spellcasting.py` + normal slot tests | Cleric2/Wizard3, Cleric3/Paladin3, Paladin5/Sorcerer1, Wizard1/Cleric4, Paladin1/Wizard1, Fighter/Barbarian cases; explicit slots, per-source access and spent-slot preservation on success/failure/removal. |
| `tests/engine/test_wizard_scroll_learning.py` | Every existing eligible scroll retains Cast and adds Learn; Fire Bolt cantrip, Spike Growth exclusion, other-class known spell, duplicates, upcast base identity, spent shared slots, stale item/class/book, stack exhaustion, rejected/accepted use, zero gold, no cast/slot effect; permanent knowledge/rematerialization. |
| Existing spell item/charge suites | Rings/wands/wearables/Acid Flask unchanged; rejected charge, exact stack decrement, last-unit retirement, equipment/custody and no double consumption. |
| `tests/engine/test_cleric_features.py` | Section6 exact numeric and control cases, Life source/cadence, Turned separate from Fear, Divinity spending and ordinary allies. |
| `tests/engine/test_paladin_features.py` | Section7 variants, exact weapon and slot Smite, shared entitlement distinctions, class resource recovery, styles/multiplicity and Cleansing Touch. |
| `tests/engine/test_paladin_auras.py` | Two different CHA Paladins; edge membership, radius18, conscious/recovery/faction/teleport/death, winner fallback, charm/fear policy, Heroes Feast/Heroism/Protection spell overlaps. |
| `tests/engine/test_wizard_evocation.py` | Direct/save/miss/multi-projectile/mixed-component/retained spell cases, all four save cantrips, true school/source eligibility, Sculpt preview versus runtime, all rank1–5 Overchannel schools, affinity bypass. |
| `tests/engine/test_wizard_recovery_and_capstones.py` | Recovery outside combat and budget, Mastery/Signature actual spell/reaction variants, base versus upcast costs, preparation, SR/LR and no slot overfill. |
| `tests/engine/test_divine_intervention.py` | All chosen branch outputs, exact Action cost, one permanent use, living/dead/blocked recipients, resources/slots versus durations/action economy, item custody and rebuild. |
| `tests/player/test_divine_and_wizard_transport.py` | Real worker choices → preview → command → serialized state/facts/reduction/replay. Native Cast/Learn item uses, no preview mutation, exact source identity, book/prepared facts, low/mid/high class actions and rejection. |
| Architecture suites | New owners respect existing leaf/direct composition policy; cold imports, no content_system/obsolete runtime dependency in direct grants, no late imports/getattr/TYPE_CHECKING evasions. |

Cross-feature cases must include Cleric6/Paladin6/Wizard1 prepared duplicates; WIS/CHA/INT with intentionally different modifiers; Rage plus class Smite versus spell casting; counterspelled spell versus nonspell class action; Globe versus class and spell damage; Antimagic source/recipient boundaries; Heroism/Calm Emotions/Turned; Life bonuses with mass healing/Regenerate/Goodberry/Lay Hands; Sculpt/Potent/Empowered with source changes and Sorcerer affinity; free Mastery/Signature casts with Overchannel; Overchannel with Smite/weapon/surface nested effects; preparation and scribed book across class removal; permanent rewards and DI usage after removal/rebuild.

Run the focused phase tests, then one combined affected lane covering the six direct classes, builds/progression, source primitives, slots/preparation, spell items, relevant spell batches/conditions/movement/aura/summon lifecycle and player transport. Run active architecture checks and the normal typing/protocol generation checks. Broaden once after the integrated implementation; repeat only for actual changes/failures. Existing baseline exclusions/diagnostics must be identified from current runs and kept distinct from new failures. Use the configured uv environment and `--assert=plain --tb=short` to avoid recursive Entity repr failures. Record fresh gameplay qualification during implementation; the earlier planning review is not test evidence.

## 13. Selected implementation defaults and remaining factual checks

The human has already selected BG3 rules and free scroll learning. Do not ask again whether to use BG3 preparation, separate Divinity/Oath resources, shared-slot Wizard scribing, per-recipient Blessed Healer, three-turn Turned or gold-free learning. Those are selected. For the authorized implementation, use the recommendations in the table as explicit defaults: local aura cleansing, bounded DI recovery/seven-potion bounty, honest Commune gap, explicit permanent state, existing general prerequisites and retained over-capacity preparations. Mastery uses the SRD eight-hour study rule at the native time boundary; absence of such a boundary must be reported rather than inventing a calendar. These agent-selected defaults are documented so the human can steer them; no extra approval gate is invented.

| Decision | Recommendation | Dependency |
| --- | --- | --- |
| Existing charm/fear on entering Courage/Devotion aura | Local clear-on-entry plus owned immunity, using current exact control-removal helpers; explicitly label this bounded adaptation. Alternative is suppress-and-resume. Never turn immunity grants globally into destructive removal. | Aura existing-control tests only; other aura behavior is independent. |
| DI recovery meaning | Bounded HP/slots/rest-resource recovery, preserve current action economy/time/durations/exhaustion, half-HP dead revival; do not call full `on_long_rest` midcombat. | Opulent Revival. |
| DI Generosity contents | Use the explicit seven-potion bounty above instead of adding a gold/food/elixir catalog. This is the unresolved reward adaptation; the actual BG3 Devotee mace is already covered by the selected BG3 branch rules. | Golden Generosity only. |
| Devotion17 Commune | Leave its missing spell entry explicitly unavailable; grant Flame Strike and report9/10 oath spells. Do not invent an unrelated replacement or an RP answer engine. | Full exact SRD oath-spell completeness; playable class/features otherwise independent. |
| Permanent state across fresh builds | Carry scribed book and permanent feature use in current build/capture inputs. Do not add campaign persistence; document that fresh callers must retain these values. | Accurate lifetime promise for DI and scribed knowledge. |
| General multiclass prerequisites | Preserve the current creator's existing prerequisite policy unless the BG3 instruction is intended to replace it globally. If changing, remove gates consistently for all six classes and update the existing policy tests; no per-new-class exception. | Cold/live multiclass validation. |
| Preparation capacity falls below selected count | Retain existing selections, reject further swaps until a valid list is submitted; prevent new excess-capacity preparation. Do not silently unprepare spells or end their effects. If strict BG3 behavior differs, record the verified rule before implementation. | Temporary INT/WIS/CHA reductions. |
| Mastery reselection above the BG3 cap | Keep the SRD eight-hour study requirement, through an existing native time boundary if available. If no such boundary exists, decide the bounded out-of-combat study operation explicitly; do not silently make reselection instant or add a calendar service. | Wizard18 reselection only; original choices and free casts are independent. |
| Overchannel timing and retained damage | One use/recoil per qualifying committed cast, including free Mastery/Signature casts; maximize that cast's own retained spell damage too. Rejected precommit invocation spends nothing. Counterspell follows the engine's existing accepted-cost boundary rather than introducing a separate refund rule. | Wizard14 fallback tests. |

The human has authorized implementation after independent approval of the expanded plan. Use these explicit defaults without repeating permission requests. Ask only if actual source study proves a material gameplay choice cannot be resolved within them; continue independent authorized work meanwhile. Ordinary implementation choices and factual native event additions require no separate permission.

## 14. Source references and independent review

Primary rules: [SRD 5.1 PDF](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf), class sections Cleric pp15–17, Paladin pp31–34, Wizard pp50–54, spell lists pp106–114; [SRD 5.2.1 PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf) for additional allowed spell identities, not replacement class progression. The archived Markdown class/spell lists were used as searchable transcriptions and checked against the official PDF; archived implementation examples are not proof of active support.

BG3 behavior references: [Wizard](https://bg3.wiki/wiki/Wizard), [Transcribing scrolls](https://bg3.wiki/wiki/Transcribing_scrolls), [Fire Bolt](https://bg3.wiki/wiki/Fire_Bolt), [Arcane Recovery](https://bg3.wiki/wiki/Arcane_Recovery), [Ritual spells](https://bg3.wiki/wiki/Ritual_Spells), [Sculpt Spells](https://bg3.wiki/wiki/Sculpt_Spells), [Potent Cantrip](https://bg3.wiki/wiki/Potent_Cantrip), [Empowered Evocation](https://bg3.wiki/wiki/Empowered_Evocation), [Life Domain](https://bg3.wiki/wiki/Life_Domain), [Blessed Healer](https://bg3.wiki/wiki/Blessed_Healer), [Preserve Life](https://bg3.wiki/wiki/Preserve_Life), [Turn Undead](https://bg3.wiki/wiki/Turn_Undead), [Destroy Undead](https://bg3.wiki/wiki/Destroy_Undead), [Divine Sense](https://bg3.wiki/wiki/Divine_Sense), [Lay on Hands](https://bg3.wiki/wiki/Lay_on_Hands), [Devotion](https://bg3.wiki/wiki/Oath_of_Devotion), [Sacred Weapon](https://bg3.wiki/wiki/Sacred_Weapon), [Channel Oath](https://bg3.wiki/wiki/Channel_Oath_Charge).

Intervention branches: [Sunder](https://bg3.wiki/wiki/Divine_Intervention:_Sunder_the_Heretical), [Revival](https://bg3.wiki/wiki/Divine_Intervention:_Opulent_Revival), [Arm](https://bg3.wiki/wiki/Divine_Intervention:_Arm_Thy_Servant), [Generosity](https://bg3.wiki/wiki/Divine_Intervention:_Golden_Generosity), [Devotee's Mace](https://bg3.wiki/wiki/Devotee%27s_Mace). Engineering approach/ranks are inferences from the actual repository; a wiki gameplay description is not evidence of access to BG3's implementation source.

Attribution: This work includes material taken from the System Reference Document 5.1 (“SRD 5.1”) by Wizards of the Coast LLC and available at https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License available at https://creativecommons.org/licenses/by/4.0/legalcode.

Review status:

- Anti-slop: expanded complete plan APPROVED on2026-10-15. Phase1 implementation APPROVED after412 passing affected gameplay/transport/recording tests.
- Anti-OOP: expanded complete plan APPROVED on2026-10-15 for ECS/DAG/scope. Phase1 implementation APPROVED after412 passing affected gameplay/transport/recording tests.
- Plan adherence: mandatory active subagent throughout the authorized implementation, including the first spell-repair phase.

## 15. Spell-list inventory appendix

The current SRD5.1 intersection is **57 Cleric**, **18 Paladin**, **99 Wizard** spell roots, including cantrips where the class has them. These are overlapping per-class counts: many roots belong to multiple classes. Class entitlement must use explicit authored lists, because older catalog metadata often omits class membership. This plan does not implement the remaining spell backlog.

The official SRD5.2.1 class lists were checked during this study. The union with installed SRD5.1 eligibility gives **61 Cleric**, **23 Paladin** and **107 Wizard** roots. Additional class-eligible entries are listed below, including older spell roots newly assigned to a class by5.2. Do not infer legality from the current pack ID alone: some existing adaptations' pack provenance is older than the source expansion. Reject non-SRD roots and keep the ordinary preparation budget/source rank rules. Author these finite exact lists in the existing cold definitions; no new registry or automatic import of every BG3 spell is needed.

The following baseline rows are generated from the checked SRD5.1 list/installed identity intersection and serve as an implementation inventory, not test expected values copied from future production tables.


### Installed SRD5.1 class spell roots

#### Cleric: 57

| Spell level | Exact IDs (prefix `spell.` omitted) |
| --- | --- |
| 0 | `guidance`, `light`, `resistance`, `sacred_flame`, `thaumaturgy`, `spare_the_dying` |
| 1 | `bane`, `bless`, `command`, `create_or_destroy_water`, `cure_wounds`, `guiding_bolt`, `healing_word`, `inflict_wounds`, `protection_from_evil_and_good`, `sanctuary`, `shield_of_faith` |
| 2 | `aid`, `blindness_deafness`, `calm_emotions`, `continual_flame`, `enhance_ability`, `hold_person`, `lesser_restoration`, `prayer_of_healing`, `protection_from_poison`, `silence`, `spiritual_weapon` |
| 3 | `beacon_of_hope`, `bestow_curse`, `daylight`, `glyph_of_warding`, `mass_healing_word`, `protection_from_energy`, `remove_curse`, `revivify`, `spirit_guardians` |
| 4 | `banishment`, `death_ward`, `freedom_of_movement`, `guardian_of_faith` |
| 5 | `dispel_evil_and_good`, `flame_strike`, `greater_restoration`, `insect_plague`, `mass_cure_wounds` |
| 6 | `blade_barrier`, `harm`, `heal`, `heroes_feast`, `planar_ally`, `true_seeing` |
| 7 | `divine_word`, `regenerate` |
| 8 | `antimagic_field`, `holy_aura` |
| 9 | `mass_heal` |

#### Paladin: 18

| Spell level | Exact IDs (prefix `spell.` omitted) |
| --- | --- |
| 1 | `bless`, `command`, `cure_wounds`, `divine_favor`, `heroism`, `protection_from_evil_and_good`, `shield_of_faith` |
| 2 | `aid`, `branding_smite`, `lesser_restoration`, `magic_weapon`, `protection_from_poison` |
| 3 | `daylight`, `remove_curse`, `revivify` |
| 4 | `banishment`, `death_ward` |
| 5 | `dispel_evil_and_good` |

#### Wizard: 99

| Spell level | Exact IDs (prefix `spell.` omitted) |
| --- | --- |
| 0 | `acid_splash`, `chill_touch`, `dancing_lights`, `fire_bolt`, `light`, `poison_spray`, `ray_of_frost`, `shocking_grasp`, `true_strike` |
| 1 | `burning_hands`, `charm_person`, `color_spray`, `expeditious_retreat`, `false_life`, `fog_cloud`, `grease`, `hideous_laughter`, `jump`, `longstrider`, `mage_armor`, `magic_missile`, `protection_from_evil_and_good`, `shield`, `sleep`, `thunderwave` |
| 2 | `acid_arrow`, `blindness_deafness`, `blur`, `continual_flame`, `darkness`, `darkvision`, `enlarge_reduce`, `flaming_sphere`, `gust_of_wind`, `hold_person`, `invisibility`, `magic_weapon`, `mirror_image`, `misty_step`, `scorching_ray`, `see_invisibility`, `shatter`, `web` |
| 3 | `bestow_curse`, `counterspell`, `fear`, `fireball`, `fly`, `glyph_of_warding`, `haste`, `hypnotic_pattern`, `lightning_bolt`, `protection_from_energy`, `remove_curse`, `sleet_storm`, `slow`, `stinking_cloud`, `vampiric_touch` |
| 4 | `banishment`, `blight`, `dimension_door`, `fire_shield`, `greater_invisibility`, `ice_storm`, `phantasmal_killer`, `resilient_sphere`, `stoneskin`, `wall_of_fire` |
| 5 | `cloudkill`, `cone_of_cold`, `conjure_elemental`, `hold_monster`, `telekinesis`, `wall_of_force`, `wall_of_stone` |
| 6 | `chain_lightning`, `circle_of_death`, `disintegrate`, `eyebite`, `flesh_to_stone`, `freezing_sphere`, `globe_of_invulnerability`, `irresistible_dance`, `sunbeam`, `true_seeing`, `wall_of_ice` |
| 7 | `arcane_sword`, `delayed_blast_fireball`, `finger_of_death`, `forcecage`, `prismatic_spray` |
| 8 | `antimagic_field`, `feeblemind`, `incendiary_cloud`, `power_word_stun`, `sunburst` |
| 9 | `foresight`, `power_word_kill`, `weird` |

### Installed additions from SRD5.2 class eligibility

These rows add class eligibility only; they do not replace approved spell mechanics or multiply duplicate identities.

| Class | Additional exact IDs and rank | Total union |
| --- | --- | ---: |
| Cleric | `spell.aura_of_life` (4), `spell.sunbeam` (6), `spell.sunburst` (8), `spell.power_word_heal` (9) | 61 |
| Paladin | `spell.divine_smite` (1), `spell.searing_smite` (1), `spell.prayer_of_healing` (2), `spell.aura_of_life` (4), `spell.greater_restoration` (5) | 23 |
| Wizard | `spell.chromatic_orb` (1), `spell.ice_knife` (1), `spell.ray_of_sickness` (1), `spell.dragons_breath` (2), `spell.enhance_ability` (2), `spell.charm_monster` (4), `spell.vitriolic_sphere` (4), `spell.summon_dragon` (5) | 107 |

Shield and Counterspell are included as learned-reaction roots, not overlooked because they have no ordinary clickable SpellAction. Scribed cantrip Fire Bolt is covered explicitly. Conjure Fiend remains excluded as an original non-SRD identity; a similar name is not evidence of spell-list eligibility.


## 16. Implementation record

### Phase1: spell handler ownership repairs

- Expanded complete plan independently approved by anti-slop and anti-OOP reviewers before production edits; plan-adherence monitor active.
- Baseline selected engine/progression lane: **291 passed**,64.27s, source on the Linux worktree and Python3.13 at `/home/tommaso/.cache/dnd-engine/venv`.
- Implemented the finite section10.0 inventory. The maximum-HP inventory also found HarmSource's producer-side Aura guard; it now shares the factual admission with initial/repeated Life Drain. Shared static ECS capabilities remain intact.
- Added compact native committed-application and maximum-HP-admission facts with terminal histories and passive recording contracts. No copied cast/attack presentation events; added archive defaults preserve previous records. Sphere and Feeblemind consume accepted factual applications; spell-specific BaseCondition flags are removed.
- Focused gameplay covers partial/full and independently overlapping drying, native removal veto, a water-bearing native owner outside the old whitelist, separate Wet admission versus Sleep ending behavior, immediate Smite damage, late-vetoed Sphere/Heal, full-HP cure, exact relabeled spell/status identities, repeated/Harm max-HP loss and suppression/removal. Recording tests cover prior optional-field omissions and actual controlled-actor HP/maxHP capture/project/replay.
- Architecture/progression check currently reports **67 passed,13 unrelated failures**. Diagnostics refer to obsolete `game.app`, `server.world_contracts`, `server.api_models`, `server.session` expectations and unchanged presentation-geometry/combat-log/Encounter/server hygiene sources. Their tracked source/tests are unchanged in this phase; missing old paths are also absent in implementation HEAD. Do not repair these unrelated migrations here or report the architecture lane wholly green.
- Final combined affected spell/transport run: **412 passed**,104.91s. Both anti-slop and anti-OOP reviewers explicitly APPROVED phase1 implementation; class phase2 is now open.

### Existing-content inventory correction

The separately composed, already installed SRD5.1 Cleric cantrip `spell.thaumaturgy` was omitted from the original primary-catalog intersection. It is included in the cold Cleric list and direct runtime map; Cleric has57 installed SRD5.1 identities and61 in the5.1/5.2 union. This repairs entitlement coverage without implementing an additional backlog spell.

### Phases2–8: complete class delivery

Delivered the three concrete20-level class/subclass families, first/multiclass
proficiencies/HP/ASI/Lucky, exact receipts, reversible source grants, shared normal
slots, current preparations, Wizard book/scribing, scroll Cast/Learn, free rituals,
all listed class features, all four Intervention branches, actual permanent
rewards and the three ordinary level5 premades. No NDClient work was performed.
The finite adherence reviewer found no planned class feature absent. Commune
remains the documented missing spell identity; no replacement was added.

Feature behavior lives in the owning native processors/conditions. The shared
engine additions expose factual healing, damage packets, paid costs, successful
rests, local application admission and committed membership. They do not dispatch
Wizard/Cleric/Paladin feature identities. The full raw packet producer inventory
includes direct/save spells, missiles/rays, retained fields and strikes, portable
payloads, Flame Blade's native spell weapon and innate Hellish Rebuke. Sculpt's
pure discovery preview reuses its own admission predicate. Environmental
fire/ice/ground consequences retain their own ordinary semantics.

Additional concrete defects found and repaired during independent review:

- Moonbeam's initial manual exposure now asks the same generic application
  admission as later contacts, before allied saves or damage.
- No-op preparation preserves retained spell-owned strike templates. Retained
  attack actions carry their casting ability independently of a removed source.
- Overchannel retains the original selected cast, counts/recoils once per
  accepted original lineage and cannot be newly selected by a later repeat.
  Fire Shield declares its real damage eligibility.
- Committed facts attempt every owning handler before rethrowing observer
  failures. A preceding failed observer cannot reopen permanent Intervention or
  skip accepted Overchannel accounting.
- Paladin aura consciousness, faction, redeployment and live18/remove18 changes
  update native memberships/footprints. Protection contributes to actual death
  saves; Cleansing Touch preserves spending through temporary CHA loss.
- Cleansing's admitted local removal veto spends nothing; Haste keeps its ending
  penalty. Opulent revalidates a prepared corpse's placement before revival.
- Rejected provisional rewards release their exact native block/value/template
  ownership. UsableItem retires its own authored use templates; no registry scan
  or feature-specific core cleanup is used.
- Equivalent Fighter/Paladin fighting styles are rejected in both class orders.
  Paladin's handler styles reuse Fighter's processors/factory with exact Paladin
  provider receipts, including standalone creation without a server gateway.

### Public boundary and explicit operation policies

Player schema10/version1 and both current player SDKs are generated. Discovery
includes exact source/provider/ability for duplicate class spells. Public command
intents include `prepare_spells` and `study_spell_mastery`; controlled HUD sheets
carry the book, preparations, full level choices and permanent uses needed for
an explicit fresh rebuild. Private book/preparation/Mastery/permanent facts are
redacted for nonowners. There is no new durable campaign service.

The existing host previously retired its worker immediately when combat ended,
which made out-of-combat preparation, Recovery and rituals unreachable through
HTTP. The completed bounded session now publishes `outside_encounter`, a live
revision and no turn owner. Existing seat authority admits normal discovery,
preview and native actions for controlled players; `end_turn` is rejected.
The native worker/recording remain live until explicit game end/shutdown, under
the existing service limits. SSE remains open and must not interpret this state
as terminal. Authenticated HTTP, subprocess execution, actual SSE consumption
and ACKs are qualified in `test_prepared_classes_http.py`.

Ordinary turn debits refresh at combat end and between bounded outside-combat
operations; slots/rest resources and effect durations do not. This is an explicit
outside-operation policy, not an invented short/long rest or world-time tick.
Wizard18 Mastery study requires one complete8-hour operation outside combat;
there is no active calendar owner, so it updates the exact two choice/grant rows
and captures the new ledger without adding one. Persist those explicit inputs
when constructing a new character. Item fallback follows BG3's last newly entered
qualifying casting class, skipping noncasting Champion; see the
[item casting ability rule](https://bg3.wiki/wiki/Spells#Item_spellcasting_ability).

### Final qualification and reviews

Python3.13.12: `/home/tommaso/.cache/dnd-engine/venv/bin/python`; source resides
on the Linux worktree. Tests use native builds/actions/conditions and public
HTTP/worker/recording boundaries, following HOW_TO_TEST.MD.

| Lane | Fresh result | Scope / limits |
| --- | --- | --- |
| Combined gameplay/progression | **570 passed**,87.36s | Entire `tests/progression` plus approved lower/higher spell roots, support, controls, fields, payloads, summons, review and ownership suites. |
| Current player layer | **215 passed**,104.78s | `tests/player`, excluding exactly the uncollectable historical `test_application_review.py` which imports removed `game.runtime_protocol`/`game.runtime_worker`. |
| Additional native integration | **177 passed,3 legacy failures**,22.04s | Lower-batch fields/summons/repeats/riders, integrated encounter, condition/life/event lifecycle. The three failures construct CombatLogEntry without its already-required `data` field. Those fixtures and `dnd/core/combat_log.py` are unchanged; the same required field exists at baseline HEAD. |
| Current import/ownership architecture | **17 passed,4 deselected**,6.83s | Includes no local/dynamic imports, no TYPE_CHECKING workarounds, acyclic imports and explicit spatial provenance. Four unrelated old expectations concern removed game/API DTO modules and unchanged presentation-geometry imports. An initially reported new aura provenance failure was fixed with explicit ordinary `effect_origin=None`. |
| Python player SDK | **90 passed**,0.83s | Regenerated schema10 contracts and current SDK behavior. |
| TypeScript player SDK | **63 passed** | TypeScript build and runtime contract tests. |
| Last native item/public closure | **21 passed**,7.11s | After exact item-template cleanup: DI, worker Cast/Learn/replay/rebuild/Recovery/ritual/Study, HTTP/SSE and native item-resource lifetime. |
| Last direct style closure | **32 passed**,8.58s | After handler-style correction: direct progression/styles/preferences/removal, Paladin features/interactions and both new public suites. An independent fresh Python process separately proves both styles work without an installed content gateway. |

The broad gameplay/player lanes precede the final narrow template/style changes;
their affected native/public subsets were rerun after those changes. This avoids
claiming a single untouched full-suite result or adding repeated broad runs with
no new concern. Current player export reports325 definitions/1722 fields, digest
`9bf39fb5a69b67159ddaff81f27071e1b63c4e467fedb9ed489cd9a00324113c`.
The historical `generate_typescript_sdk.py` uses removed server-directory imports;
its obsolete SDK was not revived. The delivered SDKs are the current Python and
`sdk/player-typescript` player contracts. Whitespace/diff checks and new runtime
lint pass; final narrowly affected verification is recorded alongside any later
documentation-only edits.

Anti-OOP: APPROVED after independently reproduced/fixed packet, retained-source,
ownership and committed-observer defects;9 maintained native regressions pass.
Anti-slop: APPROVED after independently verified live HTTP/process/SSE, public
replay/rebuild, all outside-combat operations and rejected-reward cleanup;
15 focused cases pass. The mandatory plan-adherence subagent monitored the work
and confirmed no listed class feature missing. The final style adjustment reuses
the existing concrete handler pattern and was independently APPROVED after
fresh-process creation/preference/removal checks without a content gateway.
The Godot handoff is the companion document linked at the top of this plan.

Final post-format focused class/ownership/public/schema run: **75 passed**,14.44s. New runtime/test Ruff F/E9 checks and `git diff --check` pass. Both final reviewer approvals include all reported corrections; the style fix also has independent fresh-process approval.

Final explicit §3.3 preference closure: a plain runtime-only exact-spell bool map
on SpellcastingBlock preserves disabled Shield/Counterspell across final
unprepare/reprepare. Paladin's still-owned Smite toggles are untouched. Follow-up
prepared/reaction/Wizard/worker/schema lane: **31 passed**,5.24s. Anti-slop
independently APPROVED this narrow change after **6 passed**,0.32s in the prepared
spell lane. This adds no campaign persistence, preference framework or wire field.
