from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import IntEnum, unique
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from config import ProgramConfig
from src.util import calculate_file_checksum, validate_dict_keys_match_dataclass

_logger = logging.getLogger(__name__)


@unique
class PatchInfoStaleStatus(IntEnum):
    """Status indicating whether a patch needs to be reapplied."""

    NONE = 0  # Nothing changed, .patchinfo file is good
    NO_PATCHINFO = 1  # .patchinfo file does not exist
    PATCHINFO_OUTDATED = 2  # .patchinfo file is invalid or has old schema version
    PATCH_CHANGED = 3  # Patch file changed since last patch application
    SRC_CHANGED = 4  # Target files changed since last patch application


@dataclass
class AffectedFileData:
    """Information about a file affected by a patch.

    Attributes:
        file_relative_path: Path to the file relative to repository root
        file_checksum: SHA-256 checksum of the file, or None if not calculated
    """

    file_relative_path: str
    file_checksum: Optional[str] = None

    @staticmethod
    def load(raw_data: Dict[str, Any]) -> AffectedFileData:
        """
        Construct AffectedFileData from a dictionary.

        Args:
            raw_data: Dictionary containing file data

        Returns:
            New AffectedFileData instance

        Raises:
            TypeError: If raw_data has invalid structure or types
        """
        error_msg = """AffectedFileData must be in the following format:
{
  "file_relative_path": string
  "file_checksum": string|null
}"""
        if not validate_dict_keys_match_dataclass(raw_data, AffectedFileData):
            raise TypeError(error_msg)

        if not isinstance(raw_data["file_relative_path"], str):
            raise TypeError(error_msg)

        if not isinstance(raw_data["file_checksum"], (str, type(None))):
            raise TypeError(error_msg)

        return AffectedFileData(
            file_relative_path=raw_data["file_relative_path"],
            file_checksum=raw_data["file_checksum"],
        )


@dataclass
class PatchInfo:
    """Information about a patch and its affected files.

    Attributes:
        schema_version: Version of the patchinfo file format
        patch_checksum: SHA-256 checksum of the patch file
        affected_files: List of files modified by this patch
    """

    schema_version: int = ProgramConfig.PATCHINFO_FILE_SCHEMA_VERSION
    patch_checksum: Optional[str] = None
    affected_files: List[AffectedFileData] = field(default_factory=list)

    @staticmethod
    def parse(patchinfo_file: Path) -> PatchInfo:
        """
        Construct PatchInfo from a .patchinfo file.

        Args:
            patchinfo_file: Path to the .patchinfo file to read

        Returns:
            New PatchInfo instance with data from file

        Raises:
            TypeError: If file contains invalid data types
            Exception: If file cannot be read or parsed
        """
        error_msg = """PatchInfo must be in the following format:
{
  "schema_version": integer,
  "patch_checksum": string|null,
  "affected_files": [
    {
      "file_relative_path": string
      "file_checksum": string|null
    }
  ]
}"""
        try:
            with open(
                patchinfo_file, "r", encoding=ProgramConfig.PATCHINFO_FILE_ENCODING
            ) as file:
                data: Any = json.load(file)

                if not isinstance(data, dict):
                    raise TypeError(error_msg)

                data = cast(Dict[str, Any], data)

                if not validate_dict_keys_match_dataclass(data, PatchInfo):
                    raise TypeError(error_msg)

                if not isinstance(data["schema_version"], int):
                    raise TypeError(error_msg)
                if not isinstance(data["patch_checksum"], (str, type(None))):
                    raise TypeError(error_msg)
                if not isinstance(data["affected_files"], list):
                    raise TypeError(error_msg)

                affected_files = [
                    AffectedFileData.load(file_data)
                    for file_data in data["affected_files"]
                ]

                return PatchInfo(
                    schema_version=data["schema_version"],
                    patch_checksum=data["patch_checksum"],
                    affected_files=affected_files,
                )

        except Exception as err:
            raise RuntimeError(
                f'Error reading .patchinfo file "{patchinfo_file}": {err}'
            )

    def write(self, patchinfo_out_file: Path) -> None:
        """
        Write this PatchInfo instance to a file.

        Args:
            patchinfo_out_file: Path where the .patchinfo file should be written

        Raises:
            Exception: If the file cannot be written
        """
        try:
            with patchinfo_out_file.open(
                mode="w", encoding=ProgramConfig.PATCHINFO_FILE_ENCODING
            ) as out:
                json.dump(asdict(self), out, indent=2)
        except Exception as err:
            raise RuntimeError(
                f'Error writing .patchinfo file at path "{patchinfo_out_file}": {err}'
            ) from err

    @staticmethod
    def get_stale_status(
        repo_dir: Path, patch_file: Path, patchinfo_file: Path
    ) -> PatchInfoStaleStatus:
        """
        Check if a patch needs to be reapplied.

        This method determines whether a patch needs to be reapplied by checking:
        1. If the .patchinfo file exists and is valid
        2. If the patch file has changed since last application
        3. If any affected files have changed since last application

        Args:
            repo_dir: Path to the repository root directory
            patch_file: Path to the patch file to check
            patchinfo_file: Path to the corresponding .patchinfo file

        Returns:
            PatchInfoStaleStatus indicating whether/why the patch needs reapplication
        """
        try:
            if not patchinfo_file.is_file():
                return PatchInfoStaleStatus.NO_PATCHINFO
            patchinfo = PatchInfo.parse(patchinfo_file)
        except Exception as err:
            _logger.error(f"Error parsing .patchinfo file at {patchinfo_file}: {err}")
            return PatchInfoStaleStatus.PATCHINFO_OUTDATED

        if patchinfo.schema_version != ProgramConfig.PATCHINFO_FILE_SCHEMA_VERSION:
            return PatchInfoStaleStatus.PATCHINFO_OUTDATED

        # Check if patch file changed
        _logger.info(
            f".patch checksum from .patchinfo data: {patchinfo.patch_checksum}"
        )
        try:
            current_patch_checksum = calculate_file_checksum(patch_file)
            _logger.info(f"Current .patch checksum: {current_patch_checksum}")
        except Exception as err:
            _logger.error(
                f"Error calculating checksum for patch file {patch_file}: {err}"
            )
            return PatchInfoStaleStatus.PATCH_CHANGED

        if current_patch_checksum != patchinfo.patch_checksum:
            return PatchInfoStaleStatus.PATCH_CHANGED

        # Check if affected files changed
        for entry in patchinfo.affected_files:
            _logger.info(f"Checking file: {entry.file_relative_path}")
            _logger.info(
                f"----> File checksum from .patchinfo data: {entry.file_checksum}"
            )
            try:
                current_checksum = calculate_file_checksum(
                    repo_dir.joinpath(entry.file_relative_path)
                )
                _logger.info(f"----> Current file checksum: {current_checksum}")
            except Exception as err:
                _logger.error(
                    f"Error calculating checksum for file {entry.file_relative_path}: {err}"
                )
                return PatchInfoStaleStatus.SRC_CHANGED

            if current_checksum != entry.file_checksum:
                return PatchInfoStaleStatus.SRC_CHANGED

        return PatchInfoStaleStatus.NONE
