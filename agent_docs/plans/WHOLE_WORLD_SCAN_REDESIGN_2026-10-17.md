# Whole-world scan redesign

Date 2026-10-17. Status: **approved by the human 2026-10-17 (D14)** and merged into plan §14.8/§14.4 (v3.7). Superseded here: §2.1 Cleansing Touch and the connectors move to PD1b; §3 `get_target_variants` and §2.1 "Kept: `get_variant_facets`" are replaced by plan §14.4 `facet_domain`/`with_selection`; Q1 decided (destinations = sight ∩ empty ∩ range), Q3 decided (delete), Q2 open. Base `d13e6ad`; refs are base lines.

Rules: single-pass plan §4 (objective vs subjective); one path, old path deleted, no fallbacks.

| Symbol | Meaning |
| --- | --- |
| N | world entities |
| C | perceived creatures |
| E | encounter combatants |
| K | spell conditions per creature |
| L | castable levels |
| T | admitted targets |
| o_r | occupied cells in the chunks overlapping a radius-r box |
| k_r | cells within r |

## 1. One objective spatial query (GridMap)

No radius query exists. Reuse the chunk index `_contact_candidate_cells`, which is maintained at every membership
commit (gridmap.py:2647-2659, chunk 16 at :77). Two reads share **one walk**, beside
`get_contact_candidate_cells` (:2661):

```python
def get_entities_in_bounds(self, bounds: tuple[int, int, int, int]) -> tuple[UUID, ...]:
    """Tile occupants (any life state) in inclusive (min_x, min_y, max_x, max_y),
    ordered by (position, str(uuid)); visits only overlapping chunks."""

def get_entities_within(self, center: tuple[int, int], radius_feet: int) -> tuple[UUID, ...]:
    """in_bounds(center ± radius_feet // 5) kept where grid_distance_feet(center, cell) <= radius_feet."""
```

- **Objective:**
  - Tile membership ⇔ `is_deployed` (entity.py:780-796, 815-819, 834-844), so callers drop `is_deployed`.
  - Intact dead bodies stay members (entity.py:2547-2555).
- **Metric:** the same as range admission (base_actions.py:1338-1343). `circle_positions` (d² ≤ r²) differs and
  isn't used.
- **DAG:** GridMap adds `grid_distance_feet` to its existing `dnd.core.geometry` import; callers already import
  `get_map`.
- **Cost:** O(chunks + o_r log o_r). No other proximity helper is added.

## 2. Sites

### 2.1 Cleansing Touch (paladin.py:1399-1500), discovery

- **Rule** (SRD 5.1): end one spell on self or one willing creature you touch. Code: `self_or_allies`, reach 5,
  `TOUCH_CONTACT`, spell in `cleansing_candidates`.
- **Query:** none new. The existing pool is perceived allies (`_compute_target_pool`, Senses), self, and
  `get_touch_target_candidates` (base_actions.py:1747-1761, `get_entities_at` over 3×3).
- **Subjective:** `admits_touch_target` (:1712-1741).
- **Listed once:** one row. `valid_targets` = recipients with ≥1 candidate spell. The spell is chosen on demand (§3).
- **Deleted:**
  - `get_discovery_variants` and `get_discovery_template_name` (:1429-1438).
  - The per-condition check in `_validate` (:1452-1461). It becomes `targeting_error()` "No cleansable spell".
- **Kept:**
  - `get_variant_facets`.
  - The exact check in `_apply_costs` (:1463-1475). Execution without a spell cancels there.
- **Cost:** O(N + V·(C+10)·K) → O((C+10)·K), where V = Σ cleansable conditions over allies anywhere. Rows for
  unseen allies' spells no longer leak.

### 2.2 Revivify (necromancy.py:2741-2805), discovery

- **Rule** (:2743): an intact DEAD/DYING/STABLE allied player companion within 30 ft; optional relocation.
  - DEAD needs a cell the caster sees.
  - DYING/STABLE go through `validate_single_recipient` (LOS).
- **Query:** `get_additional_target_candidates` (:2799) becomes
  `get_entities_within(self.get_target_origin(), 30)`.
  - Filters: companion, `is_ally`, life state, `caster.senses.visible[pos]`.
  - The radius is equivalent: `_validate` (:2807-2813) already rejects >30 ft.
