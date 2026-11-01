#!/usr/bin/env python3

import argparse
import logging
import json
import yaml
import sys
import os
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define custom exception for version incompatibility
class VersionIncompatibilityError(Exception):
    """Custom exception raised when configuration version is incompatible."""
    pass

def setup_argparse() -> argparse.ArgumentParser:
    """
    Sets up the argument parser for the command-line interface.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Checks if the configuration file version is compatible with the application version."
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        required=True,
        help="Path to the configuration file."
    )
    parser.add_argument(
        "-a",
        "--app-version",
        dest="app_version",
        required=True,
        help="The version of the running application (e.g., 1.2.3)."
    )
    parser.add_argument(
        "-k",
        "--version-key",
        dest="version_key",
        default="version",
        help="The key in the configuration file that holds the version (default: 'version')."
    )
    parser.add_argument(
        "-t",
        "--config-type",
        dest="config_type",
        choices=["json", "yaml"],
        required=True,
        help="The type of the configuration file (json or yaml)."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging."
    )
    return parser

def load_config(config_file: str, config_type: str) -> Dict[str, Any]:
    """
    Loads the configuration file based on the specified type (JSON or YAML).

    Args:
        config_file (str): Path to the configuration file.
        config_type (str): Type of the configuration file (json or yaml).

    Returns:
        Dict[str, Any]: The configuration data as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the configuration type is invalid.
        json.JSONDecodeError: If the JSON file is invalid.
        yaml.YAMLError: If the YAML file is invalid.
    """
    try:
        with open(config_file, "r") as f:
            if config_type == "json":
                try:
                    config_data = json.load(f)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON file: {e}")
                    raise
            elif config_type == "yaml":
                try:
                    config_data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    logging.error(f"Error decoding YAML file: {e}")
                    raise
            else:
                raise ValueError("Invalid configuration type. Must be 'json' or 'yaml'.")

        logging.debug(f"Successfully loaded config file: {config_file}")
        return config_data
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_file}")
        raise
    except ValueError as e:
        logging.error(e)
        raise

def is_version_compatible(config_version: str, app_version: str) -> bool:
    """
    Checks if the configuration version is compatible with the application version.
    Rule (major.minor.patch): the major versions must be equal, and the
    configuration must not be newer than the application in its minor or
    patch component. Any older configuration within the same major
    version is accepted, with no lower limit.

    Args:
        config_version (str): The version specified in the configuration file.
        app_version (str): The application's current version.

    Returns:
        bool: True if the configuration version is compatible, False otherwise.

    Raises:
        VersionIncompatibilityError: If the version is not compatible.
    """
    def parse_version(version, label):
        if not isinstance(version, str):
            raise ValueError(
                f"Invalid version format: {label} version must be a string in "
                f"major.minor.patch format, got {type(version).__name__}."
            )
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid version format. Expected major.minor.patch.")
        try:
            # int() is more forgiving than the format I claim to enforce:
            # it accepts a leading plus, surrounding spaces, underscores
            # between digits, and negative numbers, so 1.-2.3 and 1. 2.3
            # both parse here as versions. What I actually require is
            # three dot separated pieces that int() will swallow.
            return tuple(int(part) for part in parts)
        except ValueError:
            raise ValueError("Invalid version format. Expected major.minor.patch.")

    try:
        config_major, config_minor, config_patch = parse_version(config_version, "Configuration")
        app_major, app_minor, app_patch = parse_version(app_version, "Application")

        # Compatibility rule: the major versions must be equal, and the
        # configuration version must not be newer than the application
        # version in its minor or patch component. Any older configuration
        # within the same major version is accepted, with no lower limit.
        if config_major != app_major:
            raise VersionIncompatibilityError(
                f"Configuration version {config_version} is not compatible with application version {app_version} (Major version mismatch: major versions must be equal)."
            )
        # Within a major version there is no floor. A configuration
        # written for the very first release of a major line is
        # accepted against the last release of that line, however
        # much the format grew in between, because only being newer
        # than the application is treated as a hazard.
        if (config_minor, config_patch) > (app_minor, app_patch):
            raise VersionIncompatibilityError(
                f"Configuration version {config_version} is not compatible with application version {app_version} (Configuration version is newer than the application version in its minor or patch component)."
            )

        logging.info(f"Configuration version {config_version} is compatible with application version {app_version}.")
        return True
    except ValueError as e:
        logging.error(str(e))
        raise
    except VersionIncompatibilityError as e:
        # This function never returns False, despite its name and
        # its docstring. Incompatibility travels as this exception,
        # and main is written around that; a library caller testing
        # the return value of a compatible looking call gets an
        # exception for the incompatible case instead.
        logging.warning(e)
        raise

def main() -> None:
    """
    Main function to parse arguments, load configuration, and check version compatibility.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")

    try:
        config_data = load_config(args.config_file, args.config_type)

        if not isinstance(config_data, dict):
            logging.error(
                f"Invalid config format: the top-level document in '{args.config_file}' "
                f"must be a mapping of keys to values, got {type(config_data).__name__}."
            )
            sys.exit(1)

        # The key is looked up at the top level only, under its exact
        # name. A version nested in a metadata section, where plenty
        # of formats keep it, reads as missing here, and a dotted key
        # name is a literal name to me, not a path.
        config_version = config_data.get(args.version_key)

        if config_version is None or config_version == "":
            logging.error(f"Version key '{args.version_key}' not found in configuration file.")
            sys.exit(1)

        # YAML makes this branch common: an unquoted version with
        # two components, 1.2, parses as a float, and even a three
        # part version can arrive as a number if it was written with
        # a trailing zero the parser folded away. The hint about
        # quoting is the whole remedy, and it is buried in this log
        # line rather than in the help text.
        if not isinstance(config_version, str):
            logging.error(
                f"Invalid version format: the value of version key '{args.version_key}' "
                f"must be a string in major.minor.patch format, got {type(config_version).__name__}. "
                "Quote the version in the configuration file if needed."
            )
            sys.exit(1)

        is_version_compatible(config_version, args.app_version)
        print("Configuration version is compatible.")

    except FileNotFoundError:
        sys.exit(1)
    except ValueError:
        sys.exit(1)
    except VersionIncompatibilityError:
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# Usage Examples:
# 1. Check compatibility with a JSON config:
#    python misconfig_checker.py -c config.json -a 1.0.0 -t json -k version
#
# 2. Check compatibility with a YAML config:
#    python misconfig_checker.py -c config.yaml -a 1.2.0 -t yaml -k config_version
#
# 3.  Run with verbose logging for debugging
#    python misconfig_checker.py -c config.yaml -a 1.2.0 -t yaml -k config_version -v