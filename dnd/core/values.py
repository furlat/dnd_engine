"""Values as data: one record per value, the modifier rows that act on it, and the reads over them.

A value is a slotted record (identity, owner, base, normalizer) whose modifiers
are rows with their channel and kind as columns. Systems add, remove and read
rows; a read takes a `ValueRead` and evaluates a sequence of `Part`s (one value,
or the components of a composed bonus) into a frozen `ValueReading`. Composing
values never builds a new value: the parts are read together.
"""
from enum import Enum
from fractions import Fraction
from math import prod
import random
from types import MappingProxyType
from typing import (Annotated, Any, Callable, ClassVar, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence,
    Tuple)
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic_core import core_schema

from dnd.core.base_object import BaseObject
from dnd.core.creature_types import DamageType, Size
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    AutoHitModifier,
    AutoHitStatus,
    CriticalModifier,
    CriticalStatus,
    DamageTypeModifier,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
    SizeModifier,
)


class Channel(Enum):
    """Which side of a value a modifier row acts on."""

    SELF_STATIC = "self_static"
    TO_TARGET_STATIC = "to_target_static"
    SELF_CONTEXTUAL = "self_contextual"
    TO_TARGET_CONTEXTUAL = "to_target_contextual"
    FIXED = "fixed"


class Kind(Enum):
    """What a modifier row contributes."""

    VALUE = "value"
    MIN = "min"
    MAX = "max"
    FACTOR = "factor"
    ADVANTAGE = "advantage"
    CRITICAL = "critical"
    AUTO_HIT = "auto_hit"
    SIZE = "size"
    DAMAGE_TYPE = "damage_type"
    RESISTANCE = "resistance"


SELF_STATIC, TO_TARGET_STATIC = Channel.SELF_STATIC, Channel.TO_TARGET_STATIC
SELF_CONTEXTUAL, TO_TARGET_CONTEXTUAL, FIXED = Channel.SELF_CONTEXTUAL, Channel.TO_TARGET_CONTEXTUAL, Channel.FIXED
VALUE, MIN, MAX, FACTOR = Kind.VALUE, Kind.MIN, Kind.MAX, Kind.FACTOR
ADVANTAGE, CRITICAL, AUTO_HIT = Kind.ADVANTAGE, Kind.CRITICAL, Kind.AUTO_HIT
SIZE, DAMAGE_TYPE, RESISTANCE = Kind.SIZE, Kind.DAMAGE_TYPE, Kind.RESISTANCE
_CONTEXTUAL_CHANNELS = (SELF_CONTEXTUAL, TO_TARGET_CONTEXTUAL)
_NUMERIC_KINDS = (VALUE, FACTOR, MIN, MAX)


def identity(x: int) -> int:
    """Return an integer unchanged.

    Args:
        x: Integer to return.

    Returns:
        The same integer.
    """
    return x


def _clamped(total: int | Fraction, minimum: int | None, maximum: int | None) -> int | Fraction:
    """Apply an upper then a lower bound; the lower bound wins when they cross."""
    if maximum is not None:
        total = min(total, maximum)
    if minimum is not None:
        total = max(total, minimum)
    return total


def _advantage_status(total: int) -> AdvantageStatus:
    if total > 0:
        return AdvantageStatus.ADVANTAGE
    if total < 0:
        return AdvantageStatus.DISADVANTAGE
    return AdvantageStatus.NONE


def _critical_status(statuses: Sequence[CriticalStatus]) -> CriticalStatus:
    if CriticalStatus.NOCRIT in statuses:
        return CriticalStatus.NOCRIT
    if CriticalStatus.AUTOCRIT in statuses:
        return CriticalStatus.AUTOCRIT
    return CriticalStatus.NONE


def _auto_hit_status(statuses: Sequence[AutoHitStatus]) -> AutoHitStatus:
    if AutoHitStatus.AUTOMISS in statuses:
        return AutoHitStatus.AUTOMISS
    if AutoHitStatus.AUTOHIT in statuses:
        return AutoHitStatus.AUTOHIT
    return AutoHitStatus.NONE


def _resistance_statuses(sums: Dict[DamageType, int]) -> Dict[DamageType, ResistanceStatus]:
    statuses = {}
    for damage_type, sum_value in sums.items():
        if sum_value > 1:
            statuses[damage_type] = ResistanceStatus.IMMUNITY
        elif sum_value == 1:
            statuses[damage_type] = ResistanceStatus.RESISTANCE
        elif sum_value == 0:
            statuses[damage_type] = ResistanceStatus.NONE
        else:
            statuses[damage_type] = ResistanceStatus.VULNERABILITY
    return statuses


class Row(NamedTuple):
    """One modifier acting on a value: its channel, what it contributes, and the modifier itself."""

    channel: Channel
    kind: Kind
    modifier: Any


