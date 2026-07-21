"""Dependency-free offline HTML renderer for connected-rating reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html import escape
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ai.evaluation.config_ladder.report_projection import (
    ReportSource,
    build_report_projection,
)


_MISSING = object()


@dataclass(frozen=True)
class _MetricValue:
    """One retained metric plus its explicit availability metadata."""

    value: Any
    available: bool
    unit: str | None = None
    denominator: Any = None
    unavailable_reason: str | None = None


def render_report_html(payload: ReportSource) -> str:
    """Render a complete offline HTML report from typed or mapping JSON.

    Args:
        payload: Report projection, Pydantic report model, or source mapping.

    Returns:
        Self-contained HTML with inline CSS, JavaScript, and source JSON.
    """
    report = build_report_projection(payload)
    source = _mapping(report.get("source"))
    status = _mapping(report.get("status"))
    title = str(source.get("title") or "Connected Configuration Rating Report")
    experiment_id = str(source["experiment_id"])
    phase = status.get("phase")
    subtitle_parts = [experiment_id]
    if source.get("generated_at") is not None:
        subtitle_parts.append(str(source["generated_at"]))
    if phase is not None:
        subtitle_parts.append(str(phase))
    embedded_json = _embedded_json(report)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{_STYLES}</style>
</head>
<body>
  <header class="masthead">
    <div class="masthead-inner">
      <p class="eyebrow">Connected configuration evaluation</p>
      <h1>{escape(title)}</h1>
      <p class="subtitle">{escape(" | ".join(subtitle_parts))}</p>
      {_identity_facts(source)}
    </div>
  </header>
  <nav class="chapter-nav" aria-label="Report chapters">
    <div class="chapter-nav-inner">
      <a href="#what-was-tested">What was tested</a>
      <a href="#who-was-powerful">Who was powerful</a>
      <a href="#content-coverage">Content coverage</a>
      <a href="#spell-coverage">Spell coverage</a>
      <a href="#how-efficiently-it-ran">How efficiently it ran</a>
      <a href="#what-parallelization-changed">What parallelization changed</a>
      <a href="#evidence">Evidence</a>
    </div>
  </nav>
  <main class="report-shell">
    {_quality_strip(report)}
    {_chapter_what_was_tested(report)}
    {_chapter_who_was_powerful(report)}
    {_chapter_content_coverage(report)}
    {_chapter_spell_coverage(report)}
    {_chapter_efficiency(report)}
    {_chapter_parallel(report)}
    {_evidence_section(report)}
  </main>
  <script type="application/json" id="report-data">{embedded_json}</script>
  <script>{_SCRIPT}</script>
</body>
</html>
"""


def render_connected_rating_report(payload: ReportSource) -> str:
    """Alias with an experiment-specific public name."""
    return render_report_html(payload)


