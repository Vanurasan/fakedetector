"""Narrow stdlib checks for application-owned runtime filesystem objects."""

from __future__ import annotations

import os
import stat
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


class FilesystemSafetyError(OSError):
    """Signal a detectable unsafe or indeterminate runtime filesystem object."""

    def __init__(self) -> None:
        super().__init__("Runtime filesystem object is unsafe.")


def ensure_private_directory(path: Path) -> None:
    """Create one directory chain with restrictive modes and validate each new object."""
    missing: list[Path] = []
    candidate = path
    while True:
        info = _lstat(candidate)
        if info is not None:
            _require_directory(candidate, info)
            break
        missing.append(candidate)
        parent = candidate.parent
        if parent == candidate:
            raise FilesystemSafetyError
        candidate = parent

    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        except FileExistsError:
            pass
        except OSError:
            raise FilesystemSafetyError from None
        info = _lstat(directory)
        if info is None:
            raise FilesystemSafetyError
        _require_directory(directory, info)

    require_safe_directory(path)


def require_safe_directory(path: Path, *, missing_ok: bool = False) -> bool:
    """Require an ordinary non-reparse directory and its immediate lexical parent."""
    info = _lstat(path)
    if info is None:
        _require_nearest_existing_directory(path.parent)
        if missing_ok:
            return False
        raise FilesystemSafetyError
    _require_directory(path, info)
    if path.parent != path:
        parent_info = _lstat(path.parent)
        if parent_info is None:
            raise FilesystemSafetyError
        _require_directory(path.parent, parent_info)
    return True


def require_direct_child_directory(parent: Path, child: Path) -> None:
    """Require *child* to remain one ordinary direct directory below *parent*."""
    if child.parent != parent:
        raise FilesystemSafetyError
    require_safe_directory(parent)
    info = _lstat(child)
    if info is None:
        raise FilesystemSafetyError
    _require_directory(child, info)


def require_regular_file(path: Path, *, missing_ok: bool = False) -> bool:
    """Require one ordinary non-reparse file without following its final component."""
    info = _lstat(path)
    if info is None:
        if missing_ok:
            return False
        raise FilesystemSafetyError
    _require_regular_file(path, info)
    return True


def require_missing_path(path: Path) -> None:
    """Require the final path component to be absent, including broken links."""
    if _lstat(path) is not None:
        raise FilesystemSafetyError


def require_relative_file_target(
    workspace: Path,
    target: Path,
    *,
    missing_ok: bool,
) -> bool:
    """Validate a lexical workspace file and every existing intermediate directory."""
    require_safe_directory(workspace)
    try:
        relative = target.relative_to(workspace)
    except ValueError:
        raise FilesystemSafetyError from None
    if not relative.parts:
        raise FilesystemSafetyError

    current = workspace
    for component in relative.parts[:-1]:
        current = current / component
        info = _lstat(current)
        if info is None:
            break
        _require_directory(current, info)
    return require_regular_file(target, missing_ok=missing_ok)


def require_relative_directory(
    workspace: Path,
    directory: Path,
    *,
    missing_ok: bool,
) -> bool:
    """Validate one directory path component-by-component below a workspace."""
    require_safe_directory(workspace)
    try:
        relative = directory.relative_to(workspace)
    except ValueError:
        raise FilesystemSafetyError from None
    if not relative.parts:
        return True

    current = workspace
    for component in relative.parts:
        current = current / component
        info = _lstat(current)
        if info is None:
            if missing_ok:
                return False
            raise FilesystemSafetyError
        _require_directory(current, info)
    return True


def require_safe_tree(root: Path) -> None:
    """Require an owned tree to contain only ordinary directories and regular files."""
    require_safe_directory(root)
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError:
            raise FilesystemSafetyError from None
        for entry in entries:
            child = directory / entry.name
            info = _lstat(child)
            if info is None:
                raise FilesystemSafetyError
            _require_not_reparse(child, info)
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
            elif not stat.S_ISREG(info.st_mode):
                raise FilesystemSafetyError


def open_regular_file_for_read(path: Path) -> BinaryIO:
    """Open one checked regular file and verify descriptor identity before use."""
    before = _lstat(path)
    if before is None:
        raise FilesystemSafetyError
    _require_regular_file(path, before)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise FilesystemSafetyError from None
    try:
        _require_descriptor_identity(descriptor, before)
        stream = os.fdopen(descriptor, "rb")
        descriptor = -1
        return stream
    except OSError:
        raise FilesystemSafetyError from None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)


def require_file_descriptor_identity(path: Path, descriptor: int) -> None:
    """Require an open descriptor to still identify the checked regular path."""
    info = _lstat(path)
    if info is None:
        raise FilesystemSafetyError
    _require_regular_file(path, info)
    _require_descriptor_identity(descriptor, info)


def _require_nearest_existing_directory(path: Path) -> None:
    candidate = path
    while True:
        info = _lstat(candidate)
        if info is not None:
            _require_directory(candidate, info)
            return
        parent = candidate.parent
        if parent == candidate:
            raise FilesystemSafetyError
        candidate = parent


def _lstat(path: Path) -> os.stat_result | None:
    try:
        if path.is_symlink():
            raise FilesystemSafetyError
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            raise FilesystemSafetyError
        return path.lstat()
    except FileNotFoundError:
        return None
    except FilesystemSafetyError:
        raise
    except OSError:
        raise FilesystemSafetyError from None


def _require_directory(path: Path, info: os.stat_result) -> None:
    _require_not_reparse(path, info)
    if not stat.S_ISDIR(info.st_mode):
        raise FilesystemSafetyError


def _require_regular_file(path: Path, info: os.stat_result) -> None:
    _require_not_reparse(path, info)
    if not stat.S_ISREG(info.st_mode):
        raise FilesystemSafetyError


def _require_not_reparse(path: Path, info: os.stat_result) -> None:
    if stat.S_ISLNK(info.st_mode):
        raise FilesystemSafetyError
    attributes = getattr(info, "st_file_attributes", 0)
    if _REPARSE_ATTRIBUTE and attributes & _REPARSE_ATTRIBUTE:
        raise FilesystemSafetyError


def _require_descriptor_identity(descriptor: int, expected: os.stat_result) -> None:
    try:
        opened = os.fstat(descriptor)
    except OSError:
        raise FilesystemSafetyError from None
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_dev != expected.st_dev
        or opened.st_ino != expected.st_ino
    ):
        raise FilesystemSafetyError
