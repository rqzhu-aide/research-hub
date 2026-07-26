"""Shared filesystem security helpers.

This module intentionally depends only on the standard library (``os``,
``stat``) so that every other module — including ``hub.py`` and
``core/launch_common.py`` — can import from it without creating circular
dependencies.
"""

from __future__ import annotations

import logging
import os
import stat

log = logging.getLogger(__name__)


def metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Recognize POSIX symlinks and Windows reparse points.

    Returns ``True`` when *metadata* (obtained via ``Path.lstat()`` or
    ``Path.stat()``) indicates a symbolic link on POSIX or a reparse
    point on Windows.  The check is used throughout the codebase to
    reject symlinks and junctions that could escape a safe directory.
    """

    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(
        stat,
        "FILE_ATTRIBUTE_REPARSE_POINT",
        0x400 if os.name == "nt" else 0,
    )
    return bool(
        reparse_flag
        and getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )
