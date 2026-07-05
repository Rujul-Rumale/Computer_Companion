import sys
sys.path.insert(0, '.')

from ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
win = MainWindow()
# Test the _should_capture_screen method
test_cases = [
    "what's on my screen",
    "what is on my screen",
    "what do you see on my screen",
    "look at my screen",
    "analyze my screen",
    "screen capture",
    "what's the weather",
]
for t in test_cases:
    result = win._should_capture_screen(t)
    print(f'{result}: "{t}"')