"""5x5 dot-matrix animations — exact CSS opacity from vercel.app SVGs.
Each pattern samples the SVG's keyframe + delay model and returns per-cell alpha values.
Rendering uses two layers per cell: a small dim background dot + a larger animated foreground dot."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui.theme import (
    C_ACCENT,
    C_GREEN,
    C_ORANGE,
    C_PURPLE,
    C_RED,
    M_BG,
    M_BORDER,
    M_IDLE_ON,
    M_OFF,
)

GRID = 5

_STATE_FAMILIES = {
    "idle": "ambient",
    "listening": "input",
    "thinking": "thought",
    "acting": "thought",
    "speaking": "output",
    "error": "alert",
    "muted": "ambient",
}

_STATE_POOLS: dict[str, list[str]] = {
    "idle": ["rain", "sparkle", "diamond", "lattice", "echo"],
    "listening": ["halt", "equalizer"],
    "thinking": ["loading", "orbit", "twin_orbit", "thinking", "compile", "needle", "quartet"],
    "acting": ["thinking", "knights_tour"],
    "speaking": ["wave", "cross_expand", "scatter"],
    "error": ["halt"],
    "muted": ["sparkle"],
}

_IDLE_HOLD_MIN = 100
_IDLE_HOLD_MAX = 250


@dataclass(frozen=True)
class MatrixStyle:
    on_color: str
    off_color: str
    bg_color: str
    border_color: str
    interval_ms: int
    border_width: float = 1.0


_STYLES: dict[str, MatrixStyle] = {
    "idle": MatrixStyle(M_IDLE_ON, M_OFF, M_BG, M_BORDER, 80),
    "listening": MatrixStyle(C_GREEN, "#0f1a14", M_BG, "#1a3d2a", 80),
    "thinking": MatrixStyle(C_ACCENT, "#0d1520", M_BG, "#1a3050", 80),
    "acting": MatrixStyle(C_ORANGE, "#1a140d", M_BG, "#3d2a14", 80),
    "speaking": MatrixStyle(C_PURPLE, "#140f1a", M_BG, "#2a1a3d", 80),
    "error": MatrixStyle(C_RED, "#1a0d0d", M_BG, "#3d1414", 80),
    "muted": MatrixStyle("#3d444d", M_OFF, M_BG, C_RED, 300, 1.5),
}


def _zero_grid() -> list[list[float]]:
    return [[0.0] * GRID for _ in range(GRID)]


# ── CSS animation sampler (returns alpha 0.0-1.0) ────

@dataclass
class _CellAnim:
    delay: int
    duration: int | None = None


def _eval_keyframes(kf: list[tuple[float, float]], pct: float) -> float:
    for i in range(len(kf) - 1):
        p0, v0 = kf[i]
        p1, v1 = kf[i + 1]
        if p0 <= pct <= p1:
            if p1 == p0:
                return v0
            t = (pct - p0) / (p1 - p0)
            return v0 + (v1 - v0) * t
    return kf[-1][1]


def _sample_alpha(
    frame: int,
    duration_ms: int,
    keyframes: list[tuple[float, float]],
    cells: list[list[_CellAnim | None]],
    timer_ms: int = 80,
) -> list[list[float]]:
    """Return 5x5 alpha grid (0.0-1.0) by sampling the CSS animation at *frame*."""
    t = frame * timer_ms
    g = _zero_grid()
    for r in range(GRID):
        for c in range(GRID):
            ca = cells[r][c]
            if ca is None:
                continue
            dur = ca.duration if ca.duration is not None else duration_ms
            if t < ca.delay:
                alpha = keyframes[0][1]
            else:
                elapsed = (t - ca.delay) % dur
                alpha = _eval_keyframes(keyframes, elapsed / dur)
            g[r][c] = max(0.0, min(1.0, alpha))
    return g


# ── 03 Wave ──────────────────────────────────────────

_WAVE_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(r * 48 + c * 480) for c in range(5)] for r in range(5)
]

def _pattern_wave(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2400,
        [(0, 0.05), (0.20, 1.0), (0.55, 0.18), (1.0, 0.05)], _WAVE_CELLS)


# ── 04 Cross Expand ──────────────────────────────────

_XPAND_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(880), _CellAnim(660), _CellAnim(440), _CellAnim(660), _CellAnim(880)],
    [_CellAnim(660), _CellAnim(440), _CellAnim(220), _CellAnim(440), _CellAnim(660)],
    [_CellAnim(440), _CellAnim(220), _CellAnim(0),   _CellAnim(220), _CellAnim(440)],
    [_CellAnim(660), _CellAnim(440), _CellAnim(220), _CellAnim(440), _CellAnim(660)],
    [_CellAnim(880), _CellAnim(660), _CellAnim(440), _CellAnim(660), _CellAnim(880)],
]

def _pattern_cross_expand(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2200,
        [(0, 0), (0.08, 1), (0.36, 0.05), (1.0, 0)], _XPAND_CELLS)


# ── 05 Rain ──────────────────────────────────────────

_RAIN_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0),   _CellAnim(990),  _CellAnim(360),  _CellAnim(1350), _CellAnim(630)],
    [_CellAnim(126), _CellAnim(1116), _CellAnim(486),  _CellAnim(1476), _CellAnim(756)],
    [_CellAnim(252), _CellAnim(1242), _CellAnim(612),  _CellAnim(1602), _CellAnim(882)],
    [_CellAnim(378), _CellAnim(1368), _CellAnim(738),  _CellAnim(1728), _CellAnim(1008)],
    [_CellAnim(504), _CellAnim(1494), _CellAnim(864),  _CellAnim(54),   _CellAnim(1134)],
]

def _pattern_rain(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1800,
        [(0, 0), (0.06, 1), (0.22, 0.10), (1.0, 0)], _RAIN_CELLS)


# ── 07 Loading ───────────────────────────────────────

_LOADING_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0), _CellAnim(125), _CellAnim(250), _CellAnim(375), _CellAnim(500)],
    [_CellAnim(1875), None, None, None, _CellAnim(625)],
    [_CellAnim(1750), None, None, None, _CellAnim(750)],
    [_CellAnim(1625), None, None, None, _CellAnim(875)],
    [_CellAnim(1500), _CellAnim(1375), _CellAnim(1250), _CellAnim(1125), _CellAnim(1000)],
]

def _pattern_loading(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2000,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _LOADING_CELLS)


# ── 09 Sparkle ───────────────────────────────────────

_SPARKLE_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0),    _CellAnim(2283), _CellAnim(1617), _CellAnim(1466), _CellAnim(31)],
    [_CellAnim(2106), _CellAnim(296),  _CellAnim(1206), _CellAnim(333),  _CellAnim(2241)],
    [_CellAnim(1929), _CellAnim(967),  _CellAnim(1238), _CellAnim(1004), _CellAnim(2252)],
    [_CellAnim(1955), _CellAnim(2517), _CellAnim(1139), _CellAnim(1076), _CellAnim(1362)],
    [_CellAnim(2132), _CellAnim(920),  _CellAnim(1274), _CellAnim(1310), _CellAnim(1019)],
]

def _pattern_sparkle(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2600,
        [(0, 0.05), (0.40, 0.05), (0.50, 1), (0.60, 0.05), (1.0, 0.05)], _SPARKLE_CELLS)


# ── 12 Diamond ───────────────────────────────────────

_DIAMOND_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(733), _CellAnim(550), _CellAnim(367), _CellAnim(550), _CellAnim(733)],
    [_CellAnim(550), _CellAnim(367), _CellAnim(183), _CellAnim(367), _CellAnim(550)],
    [_CellAnim(367), _CellAnim(183), _CellAnim(0),   _CellAnim(183), _CellAnim(367)],
    [_CellAnim(550), _CellAnim(367), _CellAnim(183), _CellAnim(367), _CellAnim(550)],
    [_CellAnim(733), _CellAnim(550), _CellAnim(367), _CellAnim(550), _CellAnim(733)],
]

def _pattern_diamond(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2200,
        [(0, 0), (0.10, 1), (0.55, 0.85), (1.0, 0)], _DIAMOND_CELLS)


# ── 16 Orbit ─────────────────────────────────────────

_ORBIT_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0), _CellAnim(150), _CellAnim(300), _CellAnim(450), _CellAnim(600)],
    [_CellAnim(2250), None, None, None, _CellAnim(750)],
    [_CellAnim(2100), None, None, None, _CellAnim(900)],
    [_CellAnim(1950), None, None, None, _CellAnim(1050)],
    [_CellAnim(1800), _CellAnim(1650), _CellAnim(1500), _CellAnim(1350), _CellAnim(1200)],
]

def _pattern_orbit(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2400,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _ORBIT_CELLS)


# ── 17 Twin Orbit ────────────────────────────────────

_TWIN_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0), _CellAnim(113), _CellAnim(225), _CellAnim(338), _CellAnim(450)],
    [_CellAnim(788), None, None, None, _CellAnim(563)],
    [_CellAnim(675), None, None, None, _CellAnim(675)],
    [_CellAnim(563), None, None, None, _CellAnim(788)],
    [_CellAnim(450), _CellAnim(338), _CellAnim(225), _CellAnim(113), _CellAnim(0)],
]

def _pattern_twin_orbit(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1800,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _TWIN_CELLS)


# ── 19 Thinking ──────────────────────────────────────

_THINKING_CELLS: list[list[_CellAnim | None]] = [[None] * 5 for _ in range(5)]
_THINKING_CELLS[1][1] = _CellAnim(1352)
_THINKING_CELLS[1][2] = _CellAnim(1197)
_THINKING_CELLS[1][3] = _CellAnim(823)
_THINKING_CELLS[2][1] = _CellAnim(1661)
_THINKING_CELLS[2][2] = _CellAnim(884)
_THINKING_CELLS[2][3] = _CellAnim(873)
_THINKING_CELLS[3][1] = _CellAnim(787)
_THINKING_CELLS[3][2] = _CellAnim(1280)
_THINKING_CELLS[3][3] = _CellAnim(1366)

def _pattern_thinking(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1800,
        [(0, 0.05), (0.30, 0.05), (0.40, 1), (0.55, 0.10), (1.0, 0.05)], _THINKING_CELLS)


# ── 23 Knight's Tour ─────────────────────────────────

_KT_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0),    _CellAnim(2538), _CellAnim(1986), _CellAnim(1434), _CellAnim(221)],
    [_CellAnim(1876), _CellAnim(1324), _CellAnim(110),  _CellAnim(883),  _CellAnim(2097)],
    [_CellAnim(2648), _CellAnim(772),  _CellAnim(2428), _CellAnim(331),  _CellAnim(1545)],
    [_CellAnim(1214), _CellAnim(1766), _CellAnim(552),  _CellAnim(2207), _CellAnim(993)],
    [_CellAnim(662),  _CellAnim(2317), _CellAnim(1103), _CellAnim(1655), _CellAnim(441)],
]

def _pattern_knights_tour(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 3200,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _KT_CELLS)


# ── 24 Lattice ───────────────────────────────────────

_LATTICE_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0), _CellAnim(1200), _CellAnim(0), _CellAnim(1200), _CellAnim(0)],
    [_CellAnim(1200), _CellAnim(0), _CellAnim(1200), _CellAnim(0), _CellAnim(1200)],
    [_CellAnim(0), _CellAnim(1200), _CellAnim(0), _CellAnim(1200), _CellAnim(0)],
    [_CellAnim(1200), _CellAnim(0), _CellAnim(1200), _CellAnim(0), _CellAnim(1200)],
    [_CellAnim(0), _CellAnim(1200), _CellAnim(0), _CellAnim(1200), _CellAnim(0)],
]

def _pattern_lattice(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2400,
        [(0, 0.08), (0.30, 0.85), (0.60, 0.12), (1.0, 0.08)], _LATTICE_CELLS)


# ── 28 Compile ───────────────────────────────────────

_COMPILE_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(960), _CellAnim(1056), _CellAnim(1152), _CellAnim(1248), _CellAnim(1344)],
    [_CellAnim(720), _CellAnim(816),  _CellAnim(912),  _CellAnim(1008), _CellAnim(1104)],
    [_CellAnim(480), _CellAnim(576),  _CellAnim(672),  _CellAnim(768),  _CellAnim(864)],
    [_CellAnim(240), _CellAnim(336),  _CellAnim(432),  _CellAnim(528),  _CellAnim(624)],
    [_CellAnim(0),   _CellAnim(96),   _CellAnim(192),  _CellAnim(288),  _CellAnim(384)],
]

def _pattern_compile(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2400,
        [(0, 0.08), (0.14, 1), (0.72, 0.95), (1.0, 0.08)], _COMPILE_CELLS)


# ── 36 Scatter ───────────────────────────────────────

_SCATTER_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(1399), _CellAnim(686),  _CellAnim(550),  _CellAnim(1149), _CellAnim(1016)],
    [_CellAnim(908),  _CellAnim(1089), _CellAnim(1087), _CellAnim(940),  _CellAnim(1305)],
    [_CellAnim(945),  _CellAnim(1104), _CellAnim(0),    _CellAnim(314),  _CellAnim(758)],
    [_CellAnim(1004), _CellAnim(827),  _CellAnim(838),  _CellAnim(656),  _CellAnim(726)],
    [_CellAnim(825),  _CellAnim(950),  _CellAnim(1209), _CellAnim(1180), _CellAnim(1118)],
]

def _pattern_scatter(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2200,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _SCATTER_CELLS)


# ── 39 Halt ──────────────────────────────────────────

_HALT_CELLS: list[list[_CellAnim | None]] = [[None] * 5 for _ in range(5)]
for r in range(1, 4):
    for c in range(1, 4):
        _HALT_CELLS[r][c] = _CellAnim(800) if (r == 2 and c == 2) else _CellAnim(0)

def _pattern_halt(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1600,
        [(0, 0.08), (0.14, 1), (0.72, 0.95), (1.0, 0.08)], _HALT_CELLS)


# ── 41 Needle ────────────────────────────────────────

_NEEDLE_CELLS: list[list[_CellAnim | None]] = [[None] * 5 for _ in range(5)]
_NEEDLE_CELLS[0][0] = _CellAnim(2100)
_NEEDLE_CELLS[0][2] = _CellAnim(0)
_NEEDLE_CELLS[0][4] = _CellAnim(300)
_NEEDLE_CELLS[1][1] = _CellAnim(2100)
_NEEDLE_CELLS[1][2] = _CellAnim(0)
_NEEDLE_CELLS[1][3] = _CellAnim(300)
_NEEDLE_CELLS[2][0] = _CellAnim(1800)
_NEEDLE_CELLS[2][1] = _CellAnim(1800)
_NEEDLE_CELLS[2][2] = _CellAnim(0)
_NEEDLE_CELLS[2][3] = _CellAnim(600)
_NEEDLE_CELLS[2][4] = _CellAnim(600)
_NEEDLE_CELLS[3][1] = _CellAnim(1500)
_NEEDLE_CELLS[3][2] = _CellAnim(1200)
_NEEDLE_CELLS[3][3] = _CellAnim(900)
_NEEDLE_CELLS[4][0] = _CellAnim(1500)
_NEEDLE_CELLS[4][2] = _CellAnim(1200)
_NEEDLE_CELLS[4][4] = _CellAnim(900)

def _pattern_needle(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2400,
        [(0, 0), (0.08, 1), (0.36, 0.05), (1.0, 0)], _NEEDLE_CELLS)


# ── 47 Quartet ───────────────────────────────────────

_QUARTET_CELLS: list[list[_CellAnim | None]] = [
    [_CellAnim(0), _CellAnim(400), _CellAnim(800), _CellAnim(1200), _CellAnim(0)],
    [_CellAnim(1200), None, None, None, _CellAnim(400)],
    [_CellAnim(800), None, None, None, _CellAnim(800)],
    [_CellAnim(400), None, None, None, _CellAnim(1200)],
    [_CellAnim(0), _CellAnim(1200), _CellAnim(800), _CellAnim(400), _CellAnim(0)],
]

def _pattern_quartet(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1600,
        [(0, 0), (0.04, 1), (0.26, 0.08), (1.0, 0)], _QUARTET_CELLS)


# ── 50 Equalizer ─────────────────────────────────────

_EQ_CELLS: list[list[_CellAnim | None]] = [[None] * 5 for _ in range(5)]
_EQ_CELLS[0][1] = _CellAnim(288, 1530)
_EQ_CELLS[1][1] = _CellAnim(216, 1530)
_EQ_CELLS[2][1] = _CellAnim(144, 1530)
_EQ_CELLS[3][1] = _CellAnim(72, 1530)
_EQ_CELLS[4][1] = _CellAnim(0, 1530)
_EQ_CELLS[0][2] = _CellAnim(888)
_EQ_CELLS[1][2] = _CellAnim(816)
_EQ_CELLS[2][2] = _CellAnim(744)
_EQ_CELLS[3][2] = _CellAnim(672)
_EQ_CELLS[4][2] = _CellAnim(600)
_EQ_CELLS[0][3] = _CellAnim(1488, 2070)
_EQ_CELLS[1][3] = _CellAnim(1416, 2070)
_EQ_CELLS[2][3] = _CellAnim(1344, 2070)
_EQ_CELLS[3][3] = _CellAnim(1272, 2070)
_EQ_CELLS[4][3] = _CellAnim(1200, 2070)

def _pattern_equalizer(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 1800,
        [(0, 0.08), (0.14, 1), (0.72, 0.95), (1.0, 0.08)], _EQ_CELLS)


# ── 52 Echo ──────────────────────────────────────────

_ECHO_CELLS: list[list[_CellAnim | None]] = [[_CellAnim(1733)] * 5 for _ in range(5)]
for r in range(1, 4):
    for c in range(1, 4):
        _ECHO_CELLS[r][c] = _CellAnim(867) if (r != 2 or c != 2) else _CellAnim(0)

def _pattern_echo(frame: int) -> list[list[float]]:
    return _sample_alpha(frame, 2600,
        [(0, 0.10), (0.20, 1), (0.60, 0.20), (1.0, 0.10)], _ECHO_CELLS)


# ── Pattern registry ─────────────────────────────────

_PATTERNS: dict[str, Callable[[int], list[list[float]]]] = {
    "wave": _pattern_wave,
    "cross_expand": _pattern_cross_expand,
    "rain": _pattern_rain,
    "loading": _pattern_loading,
    "sparkle": _pattern_sparkle,
    "diamond": _pattern_diamond,
    "orbit": _pattern_orbit,
    "twin_orbit": _pattern_twin_orbit,
    "thinking": _pattern_thinking,
    "knights_tour": _pattern_knights_tour,
    "lattice": _pattern_lattice,
    "compile": _pattern_compile,
    "scatter": _pattern_scatter,
    "halt": _pattern_halt,
    "needle": _pattern_needle,
    "quartet": _pattern_quartet,
    "equalizer": _pattern_equalizer,
    "echo": _pattern_echo,
}


class DotMatrixWidget(QWidget):
    """Rounded square with a centered 5×5 animated dot grid.
    Uses two-layer rendering: small dim background dots + larger animated foreground dots
    with continuous alpha from the SVG's CSS animation model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._style = _STYLES["idle"]
        self._visual_key = "idle"
        self._pattern_name = ""
        self._pattern_frame = 0
        self._idle_remaining = 0
        self._alpha = _zero_grid()
        self._pick_idle_pattern()

        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._style.interval_ms)

    def _pick_idle_pattern(self):
        pool = _STATE_POOLS["idle"]
        self._pattern_name = random.choice(pool)
        self._pattern_frame = 0
        self._idle_remaining = random.randint(_IDLE_HOLD_MIN, _IDLE_HOLD_MAX)
        self._alpha = _PATTERNS[self._pattern_name](0)

    def set_visual_state(self, state: str):
        style = _STYLES.get(state, _STYLES["idle"])
        if state == self._visual_key:
            self._style = style
            self.update()
            return
        family_new = _STATE_FAMILIES.get(state, "other")
        family_old = _STATE_FAMILIES.get(self._visual_key, "other")
        if family_old != family_new:
            pool = _STATE_POOLS.get(state, _STATE_POOLS["idle"])
            self._pattern_name = random.choice(pool)
            self._pattern_frame = 0
            self._alpha = _PATTERNS[self._pattern_name](0)
            if state == "idle":
                self._idle_remaining = random.randint(_IDLE_HOLD_MIN, _IDLE_HOLD_MAX)
        self._visual_key = state
        self._style = style
        self._timer.setInterval(style.interval_ms)
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def _tick(self):
        self._alpha = _PATTERNS[self._pattern_name](self._pattern_frame)
        self._pattern_frame += 1
        if self._visual_key == "idle":
            self._idle_remaining -= 1
            if self._idle_remaining <= 0:
                self._pick_idle_pattern()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        radius = 6.0
        inset = int(max(6, min(w, h) * 0.15))
        pitch = (w - 2 * inset) // (GRID - 1) if GRID > 1 else 0
        bg_dot_r = max(1.2, pitch * 0.20)
        fg_dot_r = max(2.0, pitch * 0.30)

        bg = QColor(self._style.bg_color)
        border = QColor(self._style.border_color)
        painter.setPen(QPen(border, self._style.border_width))
        painter.setBrush(bg)
        painter.drawRoundedRect(0.5, 0.5, w - 1, h - 1, radius, radius)

        on_c = QColor(self._style.on_color)
        off_brush = QBrush(QColor(self._style.off_color))
        fg_brush = QBrush(on_c)
        use_fg = fg_dot_r > 0 and fg_dot_r != bg_dot_r

        for r in range(GRID):
            for c in range(GRID):
                cx = inset + c * pitch
                cy = inset + r * pitch

                # Background dot (small, always visible)
                painter.setPen(Qt.NoPen)
                painter.setBrush(off_brush)
                painter.drawEllipse(QPointF(cx, cy), bg_dot_r, bg_dot_r)

                # Foreground dot (larger, with animated alpha)
                alpha = self._alpha[r][c]
                if use_fg and alpha > 0.01:
                    on_c.setAlphaF(min(1.0, alpha))
                    fg_brush.setColor(on_c)
                    painter.setBrush(fg_brush)
                    painter.drawEllipse(QPointF(cx, cy), fg_dot_r, fg_dot_r)

        painter.end()
