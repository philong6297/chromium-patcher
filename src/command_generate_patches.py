import logging
import os
import sys

from config import ProgramConfig
from patch_generator import GitPatchGenerator

__all__ = ["command_generate_patches"]

_logger = logging.getLogger(__name__)


def command_generate_patches(config: ProgramConfig) -> None:
    repo_dirs_list = "  - ".join(
        f"{'/'.join(path)}{os.linesep}" for path in config.REPO_DIRS
    )

    _logger.info(
        f"Generate patches from {config.PATCHES_DIR.as_posix()}{os.linesep}"
        f"for Chromium-based project {config.CHROMIUM_SRC_DIR.as_posix()}{os.linesep}"
        f"Repository directories:{os.linesep}"
        f"{repo_dirs_list}"
    )

    try:
        repo_mappings = [
            (
                config.CHROMIUM_SRC_DIR.joinpath(*path),
                config.PATCHES_DIR.joinpath(*path),
            )
            for path in config.REPO_DIRS
        ]

        for repo_dir, patch_dir in repo_mappings:
            generator = GitPatchGenerator(
                git_repo_dir=repo_dir,
                patch_dir=patch_dir,
                relative_paths_to_ignore=None,
                patch_files_to_keep=None,
            )
            generator.update_patches()

        _logger.info("Done.")
        sys.exit(0)
    except Exception as err:
        _logger.error(f"Error updating patch files: {err}")
        sys.exit(1)
