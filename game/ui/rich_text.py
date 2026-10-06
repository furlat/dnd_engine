"""The native combat-log markup, rendered as measured antialiased spans."""

from dataclasses import dataclass, replace

import pygame

from game.ui.primitives import BLUE, GOLD, GREEN, MUTED, RED, TEXT


@dataclass(frozen=True, slots=True)
class TextSpan:
    text: str
    color: tuple[int, int, int] = TEXT
    bold: bool = False


_STYLES = {'cyan': (BLUE, False), 'yellow': (GOLD, False), 'red': (RED, False),
    'green': (GREEN, False), 'bold': (TEXT, True), 'dim': (MUTED, False),
    'bold red': (RED, True), 'bold yellow': (GOLD, True)}


def log_spans(value: str) -> tuple[TextSpan, ...]:
    """Unknown, nested and unfinished delimiters remain literal text."""
    result: list[TextSpan] = []
    index = 0
    while index < len(value):
        end = index + 1
        span = TextSpan(value[index:end])
        if value[index] == '{':
            depth = 1
            while end < len(value) and depth:
                depth += (value[end] == '{') - (value[end] == '}')
                end += 1
            block = value[index:end]
            style, separator, content = block[1:-1].partition(':')
            if not depth and separator and style in _STYLES and not any(c in content for c in '{}') and '**' not in content:
                color, bold = _STYLES[style]
                span = TextSpan(content, color, bold)
            else:
                span = TextSpan(block)
        elif value.startswith('**', index):
            close = value.find('**', index + 2)
            end = len(value) if close < 0 else close + 2
            content = value[index+2:close] if close >= 0 else ''
            span = (TextSpan(content, bold=True) if close >= 0 and '{' not in content and '}' not in content
                    else TextSpan(value[index:end]))
        if result and result[-1].color == span.color and result[-1].bold == span.bold:
            result[-1] = replace(result[-1], text=result[-1].text + span.text)
        else:
            result.append(span)
        index = end
    return tuple(result)


def plain_log(value: str) -> str:
    return ''.join(span.text for span in log_spans(value))


def wrap_spans(spans: tuple[TextSpan, ...], normal: pygame.font.Font,
               bold: pygame.font.Font, width: int) -> tuple[tuple[TextSpan, ...], ...]:
    """Keep explicit newlines/indentation and split long tokens without loss."""
    lines: list[list[TextSpan]] = [[]]
    used = 0
    for span in spans:
        font = bold if span.bold else normal
        # Runs ending in whitespace keep word boundaries where they fit. A
        # longer-than-line run is divided at measured character boundaries.
        runs: list[str] = []
        start = 0
        for i, char in enumerate(span.text):
            if char.isspace():
                if start < i:
                    runs.append(span.text[start:i])
                runs.append(char)
                start = i + 1
        if start < len(span.text):
            runs.append(span.text[start:])
        for run in runs:
            if run == '\n':
                lines.append([])
                used = 0
                continue
            if run == '\r':
                continue
            size = font.size(run)[0]
            if used and used + size > width and not run.isspace():
                lines.append([])
                used = 0
            for char in run:
                size = font.size(char)[0]
                if used and used + size > max(1, width):
                    lines.append([])
                    used = 0
                cell = replace(span, text=char)
                if lines[-1] and lines[-1][-1].color == cell.color and lines[-1][-1].bold == cell.bold:
                    lines[-1][-1] = replace(lines[-1][-1], text=lines[-1][-1].text + char)
                else:
                    lines[-1].append(cell)
                used += size
    return tuple(tuple(line) for line in lines)


def draw_spans(screen: pygame.Surface, lines: tuple[tuple[TextSpan, ...], ...],
               normal: pygame.font.Font, bold: pygame.font.Font,
               position: tuple[int, int], *, muted: bool = False) -> None:
    for row, spans in enumerate(lines):
        x, y = position[0], position[1] + row * normal.get_linesize()
        for span in spans:
            image = (bold if span.bold else normal).render(span.text, True, MUTED if muted else span.color)
            screen.blit(image, (x, y))
            x += image.width
