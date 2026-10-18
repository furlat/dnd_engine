# Remaining nonanimal NPCs: native authoring

2026-10-18. Worktree `/home/tommaso/.codex/worktrees/remaining-npc-authoring/dnd_engine`,
branch `codex/npc-abilities-mechanics`, base `5779fecb60f0d65e5b9c70070ed190a17e0f930b`
from `codex/event-native-deltas`.

## Delivery and source accounting

All **123 previously unmapped admitted characters now have native recipes**:
28 Fiends,41 Humanoids (11 Orcs,12 HD Enemies,9 Barbarians,9 Characters),
eight Undead and46 fantasy Zombies. Twenty-five existing identities remain:
17 Goblins, six Fiends, canonical Orc and canonical Skeleton Archer. That
makes **148 distinct native identities** for all148 admitted source designs.
The original180-row inventory and its source columns remain intact.

The [completion ledger](native_authoring.csv) records each source variant,
selected creature reference, selected name, reconciliation and presentation
status. Its dispositions are123 authored,20 retained accepted, five retained
with explicit reconciliation, eight visual holds and24 modern exclusions.
No held/excluded row acquires a recipe. The ledger is audit data; gameplay
continues through existing registered creature declarations and recipes.

| Family | Newly authored | Retained | Native admitted total |
| --- | ---: | ---: | ---: |
| Goblins | 0 | 17 | 17 |
| Orcs | 11 | 1 | 12 |
| Fiends | 28 | 6 | 34 |
| Undead | 8 | 1 | 9 |
| HD Enemy combatants | 12 | 0 | 12 |
| Barbarians | 9 | 0 | 9 |
| Characters | 9 | 0 | 9 |
| Fantasy zombies | 46 | 0 | 46 |
| **Total** | **123** | **25** | **148** |

Exact kits, stats, possessions, spell lists and adaptations are recorded in:

- [Fiend authoring](FIEND_AUTHORING_EVIDENCE.md) and actual materialized
  [Fiend evidence](FIEND_AUTHORING_EVIDENCE.json): all34 source rows.
- [Humanoid authoring](HUMANOID_AUTHORING.md): all41 new kits and canonical
  Orc01 reconciliation.
- [Undead and Zombie authoring](UNDEAD_ZOMBIE_AUTHORING.md): all54 new kits,
  seven formerly excluded fantasy zombie cards and Skeleton Archer reconciliation.

The five older mappings remain their current canonical identities. Demon
Beast1–3 retain Dretch, Corrosive Demon and Dread Demon; the Thornback,
Hookclaw and Ironhide proposals are omitted. Orc01 retains canonical Orc;
its old Iron Cask armor/vanguard proposal is omitted, with the baked artwork
mismatch recorded. Undead5Archer retains Skeleton Archer; the Gravesight
Wight proposal is omitted. These decisions create no duplicate substitute.

## Composition and bounded shared corrections

New kits reuse current actions, traits, spells, possessions, typed Multiattack
configurations and the completed [mechanics batch](MECHANICS_IMPLEMENTATION.md).
No NPC class hierarchy, parallel roster registry, additional combat executor,
new event family, per-hit world scan or stored-event search was introduced.
The two trained unarmed fighters use the selected level11 Monk damage
reference: d8+STR4 per ordinary punch, three punches/action, with explicit
separate equipment defenses. They do not grant a Monk class.

Four bounded existing-owner changes were needed by actual kits:

- Innate spell sources accept their exact `creature.*` provider. They retain
  source UUIDs, fixed spell ranks, owned daily resources, existing casting
  ability and long-rest recharge. Existing class slot and ritual constraints
  remain enforced. Devil Eldritch Blast uses actual caster levels5/11/5/1.
- Possession data can specify an existing finite stack quantity for inventory
  items. Assassins carry one three-dose Assassin Poison stack; the ritualist
  carries two Basic Poison doses. Native application/consumption/transfer and
  exhaustion are exercised. No free coating, infinite supply or ammo model.
- The exact existing Protection reaction remains admissible for selected NPCs
  despite retirement of old PC feature IDs. NPCs compose its existing handler
  with truthful behavior ownership. Paired weapon training reuses the current
  contextual off-hand ability modifier without reviving retired PC classes.
