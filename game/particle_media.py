"""Absolute world-space samples of authored particles; no simulation state."""

from dataclasses import dataclass
from math import hypot

from game.action_media import ActionStripSample
from game.animation import body_elevation_steps
from game.animation_types import ParticleMediaAsset
from game.residue_media import landing_point, landing_template, target_cell


@dataclass(frozen=True, slots=True)
class ParticleSample:
    identity: int
    grid: tuple[float, float]
    elevation: float
    previous_grid: tuple[float, float]
    previous_elevation: float
    size: float
    fragment: tuple[tuple[float, float], ...] = ()


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
                duration = particle.duration * family.durationScale * (1.08 if copy else 1)
                t = age - particle.delay * family.delayScale
                if not 0 <= t < duration:
                    continue
                vx, vy = (goal[0] - source[0]) / duration, (goal[1] - source[1]) / duration
                vz = (region.elevation_steps - source_height + .5 * particle.gravity * duration ** 2) / duration
                point = source[0] + vx * t, source[1] + vy * t
                height = source_height + vz * t - .5 * particle.gravity * t * t
                previous = point[0] - vx * asset.tailSeconds, point[1] - vy * asset.tailSeconds
                previous_height = height - (vz - particle.gravity * t) * asset.tailSeconds
                identity = (region_index * len(template.particles) + particle.id) * copies + copy
                result.append(ParticleSample(identity, point, height, previous, previous_height,
                    particle.size, tuple((point[0] - goal[0], point[1] - goal[1])
                        for vertex in particle.fragment for point in (landing_point(region.ellipse, vertex),))
                        if style.primitive == "fragments" else ()))
    return tuple(result)
