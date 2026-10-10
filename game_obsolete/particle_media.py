"""Absolute world-space samples of authored particles; no simulation state."""

from dataclasses import dataclass
from math import hypot

from game.action_media import ActionStripSample
from game.animation import body_elevation_steps
from game.animation_types import ParticleMediaAsset
from game.residue_media import landing_point, landing_template, particle_schedule, target_cell


@dataclass(frozen=True, slots=True)
class ParticleSample:
    identity: int
    grid: tuple[float, float]
    elevation: float
    previous_grid: tuple[float, float]
    previous_elevation: float
    size: float
    fragment: tuple[tuple[float, float], ...] = ()
    solid: float = 1
    age: float = 0


def sample_particles(sample: ActionStripSample, asset: ParticleMediaAsset) -> tuple[ParticleSample, ...]:
    cue = sample.cue
    if asset.region is not None:
        return sample_region_particles(sample, asset)
    age = sample.elapsed_ms / 1000 * cue.track.fps / asset.defaultFps
    dx, dy = cue.direction
    length = hypot(dx, dy)
    ux, uy = (dx / length, dy / length) if length else (1.0, 0.0)
    scale = cue.track.scale
    height = body_elevation_steps(cue.contact, cue.data)

    def point(x: float, y: float) -> tuple[float, float]:
        return (cue.contact.grid[0] + (x * ux - y * uy) * scale,
                cue.contact.grid[1] + (x * uy + y * ux) * scale)

    result = []
    for particle in asset.particles:
        t = age - particle.delay
        if not 0 <= t < particle.life:
            continue
        x, y = particle.x + particle.vx * t, particle.y + particle.vy * t
        z = particle.z + particle.vz * t - .5 * particle.g * t * t
        # The approved artwork uses the local velocity tangent for its tail.
        previous = point(x - particle.vx * asset.tailSeconds, y - particle.vy * asset.tailSeconds)
        previous_z = z - (particle.vz - particle.g * t) * asset.tailSeconds
        result.append(ParticleSample(particle.id, point(x, y), height + z * scale,
            previous, height + previous_z * scale, particle.size * scale))
    return tuple(result)


def sample_region_particles(sample: ActionStripSample, asset: ParticleMediaAsset) -> tuple[ParticleSample, ...]:
    cue, style = sample.cue, asset.region
    release = cue.release
    assert style is not None
    if release is None or release.pattern is None:
        return ()
    family = style.families[release.pattern]
    age = sample.elapsed_ms / 1000 * cue.track.fps / asset.defaultFps
    source = cue.contact.grid
    source_height = body_elevation_steps(cue.contact, cue.data) + style.sourceHeight
    result = []
    copies = style.criticalCopies if release.critical_hit else 1
    for region_index, region in enumerate(release.regions):
        template = landing_template(style, region.ellipse)
        for particle in template.particles:
            goal = landing_point(region.ellipse, particle.target)
            if target_cell(goal) not in region.positions:
                continue
            for copy in range(copies):
                delay, duration, melt = particle_schedule(particle, family, cue.response, copy)
                t = age - delay
                if not 0 <= t < duration + melt:
                    continue
                gravity = particle.gravity * (cue.response.gravityScale if cue.response else 1)
                point, height = _flight_point(source, source_height, goal, region.elevation_steps,
                    min(t, duration), duration, gravity)
                vx, vy = (goal[0]-source[0])/duration, (goal[1]-source[1])/duration
                vz = (region.elevation_steps-source_height+.5*gravity*duration**2)/duration
                previous = point[0]-vx*asset.tailSeconds, point[1]-vy*asset.tailSeconds
                previous_height = height-(vz-gravity*min(t,duration))*asset.tailSeconds
                identity = (region_index * len(template.particles) + particle.id) * copies + copy
                size = particle.size * (cue.response.sizeScale if cue.response else 1)
                if cue.response is not None and cue.response.heavyEvery and particle.id % cue.response.heavyEvery == 0:
                    size *= cue.response.heavyScale
                solid = 1 - max(0, t - duration) / melt if melt else 1
                result.append(ParticleSample(identity, point, height, previous, previous_height,
                    size, tuple((point[0] - goal[0], point[1] - goal[1])
                        for vertex in particle.fragment for point in (landing_point(region.ellipse, vertex),))
                        if style.primitive == "fragments" else (), solid, t))
    return tuple(result)


def _flight_point(source: tuple[float, float], source_height: float,
                   goal: tuple[float, float], goal_height: float, t: float,
                   duration: float, gravity: float) -> tuple[tuple[float, float], float]:
    vx, vy = (goal[0] - source[0]) / duration, (goal[1] - source[1]) / duration
    vz = (goal_height - source_height + .5 * gravity * duration ** 2) / duration
    return (source[0] + vx * t, source[1] + vy * t), source_height + vz * t - .5 * gravity * t * t


@dataclass(frozen=True, slots=True)
class VaporSample:
    identity: tuple[int, int]
    grid: tuple[float, float]
    elevation: float
    size: float
    alpha: float
    color: int


def sample_vapor(sample: ActionStripSample, asset: ParticleMediaAsset) -> tuple[VaporSample, ...]:
    """Finite emissions keep their own historical droplet origin while rising."""
    cue, style = sample.cue, asset.region
    response, release = cue.response, cue.release
    if style is None or response is None or response.vapor is None or release is None or release.pattern is None:
        return ()
    vapor, family = response.vapor, style.families[release.pattern]
    age = sample.elapsed_ms / 1000 * cue.track.fps / asset.defaultFps
    source_height = body_elevation_steps(cue.contact, cue.data) + style.sourceHeight
    result = []
    copies = style.criticalCopies if release.critical_hit else 1
    for region_index, region in enumerate(release.regions):
        template = landing_template(style, region.ellipse)
        for particle in template.particles:
            goal = landing_point(region.ellipse, particle.target)
            if particle.id % vapor.every or target_cell(goal) not in region.positions:
                continue
            for copy in range(copies):
                delay, duration, _ = particle_schedule(particle, family, response, copy)
                identity = (region_index * len(template.particles) + particle.id) * copies + copy
                for emission in range(vapor.count):
                    emit = duration * vapor.startFraction + emission * vapor.interval
                    t = age - delay - emit
                    if not 0 <= t < vapor.life:
                        continue
                    point, height = _flight_point(cue.contact.grid, source_height, goal, region.elevation_steps,
                        min(emit, duration), duration, particle.gravity * response.gravityScale)
                    u = t / vapor.life
                    drift = ((identity * 31 + emission * 17) % 101 / 100 - .5) * .15
                    result.append(VaporSample((identity, emission), (point[0] + drift * u, point[1]),
                        height + vapor.rise * u, 1 + int(u * 2), (1-u) * vapor.opacity, vapor.color))
    return tuple(result)
