# Typed Condition and Counterspell Evidence — Complete Implementation Plan

**Status:** forward implementation specification

**Date:** 2026-08-05

**Scope:** one bounded core-engine evidence unit, one mechanical event-contract
regeneration, and focused tests

## 1. Mission

Make condition transitions and Counterspell resolutions carry closed,
machine-validatable objective evidence without changing their mechanics.

After this patch:

- condition application and removal events freeze the exact authored condition
  identity at declaration time;
- condition combat logs use one typed payload instead of ad-hoc dictionaries;
- immunity is an explicit condition-application disposition rather than a fact
  recoverable only from prose;
- absence of a content binding remains explicit `None`; a display name,
  semantic key, or Python path is never substituted as authored identity;
- Counterspell events and logs carry both causal content roles: the reaction
  and the incoming spell;
- impossible automatic/check Counterspell combinations are rejected when the
  objective model is built;
- a Counterspell outcome code cannot contradict its success result;
- existing resource spending, spell cancellation, handler ordering,
  subjectivity filtering, and redaction remain unchanged;
- no server runtime, generated player SDK, frontend, persistence, worker,
  thread, or background coordination system is added.

This document is self-contained. It describes only the desired forward
implementation. No historical branch or implementation attempt is required.

## 2. Files in scope

Core production:

```text
dnd/core/condition_types.py
dnd/core/combat_log.py
dnd/core/base_conditions.py
dnd/entity.py
dnd/spells/abjuration.py
```

Mechanical generated mirror:

```text
server/event_contract.generated.json
```

New focused regressions:

```text
tests/engine/test_condition_content_evidence.py
tests/engine/test_counterspell_evidence.py
```

Existing focused regressions with small assertion/fixture updates:

```text
tests/manual/test_50_counterspell_engine_contract.py
tests/manual/test_121_canonical_presentation_mapper.py
tests/manual/test_97_event_wire_contract.py
```

The generated JSON must be produced by
`devtools/generate_event_contract.py`. Do not hand-edit it.

No other production, runtime, transport, SDK, frontend, dependency, or
documentation file should need modification.

## 3. Architectural ownership

### 3.1 Conditions own transition meaning

`BaseCondition` owns the live rules behavior and its optional authenticated
`BehaviorBinding`. `ConditionApplicationEvent` and `ConditionRemovalEvent` own
immutable event-time transition facts. `CombatLogEntry` is an observational
projection created at event completion.

The dependency order remains:

```text
dnd/core/condition_types.py
  -> imported by combat-log and condition-event models

dnd/core/combat_log.py
  -> imported by condition and spell events

dnd/core/base_conditions.py
  -> imported by Entity and concrete conditions

dnd/entity.py / dnd/spells/abjuration.py
  -> high-level mechanics and causal orchestration
```

`dnd/core/combat_log.py` may import the dependency-neutral
`ConditionApplicationDisposition` enum. It must not import `Entity`, concrete
conditions, spell modules, content registries, server modules, or projectors.

### 3.2 A binding is the only authored identity authority

For a live condition, the exact authored identity is:

```python
condition.behavior_binding.definition_ref.identity_key
```

only when `behavior_binding` is a real `BehaviorBinding`.

These values are not equivalent and must never be used as fallbacks:

```text
condition.name                 display text
condition.semantic_key         rules-family/legacy dispatch key
type(condition).__module__     Python implementation detail
type(condition).__name__       Python implementation detail
condition.uuid                 encounter-local runtime identity
```

Unbound legacy/custom diagnostic conditions remain representable with:

```python
condition_content_identity=None
```

That explicit absence is more truthful than an invented catalog identity.

### 3.3 Counterspell has two distinct authored roles

A completed Counterspell reaction has two independent causal identities:

1. `reaction_content_identity`: the handler/reaction behavior that attempted
   Counterspell;
2. `incoming_spell_content_identity`: the spell behavior being challenged.

The reaction identity comes from the active handler binding. The incoming
spell identity comes from the already-frozen `SpellEvent.behavior_binding`.
They must not be collapsed into one `spell_id`, semantic key, display name, or
Python class.

### 3.4 Evidence is not a second mechanics owner

The new validators only reject contradictory facts. They do not decide which
slot to spend, roll a die, consume a reaction, interrupt a spell, apply a
condition, remove a condition, or project a player view.

The existing owners remain unchanged:

- `Entity.add_condition()` owns immunity admission and condition installation;
- `BaseCondition`/`BaseBlock` own apply/remove lifecycles;
- `counterspell_reaction_processor()` owns Counterspell mechanics and resource
  settlement;
- `EventQueue` owns causal event publication;
- subjective projection/redaction remains downstream and read-only.

## 4. Closed condition evidence model

### 4.1 Application dispositions

The current enum models applied, rejected, retained-stronger, and promoted
outcomes. Immunity is also a distinct objective application outcome and must
be represented in the same closed enum.

In `dnd/core/condition_types.py`, replace the enum with:

```python
class ConditionApplicationDisposition(str, Enum):
    """Observable outcome of one condition-application attempt."""

    APPLIED = "applied"
    REJECTED = "rejected"
    RETAINED_STRONGER = "retained_stronger"
    PROMOTED = "promoted"
    IMMUNE = "immune"
```

Do not encode immunity as uppercase free text. Do not reuse `REJECTED`:
repeated-condition arbitration and rules immunity are different facts.

### 4.2 Typed condition log data

In `dnd/core/combat_log.py`, add this import immediately after the Pydantic
imports:

```python
from dnd.core.condition_types import ConditionApplicationDisposition
```

Place the following model after `SpatialEffectInteractionLogData` and before
the general roll/log models:

