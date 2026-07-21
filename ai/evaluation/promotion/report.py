"""Offline JSON-derived report for versioned policy promotion experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Mapping, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.evaluation.config_ladder.artifact_store import canonical_json_bytes


class ReportModel(BaseModel):
    """Immutable finite report input with no undeclared presentation data."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class ReportSource(ReportModel):
    """Canonical experiment provenance displayed in the report."""

    experiment_id: str = Field(description="Stable policy-promotion experiment identifier.")
    title: str = Field(description="Human-facing report title.")
    generated_at: str = Field(description="UTC report-generation timestamp.")
    schedule_hash: str = Field(description="Authenticated promotion schedule hash.")
    catalog_hash: str = Field(description="Authenticated promotion catalog hash.")


class PolicyIdentityProjection(ReportModel):
    """Executable policy generation identity shown in the comparison header."""

    generation_id: str = Field(description="Stable executable policy generation identifier.")
    display_name: str = Field(description="Human-facing policy generation name.")
    version: str = Field(description="Declared policy semantic version.")
    executable_sha256: str = Field(description="SHA-256 identity of decision-bearing source and parameters.")
    controller_profile: str = Field(description="Controller protocol/profile used by this generation.")


class EloEstimateProjection(ReportModel):
    """One candidate-minus-baseline Elo estimate with uncertainty."""

    candidate_generation_id: str = Field(description="Candidate represented by this estimate.")
    baseline_generation_id: str = Field(description="Baseline represented by this estimate.")
    elo_delta: float = Field(description="Candidate-minus-baseline Elo-equivalent uplift.")
    elo_lower_95: float | None = Field(description="Lower 95 percent confidence bound when estimable.")
    elo_upper_95: float | None = Field(description="Upper 95 percent confidence bound when estimable.")
    games: int = Field(ge=0, description="Admitted treatment rows supporting the estimate.")

    @model_validator(mode="after")
    def validate_interval(self) -> EloEstimateProjection:
        """Reject confidence intervals that cannot describe the estimate."""
        if self.elo_lower_95 is not None and self.elo_upper_95 is not None:
            if self.elo_lower_95 > self.elo_upper_95:
                raise ValueError("Elo lower bound must not exceed upper bound.")
            if not self.elo_lower_95 <= self.elo_delta <= self.elo_upper_95:
                raise ValueError("Elo estimate must lie inside its confidence interval.")
        return self


class PromotionDecisionProjection(ReportModel):
    """Auditable promotion gate outcome."""

    accepted: bool = Field(description="Whether the candidate may replace the baseline.")
    reasons: tuple[str, ...] = Field(description="Every failed gate; empty only for acceptance.")

    @model_validator(mode="after")
    def validate_reasons(self) -> PromotionDecisionProjection:
        """Require rejected candidates to retain at least one explicit gate reason."""
        if self.accepted and self.reasons:
            raise ValueError("Accepted promotions cannot retain failed gate reasons.")
        if not self.accepted and not self.reasons:
            raise ValueError("Rejected promotions must explain at least one failed gate.")
        return self


class PolicySliceProjection(ReportModel):
    """Candidate uplift within a longitudinal panel or matchup family."""

    slice_kind: Literal["panel", "matchup_family", "tag"] = Field(
        description="Reporting dimension represented by the slice."
    )
    slice_id: str = Field(description="Stable panel, matchup-family, or protected-tag identifier.")
    label: str = Field(description="Human-facing slice label.")
    estimate: EloEstimateProjection = Field(description="Candidate uplift inside this slice.")


class RosterStrengthProjection(ReportModel):
    """One fitted nuisance roster strength on the shared Elo scale."""

    configuration_id: str = Field(description="Stable roster configuration identifier.")
    label: str = Field(description="Human-facing roster name.")
    roster_kind: Literal["hero", "monster_party"] = Field(description="Roster catalog family.")
    adjusted_elo: float = Field(description="Centered fitted roster power on the 1000-Elo scale.")
    games: int = Field(ge=0, description="Admitted rows involving this roster.")