class ModifiableValue:
    """One value as a record: identity, owner, base contribution, normalizer and modifier rows.

    The base contributes `base` raw and `score_normalizer(base)` normalized, displayed
    as `<name>_base_value`; `base_owner_uuid` gates it like a modifier's contribution
    owner. A removed base (`remove_all_modifiers`) is None: it contributes and shows nothing. `modifiers` holds one row per (channel, kind, modifier uuid), in insertion
    order. The properties below read the value alone with no target or context, through
    the same read functions every other read uses.
    """

    __slots__ = ("uuid", "name", "source_entity_uuid", "source_entity_name", "base", "base_owner_uuid",
                 "score_normalizer", "modifiers")
    _registry: ClassVar[Dict[UUID, "ModifiableValue"]] = {}

    def __init__(self, *, source_entity_uuid: UUID, name: str = "Value", base: int = 0,
                 score_normalizer: Optional[Callable[[int], int]] = None, uuid: Optional[UUID] = None,
                 source_entity_name: Optional[str] = None, base_owner_uuid: Optional[UUID] = None,
                 use_register: bool = True) -> None:
        self.uuid = uuid if uuid is not None else uuid4()
        self.name = name
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name
        self.base: Optional[int] = base
        self.base_owner_uuid = base_owner_uuid
        self.score_normalizer = score_normalizer if score_normalizer is not None else identity
        self.modifiers: Tuple[Row, ...] = ()
        if use_register:
            ModifiableValue._registry[self.uuid] = self

    def __repr__(self) -> str:
        return f"ModifiableValue({self.name!r}, base={self.base}, rows={len(self.modifiers)})"

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.is_instance_schema(cls, serialization=core_schema.plain_serializer_function_ser_schema(
            _value_json, when_used="json"))

    @classmethod
    def get(cls, uuid: UUID) -> Optional["ModifiableValue"]:
        """The registered (owned) value with this uuid, or None."""
        return cls._registry.get(uuid)

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """Remove a value from the registry."""
        cls._registry.pop(uuid, None)

    @property
    def score(self) -> int:
        """Raw total read with no target or context."""
        return value_score(parts(self), ValueRead(self.source_entity_uuid), normalized=False)

    @property
    def normalized_score(self) -> int:
        """Normalized total read with no target or context."""
        return value_score(parts(self), ValueRead(self.source_entity_uuid), normalized=True)

    @property
    def advantage_sum(self) -> int:
        """Signed advantage total read with no target or context."""
        return value_advantage_sum(parts(self), ValueRead(self.source_entity_uuid))

    @property
    def advantage(self) -> AdvantageStatus:
        """Advantage state read with no target or context."""
        return _advantage_status(self.advantage_sum)

    @property
    def critical(self) -> CriticalStatus:
        """Critical override read with no target or context."""
        return value_critical(parts(self), ValueRead(self.source_entity_uuid))

    @property
    def auto_hit(self) -> AutoHitStatus:
        """Hit override read with no target or context."""
        return value_auto_hit(parts(self), ValueRead(self.source_entity_uuid))

    @property
    def size(self) -> Size:
        """Effective size read with no target or context."""
        return value_size(parts(self), ValueRead(self.source_entity_uuid))

    @property
    def damage_types(self) -> List[DamageType]:
        """Most common damage types read with no target or context."""
        return value_damage_types(parts(self), ValueRead(self.source_entity_uuid))

    @property
    def damage_type(self) -> Optional[DamageType]:
        """One of the most common damage types, chosen at random, or None."""
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """Resistance states read with no target or context."""
        return value_resistance(parts(self), ValueRead(self.source_entity_uuid))



def _value_json(value: ModifiableValue) -> Dict[str, Any]:
    """The stated JSON form of a value record."""
    read = ValueRead(value.source_entity_uuid)
    whole = parts(value)
    return {"name": value.name, "uuid": str(value.uuid), "source_entity_uuid": str(value.source_entity_uuid),
            "base": value.base, "score": value_score(whole, read, normalized=False),
            "normalized_score": value_score(whole, read, normalized=True),
            "advantage": _advantage_status(value_advantage_sum(whole, read)).value,
            "critical": value_critical(whole, read).value, "auto_hit": value_auto_hit(whole, read).value,
            "modifiers": [[row.channel.value, row.kind.value, row.modifier.model_dump(mode="json")]
                          for row in value.modifiers]}


def _checked_kind(channel: Channel, kind: Kind) -> None:
    if channel is FIXED and kind is not VALUE:
        raise ValueError("fixed scores are value rows")
    if channel in _CONTEXTUAL_CHANNELS and kind is FACTOR:
        raise ValueError("contextual channels hold no factor rows")


def _with_row(rows: Tuple[Row, ...], new: Row) -> Tuple[Row, ...]:
    """Rows with one more row; a row with the same (channel, kind, uuid) is replaced in place."""
    _checked_kind(new.channel, new.kind)
    identity_uuid = new.modifier.uuid
    for index, row in enumerate(rows):
        if row.channel is new.channel and row.kind is new.kind and row.modifier.uuid == identity_uuid:
            return rows[:index] + (new,) + rows[index + 1:]
    return rows + (new,)


def add_modifier(value: ModifiableValue, channel: Channel, kind: Kind, modifier: Any) -> UUID:
    """Add one modifier row to a value; a row with the same (channel, kind, uuid) is replaced in place."""
    value.modifiers = _with_row(value.modifiers, Row(channel, kind, modifier))
    return modifier.uuid


def remove_modifier(value: ModifiableValue, uuid: UUID, channel: Optional[Channel] = None,
                    kind: Optional[Kind] = None) -> None:
    """Remove a modifier from every row of a value, or only from one channel, or one (channel, kind)."""
    kept = tuple(row for row in value.modifiers if not (row.modifier.uuid == uuid
                 and (channel is None or row.channel is channel) and (kind is None or row.kind is kind)))
    if len(kept) != len(value.modifiers):
        value.modifiers = kept


def modifiers_of(value: ModifiableValue, channel: Channel, kind: Kind) -> tuple:
    """The modifiers of one (channel, kind) of a value, in insertion order."""
    return tuple(row.modifier for row in value.modifiers if row.channel is channel and row.kind is kind)


def modifier_of(value: ModifiableValue, channel: Channel, kind: Kind, uuid: UUID) -> Any:
    """The modifier with this uuid in one (channel, kind) of a value, or None."""
    for row in value.modifiers:
        if row.channel is channel and row.kind is kind and row.modifier.uuid == uuid:
            return row.modifier
    return None


def normalized_base(value: ModifiableValue) -> int:
    """A value's base contribution, normalized; 0 once the base was removed."""
    return value.score_normalizer(value.base) if value.base is not None else 0


def remove_all_modifiers(value: ModifiableValue) -> None:
    """Remove every row of a value and its base contribution."""
    value.modifiers = ()
    value.base = None


