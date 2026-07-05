from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    state_changed = Signal(str)
    connection_changed = Signal(str)
    mode_changed = Signal(str)
    user_message_sent = Signal(str)
    assistant_token = Signal(str)
    assistant_done = Signal(str)
    sentence_complete = Signal(str)
    tool_executed = Signal(str, bool)
    speaking_changed = Signal(bool)
    error_occurred = Signal(str)
    metrics_updated = Signal(dict)
    interruption_requested = Signal()
    audio_level = Signal(float)
    stop_requested = Signal()
    window_context_changed = Signal(dict)
    mic_muted_changed = Signal(bool)
    dock_toggle_requested = Signal()
    quit_requested = Signal()
    show_control_panel_requested = Signal()


_signals_instance = None


def get_signals() -> AppSignals:
    global _signals_instance
    if _signals_instance is None:
        _signals_instance = AppSignals()
    return _signals_instance
