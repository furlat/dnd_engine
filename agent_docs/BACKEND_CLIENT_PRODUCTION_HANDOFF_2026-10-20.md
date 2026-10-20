# Backend fixes for client production adoption

20 October 2026. Backend handoff to NDClientGodot production ownership.

Sixteen issue groups from the client backend review, plus its subsequent lazy
position-region SDK refusal, now have bounded repairs and regression coverage.
Adopt the committed engine and updated
contracts, then re-record the unchanged legal client cases below. Backend tests
qualify the producer boundaries; production Play and Studio acceptance still
requires the new independent seat recordings and visual checks.

## Engine revision and checkout

- Fixes commit: `09e93c439a3a5735ad06e8c6bc6c841660eb79b1`.
  This includes the earlier producer fixes in
  `a97bb55b0a5138d9b26289c7d58aeb8ee25678dc` and the subsequent SDK repair.
- Active branch in the main engine folder: `feature/rules-checking`.
- Main folder: `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine`
  (`C:\Users\tommaso\Documents\Dev\dnd_engine` on Windows).
- Integration base: `cdfafea0c9645819470dc8f5337a3de2abd401e0`.
  The client's original evidence used the older frozen
  `211b71134ed15c89e62232587381f7e15a5961c3` export.
- The earlier rules-checking worktree remains detached at `a97bb55b0`.
  The local main checkout is ready; no remote push or replacement of the
  client's frozen engine export is claimed.

The handoff document is a subsequent documentation-only commit. Pin the fixes
commit when creating an immutable engine export, and retain the actual source
revision in new recording metadata. Preserve the old recordings as evidence of
the original failures.

## Protocol adoption

Protocol version remains **1**, player schema remains **16**, and the new exact
schema digest is:

```text
2c11d7a9919c8aa9b1490628fff224627f19d6388c3884171d14a4a5cbecea22
```

The additions are optional/defaulted fields, but the existing digest handshake
requires matching generated contracts. Update the client protocol import and
the recorder's SDK from this revision together. Old packets retain empty or
absent operands; importing the new schema does not supply missing historical
facts.

Canonical files are [the schema](../sdk/protocol/player-api-v1.schema.json),
[identity](../sdk/protocol/protocol-identity.json),
[OpenAPI](../sdk/protocol/openapi.json), and
[field ledger](../sdk/protocol/field-ledger.json). Both
`sdk/python/src/dnd_player` and `sdk/player-typescript/src` are regenerated.
The [protocol notes](../sdk/protocol/README.md) describe the additions.

### Lazy position-region SDK correction

The original 78,716-byte targeting Choices response reproduced the Python SDK
refusal before Preview: Drop rows 15 and 16 were available and affordable, with
empty target sets and nonnull regions. Both supported SDK validators incorrectly
required enumerated targets for every available action. Their old fixtures
covered only enumerated choices, so the earlier 91 Python / 64 TypeScript passes
did not establish lazy-region admission.

Both SDKs now follow the native contract: available rows require targets or a
nonnull region, including `{}` with schema defaults. Unavailable rows may retain
region metadata but cannot carry enumerated targets. Affordability, reference,
ordinal, generation and schema checks remain intact. Admission preserves the
payload; it does not enumerate cells or decide whether an aim is legal.

The unchanged original response now passes `validate` and `decode` in both SDKs.
Each SDK has 15 new public-boundary regression cases; the two available-region
cases failed before the fix. Final suites: **106 Python tests, 79 TypeScript
tests and TypeScript build passed**. Four existing native compound-selection /
Preview cases also passed. No schema or identity changed in this correction.
Reinstall/rebuild the recorder's SDK from the fixes commit even if its protocol
identity already matches: the identity does not distinguish this code repair.

After promoting the engine export and SDK together, rerun the unchanged Fireball
footprint and Magic Missile ordered-prefix/undo targeting witness. Its original
failure remains evidence with zero checks and no Preview or gameplay commands;
offline admission is not a successful targeting recording or client acceptance.

## Published facts and producer corrections