def retire_value(value: ModifiableValue) -> None:
    """Release a value: its modifiers leave the object registry and the value leaves the value registry."""
    for row in value.modifiers:
        BaseObject.unregister(row.modifier.uuid)
    remove_all_modifiers(value)
    ModifiableValue.unregister(value.uuid)


class Part(NamedTuple):
    """One value inside a read.

    `rows` is None while the part reads its value live; it holds the value's rows as
    they were when the part was composed (`composed`, a proficiency rule, read-only
    rows), as the old combined and renormalized copies did. `normalizer`, when set,
    replaces the normalizer of the value's base, its static value rows and its fixed
    score (a proficiency rule for one read). `extra` are rows of this read only, each
    read with its own normalizer.
    """

    value: ModifiableValue
    rows: Optional[Tuple[Row, ...]] = None
    normalizer: Optional[Callable[[int], int]] = None
    extra: Tuple[Row, ...] = ()


def _rows_of(item: Part) -> Tuple[Row, ...]:
    return item.value.modifiers if item.rows is None else item.rows


def _taken(item: Part) -> Part:
    """The part with its value's rows taken now (a live part becomes a snapshot)."""
    return item if item.rows is not None else Part(item.value, item.value.modifiers, item.normalizer, item.extra)


def part(value: ModifiableValue, normalizer: Optional[Callable[[int], int]] = None) -> Part:
    """A value as one part of a read: live, or with its rows taken now when a proficiency rule applies."""
    return Part(value) if normalizer is None else Part(value, value.modifiers, normalizer)


def parts(*values: ModifiableValue) -> Tuple[Part, ...]:
    """Values as live parts of one read, in order."""
    return tuple(Part(value) for value in values)


def with_rows(composed_parts: Sequence[Part], rows: Tuple[Row, ...]) -> Tuple[Part, ...]:
    """The parts with rows that apply to this read only (a long-range shot, a formula bonus), added last.

    The rows join the last part as `add_modifier` would add them (one per channel, kind and uuid), each read
    with its own normalizer; the part's own rows are taken now.
    """
    last = _taken(composed_parts[-1])
    extra = last.extra
    for row in rows:
        extra = _with_row(extra, row)
    return (*composed_parts[:-1], Part(last.value, last.rows, last.normalizer, extra))


def _source_checked(composed_parts: Sequence[Part]) -> UUID:
    source = composed_parts[0].value.source_entity_uuid
    for other in composed_parts[1:]:
        if other.value.source_entity_uuid != source:
            raise ValueError("Source entity UUIDs do not match")
    return source


def _outgoing_checked(composed_parts: Sequence[Part], source: UUID) -> None:
    for (channel, kind), entries in _buckets(composed_parts).items():
        if channel is TO_TARGET_STATIC and kind in _NUMERIC_KINDS:
            for modifier, _ in entries:
                if modifier.target_entity_uuid == source:
                    raise ValueError(f"Outgoing modifier target ({modifier.target_entity_uuid}) should not be "
                                     f"the same as the value source ({source})")


def composed(composed_parts: Sequence[Part]) -> Tuple[Part, ...]:
    """Parts read as one bonus, their rows taken now: they share an owner and export no row targeting it."""
    _outgoing_checked(composed_parts, _source_checked(composed_parts))
    return tuple(_taken(item) for item in composed_parts)


def _composed_json(composed_parts: Tuple[Part, ...]) -> Dict[str, Any]:
    """The stated JSON form of a composed value: the read it gives with no target or context."""
    read = ValueRead(composed_parts[0].value.source_entity_uuid)
    return {"name": _joined_name(composed_parts), "source_entity_uuid": str(read.source_entity_uuid),
            "score": value_score(composed_parts, read, normalized=False),
            "normalized_score": value_score(composed_parts, read, normalized=True),
            "advantage": _advantage_status(value_advantage_sum(composed_parts, read)).value,
            "critical": value_critical(composed_parts, read).value,
            "auto_hit": value_auto_hit(composed_parts, read).value,
            "parts": [str(item.value.uuid) for item in composed_parts]}


