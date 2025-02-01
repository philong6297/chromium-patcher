from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Type, TypeVar

__all__ = [
    "calculate_file_checksum",
    "run_git",
    "validate_dict_keys_match_dataclass",
]

_logger = logging.getLogger(__name__)


def run_git(
    git_repo_dir: Path,
    git_args: List[str],
    verbose: bool = False,
    log_error: bool = True,
) -> str:
    """
    Run a git command in the specified repository.

    Args:
        git_repo_dir: Path to the git repository directory
        git_args: List of git command arguments to execute
        verbose: If True, print command output to logs
        log_error: If True, log error messages when command fails

    Returns:
        The stdout output of the git command as a string

    Raises:
        ValueError: If git_repo_dir doesn't exist or git_args is empty
        RuntimeError: If the git command fails or returns non-zero exit code
    """
    if not git_repo_dir.is_dir():
        raise ValueError(f"Git repository directory does not exist: {git_repo_dir}")

    if not git_args:
        raise ValueError("Git arguments cannot be empty")

    # Validate git installation
    if not shutil.which("git"):
        raise ValueError("Git executable not found in PATH")

    # Construct safe command list
    cmd = ["git"] + git_args

    try:
        result = subprocess.run(
            cmd,
            cwd=git_repo_dir,
            text=True,
            capture_output=True,
            check=True,  # raise an exception on non-zero return codes
        )
        if verbose:
            _logger.info(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as err:
        err_msg = (
            f"Git command failed in {git_repo_dir}:{os.linesep}"
            f"  Args: {' '.join(git_args)}{os.linesep}"
            f"  Stdout: {err.stdout.strip()}{os.linesep}"
            f"  Stderr: {err.stderr.strip()}"
        )
        if log_error:
            _logger.error(err_msg)

        raise RuntimeError(err_msg)


def calculate_file_checksum(file_path: Path, buffer_size: int = 8192) -> str:
    """
    Calculate SHA-256 checksum of a file.

    The function reads the file in chunks to efficiently handle large files
    without loading them entirely into memory.

    Args:
        file_path: Path to the file to calculate checksum for
        buffer_size: Size of chunks to read from file, in bytes

    Returns:
        Hexadecimal string representation of the file's SHA-256 checksum

    Raises:
        ValueError: If file_path doesn't exist or is not a file
        RuntimeError: If file access fails or checksum calculation fails
    """
    # Input validation
    if not file_path.exists():
        raise ValueError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    try:
        checksum_generator = hashlib.new("sha256")
        with open(file_path, "rb") as file:
            while chunk := file.read(buffer_size):
                checksum_generator.update(chunk)
        return checksum_generator.hexdigest()
    except Exception as err:
        raise RuntimeError(
            f"Checksum calculation failed for {file_path}: {err}"
        ) from err


T = TypeVar("T")


def validate_dict_keys_match_dataclass(
    data: Dict[str, Any], dataclass_type: Type[T]
) -> bool:
    """
    Validate that a dictionary contains all required fields of a dataclass.

    This function checks if all fields defined in the dataclass are present
    in the dictionary. It does not validate field types or extra fields
    in the dictionary.

    Args:
        data: Dictionary to validate
        dataclass_type: Type of dataclass to compare against

    Returns:
        True if the dictionary keys exactly match the dataclass fields, False otherwise

    Raises:
        ValueError: If dataclass_type is not a dataclass
    """
    if not is_dataclass(dataclass_type):
        return False

    # Get all field names from the dataclass
    dataclass_field_names = {field.name for field in fields(dataclass_type)}

    # Check if all dataclass fields are present in the dictionary
    if not dataclass_field_names.issubset(data.keys()):
        return False

    return True
