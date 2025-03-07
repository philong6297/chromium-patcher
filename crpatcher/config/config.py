# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import jsonschema.exceptions
import yaml
from jsonschema import validate

from crpatcher.config.schema import CRPATCHER_SCHEMA

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


@dataclass(frozen=True)
class ProgramConfig:
    # Example: src/
    chromium_src_dir: Path

    # Example: src/patches
    patches_dir: Path

    # List of repository subdirectories to be patched
    # Each repo dir should be relative to chromium_src_dir and use Posix style
    # Example: ["third_party", "search_engines_data", "resources"]
    repo_dirs: list[list[str]]

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

        with open(config_file, "r", encoding="utf-8") as f:
            try:
                config_data: dict[str, Any] = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ConfigYAMLError(
                    f"Invalid YAML format in {config_file_as_str}:{os.linesep}" f"{e}"
                )

        try:
            validate(instance=config_data, schema=CRPATCHER_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            raise ConfigValidationError(
                f"Config validation failed for {config_file_as_str}:{os.linesep}"
                f"{e.message}"
            )

        patchinfo_config = config_data.get("patchinfo_file", {})
        patch_config = config_data.get("patch_file", {})

        return cls(
            chromium_src_dir=Path(config_data["chromium_src_dir"]),
            patches_dir=Path(config_data["patches_dir"]),
            repo_dirs=config_data["submodule_dirs"],
            patchinfo_file_schema_version=patchinfo_config.get(
                "version", cls.patchinfo_file_schema_version
            ),
            patchinfo_file_encoding=patchinfo_config.get(
                "encoding", cls.patchinfo_file_encoding
            ),
            patchinfo_file_ext=patchinfo_config.get("ext", cls.patchinfo_file_ext),
            patch_file_ext=patch_config.get("ext", cls.patch_file_ext),
            patch_file_replacement_separator=patch_config.get(
                "replacement_separator", cls.patch_file_replacement_separator
            ),
        )
