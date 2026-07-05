import sys
sys.path.insert(0, '.')

from ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
win = MainWindow()

# Now let's trace what _dispatch_message does with "what's on my screen"
# We'll trace step by step

text = "what's on my screen"
print(f"Input: {text}")

# Step 1: Check _assistant_responding
print(f"_assistant_responding: {win._assistant_responding}")

# Step 2: Mode command check
mode_cmd = win._sm.detect_mode_command(text)
print(f"Mode command detected: '{mode_cmd}'")

# Step 3: Should capture screen
should_capture = win._should_capture_screen(text)
print(f"Should capture screen: {should_capture}")

# Step 4: If should capture, what does the tool return
from tools import execute_tool
result = execute_tool("take_screenshot", {})
print(f"Screenshot tool result: {result.success}, path={result.data.get('path') if result.data else None}")

# Step 5: What would be the image_path?
if result.success:
    image_path = result.data.get("path")
    print(f"Image path that would be sent: {image_path}")