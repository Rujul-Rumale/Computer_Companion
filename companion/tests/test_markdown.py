from ui.markdown import md_to_html


def test_bold():
    r = md_to_html("this is **bold** text")
    assert "<b>bold</b>" in r


def test_italic():
    r = md_to_html("this is *italic* text")
    assert "<i>italic</i>" in r


def test_inline_code():
    r = md_to_html("use `print(x)` here")
    assert "<code>print(x)</code>" in r


def test_code_block():
    code_text = "before\n```\ndef foo():\n    pass\n```\nafter"
    r = md_to_html(code_text)
    assert "<pre" in r


def test_link():
    r = md_to_html("click [here](https://x.com)")
    assert "href=" in r


def test_empty():
    assert md_to_html("") == ""


def test_plain_text():
    r = md_to_html("hello world")
    assert "hello world" in r


def test_newlines():
    r = md_to_html("line1\n\nline2")
    assert "line1" in r and "line2" in r


def test_combined():
    r = md_to_html("**bold** and `code` and *italic*")
    assert "<b>bold</b>" in r
    assert "<code>code</code>" in r
    assert "<i>italic</i>" in r
