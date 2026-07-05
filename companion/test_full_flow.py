import sys
sys.path.insert(0, '.')

# Test the full dispatch flow
from ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from adapters.tool_runner import get_tool_runner
import time

app = QApplication.instance() or QApplication([])
win = MainWindow()

text = "what's on my screen"
print(f"=== Testing dispatch for: '{text}' ===")

# 1. _assistant_responding check
print(f"1. _assistant_responding: {win._assistant_responding}")

# 2. Mode command check
mode_cmd = win._sm.detect_mode_command(text)
print(f"2. Mode command: '{mode_cmd}'")

# 3. Should capture screen
should_capture = win._should_capture_screen(text)
print(f"3. Should capture: {should_capture}")

# 4. Screenshot tool
result = get_tool_runner().run("take_screenshot", {}, require_confirmation=False)
print(f"4. Screenshot: success={result.success}, path={result.data.get('path') if result.data else None}")

# 5. Simulate what _dispatch_message does
image_path = result.data.get("path") if result.success else None
print(f"5. image_path: {image_path}")

# 6. Check active window tracker
active_window_info = None
if win._active_window_tracker and win.cfg.track_active_window:
    active_window_info = win._active_window_tracker.current
print(f"6. Active window: {active_window_info}")

# 7. Now create the LLMWorker
from ui.main_window import LLMWorker
worker = LLMWorker(win.conv, text, win._sm.mode_config, image_path, active_window_info, [])
print(f"7. LLMWorker created")

# 8. Start worker
print(f"8. Starting worker...")
win._thread_pool.start(worker)

# Give it time to process
time.sleep(2)
print("Done")