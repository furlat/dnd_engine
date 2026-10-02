# Item-first roster inventory and composition

October 2 read-only study. Scope: all 150 retained fixed-art characters, existing
item integrity, candidate modular equipment and a minimal composition design.
No new item mechanics, creatures or production artwork are installed by this study.
Scenario redesign and wall rendering remain outside this lane.

## Inventory and visual evidence

The canonical direct builder table contains 289 items: 153 environment, 47 weapons,
44 apparel, 18 armor, 2 shields, 9 consumables, 9 spell items, 6 gear and 1 equipment.
The cold definition maps contain 46 weapons and 64 wearables. Assassin's Dagger has
a separate builder. These counts describe different catalog views, not duplicates
that should automatically be deleted.

The modular visual ledger contains 77 categories and 205 supported named variants.
Rusty Blade is an unsupported category with zero variants. A supported ledger row
is not proof that its sheets are installed or that every action has valid artwork.
Presentation variants must remain separate from native magic properties. Raw vendor
variant IDs are not globally unique; preserve category-qualified identities.

Private review: `.runtime/gear-study-20261002/index.html`; matching evidence:
`data/item-candidates.json` in that directory. All 150 roster rows are present with
observed gear, proposed kit, existing item candidates, missing/decision candidates,
modular layer names and current directory availability. All eight roster contact
sheets and four modular contact sheets were viewed. Inspection covers sampled
poses; this is not a certification of every combat frame, direction or hand.
The generator matches named attacks in proposed kits and declared armor choices
in adapted and authored kit formats. Its item details contain the 110 cold
weapon/wearable records, with category-qualified specific visual variants; the
separate `data/direct-builder-inventory.json` lists all 289 canonical builder IDs,
including behavioral items absent from that cold subset.
Removed source weapons are not grounds to grant a possession. The original full
kit remains visible to review ambiguous automated matches.

Modular samples use the vendor archive's untinted Idle layers in two directions,
not a production-rendered animation. Directory availability is a preliminary
check, not complete clip coverage. Armor silhouettes cannot establish exact armor
grade, AC or magical properties. Clothing/accessories not enumerated in a proposed
kit remain a separate appearance pass, not automatically absent possessions.

## Existing mechanical candidates

| Depicted/proposed item | Existing native identity | Visual caveat |
| --- | --- | --- |
| Club | `weapon.club` | Ledger uses tinted light-hammer `Melee10`; approximation, not exact club |
| Dagger | `weapon.dagger` | Inspect hand and orientation; don't infer thrown-mode coverage |
| Handaxe | `weapon.handaxe` | Main-hand axe candidate; off-hand dagger substitute isn't equivalent |
| Mace | `weapon.mace` | Paladin's rounded/spiked head also warrants Morningstar comparison |
| Quarterstaff | `weapon.quarterstaff` | Crooked caster staffs/focus tips differ; optional native focus semantics |
| Spear | `weapon.spear` | Existing thrown/versatile capability gaps remain |
| Sickle | `weapon.sickle` | Off-hand visual may be a dagger approximation |
| Battleaxe | `weapon.battleaxe` | Size and one-/two-hand use need authored hand mapping |
| Greataxe | `weapon.greataxe` | Long polearm-like head must be checked against full attack frames |
| Greatsword | `weapon.greatsword` | Oversized cleavers need explicit silhouette and transferable representation |
| Longsword | `weapon.longsword` | Keep distinct from short sword and magical variants |
| Shortsword | `weapon.shortsword` | Two blades require actual hand membership, not duplicate unnamed layers |
| Scimitar | `weapon.scimitar` | Broad curved cleavers are candidates, not proof of stock weapon size |
| Trident | `weapon.trident` | Existing thrown/versatile capability gaps remain |
| Shortbow | `weapon.shortbow` | Requires two-hand/ammunition semantics and action coverage |
| Longbow | `weapon.longbow` | Same; visible quiver isn't proof of unlimited ammunition |
| Shield | `shield.shield` / `shield.wooden` | Select depicted material/shape; keep don/doff and hand conflicts |
| Plate | `armor.plate` | Gameplay grade proposal, not inferred from pixels |
| Half plate | `armor.half_plate` | Same |
| Scale mail | `armor.scale_mail` | Same; shared modular silhouettes may be approximations |
| Studded leather | `armor.studded_leather` | Same |
| Leather | `armor.leather` | Same |

