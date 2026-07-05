C_BG        = "#0d0f12"
C_BG2       = "#12151a"
C_PANEL     = "#161a21"
C_BORDER    = "#232830"
C_BORDER2   = "#2d333d"
C_TEXT      = "#c9d1d9"
C_TEXT_DIM  = "#5c6370"
C_TEXT_MID  = "#7d8590"
C_ACCENT    = "#4d8fea"
C_ACCENT2   = "#1a5cc8"
C_GREEN     = "#2ea043"
C_ORANGE    = "#d1862a"
C_RED       = "#da3633"
C_YELLOW    = "#b08800"
C_PURPLE    = "#a371f7"

# Dot-matrix tile (extra-dark)
M_BG        = "#080a0d"
M_OFF       = "#12151b"
M_BORDER    = "#1a1f28"
M_IDLE_ON   = "#6e7681"

STATE_COLORS = {
    "READY":       C_TEXT_DIM,
    "LISTENING":   C_GREEN,
    "TRANSCRIBING": C_YELLOW,
    "THINKING":    C_ACCENT,
    "TOOL_USE":    C_ORANGE,
    "SPEAKING":    C_PURPLE,
    "ERROR":       C_RED,
}

MODE_COLORS = {
    "default":   C_TEXT_DIM,
    "think":     C_ACCENT,
    "brainstorm": C_PURPLE,
}


def state_display(s: str) -> str:
    return {
        "READY": "Ready",
        "LISTENING": "Listening",
        "TRANSCRIBING": "Understanding",
        "THINKING": "Thinking",
        "TOOL_USE": "Using Tool",
        "SPEAKING": "Speaking",
        "ERROR": "Error",
    }.get(s, s)


def connection_display(s: str) -> str:
    return {
        "CONNECTING": "Connecting...",
        "READY": "Online",
        "OFFLINE": "Offline",
    }.get(s, s)
