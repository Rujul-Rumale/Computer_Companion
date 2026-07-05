import sys
sys.path.insert(0, '.')

from tools import execute_tool

result = execute_tool("take_screenshot", {})
print(f"Success: {result.success}")
print(f"Message: {result.message}")
if result.data:
    print(f"Data: {result.data}")