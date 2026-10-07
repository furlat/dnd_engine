"""Exact public bytes. Uncommitted tail writes never enter the delivery index."""
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import shutil
import struct
from typing import BinaryIO

from player_server.framing import MAX_PACKET_BYTES


class RecordUnavailable(OSError):
    """A previously committed public record can no longer be read."""


@dataclass(slots=True)
class AudienceSpool:
    path: Path
    file: BinaryIO
    offsets: list[tuple[int, int]] = field(default_factory=list)
    committed_bytes: int = 0


@dataclass(slots=True)
class Recording:
    directory: Path
    quota_per_audience: int
    audiences: dict[str, AudienceSpool]


def open_recording(directory: Path, seats: tuple[str, ...], quota: int) -> Recording:
    directory.mkdir(parents=True, exist_ok=False)
    audiences = {}
    try:
        for seat in seats:
            path = directory / (sha256(seat.encode()).hexdigest() + '.frames')
            audiences[seat] = AudienceSpool(path, path.open('w+b'))
    except BaseException:
        for spool in audiences.values():
            spool.file.close()
            spool.path.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return Recording(directory, quota, audiences)


def has_capacity(recording: Recording) -> bool:
    required = MAX_PACKET_BYTES + 4
    return (all(spool.committed_bytes + required <= recording.quota_per_audience
                for spool in recording.audiences.values())
        and shutil.disk_usage(recording.directory).free >= required * len(recording.audiences))


def stage_record(recording: Recording, seat: str, sequence: int, payload: bytes) -> tuple[int, int]:
    spool = recording.audiences[seat]
    if sequence != len(spool.offsets) or len(payload) > MAX_PACKET_BYTES:
        raise ValueError('Unexpected public sequence or oversized record')
    position = spool.committed_bytes
    if position + len(payload) + 4 > recording.quota_per_audience:
        raise OSError('Recording quota exhausted')
    spool.file.seek(position)
    spool.file.write(struct.pack('!I', len(payload)))
    spool.file.write(payload)
    spool.file.flush()
    return position, len(payload)


def commit_records(recording: Recording, staged: dict[str, tuple[int, int]]) -> None:
    for seat, (position, _) in staged.items():
        spool = recording.audiences[seat]
        if position != spool.committed_bytes:
            raise ValueError('Recording commit does not follow its retained prefix')
    for seat, location in staged.items():
        spool = recording.audiences[seat]
        spool.offsets.append(location)
        spool.committed_bytes = location[0] + location[1] + 4


def discard_tails(recording: Recording) -> None:
    for spool in recording.audiences.values():
        spool.file.truncate(spool.committed_bytes)


def read_record(recording: Recording, seat: str, sequence: int) -> bytes:
    spool = recording.audiences[seat]
    position, size = spool.offsets[sequence]
    with spool.path.open('rb') as source:
        source.seek(position + 4)
        result = source.read(size)
    if len(result) != size:
        raise EOFError('Committed public record is truncated')
    return result


def close_recording(recording: Recording) -> None:
    for spool in recording.audiences.values():
        spool.file.close()


def expire_recording(recording: Recording) -> None:
    """Remove only this game's owned public spool after its retention expires."""
    close_recording(recording)
    for spool in recording.audiences.values():
        spool.path.unlink(missing_ok=True)
        spool.offsets.clear()
    recording.directory.rmdir()


def require_record(recording: Recording, seat: str, sequence: int) -> None:
    spool = recording.audiences[seat]
    if not 0 <= sequence < len(spool.offsets):
        raise RecordUnavailable('Public sequence is not retained')
    position, length = spool.offsets[sequence]
    try:
        if spool.path.stat().st_size < position + length + 4:
            raise RecordUnavailable('Committed public record is truncated')
    except OSError as error:
        raise RecordUnavailable('Public recording is unavailable') from error


def read_chunk(recording: Recording, seat: str, sequence: int, offset: int, size: int) -> bytes:
    spool = recording.audiences[seat]
    if not 0 <= sequence < len(spool.offsets):
        raise RecordUnavailable('Public sequence is not retained')
    position, length = spool.offsets[sequence]
    count = min(size, length - offset)
    if count < 0:
        raise ValueError('Record offset beyond committed payload')
    try:
        with spool.path.open('rb') as source:
            source.seek(position + 4 + offset)
            result = source.read(count)
    except OSError as error:
        raise RecordUnavailable('Public recording is unavailable') from error
    if len(result) != count:
        raise RecordUnavailable('Committed public record is truncated')
    return result
