from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from memory import get_all_facts, get_projects, get_recent_summaries
from ui.theme import C_ACCENT, C_BG2, C_BORDER, C_BORDER2, C_TEXT, C_TEXT_DIM, C_TEXT_MID


class MemoryDrawer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = True
        self._collapsed_width = 28
        self._expanded_width = 260
        self.setFixedWidth(self._collapsed_width)
        self._setup_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(15000)

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_BG2};
                border-left: 1px solid {C_BORDER};
            }}
            QListWidget {{
                background: {C_BG2}; color: {C_TEXT};
                border: 1px solid {C_BORDER};
                font-family: Consolas; font-size: 10px;
                border-radius: 2px;
            }}
            QListWidget::item {{ padding: 2px 4px; }}
            QListWidget::item:selected {{ background: {C_BORDER2}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        self._toggle_btn = QPushButton("MEM")
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_ACCENT};
                border: 1px solid {C_BORDER}; border-radius: 2px;
                text-align: left; padding: 4px 8px;
                font-family: Consolas; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_BORDER2}; }}
        """)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content.setVisible(False)
        content_layout = QVBoxLayout(self._content)
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._session_label = QLabel("SESSION")
        self._session_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; font-weight: bold; margin-top: 4px;")
        content_layout.addWidget(self._session_label)
        self._project_label = QLabel()
        self._task_label = QLabel()
        self._topic_label = QLabel()
        for lbl in [self._project_label, self._task_label, self._topic_label]:
            lbl.setStyleSheet(f"color: {C_TEXT_MID}; font-family: Consolas; font-size: 10px; padding-left: 4px;")
            lbl.setWordWrap(True)
            content_layout.addWidget(lbl)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C_BORDER}; margin: 4px 0;")
        content_layout.addWidget(sep)

        self._long_term_label = QLabel("LONG TERM")
        self._long_term_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; font-weight: bold;")
        content_layout.addWidget(self._long_term_label)
        self._facts_label = QLabel()
        self._facts_label.setStyleSheet(f"color: {C_TEXT_MID}; font-family: Consolas; font-size: 10px; padding-left: 4px;")
        content_layout.addWidget(self._facts_label)

        self._projects_list = QListWidget()
        self._projects_list.setFixedHeight(80)
        content_layout.addWidget(self._projects_list)

        self._summaries_list = QListWidget()
        self._summaries_list.setFixedHeight(60)
        content_layout.addWidget(self._summaries_list)

        content_layout.addStretch()
        layout.addWidget(self._content)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("<<" if not self._collapsed else "MEM")
        self.setFixedWidth(self._expanded_width if not self._collapsed else self._collapsed_width)

    def update_session(self, project=None, task="", topic=""):
        self._project_label.setText(f"Project: {project['name'] if project else '—'}")
        self._task_label.setText(f"Task: {task or '—'}")
        self._topic_label.setText(f"Topic: {topic or '—'}")

    def _refresh(self):
        self._projects_list.clear()
        for p in get_projects(status="active"):
            self._projects_list.addItem(f"{p['name']}: {p['description'][:40]}")

        facts = get_all_facts()
        self._facts_label.setText(f"Saved facts: {len(facts)}")

        self._summaries_list.clear()
        for s in get_recent_summaries(limit=3):
            self._summaries_list.addItem(f"{s['created_at'][:10]} {s['summary'][:50]}")
