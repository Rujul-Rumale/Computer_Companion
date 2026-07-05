import math

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ui.theme import C_RED, C_TEXT_DIM, STATE_COLORS


class AssistantOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "READY"
        self._t = 0.0
        self._spin = 0.0
        self._pulse = 0.0
        self.setMinimumSize(24, 24)
        self.setMaximumSize(160, 160)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, state: str):
        self._state = (state or "READY").upper()

    def _tick(self):
        self._t += 0.05
        self._spin = (self._spin + 0.06) % (2 * math.pi)
        self._pulse = 0.5 + 0.5 * math.sin(self._t * 2.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        r = min(w, h) / 2.0
        accent = QColor(STATE_COLORS.get(self._state, C_RED if self._state == "ERROR" else C_TEXT_DIM))

        if self._state == "READY":
            self._draw_ready(painter, cx, cy, r, accent)
        elif self._state == "LISTENING":
            self._draw_listening(painter, cx, cy, r, accent)
        elif self._state == "TRANSCRIBING":
            self._draw_transcribing(painter, cx, cy, r, accent)
        elif self._state == "THINKING":
            self._draw_thinking(painter, cx, cy, r, accent)
        elif self._state == "TOOL_USE":
            self._draw_tool_use(painter, cx, cy, r, accent)
        elif self._state == "SPEAKING":
            self._draw_speaking(painter, cx, cy, r, accent)
        else:
            self._draw_error(painter, cx, cy, r)

        painter.end()

    def _draw_ready(self, painter, cx, cy, r, accent):
        core_r = r * 0.35
        glow_r = r * 0.7 + 2 * self._pulse
        c = QColor(accent)
        c.setAlphaF(0.08 + 0.06 * self._pulse)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        pen_c = QColor(accent)
        pen_c.setAlphaF(0.15 + 0.1 * self._pulse)
        pen = QPen(pen_c, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), core_r * 1.6, core_r * 1.6)

        grad = QRadialGradient(cx, cy, core_r)
        grad.setColorAt(0, QColor("#ffffff"))
        grad.setColorAt(0.4, QColor(accent))
        c2 = QColor(accent)
        c2.setAlphaF(0.15)
        grad.setColorAt(1, c2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

    def _draw_listening(self, painter, cx, cy, r, accent):
        for i in range(3):
            phase = (self._t + i * 1.2) % (2 * math.pi)
            ring_r = r * (0.3 + 0.2 * (1 + math.sin(phase)) / 2)
            c = QColor(accent)
            alpha = int(30 + 40 * (1 + math.sin(phase)) / 2)
            c.setAlpha(alpha)
            painter.setPen(QPen(c, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        core_r = r * 0.3 + 2 * self._pulse
        glow_r = core_r + 4
        c = QColor(accent)
        c.setAlphaF(0.12 + 0.08 * self._pulse)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        grad = QRadialGradient(cx, cy, core_r)
        grad.setColorAt(0, QColor("#ffffff"))
        grad.setColorAt(0.6, QColor(accent))
        c2 = QColor(accent)
        c2.setAlphaF(0.1)
        grad.setColorAt(1, c2)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

    def _draw_transcribing(self, painter, cx, cy, r, accent):
        painter.save()
        painter.translate(cx, cy)
        arc_r = r * 0.55
        start = -self._spin * 4.0
        span = 90 + 60 * (0.5 + 0.5 * math.sin(self._t * 1.5))

        pen_c = QColor(accent)
        pen_c.setAlphaF(0.6)
        pen = QPen(pen_c, 2.5, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(int(-arc_r), int(-arc_r), int(2 * arc_r), int(2 * arc_r),
                        int(start * 16), int(span * 16))

        pen_c.setAlphaF(0.15)
        pen.setColor(pen_c)
        painter.setPen(pen)
        painter.drawArc(int(-arc_r), int(-arc_r), int(2 * arc_r), int(2 * arc_r),
                        int((start + 180) * 16), int(span * 16))

        grad = QRadialGradient(0, 0, r * 0.2)
        grad.setColorAt(0, QColor(accent))
        c = QColor(accent)
        c.setAlphaF(0.08)
        grad.setColorAt(1, c)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), r * 0.2, r * 0.2)
        painter.restore()

    def _draw_thinking(self, painter, cx, cy, r, accent):
        # Elegant pulsing ring with a slow-rotating arc
        pulse = 0.5 + 0.5 * math.sin(self._t * 1.2)
        painter.save()
        painter.translate(cx, cy)
        # Outer breathing ring
        ring_r = r * 0.55
        c = QColor(accent)
        c.setAlphaF(0.1 + 0.08 * pulse)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(0, 0), ring_r, ring_r)
        # Rotating arc
        pen_c = QColor(accent)
        pen_c.setAlphaF(0.4 + 0.2 * pulse)
        pen = QPen(pen_c, 2, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        angle = self._spin * 30.0
        span = 120 + 60 * pulse
        painter.drawArc(int(-ring_r), int(-ring_r), int(2 * ring_r), int(2 * ring_r),
                        int(-angle * 16), int(span * 16))
        # Inner subtle core
        core_r = r * 0.15 + 2 * pulse
        grad = QRadialGradient(0, 0, core_r)
        grad.setColorAt(0, accent)
        c2 = QColor(accent)
        c2.setAlphaF(0.1)
        grad.setColorAt(1, c2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), core_r, core_r)
        painter.restore()

    def _draw_tool_use(self, painter, cx, cy, r, accent):
        painter.save()
        painter.translate(cx, cy)
        n = 6
        for i in range(n):
            a = self._spin + 2 * math.pi * i / n
            inner = r * 0.15
            outer = r * 0.55
            x1 = inner * math.cos(a)
            y1 = inner * math.sin(a)
            x2 = outer * math.cos(a)
            y2 = outer * math.sin(a)
            c = QColor(accent)
            bright = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self._t * 3.0 + i * 1.0))
            c.setAlphaF(bright)
            painter.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        ring_r = r * 0.55
        c = QColor(accent)
        c.setAlphaF(0.08 + 0.06 * math.sin(self._t * 2.0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(0, 0), ring_r, ring_r)
        painter.restore()

    def _draw_speaking(self, painter, cx, cy, r, accent):
        painter.save()
        painter.translate(cx, cy)
        n = 5
        for i in range(n):
            a = -math.pi / 2 + 2 * math.pi * i / n
            spread = r * 0.55
            wave = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(self._t * 2.5 - i * 0.8))
            px = spread * math.cos(a) * wave
            py = spread * math.sin(a) * wave
            size = 2.5 + 4 * wave
            c = QColor(accent)
            c.setAlphaF(0.5 + 0.5 * wave)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(QPointF(px, py), size, size)

        core = QColor(accent)
        core.setAlphaF(0.3 + 0.3 * self._pulse)
        painter.setPen(Qt.NoPen)
        painter.setBrush(core)
        painter.drawEllipse(QPointF(0, 0), r * 0.15, r * 0.15)
        painter.restore()

    def _draw_error(self, painter, cx, cy, r):
        pulse = 0.5 + 0.5 * math.sin(self._t * 4.0)
        glitch = 0
        if hasattr(self, '_t') and pulse > 0.8:
            import random
            glitch = random.uniform(-1.5, 1.5)

        painter.save()
        painter.translate(cx + glitch, cy)
        glow_r = r * 0.7 + 4 * pulse
        c = QColor(C_RED)
        c.setAlphaF(0.08 + 0.08 * pulse)
        painter.setPen(Qt.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(0, 0), glow_r, glow_r)

        grad = QRadialGradient(0, 0, r * 0.3)
        grad.setColorAt(0, QColor(C_RED))
        c = QColor(C_RED)
        c.setAlphaF(0.2)
        grad.setColorAt(1, c)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(0, 0), r * 0.3, r * 0.3)

        painter.setPen(QPen(QColor("#111"), 2.5, Qt.SolidLine, Qt.RoundCap))
        s = r * 0.2
        painter.drawLine(QPointF(-s, -s), QPointF(s, s))
        painter.drawLine(QPointF(s, -s), QPointF(-s, s))
        painter.restore()

    def sizeHint(self):
        return self.minimumSize()
