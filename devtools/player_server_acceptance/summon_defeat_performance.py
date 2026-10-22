"""Bounded caster-defeat comparison using the existing worker timing helpers."""

import argparse
import gc
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
from uuid import uuid4

from dnd.core.dice import fixed_dice_faces
from dnd.core.life_types import LifeState
from dnd.player.session import close_session
from devtools.player_server_acceptance.summon_control_performance import (
    await_actor, cast, choose, discover, execute, population, summary,
)
from monty_sandbox.prepare_trial import summoner_duel_configuration
from server import worker
from server.worker_protocol import Start


CASES = ('ordinary_damage', 'defeat_one', 'defeat_two')


def run_case(case):
    started = perf_counter()
    config = summoner_duel_configuration(Path('/unused'), seed=7)
    runtime, _, _ = worker.start(Start(game_id='summon-defeat-timing', game_epoch=uuid4(),
        audience_ids={seat.seat_id: uuid4() for seat in config.assignments},
        encounter_id=None, recipe=config.recipe, assignments=config.assignments, test_seed=7))
    caster_uuid, = runtime.session.seats['amber'].controlled
    attacker_uuid, = runtime.session.seats['blue'].controlled
    caster = runtime.session.game.entities[caster_uuid]
    try:
        await_actor(runtime, caster_uuid)
        with fixed_dice_faces(*([2] * 1000)):
            if case != 'ordinary_damage':
                cast(runtime, 'weapon', (5, 7))
            if case == 'defeat_two':
                cast(runtime, 'animals', (5, 8))
            await_actor(runtime, attacker_uuid)
        choices, _ = discover(runtime)
        selection = choose(choices, 'spell.guiding_bolt', 1, target=caster_uuid)
        result = {'setup_ms_excluded': (perf_counter() - started) * 1000,
            'before': population(runtime), 'caster_hp_before': caster.get_normal_hp(),
            'operations': {}}
        worker.collect_between_requests()
        # A critical rank-1 bolt deals 48 damage: downing the 38-HP creator
        # without massive-damage instant death. The ordinary bolt deals 8.
        faces = [12, *([2] * 200)] if case == 'ordinary_damage' else [20, *([6] * 200)]
        with fixed_dice_faces(*faces):
            preview, command = execute(runtime, choices, selection)
        result['operations'].update(preview=preview, command=command)
        result.update(after=population(runtime), caster_hp_after=caster.get_normal_hp(),
            caster_life_after=caster.health.life_state.value,
            boundaries={seat: publication.boundary.lifecycle for seat, publication in runtime.publications.items()})
        expected = LifeState.ALIVE if case == 'ordinary_damage' else LifeState.DYING
        if caster.health.life_state is not expected:
            raise RuntimeError(f'Expected {expected}, got {caster.health.life_state}: {result}')
        return result
    finally:
        close_session(runtime.session)
        gc.unfreeze()
        gc.collect()
        gc.freeze()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--samples', type=int, default=3)
    args = parser.parse_args()
    gc.disable()
    gc.collect()
    gc.freeze()
    report = {'label': args.label, 'samples_per_case': args.samples,
        'environment': {'python': sys.version, 'executable': sys.executable,
            'platform': platform.platform(), 'source': str(Path(__file__).resolve().parents[2])},
        'method': {'boundary': 'real worker Command through publication plus canonical response encoding; Preview separately reported',
            'fixture': 'same creator-backed L5 Life Clerics as Monty; both receive the existing equal Conjure Animals scenario grant',
            'setup': 'fresh scene; paid Spiritual Weapon and optionally paid rank-3 Wolf, then normal end-turn commands to Blue; setup/discovery excluded',
            'damage': 'Blue uses real rank-1 Guiding Bolt: nonlethal or critical for caster downing; no HP mutation',
            'samples': 'one excluded fresh-scene warmup then three fresh-scene samples by default',
            'capture': 'existing capture forwarding clock; no native instrumentation or disabled sensory work',
            'gc': 'automatic GC disabled like worker; post-response collection reported separately',
            'excludes': 'network transport, client rendering, agent reasoning and startup/import latency'}, 'cases': {}}
    for case in CASES:
        print(f'{case}: warmup', flush=True)
        warmup = run_case(case)
        samples = []
        for number in range(args.samples):
            print(f'{case}: sample {number + 1}/{args.samples}', flush=True)
            samples.append(run_case(case))
        report['cases'][case] = {'warmup_excluded': warmup, 'samples': samples,
            'summary': summary(samples)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Saved {args.output}', flush=True)


if __name__ == '__main__':
    main()
