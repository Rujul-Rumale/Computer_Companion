import sys, base64, os
sys.path.insert(0, '.')
from ai.llm_client import ConversationManager
from tools import execute_tool

# Take screenshot
result = execute_tool('take_screenshot', {})
if not result.success:
    print(f"Screenshot failed: {result.message}")
    sys.exit(1)

path = result.data['path']
print(f'Screenshot: {path} ({os.path.getsize(path)} bytes)')

# Read and encode
with open(path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
print(f'Base64 length: {len(b64)} chars')
print(f'Estimated tokens: {len(b64) // 4}')

# Now try LLM with vision
conv = ConversationManager()
print('Sending vision request to llama...')
tokens = []
try:
    for token in conv.chat_stream('What do you see in this image?', image_path=path):
        tokens.append(token)
        print(token, end='', flush=True)
    print()
    full = "".join(tokens)
    print(f'Response ({len(full)} chars): {full[:200]}...')
except Exception as e:
    print(f'LLM ERROR: {e}')
    import traceback
    traceback.print_exc()