class ScheduleCompositionProjection(ReportModel):
    """Immutable treatment composition by roster matchup family."""

    total_matches: int = Field(ge=0, description="Total scheduled treatment rows.")
    comparison_blocks: int = Field(ge=0, description="Counterbalanced four-treatment blocks.")
    hero_vs_monster: int = Field(ge=0, description="Hero-versus-monster treatment rows.")
    monster_vs_monster: int = Field(ge=0, description="Monster-versus-monster treatment rows.")
    hero_vs_hero: int = Field(ge=0, description="Hero-versus-hero treatment rows.")
    mirror: int = Field(ge=0, description="Explicit mirror treatment rows.")

    @model_validator(mode="after")
    def validate_total(self) -> ScheduleCompositionProjection:
        """Ensure family counts account for every scheduled treatment."""
        family_total = self.hero_vs_monster + self.monster_vs_monster + self.hero_vs_hero + self.mirror
        if family_total != self.total_matches:
            raise ValueError("Schedule family counts must sum to total_matches.")
        return self


class WorkerEvidenceProjection(ReportModel):
    """Authenticated worker and scientific-admission evidence counts."""

    scheduled_matches: int = Field(ge=0, description="Total immutable worker requests.")
    completed_matches: int = Field(ge=0, description="Authenticated completed worker results.")
    eligible_matches: int = Field(ge=0, description="Completed rows admitted to estimation.")
    infrastructure_failures: int = Field(ge=0, description="Requests lacking authenticated completion.")
    subjectivity_violations: int = Field(ge=0, description="Detected hidden-information violations.")
    protocol_failures: int = Field(ge=0, description="Rejected, stale, error, or missing command results.")
    deterministic_mismatches: int = Field(ge=0, description="Replicated normalized outcomes that disagreed.")
    content_coverage_regressions: int = Field(ge=0, description="Protected content identities losing evidence.")
    max_active_workers: int = Field(ge=0, description="Observed parallel-worker high-water mark.")

    @model_validator(mode="after")
    def validate_admission_funnel(self) -> WorkerEvidenceProjection:
        """Reject impossible worker completion and admission funnels."""
        if self.completed_matches > self.scheduled_matches:
            raise ValueError("completed_matches cannot exceed scheduled_matches.")
        if self.eligible_matches > self.completed_matches:
            raise ValueError("eligible_matches cannot exceed completed_matches.")
        return self


class TimingMetricProjection(ReportModel):
    """One retained latency or elapsed-time statistic."""

    metric_id: str = Field(description="Stable metric identifier.")
    label: str = Field(description="Human-facing timing metric label.")
    milliseconds: float = Field(ge=0.0, description="Measured duration in milliseconds.")


class RateMetricProjection(ReportModel):
    """One retained throughput statistic with an explicit unit."""

    metric_id: str = Field(description="Stable metric identifier.")
    label: str = Field(description="Human-facing throughput metric label.")
    value: float = Field(ge=0.0, description="Measured throughput value.")
    unit: str = Field(description="Display unit, such as matches/s or commands/s.")


class EfficiencyProjection(ReportModel):
    """Command volume, latency, and throughput retained by the experiment."""

    total_commands: int = Field(ge=0, description="Commands across authenticated completed matches.")
    timings: tuple[TimingMetricProjection, ...] = Field(description="Measured elapsed-time statistics.")
    rates: tuple[RateMetricProjection, ...] = Field(description="Measured throughput statistics.")


class CountMetricProjection(ReportModel):
    """One input-derived content catalog or lifecycle count."""

    metric_id: str = Field(description="Stable count identifier.")
    label: str = Field(description="Human-facing count label.")
    value: int = Field(ge=0, description="Retained count value.")


class ContentCatalogProjection(ReportModel):
    """Configured content universe and observed lifecycle evidence counts."""

    catalog_counts: tuple[CountMetricProjection, ...] = Field(description="Static catalog composition counts.")
    effect_counts: tuple[CountMetricProjection, ...] = Field(description="Observed content lifecycle counts.")


