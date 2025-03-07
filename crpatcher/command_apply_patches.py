import logging
import os
import sys
from pathlib import Path
from typing import List

from crpatcher.config import ProgramConfig
from crpatcher.patch_apply import FileChangeResult, GitPatcher

__all__ = ["command_apply_patches"]

_logger = logging.getLogger(__name__)

_DIVIDER = "-" * 10


def _get_path_as_str(path: Path) -> str:
    posix_str = path.as_posix()
    return posix_str if posix_str else "Unknown"


def _print_file_change_report(file_result: FileChangeResult) -> None:
    _logger.info(_DIVIDER)
    _logger.info(
        f"""{{
    - file: {_get_path_as_str(file_result.file_path)}
    - patch: {_get_path_as_str(file_result.patch_path)}
    - applied because: {file_result.reason or "Unknown"}
    - error: {file_result.error or "None"}
    - warning: {file_result.warning or "None"}
}}"""
    )
    _logger.info(_DIVIDER)


def _print_report(result: List[FileChangeResult]) -> None:
    if not result:
        _logger.info("There are no updates to apply.")
        return

    successful_files: List[FileChangeResult] = []
    failed_files: List[FileChangeResult] = []

    for file_result in result:
        if file_result.error is not None:
            failed_files.append(file_result)
        else:
            successful_files.append(file_result)

    _logger.info(f"There were {len(result)} updates to apply.")

    if successful_files:
        _logger.info(f"{len(successful_files)} successful:")
        for file_result in successful_files:
            _print_file_change_report(file_result)

    if failed_files:
        _logger.info(f"{len(failed_files)} failed:")
        for file_result in failed_files:
            _print_file_change_report(file_result)


def command_apply_patches(
    config: ProgramConfig, should_print_report: bool = False
) -> None:
    repo_dirs_list = "  - ".join(
        f"{'/'.join(path)}{os.linesep}" for path in config.repo_dirs
    )

    _logger.info(
        f"Apply patches from {config.patches_dir.as_posix()}{os.linesep}"
        f"for Chromium-based project {config.chromium_src_dir.as_posix()}{os.linesep}"
        f"Repository directories:{os.linesep}"
        f"{repo_dirs_list}"
    )

    repo_mappings = [
        (
            config.chromium_src_dir.joinpath(*path),
            config.patches_dir.joinpath(*path),
        )
        for path in config.repo_dirs
    ]

    result: List[FileChangeResult] = []

    for repo_dir, patch_dir in repo_mappings:
        patcher = GitPatcher(patch_dir=patch_dir, git_repo_dir=repo_dir, config=config)
        result.extend(patcher.apply_patches())

    if should_print_report:
        _print_report(result)

    if any(patch_file_result.error is not None for patch_file_result in result):
        _logger.error("Error: Not all patches were successful!")
        sys.exit(1)

    _logger.info("Patches applied successfully.")
    sys.exit(0)
