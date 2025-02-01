from dataclasses import dataclass
from pathlib import Path

__all__ = ["ProgramConfig"]


@dataclass(frozen=True)
class ProgramConfig:

    PATCHINFO_FILE_SCHEMA_VERSION = 1

    PATCHINFO_FILE_ENCODING = "utf-8"

    PATCHINFO_FILE_EXT = "patchinfo"

    PATCH_FILE_EXT = "patch"

    # Constants for patch filename formatting
    # Given base/win/embedded_i18n/create_string.cc
    # Its patch will be base-win-embedded_i18n-create_string.cc.patch
    PATCH_FILE_REPLACEMENT_SEPARATOR = "-"

    # project src dir: src/
    # tools/longlp/apply_patches/config.py
    CONFIG_FILE_PATH = Path(__file__)

    # src/
    CHROMIUM_SRC_DIR = CONFIG_FILE_PATH.parent.parent.parent.parent

    # src/patches
    PATCHES_DIR = CHROMIUM_SRC_DIR.joinpath("patches")

    # List of repository subdirectories to be patched
    REPO_DIRS = [
        # patches for third_party/search_engines_data/resources
        ["third_party", "search_engines_data", "resources"],
    ]
