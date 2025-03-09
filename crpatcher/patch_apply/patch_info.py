# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from enum import IntEnum, unique
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from crpatcher.config import PATCHINFO_SCHEMA, ProgramConfig
from crpatcher.util import calculate_file_checksum

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
    file_checksum: Optional[str]


@dataclass
class PatchInfo:
    """Information about a patch and its affected files.

    Attributes:
        schema_version: Version of the patchinfo file format
        patch_checksum: SHA-256 checksum of the patch file
        affected_files: List of files modified by this patch
    """

    schema_version: int
    patch_checksum: Optional[str]
    affected_files: List[AffectedFileData]

    @staticmethod
    def parse(patchinfo_file: Path, config: ProgramConfig) -> PatchInfo:
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
        try:
            with patchinfo_file.open(
                "r", encoding=config.patchinfo_file_encoding
            ) as file:
                data: Any = json.load(file)

                # Validate against schema
                validate(instance=data, schema=PATCHINFO_SCHEMA)
                data = cast(Dict[str, Any], data)

                return PatchInfo(
                    schema_version=data["schema_version"],
                    patch_checksum=data["patch_checksum"],
                    affected_files=[
                        AffectedFileData(
                            file_relative_path=file_data["file_relative_path"],
                            file_checksum=file_data["file_checksum"],
                        )
                        for file_data in data["affected_files"]
                    ],
                )

        except (ValidationError, TypeError) as err:
            raise TypeError(f"Invalid {config.patchinfo_file_ext} file: {err}")
        except Exception as err:
            raise RuntimeError(
                f'Error reading {config.patchinfo_file_ext} file "{patchinfo_file}": {err}'
            )

    def write(self, patchinfo_out_file: Path, config: ProgramConfig) -> None:
        """
        Write this PatchInfo instance to a file.

        Args:
            patchinfo_out_file: Path where the .patchinfo file should be written

        Raises:
            Exception: If the file cannot be written
        """
        try:
            with patchinfo_out_file.open(
                mode="w", encoding=config.patchinfo_file_encoding
            ) as out:
                json.dump(asdict(self), out, indent=2)
        except Exception as err:
            raise RuntimeError(
                f'Error writing {config.patchinfo_file_ext} file at path "{patchinfo_out_file}": {err}'
            ) from err

    @staticmethod
    def get_stale_status(
        repo_dir: Path, patch_file: Path, patchinfo_file: Path, config: ProgramConfig
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
            patchinfo = PatchInfo.parse(patchinfo_file, config)
        except Exception as err:
            _logger.error(
                f"Error parsing {config.patchinfo_file_ext} file at {patchinfo_file}: {err}"
            )
            return PatchInfoStaleStatus.PATCHINFO_OUTDATED

        if patchinfo.schema_version != config.patchinfo_file_schema_version:
            return PatchInfoStaleStatus.PATCHINFO_OUTDATED

        # Check if patch file changed
        _logger.info(
            f"{config.patch_file_ext} checksum from {config.patchinfo_file_ext} data: {patchinfo.patch_checksum}"
        )
        try:
            current_patch_checksum = calculate_file_checksum(patch_file)
            _logger.info(
                f"Current {config.patch_file_ext} checksum: {current_patch_checksum}"
            )
        except Exception as err:
            _logger.error(
                f"Error calculating checksum for {config.patch_file_ext} file {patch_file}: {err}"
            )
            return PatchInfoStaleStatus.PATCH_CHANGED

        if current_patch_checksum != patchinfo.patch_checksum:
            return PatchInfoStaleStatus.PATCH_CHANGED

        # Check if affected files changed
        for entry in patchinfo.affected_files:
            _logger.info(f"Checking file: {entry.file_relative_path}")
            _logger.info(
                f"----> File checksum from {config.patchinfo_file_ext} data: {entry.file_checksum}"
            )
            try:
                current_checksum = calculate_file_checksum(
                    repo_dir.joinpath(entry.file_relative_path)
                )
                _logger.info(f"----> Current checksum: {current_checksum}")
            except Exception as err:
                _logger.error(
                    f"Error calculating checksum for file {entry.file_relative_path}: {err}"
                )
                return PatchInfoStaleStatus.SRC_CHANGED

            if current_checksum != entry.file_checksum:
                return PatchInfoStaleStatus.SRC_CHANGED

        return PatchInfoStaleStatus.NONE
