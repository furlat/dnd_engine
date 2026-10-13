"""A rejected pack's native handler registration cannot poison a clean retry."""

from uuid import UUID

import pytest

from dnd.content_system.pack_loader import load_content_system
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def cold_runtime():
    reset_engine_runtime()
    GridMap.reset()
    EventQueue.reset()
    yield
    reset_engine_runtime()
    GridMap.reset()
    EventQueue.reset()


@pytest.mark.parametrize("import_failure", [False, True])
def test_native_handler_registration_rolls_back_before_clean_pack_retry(tmp_path, import_failure):
    pack = tmp_path / "packs" / "handler_rollback"
    package = pack / "src" / "fixture_handler_rollback"
    package.mkdir(parents=True)
    (pack / "content-pack.toml").write_text(
        'schema_version = 1\n'
        'pack_id = "fixture.handler_rollback"\n'
        'pack_version = "1.0.0"\n'
        'engine_content_api = 2\n'
        'python_root = "src"\n'
        'python_package = "fixture_handler_rollback"\n', encoding="utf-8")
    identity = UUID("20000000-0000-0000-0000-000000000011")
    module = package / "__init__.py"
    module.write_text(
        "from uuid import UUID\n"
        "from dnd.core.events import EventHandler, EventQueue, EventType, EventPhase, Trigger\n"
        "handler = EventHandler(\n"
        f"    uuid=UUID('{identity}'), source_entity_uuid=UUID('{identity}'),\n"
        "    name='Rejected import handler', event_processor=lambda event, source: None,\n"
        "    trigger_conditions=[Trigger(event_type=EventType.TURN_START,\n"
        "                                event_phase=EventPhase.EFFECT)])\n"
        "EventQueue.add_event_handler(handler)\n"
        + ("raise RuntimeError('fixture import failed')\n" if import_failure else ""), encoding="utf-8")

    expected = "fixture import failed" if import_failure else "mutated engine runtime state"
    with pytest.raises(RuntimeError, match=expected):
        load_content_system(pack_roots=(pack.parent,))
    assert EventQueue.event_handler_order() == ()
    assert BaseObject.get(identity) is None
    assert EventQueue.event_cursor() == 0

    # No reset between attempts: the loader's own cold-runtime check also
    # rejects a leaked native handler-order counter before accepting this pack.
    module.write_text("PACK_READY = True\n", encoding="utf-8")
    loaded = load_content_system(pack_roots=(pack.parent,))
    assert tuple(value.manifest.pack_id for value in loaded.packs) == ("fixture.handler_rollback",)
    assert EventQueue.event_handler_order() == ()
    assert BaseObject.get(identity) is None
