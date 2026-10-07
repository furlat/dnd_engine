"""Bounded frames shared by the local desktop and network worker transports."""
from typing import IO
import struct

MAX_PACKET_BYTES = 64 * 1024 * 1024


def read_packet(stream: IO[bytes]) -> bytes | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise EOFError('Truncated native reply header')
    size, = struct.unpack('!I', header)
    if size > MAX_PACKET_BYTES:
        raise ValueError('Native packet exceeds the bounded transport size')
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError('Truncated native packet')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def write_packet(stream: IO[bytes], payload: bytes) -> None:
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError('Native packet exceeds the bounded transport size')
    stream.write(struct.pack('!I', len(payload)))
    stream.write(payload)
    stream.flush()
