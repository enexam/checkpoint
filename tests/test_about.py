"""Tests for about.py — build_issue_url, data_dir, and __version__."""
import platform
import urllib.parse
from pathlib import Path


def test_version_is_0_0_0():
    import checkpoint
    assert checkpoint.__version__ == "0.0.0"


def test_build_issue_url_bug_contains_issues_new():
    from checkpoint.about import build_issue_url
    url = build_issue_url("bug")
    assert "issues/new" in url


def test_build_issue_url_bug_has_bug_label():
    from checkpoint.about import build_issue_url
    url = build_issue_url("bug")
    assert "labels=bug" in url


def test_build_issue_url_bug_title_starts_with_bug_prefix():
    from checkpoint.about import build_issue_url
    url = build_issue_url("bug")
    # The query string is urlencoded; unquote to check the raw title.
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    title = params["title"][0]
    assert title.startswith("[Bug]")


def test_build_issue_url_bug_body_contains_version():
    from checkpoint.about import build_issue_url
    import checkpoint
    url = build_issue_url("bug")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    body = params["body"][0]
    assert checkpoint.__version__ in body


def test_build_issue_url_bug_body_contains_os():
    from checkpoint.about import build_issue_url
    url = build_issue_url("bug")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    body = params["body"][0]
    assert platform.platform() in body


def test_build_issue_url_bug_body_contains_python_version():
    from checkpoint.about import build_issue_url
    url = build_issue_url("bug")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    body = params["body"][0]
    assert platform.python_version() in body


def test_build_issue_url_feature_has_enhancement_label():
    from checkpoint.about import build_issue_url
    url = build_issue_url("feature")
    assert "labels=enhancement" in url


def test_build_issue_url_feature_title_starts_with_feature_prefix():
    from checkpoint.about import build_issue_url
    url = build_issue_url("feature")
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    title = params["title"][0]
    assert title.startswith("[Feature]")


def test_build_issue_url_feature_contains_issues_new():
    from checkpoint.about import build_issue_url
    url = build_issue_url("feature")
    assert "issues/new" in url


def test_data_dir_returns_path_ending_in_checkpoint():
    from checkpoint.about import data_dir
    result = data_dir()
    assert isinstance(result, Path)
    assert result.name == "Checkpoint"


def test_build_about_tab_renders_without_error(_tk_session_root):
    """build_about_tab must not raise during construction."""
    from tkinter import ttk
    from checkpoint.about import build_about_tab
    frame = ttk.Frame(_tk_session_root)
    build_about_tab(frame)
    _tk_session_root.update()
    frame.destroy()