class _ComposedSchema:
    def __get_pydantic_core_schema__(self, source: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.is_instance_schema(tuple,
            serialization=core_schema.plain_serializer_function_ser_schema(_composed_json, when_used="json"))


ComposedValue = Annotated[Tuple[Part, ...], _ComposedSchema()]


def _joined_name(composed_parts: Sequence[Part]) -> str:
    return "_".join(item.value.name for item in composed_parts)


class OpponentOutgoing(NamedTuple):
    """The opponent's parts in an opposed read (their outgoing rows apply) and the context those rows read."""

    parts: Tuple[Part, ...]
    context: Optional[Dict[str, Any]] = None


class ValueRead(NamedTuple):
    """One read of a value: its owner, the target, the situation and the opponent's outgoing rows.

    The owner's contextual rows are read with (target, context). The opponent's
    outgoing contextual rows are read with (owner, opponent context).
    """

    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None
    opponent: Optional[OpponentOutgoing] = None


def outgoing_of(composed_parts: Sequence[Part], context: Optional[Dict[str, Any]]) -> OpponentOutgoing:
    """The opponent side of an opposed read: one live part, or several composed as one bonus."""
    if len(composed_parts) > 1:
        return OpponentOutgoing(composed(composed_parts), context)
    return OpponentOutgoing(tuple(composed_parts), context)


_DISPLAY_NAMES = {
    "proficiency_bonus_base_value": "Prof",
    "Value_base_value": "Prof",
    "Attack Bonus_base_value": "Base",
    "Melee Attack Bonus_base_value": "Melee",
    "Ranged Attack Bonus_base_value": "Ranged",
    "Damage Bonus_base_value": "Base",
    "strength_modifier_base_value": "STR",
    "dexterity_modifier_base_value": "DEX",
    "constitution_modifier_base_value": "CON",
    "intelligence_modifier_base_value": "INT",
    "wisdom_modifier_base_value": "WIS",
    "charisma_modifier_base_value": "CHA",
    "strength Ability Score_base_value": "STR",
    "dexterity Ability Score_base_value": "DEX",
    "constitution Ability Score_base_value": "CON",
    "intelligence Ability Score_base_value": "INT",
    "wisdom Ability Score_base_value": "WIS",
    "charisma Ability Score_base_value": "CHA",
    "strength Modifier Bonus_base_value": "STR Mod",
    "dexterity Modifier Bonus_base_value": "DEX Mod",
    "constitution Modifier Bonus_base_value": "CON Mod",
    "intelligence Modifier Bonus_base_value": "INT Mod",
    "wisdom Modifier Bonus_base_value": "WIS Mod",
    "charisma Modifier Bonus_base_value": "CHA Mod",
    "ac_bonus_base_value": "Base AC",
    "AC Bonus_base_value": "Base AC",
    "Armor Class_base_value": "Armor",
    "Armor Class Bonus_base_value": "AC Bonus",
    "Max Dex Bonus_base_value": "Max DEX",
}


def _display_name(raw_name: str) -> str:
    """Normalize an internal modifier name for breakdown display."""
    if raw_name in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[raw_name]
    cleaned = raw_name
    for suffix in ["_base_value", "_bonus", "_modifier", " Bonus", " Modifier"]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
    if " Ability Score" in cleaned:
        cleaned = cleaned.replace(" Ability Score", "")
    return cleaned.replace("_", " ").title()


class ValueBreakdownRow(BaseModel):
    """One displayed static numerical row: a flat value or a multiplying factor."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Display name of the contribution.")
    source: str = Field(description="'self' for the owner's rows, 'from_target' for the opponent's outgoing rows.")
    value: int = Field(default=0, description="Normalized flat value; 0 for factor rows.")
    numerator: Optional[int] = Field(default=None, description="Factor numerator for multiplying rows.")
    denominator: Optional[int] = Field(default=None, description="Factor denominator for multiplying rows.")
    operation: Optional[str] = Field(default=None, description="'multiply' for factor rows.")


class AdvantageBreakdownRow(BaseModel):
    """One displayed advantage row; contextual rows record whether they applied in the read."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Display name of the contribution.")
    value: str = Field(description="'advantage', 'disadvantage', a lower-cased contextual status, or 'inactive'.")
    source: str = Field(description="'self', 'from_target', 'self_contextual' or 'from_target_contextual'.")
    active: Optional[bool] = Field(default=None, description="Whether a contextual row applied; None for static rows.")


class ValueChannelReading(BaseModel):
    """One channel's numerical aggregate in a read: totals, bounds and factor."""

    model_config = ConfigDict(frozen=True)

    raw: int = Field(description="Sum of the active raw contributions.")
    normalized: int = Field(description="Sum of the active normalized contributions.")
    minimum: Optional[int] = Field(default=None, description="Lowest active minimum constraint.")
    maximum: Optional[int] = Field(default=None, description="Highest active maximum constraint.")
    factor_numerator: int = Field(default=1, description="Numerator of the product of active factors.")
    factor_denominator: int = Field(default=1, description="Denominator of the product of active factors.")
    factor_keyed: bool = Field(default=False, description="Whether the channel holds factor rows, which select the factor rule.")


class _ChannelNumbers(NamedTuple):
    raw: int
    normalized: int
    minimum: Optional[int]
    maximum: Optional[int]
    factor: Optional[Fraction]
    factor_keyed: bool


def _score_of(channels: Sequence[_ChannelNumbers], normalized: bool) -> int:
    """Sum the channels, multiply once when any factor row exists, then bound.

    Without factors each channel is clamped by its own bounds before the sum, and
    the sum by the lowest minimum and highest maximum of all channels.
    """
    keyed = False
    total = 0
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    for channel in channels:
        low, high = channel.minimum, channel.maximum
        if low is not None and (minimum is None or low < minimum):
            minimum = low
        if high is not None and (maximum is None or high > maximum):
            maximum = high
        keyed = keyed or channel.factor_keyed
    if keyed:
        factor = Fraction(1)
        for channel in channels:
            total += channel.normalized if normalized else channel.raw
            if channel.factor is not None:
                factor *= channel.factor
        return int(_clamped(total * factor, minimum, maximum))
    for channel in channels:
        number = channel.normalized if normalized else channel.raw
        if channel.minimum is not None or channel.maximum is not None:
            number = int(_clamped(number, channel.minimum, channel.maximum))
        total += number
    return int(_clamped(total, minimum, maximum))



def _insert_after_source(rows: tuple, row: BaseModel, source: str, static_only: bool) -> tuple:
    at = 0
    for index, existing in enumerate(rows):
        if existing.source == source and (not static_only or existing.active is None):
            at = index + 1
    return rows[:at] + (row,) + rows[at:]