```python
class ConditionLogData(BaseModel):
    """Typed authored identity and outcome for one condition transition."""

    condition_name: str = Field(
        min_length=1,
        description="Human-readable condition name captured for display.",
    )
    condition_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact bound authored condition identity; absent only for "
            "legacy or custom unbound diagnostics."
        ),
    )
    reveals_target: bool = Field(
        default=False,
        description="Whether removal can reveal the affected target.",
    )
    application_disposition: Optional[
        ConditionApplicationDisposition
    ] = Field(
        default=None,
        description=(
            "Closed application outcome; absent on removal transitions."
        ),
    )
```

This model is deliberately small. Do not add live condition objects, duration
callables, modifier lists, registry lookups, observer sets, presentation cue
data, or client animation instructions.

### 4.3 Freeze authored identity on condition events

In `dnd/core/base_conditions.py`, extend the combat-log import:

```python
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    ConditionLogData,
)
```

Add this field to `ConditionApplicationEvent` immediately after
`application_disposition`:

```python
condition_content_identity: Optional[str] = Field(
    default=None,
    min_length=1,
    description=(
        "Exact authored condition identity frozen when the declaration is "
        "created; absent only for legacy unbound diagnostic events."
    ),
)
```

Add the same field to `ConditionRemovalEvent` after its name fields:

```python
condition_content_identity: Optional[str] = Field(
    default=None,
    min_length=1,
    description=(
        "Exact authored condition identity frozen when the declaration is "
        "created; absent only for legacy unbound diagnostic events."
    ),
)
```

The field is copied through event phases by the existing event lifecycle. A
completion log reads this field, not the current mutable condition binding.

### 4.4 Exact identity helper

Add this method to `BaseCondition` immediately after `get_semantic_key()`:

```python
def authored_content_identity(self) -> Optional[str]:
    """Return exact bound authored identity, or ``None`` when unbound.

    Names, semantic keys, UUIDs, and Python paths are intentionally not
    accepted as content-identity fallbacks.
    """
    binding = self.behavior_binding
    return (
        binding.definition_ref.identity_key
        if isinstance(binding, BehaviorBinding)
        else None
    )
```

Do not alter `get_semantic_key()`. It remains useful for mechanics and legacy
rules-family comparisons, but it is not an authored-catalog identity API.

### 4.5 Declaration construction

In `BaseCondition.declare_event()`, add exactly one constructor argument:

```python
condition_content_identity=self.authored_content_identity(),
```

The complete return block becomes:

```python
return ConditionApplicationEvent(
    name=self.name,
    condition=self,
    source_entity_uuid=self.source_entity_uuid,
    target_entity_uuid=self.target_entity_uuid,
    phase=EventPhase.DECLARATION,
    parent_event=parent_event.uuid if parent_event else None,
    source_entity_name=self.source_entity_name,
    target_entity_name=self.target_entity_name,
    application_disposition=application_disposition,
    condition_content_identity=self.authored_content_identity(),
    use_register=False,
)
```

In `BaseCondition._declare_removal_event()`, add the same frozen fact. The
complete return block becomes:

```python
return ConditionRemovalEvent(
    name=self.name if self.name else "Condition Removal",
    condition=self,
    expired=expired,
    source_entity_uuid=self.source_entity_uuid,
    target_entity_uuid=self.target_entity_uuid,
    phase=EventPhase.DECLARATION,
    parent_event=parent_event.uuid if parent_event else None,
    source_entity_name=self.source_entity_name,
    target_entity_name=self.target_entity_name,
    condition_content_identity=self.authored_content_identity(),
    use_register=False,
)
```

Identity is captured only after `Entity.add_condition()` has executed the
existing binding step and before the declaration enters `EventQueue`.

### 4.6 Application log generation

In `ConditionApplicationEvent.generate_combat_log()`, add an explicit immunity
text branch before the retained-stronger branch:

```python
if self.application_disposition is ConditionApplicationDisposition.IMMUNE:
    compact = (
        f"{{cyan:{target_name}}} is immune to "
        f"**{cond.name or 'Unknown'}**"
    )
elif self.application_disposition is (
    ConditionApplicationDisposition.RETAINED_STRONGER
):
    compact = (
        f"{{cyan:{target_name}}} remains under the stronger "
        f"**{cond.name or 'Unknown'}** effect"
    )
```

Keep the existing `REJECTED`, `PROMOTED`, and normal application branches
after it.

Replace the end of the `CombatLogEntry` construction with:

```python
success=self.application_disposition not in {
    ConditionApplicationDisposition.REJECTED,
    ConditionApplicationDisposition.RETAINED_STRONGER,
    ConditionApplicationDisposition.IMMUNE,
},
data=ConditionLogData(
    condition_name=cond.name or "Unknown",
    condition_content_identity=self.condition_content_identity,
    application_disposition=self.application_disposition,
).model_dump(mode="json"),
```

Use JSON mode so the enum is emitted as its lowercase value. Do not use
`exclude_none=True`: an explicit `null` identity is useful evidence that no
authored binding existed.

### 4.7 Removal log generation

Replace the raw `data={...}` in
`ConditionRemovalEvent.generate_combat_log()` with:

```python
data=ConditionLogData(
    condition_name=condition_name,
    condition_content_identity=self.condition_content_identity,
    reveals_target=cond.obscures_perceivability,
).model_dump(mode="json"),
```

This retains the existing `reveals_target` behavior while closing the payload
shape and adding exact authored identity.

### 4.8 Immunity branch in Entity

In `dnd/entity.py`, extend the combat-log import to include
`ConditionLogData` and extend the condition-types import to include
`ConditionApplicationDisposition` if it is not already present in that import
block.

In the immunity branch of `Entity.add_condition()`, keep the existing
standalone log and cancellation ordering, but add typed data and return a
canceled event whose disposition is `IMMUNE`.

The complete branch must be:

