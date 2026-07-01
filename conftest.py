"""Pytest environment shim.

On this machine the global temp dir (``C:\\Users\\david\\AppData\\Local\\Temp\\
pytest-of-david``) is ACL-locked and raises ``PermissionError [WinError 5]``
when pytest's ``tmp_path`` fixture tries to scan it. Redirect the temp base to
a writable, repo-local directory before pytest computes its basetemp so
``tmp_path``-based tests (e.g. market_sim/tests/test_run.py) work out of the box.

This only affects the test session's temp location; it does not touch product
code or the on-disk config.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

_tmp = pathlib.Path(__file__).resolve().parent / ".pytest_tmp"
_tmp.mkdir(exist_ok=True)
for _var in ("TMP", "TEMP", "TMPDIR"):
    os.environ[_var] = str(_tmp)
# tempfile caches the temp dir on first use, so override it directly too —
# this is what pytest's basetemp is derived from.
tempfile.tempdir = str(_tmp)