class ValueReading(BaseModel):
    """A value evaluated once in one read situation: the record that dice, events and logs keep.

    Rows a reaction adds during an attack (Shield, Parry, Protection) enter the
    owner's static channel, so the totals recompute as they did on the composed value.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Name of the value that was read.")
    source_entity_uuid: UUID = Field(description="Entity that owns the value.")
    target_entity_uuid: Optional[UUID] = Field(default=None, description="Entity the value was read against.")
    fixed_score: Optional[int] = Field(default=None, description="Active fixed score, which replaces the channels.")
    fixed_normalized_score: Optional[int] = Field(default=None, description="Normalized active fixed score.")
    channels: tuple[ValueChannelReading, ...] = Field(
        description="Owner static, owner contextual, then opponent contextual and static channels.")
    advantage_sum: int = Field(description="Signed total of the active advantage rows.")
    critical: CriticalStatus = Field(description="Critical override, NOCRIT first.")
    auto_hit: AutoHitStatus = Field(description="Hit override, AUTOMISS first.")
    breakdown: tuple[ValueBreakdownRow, ...] = Field(default=(), description="Static numerical rows, owner first.")
    advantage_breakdown: tuple[AdvantageBreakdownRow, ...] = Field(
        default=(), description="Static advantage rows, then contextual rows with whether they applied.")

    def _total(self, normalized: bool) -> int:
        if self.fixed_score is not None and self.fixed_normalized_score is not None:
            return self.fixed_normalized_score if normalized else self.fixed_score
        return _score_of([_ChannelNumbers(channel.raw, channel.normalized, channel.minimum, channel.maximum,
                                          Fraction(channel.factor_numerator, channel.factor_denominator),
                                          channel.factor_keyed) for channel in self.channels], normalized)

    @computed_field
    @property
    def score(self) -> int:
        """Raw total of the read."""
        return self._total(False)

    @computed_field
    @property
    def normalized_score(self) -> int:
        """Normalized total of the read; what dice add."""
        return self._total(True)

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """Advantage state of the read."""
        return _advantage_status(self.advantage_sum)


_Entry = Tuple[Any, Optional[Callable[[int], int]]]
_Buckets = Mapping[Tuple[Channel, Kind], List[_Entry]]
_NO_BUCKETS: Mapping[Tuple[Channel, Kind], List[_Entry]] = MappingProxyType({})


def _buckets(composed_parts: Sequence[Part]) -> _Buckets:
    """The parts' rows by (channel, kind), one per (channel, kind, uuid): last wins at its first position.

    One part without read-only rows is already one row per key (`add_modifier`); everything else is merged.
    """
    if len(composed_parts) == 1 and not composed_parts[0].extra:
        only = composed_parts[0]
        rows = _rows_of(only)
        if not rows:
            return _NO_BUCKETS
        single: Dict[Tuple[Channel, Kind], List[_Entry]] = {}
        for row in rows:
            single.setdefault((row.channel, row.kind), []).append((row.modifier, only.normalizer))
        return single
    merged: Dict[Tuple[Channel, Kind, UUID], Tuple[Row, Optional[Callable[[int], int]]]] = {}
    for item in composed_parts:
        for row in _rows_of(item):
            merged[(row.channel, row.kind, row.modifier.uuid)] = (row, item.normalizer)
        for row in item.extra:
            merged[(row.channel, row.kind, row.modifier.uuid)] = (row, None)
    buckets: Dict[Tuple[Channel, Kind], List[_Entry]] = {}
    for (channel, kind, _), (row, normalizer) in merged.items():
        buckets.setdefault((channel, kind), []).append((row.modifier, normalizer))
    return buckets


def _bases(composed_parts: Sequence[Part]) -> List[Tuple[int, Optional[UUID], Callable[[int], int]]]:
    """Each part value's present base (raw, owner gate, normalizer it is read with), one per value."""
    merged = {}
    for item in composed_parts:
        if item.value.base is not None:
            merged[item.value.uuid] = (item.value.base, item.value.base_owner_uuid,
                                       item.normalizer if item.normalizer is not None else item.value.score_normalizer)
    return list(merged.values())


def _owner_allows(owner_uuid: Optional[UUID]) -> bool:
    if owner_uuid is None:
        return True
    owner = BaseObject.get_contribution_owner(owner_uuid)
    return owner is not None and owner.allows_contribution_at(None)


def _row_normalized(modifier: NumericalModifier, normalizer: Optional[Callable[[int], int]]) -> int:
    return normalizer(modifier.value) if normalizer is not None else modifier.normalized_value


def _static_numbers(buckets: _Buckets, channel: Channel,
                    bases: Sequence[Tuple[int, Optional[UUID], Callable[[int], int]]],
                    excluded: frozenset[UUID], sides: Tuple[bool, bool]) -> "_ChannelNumbers":
    """A static channel's totals (raw and/or normalized, as `sides` asks), bounds and factor."""
    raw = normalized = 0
    for base, owner_uuid, normalizer in bases:
        if _owner_allows(owner_uuid):
            if sides[0]:
                raw += base
            if sides[1]:
                normalized += normalizer(base)
    for modifier, normalizer in buckets.get((channel, VALUE), ()):
        if modifier.uuid in excluded or not modifier.contributions_active():
            continue
        if sides[0]:
            raw += modifier.value
        if sides[1]:
            normalized += _row_normalized(modifier, normalizer)
    minima = buckets.get((channel, MIN))
    maxima = buckets.get((channel, MAX))
    factors = buckets.get((channel, FACTOR))
    return _ChannelNumbers(
        raw, normalized,
        min((modifier.value for modifier, _ in minima if modifier.uuid not in excluded
             and modifier.contributions_active()), default=None) if minima else None,
        max((modifier.value for modifier, _ in maxima if modifier.uuid not in excluded
             and modifier.contributions_active()), default=None) if maxima else None,
        prod((Fraction(modifier.numerator, modifier.denominator) for modifier, _ in factors
              if modifier.uuid not in excluded and modifier.contributions_active()), start=Fraction(1))
        if factors else None,
        any(modifier.uuid not in excluded for modifier, _ in factors) if factors else False)


def _contextual_numbers(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                        context: Optional[Dict[str, Any]]) -> "_ChannelNumbers":
    """A contextual channel's totals and bounds in one read situation; each callable is evaluated once."""
    raw = normalized = 0
    for modifier, _ in buckets.get((channel, VALUE), ()):
        result = modifier.evaluate(source, target, context)
        if isinstance(result, NumericalModifier):
            raw += result.value
            normalized += result.normalized_value
    minima = buckets.get((channel, MIN))
    maxima = buckets.get((channel, MAX))
    minimum = min(_numerical_results(minima, source, target, context), default=None) if minima else None
    maximum = max(_numerical_results(maxima, source, target, context), default=None) if maxima else None
    return _ChannelNumbers(raw, normalized, minimum, maximum, None, False)


