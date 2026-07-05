import sys
sys.path.insert(0, '.')

from tools import execute_tool
from adapters import get_attachment_processor

# Test screenshot + attachment
result = execute_tool("take_screenshot", {})
print(f"Screenshot: {result.message}")

if result.success and result.data.get("path"):
    processor = get_attachment_processor()
    summary = processor.summarize_path(result.data["path"])
    print(f"Attachment summary: kind={summary.kind}, display={summary.display_name}")
    if summary.image_payload:
        print(f"Image payload length: {len(summary.image_payload)}")
    else:
        print("No image payload!")