Reuse ordinary bases; creature ability bonuses and extra dice do not automatically
become magical equipment bonuses. Full proposed kits contain creature-specific
Multiattack, Brute, poison and spell proposals; none are approved by an item name
match. Body horns, forearm blades, teeth and hide are not detached weapon loot.
Bare-hand characters do not receive a hidden sword to satisfy a source stat block.

## Additions and unresolved matches

| Artwork | Required item decision | Modular comparison |
| --- | --- | --- |
| Enemy `1Hammer` | Maul base missing; large two-handed hammer | Warhammer candidate has different scale/hand silhouette; exact transferable art not established |
| Enemy `2Shooter`, `7Sniper` | Firearm-like barrel; Musket proposal requires explicit rules choice | Crossbows are comparisons, not an approved gun substitute; ammunition/loading capability absent |
| Top `Zombie Worker01` | Crowbar-like hooked red tool; utility/improvised attack authoring | Club/hammer aren't exact visual matches |
| DemonSpawn1 / DemonSpawn11 | Passive short wand/focus possession candidates | Charged spell wands must not replace innate creature casting |
| DemonElite3 | Dark held blade-like silhouette versus claw-only kit | Reconcile using combat frames before binding an attack or inventing loot |
| Top `Zombie Swamp09` | Two short blades | Verify both hands and source multiattack versus ordinary two-weapon eligibility |
| Character `4Paladin` | Mace/Morningstar candidates | Rounded/spiked pale head; no resolved sword blade |

Goblin 04, 06 and 16 visibly have shields in the sampled contact sheets; their
short observed-gear text omits these, while the proposed kits include Shield.
This is an observation metadata correction, not evidence to delete their shield.
DemonBeast forearm blades are anatomy candidates, not inferred equipment.
Zombie clothing remains appearance evidence, not a list of lootable armor grants.

Ordinary detachable items retain legal native transfer. Visual acceptance requires
matching representation for the receiving holder and the original fixed-sheet
holder after removal. When a
specific item is truly intrinsic, owner-bound, conjured or spiritual, record that
native physical fiction and its lifecycle. Missing artwork alone does not create
an arbitrary removal ban, death destruction or restricted action. Fixed-sheet
armed pixels cannot disappear through the modular `HIDDEN` equipment policy.

## Existing item correctness findings

| Finding | Evidence / consequence | Required acceptance case |
| --- | --- | --- |
| Intrinsic gear loses its physical meaning | `creature_possessions.py:40–61` filters grants; natural bite/hide become pickable ordinary items. Public probe can equip, unequip and drop wolf bite/hide | Native removal/replacement/inventory/drop/pickup reject true intrinsic anatomy; ordinary loot remains legal |
| Assassin's Dagger affects another weapon | `authored_item_builders.py:105–149` checks wielder, not participating weapon | Dagger bonus only on its own eligible attack; bow/off-hand/other-item attack stays unchanged |
| Coating cleanup is damage-type based | `consumables.py:411–427` removes a matching packet without exact ownership | Two same-type independent contributions; removing one preserves the other regardless of order |
| Coat lifetime belongs to old wielder | Item UUID exists but condition targets applying entity | Transfer, destruction, expiration and optional concentration have explicit item/source ownership |
| Magical wearables cannot declare magic | WearableDefinition lacks magical flag; Spellblade Crown +3 CHA materializes nonmagical | Crown's intended native magical identity and item-directed spell interactions; ordinary apparel remains nonmagical |
| Two-handed reservation only covers melee | `equipment.py:399` omits ranged off-hand reservation | Bow/crossbow cannot coexist with an occupied conflicting hand; preserve shield transactions |
| THROWN/VERSATILE are underimplemented | Flags exist, but one attack range/damage mode | Authored melee/thrown and one-/two-hand modes retain actual possession and action budgets |
| Ammunition/loading aren't authored | No corresponding property/capability | Decide ammunition supply/loading before firearm/expanded ranged kits; don't claim rule completeness |
| Magical item versus magical damage provenance | `is_magical` protects item-directed Disintegrate; it doesn't establish attack provenance for Stoneskin | Separate accepted item identity from an attack's magical/nonmagical provenance |
| Item behavior uses special subclasses/ID switch | Staff, crown, dagger and stealth armor install bespoke hooks | Move accepted properties to typed shared composers with identical native outcomes |

