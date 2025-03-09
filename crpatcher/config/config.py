# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

import os

# from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, Field, dataclass, field_validator

__all__ = [
    "ProgramConfig",
    "ConfigErrorBase",
    "ConfigYAMLError",
    "ConfigValidationError",
]


class ConfigErrorBase(Exception):
    """Base exception for configuration errors."""

    pass


class ConfigYAMLError(ConfigErrorBase):
    """Raised when the config file is not valid YAML."""

    pass


class ConfigValidationError(ConfigErrorBase):
    """Raised when the config fails schema validation."""

    pass


class PatchInfoConfig(BaseModel):
    """Configuration for patchinfo files."""

    version: int = Field(default=1, description="Version of the patchinfo file format")
    encoding: str = Field(default="utf-8", description="Encoding of the patchinfo file")
    ext: str = Field(default="patchinfo", description="Extension of the patchinfo file")


class PatchFileConfig(BaseModel):
    """Configuration for patch files."""

    ext: str = Field(default="patch", description="Extension of the patch file")
    replacement_separator: str = Field(
        default="-",
        description="Separator used when converting file paths to patch filenames",
    )


class ConfigModel(BaseModel):
    """Pydantic model for .crpatcher config file."""

    chromium_src_dir: str = Field(description="Path to Chromium source directory")
    patches_dir: str = Field(description="Path to patches directory")
    submodule_dirs: list[str] = Field(
        description="List of repository subdirectories to patch"
    )
    patchinfo_file: PatchInfoConfig = Field(default_factory=PatchInfoConfig)
    patch_file: PatchFileConfig = Field(default_factory=PatchFileConfig)

    @field_validator("chromium_src_dir", "patches_dir")
    @classmethod
    def validate_paths(cls, v: str) -> str:
        """Validate that paths are not empty and don't start with /."""
        if not v:
            raise ValueError("Path cannot be empty")
        if v.startswith("/"):
            raise ValueError("Path cannot start with /")
        return v


@dataclass(frozen=True)
class ProgramConfig:
    # Example: src/
    chromium_src_dir: Path

    # Example: src/patches
    patches_dir: Path

    # List of repository subdirectories to be patched
    # Each repo dir should be relative to chromium_src_dir and use Posix style
    # Example: ["third_party", "search_engines_data", "resources"]
    repo_dirs: list[str]

    # Configuration for patchinfo files
    patchinfo_file_schema_version: int = 1
    patchinfo_file_encoding: str = "utf-8"
    patchinfo_file_ext: str = "patchinfo"
    patch_file_ext: str = "patch"

    # Constants for patch filename formatting
    # Given base/win/embedded_i18n/create_string.cc
    # Its patch will be base-win-embedded_i18n-create_string.cc.patch
    patch_file_replacement_separator: str = "-"

    @classmethod
    def load(cls, config_file: Path | str) -> Self:
        """Load and validate a .crpatcher config file.

        Args:
            config_file: Path to the .crpatcher config file

        Returns:
            A validated ProgramConfig instance

        Raises:
            ConfigYAMLError: If the config file is not valid YAML
            ConfigValidationError: If the config file fails schema validation
            FileNotFoundError: If the config file does not exist
            PermissionError: If there are permission issues reading the file
            OSError: For other file operation errors
        """
        config_file = Path(config_file)
        config_file_as_str = config_file.as_posix()

        if not config_file.is_file():
            raise FileNotFoundError(f"File not found: {config_file_as_str}")

        try:
            with config_file.open("r", encoding="utf-8") as f:
                config_data: dict[str, Any] = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigYAMLError(
                f"Invalid YAML format in {config_file_as_str}:{os.linesep}" f"{e}"
            )

        try:
            config = ConfigModel.model_validate(config_data)
        except Exception as e:
            raise ConfigValidationError(
                f"Config validation failed for {config_file_as_str}:{os.linesep}" f"{e}"
            )

        return cls(
            chromium_src_dir=Path(config.chromium_src_dir),
            patches_dir=Path(config.patches_dir),
            repo_dirs=config.submodule_dirs,
            patchinfo_file_schema_version=config.patchinfo_file.version,
            patchinfo_file_encoding=config.patchinfo_file.encoding,
            patchinfo_file_ext=config.patchinfo_file.ext,
            patch_file_ext=config.patch_file.ext,
            patch_file_replacement_separator=config.patch_file.replacement_separator,
        )
