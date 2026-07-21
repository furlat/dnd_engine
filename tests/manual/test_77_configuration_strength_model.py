from ai.evaluation.config_ladder.contracts import RatedOutcome, StrengthObservation
from ai.evaluation.config_ladder.strength_model import fit_configuration_strength


def test_adjusted_strength_model_recovers_order_and_context_effects() -> None:
    observations: list[StrengthObservation] = []
    hero_wins = {
        ("hero.strong", "monsters.weak"): 18,
        ("hero.strong", "monsters.strong"): 13,
        ("hero.weak", "monsters.weak"): 11,
        ("hero.weak", "monsters.strong"): 4,
    }
    for hero_id in ("hero.strong", "hero.weak"):
        for monster_id in ("monsters.weak", "monsters.strong"):
            wins = hero_wins[(hero_id, monster_id)]
            for index in range(20):
                observations.append(StrengthObservation(
                    match_id=f"{hero_id}-{monster_id}-{index}",
                    pair_block_id=f"block-{hero_id}-{monster_id}-{index // 2}",
                    hero_configuration_id=hero_id,
                    monster_configuration_id=monster_id,
                    battlefield_id="field.open" if index % 4 < 2 else "field.door",
                    deployment_id="deployment.default",
                    opening_treatment="hero_first" if index % 2 == 0 else "monster_first",
                    outcome=RatedOutcome.HERO_WIN if index < wins else RatedOutcome.MONSTER_WIN,
                ))

    result = fit_configuration_strength(observations, regularization=0.25)
    reversed_result = fit_configuration_strength(list(reversed(observations)), regularization=0.25)

    hero_ratings = {row.configuration_id: row.adjusted_elo for row in result.hero_ratings}
    monster_ratings = {row.configuration_id: row.adjusted_elo for row in result.monster_ratings}
    reversed_heroes = {row.configuration_id: row.adjusted_elo for row in reversed_result.hero_ratings}

    assert result.converged
    assert hero_ratings["hero.strong"] > hero_ratings["hero.weak"]
    assert monster_ratings["monsters.strong"] > monster_ratings["monsters.weak"]
    assert hero_ratings == reversed_heroes
    assert result.design.connected
    assert result.design.rank == result.design.parameter_count
    assert result.log_loss >= 0
    assert result.brier_score >= 0


def test_disconnected_observations_are_not_published_as_global_ratings() -> None:
    observations = [
        StrengthObservation(
            match_id="a",
            pair_block_id="a",
            hero_configuration_id="hero.a",
            monster_configuration_id="monsters.a",
            battlefield_id="field.open",
            deployment_id="deployment.default",
            opening_treatment="hero_first",
            outcome=RatedOutcome.HERO_WIN,
        ),
        StrengthObservation(
            match_id="b",
            pair_block_id="b",
            hero_configuration_id="hero.b",
            monster_configuration_id="monsters.b",
            battlefield_id="field.open",
            deployment_id="deployment.default",
            opening_treatment="monster_first",
            outcome=RatedOutcome.MONSTER_WIN,
        ),
    ]

    result = fit_configuration_strength(observations, regularization=0.25)

    assert not result.design.connected
    assert result.publishable is False
    assert "participant_graph_disconnected" in result.gate_reasons


def test_one_deployment_per_battlefield_is_not_double_counted_as_a_context_effect() -> None:
    observations: list[StrengthObservation] = []
    for hero_id in ("hero.a", "hero.b"):
        for monster_id in ("monsters.a", "monsters.b"):
            for battlefield_id, deployment_id in (
                ("field.open", "deployment.open"),
                ("field.door", "deployment.door"),
            ):
                for opening in ("hero_first", "monster_first"):
                    observations.append(StrengthObservation(
                        match_id=f"{hero_id}-{monster_id}-{battlefield_id}-{opening}",
                        pair_block_id=f"{hero_id}-{monster_id}-{battlefield_id}",
                        hero_configuration_id=hero_id,
                        monster_configuration_id=monster_id,
                        battlefield_id=battlefield_id,
                        deployment_id=deployment_id,
                        opening_treatment=opening,
                        outcome=(
                            RatedOutcome.HERO_WIN
                            if (hero_id, monster_id, opening) != ("hero.b", "monsters.b", "monster_first")
                            else RatedOutcome.MONSTER_WIN
                        ),
                    ))

    result = fit_configuration_strength(observations, regularization=0.25)

    assert result.design.rank == result.design.parameter_count
    assert "design_matrix_rank_deficient" not in result.gate_reasons
    deployment_effects = [row for row in result.context_effects if row.context_kind == "deployment"]
    assert {row.context_id for row in deployment_effects} == {
        "field.door:deployment.door",
        "field.open:deployment.open",
    }
    assert {row.coefficient for row in deployment_effects} == {0.0}
