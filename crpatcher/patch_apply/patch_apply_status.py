# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from crpatcher.config import ProgramConfig
from crpatcher.patch_apply.patch_info import AffectedFileData
from crpatcher.patch_apply.patch_info import PatchInfoStaleStatus as StaleStatus


class PatchApplyReasonCreator:
    """Why a patch file needs to be applied or was applied."""

    def __init__(self, config: ProgramConfig) -> None:
        self._config = config

    def patch_removed(self) -> str:
        return (
            f"The .{self._config.patch_file_ext} file was removed since last applied."
        )

    def from_patchinfo_stale_status(self, status: StaleStatus) -> str:
        """Convert a StaleStatus to a PatchApplyReason message.

        Args:
            status: The stale status to convert
            config: The program configuration
        Returns:
            string message explaining the status

        Raises:
            ValueError: If the status is not a recognized StaleStatus value
        """
        match status:
            case StaleStatus.NONE:
                return "None"
            case StaleStatus.NO_PATCHINFO:
                return f"No corresponding .{self._config.patchinfo_file_ext} file was found."
            case StaleStatus.PATCHINFO_OUTDATED:
                return (
                    f"The corresponding .{self._config.patchinfo_file_ext} file was unreadable "
                    f"or not in the correct schema version of {self._config.patchinfo_file_schema_version}."
                )
            case StaleStatus.PATCH_CHANGED:
                return f"The .{self._config.patch_file_ext} file was modified since last applied."
            case StaleStatus.SRC_CHANGED:
                return "The target file was modified since the patch was last applied."

        raise ValueError(
            f"Unknown stale status: {status}. "
            f"Expected one of: {', '.join(s.name for s in StaleStatus)}"
        )


@dataclass(frozen=True)
class PatchApplyData:
    """Data required to apply a patch.

    Attributes:
        patch_path: Path to the patch file to apply
        patchinfo_path: Path to the corresponding .patchinfo file
        reason: string message explaining why this patch needs to be applied
    """

    patch_path: Path
    patchinfo_path: Path
    reason: str


@dataclass
class PatchApplyResult:
    """Result of a patch apply operation.

    Attributes:
        data: The original patch application data
        affected_files: List of files that were modified by the patch
        error: Error message if the patch application failed, None if successful
    """

    data: PatchApplyData
    affected_files: List[AffectedFileData] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Whether the patch application was successful."""
        return self.error is None
