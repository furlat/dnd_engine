"""Combat log filtering: temporal visibility + entity anonymization."""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

ANON_NAME = "???"
ANON_POS = "(?,?)"
_COORD_RE = re.compile(r'\(\d+\s*,\s*\d+\)')


def filter_combat_log(
    entries: List[dict],
    controlled_uuids: List[str],
    visible_entity_uuids: Optional[Set[str]] = None,
    parent_revealed: Optional[Set[str]] = None,
) -> List[dict]:
    """Combat log filtering: temporal visibility + entity anonymization.

    Layer 1 (temporal): If observer couldn't perceive the event at the time
    it happened (not in perceiver_uuids), fully anonymize it — names become
    '???' and positions become '(?,?)'. The entry is kept (not dropped) so
    the player knows something happened.

    Layer 2 (identity): Anonymize entity names for entities the observer
    can't currently identify (not in visible_entity_uuids). Entities in
    revealed_entity_uuids (Hidden/Invisible removed mid-event) are treated
    as visible.

    Movement: hidden positions in parent text are replaced with (?,?).

    If visible_entity_uuids is None -> omniscient view (no filtering).
    """
    if visible_entity_uuids is None:
        return entries

    controlled_set = set(controlled_uuids)
    result: List[dict] = []

    for entry in entries:
        # Collect revealed entity UUIDs (entities whose Hidden/Invisible was removed mid-event)
        # Merge with parent's revealed set so sub-entries inherit reveals
        revealed = set(entry.get("revealed_entity_uuids", []))
        if parent_revealed:
            revealed |= parent_revealed

        # Layer 1: temporal — could observer perceive this event?
        perceiver_uuids = set(entry.get("perceiver_uuids", []))
        not_perceived = bool(perceiver_uuids) and not (perceiver_uuids & controlled_set)

        if not_perceived:
            # Check if entry involves a revealed entity — if so, bypass full anonymization
            # (revealed entities were exposed during the parent event chain, observer knows about them)
            source_uuid = entry.get("source_uuid", "")
            target_uuid = entry.get("target_uuid")
            involves_revealed = bool(revealed) and (
                source_uuid in revealed or (target_uuid is not None and target_uuid in revealed)
            )
            if involves_revealed:
                anon = _anonymize_entry(entry, visible_entity_uuids, revealed)
            else:
                # Fully anonymize: names + ALL positions + text
                anon = _full_anonymize(entry)
        else:
            # Layer 2: identity — anonymize hidden entity names only
            # Revealed entities are treated as visible for identity purposes
            anon = _anonymize_entry(entry, visible_entity_uuids, revealed)

        # Recurse into sub_entries (pass revealed set down)
        subs = entry.get("sub_entries", [])
        if subs:
            filtered_subs = filter_combat_log(subs, controlled_uuids, visible_entity_uuids, revealed)
            anon = {**anon, "sub_entries": filtered_subs}

            # Movement: anonymize hidden positions in parent text
            if not not_perceived and entry.get("entry_type") == "movement":
                anon = _anonymize_hidden_movement_positions(anon, subs, controlled_set)

        result.append(anon)

    return result


def _full_anonymize(entry: dict) -> dict:
    """Fully anonymize an imperceivable entry: all names → '???', all positions → '(?,?)'."""
    anon: Dict[str, Any] = {**entry}

    # Anonymize all names
    source_name = entry.get("source_name", "")
    target_name = entry.get("target_name")

    if source_name:
        anon["source_name"] = ANON_NAME
    if target_name:
        anon["target_name"] = ANON_NAME

    # Rewrite text fields: replace names then coordinates
    for field in ("compact", "verbose", "detailed"):
        if field in anon and isinstance(anon[field], str):
            text = anon[field]
            if source_name:
                text = text.replace(source_name, ANON_NAME)
            if target_name:
                text = text.replace(target_name, ANON_NAME)
            text = _COORD_RE.sub(ANON_POS, text)
            anon[field] = text

    return anon


def _anonymize_entry(entry: dict, visible_uuids: Set[str], revealed_uuids: Optional[Set[str]] = None) -> dict:
    """Replace hidden entity names with '???' and positions in movement entries.

    Entities in revealed_uuids are treated as visible (they were revealed
    mid-event-chain, e.g., AoE damage broke Hidden condition).
    """
    effective_visible = (visible_uuids | revealed_uuids) if revealed_uuids else visible_uuids

    source_uuid = entry.get("source_uuid", "")
    target_uuid = entry.get("target_uuid")
    source_name = entry.get("source_name", "")
    target_name = entry.get("target_name")

    source_hidden = bool(source_uuid) and source_uuid not in effective_visible
    target_hidden = bool(target_uuid) and target_uuid not in effective_visible

    if not source_hidden and not target_hidden:
        return entry

    anon: Dict[str, Any] = {**entry}

    if source_hidden and source_name:
        anon["source_name"] = ANON_NAME
        for field in ("compact", "verbose", "detailed"):
            if field in anon and isinstance(anon[field], str):
                anon[field] = anon[field].replace(source_name, ANON_NAME)

    if target_hidden and target_name:
        anon["target_name"] = ANON_NAME
        for field in ("compact", "verbose", "detailed"):
            if field in anon and isinstance(anon[field], str):
                anon[field] = anon[field].replace(target_name, ANON_NAME)

    # Anonymize positions in movement entries when source is hidden
    if source_hidden and entry.get("entry_type") == "movement":
        for field in ("compact", "verbose", "detailed"):
            if field in anon and isinstance(anon[field], str):
                anon[field] = _COORD_RE.sub(ANON_POS, anon[field])

    return anon


def _anonymize_hidden_movement_positions(
    anon: dict,
    original_subs: List[dict],
    controlled_set: Set[str],
) -> dict:
    """Replace coordinates in parent movement text that come from non-perceived steps."""
    perceived_positions: Set[Tuple[int, ...]] = set()
    all_positions: Set[Tuple[int, ...]] = set()

    for sub in original_subs:
        sub_pu = set(sub.get("perceiver_uuids", []))
        sub_data = sub.get("data", {})
        if not isinstance(sub_data, dict):
            continue
        fp = sub_data.get("from_position")
        tp = sub_data.get("to_position")

        if fp:
            all_positions.add(tuple(fp))
        if tp:
            all_positions.add(tuple(tp))

        # Perceived if no perceiver_uuids (legacy) or intersection with controlled
        if not sub_pu or (sub_pu & controlled_set):
            if fp:
                perceived_positions.add(tuple(fp))
            if tp:
                perceived_positions.add(tuple(tp))

    hidden_positions = all_positions - perceived_positions
    if not hidden_positions:
        return anon

    anon = {**anon}
    for field in ("compact", "verbose", "detailed"):
        if field in anon and isinstance(anon[field], str):
            text = anon[field]
            for pos in hidden_positions:
                text = text.replace(f"({pos[0]},{pos[1]})", ANON_POS)
                text = text.replace(f"({pos[0]}, {pos[1]})", ANON_POS)
            anon[field] = text

    return anon