def _numerical_results(entries: List[_Entry], source: UUID, target: Optional[UUID],
                       context: Optional[Dict[str, Any]]) -> List[int]:
    results = [modifier.evaluate(source, target, context) for modifier, _ in entries]
    return [result.value for result in results if isinstance(result, NumericalModifier)]


def _opponent(read: ValueRead) -> Tuple[_Buckets, UUID]:
    opponent = read.opponent
    assert opponent is not None
    return _buckets(opponent.parts), opponent.parts[0].value.source_entity_uuid


def _channel_numbers(composed_parts: Sequence[Part], buckets: _Buckets, read: ValueRead, excluded: frozenset[UUID],
                     sides: Tuple[bool, bool]) -> List["_ChannelNumbers"]:
    """Each channel's totals in this read, in score order (owner static, owner contextual, opponent)."""
    source = composed_parts[0].value.source_entity_uuid
    channels = [_static_numbers(buckets, SELF_STATIC, _bases(composed_parts), excluded, sides),
                _contextual_numbers(buckets, SELF_CONTEXTUAL, source, read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        channels.append(_contextual_numbers(opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source,
                                            read.source_entity_uuid, read.opponent.context))
        channels.append(_static_numbers(opponent_buckets, TO_TARGET_STATIC, (), excluded, sides))
    return channels


def _fixed_score(buckets: _Buckets, excluded: frozenset[UUID]) -> Optional[int]:
    rows = buckets.get((FIXED, VALUE))
    if not rows:
        return None
    fixed = [modifier.value for modifier, _ in rows if modifier.uuid not in excluded and modifier.contributions_active()]
    return min(fixed) if fixed else None


def _fixed_normalizer(composed_parts: Sequence[Part]) -> Callable[[int], int]:
    first = composed_parts[0]
    return first.normalizer if first.normalizer is not None else first.value.score_normalizer


def value_score(composed_parts: Sequence[Part], read: ValueRead, *, normalized: bool,
                excluded: frozenset[UUID] = frozenset()) -> int:
    """A read's total: channels summed, multiplied exactly once, then bounded (and normalized)."""
    buckets = _buckets(composed_parts)
    fixed = _fixed_score(buckets, excluded)
    if fixed is not None:
        return _fixed_normalizer(composed_parts)(fixed) if normalized else fixed
    return _score_of(_channel_numbers(composed_parts, buckets, read, excluded, (not normalized, normalized)),
                     normalized)


def _static_advantage_sum(buckets: _Buckets, channel: Channel) -> int:
    return sum(modifier.numerical_value for modifier, _ in buckets.get((channel, ADVANTAGE), ())
               if modifier.contributions_active())


def _contextual_advantage_results(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                                  context: Optional[Dict[str, Any]]) -> List[Tuple[Any, Any]]:
    """Each contextual advantage row with its result in one read situation."""
    return [(modifier, modifier.evaluate(source, target, context))
            for modifier, _ in buckets.get((channel, ADVANTAGE), ())]


def _contextual_advantage_sum(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                              context: Optional[Dict[str, Any]]) -> int:
    return sum(result.numerical_value for _, result in
               _contextual_advantage_results(buckets, channel, source, target, context)
               if isinstance(result, AdvantageModifier))


def value_advantage_sum(composed_parts: Sequence[Part], read: ValueRead) -> int:
    """Signed advantage total of a read: owner static and contextual rows, then the opponent's outgoing rows."""
    buckets = _buckets(composed_parts)
    total = _static_advantage_sum(buckets, SELF_STATIC) + _contextual_advantage_sum(
        buckets, SELF_CONTEXTUAL, composed_parts[0].value.source_entity_uuid, read.target_entity_uuid, read.context)
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        total += _static_advantage_sum(opponent_buckets, TO_TARGET_STATIC) + _contextual_advantage_sum(
            opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source, read.source_entity_uuid, read.opponent.context)
    return total


def _static_status(buckets: _Buckets, channel: Channel, kind: Kind) -> List[Any]:
    return [modifier.value for modifier, _ in buckets.get((channel, kind), ()) if modifier.contributions_active()]


def _contextual_status(buckets: _Buckets, channel: Channel, kind: Kind, payload: type, source: UUID,
                       target: Optional[UUID], context: Optional[Dict[str, Any]]) -> List[Any]:
    results = [modifier.evaluate(source, target, context) for modifier, _ in buckets.get((channel, kind), ())]
    return [result.value for result in results if isinstance(result, payload)]


def _override(composed_parts: Sequence[Part], read: ValueRead, kind: Kind, payload: type,
              status: Callable[[Sequence[Any]], Any]) -> Any:
    """A critical or hit override: each channel's status, then the read's, by precedence."""
    buckets = _buckets(composed_parts)
    statuses = [status(_static_status(buckets, SELF_STATIC, kind)),
                status(_contextual_status(buckets, SELF_CONTEXTUAL, kind, payload,
                                          composed_parts[0].value.source_entity_uuid,
                                          read.target_entity_uuid, read.context))]
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        statuses += [status(_contextual_status(opponent_buckets, TO_TARGET_CONTEXTUAL, kind, payload, opponent_source,
                                               read.source_entity_uuid, read.opponent.context)),
                     status(_static_status(opponent_buckets, TO_TARGET_STATIC, kind))]
    return status(statuses)


def value_critical(composed_parts: Sequence[Part], read: ValueRead) -> CriticalStatus:
    """Critical override of a read; NOCRIT takes precedence."""
    return _override(composed_parts, read, CRITICAL, CriticalModifier, _critical_status)


def value_auto_hit(composed_parts: Sequence[Part], read: ValueRead) -> AutoHitStatus:
    """Hit override of a read; AUTOMISS takes precedence."""
    return _override(composed_parts, read, AUTO_HIT, AutoHitModifier, _auto_hit_status)


_SIZE_ORDER = {size: index for index, size in enumerate(Size)}


def _largest(sizes: Sequence[Size]) -> Size:
    return max(sizes, key=_SIZE_ORDER.__getitem__) if sizes else Size.MEDIUM


def _static_size(buckets: _Buckets, channel: Channel) -> Size:
    rows = buckets.get((channel, SIZE))
    if not rows:
        return Size.MEDIUM
    return _largest([modifier.value for modifier, _ in rows if modifier.contributions_active()])


def _contextual_size(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                     context: Optional[Dict[str, Any]]) -> Size:
    rows = buckets.get((channel, SIZE))
    if not rows:
        return Size.MEDIUM
    return _largest(_contextual_status(buckets, channel, SIZE, SizeModifier, source, target, context))


def value_size(composed_parts: Sequence[Part], read: ValueRead) -> Size:
    """Effective size of a read: the largest non-medium size of its channels."""
    buckets = _buckets(composed_parts)
    sizes = [size for size in (_static_size(buckets, SELF_STATIC),
                               _contextual_size(buckets, SELF_CONTEXTUAL, composed_parts[0].value.source_entity_uuid,
                                                read.target_entity_uuid, read.context)) if size != Size.MEDIUM]
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        sizes += [size for size in (_contextual_size(opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source,
                                                     read.source_entity_uuid, read.opponent.context),
                                    _static_size(opponent_buckets, TO_TARGET_STATIC)) if size != Size.MEDIUM]
    return _largest(sizes)


def _most_common(types: Iterable[DamageType]) -> List[DamageType]:
    counts: Dict[DamageType, int] = {}
    for damage_type in types:
        counts[damage_type] = counts.get(damage_type, 0) + 1
    if not counts:
        return []
    top = max(counts.values())
    return [damage_type for damage_type, count in counts.items() if count == top]


def _static_damage_types(buckets: _Buckets, channel: Channel) -> List[DamageType]:
    return _most_common(_static_status(buckets, channel, DAMAGE_TYPE))


def _contextual_damage_types(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                             context: Optional[Dict[str, Any]]) -> List[DamageType]:
    if not buckets.get((channel, DAMAGE_TYPE)):
        return []
    return _most_common(_contextual_status(buckets, channel, DAMAGE_TYPE, DamageTypeModifier, source, target, context))


def value_damage_types(composed_parts: Sequence[Part], read: ValueRead) -> List[DamageType]:
    """Most common damage types of a read: the most common of each channel, counted across channels."""
    buckets = _buckets(composed_parts)
    source = composed_parts[0].value.source_entity_uuid
    groups = [_static_damage_types(buckets, SELF_STATIC), _static_damage_types(buckets, TO_TARGET_STATIC),
              _contextual_damage_types(buckets, SELF_CONTEXTUAL, source, read.target_entity_uuid, read.context),
              _contextual_damage_types(buckets, TO_TARGET_CONTEXTUAL, source, read.target_entity_uuid, read.context)]
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        groups += [_static_damage_types(opponent_buckets, TO_TARGET_STATIC),
                   _contextual_damage_types(opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source,
                                            read.source_entity_uuid, read.opponent.context)]
    return _most_common(damage_type for group in groups for damage_type in group)


def _static_resistance(buckets: _Buckets, channel: Channel, total: Dict[DamageType, int]) -> None:
    for modifier, _ in buckets.get((channel, RESISTANCE), ()):
        if modifier.contributions_active():
            total[modifier.damage_type] += modifier.numerical_value


def _contextual_resistance(buckets: _Buckets, channel: Channel, source: UUID, target: Optional[UUID],
                           context: Optional[Dict[str, Any]], total: Dict[DamageType, int]) -> None:
    for modifier, _ in buckets.get((channel, RESISTANCE), ()):
        result = modifier.evaluate(source, target, context)
        if isinstance(result, ResistanceModifier):
            total[result.damage_type] += result.numerical_value


def value_resistance_sum(composed_parts: Sequence[Part], read: ValueRead) -> Dict[DamageType, int]:
    """Signed resistance totals of a read, over its own, outgoing and the opponent's outgoing rows."""
    buckets = _buckets(composed_parts)
    source = composed_parts[0].value.source_entity_uuid
    total = {damage_type: 0 for damage_type in DamageType}
    _static_resistance(buckets, SELF_STATIC, total)
    _static_resistance(buckets, TO_TARGET_STATIC, total)
    _contextual_resistance(buckets, SELF_CONTEXTUAL, source, read.target_entity_uuid, read.context, total)
    _contextual_resistance(buckets, TO_TARGET_CONTEXTUAL, source, read.target_entity_uuid, read.context, total)
    if read.opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        _static_resistance(opponent_buckets, TO_TARGET_STATIC, total)
        _contextual_resistance(opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source, read.source_entity_uuid,
                               read.opponent.context, total)
    return total


def value_resistance(composed_parts: Sequence[Part], read: ValueRead) -> Dict[DamageType, ResistanceStatus]:
    """Resistance states of a read."""
    return _resistance_statuses(value_resistance_sum(composed_parts, read))


def _value_rows(composed_parts: Sequence[Part], buckets: _Buckets, channel: Channel, source: str,
                with_bases: bool) -> List[ValueBreakdownRow]:
    """Displayed static numerical rows: factors, then each base and value row in composition order."""
    rows = [ValueBreakdownRow(name=_display_name(modifier.name or "Factor"), source=source,
                              numerator=modifier.numerator, denominator=modifier.denominator, operation="multiply")
            for modifier, _ in buckets.get((channel, FACTOR), ())]
    ordered: Dict[Tuple[str, UUID], Tuple[str, int]] = {}
    for item in composed_parts:
        if with_bases and item.value.base is not None:
            normalizer = item.normalizer if item.normalizer is not None else item.value.score_normalizer
            ordered[("base", item.value.uuid)] = (f"{item.value.name}_base_value", normalizer(item.value.base))
        for row in _rows_of(item):
            if row.channel is channel and row.kind is VALUE:
                ordered[("row", row.modifier.uuid)] = (row.modifier.name or "Unknown",
                                                       _row_normalized(row.modifier, item.normalizer))
        for row in item.extra:
            if row.channel is channel and row.kind is VALUE:
                ordered[("row", row.modifier.uuid)] = (row.modifier.name or "Unknown", _row_normalized(row.modifier, None))
    for name, value in ordered.values():
        if value != 0:
            rows.append(ValueBreakdownRow(name=_display_name(name), source=source, value=value))
    return rows


def value_breakdown(composed_parts: Sequence[Part]) -> List[ValueBreakdownRow]:
    """The owner's static numerical rows of a read, for display."""
    return _value_rows(composed_parts, _buckets(composed_parts), SELF_STATIC, "self", True)


def _static_advantage_rows(entries: Iterable[_Entry], source: str) -> List[AdvantageBreakdownRow]:
    rows = []
    for modifier, _ in entries:
        if modifier.value == AdvantageStatus.ADVANTAGE:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="advantage", source=source))
        elif modifier.value == AdvantageStatus.DISADVANTAGE:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="disadvantage", source=source))
    return rows


