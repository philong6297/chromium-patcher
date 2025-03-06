import argparse
import logging
import os

from command_apply_patches import command_apply_patches
from command_generate_patches import command_generate_patches
from config import ProgramConfig


def main() -> None:
    repo_dirs_list = "  - ".join(
        f"{'/'.join(path)}{os.linesep}" for path in ProgramConfig.REPO_DIRS
    )

    parser = argparse.ArgumentParser(
        description=(
            f"Manage patches from {ProgramConfig.PATCHES_DIR.as_posix()}{os.linesep}"
            f"for Chromium-based project {ProgramConfig.CHROMIUM_SRC_DIR.as_posix()}{os.linesep}"
            f"Repository directories:{os.linesep}"
            f"{repo_dirs_list}"
        )
    )
    parser.add_argument(
        "--print-report",
        action="store_true",
        default=True,
        help="Enable logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # main.py apply_patches
    subparsers.add_parser("apply_patches", help="Apply patches to the project")

    # main.py generate_patches
    subparsers.add_parser(
        "generate_patches", help="Generate patches from modified files"
    )

    args = parser.parse_args()

    # Log in other modules will use this configuration
    logging.basicConfig(
        level=logging.INFO if args.print_report else logging.ERROR,
        format="%(levelname)s:%(filename)s:%(lineno)d:%(message)s",
    )

    if args.command == "apply_patches":
        command_apply_patches(should_print_report=args.print_report)
    elif args.command == "generate_patches":
        command_generate_patches()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
