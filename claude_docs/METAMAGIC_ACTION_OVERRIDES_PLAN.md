# Metamagic & Action Overrides Plan

See the implementation plan in the conversation transcript. This file archives the approved plan for reference.

## Summary

Action templates get temporary override fields (`alt_*`) that conditions set directly. When present, the system uses `effective_*` properties instead of base values.

### Alt Fields on BaseAction
- `alt_cost_type` — Replace primary action cost type
- `alt_extra_costs` — Additional costs appended (SP, etc.)
- `alt_target_type` — Replace target type
- `alt_target_count` — Multi-target count override

### Alt Fields on SpellAction
- `alt_range` — Override spell_range
- `alt_skip_slot` — Skip spell slot cost

### Helper Functions
- `apply_action_overrides(entity, filter_fn, overrides)` → List[UUID]
- `clear_action_overrides(entity, template_uuids)`

### MetamagicActive Condition
- Sets alt fields on eligible templates via helpers
- Auto-removes on CAST_SPELL event
- Cleanup clears alt fields

### Metamagic Types
| Type | Filter | Overrides |
|------|--------|-----------|
| Quickened | Spells with action cost | `alt_cost_type="bonus_actions"`, SP cost 2 |
| Distant | Spells with range > SELF | `alt_range=spell_range*2` (Touch→30), SP cost 1 |
| Twinned | Spells with ENTITY target | `alt_target_type=MULTI_ENTITY`, `alt_target_count=2`, SP cost = spell level |

### Bug Fixes (Phase B)
1. `ensure_concentration()` — UUID-tracked, safe for convolution loop
2. `_finalize_aoe()` hook — replaces apply() override anti-pattern in Ice Storm / Gust of Wind
