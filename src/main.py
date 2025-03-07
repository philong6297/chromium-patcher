# Copyright 2025 Phi-Long Le. All rights reserved.
# Use of this source code is governed by a MIT license that can be
# found in the LICENSE file.

import argparse
import logging
import sys
from pathlib import Path

from src.command_apply_patches import command_apply_patches
from src.command_generate_patches import command_generate_patches
from src.config import ProgramConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage patches for Chromium-based project submodules."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the .crpatcher config file",
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

    try:
        # Load config first
        config = ProgramConfig.load(args.config)

        # Log in other modules will use this configuration
        logging.basicConfig(
            level=logging.INFO if args.print_report else logging.ERROR,
            format="%(levelname)s:%(filename)s:%(lineno)d:%(message)s",
        )

        if args.command == "apply_patches":
            command_apply_patches(config=config, should_print_report=args.print_report)
        elif args.command == "generate_patches":
            command_generate_patches(config=config)
        else:
            parser.print_help()

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
