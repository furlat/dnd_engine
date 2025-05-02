# Action System Implementation Notes

## Core Action Decorator Pattern

The action system uses a decorator-based approach to standardize action execution flow and requirements checking. This creates a separation between:

1. Action prerequisites validation
2. Action execution logic 
3. Action economy resource management

```python
@action(
    action_type="actions",  # or "bonus_actions", "reactions"
    cost=1,
    requirements=[requires_line_of_sight(), requires_range(5)],
    revalidate_after_reactions=True
)
def melee_attack(entity, target):
    # Implementation focusing only on the attack effects
    pass
```

The decorator handles:
- Initial validation of all requirements
- Creation and processing of the action event
- Revalidation after reactions have occurred
- Resource consumption only on successful completion

## Target Types

Actions can be defined to work with different target types through specialized decorators:

### Entity-Targeted Actions
Standard actions that affect a single target entity.

```python
@action(requirements=[requires_range(30)])
def single_target_spell(entity, target):
    # Cast spell on single target
    pass
```

### Position-Targeted Actions
Actions that affect an area rather than a specific entity.

```python
@action_with_position_target(
    area_type="circle",
    area_size=20,  # 20-foot radius
    requirements=[requires_line_of_sight()]
)
def fireball(entity, position):
    # Implementation handles a single position
    # Decorator finds all targets in the area
    pass
```

### Multi-Target Actions
Actions that explicitly target multiple entities.

```python
@action_with_multiple_targets(
    target_count=3,
    requirements=[requires_line_of_sight()]
)
def magic_missile(entity, targets):
    # Implementation handles multiple targets
    pass
```

## Integration with Event System

When an action is invoked, it generates appropriate events that flow through the event system:
1. DECLARATION phase allows for interruption before resources are committed
2. EXECUTION phase processes the core action logic
3. EFFECT phase applies results to targets
4. COMPLETION phase finalizes the action and consumes resources

This integration ensures that all actions follow the same flow while respecting the event-driven architecture of the system.