class PolicyPromotionReportProjection(ReportModel):
    """Complete data contract for one offline policy promotion report."""

    schema_version: Literal[1] = Field(default=1, description="Policy promotion report schema version.")
    source: ReportSource = Field(description="Experiment and evidence provenance.")
    candidate: PolicyIdentityProjection = Field(description="Policy generation under review.")
    baseline: PolicyIdentityProjection = Field(description="Previously accepted policy generation.")
    decision: PromotionDecisionProjection = Field(description="Final promotion gate outcome.")
    global_uplift: EloEstimateProjection = Field(description="Primary assignment-balanced Elo contrast.")
    slices: tuple[PolicySliceProjection, ...] = Field(description="Panel, family, and protected-tag contrasts.")
    roster_strengths: tuple[RosterStrengthProjection, ...] = Field(description="Shared-field roster power estimates.")
    schedule: ScheduleCompositionProjection = Field(description="Scheduled matchup-family composition.")
    workers: WorkerEvidenceProjection = Field(description="Worker completion and scientific evidence counts.")
    efficiency: EfficiencyProjection = Field(description="Retained timing and throughput evidence.")
    content: ContentCatalogProjection = Field(description="Catalog and observed effect coverage counts.")

    @model_validator(mode="after")
    def validate_identity_and_counts(self) -> PolicyPromotionReportProjection:
        """Keep all repeated policy and schedule identities internally consistent."""
        estimates = [self.global_uplift, *(row.estimate for row in self.slices)]
        for estimate in estimates:
            if estimate.candidate_generation_id != self.candidate.generation_id:
                raise ValueError("Every Elo estimate must identify the report candidate.")
            if estimate.baseline_generation_id != self.baseline.generation_id:
                raise ValueError("Every Elo estimate must identify the report baseline.")
        if self.schedule.total_matches != self.workers.scheduled_matches:
            raise ValueError("Schedule and worker scheduled-match counts must agree.")
        return self


ReportInput: TypeAlias = PolicyPromotionReportProjection | Mapping[str, object]


def coerce_report_projection(payload: ReportInput) -> PolicyPromotionReportProjection:
    """Validate a typed or dictionary projection before presentation."""
    if isinstance(payload, PolicyPromotionReportProjection):
        return payload
    return PolicyPromotionReportProjection.model_validate(payload)


def render_promotion_report_html(payload: ReportInput) -> str:
    """Render one self-contained report whose values come only from embedded JSON."""
    projection = coerce_report_projection(payload)
    embedded_json = _script_safe_json(projection)
    return _REPORT_DOCUMENT.replace("__REPORT_JSON__", embedded_json)


def write_promotion_report_json(payload: ReportInput, output_path: Path | str) -> Path:
    """Write the validated projection as canonical JSON with a trailing newline."""
    projection = coerce_report_projection(payload)
    destination = Path(output_path)
    _atomic_write(destination, canonical_json_bytes(projection, trailing_newline=True))
    return destination


def write_promotion_report_html(payload: ReportInput, output_path: Path | str) -> Path:
    """Write the self-contained offline HTML report."""
    destination = Path(output_path)
    _atomic_write(destination, render_promotion_report_html(payload).encode("utf-8"))
    return destination


def write_promotion_report(
    payload: ReportInput,
    *,
    json_path: Path | str,
    html_path: Path | str,
) -> tuple[Path, Path]:
    """Write canonical JSON evidence and its self-contained HTML projection."""
    projection = coerce_report_projection(payload)
    written_json = write_promotion_report_json(projection, json_path)
    written_html = write_promotion_report_html(projection, html_path)
    return written_json, written_html


def _script_safe_json(payload: PolicyPromotionReportProjection) -> str:
    """Escape canonical JSON for an inert HTML script-data element."""
    encoded = canonical_json_bytes(payload).decode("utf-8")
    return encoded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _atomic_write(destination: Path, payload: bytes) -> None:
    """Publish one report artifact without exposing a partial file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)


_REPORT_DOCUMENT = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Policy Promotion Review</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f5f7f8;
      --surface: #ffffff;
      --surface-2: #edf1f3;
      --ink: #172126;
      --muted: #59676e;
      --line: #cbd4d8;
      --accent: #006b67;
      --accent-2: #b34a13;
      --good: #147a45;
      --bad: #b12634;
      --neutral: #637078;
      --shadow: 0 8px 24px rgba(23, 33, 38, 0.08);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #101517;
        --surface: #182024;
        --surface-2: #222d32;
        --ink: #eef4f5;
        --muted: #a9b7bd;
        --line: #3b4a50;
        --accent: #58c9c0;
        --accent-2: #f0a36e;
        --good: #66d59a;
        --bad: #ff8590;
        --neutral: #a9b7bd;
        --shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
      }
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
      letter-spacing: 0;
    }
    .skip-link {
      position: fixed;
      left: 1rem;
      top: -5rem;
      z-index: 20;
      padding: .65rem .85rem;
      background: var(--ink);
      color: var(--surface);
      border-radius: 4px;
    }
    .skip-link:focus { top: 1rem; }
    .shell { width: min(1220px, calc(100% - 2rem)); margin: 0 auto; }
    header {
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }
    .masthead { padding: 2.5rem 0 2.2rem; }
    .eyebrow {
      margin: 0 0 .55rem;
      color: var(--accent);
      font-size: .78rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    h1, h2, h3 { line-height: 1.15; letter-spacing: 0; }
    h1 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2rem, 6vw, 4.5rem); }
    h2 { margin: 0; font-size: 1.5rem; }
    h3 { margin: 0; font-size: 1rem; }
    .subtitle { max-width: 72ch; margin: .8rem 0 0; color: var(--muted); }
    .identity-line { margin-top: 1.3rem; display: flex; flex-wrap: wrap; align-items: center; gap: .55rem; }
    .policy-name { font-weight: 750; }
    .versus { color: var(--muted); font-size: .82rem; text-transform: uppercase; letter-spacing: .08em; }
    .status-badge {
      display: inline-flex;
      align-items: center;
      min-height: 2rem;
      padding: .3rem .7rem;
      border: 1px solid currentColor;
      border-radius: 999px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .06em;
      font-size: .72rem;
    }
    .status-badge.accepted { color: var(--good); }
    .status-badge.rejected { color: var(--bad); }
    main { padding: 2rem 0 4rem; }
    .summary-grid, .identity-grid, .chart-grid, .metric-grid {
      display: grid;
      gap: 1rem;
    }
    .summary-grid { grid-template-columns: minmax(0, 1.45fr) minmax(260px, .55fr); }
    .identity-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 1rem; }
    .chart-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .metric-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .panel, .metric {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 7px;
      box-shadow: var(--shadow);
    }
    .panel { padding: 1.15rem; }
    .metric { padding: .9rem; min-width: 0; }
    .metric-label { display: block; color: var(--muted); font-size: .78rem; font-weight: 700; }
    .metric-value { display: block; margin-top: .2rem; font-size: 1.4rem; font-weight: 800; overflow-wrap: anywhere; }
    .hero-metric { font-size: clamp(3rem, 10vw, 6.8rem); font-weight: 850; line-height: .9; }
    .positive { color: var(--good); }
    .negative { color: var(--bad); }
    .neutral { color: var(--neutral); }
    .supporting { margin: .7rem 0 0; color: var(--muted); }
    .section { margin-top: 2.2rem; scroll-margin-top: 1rem; }
    .section-heading { margin-bottom: .85rem; display: flex; align-items: end; justify-content: space-between; gap: 1rem; }
    .section-heading p { margin: 0; color: var(--muted); max-width: 68ch; }
    .reason-list { margin: .8rem 0 0; padding-left: 1.15rem; }
    .reason-list li + li { margin-top: .3rem; }
    .hash { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .76rem; overflow-wrap: anywhere; color: var(--muted); }
    .chart { width: 100%; min-height: 210px; overflow-x: auto; }
    .chart svg { width: 100%; height: auto; min-width: 560px; display: block; }
    .chart text { fill: var(--ink); font-family: inherit; }
    .chart .muted { fill: var(--muted); }
    .chart .grid { stroke: var(--line); stroke-width: 1; }
    .chart .zero { stroke: var(--ink); stroke-width: 1.4; }
    .chart .bar { fill: var(--accent); }
    .chart .bar-secondary { fill: var(--accent-2); }
    .chart .interval { stroke: var(--ink); stroke-width: 2; }
    .chart .estimate { fill: var(--accent); stroke: var(--surface); stroke-width: 2; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }
    table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
    caption { padding: .8rem; text-align: left; font-weight: 800; color: var(--ink); }
    th, td { padding: .7rem .8rem; border-top: 1px solid var(--line); text-align: right; white-space: nowrap; }
    th { color: var(--muted); font-size: .76rem; text-transform: uppercase; letter-spacing: .05em; }
    th:first-child, td:first-child { text-align: left; white-space: normal; }
    tbody tr:hover { background: var(--surface-2); }
    .provenance { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; margin: 0; }
    .provenance div { padding: .75rem; background: var(--surface-2); border-radius: 5px; }
    .provenance dt { color: var(--muted); font-size: .76rem; font-weight: 700; }
    .provenance dd { margin: .2rem 0 0; overflow-wrap: anywhere; }
    footer { padding: 1.3rem 0 2.5rem; color: var(--muted); font-size: .82rem; }
    noscript { display: block; margin: 2rem; padding: 1rem; border: 2px solid var(--bad); }
    @media (max-width: 850px) {
      .summary-grid, .chart-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 560px) {
      .shell { width: min(100% - 1.1rem, 1220px); }
      .masthead { padding: 1.7rem 0; }
      .identity-grid, .metric-grid, .provenance { grid-template-columns: 1fr; }
      .section-heading { display: block; }
      .section-heading p { margin-top: .35rem; }
      .panel { padding: .9rem; }
    }
    @media print {
      :root { --bg: white; --surface: white; --surface-2: #f4f4f4; --ink: black; --muted: #444; --line: #aaa; --shadow: none; }
      .panel, .metric { break-inside: avoid; }
      .chart { overflow: visible; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to report</a>
  <header>
    <div class="shell masthead">
      <p class="eyebrow">Versioned AI evaluation</p>
      <h1 id="report-title">Policy Promotion Review</h1>
      <p class="subtitle" id="report-subtitle"></p>
      <div class="identity-line" aria-label="Compared policy generations">
        <span class="policy-name" id="candidate-name"></span>
        <span class="versus">candidate vs baseline</span>
        <span class="policy-name" id="baseline-name"></span>
        <span class="status-badge" id="decision-badge"></span>
      </div>
    </div>
  </header>
  <main class="shell" id="main">
    <section class="summary-grid" aria-labelledby="decision-title">
      <article class="panel">
        <p class="eyebrow">Assignment-balanced result</p>
        <h2 id="decision-title">Candidate uplift</h2>
        <div class="hero-metric" id="global-elo"></div>
        <p class="supporting" id="global-interval"></p>
        <ul class="reason-list" id="gate-reasons"></ul>
      </article>
      <aside class="panel" aria-labelledby="identity-title">
        <h2 id="identity-title">Executable identities</h2>
        <div class="identity-grid" id="policy-identities"></div>
      </aside>
    </section>

    <section class="section" aria-labelledby="uplift-title">
      <div class="section-heading">
        <div><p class="eyebrow">Power</p><h2 id="uplift-title">Policy uplift by field</h2></div>
        <p>Confidence intervals and point estimates use an Elo-only scale centered on zero.</p>
      </div>
      <div class="panel"><div class="chart" id="uplift-chart"></div></div>
      <div class="table-wrap" id="uplift-table-wrap"></div>
    </section>

    <section class="section" aria-labelledby="schedule-title">
      <div class="section-heading">
        <div><p class="eyebrow">Design</p><h2 id="schedule-title">Schedule composition</h2></div>
        <p>Hero, monster, and mirror treatments remain explicit rather than being folded into one total.</p>
      </div>
      <div class="chart-grid">
        <article class="panel"><h3>Matchup families</h3><div class="chart" id="schedule-chart"></div></article>
        <article class="panel"><h3>Worker evidence</h3><div class="chart" id="worker-chart"></div></article>
      </div>
    </section>

    <section class="section" aria-labelledby="efficiency-title">
      <div class="section-heading">
        <div><p class="eyebrow">Execution</p><h2 id="efficiency-title">Efficiency and timing</h2></div>
        <p>Durations and rates use separate scales and retain their declared units.</p>
      </div>
      <div class="metric-grid" id="efficiency-metrics"></div>
      <div class="chart-grid">
        <article class="panel"><h3>Timing</h3><div class="chart" id="timing-chart"></div></article>
        <article class="panel"><h3>Throughput</h3><div class="chart" id="rate-chart"></div></article>
      </div>
    </section>

    <section class="section" aria-labelledby="rosters-title">
      <div class="section-heading">
        <div><p class="eyebrow">Configuration power</p><h2 id="rosters-title">Roster strengths</h2></div>
        <p>Roster coefficients are nuisance estimates on their own 1000-centered Elo scale.</p>
      </div>
      <div class="panel"><div class="chart" id="roster-chart"></div></div>
      <div class="table-wrap" id="roster-table-wrap"></div>
    </section>

    <section class="section" aria-labelledby="content-title">
      <div class="section-heading">
        <div><p class="eyebrow">Breadth</p><h2 id="content-title">Content coverage</h2></div>
        <p>Catalog availability and observed lifecycle evidence are shown independently.</p>
      </div>
      <div class="chart-grid">
        <article class="panel"><h3>Catalog</h3><div class="chart" id="catalog-chart"></div></article>
        <article class="panel"><h3>Effects observed</h3><div class="chart" id="effects-chart"></div></article>
      </div>
    </section>

    <section class="section panel" aria-labelledby="provenance-title">
      <div class="section-heading">
        <div><p class="eyebrow">Evidence</p><h2 id="provenance-title">Provenance</h2></div>
      </div>
      <dl class="provenance" id="provenance"></dl>
    </section>
  </main>
  <footer class="shell">Offline report. Every displayed measurement is rendered from the embedded canonical JSON projection.</footer>
  <noscript>This report needs JavaScript to project its embedded JSON evidence into accessible charts and tables.</noscript>
  <script type="application/json" id="report-data">__REPORT_JSON__</script>
  <script>
  (() => {
    "use strict";
    const report = JSON.parse(document.getElementById("report-data").textContent);
    const byId = (id) => document.getElementById(id);
    const svgNS = "http://www.w3.org/2000/svg";
    const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
    const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

    function setText(id, value) { byId(id).textContent = String(value); }
    function signed(value, digits = 1) {
      const shown = Number(value).toFixed(digits);
      return `${value > 0 ? "+" : ""}${shown}`;
    }
    function tone(value) { return value > 0 ? "positive" : value < 0 ? "negative" : "neutral"; }
    function el(name, className, text) {
      const node = document.createElement(name);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = String(text);
      return node;
    }
    function svgEl(name, attributes = {}, text) {
      const node = document.createElementNS(svgNS, name);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
      if (text !== undefined) node.textContent = String(text);
      return node;
    }
    function metric(label, value) {
      const node = el("div", "metric");
      node.append(el("span", "metric-label", label), el("strong", "metric-value", value));
      return node;
    }
    function humanize(value) {
      return String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function renderIdentity(identity, role) {
      const node = el("div", "metric");
      node.append(el("span", "metric-label", role), el("strong", "metric-value", identity.display_name));
      node.append(el("div", "supporting", `${identity.generation_id} · v${identity.version}`));
      node.append(el("div", "hash", identity.executable_sha256));
      node.append(el("div", "supporting", identity.controller_profile));
      return node;
    }

    function table(containerId, captionText, columns, rows) {
      const tableNode = document.createElement("table");
      tableNode.append(el("caption", "", captionText));
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      columns.forEach((column) => {
        const cell = el("th", "", column.label);
        cell.scope = "col";
        headRow.append(cell);
      });
      head.append(headRow);
      const body = document.createElement("tbody");
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((column, index) => {
          const cell = el(index === 0 ? "th" : "td", "", column.value(row));
          if (index === 0) cell.scope = "row";
          tr.append(cell);
        });
        body.append(tr);
      });
      tableNode.append(head, body);
      byId(containerId).replaceChildren(tableNode);
    }

    function chartShell(containerId, title, description, height) {
      const container = byId(containerId);
      const titleId = `${containerId}-title`;
      const descId = `${containerId}-desc`;
      const svg = svgEl("svg", {
        viewBox: `0 0 920 ${height}`,
        role: "img",
        "aria-labelledby": `${titleId} ${descId}`,
      });
      svg.append(svgEl("title", { id: titleId }, title), svgEl("desc", { id: descId }, description));
      container.replaceChildren(svg);
      return svg;
    }

    function renderEloChart(containerId, rows, title) {
      const normalized = rows.map((row) => ({
        label: row.label,
        value: row.estimate.elo_delta,
        low: row.estimate.elo_lower_95 ?? row.estimate.elo_delta,
        high: row.estimate.elo_upper_95 ?? row.estimate.elo_delta,
      }));
      const height = Math.max(220, 76 + normalized.length * 44);
      const svg = chartShell(containerId, title, "Elo point estimates with 95 percent confidence intervals around a zero reference.", height);
      const left = 260, right = 850, center = (left + right) / 2;
      const extent = Math.max(1, ...normalized.flatMap((row) => [Math.abs(row.low), Math.abs(row.high), Math.abs(row.value)]));
      const x = (value) => center + (value / extent) * ((right - left) / 2);
      svg.append(svgEl("line", { x1: center, x2: center, y1: 34, y2: height - 34, class: "zero" }));
      [-1, -.5, .5, 1].forEach((fraction) => {
        const px = center + fraction * ((right - left) / 2);
        svg.append(svgEl("line", { x1: px, x2: px, y1: 34, y2: height - 34, class: "grid" }));
      });
      normalized.forEach((row, index) => {
        const y = 62 + index * 44;
        svg.append(svgEl("text", { x: 12, y: y + 5, "font-size": 14 }, row.label));
        svg.append(svgEl("line", { x1: x(row.low), x2: x(row.high), y1: y, y2: y, class: "interval" }));
        svg.append(svgEl("line", { x1: x(row.low), x2: x(row.low), y1: y - 6, y2: y + 6, class: "interval" }));
        svg.append(svgEl("line", { x1: x(row.high), x2: x(row.high), y1: y - 6, y2: y + 6, class: "interval" }));
        svg.append(svgEl("circle", { cx: x(row.value), cy: y, r: 6, class: "estimate" }));
        svg.append(svgEl("text", { x: 900, y: y + 5, "text-anchor": "end", "font-size": 13 }, `${signed(row.value)} Elo`));
      });
      svg.append(svgEl("text", { x: left, y: height - 10, class: "muted", "font-size": 12 }, `${signed(-extent)} Elo`));
      svg.append(svgEl("text", { x: center, y: height - 10, class: "muted", "font-size": 12, "text-anchor": "middle" }, "0"));
      svg.append(svgEl("text", { x: right, y: height - 10, class: "muted", "font-size": 12, "text-anchor": "end" }, `${signed(extent)} Elo`));
    }

    function renderBarChart(containerId, rows, title, unit, valueFormatter = number.format) {
      const height = Math.max(220, 76 + rows.length * 40);
      const svg = chartShell(containerId, title, `${title}. Horizontal bars use a ${unit} scale.`, height);
      const left = 255, right = 850;
      const maximum = Math.max(1, ...rows.map((row) => row.value));
      rows.forEach((row, index) => {
        const y = 50 + index * 40;
        const width = (row.value / maximum) * (right - left);
        svg.append(svgEl("text", { x: 12, y: y + 14, "font-size": 13 }, row.label));
        svg.append(svgEl("rect", { x: left, y, width: right - left, height: 20, rx: 2, fill: "var(--surface-2)" }));
        svg.append(svgEl("rect", { x: left, y, width, height: 20, rx: 2, class: index % 2 ? "bar-secondary" : "bar" }));
        svg.append(svgEl("text", { x: 900, y: y + 15, "text-anchor": "end", "font-size": 13 }, `${valueFormatter(row.value)} ${row.unit ?? unit}`));
      });
      svg.append(svgEl("text", { x: left, y: height - 10, class: "muted", "font-size": 12 }, `0 ${unit}`));
      svg.append(svgEl("text", { x: right, y: height - 10, class: "muted", "font-size": 12, "text-anchor": "end" }, `${valueFormatter(maximum)} ${unit}`));
    }

    const upliftRows = [{ label: "Global", estimate: report.global_uplift }, ...report.slices];
    const global = report.global_uplift;
    setText("report-title", report.source.title);
    setText("report-subtitle", `${report.source.experiment_id} · generated ${report.source.generated_at}`);
    setText("candidate-name", report.candidate.display_name);
    setText("baseline-name", report.baseline.display_name);
    setText("decision-badge", report.decision.accepted ? "Accepted" : "Rejected");
    byId("decision-badge").classList.add(report.decision.accepted ? "accepted" : "rejected");
    setText("global-elo", `${signed(global.elo_delta)} Elo`);
    byId("global-elo").classList.add(tone(global.elo_delta));
    const lower = global.elo_lower_95 === null ? "not estimable" : signed(global.elo_lower_95);
    const upper = global.elo_upper_95 === null ? "not estimable" : signed(global.elo_upper_95);
    setText("global-interval", `95% CI ${lower} to ${upper} · ${integer.format(global.games)} admitted treatments`);
    const reasons = byId("gate-reasons");
    const reasonRows = report.decision.reasons.length ? report.decision.reasons : ["All declared promotion gates passed."];
    reasonRows.forEach((reason) => reasons.append(el("li", "", humanize(reason))));
    byId("policy-identities").append(renderIdentity(report.candidate, "Candidate"), renderIdentity(report.baseline, "Baseline"));

    renderEloChart("uplift-chart", upliftRows, "Candidate policy uplift by reporting field");
    table("uplift-table-wrap", "Policy uplift estimates", [
      { label: "Field", value: (row) => row.label },
      { label: "Kind", value: (row) => row.slice_kind ?? "global" },
      { label: "Delta", value: (row) => `${signed(row.estimate.elo_delta)} Elo` },
      { label: "Lower 95%", value: (row) => row.estimate.elo_lower_95 === null ? "—" : signed(row.estimate.elo_lower_95) },
      { label: "Upper 95%", value: (row) => row.estimate.elo_upper_95 === null ? "—" : signed(row.estimate.elo_upper_95) },
      { label: "Games", value: (row) => integer.format(row.estimate.games) },
    ], upliftRows);

    renderBarChart("schedule-chart", [
      { label: "Hero vs monster", value: report.schedule.hero_vs_monster },
      { label: "Monster vs monster", value: report.schedule.monster_vs_monster },
      { label: "Hero vs hero", value: report.schedule.hero_vs_hero },
      { label: "Mirror", value: report.schedule.mirror },
    ], "Scheduled matchup treatments", "matches", integer.format);
    renderBarChart("worker-chart", [
      { label: "Scheduled", value: report.workers.scheduled_matches },
      { label: "Completed", value: report.workers.completed_matches },
      { label: "Eligible", value: report.workers.eligible_matches },
      { label: "Infrastructure failures", value: report.workers.infrastructure_failures },
      { label: "Subjectivity violations", value: report.workers.subjectivity_violations },
      { label: "Protocol failures", value: report.workers.protocol_failures },
      { label: "Determinism mismatches", value: report.workers.deterministic_mismatches },
      { label: "Coverage regressions", value: report.workers.content_coverage_regressions },
    ], "Authenticated worker evidence", "events", integer.format);

    byId("efficiency-metrics").append(
      metric("Total commands", integer.format(report.efficiency.total_commands)),
      metric("Comparison blocks", integer.format(report.schedule.comparison_blocks)),
      metric("Active workers", integer.format(report.workers.max_active_workers)),
      metric("Eligible matches", integer.format(report.workers.eligible_matches)),
    );
    renderBarChart("timing-chart", report.efficiency.timings.map((row) => ({ label: row.label, value: row.milliseconds })), "Retained timing summary", "ms", number.format);
    renderBarChart("rate-chart", report.efficiency.rates.map((row) => ({ label: row.label, value: row.value, unit: row.unit })), "Retained throughput summary", "rate", number.format);

    const rosters = [...report.roster_strengths].sort((a, b) => b.adjusted_elo - a.adjusted_elo || a.configuration_id.localeCompare(b.configuration_id));
    renderBarChart("roster-chart", rosters.map((row) => ({ label: row.label, value: row.adjusted_elo })), "Centered roster strengths", "Elo", number.format);
    table("roster-table-wrap", "Roster strength estimates", [
      { label: "Roster", value: (row) => row.label },
      { label: "Kind", value: (row) => humanize(row.roster_kind) },
      { label: "Adjusted Elo", value: (row) => number.format(row.adjusted_elo) },
      { label: "Games", value: (row) => integer.format(row.games) },
      { label: "Configuration ID", value: (row) => row.configuration_id },
    ], rosters);

    renderBarChart("catalog-chart", report.content.catalog_counts.map((row) => ({ label: row.label, value: row.value })), "Catalog composition", "identities", integer.format);
    renderBarChart("effects-chart", report.content.effect_counts.map((row) => ({ label: row.label, value: row.value })), "Observed lifecycle evidence", "identities", integer.format);

    const provenanceRows = [
      ["Experiment", report.source.experiment_id],
      ["Generated", report.source.generated_at],
      ["Schedule SHA-256", report.source.schedule_hash],
      ["Catalog SHA-256", report.source.catalog_hash],
      ["Candidate executable", report.candidate.executable_sha256],
      ["Baseline executable", report.baseline.executable_sha256],
    ];
    const provenance = byId("provenance");
    provenanceRows.forEach(([label, value]) => {
      const node = document.createElement("div");
      node.append(el("dt", "", label), el("dd", label.includes("SHA") || label.includes("executable") ? "hash" : "", value));
      provenance.append(node);
    });
  })();
  </script>
</body>
</html>
'''