def write_report_html(payload: ReportSource, output_path: Path | str) -> Path:
    """Write one rendered report HTML file.

    Args:
        payload: Typed or mapping report data.
        output_path: Destination HTML path.

    Returns:
        Destination path.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_report_html(payload), encoding="utf-8")
    return destination


def _chapter_what_was_tested(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    connectivity = _mapping(report.get("connectivity"))
    status_specs = (
        ("Scheduled matches", "scheduled_matches", None, "integer"),
        ("Completed matches", "completed_matches", None, "integer"),
        ("Eligible matches", "eligible_matches", None, "integer"),
        ("Failed matches", "failed_matches", None, "integer"),
        ("Scheduled pair blocks", "scheduled_pair_blocks", None, "integer"),
        ("Completed pair blocks", "completed_pair_blocks", None, "integer"),
        ("Hero wins", "hero_wins", None, "integer"),
        ("Monster wins", "monster_wins", None, "integer"),
        ("Draws", "draws", None, "integer"),
        ("Stalemate draws", "stalemate_draws", None, "integer"),
    )
    connectivity_specs = (
        ("Graph components", "component_count", None, "integer"),
        ("Hero configurations", "hero_count", None, "integer"),
        ("Monster parties", "monster_party_count", None, "integer"),
        ("Matchup edges", "edge_count", None, "integer"),
    )
    strength = _mapping(report.get("strength"))
    design = _mapping(strength.get("design"))
    design_cards = "".join((
        _metric_card("Design rank", design, "rank", "strength.design.rank", format_kind="integer"),
        _metric_card("Model parameters", design, "parameter_count", "strength.design.parameter_count", format_kind="integer"),
        _metric_card("Model observations", design, "observation_count", "strength.design.observation_count", format_kind="integer"),
    ))
    return f"""
    <article class="chapter" id="what-was-tested">
      {_chapter_heading("01", "What Was Tested", "The experiment scope, retained identities, paired treatments, and whether the evidence supports one global comparison.")}
      <div class="metric-grid">{_metric_cards(status, "status", status_specs)}</div>
      <div class="split-band">
        <section class="plain-section" aria-labelledby="method-heading">
          <h3 id="method-heading">Method</h3>
          {_facts_table(_mapping(report.get("method")), "Experiment method")}
        </section>
        <section class="plain-section" aria-labelledby="connectivity-heading">
          <h3 id="connectivity-heading">Connectivity</h3>
          <div class="metric-grid compact">{_metric_cards(connectivity, "connectivity", connectivity_specs)}{design_cards}</div>
        </section>
      </div>
      {_degree_figure(connectivity, _explanation(report, "connectivity", "Distinct-opponent degree is reported for every rated configuration; the companion table carries the exact retained counts."))}
    </article>
    """


def _chapter_who_was_powerful(report: Mapping[str, Any]) -> str:
    strength = _mapping(report.get("strength"))
    matchups = _mapping(report.get("matchups"))
    return f"""
    <article class="chapter" id="who-was-powerful">
      {_chapter_heading("02", "Who Was Powerful", "Adjusted configuration strength is kept separate by side and shown with retained uncertainty.")}
      <div class="figure-grid">
        {_forest_figure(_rows(strength.get("hero_ratings")), "Adjusted hero strength", "hero-strength", _explanation(report, "hero_strength", "Intervals are shown only when retained by the strength result."))}
        {_forest_figure(_rows(strength.get("monster_ratings")), "Adjusted monster-party strength", "monster-strength", _explanation(report, "monster_strength", "Intervals are shown only when retained by the strength result."))}
      </div>
      {_rank_uncertainty_table(_rows(report.get("rank_uncertainty")))}
      {_effect_figure(_rows(strength.get("context_effects")), "Battlefield, deployment, and opening effects", "context-effects", "context_id", "elo_equivalent", _explanation(report, "context_effects", "Positive Elo-equivalent effects favor the hero outcome; exact context kinds remain visible in the table."))}
      <div class="matrix-grid">
        {_matrix_figure(_mapping(matchups.get("predicted")), "Predicted hero win probability", "predicted-matrix", _explanation(report, "predicted_matchups", "Model probabilities and intervals are displayed exactly as retained."))}
        {_matrix_figure(_mapping(matchups.get("empirical")), "Empirical hero win rate", "empirical-matrix", _explanation(report, "empirical_matchups", "Observed cells retain their games and win-loss-draw denominators."))}
      </div>
      {_specialization_figure(_rows(report.get("specialization")), _explanation(report, "specialization", "Residual Elo is a battlefield-specific deviation from adjusted global strength."))}
      {_calibration_table(_rows(report.get("calibration")))}
      {_secondary_estimator_section(_mapping(report.get("secondary_estimators")))}
    </article>
    """


def _chapter_spell_coverage(report: Mapping[str, Any]) -> str:
    coverage = _mapping(report.get("spell_coverage"))
    specs = (
        ("Implemented spells", "implemented_spell_count", None, "integer"),
        ("Configured spells", "configured_spell_count", None, "integer"),
        ("Exercised spells", "exercised_spell_count", None, "integer"),
        ("Spell commands", "total_spell_casts", None, "integer"),
        ("Implementation exercised", "exercise_coverage_pct", "%", "decimal"),
        ("Configured set exercised", "configured_exercise_pct", "%", "decimal"),
    )
    return f"""
    <article class="chapter" id="spell-coverage">
      {_chapter_heading("04", "Spell Coverage", "Exact semantic identities show which implemented spells entered a configuration and which the AI actually cast.")}
      <div class="metric-grid">{_metric_cards(coverage, "spell_coverage", specs)}</div>
      {_spell_level_coverage_table(_rows(coverage.get("by_level")))}
      {_spell_coverage_table(_rows(coverage.get("spells")), _explanation(report, "spell_coverage", "A spell is exercised only after an accepted and completed command carrying its exact implementation semantic key."))}
    </article>
    """


def _chapter_content_coverage(report: Mapping[str, Any]) -> str:
    coverage = _mapping(report.get("content_coverage"))
    specs = (
        ("Implemented identities", "implemented_identity_count", None, "integer"),
        ("Configured implementations", "configured_implemented_identity_count", None, "integer"),
        ("Effected implementations", "effected_implemented_identity_count", None, "integer"),
        ("Observed but uncatalogued", "observed_uncatalogued_identity_count", None, "integer"),
        ("Implementation configured", "configuration_coverage_pct", "%", "decimal"),
        ("Implementation effected", "effect_coverage_pct", "%", "decimal"),
    )
    match_count = coverage.get("match_count")
    manifest_count = coverage.get("manifest_match_count")
    affordance_count = coverage.get("affordance_evidence_match_count")
    lifecycle_count = coverage.get("lifecycle_evidence_match_count")
    observability = (
        '<section class="plain-section"><h3>Evidence availability</h3>'
        f'<p class="interpretation">Manifest identities: {escape(_format_optional(manifest_count, integer=True))} / {escape(_format_optional(match_count, integer=True))} matches. '
        f'Decision-epoch opportunity evidence: {escape(_format_optional(affordance_count, integer=True))} / {escape(_format_optional(match_count, integer=True))}. '
        f'Handler and condition lifecycle evidence: {escape(_format_optional(lifecycle_count, integer=True))} / {escape(_format_optional(match_count, integer=True))}. '
        'A missing evidence channel is unavailable, not a measured zero.</p></section>'
    )
    return f"""
    <article class="chapter" id="content-coverage">
      {_chapter_heading("03", "Content Coverage", "Actions, reactions, traits, feats, conditions, items, and environmental interactions are measured against their own engine-native lifecycles.")}
      <div class="metric-grid">{_metric_cards(coverage, "content_coverage", specs)}</div>
      {observability}
      {_content_family_table(_rows(coverage.get("by_family")))}
      {_content_coverage_table(_rows(coverage.get("content")), _explanation(report, "content_coverage", "Coverage stages are not interchangeable across content families."))}
    </article>
    """


def _content_family_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _figure_unavailable("Coverage by family", "Family coverage evidence was not retained.")
    body = []
    for row in rows:
        body.append(
            f'<tr><th scope="row">{escape(str(row.get("content_kind") or "Unavailable").replace("_", " ").title())}</th>'
            f'<td>{escape(_format_optional(row.get("implemented_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("configured_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("opportunity_identity_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("effected_identity_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("opportunity_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("effect_count"), integer=True))}</td></tr>'
        )
    return (
        '<section class="plain-section"><h3>Coverage by content family</h3><div class="table-wrap">'
        '<table><caption>Implemented identities and retained lifecycle evidence by rules-content family</caption>'
        '<thead><tr><th scope="col">Family</th><th scope="col">Implemented</th><th scope="col">Configured</th>'
        '<th scope="col">Given opportunity</th><th scope="col">Effected</th><th scope="col">Opportunities</th><th scope="col">Effects</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'
    )


def _content_coverage_table(rows: list[dict[str, Any]], explanation: str) -> str:
    if not rows:
        return _figure_unavailable("Content lifecycle ledger", "Per-content evidence was not retained.")
    body = []
    for row in rows:
        name = str(row.get("display_name") or "Unavailable")
        semantic_key = str(row.get("semantic_key") or "Unavailable")
        family = str(row.get("content_kind") or "unclassified")
        subtype = str(row.get("subtype") or "unclassified")
        status = str(row.get("status") or "unavailable")
        configured = row.get("configured_configuration_ids")
        configured_values = [str(value) for value in configured] if isinstance(configured, list) else []
        configured_text = ", ".join(configured_values) if configured_values else "None"
        configured_cell = (
            f'<details><summary>{len(configured_values)} configurations</summary><span>{escape(configured_text)}</span></details>'
            if len(configured_values) > 3
            else escape(configured_text)
        )
        filter_text = " ".join((name, semantic_key, family, subtype, status, configured_text)).lower()
        body.append(
            f'<tr data-filter-row data-filter-text="{escape(filter_text, quote=True)}">'
            f'<th scope="row"><span class="spell-name">{escape(name)}</span><code>{escape(semantic_key)}</code></th>'
            f'<td>{escape(family.replace("_", " "))}<br><small>{escape(subtype.replace("_", " "))}</small></td>'
            f'<td><span class="coverage-status {escape(status, quote=True)}">{escape(status.replace("_", " "))}</span></td>'
            f'<td>{escape(_format_optional(row.get("exposure_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("resolved_command_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("handler_effect_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("condition_application_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("item_consumption_count"), integer=True))}</td>'
            f'<td class="wide-cell">{configured_cell}</td></tr>'
        )
    table_id = "content-coverage-ledger"
    return f"""
      <section class="plain-section">
        <div class="figure-heading"><h3>Content lifecycle ledger</h3><input class="filter" type="search" data-filter-input="{table_id}" aria-controls="{table_id}" aria-label="Filter content coverage" placeholder="Filter actions, reactions, feats, traits, items"></div>
        <div class="table-wrap"><table id="{table_id}"><caption>Every catalogued or observed content identity and its retained lifecycle evidence</caption>
          <thead><tr><th scope="col">Content</th><th scope="col">Family</th><th scope="col">Status</th><th scope="col">Exposed</th><th scope="col">Commands</th><th scope="col">Handler effects</th><th scope="col">Applications</th><th scope="col">Item uses</th><th scope="col">Configured in</th></tr></thead>
          <tbody>{"".join(body)}</tbody></table></div>
        <p class="interpretation">{escape(explanation)}</p>
      </section>
    """


def _spell_level_coverage_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _figure_unavailable("Coverage by spell level", "Per-level spell coverage was not retained.")
    body = []
    for row in rows:
        level = row.get("level")
        label = "Cantrip" if level == 0 else f"Level {level}"
        body.append(
            f'<tr><th scope="row">{escape(label)}</th>'
            f'<td>{escape(_format_optional(row.get("implemented_spells"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("configured_spells"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("exercised_spells"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("casts"), integer=True))}</td></tr>'
        )
    return (
        '<section class="plain-section"><h3>Coverage by spell level</h3><div class="table-wrap">'
        '<table><caption>Implemented, configured, and exercised spell identities by level</caption>'
        '<thead><tr><th scope="col">Level</th><th scope="col">Implemented</th>'
        '<th scope="col">Configured</th><th scope="col">Exercised</th><th scope="col">Casts</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'
    )


def _spell_coverage_table(rows: list[dict[str, Any]], explanation: str) -> str:
    if not rows:
        return _figure_unavailable("Spell exercise ledger", "Per-spell coverage evidence was not retained.")
    body = []
    for row in rows:
        spell_name = str(row.get("spell_name") or "Unavailable")
        level = row.get("spell_level")
        level_label = "Cantrip" if level == 0 else f"Level {level}" if level is not None else "Unavailable"
        status = str(row.get("status") or "Unavailable")
        configured_ids = row.get("configured_configuration_ids")
        casting_ids = row.get("casting_configuration_ids")
        configured_text = ", ".join(str(value) for value in configured_ids) if isinstance(configured_ids, list) and configured_ids else "None"
        casting_text = ", ".join(str(value) for value in casting_ids) if isinstance(casting_ids, list) and casting_ids else "None"
        filter_text = " ".join((spell_name, status, configured_text, casting_text)).lower()
        body.append(
            f'<tr data-filter-row data-filter-text="{escape(filter_text, quote=True)}">'
            f'<th scope="row"><span class="spell-name">{escape(spell_name)}</span><code>{escape(str(row.get("semantic_key") or "Unavailable"))}</code></th>'
            f'<td>{escape(level_label)}</td><td><span class="coverage-status {escape(status, quote=True)}">{escape(status.replace("_", " "))}</span></td>'
            f'<td>{escape(_format_optional(row.get("cast_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("hero_cast_count"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("monster_cast_count"), integer=True))}</td>'
            f'<td class="wide-cell">{escape(configured_text)}</td><td class="wide-cell">{escape(casting_text)}</td></tr>'
        )
    table_id = "spell-coverage-ledger"
    return f"""
      <section class="plain-section">
        <div class="figure-heading"><h3>Spell exercise ledger</h3><input class="filter" type="search" data-filter-input="{table_id}" aria-controls="{table_id}" aria-label="Filter spell coverage" placeholder="Filter spells or configurations"></div>
        <div class="table-wrap"><table id="{table_id}"><caption>Every implemented spell and its retained configuration and cast evidence</caption>
          <thead><tr><th scope="col">Spell</th><th scope="col">Level</th><th scope="col">Status</th><th scope="col">Casts</th><th scope="col">Hero</th><th scope="col">Monster</th><th scope="col">Configured in</th><th scope="col">Cast by</th></tr></thead>
          <tbody>{"".join(body)}</tbody></table></div>
        <p class="interpretation">{escape(explanation)}</p>
      </section>
    """


def _chapter_efficiency(report: Mapping[str, Any]) -> str:
    performance = _mapping(report.get("performance"))
    specs = (
        ("Wall time", "wall_time_ms", "ms", "duration"),
        ("Matches / second", "matches_per_second", "/ s", "decimal"),
        ("Turns / second", "turns_per_second", "/ s", "decimal"),
        ("CPU utilization", "cpu_utilization_pct", "%", "decimal"),
        ("Peak RSS", "peak_rss_mb", "MB", "decimal"),
        ("Artifact bytes", "artifact_bytes", "bytes", "integer"),
    )
    return f"""
    <article class="chapter" id="how-efficiently-it-ran">
      {_chapter_heading("05", "How Efficiently It Ran", "Wall-clock throughput, retained resource evidence, runtime composition, and progress over time.")}
      <div class="metric-grid">{_metric_cards(performance, "performance", specs)}</div>
      <div class="figure-grid">
        {_phase_figure(_rows(performance.get("phase_timings")), _explanation(report, "runtime_phases", "Phase shares and totals come from retained worker and coordinator timing records."))}
        {_completion_figure(_rows(performance.get("completion_series")), _explanation(report, "completion", "The cumulative line uses retained elapsed time and committed match counts."))}
      </div>
      {_worker_timeline(_rows(performance.get("worker_series")), _explanation(report, "workers", "Worker, queue, memory, and failure samples share the retained coordinator timeline."))}
    </article>
    """


def _chapter_parallel(report: Mapping[str, Any]) -> str:
    scaling = _mapping(report.get("scaling"))
    selected = _metric_card(
        "Selected workers",
        scaling,
        "selected_worker_count",
        "scaling.selected_worker_count",
        format_kind="integer",
    )
    reason = scaling.get("selection_reason")
    reason_html = f'<p class="interpretation">{escape(str(reason))}</p>' if reason is not None else _unavailable("Production-concurrency selection reason was not retained.")
    return f"""
    <article class="chapter" id="what-parallelization-changed">
      {_chapter_heading("06", "What Parallelization Changed", "Comparable pilots expose throughput gains, efficiency loss, resource pressure, and the selected production concurrency.")}
      <div class="selection-band">{selected}<div><h3>Selection rationale</h3>{reason_html}</div></div>
      {_scaling_figure(_rows(scaling.get("pilots")), _explanation(report, "scaling", "Observed speedup is plotted beside the ideal worker-count reference; efficiency remains explicit in the table."))}
    </article>
    """


def _chapter_heading(number: str, title: str, summary: str) -> str:
    return f"""
      <header class="chapter-heading">
        <span class="chapter-number">{escape(number)}</span>
        <div><h2>{escape(title)}</h2><p>{escape(summary)}</p></div>
      </header>
    """


def _identity_facts(source: Mapping[str, Any]) -> str:
    keys = ("schedule_hash", "catalog_hash", "policy_hash", "engine_hash")
    rows = []
    for key in keys:
        value = source.get(key)
        if value is not None:
            rows.append(f'<span><strong>{escape(_humanize(key))}</strong> {escape(str(value))}</span>')
    return f'<div class="identity-row">{"".join(rows)}</div>' if rows else ""


def _quality_strip(report: Mapping[str, Any]) -> str:
    quality = report.get("quality")
    rows: list[tuple[str, Any]] = []
    if isinstance(quality, Mapping):
        rows = [(str(key), value) for key, value in quality.items()]
    elif isinstance(quality, list):
        rows = [
            (str(value.get("label") or value.get("id") or f"Quality {index + 1}"), value)
            for index, value in enumerate(quality)
            if isinstance(value, Mapping)
        ]
    if not rows:
        return '<section class="quality-strip" aria-label="Evidence quality"><div class="unavailable">Evidence-quality statuses were not retained.</div></section>'
    cards = []
    for key, value in rows:
        detail = None
        status = value
        if isinstance(value, Mapping):
            status = value.get("status") if value.get("status") is not None else value.get("value")
            detail = value.get("detail") or value.get("explanation")
        tone = _status_tone(status)
        cards.append(
            f'<div class="quality-item {tone}"><span>{escape(_humanize(key))}</span>'
            f'<strong>{escape(str(status)) if status is not None else "Unavailable"}</strong>'
            f'{f"<small>{escape(str(detail))}</small>" if detail is not None else ""}</div>'
        )
    return f'<section class="quality-strip" aria-label="Evidence quality">{"".join(cards)}</section>'


def _metric_cards(
    data: Mapping[str, Any],
    prefix: str,
    specs: Sequence[tuple[str, str, str | None, str]],
) -> str:
    return "".join(
        _metric_card(label, data, key, f"{prefix}.{key}", default_unit=unit, format_kind=format_kind)
        for label, key, unit, format_kind in specs
    )


def _metric_card(
    label: str,
    data: Mapping[str, Any],
    key: str,
    source_path: str,
    *,
    default_unit: str | None = None,
    format_kind: str = "decimal",
) -> str:
    metric = _metric_value(data.get(key, _MISSING), default_unit=default_unit)
    source_attr = escape(source_path, quote=True)
    if not metric.available:
        reason = metric.unavailable_reason or "Not retained in report JSON."
        return (
            f'<div class="metric"><span>{escape(label)}</span>'
            f'<strong data-source="{source_attr}">Unavailable</strong>'
            f'<small>{escape(reason)}</small></div>'
        )
    raw = _raw_value(metric.value)
    formatted = _format_metric(metric.value, metric.unit, format_kind)
    denominator = ""
    if metric.denominator is not None:
        denominator = f'<small>Denominator: {escape(_format_scalar(metric.denominator))}</small>'
    return (
        f'<div class="metric"><span>{escape(label)}</span>'
        f'<strong data-source="{source_attr}" data-value="{escape(raw, quote=True)}">{escape(formatted)}</strong>'
        f'{denominator}</div>'
    )


def _metric_value(value: Any, *, default_unit: str | None = None) -> _MetricValue:
    if value is _MISSING:
        return _MetricValue(value=None, available=False, unit=default_unit)
    if isinstance(value, Mapping) and ("value" in value or "availability" in value):
        raw_value = value.get("value")
        availability = value.get("availability")
        available = availability not in {"unavailable", "missing", "not_run"} and raw_value is not None
        return _MetricValue(
            value=raw_value,
            available=available,
            unit=str(value.get("unit")) if value.get("unit") is not None else default_unit,
            denominator=value.get("denominator"),
            unavailable_reason=str(value.get("unavailable_reason") or value.get("explanation"))
            if value.get("unavailable_reason") is not None or value.get("explanation") is not None
            else None,
        )
    return _MetricValue(value=value, available=value is not None, unit=default_unit)


def _facts_table(data: Mapping[str, Any], caption: str) -> str:
    rows = []
    for key, value in data.items():
        rows.append(
            f'<tr><th scope="row">{escape(_humanize(str(key)))}</th><td>{escape(_format_scalar(value))}</td></tr>'
        )
    if not rows:
        return _unavailable("Method metadata was not retained.")
    return f'<div class="table-wrap"><table class="facts-table"><caption>{escape(caption)}</caption><tbody>{"".join(rows)}</tbody></table></div>'


def _degree_figure(connectivity: Mapping[str, Any], explanation: str) -> str:
    degrees = connectivity.get("degree_by_participant")
    if not isinstance(degrees, Mapping) or not degrees:
        return _figure_unavailable("Matchup graph connectivity", "Opponent-degree evidence was not retained.")
    rows = [
        {"label": str(participant), "value": value}
        for participant, value in sorted(degrees.items(), key=lambda item: (-_sort_number(item[1]), str(item[0])))
    ]
    return _bar_figure(rows, "Matchup graph connectivity", "connectivity-degree", "Opponents", explanation)


def _forest_figure(rows: list[dict[str, Any]], title: str, chart_id: str, explanation: str) -> str:
    measured = [row for row in rows if _number(row.get("adjusted_elo")) is not None]
    if not measured:
        return _figure_unavailable(title, "Adjusted Elo rows were not retained.")
    measured.sort(key=lambda row: (-float(row["adjusted_elo"]), str(row.get("configuration_id", ""))))
    values = [float(row["adjusted_elo"]) for row in measured]
    bounds = [1000.0, *values]
    for row in measured:
        lower = _number(row.get("elo_lower_95"))
        upper = _number(row.get("elo_upper_95"))
        if lower is not None:
            bounds.append(lower)
        if upper is not None:
            bounds.append(upper)
    minimum, maximum = _padded_bounds(bounds)
    width = 920
    row_height = 34
    height = max(190, 78 + row_height * len(measured))
    left, right, top, bottom = 240, 72, 28, 42
    plot_width = width - left - right

    def x(value: float) -> float:
        return left + ((value - minimum) / max(1e-9, maximum - minimum)) * plot_width

    title_id = f"{chart_id}-title"
    desc_id = f"{chart_id}-desc"
    baseline = x(1000.0)
    marks = [f'<line class="reference" x1="{baseline:.2f}" x2="{baseline:.2f}" y1="{top}" y2="{height - bottom}"></line>']
    table_rows = []
    for index, row in enumerate(measured):
        y = top + 24 + index * row_height
        identifier = str(row.get("display_name") or row.get("configuration_id") or f"row-{index + 1}")
        estimate = float(row["adjusted_elo"])
        lower = _number(row.get("elo_lower_95"))
        upper = _number(row.get("elo_upper_95"))
        marks.append(f'<text class="row-label" x="0" y="{y + 4:.2f}">{escape(identifier)}</text>')
        if lower is not None and upper is not None:
            marks.append(f'<line class="interval" x1="{x(lower):.2f}" x2="{x(upper):.2f}" y1="{y:.2f}" y2="{y:.2f}"></line>')
        tooltip = f"{identifier}: {_format_number(estimate)} Elo"
        if lower is not None and upper is not None:
            tooltip += f"; 95% interval {_format_number(lower)} to {_format_number(upper)}"
        marks.append(
            f'<circle class="estimate" cx="{x(estimate):.2f}" cy="{y:.2f}" r="5"><title>{escape(tooltip)}</title></circle>'
        )
        marks.append(f'<text class="value-label" x="{width - right + 8}" y="{y + 4:.2f}">{escape(_format_number(estimate))}</text>')
        table_rows.append(
            f'<tr><th scope="row">{escape(identifier)}</th><td>{escape(_format_number(estimate))}</td>'
            f'<td>{escape(_format_optional(lower))}</td><td>{escape(_format_optional(upper))}</td>'
            f'<td>{escape(_format_optional(row.get("games"), integer=True))}</td></tr>'
        )
    ticks = []
    for tick in (minimum, (minimum + maximum) / 2.0, maximum):
        ticks.append(
            f'<line class="gridline" x1="{x(tick):.2f}" x2="{x(tick):.2f}" y1="{top}" y2="{height - bottom}"></line>'
            f'<text class="axis-label" x="{x(tick):.2f}" y="{height - 10}" text-anchor="middle">{escape(_format_number(tick))}</text>'
        )
    return f"""
      <figure class="figure">
        <div class="figure-heading"><h3>{escape(title)}</h3></div>
        <svg class="plot forest" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id} {desc_id}">
          <title id="{title_id}">{escape(title)}</title>
          <desc id="{desc_id}">Adjusted Elo point estimates with retained 95 percent intervals. A vertical reference marks 1000 Elo.</desc>
          {"".join(ticks)}{"".join(marks)}
        </svg>
        <p class="interpretation">{escape(explanation)}</p>
        <div class="table-wrap"><table><caption>{escape(title)} values</caption><thead><tr><th scope="col">Configuration</th><th scope="col">Adjusted Elo</th><th scope="col">Lower 95%</th><th scope="col">Upper 95%</th><th scope="col">Games</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>
      </figure>
    """


def _effect_figure(
    rows: list[dict[str, Any]],
    title: str,
    chart_id: str,
    label_key: str,
    value_key: str,
    explanation: str,
) -> str:
    measured = []
    for row in rows:
        value = _number(row.get(value_key))
        if value is None:
            continue
        context = row.get("context_kind")
        label = str(row.get(label_key) or row.get("configuration_id") or "unlabeled")
        if context is not None:
            label = f"{context}: {label}"
        measured.append({"label": label, "value": value, "row": row})
    if not measured:
        return _figure_unavailable(title, "Effect estimates were not retained.")
    return _signed_bar_figure(measured, title, chart_id, "Elo equivalent", explanation)


def _specialization_figure(rows: list[dict[str, Any]], explanation: str) -> str:
    measured = []
    for row in rows:
        value = _number(row.get("residual_elo"))
        if value is None:
            continue
        config = row.get("configuration_id")
        battlefield = row.get("battlefield_id")
        measured.append({"label": f"{config} | {battlefield}", "value": value, "row": row})
    if not measured:
        return _figure_unavailable("Battlefield specialization", "Configuration-by-battlefield residuals were not retained.")
    return _signed_bar_figure(measured, "Battlefield specialization", "battlefield-specialization", "Residual Elo", explanation)


def _bar_figure(rows: list[dict[str, Any]], title: str, chart_id: str, unit: str, explanation: str) -> str:
    measured = [(str(row["label"]), _number(row.get("value"))) for row in rows]
    measured = [(label, value) for label, value in measured if value is not None]
    if not measured:
        return _figure_unavailable(title, "No measured rows were retained.")
    maximum = max(value for _label, value in measured)
    width = 920
    row_height = 30
    height = max(180, 72 + row_height * len(measured))
    left, right, top = 240, 80, 24
    plot_width = width - left - right
    title_id = f"{chart_id}-title"
    desc_id = f"{chart_id}-desc"
    marks = []
    table_rows = []
    for index, (label, value) in enumerate(measured):
        y = top + 12 + index * row_height
        bar_width = 0.0 if maximum <= 0 else (value / maximum) * plot_width
        marks.append(f'<text class="row-label" x="0" y="{y + 10:.2f}">{escape(label)}</text>')
        marks.append(f'<rect class="bar" x="{left}" y="{y:.2f}" width="{bar_width:.2f}" height="14"><title>{escape(label)}: {escape(_format_number(value))} {escape(unit)}</title></rect>')
        marks.append(f'<text class="value-label" x="{left + bar_width + 7:.2f}" y="{y + 11:.2f}">{escape(_format_number(value))}</text>')
        table_rows.append(f'<tr><th scope="row">{escape(label)}</th><td>{escape(_format_number(value))}</td></tr>')
    return f"""
      <figure class="figure">
        <div class="figure-heading"><h3>{escape(title)}</h3></div>
        <svg class="plot" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id} {desc_id}">
          <title id="{title_id}">{escape(title)}</title><desc id="{desc_id}">{escape(unit)} values for each retained row.</desc>{"".join(marks)}
        </svg>
        <p class="interpretation">{escape(explanation)}</p>
        <div class="table-wrap"><table><caption>{escape(title)} values</caption><thead><tr><th scope="col">Row</th><th scope="col">{escape(unit)}</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>
      </figure>
    """


def _signed_bar_figure(rows: list[dict[str, Any]], title: str, chart_id: str, unit: str, explanation: str) -> str:
    measured = [(str(row["label"]), float(row["value"]), _mapping(row.get("row"))) for row in rows]
    extent = max(abs(value) for _label, value, _row in measured) or 1.0
    width = 920
    row_height = 32
    height = max(180, 72 + row_height * len(measured))
    left, right, top, bottom = 240, 76, 24, 38
    plot_width = width - left - right
    center = left + plot_width / 2.0
    scale = (plot_width / 2.0) / extent
    title_id = f"{chart_id}-title"
    desc_id = f"{chart_id}-desc"
    marks = [f'<line class="reference" x1="{center:.2f}" x2="{center:.2f}" y1="{top}" y2="{height - bottom}"></line>']
    table_rows = []
    for index, (label, value, source_row) in enumerate(measured):
        y = top + 12 + index * row_height
        start = center if value >= 0 else center + value * scale
        bar_width = abs(value) * scale
        tone = "bar positive" if value >= 0 else "bar negative"
        marks.append(f'<text class="row-label" x="0" y="{y + 11:.2f}">{escape(label)}</text>')
        marks.append(f'<rect class="{tone}" x="{start:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="16"><title>{escape(label)}: {escape(_format_number(value))} {escape(unit)}</title></rect>')
        value_x = center + value * scale + (7 if value >= 0 else -7)
        anchor = "start" if value >= 0 else "end"
        marks.append(f'<text class="value-label" x="{value_x:.2f}" y="{y + 12:.2f}" text-anchor="{anchor}">{escape(_format_number(value))}</text>')
        table_rows.append(
            f'<tr><th scope="row">{escape(label)}</th><td>{escape(_format_number(value))}</td>'
            f'<td>{escape(_format_optional(source_row.get("games"), integer=True))}</td></tr>'
        )
    return f"""
      <figure class="figure wide-figure">
        <div class="figure-heading"><h3>{escape(title)}</h3></div>
        <svg class="plot" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id} {desc_id}">
          <title id="{title_id}">{escape(title)}</title><desc id="{desc_id}">Signed {escape(unit)} estimates centered on zero.</desc>{"".join(marks)}
        </svg>
        <p class="interpretation">{escape(explanation)}</p>
        <div class="table-wrap"><table><caption>{escape(title)} values</caption><thead><tr><th scope="col">Context</th><th scope="col">{escape(unit)}</th><th scope="col">Games</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div>
      </figure>
    """


def _matrix_figure(matrix: Mapping[str, Any], title: str, matrix_id: str, explanation: str) -> str:
    row_ids = _string_list(matrix.get("row_ids") if matrix.get("row_ids") is not None else matrix.get("rows"))
    column_ids = _string_list(matrix.get("column_ids") if matrix.get("column_ids") is not None else matrix.get("columns"))
    cells = _rows(matrix.get("cells"))
    if not row_ids or not column_ids or not cells:
        return _figure_unavailable(title, "Matchup matrix cells were not retained.")
    lookup = {
        (str(cell.get("row_id")), str(cell.get("column_id"))): cell
        for cell in cells
        if cell.get("row_id") is not None and cell.get("column_id") is not None
    }
    header = "".join(f'<th scope="col">{escape(column)}</th>' for column in column_ids)
    body = []
    for row_id in row_ids:
        values = []
        for column_id in column_ids:
            cell = lookup.get((row_id, column_id))
            if cell is None:
                values.append('<td class="heat-empty">Unavailable</td>')
                continue
            probability = _number(
                cell.get("probability")
                if cell.get("probability") is not None
                else cell.get("hero_win_probability", cell.get("value"))
            )
            if probability is None:
                values.append('<td class="heat-empty">Unavailable</td>')
                continue
            tooltip_parts = [f"{row_id} vs {column_id}: {_format_percent(probability)}"]
            lower = _number(cell.get("lower_95"))
            upper = _number(cell.get("upper_95"))
            if lower is not None and upper is not None:
                tooltip_parts.append(f"95% interval {_format_percent(lower)} to {_format_percent(upper)}")
            games = cell.get("games")
            if games is not None:
                tooltip_parts.append(f"{_format_scalar(games)} games")
            values.append(
                f'<td class="{_heat_class(probability)}"><span title="{escape("; ".join(tooltip_parts), quote=True)}">{escape(_format_percent(probability))}</span></td>'
            )
        body.append(f'<tr data-filter-row data-filter-text="{escape(row_id.lower(), quote=True)}"><th scope="row">{escape(row_id)}</th>{"".join(values)}</tr>')
    return f"""
      <figure class="figure matrix-figure">
        <div class="figure-heading"><h3>{escape(title)}</h3><input class="filter" type="search" data-filter-input="{escape(matrix_id, quote=True)}" aria-controls="{escape(matrix_id, quote=True)}" aria-label="Filter {escape(title)} rows" placeholder="Filter configurations"></div>
        <div class="table-wrap matrix-wrap"><table id="{escape(matrix_id, quote=True)}"><caption>{escape(title)}</caption><thead><tr><th scope="col">Hero configuration</th>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>
        <p class="interpretation">{escape(explanation)}</p>
      </figure>
    """


def _rank_uncertainty_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _figure_unavailable("Rank uncertainty", "Bootstrap rank intervals were not retained.")
    body = []
    for row in rows:
        identifier = row.get("configuration_id") or row.get("participant_id")
        body.append(
            f'<tr><th scope="row">{escape(str(identifier))}</th>'
            f'<td>{escape(_format_optional(row.get("median_rank")))}</td>'
            f'<td>{escape(_format_optional(row.get("rank_lower_95")))}</td>'
            f'<td>{escape(_format_optional(row.get("rank_upper_95")))}</td>'
            f'<td>{escape(_format_optional(row.get("top_n_probability"), percent=True))}</td></tr>'
        )
    return f'<section class="plain-section"><h3>Rank uncertainty</h3><div class="table-wrap"><table><caption>Bootstrap rank ranges</caption><thead><tr><th scope="col">Configuration</th><th scope="col">Median rank</th><th scope="col">Lower rank</th><th scope="col">Upper rank</th><th scope="col">Top-N probability</th></tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'


def _calibration_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _figure_unavailable("Calibration", "Calibration buckets were not retained.")
    body = []
    for index, row in enumerate(rows):
        label = row.get("label") or row.get("bucket") or f"Bucket {index + 1}"
        body.append(
            f'<tr><th scope="row">{escape(str(label))}</th>'
            f'<td>{escape(_format_optional(row.get("predicted_probability"), percent=True))}</td>'
            f'<td>{escape(_format_optional(row.get("observed_rate"), percent=True))}</td>'
            f'<td>{escape(_format_optional(row.get("count"), integer=True))}</td></tr>'
        )
    return f'<section class="plain-section"><h3>Calibration</h3><div class="table-wrap"><table><caption>Held-out or retained calibration buckets</caption><thead><tr><th scope="col">Bucket</th><th scope="col">Predicted</th><th scope="col">Observed</th><th scope="col">Count</th></tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'


def _secondary_estimator_section(secondary: Mapping[str, Any]) -> str:
    provisional = _mapping(secondary.get("provisional_paired_elo"))
    order_audit = _mapping(secondary.get("elo_order_sensitivity"))
    bootstrap = _mapping(secondary.get("paired_bootstrap"))
    if not provisional and not order_audit and not bootstrap:
        return _unavailable("Secondary estimator audits were not retained.")
    standing_rows = [
        *_rows(provisional.get("hero_standings"))[:10],
        *_rows(provisional.get("monster_standings"))[:10],
    ]
    table_rows = []
    for row in standing_rows:
        table_rows.append(
            f'<tr><th scope="row">{escape(str(row.get("configuration_id") or "Unavailable"))}</th>'
            f'<td>{escape(str(row.get("side_kind") or "Unavailable"))}</td>'
            f'<td>{escape(_format_optional(row.get("rating")))}</td>'
            f'<td>{escape(_format_optional(row.get("rank"), integer=True))}</td>'
            f'<td>{escape(_format_optional(row.get("matches"), integer=True))}</td></tr>'
        )
    audit = {
        "paired Elo blocks": provisional.get("completed_pair_block_count"),
        "order permutations": order_audit.get("permutation_count"),
        "maximum Elo order range": order_audit.get("maximum_rating_range"),
        "bootstrap replicates": bootstrap.get("requested_replicates"),
        "successful bootstrap fits": bootstrap.get("successful_replicates"),
        "bootstrap success rate": bootstrap.get("success_rate"),
        "bootstrap publishable": bootstrap.get("publishable"),
    }
    standings = (
        f'<div class="table-wrap"><table><caption>Top provisional paired-Elo standings by side</caption>'
        f'<thead><tr><th scope="col">Configuration</th><th scope="col">Side</th><th scope="col">Elo</th><th scope="col">Rank</th><th scope="col">Matches</th></tr></thead>'
        f'<tbody>{"".join(table_rows)}</tbody></table></div>'
        if table_rows
        else _unavailable("Provisional paired-Elo standings were not retained.")
    )
    return f'<section class="plain-section"><h3>Estimator robustness</h3><p class="interpretation">The adjusted model is the official power estimate. Online Elo is retained as a secondary diagnostic, while permutation and paired-bootstrap audits quantify order and rank uncertainty.</p>{_facts_table(audit, "Statistical robustness audit")}{standings}</section>'


def _phase_figure(rows: list[dict[str, Any]], explanation: str) -> str:
    if not rows:
        return _figure_unavailable("Runtime composition", "Phase-level timing was not retained.")
    use_share = all(_number(row.get("share_pct")) is not None for row in rows)
    value_key = "share_pct" if use_share else "total_ms"
    unit = "% wall time" if use_share else "ms total"
    measured = [
        {"label": str(row.get("phase") or row.get("name") or f"phase-{index + 1}"), "value": row.get(value_key)}
        for index, row in enumerate(rows)
    ]
    return _bar_figure(measured, "Runtime composition", "runtime-composition", unit, explanation)


def _completion_figure(rows: list[dict[str, Any]], explanation: str) -> str:
    return _line_figure(
        rows,
        title="Cumulative completion",
        chart_id="completion-series",
        x_key="elapsed_seconds",
        x_label="Elapsed seconds",
        series=(("completed_matches", "Completed matches", "series-blue"),),
        explanation=explanation,
    )


def _worker_timeline(rows: list[dict[str, Any]], explanation: str) -> str:
    if not rows:
        return _figure_unavailable("Worker occupancy and pressure", "Worker timeline samples were not retained.")
    return _line_figure(
        rows,
        title="Worker occupancy and pressure",
        chart_id="worker-series",
        x_key="elapsed_seconds",
        x_label="Elapsed seconds",
        series=(
            ("active_workers", "Active workers", "series-blue"),
            ("queue_depth", "Queue depth", "series-gold"),
            ("rss_mb", "RSS MB", "series-coral"),
            ("failures", "Failures", "series-red"),
        ),
        explanation=explanation,
    )


def _line_figure(
    rows: list[dict[str, Any]],
    *,
    title: str,
    chart_id: str,
    x_key: str,
    x_label: str,
    series: Sequence[tuple[str, str, str]],
    explanation: str,
) -> str:
    ordered = sorted(
        [row for row in rows if _number(row.get(x_key)) is not None],
        key=lambda row: float(row[x_key]),
    )
    points = [
        (row, key, label, css_class, _number(row.get(key)))
        for row in ordered
        for key, label, css_class in series
        if _number(row.get(key)) is not None
    ]
    if not points:
        return _figure_unavailable(title, "Time-series samples were not retained.")
    x_values = [float(row[x_key]) for row in ordered]
    y_values = [float(value) for _row, _key, _label, _class, value in points if value is not None]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = _padded_bounds([0.0, *y_values], pad_fraction=0.08)
    width, height = 920, 310
    left, right, top, bottom = 64, 28, 24, 48

    def x(value: float) -> float:
        return left + ((value - x_min) / max(1e-9, x_max - x_min)) * (width - left - right)

    def y(value: float) -> float:
        return top + ((y_max - value) / max(1e-9, y_max - y_min)) * (height - top - bottom)

    title_id = f"{chart_id}-title"
    desc_id = f"{chart_id}-desc"
    marks = []
    legends = []
    visible_series = []
    for key, label, css_class in series:
        series_rows = [(row, _number(row.get(key))) for row in ordered if _number(row.get(key)) is not None]
        if not series_rows:
            continue
        visible_series.append((key, label))
        path = " ".join(f'{"M" if index == 0 else "L"} {x(float(row[x_key])):.2f} {y(float(value)):.2f}' for index, (row, value) in enumerate(series_rows) if value is not None)
        marks.append(f'<path class="series-line {css_class}" d="{path}"></path>')
        for row, value in series_rows:
            if value is None:
                continue
            tooltip = f"{label}: {_format_number(value)} at {_format_number(float(row[x_key]))} {x_label.lower()}"
            marks.append(f'<circle class="series-dot {css_class}" cx="{x(float(row[x_key])):.2f}" cy="{y(value):.2f}" r="4"><title>{escape(tooltip)}</title></circle>')
        legends.append(f'<span class="legend-item {css_class}"><span></span>{escape(label)}</span>')
    grid = []
    for tick in (y_min, (y_min + y_max) / 2.0, y_max):
        grid.append(f'<line class="gridline" x1="{left}" x2="{width - right}" y1="{y(tick):.2f}" y2="{y(tick):.2f}"></line><text class="axis-label" x="4" y="{y(tick) + 4:.2f}">{escape(_format_number(tick))}</text>')
    table_header = "".join(f'<th scope="col">{escape(label)}</th>' for _key, label in visible_series)
    table_body = []
    for row in ordered:
        table_body.append(
            f'<tr><th scope="row">{escape(_format_number(float(row[x_key])))}</th>'
            + "".join(f'<td>{escape(_format_optional(row.get(key)))}</td>' for key, _label in visible_series)
            + "</tr>"
        )
    return f"""
      <figure class="figure">
        <div class="figure-heading"><h3>{escape(title)}</h3></div>
        <svg class="plot" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{title_id} {desc_id}">
          <title id="{title_id}">{escape(title)}</title><desc id="{desc_id}">Retained values plotted against {escape(x_label.lower())}.</desc>
          {"".join(grid)}<line class="axis" x1="{left}" x2="{width - right}" y1="{height - bottom}" y2="{height - bottom}"></line>{"".join(marks)}
          <text class="axis-label" x="{width / 2}" y="{height - 8}" text-anchor="middle">{escape(x_label)}</text>
        </svg>
        <div class="legend">{"".join(legends)}</div><p class="interpretation">{escape(explanation)}</p>
        <div class="table-wrap"><table><caption>{escape(title)} values</caption><thead><tr><th scope="col">{escape(x_label)}</th>{table_header}</tr></thead><tbody>{"".join(table_body)}</tbody></table></div>
      </figure>
    """


def _scaling_figure(rows: list[dict[str, Any]], explanation: str) -> str:
    measured = sorted(
        [row for row in rows if _number(row.get("workers")) is not None],
        key=lambda row: float(row["workers"]),
    )
    observed = [row for row in measured if _number(row.get("speedup")) is not None]
    if not measured:
        return _figure_unavailable("Parallel scaling", "Comparable scaling pilots were not retained.")
    chart = ""
    if observed:
        width, height = 920, 320
        left, right, top, bottom = 62, 28, 24, 50
        max_workers = max(float(row["workers"]) for row in measured)
        max_speedup = max(max_workers, *(float(row["speedup"]) for row in observed))

        def x(value: float) -> float:
            return left + ((value - 1.0) / max(1.0, max_workers - 1.0)) * (width - left - right)

        def y(value: float) -> float:
            return top + ((max_speedup - value) / max(1.0, max_speedup)) * (height - top - bottom)

        observed_path = " ".join(f'{"M" if index == 0 else "L"} {x(float(row["workers"])):.2f} {y(float(row["speedup"])):.2f}' for index, row in enumerate(observed))
        ideal_path = f'M {x(1.0):.2f} {y(1.0):.2f} L {x(max_workers):.2f} {y(max_workers):.2f}'
        dots = "".join(
            f'<circle class="series-dot series-blue" cx="{x(float(row["workers"])):.2f}" cy="{y(float(row["speedup"])):.2f}" r="5"><title>{escape(_format_number(float(row["workers"])))} workers: {escape(_format_number(float(row["speedup"])))}x speedup</title></circle>'
            for row in observed
        )
        chart = f"""
          <svg class="plot" viewBox="0 0 {width} {height}" role="img" aria-labelledby="scaling-title scaling-desc">
            <title id="scaling-title">Serial versus parallel speedup</title><desc id="scaling-desc">Observed speedup by worker count with an ideal linear-scaling reference.</desc>
            <line class="axis" x1="{left}" x2="{width - right}" y1="{height - bottom}" y2="{height - bottom}"></line>
            <path class="series-line ideal-line" d="{ideal_path}"></path><path class="series-line series-blue" d="{observed_path}"></path>{dots}
            <text class="axis-label" x="{width / 2}" y="{height - 8}" text-anchor="middle">Workers</text>
          </svg>
          <div class="legend"><span class="legend-item series-blue"><span></span>Observed speedup</span><span class="legend-item ideal"><span></span>Ideal scaling</span></div>
        """
    else:
        chart = _unavailable("Speedup values were not retained.")
    columns = (
        ("workers", "Workers", "integer"),
        ("wall_time_ms", "Wall time", "duration"),
        ("throughput_matches_per_second", "Matches / s", "decimal"),
        ("speedup", "Speedup", "decimal"),
        ("parallel_efficiency_pct", "Efficiency %", "decimal"),
        ("cpu_utilization_pct", "CPU %", "decimal"),
        ("peak_rss_mb", "Peak RSS MB", "decimal"),
        ("failure_rate_pct", "Failure %", "decimal"),
    )
    header = "".join(f'<th scope="col">{escape(label)}</th>' for _key, label, _kind in columns)
    body = []
    for row in measured:
        cells = []
        for key, _label, kind in columns:
            value = row.get(key)
            if value is None:
                cells.append("<td>Unavailable</td>")
            else:
                cells.append(f'<td>{escape(_format_metric(value, "ms" if kind == "duration" else None, kind))}</td>')
        body.append(f'<tr><th scope="row">{cells[0][4:-5]}</th>{"".join(cells[1:])}</tr>')
    return f"""
      <figure class="figure wide-figure">
        <div class="figure-heading"><h3>Parallel scaling</h3></div>{chart}
        <p class="interpretation">{escape(explanation)}</p>
        <div class="table-wrap"><table><caption>Comparable scaling pilots</caption><thead><tr>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>
      </figure>
    """


def _evidence_section(report: Mapping[str, Any]) -> str:
    artifacts = _rows(report.get("artifacts"))
    if not artifacts:
        body = _unavailable("Artifact links were not retained in report JSON.")
    else:
        rows = []
        for artifact in artifacts:
            label = artifact.get("match_id") or artifact.get("artifact_id") or artifact.get("path") or "artifact"
            path = artifact.get("path")
            href = _safe_href(artifact.get("href"))
            path_cell = escape(str(path)) if path is not None else "Unavailable"
            if href is not None:
                path_cell = f'<a href="{escape(href, quote=True)}">{path_cell}</a>'
            rows.append(
                f'<tr data-filter-row data-filter-text="{escape(json.dumps(artifact, sort_keys=True).lower(), quote=True)}">'
                f'<th scope="row">{escape(str(label))}</th><td>{escape(str(artifact.get("kind"))) if artifact.get("kind") is not None else "Unavailable"}</td>'
                f'<td class="path-cell">{path_cell}</td><td class="hash-cell">{escape(str(artifact.get("sha256"))) if artifact.get("sha256") is not None else "Unavailable"}</td></tr>'
            )
        body = f"""
          <div class="figure-heading"><input class="filter" type="search" data-filter-input="artifact-table" aria-controls="artifact-table" aria-label="Filter evidence artifacts" placeholder="Filter artifacts"></div>
          <div class="table-wrap"><table id="artifact-table"><caption>Retained evidence artifacts</caption><thead><tr><th scope="col">Evidence</th><th scope="col">Kind</th><th scope="col">Path</th><th scope="col">SHA-256</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
        """
    return f"""
      <footer class="evidence" id="evidence">
        <div><p class="eyebrow">Forensic appendix</p><h2>Evidence</h2><p>Paths and hashes are rendered only when retained by the report projection.</p></div>
        {body}
      </footer>
    """


def _figure_unavailable(title: str, reason: str) -> str:
    return f'<figure class="figure unavailable-figure"><div class="figure-heading"><h3>{escape(title)}</h3></div>{_unavailable(reason)}</figure>'


def _unavailable(reason: str) -> str:
    return f'<div class="unavailable"><strong>Unavailable</strong><span>{escape(reason)}</span></div>'


def _explanation(report: Mapping[str, Any], key: str, fallback: str) -> str:
    explanations = _mapping(report.get("explanations"))
    value = explanations.get(key)
    if isinstance(value, Mapping):
        value = value.get("text") or value.get("summary") or value.get("explanation")
    return str(value) if value is not None else fallback


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output = []
    for row in value:
        if isinstance(row, str):
            output.append(row)
        elif isinstance(row, Mapping):
            identifier = row.get("id") or row.get("configuration_id") or row.get("participant_id")
            if identifier is not None:
                output.append(str(identifier))
    return output


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sort_number(value: Any) -> float:
    number = _number(value)
    return number if number is not None else float("-inf")


def _padded_bounds(values: Sequence[float], *, pad_fraction: float = 0.08) -> tuple[float, float]:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        padding = max(1.0, abs(maximum) * pad_fraction)
    else:
        padding = (maximum - minimum) * pad_fraction
    return minimum - padding, maximum + padding


def _format_metric(value: Any, unit: str | None, format_kind: str) -> str:
    number = _number(value)
    if format_kind == "duration" and number is not None:
        formatted = _format_duration_ms(number)
    elif format_kind == "integer" and number is not None:
        formatted = f"{int(round(number)):,}"
    elif number is not None:
        formatted = _format_number(number)
    else:
        formatted = _format_scalar(value)
    if unit and format_kind != "duration":
        return f"{formatted} {unit}"
    return formatted


def _format_duration_ms(value: float) -> str:
    if value >= 3_600_000:
        return f"{value / 3_600_000:.2f} h"
    if value >= 60_000:
        return f"{value / 60_000:.2f} min"
    if value >= 1_000:
        return f"{value / 1_000:.2f} s"
    return f"{value:.2f} ms"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _format_percent(value: float) -> str:
    probability = value / 100.0 if value > 1.0 else value
    return f"{100.0 * probability:.1f}%"


def _format_optional(value: Any, *, integer: bool = False, percent: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "Unavailable"
    if percent:
        return _format_percent(number)
    if integer:
        return f"{int(round(number)):,}"
    return _format_number(number)


def _format_scalar(value: Any) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        number = _number(value)
        return _format_number(number) if number is not None else "Unavailable"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def _raw_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _status_tone(value: Any) -> str:
    normalized = str(value).lower()
    if normalized in {"passed", "complete", "completed", "connected", "converged"}:
        return "quality-good"
    if normalized in {"failed", "error", "disconnected", "ineligible"}:
        return "quality-bad"
    return "quality-neutral"


def _heat_class(probability: float) -> str:
    normalized = probability / 100.0 if probability > 1.0 else probability
    if normalized < 0.2:
        return "heat heat-0"
    if normalized < 0.35:
        return "heat heat-1"
    if normalized < 0.48:
        return "heat heat-2"
    if normalized <= 0.52:
        return "heat heat-3"
    if normalized <= 0.65:
        return "heat heat-4"
    if normalized <= 0.8:
        return "heat heat-5"
    return "heat heat-6"


def _safe_href(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if value.lstrip().lower().startswith(("javascript:", "data:")):
        return None
    return value


def _embedded_json(report: Mapping[str, Any]) -> str:
    return (
        json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


_STYLES = r"""
:root {
  color-scheme: light dark;
  --bg: #f5f6f7;
  --surface: #ffffff;
  --surface-2: #eef1f4;
  --surface-3: #e5e9ee;
  --text: #171a1f;
  --muted: #596270;
  --line: #c9d0d8;
  --blue: #1769aa;
  --green: #177245;
  --coral: #b4473a;
  --gold: #8c6500;
  --magenta: #8b3f78;
  --red: #a52d35;
  --focus: #006fd6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111419;
    --surface: #191e25;
    --surface-2: #212832;
    --surface-3: #2a333e;
    --text: #f0f3f6;
    --muted: #aeb8c4;
    --line: #3d4855;
    --blue: #72b7ff;
    --green: #75d69c;
    --coral: #ff9a8d;
    --gold: #e7bd68;
    --magenta: #dda0d0;
    --red: #ff8f96;
    --focus: #79bfff;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  min-width: 320px;
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  letter-spacing: 0;
}
a { color: var(--blue); }
a:focus-visible, input:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.masthead { border-bottom: 1px solid var(--line); background: var(--surface); }
.masthead-inner, .chapter-nav-inner, .report-shell { width: min(1480px, calc(100% - 36px)); margin: 0 auto; }
.masthead-inner { padding: 34px 0 26px; }
.eyebrow { margin: 0 0 7px; color: var(--blue); font-size: 12px; font-weight: 750; text-transform: uppercase; }
h1, h2, h3 { margin: 0; line-height: 1.2; letter-spacing: 0; }
h1 { max-width: 920px; font-size: 32px; }
h2 { font-size: 25px; }
h3 { font-size: 16px; }
.subtitle { margin: 8px 0 0; color: var(--muted); overflow-wrap: anywhere; }
.identity-row { display: flex; flex-wrap: wrap; gap: 7px 18px; margin-top: 17px; color: var(--muted); font-size: 12px; }
.identity-row span { overflow-wrap: anywhere; }
.identity-row strong { color: var(--text); }
.chapter-nav { position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--line); background: color-mix(in srgb, var(--surface) 94%, transparent); backdrop-filter: blur(10px); }
.chapter-nav-inner { display: flex; gap: 6px 22px; overflow-x: auto; padding: 11px 0; }
.chapter-nav a { color: var(--muted); font-size: 13px; font-weight: 650; text-decoration: none; white-space: nowrap; }
.chapter-nav a:hover { color: var(--text); }
.report-shell { padding: 20px 0 56px; }
.quality-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 12px; }
.quality-item, .metric { min-width: 0; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); padding: 12px; }
.quality-item { border-left-width: 4px; }
.quality-item span, .metric span { display: block; color: var(--muted); font-size: 12px; }
.quality-item strong, .metric strong { display: block; margin-top: 4px; font-size: 22px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.quality-item small, .metric small { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; }
.quality-good { border-left-color: var(--green); }
.quality-bad { border-left-color: var(--red); }
.quality-neutral { border-left-color: var(--gold); }
.chapter { padding: 48px 0 18px; border-top: 1px solid var(--line); }
.chapter:first-of-type { border-top: 0; }
.chapter-heading { display: grid; grid-template-columns: 54px minmax(0, 760px); gap: 14px; margin-bottom: 22px; }
.chapter-heading p { margin: 7px 0 0; color: var(--muted); }
.chapter-number { color: var(--coral); font-size: 20px; font-weight: 750; font-variant-numeric: tabular-nums; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 10px; margin: 14px 0 22px; }
.metric-grid.compact { grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); margin-bottom: 0; }
.split-band, .figure-grid, .matrix-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; align-items: start; }
.plain-section { min-width: 0; padding: 14px 0 22px; }
.plain-section > h3 { margin-bottom: 10px; }
.figure { min-width: 0; margin: 18px 0; border-top: 1px solid var(--line); padding-top: 16px; }
.wide-figure, .unavailable-figure { grid-column: 1 / -1; }
.figure-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 9px; }
.plot { display: block; width: 100%; height: auto; min-height: 180px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
.row-label, .axis-label, .value-label { fill: var(--muted); font-size: 11px; }
.value-label { fill: var(--text); font-variant-numeric: tabular-nums; }
.gridline { stroke: var(--line); stroke-width: 1; }
.axis, .reference { stroke: var(--muted); stroke-width: 1; }
.reference { stroke-dasharray: 4 4; }
.interval { stroke: var(--blue); stroke-width: 3; stroke-linecap: round; }
.estimate { fill: var(--blue); stroke: var(--surface); stroke-width: 2; }
.bar { fill: var(--blue); }
.bar.positive { fill: var(--green); }
.bar.negative { fill: var(--coral); }
.series-line { fill: none; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
.series-dot { stroke: var(--surface); stroke-width: 2; }
.series-blue { stroke: var(--blue); fill: var(--blue); color: var(--blue); }
.series-gold { stroke: var(--gold); fill: var(--gold); color: var(--gold); }
.series-coral { stroke: var(--coral); fill: var(--coral); color: var(--coral); }
.series-red { stroke: var(--red); fill: var(--red); color: var(--red); }
.ideal-line { stroke: var(--muted); stroke-dasharray: 7 5; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 8px; color: var(--muted); font-size: 12px; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; }
.legend-item span { width: 16px; height: 3px; background: currentColor; }
.legend-item.ideal { color: var(--muted); }
.interpretation { margin: 9px 0 0; color: var(--muted); font-size: 13px; }
.table-wrap { max-width: 100%; overflow: auto; margin-top: 11px; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; background: var(--surface); font-size: 13px; }
caption { padding: 9px 10px; color: var(--muted); text-align: left; font-size: 12px; }
th, td { padding: 8px 9px; border-top: 1px solid var(--line); text-align: left; vertical-align: top; font-variant-numeric: tabular-nums; }
thead th { position: sticky; top: 0; z-index: 2; background: var(--surface-2); color: var(--muted); font-size: 12px; white-space: nowrap; }
tbody th { min-width: 170px; font-weight: 650; }
tbody th code { display: block; max-width: 360px; margin-top: 3px; color: var(--muted); font-size: 10px; font-weight: 450; overflow-wrap: anywhere; white-space: normal; }
.spell-name { display: block; }
.wide-cell { min-width: 240px; max-width: 420px; overflow-wrap: anywhere; }
.coverage-status { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 2px 7px; font-size: 11px; white-space: nowrap; }
.coverage-status.exercised { border-color: var(--green); color: var(--green); }
.coverage-status.configured_unused { border-color: var(--gold); color: var(--gold); }
.coverage-status.unconfigured { color: var(--muted); }
.facts-table th { width: 38%; }
.matrix-wrap { max-height: 620px; }
.matrix-wrap table { width: max-content; min-width: 100%; }
.matrix-wrap thead th { top: 0; }
.matrix-wrap tbody th { position: sticky; left: 0; z-index: 1; background: var(--surface); }
.matrix-wrap td { min-width: 84px; text-align: center; }
.heat-0 { background: color-mix(in srgb, var(--coral) 74%, var(--surface)); }
.heat-1 { background: color-mix(in srgb, var(--coral) 48%, var(--surface)); }
.heat-2 { background: color-mix(in srgb, var(--gold) 28%, var(--surface)); }
.heat-3 { background: var(--surface-2); }
.heat-4 { background: color-mix(in srgb, var(--green) 25%, var(--surface)); }
.heat-5 { background: color-mix(in srgb, var(--green) 44%, var(--surface)); }
.heat-6 { background: color-mix(in srgb, var(--blue) 58%, var(--surface)); }
.heat-empty { color: var(--muted); }
.filter { width: min(300px, 100%); min-height: 36px; border: 1px solid var(--line); border-radius: 6px; padding: 7px 9px; background: var(--surface); color: var(--text); font: inherit; }
.selection-band { display: grid; grid-template-columns: minmax(180px, 0.32fr) minmax(0, 1fr); gap: 18px; align-items: stretch; margin-bottom: 16px; }
.selection-band > div:last-child { padding: 13px 0; }
.selection-band h3 { margin-bottom: 6px; }
.unavailable { display: flex; flex-direction: column; gap: 4px; min-height: 74px; justify-content: center; border: 1px dashed var(--line); border-radius: 8px; padding: 12px; color: var(--muted); }
.unavailable strong { color: var(--text); }
.evidence { margin-top: 48px; padding-top: 30px; border-top: 2px solid var(--line); }
.evidence h2 { font-size: 24px; }
.evidence p { color: var(--muted); }
.path-cell, .hash-cell { max-width: 430px; overflow-wrap: anywhere; }
@media (max-width: 960px) {
  .split-band, .figure-grid, .matrix-grid { grid-template-columns: 1fr; }
  .selection-band { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .masthead-inner, .chapter-nav-inner, .report-shell { width: min(100% - 20px, 1480px); }
  .masthead-inner { padding-top: 24px; }
  h1 { font-size: 27px; }
  .chapter { padding-top: 36px; }
  .chapter-heading { grid-template-columns: 38px minmax(0, 1fr); }
  .figure-heading { align-items: stretch; flex-direction: column; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric strong { font-size: 19px; }
}
@media print {
  :root { color-scheme: light; --bg: #fff; --surface: #fff; --surface-2: #f1f3f5; --surface-3: #e5e8eb; --text: #111; --muted: #444; --line: #aaa; }
  .chapter-nav, .filter { display: none; }
  .chapter, .figure, table { break-inside: avoid; }
  .table-wrap { overflow: visible; }
}
"""


_SCRIPT = r"""
(() => {
  const applyFilter = (input) => {
    const table = document.getElementById(input.dataset.filterInput);
    if (!table) return;
    const query = input.value.trim().toLowerCase();
    table.querySelectorAll("[data-filter-row]").forEach((row) => {
      const text = row.dataset.filterText || row.textContent.toLowerCase();
      row.hidden = Boolean(query) && !text.includes(query);
    });
  };
  document.querySelectorAll("[data-filter-input]").forEach((input) => {
    input.addEventListener("input", () => applyFilter(input));
  });
})();
"""
