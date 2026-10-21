"""Minimal stand-in for ``streamlit`` (and ``altair``) to execute page logic.

This is NOT a rendering test: it only runs every page script top to bottom
against the real evidence, with widgets returning their defaults (or values
preset in the session state), so data-access and arithmetic errors surface
without a browser. Every ``st.dataframe`` payload is converted with pyarrow
the way Streamlit serialises it, so a column Streamlit could not send is
reported. The real Streamlit smoke test is test_app_smoke.py (AppTest).
"""
from __future__ import annotations

import contextlib
import runpy
import sys
import types
from pathlib import Path
from unittest import mock

import pandas as pd
import pyarrow as pa


class StopPage(Exception):
    """st.stop() / st.rerun() inside a stub run."""


class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v


class Recorder:
    def __init__(self, presses=(), state=None):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.widgets: dict[str, str] = {}
        self.presses = set(presses)
        self.state = SessionState(state or {})
        self.arrow_errors: list[str] = []


def _container(rec: Recorder, mod) -> object:
    c = types.SimpleNamespace()
    for name in dir(mod):
        if not name.startswith("_"):
            setattr(c, name, getattr(mod, name))
    c.__enter__ = lambda *a: c
    c.__exit__ = lambda *a: False
    return _Ctx(c)


class _Ctx:
    def __init__(self, ns):
        self._ns = ns

    def __getattr__(self, k):
        return getattr(self._ns, k)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_streamlit(rec: Recorder) -> types.ModuleType:
    st = types.ModuleType("streamlit")
    st.session_state = rec.state

    def _record(name):
        def f(*a, **k):
            rec.calls.append((name, a, k))
        return f

    for n in ("set_page_config", "markdown", "caption", "title", "subheader", "header",
              "write", "info", "warning", "error", "success", "code", "latex", "metric",
              "image", "altair_chart", "divider", "json", "toast"):
        setattr(st, n, _record(n))

    def dataframe(data, *a, **k):
        rec.calls.append(("dataframe", (data,), k))
        df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        try:
            pa.Table.from_pandas(df)
        except Exception as e:  # what Streamlit's arrow serialisation would hit
            rec.arrow_errors.append(f"{list(df.columns)}: {e}")
    st.dataframe = dataframe

    def _widget(kind, key, label):
        rec.widgets[key or label] = kind

    def selectbox(label, options, index=0, format_func=str, key=None, **k):
        opts = list(options)
        _widget("selectbox", key, label)
        for o in opts:
            format_func(o)
        if not opts:
            return None
        v = rec.state.get(key, opts[index]) if key else opts[index]
        v = v if v in opts else opts[index]
        if key:
            rec.state[key] = v
        return v
    st.selectbox = selectbox
    st.radio = selectbox

    def number_input(label, min_value=None, max_value=None, value="min", step=None,
                     key=None, **k):
        _widget("number_input", key, label)
        if value == "min":
            value = min_value if min_value is not None else 0
        v = rec.state.get(key, value) if key else value
        if min_value is not None and v < min_value:
            raise ValueError(f"{key}: {v} below min {min_value}")
        if max_value is not None and v > max_value:
            raise ValueError(f"{key}: {v} above max {max_value}")
        if key:
            rec.state[key] = v
        return v
    st.number_input = number_input

    def slider(label, min_value=None, max_value=None, value=None, step=None, key=None, **k):
        _widget("slider", key, label)
        if min_value is not None and max_value is not None and not (min_value <= max_value):
            raise ValueError("slider min > max")
        v = rec.state.get(key, value) if key else value
        if key:
            rec.state[key] = v
        return v
    st.slider = slider

    def text_input(label, value="", key=None, **k):
        _widget("text_input", key, label)
        v = rec.state.get(key, value) if key else value
        if key:
            rec.state[key] = v
        return v
    st.text_input = text_input

    def toggle(label, value=False, key=None, **k):
        _widget("toggle", key, label)
        v = rec.state.get(key, value) if key else value
        if key:
            rec.state[key] = v
        return v
    st.toggle = toggle
    st.checkbox = toggle

    def button(label, key=None, on_click=None, args=(), kwargs=None, **k):
        _widget("button", key, label)
        if (key or label) in rec.presses:
            rec.presses.discard(key or label)
            if on_click:
                on_click(*args, **(kwargs or {}))
            return True
        return False
    st.button = button

    def columns(spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_container(rec, st) for _ in range(n)]
    st.columns = columns

    def tabs(names):
        return [_container(rec, st) for _ in names]
    st.tabs = tabs

    for n in ("expander", "container", "spinner", "empty", "popover", "form"):
        setattr(st, n, lambda *a, **k: _container(rec, st))

    class _Cache:
        def __call__(self, func=None, **k):
            if func is None:
                return lambda f: f
            return func

        def clear(self):
            pass
    st.cache_data = _Cache()
    st.cache_resource = _Cache()

    def fragment(func=None, *, run_every=None):
        rec.calls.append(("fragment", (), {"run_every": run_every}))
        return func if func is not None else (lambda f: f)
    st.fragment = fragment
    st.column_config = mock.MagicMock(name="column_config")

    def stop():
        raise StopPage("stop")
    st.stop = stop

    def rerun(*a, **k):
        raise StopPage("rerun")
    st.rerun = rerun

    class Page:
        def __init__(self, page, title=None, default=False, url_path=None, **k):
            self.page, self.title, self.default, self.url_path = page, title, default, url_path
    st.Page = Page

    class _Nav:
        def __init__(self, pages):
            self.pages = pages

        def run(self):
            page = next(p for p in self.pages if p.default)
            runpy.run_path(str(Path(sys.argv[0]).parent / page.page), run_name="__main__")
    st.navigation = lambda pages, **k: _Nav(pages)
    st.sidebar = _container(rec, st)
    return st


@contextlib.contextmanager
def stubbed(rec: Recorder):
    saved = {k: sys.modules.get(k) for k in ("streamlit", "altair", "ui")}
    sys.modules["streamlit"] = make_streamlit(rec)
    sys.modules["altair"] = mock.MagicMock(name="altair")
    sys.modules.pop("ui", None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def run_page(script: Path, presses=(), state=None) -> Recorder:
    """Execute one page script with the stub; returns the recorder."""
    rec = Recorder(presses, state)
    argv = sys.argv
    with stubbed(rec):
        sys.argv = [str(script)]
        try:
            runpy.run_path(str(script), run_name="__main__")
        except StopPage:
            pass
        finally:
            sys.argv = argv
    return rec
