from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, List, Optional

from src.config import ProgramConfig
from src.util import run_git

_logger = logging.getLogger(__name__)


class GitPatchGenerator:
    """Generates and manages patch files from Git repository changes."""

    def __init__(
        self,
        git_repo_dir: Path,
        patch_dir: Path,
        relative_paths_to_ignore: Optional[Callable[[str], bool]] = None,
        patch_files_to_keep: Optional[List[str]] = None,
    ):
        """Initialize the patch generator.

        Args:
            git_repo_dir: Path to the Git repository
            patch_dir: Directory where patch files should be stored
            relative_paths_to_ignore: Optional filter function to filter modified paths
            patch_files_to_keep: List of patch filenames to never delete
        """
        self._git_repo_dir = git_repo_dir
        self._patch_dir = patch_dir
        self._relative_paths_to_ignore_filter = relative_paths_to_ignore
        self._patch_files_to_keep = patch_files_to_keep or []

    def get_modified_relative_paths(self) -> List[str]:
        """Get list of modified files in the Git repository.

        Returns:
            List of modified file paths relative to repository root

        Raises:
            Exception: If git diff command fails
        """
        try:
            cmd_output = run_git(
                self._git_repo_dir,
                [
                    "diff",
                    "--ignore-submodules",
                    "--diff-filter=M",
                    "--name-only",
                    "--ignore-space-at-eol",
                ],
            )
            return [line.strip() for line in cmd_output.split(os.linesep) if line]
        except Exception as e:
            raise Exception(f"Failed to get modified paths: {e}") from e

    def write_patch_files(self, modified_relative_paths: List[str]) -> List[str]:
        """Generate patch files for modified paths.

        Args:
            modified_relative_paths: List of modified file paths relative to repository root

        Returns:
            List of generated patch filenames

        Raises:
            Exception: If patch directory creation or file writing fails
        """
        try:
            self._patch_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise Exception(f"Failed to create patch directory: {e}") from e

        # Format patch filenames
        patch_filenames = [
            Path(relative_path)
            .as_posix()
            .replace("/", ProgramConfig.PATCH_FILE_REPLACEMENT_SEPARATOR)
            + f".{ProgramConfig.patch_file_ext}"
            for relative_path in modified_relative_paths
        ]

        write_ops_done_count = 0
        patch_count = len(modified_relative_paths)

        _logger.info(f"Writing {patch_count} .patch files:")
        for modified_file, patch_filename in zip(
            modified_relative_paths, patch_filenames
        ):
            try:
                single_diff_args = [
                    "diff",
                    "--src-prefix=a/",
                    "--dst-prefix=b/",
                    "--full-index",
                    modified_file,
                ]
                patch_contents = run_git(self._git_repo_dir, single_diff_args)
                patch_file = self._patch_dir.joinpath(patch_filename)
                patch_file.write_text(patch_contents)

                write_ops_done_count += 1
                _logger.info(
                    f"----wrote {write_ops_done_count} / {patch_count}: {patch_filename}"
                )
            except Exception as e:
                raise Exception(
                    f"Failed to write patch file {patch_filename}: {e}"
                ) from e

        return patch_filenames

    def remove_stale_patch_files(self, patch_filenames: List[str]) -> None:
        """Remove patch files that are no longer associated with modified files.

        Args:
            patch_filenames: List of valid patch filenames to keep

        Raises:
            Exception: If file removal fails
        """
        if not self._patch_dir.exists():
            _logger.error(f"Path at {self._patch_dir} does not exist.")
            return

        _logger.info("Remove stale .patch files if needed:")

        try:
            existing_patch_filenames = [f.name for f in self._patch_dir.glob("*.patch")]
            valid_filenames = set(patch_filenames + self._patch_files_to_keep)
            to_remove_filenames = [
                f for f in existing_patch_filenames if f not in valid_filenames
            ]

            if not to_remove_filenames:
                _logger.info("No stale .patch files to remove.")
                return

            remove_count = len(to_remove_filenames)
            for i, filename in enumerate(to_remove_filenames, 1):
                try:
                    (self._patch_dir / filename).unlink()
                    _logger.info(f"----removed {i}/{remove_count}: {filename}")
                except Exception as e:
                    raise Exception(
                        f"Failed to remove stale patch file {filename}: {e}"
                    ) from e
        except Exception as e:
            raise Exception(f"Failed to process stale patch files: {e}") from e

    def update_patches(self) -> None:
        """Update patch files based on current Git repository state.

        Raises:
            Exception: If patch update process fails
        """
        _logger.info(
            f"Updating patches for {self._git_repo_dir}, saving to {self._patch_dir}:"
        )
        try:
            modified_relative_paths = self.get_modified_relative_paths()
            if self._relative_paths_to_ignore_filter:
                modified_relative_paths = list(
                    filter(
                        self._relative_paths_to_ignore_filter, modified_relative_paths
                    )
                )

            patch_files = self.write_patch_files(modified_relative_paths)
            self.remove_stale_patch_files(patch_files)
        except Exception as e:
            raise Exception(f"Unexpected error during patch update: {e}") from e