```python
if self.check_condition_immunity(condition.name, condition=condition):
    target_name = self.name
    condition_name = condition.name
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.CONDITION_APPLIED,
        source_name=target_name,
        source_uuid=str(self.uuid),
        target_name=target_name,
        target_uuid=str(self.uuid),
        compact=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
        verbose=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
        detailed=f"{{yellow:{target_name}}} is **immune** to {condition_name}",
        success=False,
        data=ConditionLogData(
            condition_name=condition_name,
            condition_content_identity=(
                declaration_event.condition_content_identity
            ),
            application_disposition=(
                ConditionApplicationDisposition.IMMUNE
            ),
        ).model_dump(mode="json"),
    )
    EventQueue.push_combat_log(entry, self.uuid)

    canceled = declaration_event.cancel(
        status_message=f"Condition {condition.name} is immune",
        application_disposition=ConditionApplicationDisposition.IMMUNE,
    )
    self._discard_uncommitted_condition_tree(condition)
    return canceled
```

`declaration_event` is non-optional at this point, so remove the unreachable
`if declaration_event is not None` / `else` split from this branch. The method
has already constructed and published the declaration and returned early if it
was vetoed.

Do not complete the condition application, call `condition.apply()`, or
install it in `active_conditions`. Immunity remains a canceled application
with a standalone informational log.

## 5. Closed Counterspell evidence model

### 5.1 Resolution state machine

Counterspell evidence has exactly two legal resolution families:

```text
AUTOMATIC
  counterspell_slot_level >= incoming_spell_level
  succeeded is True
  check_total is None
  check_dc is None

CHECKED
  counterspell_slot_level < incoming_spell_level
  check_total is present
  check_dc is present
  check_dc == 10 + incoming_spell_level
  succeeded == (check_total >= check_dc)
```

Global level bounds are:

```text
incoming_spell_level:    0..9
counterspell_slot_level: 3..9
```

Cantrips remain level zero and are automatically interrupted by any legal
Counterspell slot. Checked resolution is valid only when the incoming spell is
higher level than the spent Counterspell slot.

Outcome code is derived from the same success fact:

```text
succeeded=True   -> spell.counterspell.interrupted
succeeded=False  -> spell.counterspell.failed
```

### 5.2 Validate typed log data

In `dnd/core/combat_log.py`, extend the Pydantic import:

```python
from pydantic import BaseModel, Field, field_serializer, model_validator
```

Replace `SpellInterruptionLogData` with:

```python
class SpellInterruptionLogData(BaseModel):
    """Structured result of one Counterspell reaction."""

    outcome_code: str = Field(
        min_length=1,
        description="Stable reaction outcome identity.",
    )
    counterspeller_name: str = Field(
        description="Display name of the reacting caster.",
    )
    counterspeller_uuid: str = Field(
        description="UUID of the reacting caster.",
    )
    original_caster_name: str = Field(
        description="Display name of the interrupted caster.",
    )
    original_caster_uuid: str = Field(
        description="UUID of the interrupted caster.",
    )
    spell_name: str = Field(
        description="Display name of the incoming spell.",
    )
    incoming_spell_level: int = Field(
        ge=0,
        le=9,
        description="Level of the incoming cast.",
    )
    counterspell_slot_level: int = Field(
        ge=3,
        le=9,
        description="Slot level spent on Counterspell.",
    )
    automatic: bool = Field(
        description="Whether slot level made the result automatic.",
    )
    check_total: Optional[int] = Field(
        default=None,
        description="Spellcasting check total when rolled.",
    )
    check_dc: Optional[int] = Field(
        default=None,
        description="Spellcasting check DC when rolled.",
    )
    succeeded: bool = Field(
        description="Whether the reaction interrupted the incoming spell.",
    )
    reaction_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authenticated authored reaction identity; absent only "
            "from legacy diagnostic events."
        ),
    )
    incoming_spell_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authenticated authored identity of the incoming spell; "
            "absent only from legacy diagnostic events."
        ),
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "SpellInterruptionLogData":
        """Reject contradictory automatic or checked resolution evidence."""
        if self.automatic:
            if self.counterspell_slot_level < self.incoming_spell_level:
                raise ValueError(
                    "automatic Counterspell requires a sufficient slot",
                )
            if not self.succeeded:
                raise ValueError("automatic Counterspell must succeed")
            if self.check_total is not None or self.check_dc is not None:
                raise ValueError(
                    "automatic Counterspell forbids check evidence",
                )
            return self

        if self.counterspell_slot_level >= self.incoming_spell_level:
            raise ValueError(
                "checked Counterspell requires a lower-level slot",
            )
        if self.check_total is None or self.check_dc is None:
            raise ValueError(
                "checked Counterspell requires total and DC",
            )
        if self.check_dc != 10 + self.incoming_spell_level:
            raise ValueError(
                "Counterspell check DC must equal 10 plus spell level",
            )
        if self.succeeded != (self.check_total >= self.check_dc):
            raise ValueError("Counterspell success contradicts its check")
        return self
```

`dnd/core/combat_log.py` deliberately does not import spell-specific outcome
constants. The objective event validates the code/result relationship; the log
copies the already-validated code exactly.

### 5.3 Validate the objective reaction event

In `dnd/spells/abjuration.py`, extend the Pydantic import:

```python
from pydantic import Field, PrivateAttr, model_validator
```

Replace the fields and validator portion of `CounterspellReactionEvent` with:

