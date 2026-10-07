"""Headless native fixture cost samples; no renderer or substitute event records."""

import argparse
from collections import Counter
import cProfile
from functools import partial
import json
from pathlib import Path
import pstats
from time import perf_counter

from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.equipment_types import WeaponSlot
from dnd.player.recorded import RecordedSequence, project_sequence
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.combat_demo import capture_combat_demo
from devtools.animation_review.summoning_cases import summoning_history
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.interruption_scenarios import interruption_history
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.scenarios import attack_history
from tests.game.scorching_scenarios import scorching_history
from tests.game.spell_handoff_scenarios import spell_handoff_history
from tests.game.support_conditions_scenarios import support_condition_history
from tests.game.wall_spell_scenarios import wall_spell_history
from devtools.player_server_acceptance.performance import fingerprint


CASES = {
    'melee': partial(attack_history, 'weapon.shortsword', 0),
    'ranged': partial(attack_history, 'weapon.shortbow', 0, weapon_slot=WeaponSlot.RANGED_MAIN),
    'opportunity': partial(attack_history, 'weapon.shortsword', 0, opportunity=True),
    'magic-missile-aba': partial(capture_combat_demo, magic_missile=True),
    'scorching-aba': partial(scorching_history, split=True),
    'scorching-aba-miss': partial(scorching_history, split=True, miss=True),
    'eldritch-three-aba': partial(spell_handoff_history, program='eldritch', level=11, split=True),
    'fireball-open': partial(spell_handoff_history, program='fireball'),
    'fireball-wall': partial(spell_handoff_history, program='fireball', environment='wall-east'),
    'wall-fire': partial(wall_spell_history, multiple_targets=True),
    'call-lightning-repeat': partial(area_spell_history, program='call_lightning'),
    'shield-missile': partial(persistent_spell_history, program='shield', shield_delivery='missile'),
    'stoneskin': partial(support_condition_history, program='stoneskin'),
    'counterspell': partial(interruption_history, blocker='counterspell'),
    'summon-bear': partial(summoning_history, form='brown_bear', family='animals', slot=4),
    'summon-fey-release': partial(summoning_history, form='jaguar', family='fey', slot=6, release_control=True),
    'wall-ring': partial(wall_spell_history, ring_hot_side='inside'),
}


def sample(name: str, *, profiled: bool, output: Path) -> dict:
    producer = CASES[name]
    profiler = cProfile.Profile()
    phases: dict[str, list[float]] = {}
    token = set_action_timing_recorder(lambda phase, start: phases.setdefault(phase, []).append((perf_counter() - start) * 1000))
    started = perf_counter()
    if profiled:
        profiler.enable()
    try:
        captured = producer()
    finally:
        reset_action_timing_recorder(token)
        if profiled:
            profiler.disable()
    elapsed = (perf_counter() - started) * 1000
    views = captured.views or {'primary': RecordedSequence(initialization=captured.initialization, lineages=captured.lineages)}
    public = []
    for role, native in views.items():
        started = perf_counter()
        sequence = project_sequence(native)
        projection_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        raw = encode_player_sequence(sequence)
        encode_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        state, lineages = decode_player_sequence(raw)
        for lineage in lineages:
            state = reduce_lineage(state, lineage)
        reduced_ms = (perf_counter() - started) * 1000
        facts = Counter(node.fact.kind for lineage in sequence.lineages for node in lineage.events if node.fact is not None)
        public.append({'role': role, 'native_roots': len(native.lineages),
            'native_occurrences': sum(len(lineage.events) for lineage in native.lineages),
            'initialization_cursor': native.initialization.end_cursor, 'public_roots': len(sequence.lineages),
            'bytes': len(raw), 'projection_ms': projection_ms, 'encode_ms': encode_ms,
            'cold_decode_reduction_ms': reduced_ms, 'final_reducer_cursor': state.reducer_cursor,
            'facts': dict(facts), 'actors': [{'name': actor.name, 'hp': actor.normal_hp,
                'life_state': actor.life_state.value, 'position': actor.last_visual_position}
                for actor in sorted(state.actors.values(), key=lambda actor: actor.name)]})
    result = {'case': name, 'fixture': producer.func.__module__ + '.' + producer.func.__name__,
        'profiled': profiled, 'native_fixture_including_setup_capture_ms': elapsed, 'views': public,
        'action_phases_ms': phases}
    if profiled:
        destination = output / (name + '.pstats')
        profiler.dump_stats(str(destination))
        owners = [{'file': key[0], 'line': key[1], 'function': key[2], 'calls': value[1],
            'self_ms': value[2] * 1000, 'inclusive_ms': value[3] * 1000}
            for key, value in pstats.Stats(profiler).stats.items() if '/dnd_engine/' in key[0]]
        result.update(profile=str(destination),
            top_inclusive=sorted(owners, key=lambda row: row['inclusive_ms'], reverse=True)[:30],
            top_self=sorted(owners, key=lambda row: row['self_ms'], reverse=True)[:25])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cases', nargs='+', choices=tuple(CASES), default=list(CASES))
    parser.add_argument('--samples', type=int, default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    environment = fingerprint()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    result = {'kind': 'native-fixture-samples', 'environment': environment, 'samples': [], 'failures': [],
        'scope': f'{args.samples} unprofiled and one profiled native fixture executions per case, setup/capture included; no rendering.'}
    for name in args.cases:
        try:
            rows = [sample(name, profiled=False, output=args.output) for _ in range(args.samples)]
            rows.append(sample(name, profiled=True, output=args.output))
            result['samples'].extend(rows)
            print(json.dumps({'case': name, 'unprofiled_fixture_ms': rows[0]['native_fixture_including_setup_capture_ms']}), flush=True)
        except Exception as exc:
            result['failures'].append({'case': name, 'error': str(exc)})
            print(json.dumps(result['failures'][-1]), flush=True)
        (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    if result['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
