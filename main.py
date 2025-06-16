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
    Simple version comparison (major.minor.patch). Extend as needed.

    Args:
        config_version (str): The version specified in the configuration file.
        app_version (str): The application's current version.

    Returns:
        bool: True if the configuration version is compatible, False otherwise.

    Raises:
        VersionIncompatibilityError: If the version is not compatible.
    """
    try:
        config_major, config_minor, config_patch = map(int, config_version.split("."))
        app_major, app_minor, app_patch = map(int, app_version.split("."))

        if config_major > app_major:
            raise VersionIncompatibilityError(
                f"Configuration version {config_version} is not compatible with application version {app_version} (Major version mismatch)."
            )
        elif config_major == app_major and config_minor > app_minor:
             raise VersionIncompatibilityError(
                f"Configuration version {config_version} is not compatible with application version {app_version} (Minor version mismatch)."
            )
        
        logging.info(f"Configuration version {config_version} is compatible with application version {app_version}.")
        return True
    except ValueError:
        logging.error("Invalid version format. Expected major.minor.patch.")
        raise
    except VersionIncompatibilityError as e:
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
        config_version = config_data.get(args.version_key)

        if not config_version:
            logging.error(f"Version key '{args.version_key}' not found in configuration file.")
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