53 existing tests passed (4.99 seconds): direct item runtime, item inventory/equipment,
equipment domain ownership and recovered item semantics. These construct all
registered direct builders and check existing behavior; they do not certify the
newly exposed lifecycle, ownership and weapon-provenance cases. No unrelated full
suite claim or implementation fix is made by this audit.

## Minimal composition design for approval

1. Keep the existing cold base definitions and canonical direct builder table.
   Author a stable derived item identity referencing one base item plus typed
   property data. Resolve this composition at the content boundary, producing
   the same ordinary native item structure. No new gameplay registry or item
   subclass per enchantment; no mutable prototype objects or renderer imports.
2. Add only the property families needed by existing behavior: attack/damage
   bonuses, additional damage packets, wearer modifiers and conditional weapon
   effects. Reuse existing spell-item/charge and duration/concentration machinery
   rather than rebuilding them under a universal property interpreter. Validate
   property/base compatibility and duplicate/stacking rules when content is loaded.
3. Keep native magical identity, attack damage provenance, visual choice,
   removability and source lifetime separate. A glow/color is presentation;
   +1 or fire damage is explicit rules data. A focus isn't a charged spell item.
4. Every installed contribution retains its own identity, provider/item identity,
   and exact modifier/handler/damage-packet handles. Apply/remove by those handles,
   never by damage type, display name or last matching array entry. Item properties
   belong to the item; equipped wearer effects attach/detach through existing
   equipment transactions. Concentration/source links add lifetime relationships.
5. Conditional attack properties inspect the actual weapon participating in the
   native event, preserving chosen hand, off-hand, reactions and object targets.
   Reuse existing attack routes and budgets; no enchanted-object-attack executor.
6. Physical ownership is explicit cold item data (detachable, intrinsic/bound,
   conjured with declared source lifetime). Enforce it in existing preflight and
   inventory/floor transitions. Destruction/removal uses existing item cleanup and
   events; visuals consume those native transitions.
7. Migrate the existing special items first without changing their accepted rules.
   Resolve genuine rule ambiguities (Crown magical identity, dagger scope, coating
   transfer/sustainer semantics, two-hand conflicts) before adding roster variants.
   Add missing bases only after the matching/lifecycle decisions above. Gear then
   supports ability/condition authoring, and finally all 150 character definitions.

Verification follows HOW_TO_TEST.MD: public engine equipment/attack/condition flows,
not private helper snapshots. Cover repeated equip/unequip, actual-weapon-only
bonuses, concurrent same-type enhancements in both removal orders, transfer,
destruction, expiration, concentration loss and intrinsic/conjured restrictions.
Keep existing Extra Attack/Haste/Slow/Action Surge/Frenzy/off-hand/reaction budgets
and creature/object attack behavior intact. Review implementation as one bounded
gear lane; full roster artwork imports and abilities follow later.

## Independent review

Both independent reviewers approve the corrected read-only study and bounded
composition design. Anti-slop review verified 150 unique roster rows, restored
authored armor/shields, attached conflict decisions, exact specific variant colors
and all 289 unique builder IDs. ECS/anti-OOP review approved canonical ownership,
typed shared composers and preserved native transfer legality. Approval is not
runtime implementation, full animation certification or acceptance of unresolved
item-rule choices. No runtime edits are authorized by this document.