```python
class CounterspellReactionEvent(ActionEvent):
    """Observable resolution of one Counterspell reaction."""

    name: str = Field(default="Counterspell", description="Reaction event name.")
    event_type: EventType = Field(
        default=EventType.TRIGGER_EVENT,
        description="Reaction event category.",
    )
    triggered_event_uuid: UUID = Field(
        description="Incoming spell event version that triggered the reaction.",
    )
    triggered_lineage_uuid: UUID = Field(
        description="Incoming spell lineage interrupted or challenged.",
    )
    incoming_spell_name: str = Field(
        description="Display name of the incoming spell.",
    )
    incoming_spell_level: int = Field(
        ge=0,
        le=9,
        description="Level of the incoming cast.",
    )
    counterspell_slot_level: int = Field(
        ge=3,
        le=9,
        description="Slot level spent on Counterspell.",
    )
    automatic: bool = Field(
        description="Whether the selected slot guarantees interruption.",
    )
    check_total: Optional[int] = Field(
        default=None,
        description="Spellcasting check total when required.",
    )
    check_dc: Optional[int] = Field(
        default=None,
        description="Spellcasting check DC when required.",
    )
    succeeded: bool = Field(
        description="Whether Counterspell interrupted the incoming spell.",
    )
    outcome_code: str = Field(
        min_length=1,
        description="Stable Counterspell result code matching succeeded.",
    )
    reaction_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authored Counterspell reaction identity frozen at "
            "declaration."
        ),
    )
    incoming_spell_content_identity: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "Exact authored incoming spell identity frozen at declaration."
        ),
    )

    @model_validator(mode="after")
    def validate_counterspell_resolution(
        self,
    ) -> "CounterspellReactionEvent":
        """Reject contradictory reaction, roll, and outcome-code facts."""
        expected_outcome_code = (
            COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
            if self.succeeded
            else COUNTERSPELL_FAILURE_OUTCOME_CODE
        )
        if self.outcome_code != expected_outcome_code:
            raise ValueError(
                "Counterspell outcome code contradicts its success result",
            )

        if self.automatic:
            if self.counterspell_slot_level < self.incoming_spell_level:
                raise ValueError(
                    "automatic Counterspell requires a sufficient slot",
                )
            if not self.succeeded:
                raise ValueError("automatic Counterspell must succeed")
            if self.check_total is not None or self.check_dc is not None:
                raise ValueError(
                    "automatic Counterspell forbids check evidence",
                )
            return self

        if self.counterspell_slot_level >= self.incoming_spell_level:
            raise ValueError(
                "checked Counterspell requires a lower-level slot",
            )
        if self.check_total is None or self.check_dc is None:
            raise ValueError(
                "checked Counterspell requires total and DC",
            )
        if self.check_dc != 10 + self.incoming_spell_level:
            raise ValueError(
                "Counterspell check DC must equal 10 plus spell level",
            )
        if self.succeeded != (self.check_total >= self.check_dc):
            raise ValueError("Counterspell success contradicts its check")
        return self
```

This overrides the inherited optional `Event.outcome_code` with a required
Counterspell-specific field. Every actual Counterspell reaction already knows
its outcome before declaration, so optionality here would permit contradictory
or incomplete objective evidence.

### 5.4 Freeze both content roles at reaction declaration

Extend the content-runtime import in `dnd/spells/abjuration.py`:

```python
from dnd.core.content.runtime import (
    BehaviorBinding,
    RuntimeBehaviorKind,
    active_runtime_behavior_binding,
)
```

In `_begin_counterspell_reaction()`, compute the bindings immediately before
constructing the declaration:

```python
reaction_binding = active_runtime_behavior_binding()
incoming_spell_binding = incoming_event.behavior_binding
```

Then construct the declaration with both frozen identities:

```python
declaration = CounterspellReactionEvent(
    source_entity_uuid=counterspeller.uuid,
    target_entity_uuid=original_caster.uuid,
    source_entity_name=counterspeller.name,
    target_entity_name=original_caster.name,
    triggered_event_uuid=incoming_event.uuid,
    triggered_lineage_uuid=incoming_event.lineage_uuid,
    incoming_spell_name=incoming_event.name,
    incoming_spell_level=(
        incoming_event.cast_at_level or incoming_event.spell_level
    ),
    counterspell_slot_level=slot_level,
    automatic=automatic,
    check_total=check_total,
    check_dc=check_dc,
    succeeded=succeeded,
    outcome_code=outcome_code,
    behavior_binding=reaction_binding,
    reaction_content_identity=(
        reaction_binding.definition_ref.identity_key
        if isinstance(reaction_binding, BehaviorBinding)
        else None
    ),
    incoming_spell_content_identity=(
        incoming_spell_binding.definition_ref.identity_key
        if isinstance(incoming_spell_binding, BehaviorBinding)
        else None
    ),
    use_register=False,
)
```

Why both `behavior_binding` and the scalar identity are supplied:

- `behavior_binding` remains engine-internal causal attribution and is
  excluded from raw event serialization;
- `reaction_content_identity` is the immutable diagnostic fact that survives
  serialization and combat-log generation;
- both are derived from the same active binding in one statement scope, so
  they cannot race or diverge.

An incoming direct legacy/unregistered spell action may have no binding. Its
identity remains `None`; `incoming_spell_name` and `spell_id` are not used as
fallbacks. Registered gameplay actions retain their exact identity.

### 5.5 Copy exact event facts into the log

In `CounterspellReactionEvent.generate_combat_log()`, replace:

```python
outcome_code=self.outcome_code or COUNTERSPELL_FAILURE_OUTCOME_CODE,
```

with:

```python
outcome_code=self.outcome_code,
```

Then add these two arguments to `SpellInterruptionLogData`:

```python
reaction_content_identity=self.reaction_content_identity,
incoming_spell_content_identity=self.incoming_spell_content_identity,
```

The complete typed data block becomes:

```python
data = SpellInterruptionLogData(
    outcome_code=self.outcome_code,
    counterspeller_name=counterspeller_name,
    counterspeller_uuid=str(self.source_entity_uuid),
    original_caster_name=original_caster_name,
    original_caster_uuid=str(self.target_entity_uuid),
    spell_name=self.incoming_spell_name,
    incoming_spell_level=self.incoming_spell_level,
    counterspell_slot_level=self.counterspell_slot_level,
    automatic=self.automatic,
    check_total=self.check_total,
    check_dc=self.check_dc,
    succeeded=self.succeeded,
    reaction_content_identity=self.reaction_content_identity,
    incoming_spell_content_identity=(
        self.incoming_spell_content_identity
    ),
)
```

Do not derive any field again during log generation.

### 5.6 Causal and resource order stays unchanged