- **Objective radius + subjective LOS mask.** Dead bodies aren't contacts (entity.py:4020-4022), so the mask is the
  only perception witness.
- **Listed once:**
  - Levels collapse in the discovery plan.
  - `relocate` stays a form facet.
  - The witness (base_actions.py:2109-2116) now spans k_30 cells, not the world (Q1).
- **Deleted:** the scan and `is_deployed`.
- **Cost:** 2L·N + L·T·k_30 → o_30 + T·k_30 per row.

### 2.3 Holy Aura (abjuration.py:3752-3770), discovery

- **Rule** (SRD plan :295-301): a fixed chosen set within 30 ft, no repeats. Code: `self_or_allies`, visible.
- **Subjective:** the count is the row's admitted recipients.
- **Change:**
  - Declared field `BaseAction.any_number_of_targets: bool = False`, set `True` on Holy Aura. A validator rejects it
    together with `allow_same_target`.
  - `_make_action_info` (entity.py:5731) then reports `len(valid_targets)`.
- **Deleted:** the `get_multi_target_count` override (`len(Entity.get_all_entities())`).
- **Cost:** N per row, with the world count leaked as `num_projectiles` → O(1).

### 2.4 Forcecage displacement (wall_constructions.py:881-902), on demand + execution

- **Rule:** creatures partially inside are pushed out (predicate :887-890).
- **Query:** `get_entities_in_bounds(center ± r)`, with r = `side_feet // 10 + 2` ≥ ceil(half + Gargantuan space 2):
  a superset.
  - Predicate and `str(uuid)` order are kept, so outcomes don't change.
- **Objective** (physics); preview disclosure is Q2.
- **Discovery:** the per-centre calls (:933) vanish with the discovery plan's position-enumeration deletion.
  `position_placement_error` checks the chosen centre, and `_apply` checks again (:946).
- **Deleted:** the scan and `is_deployed`.
- **Cost:** N per call × visible centres → o_box (≤ 81 cells, ≤ 4 chunks).

### 2.5 Stone enclosure escapes (wall_constructions.py:509-548), execution

- **Rule** (SRD Wall of Stone): an enclosed creature may make a DEX save, then use its reaction to move out.
- **Query:** `get_entities_in_bounds(shell bbox)`.
  - Equivalent: displaced creatures start on shell cells, which are inside the bbox.
  - Order becomes plan §5.3's `resolution_order_key` (wall formation is a §5.2 group) instead of registry insertion
    order. Listed for sign-off.
- **Objective.**
- **Deleted:** the scan and `is_deployed`.
- **Cost:** N → o_bbox.

### 2.6 Charm Monster save advantage (enchantment.py:2636-2644), execution

- **Rule** (SRD): advantage "if you or your companions are fighting it". Code: alive hostile encounter members that
  are the caster or the caster's allies.
- **Owner:** the encounter roster, `Encounter.get(target.active_encounter_uuid).get_alive_combatants()`
  (encounter.py:318-321, 1232-1234).
  - An absent encounter gives no advantage.
  - It's equivalent: `active_encounter_uuid` is set and cleared with `combatants` (:384, 440, 507, 662).
  - New import `dnd.spells.enchantment → dnd.encounter` is acyclic: `dnd.encounter` reaches no `dnd.spells`.
- **Objective:** membership, not perception.
- **Cost:** N → E.

### 2.7 Radius features, execution (`_apply_target_batch` roots)

| Site | Rule (kept) | Query | Kind |
| --- | --- | --- | --- |
| `turning_targets` divine.py:275-289 (cleric.py:68, paladin.py:1122) | undead[/fiend] within 30 ft that see the actor | `within(actor.position, 30)` + type + `target.senses.entities[actor].visual` | objective radius; subjective from the **target's** Senses ("can see you"; hearing unmodelled, plan Q6) |
| Preserve Life cleric.py:120-131 | same faction, not undead/construct, 30 ft | `within(.., 30)` | objective |
| Sunder divine_intervention.py:133-141 | enemies, 50 ft | `within(.., 50)` | objective |
| Opulent Revival `_apply_costs` :205-236 | same faction, 60 ft | `within(.., 60)` | objective |

- **Opulent fix (D6, sign-off):**
  - The dead branch skipped the deployment check, and revival never redeploys (entity.py:2899-2928). So a suspended
    dead companion revived off-grid.
  - Grid membership excludes it.
  - `_apply` (:241-266) is unchanged.