def _contextual_advantage(buckets: _Buckets, channel: Channel, source_uuid: UUID, target: Optional[UUID],
                          context: Optional[Dict[str, Any]], source: str) -> Tuple[int, List[AdvantageBreakdownRow]]:
    """Signed advantage total and display rows of one contextual channel; each callable is evaluated once."""
    total = 0
    rows = []
    for modifier, result in _contextual_advantage_results(buckets, channel, source_uuid, target, context):
        if isinstance(result, AdvantageModifier):
            total += result.numerical_value
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value=result.value.value.lower(),
                                              source=source, active=True))
        else:
            rows.append(AdvantageBreakdownRow(name=modifier.name or "Unknown", value="inactive",
                                              source=source, active=False))
    return total, rows


def read_value(composed_parts: Sequence[Part], read: ValueRead) -> ValueReading:
    """Evaluate parts once in a read situation; the frozen record dice and events keep."""
    opponent = read.opponent
    buckets = _buckets(composed_parts)
    fixed = _fixed_score(buckets, frozenset())
    source = composed_parts[0].value.source_entity_uuid
    own_total, own_rows = _contextual_advantage(buckets, SELF_CONTEXTUAL, source, read.target_entity_uuid,
                                                read.context, "self_contextual")
    advantage_sum = _static_advantage_sum(buckets, SELF_STATIC) + own_total
    breakdown = _value_rows(composed_parts, buckets, SELF_STATIC, "self", True)
    static_rows = _static_advantage_rows(buckets.get((SELF_STATIC, ADVANTAGE), ()), "self")
    contextual_rows = own_rows
    if opponent is not None:
        opponent_buckets, opponent_source = _opponent(read)
        opponent_total, opponent_rows = _contextual_advantage(opponent_buckets, TO_TARGET_CONTEXTUAL, opponent_source,
                                                              read.source_entity_uuid, opponent.context,
                                                              "from_target_contextual")
        advantage_sum += _static_advantage_sum(opponent_buckets, TO_TARGET_STATIC) + opponent_total
        breakdown += _value_rows(opponent.parts, opponent_buckets, TO_TARGET_STATIC, "from_target", False)
        static_rows += _static_advantage_rows(opponent_buckets.get((TO_TARGET_STATIC, ADVANTAGE), ()), "from_target")
        contextual_rows += opponent_rows
    return ValueReading(
        name=_joined_name(composed_parts), source_entity_uuid=source, target_entity_uuid=read.target_entity_uuid,
        fixed_score=fixed,
        fixed_normalized_score=_fixed_normalizer(composed_parts)(fixed) if fixed is not None else None,
        channels=tuple(ValueChannelReading(raw=channel.raw, normalized=channel.normalized, minimum=channel.minimum,
            maximum=channel.maximum,
            factor_numerator=channel.factor.numerator if channel.factor is not None else 1,
            factor_denominator=channel.factor.denominator if channel.factor is not None else 1,
            factor_keyed=channel.factor_keyed)
            for channel in _channel_numbers(composed_parts, buckets, read, frozenset(), (True, True))),
        advantage_sum=advantage_sum,
        critical=value_critical(composed_parts, read), auto_hit=value_auto_hit(composed_parts, read),
        breakdown=tuple(breakdown), advantage_breakdown=tuple(static_rows + contextual_rows))