| Consumer | Delivered backend behavior |
| --- | --- |
| Dragon's Breath | Existing public condition membership now carries the exact `condition.spell.dragons_breath` owner and `state.energy_type`. Cast, Exhale and concentration retirement retain their native identities. A distinct allied caster/recipient regression verifies ally-owned grant and Exhale, original-caster damage attribution, and removal when the caster ends concentration. |
| Vitriolic Sphere | The initial cast publishes its actual `resolved_area_positions`. Delayed results disclose `source_condition_uuid` for the actual recipient-owned residue when that owner is public. Six recipients and every delayed packet are checked independently in both streams. |
| Sorcerous Burst and Chromatic Orb | Root `SpellFact.damage_types` retains the actual selected element, including misses: seven Burst and six Orb options. A client can select the delivery effect without reconstructing the element from later damage. |
| Portable Freezing Sphere | The accepted throw publishes `ActionFact.target_position` when disclosed. Its explosion retains the actual area centre, geometry and resolved cells. Each seat has its own disclosed facts. |
| Branding Smite, Searing Smite and Ensnaring Strike | The actual child weapon attack completes before the outer spell returns, allowing terminal lineage capture on hits and misses. |
| Magic Weapon and Sacred Weapon | Actual enchantments implement the existing item-effect snapshot route. Equipped-item membership, subsequent attack `source_item_uuid`/`item_effects`, and expiry or concentration removal preserve the exact effect UUID. |
| Blessed Healer and Destroy Undead | Real handlers that emit results and return `None` retain effective-handler attribution. Destroy Undead has its precise behavior binding; the existing route publishes trigger and disclosed emitted lineages. |
| Divine Strike, Improved Divine Smite, Divine Favor and smites | `DamageResultFact.components` retains actual attributed native components before executable damage payloads are detached. See the component semantics below. |
| Frenzied, Hex and Hunter's Mark | Frenzied publishes its actual live same-actor `parent_condition_uuid`. Caster-side quarry sustain owners use existing public status membership with exact apply/remove UUIDs. |
| Prismatic Spray | Each recipient application publishes the actual d8 `prismatic_roll` and selected `prismatic_colors`. Each colour's actual save has `effect_id = spell.prismatic_spray.color_<1..7>`; its damage/condition outcomes descend from that save. Nondamaging colours and both branches of an eight are covered. |

Prismatic adds no synthetic ray cast events. Capture now retains legitimate
children created after a parent save completes, bounded to the operation's
exclusive cursor. Cold capture preserves the same links and cannot borrow a
later completion. The original spell provenance remains attached to damage
rolls and conditions, preserving interception and native rule behavior.

### Damage component semantics

Each attributed component has `source_damage_uuid`, `source_entity_uuid`,
`source_id`, `damage_type`, `incoming_damage`, and `after_affinity_damage`.
The source damage UUID joins the actual native component. These amounts are
**before packet-wide reductions and HP allocation**. Use the enclosing
`applied_damage` for the packet's final HP loss; do not treat each component as
an independently applied HP result. Components list attributed sources, not
necessarily every ordinary base weapon component.

Unidentified sources have null source entity/content identity fields. A wholly
blocked packet emits no positive applied-damage result. Tests cover hits,
immunity, misses, hidden sources, full packet reduction and fresh-process replay.

### Exact condition operands

These fields belong to the concrete condition's `state`; they are not aliases
for a universal meaning of `energy_type`.

| Condition behavior | Fields |
| --- | --- |
| `condition.class.paladin.aura_benefit` | `aura_kind`: `protection`, `devotion`, `courage` |
| `condition.spell.summon_dragon.shared_resistance` | `damage_type` |
| `condition.summon.draconic_breath_cadence` | `breath_type`, and `ready` for the actual free-breath allowance |
| `condition.summon.elemental_multiattack_bonus` | `prerequisite`: `Shocked`, `Prone`, `Burning`, `Chilled` |
| `condition.summon.myrmidon_strike_dice` | `action_id`, `damage_type` |

Cadence readiness is published on grant, consumption, unused expiry and
cancellation. Removal cannot resurrect the condition. Membership or a selector
alone does not prove an action fired; retain the actual action/result ancestry.
Factory's 13 authored breath selectors do not establish 13 native playable
forms: the five actual elemental dragon forms are the worker-tested domain.
Slot-six Myrmidon discovery remains a known gap; the selector tests exercise
actual native summon creation and public capture.

## Discovery and execution repairs

- Ordinary spell discovery offers all implemented Bestow Curse branches,
  Blindness/Deafness forms and the five Protection from Energy elements.
  Submit the actual offered facet/index through the existing selection flow.
- Outer discovery honors the template's dying/dead eligibility. A lawful,
  perceived adjacent DYING patient can be selected for Spare the Dying or
  Stabilize and becomes STABLE without healing.
- Help accepts the actual secondary ally index returned by on-demand Preview.
  The current reproduced failure was `invalid_selection`; the original
  `stale_state` report was not reproduced, so re-check its original sequence.
- Equipped usable items participate in the existing use-action discovery,
  deduplicated by item UUID. Devotee's Mace Healing Incense is reachable with
  its actual item charge and native healing behavior.