The existing order is correct and must not be rewritten:

```text
incoming spell reaches EXECUTION
  -> Counterspell handler determines automatic/check result
  -> Counterspell DECLARATION (vetoable)
  -> Counterspell EXECUTION (vetoable)
  -> Counterspell EFFECT (vetoable)
  -> consume reaction and selected spell slot
  -> Counterspell COMPLETION (non-handler observational boundary)
  -> if succeeded, cancel incoming spell from EXECUTION
```

If any Counterspell phase before EFFECT is canceled, the reaction and slot are
not spent. This patch adds evidence validation only; it must not change that
transaction.

## 6. Complete condition regression file

Create `tests/engine/test_condition_content_evidence.py` with:

```python
"""Typed authored evidence for condition application and removal."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from dnd.conditions import Poisoned
from dnd.core.base_conditions import (
    BaseCondition,
    ConditionApplicationEvent,
    ConditionRemovalEvent,
)
from dnd.core.combat_log import CombatLogEntry, ConditionLogData
from dnd.core.condition_types import ConditionApplicationDisposition
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events import Event, EventQueue
from dnd.monsters.bestiary import create_skeleton
from dnd.runtime_reset import reset_engine_runtime


def _condition_ref(
    content_id: str,
    *,
    digest_char: str,
) -> ContentRef:
    """Create one exact synthetic authored condition identity."""
    return ContentRef(
        pack_id="fixture.condition_evidence",
        definition_kind=ContentDefinitionKind.CONDITION,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=digest_char * 64,
    )


def _binding(ref: ContentRef, owner_uuid: UUID) -> BehaviorBinding:
    """Bind a synthetic condition directly to its authored definition."""
    return BehaviorBinding(
        definition_ref=ref,
        provided_by_ref=ref,
        runtime_owner_uuid=owner_uuid,
    )


def _condition(
    *,
    binding: BehaviorBinding | None,
    obscures_perceivability: bool = False,
) -> BaseCondition:
    """Build a condition without invoking entity mechanics."""
    source_uuid = uuid4()
    target_uuid = (
        binding.runtime_owner_uuid
        if binding is not None
        else uuid4()
    )
    return BaseCondition(
        name="Marked",
        semantic_key="legacy.marked.family",
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Source",
        target_entity_name="Target",
        behavior_binding=binding,
        obscures_perceivability=obscures_perceivability,
    )


@pytest.mark.parametrize(
    ("disposition", "success"),
    (
        (ConditionApplicationDisposition.APPLIED, True),
        (ConditionApplicationDisposition.PROMOTED, True),
        (ConditionApplicationDisposition.REJECTED, False),
        (ConditionApplicationDisposition.RETAINED_STRONGER, False),
        (ConditionApplicationDisposition.IMMUNE, False),
    ),
)
def test_application_log_has_closed_disposition_and_bound_identity(
    disposition: ConditionApplicationDisposition,
    success: bool,
) -> None:
    """Every application outcome retains one typed identity and result."""
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.marked",
        digest_char="a",
    )
    condition = _condition(binding=_binding(ref, owner_uuid))

    event = condition.declare_event(
        application_disposition=disposition,
    )
    log = event.generate_combat_log()

    assert isinstance(event, ConditionApplicationEvent)
    assert event.condition_content_identity == ref.identity_key
    assert log is not None
    assert log.success is success
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_name == "Marked"
    assert data.condition_content_identity == ref.identity_key
    assert data.application_disposition is disposition
    assert data.reveals_target is False


def test_removal_log_uses_same_bound_identity_and_reveal_fact() -> None:
    """Removal carries authored identity and condition-owned reveal meaning."""
    owner_uuid = uuid4()
    ref = _condition_ref(
        "condition.fixture.hidden_mark",
        digest_char="b",
    )
    condition = _condition(
        binding=_binding(ref, owner_uuid),
        obscures_perceivability=True,
    )

    application = condition.declare_event()
    removal = condition._declare_removal_event(expired=True)
    log = removal.generate_combat_log()

    assert isinstance(removal, ConditionRemovalEvent)
    assert application.condition_content_identity == ref.identity_key
    assert removal.condition_content_identity == ref.identity_key
    assert log is not None
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_name == "Marked"
    assert data.condition_content_identity == ref.identity_key
    assert data.application_disposition is None
    assert data.reveals_target is True


def test_declaration_identity_does_not_follow_later_binding_mutation() -> None:
    """Event-time identity remains frozen even if the live object changes."""
    owner_uuid = uuid4()
    original_ref = _condition_ref(
        "condition.fixture.original",
        digest_char="c",
    )
    replacement_ref = _condition_ref(
        "condition.fixture.replacement",
        digest_char="d",
    )
    condition = _condition(binding=_binding(original_ref, owner_uuid))
    event = condition.declare_event()

    condition.behavior_binding = _binding(replacement_ref, owner_uuid)
    log = event.generate_combat_log()

    assert event.condition_content_identity == original_ref.identity_key
    assert log is not None
    data = ConditionLogData.model_validate(log.data)
    assert data.condition_content_identity == original_ref.identity_key


def test_unbound_condition_never_invents_authored_identity() -> None:
    """Name, semantic key, and Python type are not identity fallbacks."""
    condition = _condition(binding=None)

    application = condition.declare_event()
    removal = condition._declare_removal_event()
    application_log = application.generate_combat_log()
    removal_log = removal.generate_combat_log()

    assert condition.get_semantic_key() == "legacy.marked.family"
    assert application.condition_content_identity is None
    assert removal.condition_content_identity is None
    assert application_log is not None
    assert removal_log is not None
    assert ConditionLogData.model_validate(
        application_log.data,
    ).condition_content_identity is None
    assert ConditionLogData.model_validate(
        removal_log.data,
    ).condition_content_identity is None


def test_immune_entity_application_returns_and_logs_typed_truth() -> None:
    """Rules immunity is a canceled application with one typed log."""
    reset_engine_runtime(grid_size=(4, 4))
    skeleton = create_skeleton(
        name="Immune Skeleton",
        position=(1, 1),
        faction="monsters",
    )
    condition = Poisoned(
        source_entity_uuid=skeleton.uuid,
        target_entity_uuid=skeleton.uuid,
    )
    logs: list[CombatLogEntry] = []

    def capture(event: Event) -> None:
        if event.combat_log is not None:
            logs.append(event.combat_log)

    EventQueue.set_combat_log_callback(capture)
    try:
        result = skeleton.add_condition(condition)
    finally:
        EventQueue.set_combat_log_callback(None)

    assert isinstance(result, ConditionApplicationEvent)
    assert result.canceled
    assert (
        result.application_disposition
        is ConditionApplicationDisposition.IMMUNE
    )
    assert condition.behavior_binding is not None
    expected_identity = (
        condition.behavior_binding.definition_ref.identity_key
    )
    assert result.condition_content_identity == expected_identity
    assert "Poisoned" not in skeleton.active_conditions
    assert len(logs) == 1
    data = ConditionLogData.model_validate(logs[0].data)
    assert data.condition_name == "Poisoned"
    assert data.condition_content_identity == expected_identity
    assert (
        data.application_disposition
        is ConditionApplicationDisposition.IMMUNE
    )
    assert logs[0].success is False
```