- **Deleted:** four scans and their `is_deployed`.
- **Cost:** N → o_30, o_50 and o_60.

## 3. On-demand target facet (for 2.1)

One hook; binding is data.

- `BaseAction.get_target_variants(target_uuid) -> tuple[BaseAction, ...]`, default `()`, beside
  `get_secondary_target_options` (base_actions.py:1624).
  - It's `get_discovery_variants` scoped to one chosen target, on demand.
  - Cleansing Touch returns `model_copy(update={"condition_uuid": c.uuid})` per candidate.
- `AvailableSelectionPreview.target_facets` (:2948) holds those variants' `get_variant_facets()`, for the selected
  primary only (actions_functional.py:599).
- Preview and `execute_available_action` (:551) take `target_facet: ActionVariantFacet | None`. They pick the
  matching variant and reject an unmatched facet.
- Client protocol change (PC lane).

## 4. Tests (HOW_TO_TEST.MD)

Boundaries: `get_available_actions`, `preview_available_selection`, `execute_available_action` → state and events.
One `check` helper per file; tiles are created after `reset_combat_state()`; saves reroll natural 1/20.

**New `tests/engine/test_bounded_recipient_discovery.py`:**

- **CT1:** Bless on an adjacent ally, a visible ally at 40 ft, and an ally behind a wall.
  - Expect one Cleansing Touch row; targets = {adjacent ally}; facets = [Bless].
  - Executing removes only that Bless.
- **CT2:** an invisible adjacent ally isn't offered; with See Invisibility it is.
- **CT3:**
  - No facet → `can_confirm=False`.
  - A foreign facet → rejected.
  - Execution without a facet → cancelled, nothing paid.
- **RV1:** a dead companion visible at 25 ft is offered.
  - Not offered: at 35 ft; behind a wall; a non-companion; disintegrated; alive.
  - DYING is offered. An unperceived invisible DYING companion isn't.
- **HA1:** self, 2 visible allies in 30 ft, an ally at 40 ft, an invisible ally at 10 ft, 10 far hostiles.
  - `num_projectiles == 3`.
  - Adding 20 far entities still gives 3.
  - A 4th pick is rejected.

**Extend existing suites:**

- **FC1** (`test_high_level_spell_fields.py`): a straddler is ejected; a far creature is untouched.
- **WS1** (`test_remaining_walls.py`): an enclosed creature saves and escapes; one outside the bbox gets no save
  event.
- **CM1:** the target fighting the caster's ally in the same encounter → advantage. Another encounter or a dead ally
  → none.
- **TU1** (`test_cleric_features.py`): undead at 25 ft seeing the cleric are turned. Not turned:
  - at 35 ft;
  - can't see the invisible cleric;
  - suspended with retained coordinate 5 ft away.
- **PL1, SU1, OR1** (`test_divine_intervention.py`):
  - exactly 30/50/60 ft vs +5 ft;
  - a suspended dead companion isn't revived.
- **GM1** (GridMap contract): both reads equal a brute-force filter across chunk borders and life states.
- **Architecture** (`tests/architecture/test_source_model_hygiene.py`): AST ban on `get_all_entities` and
  `_entity_registry` iteration in `dnd/`. Exceptions: entity.py registry ops, `runtime_reset.py`, `pack_loader.py`,
  the `encounter_assembler.py:423` setup guard.

## 5. Other scans found

`get_entities_by_faction` / `get_alive_by_faction` (entity.py:4500-4522) scan the whole world but have no `dnd/`
caller (Q3).

## 6. Open questions

- **Q1:** the witness at base_actions.py:2109-2116 also serves Telekinesis (transmutation.py:1731, 1812), Dimension
  Door (conjuration.py:4314) and evocation.py:6561/6672. Move it on demand for all of them? Rows could then list a
  target with no legal destination.
- **Q2:** the Forcecage/wall preview uses objective occupancy, so a refusal reveals an unseen straddler. Keep it, or
  gate the preview on perceived contacts and let execution refuse?
- **Q3:** delete the two unused faction scans?

## 7. Reviews

| Review | Findings | Outcome |
| --- | --- | --- |
| Antislop | 9 minor | all accepted |
| AntiOOP | 2 major | accepted: a variants hook instead of a bind method; a declared field instead of a `None` sentinel |
