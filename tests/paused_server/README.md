# Paused server tests

These checks retain the HTTP/database/deployment contracts for the paused server.
They are not native engine tests. They were moved unchanged from
`tests/progression/test_persistent_character_equipment_mutation.py` and
`tests/progression/test_persistent_character_scenario_deployment.py`. The catalog
cold-start probe was split from the active architecture test.

Run explicitly with the project environment:

```sh
python -m pytest tests/paused_server
```

Known blockers: the progression modules import deleted server character modules;
the server catalog imports removed `dnd.core.senses`. No skip, xfail or automatic
collection filter hides these failures. `pytest tests` still includes this lane.

Active acceptance commands:

```sh
python -m pytest tests/engine tests/ai tests/progression
python -m pytest tests/architecture
python -m pytest tests/game
python -m pytest tests/test_*.py
```

Active durable-record and composition coverage lives in
`tests/progression/test_direct_item_durable_and_proficiency.py` and
`tests/progression/test_direct_character_builds.py`; native equipment transfer
and mutation remain under `tests/engine`. These do not certify the paused
server's persistent character directory.