The two `_declare_removal_event()` calls are narrow white-box tests of the
declaration owner. They do not bypass production state mutation because these
cases intentionally test fact construction, not removal mechanics.

## 7. Complete Counterspell regression file

Create `tests/engine/test_counterspell_evidence.py` with:

```python
"""Closed objective evidence for Counterspell resolution."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import SpellInterruptionLogData
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
)


REACTION_IDENTITY = (
    "fixture.counterspell:reaction:reaction.spell.counterspell@1"
)
INCOMING_IDENTITY = (
    "fixture.counterspell:spell:spell.fireball@1"
)


def _event(**updates: Any) -> CounterspellReactionEvent:
    """Construct one otherwise-valid automatic reaction event."""
    values: dict[str, Any] = {
        "source_entity_uuid": uuid4(),
        "target_entity_uuid": uuid4(),
        "triggered_event_uuid": uuid4(),
        "triggered_lineage_uuid": uuid4(),
        "incoming_spell_name": "Fireball",
        "incoming_spell_level": 3,
        "counterspell_slot_level": 3,
        "automatic": True,
        "check_total": None,
        "check_dc": None,
        "succeeded": True,
        "outcome_code": COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
        "reaction_content_identity": REACTION_IDENTITY,
        "incoming_spell_content_identity": INCOMING_IDENTITY,
        "use_register": False,
    }
    values.update(updates)
    return CounterspellReactionEvent(**values)


def _log(**updates: Any) -> SpellInterruptionLogData:
    """Construct equivalent otherwise-valid typed log data."""
    values: dict[str, Any] = {
        "outcome_code": COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
        "counterspeller_name": "Abjurer",
        "counterspeller_uuid": str(uuid4()),
        "original_caster_name": "Evoker",
        "original_caster_uuid": str(uuid4()),
        "spell_name": "Fireball",
        "incoming_spell_level": 3,
        "counterspell_slot_level": 3,
        "automatic": True,
        "check_total": None,
        "check_dc": None,
        "succeeded": True,
        "reaction_content_identity": REACTION_IDENTITY,
        "incoming_spell_content_identity": INCOMING_IDENTITY,
    }
    values.update(updates)
    return SpellInterruptionLogData(**values)


class Builder(Protocol):
    """Shared constructor shape for event and log validation tests."""

    def __call__(self, **updates: Any) -> Any:
        ...


@pytest.mark.parametrize("builder", (_event, _log))
def test_automatic_counterspell_is_closed(builder: Builder) -> None:
    """Automatic evidence has a sufficient slot and no check fields."""
    result = builder()
    assert result.automatic is True
    assert result.succeeded is True
    assert result.check_total is None
    assert result.check_dc is None


@pytest.mark.parametrize("builder", (_event, _log))
@pytest.mark.parametrize(
    ("check_total", "succeeded", "outcome_code"),
    (
        (15, True, COUNTERSPELL_INTERRUPTION_OUTCOME_CODE),
        (14, False, COUNTERSPELL_FAILURE_OUTCOME_CODE),
    ),
)
def test_checked_counterspell_success_and_failure_are_closed(
    builder: Builder,
    check_total: int,
    succeeded: bool,
    outcome_code: str,
) -> None:
    """Checked evidence derives success from total against exact DC."""
    result = builder(
        incoming_spell_level=5,
        counterspell_slot_level=3,
        automatic=False,
        check_total=check_total,
        check_dc=15,
        succeeded=succeeded,
        outcome_code=outcome_code,
    )
    assert result.succeeded is succeeded
    assert result.check_total == check_total
    assert result.check_dc == 15


@pytest.mark.parametrize("builder", (_event, _log))
@pytest.mark.parametrize(
    "updates",
    (
        {"incoming_spell_level": 10},
        {"counterspell_slot_level": 2},
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
        },
        {"succeeded": False},
        {"check_total": 20},
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 5,
            "automatic": False,
            "check_total": 20,
            "check_dc": 15,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": None,
            "check_dc": 15,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": 15,
            "check_dc": 14,
        },
        {
            "incoming_spell_level": 5,
            "counterspell_slot_level": 3,
            "automatic": False,
            "check_total": 14,
            "check_dc": 15,
            "succeeded": True,
        },
    ),
)
def test_impossible_counterspell_resolution_is_rejected(
    builder: Builder,
    updates: dict[str, Any],
) -> None:
    """Neither objective event nor typed log accepts contradictions."""
    with pytest.raises(ValidationError):
        builder(**updates)


def test_event_rejects_outcome_code_that_contradicts_success() -> None:
    """The spell-specific event closes code/result consistency."""
    with pytest.raises(
        ValidationError,
        match="outcome code contradicts",
    ):
        _event(outcome_code=COUNTERSPELL_FAILURE_OUTCOME_CODE)


def test_event_log_is_an_exact_typed_copy_of_both_content_roles() -> None:
    """Completion projection copies validated event facts without inference."""
    event = _event(
        incoming_spell_level=5,
        counterspell_slot_level=3,
        automatic=False,
        check_total=15,
        check_dc=15,
        succeeded=True,
        outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
    )

    entry = event.generate_combat_log()
    data = SpellInterruptionLogData.model_validate(entry.data)

    assert entry.success is True
    assert data.outcome_code == event.outcome_code
    assert data.incoming_spell_level == event.incoming_spell_level
    assert data.counterspell_slot_level == event.counterspell_slot_level
    assert data.automatic is event.automatic
    assert data.check_total == event.check_total
    assert data.check_dc == event.check_dc
    assert data.succeeded is event.succeeded
    assert (
        data.reaction_content_identity
        == event.reaction_content_identity
        == REACTION_IDENTITY
    )
    assert (
        data.incoming_spell_content_identity
        == event.incoming_spell_content_identity
        == INCOMING_IDENTITY
    )
    assert data.reaction_content_identity != (
        data.incoming_spell_content_identity
    )


def test_legacy_unbound_content_roles_remain_explicit_none() -> None:
    """Diagnostic events stay representable without invented identities."""
    event = _event(
        reaction_content_identity=None,
        incoming_spell_content_identity=None,
    )

    entry = event.generate_combat_log()
    data = SpellInterruptionLogData.model_validate(entry.data)

    assert event.reaction_content_identity is None
    assert event.incoming_spell_content_identity is None
    assert data.reaction_content_identity is None
    assert data.incoming_spell_content_identity is None
```