- Authored NaturalAttack dice use structural body size as the native baseline,
  just like intrinsic body weapons. Ogre Zombie Slam stays2d8+4; Enlarge
  adds only its actual size growth. Preview and actual damage share this owner.

The existing creature constructor also accepts explicit save proficiencies,
languages, vulnerabilities and nonmagical attack resistances as creation data;
new recipes use only their selected facts. The existing Multiattack declaration
helper is public so new families use that same typed data contract.

## Verification

All697 cases in the four new family/coverage files pass. The coverage file
compares every original source column and row order, exact123 new source
associations and all148 unique admitted refs, then materializes every admitted
recipe in both default-possession and structure/intrinsics-only modes. Family
checks exercise real attacks and costs, selected Life Drain substitution,
Protection, poison dose exhaustion across transfer, daily spell/reaction uses,
cantrip scaling and the heavy Slam/Enlarge preview-versus-damage contract.

The final33-file native integration batch reports **1,290 passed,22 existing
xfailed and one failed in50.98s**. It includes the four new suites, shared
ability suites, retained Goblins/Fiends/SRD bodies, item ownership/resources,
reactions, source propagation, inventory and model-creation declarations.
The one failure is
`tests/manual/test_51_srd_monster_roster.py::test_authored_srd_encounters_build_through_canonical_recipes`:
its old encounter requests retired `creature.player.fighter@1`. The exact same
test fails with the same missing identity on untouched base5779 in0.19s.
No retired player recipe was restored to make that unrelated fixture pass.

Existing performance/schema-build and sensory-settlement oracle controls:
**five passed in17.18s**. Gallery gameplay builds no deferred model schemas;
indexed sensory settlement matches full recomputation. These are bounded
regression controls, not an overall latency certification. The existing Help
and damage-preview checks in the integration batch also assert no events on
discovery/preview reads.

Independent inventory/icon qualification: **10 passed and two failed in2.57s**;
clean5779 produces **10 passed and the same two failures in2.47s**. The static
icon ledger lacks closure over the existing catalog as well as new entries;
the tamper fixture fails at that same earlier closure check. Current-client
portrait/icon work is not concealed as completed native work.

Commands use Python3.13.12 and the isolated existing environment:
`env UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/npc-mechanics-venv uv run --no-sync python -m pytest`.
Final logs: `/tmp/npc-authoring-final-regression.log`,
`/tmp/npc-authoring-baseline-encounter.log`, `/tmp/npc-authoring-performance.log`.
`git diff --check` passes. Earlier mechanics-only known failures retain their
separate baseline comparisons in the mechanics record.

Source and ECS review evidence is in
[ANTISLOP_REVIEW.md](ANTISLOP_REVIEW.md) and
[ANTIOOP_ECS_REVIEW.md](ANTIOOP_ECS_REVIEW.md). A separate same-task
plan-adherence agent supervised implementation and independently checked
all180 source rows and the exact123 new source-to-recipe associations.

## Presentation and balance status

Native phases0/2 are complete. Current-client phase3 remains pending: rigs,
pose/attack/cast mappings, frame-inspected contact clocks, playback rates,
facings, layers, pivots and in-client validation need the separate client
checkout described in the plan. Existing25 mappings are historical association
evidence, not renewed playback certification. No artwork was imported, moved
or packed in this backend batch. The static icon ledger's existing closure
failures remain recorded separately; no icon/portrait certification is claimed.
Threat/CR and old team XP remain **uncalibrated** for the final adapted kits.

### Existing artwork recovered after the human's source pointers

The [asset recovery record](ASSET_RECOVERY.md) narrows the pending artwork work.
Matching source portraits already exist and are installed for141/148 admitted
NPCs:25 retained native assignments and116 source-key images awaiting their new
NPC identity associations. The updated combined delivery now supplies the
other seven Radioactive zombie portraits; all148 admitted NPCs have source art.

The user-provided combined October15 handoff contains both spell batches,
190 new icons and19 portraits, including the seven zombies and five formerly
missing NPC/Unarmed icons. Together with the older bank,
actual source files cover all181 declared spell roots and the six additional
SpellCatalog composition rows. The57 new root drawings
are not yet installed in the inspected client:35 have exact native icon keys,
22 use explicit semantic artwork keys requiring association. Full CSVs record
the native IDs and actual source/client file locations. No new artwork or
client integration was performed during this recovery search.
