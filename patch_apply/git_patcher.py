from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from config import ProgramConfig
from util import calculate_file_checksum, run_git

from .patch_apply_status import PatchApplyData as ApplyData
from .patch_apply_status import PatchApplyReason as ApplyReason
from .patch_apply_status import PatchApplyResult as PatchResult
from .patch_info import AffectedFileData, PatchInfo
from .patch_info import PatchInfoStaleStatus as StaleStatus

_logger = logging.getLogger(__name__)


@dataclass
class FileChangeResult:
    """Result of a file change operation, either from applying a patch or resetting to original state

    Attributes:
        file_path: Path to the file that was changed
        patch_path: Path to the .patch file that was applied
        reason: String explaining why the change was made
        error: Error message if the operation failed, None if successful
        warning: Warning message if there were non-fatal issues, None otherwise
    """

    file_path: Path
    patch_path: Path
    reason: str
    error: Optional[str] = None
    warning: Optional[str] = None


class GitPatcher:
    """Handle applying patches to a Git repository."""

    def __init__(self, patch_dir: Path, git_repo_dir: Path):
        """
        :param patch_dir_path: Path to the directory containing patch files.
        :param repo_path: Path to the Git repository.
        """
        self._patch_dir = patch_dir
        self._git_repo_dir = git_repo_dir
        self._APPLY_ARGS = ["--ignore-space-change", "--ignore-whitespace"]

    def apply_patches(self) -> List[FileChangeResult]:
        """
        Detects modifications to a git repo and creates or updates patch files for each modified file.
        Removes patch files that are no longer relevant.

        :return: List of patch statuses.
        """
        # STRATEGY:
        # 1. iterate .patch files in dir
        # corresponding .patchinfo file?
        #  - no? add to TO_PATCH list
        #  - yes? check hash of patch file and each chromium file. different? add to TO_PATCH list.
        # 2. iterate .patchinfo files in dir
        # corresponding .patch file?
        # - no? add to TO_RESET list
        # 3. iterate TO_PATCH list
        # - reset chromium file
        # - apply patch
        # - create .patchinfo file
        # 4. iterate TO_RESET list
        # - reset chromium file
        # - delete .patchinfo file

        if not Path.is_dir(self._patch_dir):
            return []

        if not Path.is_dir(self._git_repo_dir):
            raise RuntimeError(
                f'Could not apply patches. Repo "{self._git_repo_dir}" is not a directory or does not exist'
            )

        all_patch_files = self._patch_dir.glob(f"*.{ProgramConfig.PATCH_FILE_EXT}")
        all_patchinfo_files = self._patch_dir.glob(
            f"*.{ProgramConfig.PATCHINFO_FILE_EXT}"
        )

        patches_to_apply: List[ApplyData] = []
        obsolete_patchinfo_files: List[Path] = []

        for patch_file in all_patch_files:
            expected_patchinfo_file = patch_file.with_suffix(
                f".{ProgramConfig.PATCHINFO_FILE_EXT}"
            )

            _logger.info(f"Checking .patchinfo file for {patch_file.as_posix()}:")

            stale_status = PatchInfo.get_stale_status(
                repo_dir=self._git_repo_dir,
                patch_file=patch_file,
                patchinfo_file=expected_patchinfo_file,
            )

            if stale_status != StaleStatus.NONE:
                apply_reason = ApplyReason.from_stale_status(stale_status)
                _logger.info(f"----> Adding to TO_PATCH list, reason: {apply_reason}")
                patches_to_apply.append(
                    ApplyData(
                        patch_path=patch_file,
                        patchinfo_path=expected_patchinfo_file,
                        reason=apply_reason,
                    )
                )
            else:
                _logger.info(f"----> Nothing changed, skipping the .patch file.")

        for patchinfo_file in all_patchinfo_files:
            expected_patch_file = patchinfo_file.with_suffix(
                f".{ProgramConfig.PATCH_FILE_EXT}"
            )
            _logger.info(f"Reading .patch file for {patchinfo_file.as_posix()}:")
            if not expected_patch_file.is_file():
                _logger.info(
                    f"----> Adding to TO_RESET list, reason: {ApplyReason.PATCH_REMOVED}"
                )
                obsolete_patchinfo_files.append(patchinfo_file)
            else:
                _logger.info(f"----> Nothing changed, skipping the .patchinfo file.")

        result: List[FileChangeResult] = []
        try:
            if patches_to_apply:
                result.extend(self.perform_apply_for_patches(patches_to_apply))

            if obsolete_patchinfo_files:
                result.extend(self.handle_obsolete_patchinfos(obsolete_patchinfo_files))

        except Exception as err:
            _logger.error(
                "There was an error applying added, modified, or removed patches. "
            )
            _logger.error(f"Error: {err}")

        return result

    def perform_apply_for_patches(
        self, patches_to_apply: List[ApplyData]
    ) -> List[FileChangeResult]:
        """
        Applies patches to the repository.

        :param patches_to_apply: List of dictionaries containing patch details.
        :return: List of dictionaries with status of applied patches.
        """
        processing_patches: List[PatchResult] = []

        _logger.info(os.linesep + "Getting patch data...")
        for patch_data in patches_to_apply:
            patch_result = PatchResult(data=patch_data)
            _logger.info(
                f"Getting affected files from patch {patch_data.patch_path.as_posix()}"
            )
            try:
                patch_result.affected_files = self.get_affected_files_data(
                    patch_result.data.patch_path
                )
                patch_result.error = None
            except RuntimeError as err:
                patch_result.affected_files = []
                patch_result.error = f"Could not read data from patch file: {err}"
                _logger.info(patch_result.error)

            processing_patches.append(patch_result)

        _logger.info("Resetting affected files before applying patches...")

        files_to_reset = [
            self._git_repo_dir.joinpath(entry.file_relative_path)
            for p in processing_patches
            if p.error is None
            for entry in p.affected_files
        ]

        try:
            self.reset_files_in_repo(files_to_reset)
        except RuntimeError:
            _logger.warning(
                f"Warning: There were some failures during git reset of specific repo paths: {' '.join(filepath.as_posix() for filepath in files_to_reset)}",
            )

        _logger.info("Done reset.")

        _logger.info("Applying patches...")

        # Apply patches (in series)
        for patch_result in processing_patches:
            # skip error patches, we wont try to process them anyway.
            if patch_result.error is not None:
                continue

            _logger.info(f"Applying {patch_result.data.patch_path.as_posix()}")
            try:
                run_git(
                    self._git_repo_dir,
                    ["apply", patch_result.data.patch_path.as_posix()]
                    + self._APPLY_ARGS,
                )
            except RuntimeError as err:
                patch_result.error = str(err)
                _logger.error(f"---- {err}")

        _logger.info("Finish applying.")

        # Create .pathinfo files for success patches
        _logger.info("Updating .patchinfo files...")

        for patch_result in processing_patches:
            if patch_result.error is None:
                try:
                    # Calculate patch checksum
                    patch_checksum = calculate_file_checksum(
                        patch_result.data.patch_path
                    )

                    # Update checksums for all affected files after applying patch
                    for affected_file in patch_result.affected_files:
                        try:
                            file_path = self._git_repo_dir.joinpath(
                                affected_file.file_relative_path
                            )
                            affected_file.file_checksum = calculate_file_checksum(
                                file_path
                            )
                        except Exception as err:
                            patch_result.error = f"Failed to calculate checksum for affected file {affected_file.file_relative_path}: {err}"
                            _logger.error(f"---- {err}")
                            break

                    if patch_result.error is not None:
                        continue

                except Exception as err:
                    patch_result.error = f"Failed to calculate patch checksum: {err}"
                    _logger.error(f"---- {err}")
                    continue

                patchinfo = PatchInfo(
                    schema_version=ProgramConfig.PATCHINFO_FILE_SCHEMA_VERSION,
                    patch_checksum=patch_checksum,
                    affected_files=patch_result.affected_files,
                )
                _logger.info(
                    f"Writing to {patch_result.data.patchinfo_path.as_posix()}"
                )
                patchinfo.write(patch_result.data.patchinfo_path)

        # Provide apply result as per file
        result: List[FileChangeResult] = []
        for patch_result in processing_patches:
            if patch_result.affected_files:
                result.extend(
                    FileChangeResult(
                        file_path=self._git_repo_dir.joinpath(entry.file_relative_path),
                        patch_path=patch_result.data.patch_path,
                        reason=patch_result.data.reason,
                        error=patch_result.error,
                        warning=None,
                    )
                    for entry in patch_result.affected_files
                )
            else:
                result.append(
                    FileChangeResult(
                        file_path=Path(),
                        patch_path=patch_result.data.patch_path,
                        reason=patch_result.data.reason,
                        error=patch_result.error,
                        warning=None,
                    )
                )

        return result

    def get_affected_files_data(self, patch_path: Path) -> List[AffectedFileData]:
        """
        Gets the list of files a patch applies to.

        :param patch_path: Path to the patch file.
        :return: List of file paths the patch applies to.
        """
        # Interpret `--numstat -z` line format
        # https:#regex101.com/r/jP1JEP/1
        REGEX_GIT_APPLY_NUM_STATS = re.compile(r"^((\d|-)+\s+){2}")

        result: List[AffectedFileData] = []
        apply_stat_args: list[str] = [
            "apply",
            patch_path.as_posix(),
            "--numstat",
            "-z",
        ] + self._APPLY_ARGS

        try:
            output = run_git(self._git_repo_dir, apply_stat_args)
            for line in output.splitlines():
                line = line.strip()
                if line:
                    # Intrepret `--numstat -z` line format
                    affected_file_relative_path_as_str = re.sub(
                        REGEX_GIT_APPLY_NUM_STATS, "", line
                    ).replace("\0", "")

                    affected_file = self._git_repo_dir.joinpath(
                        affected_file_relative_path_as_str
                    )
                    checksum = calculate_file_checksum(affected_file)

                    result.append(
                        AffectedFileData(affected_file_relative_path_as_str, checksum)
                    )
            return result
        except RuntimeError as err:
            raise RuntimeError(
                f'Error getting applies-to data for patch "{patch_path}": {err}'
            )

    def reset_files_in_repo(self, files: List[Path]):
        """
        Resets specified repository files to their original state.

        :param files: List of file paths to reset.
        """
        try:
            as_str_paths = [file.as_posix() for file in files]
            run_git(self._git_repo_dir, ["checkout"] + as_str_paths)
        except RuntimeError as err:
            raise RuntimeError(f"Error resetting repo files: {err}")

    def handle_obsolete_patchinfos(
        self, obsolete_patchinfo_files: List[Path]
    ) -> List[FileChangeResult]:
        """
        collect all affected files from each .patchinfo in `obsolete_patchinfo_files`. Reset all of them original state. Also remove all .patchinfo-s

        :param obsolete_patchinfo_files: List of obsolete patch info file paths.
        :return: List of dictionaries containing status information.
        """

        files_to_reset: List[Path] = []
        result: List[FileChangeResult] = []

        for patchinfo_file in obsolete_patchinfo_files:
            try:
                patchinfo = PatchInfo.parse(patchinfo_file)
                # remove .patchinfo file
                patchinfo_file.unlink(missing_ok=True)
            except Exception as err:
                # Handle error removing patch info, not fatal error
                _logger.info(
                    f"Warning: Could not remove obsolete PatchInfo file at {patchinfo_file}: {err}",
                )
                continue

            files_to_reset.extend(
                self._git_repo_dir.joinpath(affected_file_data.file_relative_path)
                for affected_file_data in patchinfo.affected_files
            )
            result.extend(
                FileChangeResult(
                    file_path=self._git_repo_dir.joinpath(entry.file_relative_path),
                    patch_path=patchinfo_file.with_suffix(
                        f".{ProgramConfig.PATCH_FILE_EXT}"
                    ),
                    reason=ApplyReason.PATCH_REMOVED,
                    error=None,
                    warning=None,
                )
                for entry in patchinfo.affected_files
            )

        reset_was_successful = True
        try:
            self.reset_files_in_repo(files_to_reset)
        except RuntimeError:
            # Don't worry about errors with resetting obsolete patch files, some paths probably don't exist anymores
            reset_was_successful = False

        if not reset_was_successful:
            for file_result in result:
                file_result.warning = "Some resets failed"

        return result