## 8. Existing Counterspell regression updates

### 8.1 Live binding assertions

In
`tests/manual/test_50_counterspell_engine_contract.py`, extend
`test_registered_counterspell_freezes_both_reaction_and_spell_bindings()`
after the existing binding-equality assertions with:

```python
assert reaction.reaction_content_identity == (
    handler.behavior_binding.definition_ref.identity_key
)
assert reaction.incoming_spell_content_identity == (
    template.behavior_binding.definition_ref.identity_key
)
assert reaction.outcome_code == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
assert reaction.combat_log is not None
typed_log = SpellInterruptionLogData.model_validate(
    reaction.combat_log.data,
)
assert typed_log.reaction_content_identity == (
    reaction.reaction_content_identity
)
assert typed_log.incoming_spell_content_identity == (
    reaction.incoming_spell_content_identity
)
```

Add `SpellInterruptionLogData` to the existing combat-log import at the top of
that test.

In the first live resource-spending test, retain all existing assertions and
add:

```python
assert interruption_logs[0].data["reaction_content_identity"] is not None
```

The direct unregistered incoming `MagicMissile` in that test may legitimately
have `incoming_spell_content_identity is None`. Do not invent one from its
name.

### 8.2 Direct event fixture updates

Because `CounterspellReactionEvent.outcome_code` becomes required, update both
direct constructors in
`tests/manual/test_121_canonical_presentation_mapper.py`.

Add this import:

```python
from dnd.spells.effect_ids import (
    COUNTERSPELL_FAILURE_OUTCOME_CODE,
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
)
```

In the parameterized constructor, add:

```python
outcome_code=(
    COUNTERSPELL_INTERRUPTION_OUTCOME_CODE
    if succeeded
    else COUNTERSPELL_FAILURE_OUTCOME_CODE
),
reaction_content_identity=reaction_ref.identity_key,
incoming_spell_content_identity=spell_ref.identity_key,
```

In the hidden-reactor automatic-success constructor, add:

```python
outcome_code=COUNTERSPELL_INTERRUPTION_OUTCOME_CODE,
reaction_content_identity=reaction_ref.identity_key,
incoming_spell_content_identity=spell_ref.identity_key,
```

Do not change mapper ownership or presentation cue logic. These fixture facts
make the objective event complete; the existing projector continues to use its
authenticated `BehaviorBinding` inputs and privacy context.

### 8.3 Privacy regression remains mandatory

The existing
`test_subjective_counterspell_log_redacts_an_unseen_reactor()` must remain
unchanged in meaning and green:

- hidden counterspeller name and UUID are absent for observers who cannot
  identify the reactor;
- the counterspeller sees its own identity;
- unrelated observers receive no interruption log;
- the stable outcome remains visible where the reaction outcome is visible.

Authored content identity is not actor identity. Adding
`reaction_content_identity` does not authorize disclosure of the reacting
entity. No redaction branch may use content identity to recover an actor UUID.

## 9. Generated event-contract mirror

The event models are part of the maintained exhaustive engine-event contract.
After production and test edits, run exactly:

```bash
uv run python devtools/generate_event_contract.py
```

This mechanically updates:

```text
server/event_contract.generated.json
```

Then verify:

```bash
uv run python devtools/generate_event_contract.py --check
```

Expected contract changes are limited to:

- `ConditionApplicationDisposition` gaining `"immune"`;
- `ConditionApplicationEvent` gaining nullable string
  `condition_content_identity`;
- `ConditionRemovalEvent` gaining nullable string
  `condition_content_identity`;
- `CounterspellReactionEvent` gaining its two nullable content identities;
- Counterspell level upper bounds if represented by the generator;
- `CounterspellReactionEvent.outcome_code` becoming non-nullable string.

The generator currently describes types, not every Pydantic numeric bound, so
absence of bound metadata from the JSON is not a defect. Do not hand-add
unsupported schema details.

This is a mechanical mirror of core event truth, not authorization to modify a
player SDK, hosted runtime, route, server reducer, or frontend.

## 10. Required behavioral invariants

All of the following must hold:

1. Condition identity derives only from `BehaviorBinding.definition_ref`.
2. Bound condition identity is captured before event admission.
3. Later mutation of the live condition binding cannot alter an existing
   event or log identity.
4. Application and removal for one unchanged bound condition use the same
   identity.
5. Unbound conditions carry explicit `None`; no name, semantic key, UUID, or
   Python path becomes content identity.
6. All condition log payloads validate through `ConditionLogData`.
7. Application dispositions serialize as lowercase closed enum values.
8. `IMMUNE` is false-success evidence and is not confused with `REJECTED`.
9. An immune condition is not installed or completed.
10. The immunity result event is canceled with disposition `IMMUNE`.
11. Removal preserves the existing `reveals_target` fact.
12. Internal conditions still emit no player-facing combat log.
13. Incoming spell level is between zero and nine.
14. Counterspell slot level is between three and nine.
15. Automatic Counterspell always succeeds with no check evidence.
16. Checked Counterspell always uses a lower slot and exact `10 + level` DC.
17. Checked success is exactly `check_total >= check_dc`.
18. Counterspell outcome code exactly matches success/failure.
19. Reaction and incoming-spell identities are separate fields.
20. Both identities are frozen at reaction declaration.
21. Missing bindings remain `None`; names never substitute.
22. Event and log values are field-for-field equal.
23. Counterspell declaration/execution/effect vetoes still spend no resource.
24. Accepted Counterspell still spends exactly one reaction and selected slot.
25. Successful Counterspell still cancels the incoming spell at its existing
    causal boundary.
26. Failed Counterspell still lets the incoming spell continue.
27. Hidden-reactor privacy remains unchanged.
28. Existing canonical presentation behavior remains unchanged.
29. Event-contract generation is fresh and deterministic.
30. No additional engine work occurs during game or encounter creation.

## 11. Performance requirements

The production delta performs only:

- one `isinstance` and one property read per condition declaration;
- construction of one small Pydantic log payload when a condition log is
  already being generated;
- constant-size validation when a Counterspell event/log is constructed;
- two already-available binding reads during a Counterspell reaction.

Expected complexity:

```text
game creation:                 no additional work
condition declaration:         O(1)
condition completion log:      O(1)
Counterspell reaction:         O(1)
unrelated actions/movement:    no additional work
```

Forbidden additions:

- content-registry scans during events;
- action discovery or serialization to determine identity;
- JSON round trips in mechanics;
- player-frame or cue construction in the engine;
- hashes of whole actors, actions, maps, or encounters;
- observer scans added solely for these fields;
- threads, executors, async tasks, queues, retries, persistence artifacts, or
  command coordination;
- server or frontend calls from core engine modules.

## 12. Focused verification sequence

Run only the following focused commands, one test file at a time:

```bash
uv run pytest tests/engine/test_condition_content_evidence.py
uv run pytest tests/engine/test_counterspell_evidence.py
uv run pytest tests/manual/test_50_counterspell_engine_contract.py
uv run pytest tests/manual/test_121_canonical_presentation_mapper.py
uv run pytest tests/manual/test_97_event_wire_contract.py
```

Then run scoped type checking:

```bash
uv run pyright \
  dnd/core/condition_types.py \
  dnd/core/combat_log.py \
  dnd/core/base_conditions.py \
  dnd/entity.py \
  dnd/spells/abjuration.py \
  tests/engine/test_condition_content_evidence.py \
  tests/engine/test_counterspell_evidence.py
```

Do not run the whole pytest suite. Do not batch archived server tests.

Supporting source scans:

```bash
rg -n "condition_content_identity|reaction_content_identity|incoming_spell_content_identity" \
  dnd tests server/event_contract.generated.json

rg -n "semantic_key|__module__|__name__" \
  dnd/core/base_conditions.py dnd/entity.py dnd/spells/abjuration.py
```

The second scan is supporting evidence only. Existing legitimate semantic-key
logic may remain; reviewers must inspect that new authored identity fields do
not use it.

## 13. Review checklist

Before accepting the unit, review the diff for:

- only the files listed in scope;
- no unrelated line-ending normalization;
- no generated JSON hand edits;
- no function-local imports or `TYPE_CHECKING` dependency workarounds;
- no upward import from `dnd/core/combat_log.py`;
- no content identity derived from display or implementation text;
- no mechanics moved into validators or logs;
- no Counterspell resource-order change;
- no swallowed validation exception that allows contradictory objective events;
- no redaction or subjective-projection authority added to the engine;
- no transport/runtime/SDK/frontend changes;
- no background work and no new game-creation cost.

## 14. Explicit exclusions

This unit does not include:

- deterministic random-number service changes;
- reaction selection UI or human prompt coordination;
- general typed reaction evidence for every reaction in the engine;
- condition presentation cues or animation recipes;
- player-product projection changes;
- SDK generation or client migration;
- server command admission, receipts, durability, lookup, or replay;
- hosted control, attachment, takeover, or lobby work;
- changes to condition mechanics, duration, saves, arbitration, or cleanup;
- changes to Counterspell range, visibility, spell-slot choice, ability choice,
  or die rolling;
- spatial-effect enum renames or movement/topology work;
- broad combat-log schema redesign.

## 15. Definition of done

The unit is complete only when:

1. both new focused regression files exist and pass;
2. all three existing focused contract files pass individually;
3. scoped Pyright reports zero errors;
4. `devtools/generate_event_contract.py --check` is green;
5. the checked-in generated manifest contains only expected model-shape drift;
6. live registered Counterspell proves two non-null, distinct authenticated
   content identities;
7. unbound diagnostic construction proves explicit `None` without fallback;
8. immune application proves a canceled `IMMUNE` event, typed log, and zero
   installed condition;
9. hidden-reactor privacy remains green;
10. no server runtime, SDK, frontend, persistence, or background coordination
    code changed.

Anything less is partial implementation, even if the new model classes compile.