## Original client cases to re-record

Use the same legal scenarios and requirements identified in the client review.
The exact failed library cases addressed by these repairs are:

| Cases | Required new evidence |
| --- | --- |
| `spell.branding_smite/baseline`, `spell.ensnaring_strike/baseline`, `spell.searing_smite/baseline` | Accepted equipped casts finish capture with terminal result ancestry. |
| `spell.spare_the_dying/baseline`, `survival.stabilize/heal_and_walk` | Offered real DYING recipient and actual stabilization result. |
| `action.class.paladin.sacred_weapon/expiry`, `spell.magic_weapon/wield_attack_remove`, `spell.magic_weapon/equipped_use_retire_replace` | Exact item/effect membership, use, retirement and replacement according to each original requirement. |
| `action.help_attack/consume_assistance` | Returned secondary selection accepted; exact assistance consumption. |
| `action.class.cleric.divine_intervention.arm_thy_servant/direct_character` | Actual equipped mace offers and executes Healing Incense. |
| `class_feature.cleric.destroy_undead/committed_turning_result`, `class_feature.cleric.blessed_healer/actual_self_heal` | Actual result carries typed passive trigger/source/emitted ancestry. |
| `spell.dragons_breath/{acid,cold,fire,lightning,poison}_grant_exhale_end` | Exact retained grant, selected element, accepted Exhale and matching removal. |

Also re-record the review's 13 selected Burst/Orb projectile originals, Vitriolic
initial/delayed cases, portable Freezing Sphere destination, Prismatic colours,
item/rider interactions and condition-selector families. Original sources are
the client's `agent_docs/BACKEND_REVIEW_2026-10-20.md` and linked fixture
documents. Keep independent faction journals independent: occurrence numbers
are local to each stream. Consume each seat's disclosed values and actual
ancestry, then qualify production Play/Studio before changing its completion
status.

## Validation and remaining work

Full engine sweep: **7,283 passed, 2 failed, 21 xfailed**, one warning,
7,306 collected in 595.29 seconds. Compared with the earlier full sweep,
all 111 added tests passed, 15 previous failures now pass, and no new failing
nodes appeared. This includes 99 handoff regressions plus 12 forced-movement
cases. The final Prismatic provenance correction was validated separately by
276 passing cases; one subsequently added ally-recipient Dragon's Breath case
also passed, bringing new handoff coverage to 100 cases.

At the producer-fix revision: Python SDK 91 passed, Monty 9 passed, and TypeScript
build / 64 tests passed. The later SDK correction's results are recorded above.
Scoped typecheck adds no diagnostics to the baseline's existing 188; capture
has zero. Fireball with faction seats and room re-entry with 31 independent
character seats have zero live-versus-client state differences. Fresh-process
SDK replay with interrupted connection/resume matches state and stamps.

Three sequential ordinary Fireball samples before/after give median command
time 120.078 to 120.738 ms and publication 47.900 to 47.150 ms. Largest packet
grows 2,374 bytes to 133,102; log bytes remain 41,332, with the same 571 native
event versions and six deaths. This small sample shows no material slowdown.

The following remain open and must retain their named status:

- **Bead retained power:** whether to publish retained dice/DC is a presentation
  contract decision. Placement, release and detonation remain usable.
- **`spell.fixture.test_bless/baseline`:** the developer fixture remains outside
  ordinary roster spell grants. Ordinary Bless is not a replacement fixture.
- **`condition.prone/drop_stand_walk`:** voluntary Drop Prone remains excluded
  by current standard-action policy.
- **Hellish Rebuke area/group results:** the older grouped-trigger case remains
  unisolated. Its successful single-target control remains valid.
- **Two ordinary suite failures:** AI semantics for Drop, AllyHelp, HelpAttack
  and DismissSummon; and Dretch missing from the authored roster inventory.
  The 21 existing expected failures remain recorded in the audit.

The old tests often checked native HP/conditions via direct execution without
checking discovery or serialized client fields. Some attribution tests started
with already-populated metadata. New tests exercise the real producers and
observable worker boundaries; existing native rule coverage remains intact.

This commit also preserves the earlier forced-push occupancy correction:
blocking creatures stop ground displacement on the preceding legal cell.
The terrain asset inventory is informational; no new height/support, cliff or
terrain-generation system was introduced.

Detailed issue mapping, tests and limits are in the
[backend audit](audits/BACKEND_HANDOFF_TEST_GAPS_2026-10-20.json) and
[progress record](ENGINE_SINGLE_PASS_PROGRESS_2026-10-17.md).