def reading_with_value_row(reading: ValueReading, modifier: NumericalModifier) -> ValueReading:
    """The read with one more owner static numerical row (a reaction's AC bonus)."""
    own = reading.channels[0]
    if modifier.contributions_active():
        own = own.model_copy(update={"raw": own.raw + modifier.value,
                                     "normalized": own.normalized + modifier.normalized_value})
    rows = reading.breakdown
    if modifier.normalized_value != 0:
        rows = _insert_after_source(rows, ValueBreakdownRow(name=_display_name(modifier.name or "Unknown"),
                                    source="self", value=modifier.normalized_value), "self", False)
    return reading.model_copy(update={"channels": (own, *reading.channels[1:]), "breakdown": rows})


def reading_with_advantage_row(reading: ValueReading, modifier: AdvantageModifier) -> ValueReading:
    """The read with one more owner static advantage row (a reaction's disadvantage)."""
    total = reading.advantage_sum + (modifier.numerical_value if modifier.contributions_active() else 0)
    rows = reading.advantage_breakdown
    for row in _static_advantage_rows(((modifier, None),), "self"):
        rows = _insert_after_source(rows, row, "self", True)
    return reading.model_copy(update={"advantage_sum": total, "advantage_breakdown": rows})


def has_static_advantage_row(reading: ValueReading, name: str) -> bool:
    """Whether the owner's static rows of the read hold an advantage row with this name."""
    return any(row.source == "self" and row.active is None and row.name == name
               for row in reading.advantage_breakdown)
