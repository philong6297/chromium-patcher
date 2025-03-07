from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional

from src.config import ProgramConfig

from .patch_info import AffectedFileData
from .patch_info import PatchInfoStaleStatus as StaleStatus


class PatchApplyReason(StrEnum):
    """Why a patch needs to be applied or was applied."""

    NO_PATCHINFO = (
        f"No corresponding .{ProgramConfig.patchinfo_file_ext} file was found."
    )

    PATCHINFO_OUTDATED = (
        f"The corresponding .{ProgramConfig.patchinfo_file_ext} file was unreadable "
        f"or not in the correct schema version of {ProgramConfig.patchinfo_file_schema_version}."
    )
    PATCH_CHANGED = (
        f"The .{ProgramConfig.patch_file_ext} file was modified since last applied."
    )
    PATCH_REMOVED = (
        f"The .{ProgramConfig.patch_file_ext} file was removed since last applied."
    )
    SRC_CHANGED = "The target file was modified since the patch was last applied."

    @staticmethod
    def from_stale_status(status: StaleStatus) -> str:
        """Convert a StaleStatus to a PatchApplyReason message.

        Args:
            status: The stale status to convert

        Returns:
            string message explaining the status

        Raises:
            ValueError: If the status is not a recognized StaleStatus value
        """
        match status:
            case StaleStatus.NONE:
                return "None"
            case StaleStatus.NO_PATCHINFO:
                return PatchApplyReason.NO_PATCHINFO
            case StaleStatus.PATCHINFO_OUTDATED:
                return PatchApplyReason.PATCHINFO_OUTDATED
            case StaleStatus.PATCH_CHANGED:
                return PatchApplyReason.PATCH_CHANGED
            case StaleStatus.SRC_CHANGED:
                return PatchApplyReason.SRC_CHANGED

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
    """Result of a patch application operation.

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
