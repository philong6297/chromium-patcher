# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from crpatcher.config.config import (
    ConfigValidationError,
    ConfigYAMLError,
    ProgramConfig,
)


@pytest.fixture
def valid_config_data() -> dict[str, Any]:
    """Create a valid config data dictionary."""
    return {
        "chromium_src_dir": "src",
        "patches_dir": "patches",
        "submodule_dirs": ["one_level_dir", "two/level_dir", "three/level/dir"],
        "patchinfo_file": {
            "version": 1,
            "encoding": "utf-8",
            "ext": ".patchinfo",
        },
        "patch_file": {
            "ext": ".patch",
            "replacement_separator": "-",
        },
    }


@pytest.fixture
def config_file(tmp_path: Path, valid_config_data: dict[str, Any]) -> Path:
    """Create a temporary config file with valid data."""
    config_path = tmp_path / ".crpatcher"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(valid_config_data, f)
    return config_path


def test_load_valid_config(config_file: Path) -> None:
    """Test loading a valid config file."""
    config = ProgramConfig.load(config_file)

    assert config.chromium_src_dir == Path("src")
    assert config.patches_dir == Path("patches")
    assert config.repo_dirs == ["one_level_dir", "two/level_dir", "three/level/dir"]
    assert config.patchinfo_file_schema_version == 1
    assert config.patchinfo_file_encoding == "utf-8"
    assert config.patchinfo_file_ext == ".patchinfo"
    assert config.patch_file_ext == ".patch"
    assert config.patch_file_replacement_separator == "-"


def test_load_with_defaults(config_file: Path) -> None:
    """Test loading a config file with minimal required fields."""
    # Overwrite with minimal config
    minimal_config = {
        "chromium_src_dir": "src",
        "patches_dir": "patches",
        "submodule_dirs": ["one_level_dir", "two/level_dir", "three/level/dir"],
    }
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(minimal_config, f)

    config = ProgramConfig.load(config_file)

    # Check required fields
    assert config.chromium_src_dir == Path("src")
    assert config.patches_dir == Path("patches")
    assert config.repo_dirs == ["one_level_dir", "two/level_dir", "three/level/dir"]

    # Check default values
    assert config.patchinfo_file_schema_version == 1
    assert config.patchinfo_file_encoding == "utf-8"
    assert config.patchinfo_file_ext == "patchinfo"
    assert config.patch_file_ext == "patch"
    assert config.patch_file_replacement_separator == "-"


def test_load_nonexistent_file() -> None:
    """Test loading a nonexistent config file."""
    with pytest.raises(FileNotFoundError):
        ProgramConfig.load("nonexistent.crpatcher")


def test_load_invalid_yaml(config_file: Path) -> None:
    """Test loading a config file with invalid YAML."""
    with open(config_file, "w", encoding="utf-8") as f:
        f.write("invalid: yaml: content: - - -")

    with pytest.raises(ConfigYAMLError) as exc_info:
        ProgramConfig.load(config_file)
    assert "Invalid YAML format" in str(exc_info.value)


def test_load_invalid_schema(config_file: Path) -> None:
    """Test loading a config file that fails schema validation."""
    invalid_config = {
        "patches_dir": "patches",  # Missing required field
        "submodule_dirs": "not_an_array",  # Wrong type
    }
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(invalid_config, f)

    with pytest.raises(ConfigValidationError) as exc_info:
        ProgramConfig.load(config_file)
    assert "Config validation failed" in str(exc_info.value)


def test_load_empty_file(config_file: Path) -> None:
    """Test loading an empty config file."""
    with open(config_file, "w", encoding="utf-8") as f:
        f.write("")

    with pytest.raises(ConfigYAMLError) as exc_info:
        ProgramConfig.load(config_file)
    assert "Invalid YAML format" in str(exc_info.value)


def test_load_permission_error(tmp_path: Path) -> None:
    """Test loading a config file with permission issues."""
    config_file = tmp_path / ".crpatcher"
    config_file.touch()
    os.chmod(config_file, 0o000)  # Remove all permissions

    with pytest.raises(PermissionError):
        ProgramConfig.load(config_file)

    # Restore permissions for cleanup
    os.chmod(config_file, 0o644)
