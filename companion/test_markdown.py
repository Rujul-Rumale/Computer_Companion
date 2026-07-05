"""
Quick test for markdown converter.
Run: .venv/Scripts/python test_markdown.py
"""
import sys; sys.path.insert(0, '.')
from ui.markdown import md_to_html

# Test 1: bold
r = md_to_html('this is **bold** text')
assert '<b>bold</b>' in r, f'bold failed: {r}'
print('OK bold')

# Test 2: italic
r = md_to_html('this is *italic* text')
assert '<i>italic</i>' in r, f'italic failed: {r}'
print('OK italic')

# Test 3: inline code
r = md_to_html('use `print(x)` here')
assert '<code>print(x)</code>' in r, f'inline code failed: {r}'
print('OK inline code')

# Test 4: code block
code_text = 'before\n```\ndef foo():\n    pass\n```\nafter'
r = md_to_html(code_text)
assert '<pre' in r, f'code block failed: {r}'
print('OK code block')

# Test 5: link
r = md_to_html('click [here](https://x.com)')
assert 'href=' in r, f'link failed: {r}'
print('OK link')

# Test 6: empty
assert md_to_html('') == '', 'empty failed'
print('OK empty')

# Test 7: plain text
r = md_to_html('hello world')
assert 'hello world' in r, f'plain failed: {r}'
print('OK plain')

# Test 8: newlines
r = md_to_html('line1\n\nline2')
assert 'line1' in r and 'line2' in r, f'newlines failed: {r}'
print('OK newlines')

# Test 9: combined
r = md_to_html('**bold** and `code` and *italic*')
assert '<b>bold</b>' in r and '<code>code</code>' in r and '<i>italic</i>' in r, f'combined failed: {r}'
print('OK combined')

print('All tests passed')
