#!/usr/bin/env python3
"""
GT Logs Helper
Uploads and downloads Redis Support packages to/from S3 buckets.
Generates S3 bucket URLs and AWS CLI commands for Redis Support packages.
"""

VERSION = "1.7.3"

import argparse
import configparser
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

# For immediate keypress detection (ESC without Enter)
if TYPE_CHECKING:
    import termios
    import tty
    IMMEDIATE_INPUT_AVAILABLE: bool
else:
    try:
        import termios
        import tty
        IMMEDIATE_INPUT_AVAILABLE = True
    except ImportError:
        IMMEDIATE_INPUT_AVAILABLE = False
        # Define dummy modules for runtime when not available
        class _DummyModule:
            def __getattr__(self, name: str) -> Any:
                raise ImportError(f"termios/tty not available on this platform")
        termios = _DummyModule()  # type: ignore
        tty = _DummyModule()  # type: ignore


class UserExitException(Exception):
    """Raised when user explicitly exits via ESC or exit commands."""
    pass


class UpdateCheckException(Exception):
    """Raised when Ctrl+U is pressed to trigger update check."""
    pass


def check_for_updates(timeout=5):
    """Check GitHub for latest release version.

    Args:
        timeout: API request timeout in seconds

    Returns:
        dict with 'available', 'latest_version', 'download_url', 'release_notes'
        or None if check fails
    """
    try:
        url = "https://api.github.com/repos/markotrapani/gtlogs-helper/releases/latest"
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3+json')

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))

        latest_version = data['tag_name'].lstrip('v')  # Remove 'v' prefix if present
        current_version = VERSION

        # Proper semantic version comparison - only update if remote is newer
        def version_tuple(v):
            return tuple(map(int, v.split('.')))

        try:
            update_available = version_tuple(latest_version) > version_tuple(current_version)
        except (ValueError, AttributeError):
            # Fall back to string comparison if version parsing fails
            update_available = latest_version != current_version

        # Get release notes (first 3 lines of body)
        release_notes = []
        if data.get('body'):
            lines = data['body'].strip().split('\n')
            release_notes = [line.strip() for line in lines[:3] if line.strip()]

        # Get download URL for the Python script
        download_url = f"https://raw.githubusercontent.com/markotrapani/gtlogs-helper/{data['tag_name']}/gtlogs-helper.py"

        return {
            'available': update_available,
            'current_version': current_version,
            'latest_version': latest_version,
            'download_url': download_url,
            'release_notes': release_notes
        }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError) as e:
        # Fail silently - user might be offline
        return None
    except Exception as e:
        # Log unexpected errors but don't crash
        print(f"⚠️  Update check failed: {e}", file=sys.stderr)
        return None


def perform_self_update(download_url, latest_version):
    """Download and install update, with backup and error handling.

    Args:
        download_url: URL to download new version from
        latest_version: Version string for logging

    Returns:
        True if successful, False otherwise
    """
    script_path = os.path.abspath(__file__)
    backup_path = script_path + '.backup'
    temp_path = script_path + '.tmp'

    try:
        print(f"\n📥 Downloading v{latest_version}...")

        # Download new version to temporary file
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            new_content = response.read()

        with open(temp_path, 'wb') as f:
            f.write(new_content)

        print(f"💾 Backing up current version to {os.path.basename(backup_path)}")

        # Backup current version
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(script_path, backup_path)

        # Install new version
        os.rename(temp_path, script_path)

        # Make executable
        os.chmod(script_path, 0o755)

        print(f"✅ Update successful! (v{latest_version})")
        print("Please restart the script to use the new version.\n")
        return True

    except urllib.error.HTTPError as e:
        print(f"❌ Download failed: HTTP {e.code} {e.reason}", file=sys.stderr)
        rollback_update(script_path, backup_path, temp_path)
        return False
    except urllib.error.URLError as e:
        print(f"❌ Download failed: {e.reason}", file=sys.stderr)
        rollback_update(script_path, backup_path, temp_path)
        return False
    except OSError as e:
        print(f"❌ File operation failed: {e}", file=sys.stderr)
        rollback_update(script_path, backup_path, temp_path)
        return False
    except Exception as e:
        print(f"❌ Unexpected error during update: {e}", file=sys.stderr)
        rollback_update(script_path, backup_path, temp_path)
        return False


def rollback_update(script_path, backup_path, temp_path):
    """Rollback failed update by restoring backup.

    Args:
        script_path: Path to the script file
        backup_path: Path to backup file
        temp_path: Path to temporary download file
    """
    try:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Restore backup if we created one
        if os.path.exists(backup_path) and not os.path.exists(script_path):
            os.rename(backup_path, script_path)
            print("✓ Rolled back to previous version", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Rollback failed: {e}", file=sys.stderr)
        print(f"⚠️  Manual recovery: restore from {backup_path}", file=sys.stderr)


def prompt_for_update(update_info):
    """Prompt user to install update.

    Args:
        update_info: Dictionary from check_for_updates()

    Returns:
        True if user wants to update, False otherwise
    """
    print(f"\n📦 Update available: v{update_info['current_version']} → v{update_info['latest_version']}")

    if update_info['release_notes']:
        print("   Changes:")
        for note in update_info['release_notes']:
            print(f"   - {note}")

    try:
        while True:
            response = input_with_esc_detection("\nUpdate now? (Y/n): ", auto_submit_chars=['y', 'n']).strip().lower()

            # Default to 'y' if user presses Enter
            if not response:
                response = 'y'

            if response == 'y':
                return perform_self_update(update_info['download_url'], update_info['latest_version'])
            elif response == 'n':
                print("\nUpdate cancelled.\n")
                return False
            else:
                print("❌ Invalid choice. Please enter Y or n\n")
    except (UserExitException, KeyboardInterrupt):
        print("\n👋 Exiting...\n")
        sys.exit(0)


def parse_aws_progress(line):
    """Parse AWS CLI progress output.

    Example AWS CLI output:
    "Completed 256.0 KiB/1.5 MiB (2.5 MiB/s) with 1 file(s) remaining"

    Returns:
        tuple: (completed_bytes, total_bytes, speed_str) or (None, None, None)
    """
    # Match pattern: "Completed X/Y (Z/s)"
    match = re.search(r'Completed\s+([\d.]+\s+\w+)/([\d.]+\s+\w+)\s+\(([\d.]+\s+\w+/s)\)', line)
    if match:
        completed_str = match.group(1)
        total_str = match.group(2)
        speed_str = match.group(3)

        # Convert to bytes
        completed_bytes = convert_to_bytes(completed_str)
        total_bytes = convert_to_bytes(total_str)

        return completed_bytes, total_bytes, speed_str
    return None, None, None


def convert_to_bytes(size_str):
    """Convert size string like '256.0 KiB' to bytes.

    Args:
        size_str: Size string like "256.0 KiB", "1.5 MiB", "3.2 GiB"

    Returns:
        int: Size in bytes
    """
    units = {
        'B': 1,
        'KiB': 1024,
        'MiB': 1024**2,
        'GiB': 1024**3,
        'TiB': 1024**4,
        'KB': 1000,
        'MB': 1000**2,
        'GB': 1000**3,
        'TB': 1000**4,
    }

    parts = size_str.strip().split()
    if len(parts) != 2:
        return 0

    try:
        value = float(parts[0])
        unit = parts[1]
        return int(value * units.get(unit, 1))
    except (ValueError, KeyError):
        return 0


def format_size(bytes_size):
    """Format bytes to human-readable size.

    Args:
        bytes_size: Size in bytes

    Returns:
        str: Formatted size like "1.5 MB", "256 KB"
    """
    if bytes_size == 0:
        return "0 B"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def display_progress_bar(completed: int, total: int, speed_str: str = "", bar_length: int = 40) -> None:
    """Display a progress bar.

    Args:
        completed: Completed bytes
        total: Total bytes
        speed_str: Speed string like "2.5 MB/s"
        bar_length: Length of progress bar in characters
    """
    if total == 0:
        return

    percentage = min(100, int((completed / total) * 100))
    filled_length = int(bar_length * completed // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    # Format sizes
    completed_str = format_size(completed)
    total_str = format_size(total)

    # Calculate ETA if we have speed
    eta_str = ""
    if speed_str:
        try:
            # Extract speed value (e.g., "2.5 MB/s" -> 2.5 MB/s)
            speed_match = re.search(r'([\d.]+)\s+(\w+)/s', speed_str)
            if speed_match:
                speed_value = float(speed_match.group(1))
                speed_unit = speed_match.group(2)
                speed_bytes = convert_to_bytes(f"{speed_value} {speed_unit}")

                if speed_bytes > 0:
                    remaining_bytes = total - completed
                    eta_seconds = remaining_bytes / speed_bytes

                    if eta_seconds < 60:
                        eta_str = f"| ETA: {int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        eta_str = f"| ETA: {int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
                    else:
                        hours = int(eta_seconds / 3600)
                        minutes = int((eta_seconds % 3600) / 60)
                        eta_str = f"| ETA: {hours}h {minutes}m"
        except (ValueError, ZeroDivisionError):
            pass

    # Display progress bar (pad with spaces to clear previous longer lines)
    progress_line = f"\r   [{bar}] {percentage}% | {completed_str}/{total_str} | {speed_str} {eta_str}"
    print(f"{progress_line:<120}", end='', flush=True)


class GTLogsHelper:
    """Helps with GT Logs S3 uploads, downloads, and URL generation."""

    BUCKET_BASE = "s3://gt-logs/exa-to-gt"
    CONFIG_FILE = os.path.expanduser("~/.gtlogs-config.ini")
    HISTORY_FILE = os.path.expanduser("~/.gtlogs-history.json")
    STATE_FILE = os.path.expanduser("~/.gtlogs-state.json")
    MAX_HISTORY_ENTRIES = 20
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1  # seconds

    def __init__(self, debug=False):
        self.config = self._load_config()
        self.history = self._load_history()
        self.current_state = None  # Active operation state
        self.debug = debug  # Enable debug output

    def _load_config(self):
        """Load configuration from config file."""
        config = configparser.ConfigParser()
        if os.path.exists(self.CONFIG_FILE):
            config.read(self.CONFIG_FILE)
        return config

    def _save_config(self, aws_profile):
        """Save AWS profile to config file."""
        if not self.config.has_section('default'):
            self.config.add_section('default')
        self.config.set('default', 'aws_profile', aws_profile)

        with open(self.CONFIG_FILE, 'w') as f:
            self.config.write(f)
        print(f"✓ Default AWS profile saved to {self.CONFIG_FILE}")

    def get_default_aws_profile(self):
        """Get the default AWS profile from config."""
        try:
            return self.config.get('default', 'aws_profile')
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def get_default_download_dir(self):
        """Get the default download directory from config."""
        try:
            path = self.config.get('default', 'download_dir')
            return os.path.expanduser(path) if path else None
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None

    def _save_download_dir(self, download_dir):
        """Save default download directory to config file."""
        if not self.config.has_section('default'):
            self.config.add_section('default')
        # Store with ~ for portability if it's in home directory
        home = os.path.expanduser("~")
        if download_dir.startswith(home):
            download_dir = "~" + download_dir[len(home):]
        self.config.set('default', 'download_dir', download_dir)

        with open(self.CONFIG_FILE, 'w') as f:
            self.config.write(f)
        print(f"✓ Default download directory saved to {self.CONFIG_FILE}")

    def get_smart_download_path(self, s3_key, filename=None):
        """Generate smart download path based on default dir and ZD ticket.

        If a default download directory is configured and a Zendesk ID can be
        extracted from the S3 key, returns a path like:
        {default_dir}/{zendesk_number}/{filename}

        Args:
            s3_key: The S3 key (e.g., "zendesk-tickets/ZD-150576/file.tar.gz")
            filename: Optional filename override (defaults to basename of s3_key)

        Returns:
            Tuple of (suggested_path, zendesk_number or None)
            Returns (None, None) if no default dir configured
        """
        default_dir = self.get_default_download_dir()
        if not default_dir:
            return None, None

        # Extract filename from key if not provided
        if not filename:
            filename = os.path.basename(s3_key.rstrip('/'))
            if not filename:
                return None, None

        # Try to extract Zendesk ID from the S3 key
        # Patterns: ZD-123456, zendesk-tickets/ZD-123456/, exa-to-gt/ZD-123456-RED-xxx/
        zd_match = re.search(r'ZD-(\d+)', s3_key, re.IGNORECASE)
        if zd_match:
            zd_number = zd_match.group(1)
            smart_path = os.path.join(default_dir, zd_number, filename)
            return smart_path, zd_number

        # No ZD found, just use default dir with filename
        return os.path.join(default_dir, filename), None

    def _load_history(self):
        """Load input history from history file."""
        if os.path.exists(self.HISTORY_FILE):
            try:
                with open(self.HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted, start fresh
                pass

        # Default empty history structure
        return {
            'zendesk_id': [],
            'jira_id': [],
            'file_path': [],
            'aws_profile': []
        }

    def _save_history(self):
        """Save input history to history file."""
        try:
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump(self.history, f, indent=2)
        except IOError as e:
            # Non-critical error, just warn
            print(f"⚠️  Warning: Could not save history: {e}")

    def add_to_history(self, field_name, value):
        """Add a validated value to history for a specific field.

        Args:
            field_name: One of 'zendesk_id', 'jira_id', 'file_path', 'aws_profile'
            value: The validated value to add
        """
        if not value or field_name not in self.history:
            return

        # Remove if already exists (to avoid duplicates)
        if value in self.history[field_name]:
            self.history[field_name].remove(value)

        # Add to front of list (most recent first)
        self.history[field_name].insert(0, value)

        # Limit history size
        self.history[field_name] = self.history[field_name][:self.MAX_HISTORY_ENTRIES]

    def get_history(self, field_name):
        """Get history list for a specific field.

        Args:
            field_name: One of 'zendesk_id', 'jira_id', 'file_path', 'aws_profile'

        Returns:
            List of historical values (most recent first)
        """
        return self.history.get(field_name, [])

    # State management for resume functionality

    def _load_state(self):
        """Load operation state from state file."""
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def _save_state(self):
        """Save operation state to state file."""
        if self.current_state is None:
            return

        try:
            # Update timestamp
            self.current_state['updated_at'] = datetime.utcnow().isoformat() + 'Z'

            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.current_state, f, indent=2)
        except IOError as e:
            print(f"⚠️  Warning: Could not save state: {e}")

    def _clean_state(self):
        """Remove state file after successful completion."""
        if os.path.exists(self.STATE_FILE):
            try:
                os.remove(self.STATE_FILE)
                self.current_state = None
            except IOError as e:
                print(f"⚠️  Warning: Could not remove state file: {e}")

    def _create_operation_state(self, operation, destination, files):
        """Create a new operation state.

        Args:
            operation: 'upload' or 'download'
            destination: S3 destination path
            files: List of file dictionaries with 'path', 'filename', 'size'

        Returns:
            State dictionary
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        session_id = f"{operation}_{destination.replace('s3://gt-logs/', '').replace('/', '_')}_{int(time.time())}"

        file_entries = []
        for f in files:
            file_entries.append({
                'path': f['path'],
                'filename': f['filename'],
                'size': f['size'],
                'status': 'pending',
                'attempts': 0,
                'last_error': None,
                'checksum': None
            })

        return {
            'session_id': session_id,
            'operation': operation,
            'started_at': timestamp,
            'updated_at': timestamp,
            'destination': destination,
            'files': file_entries
        }

    def _calculate_file_md5(self, filepath):
        """Calculate MD5 checksum of a file (for verification)."""
        md5_hash = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except IOError:
            return None

    def check_and_prompt_resume(self):
        """Check for incomplete operations and prompt user to resume.

        Returns:
            dict: State to resume, or None if no resume
        """
        state = self._load_state()

        if not state:
            return None

        # Calculate progress
        total = len(state['files'])
        completed = sum(1 for f in state['files'] if f['status'] == 'completed')
        failed = sum(1 for f in state['files'] if f['status'] == 'failed')
        pending = sum(1 for f in state['files'] if f['status'] == 'pending')

        print(f"\n⚠️  Found incomplete {state['operation']} operation:")
        print(f"   Destination: {state['destination']}")
        print(f"   Progress: {completed}/{total} completed, {failed} failed, {pending} pending")
        print(f"   Started: {state['started_at']}")

        # Prompt to resume
        try:
            response = input("\nResume this operation? [Y/n]: ").strip().lower()

            if response in ['', 'y', 'yes']:
                print("✅ Resuming operation...\n")
                return state
            else:
                # Ask if they want to delete the state file
                response = input("Delete state file and start fresh? [Y/n]: ").strip().lower()
                if response in ['', 'y', 'yes']:
                    self._clean_state()
                    print("✅ State file deleted\n")
                else:
                    print("⚠️  State file preserved. Use --clean-state to remove it.\n")
                return None
        except (KeyboardInterrupt, EOFError):
            print("\n\n⚠️  State file preserved. Use --clean-state to remove it.\n")
            return None

    @staticmethod
    def validate_zendesk_id(zd_id):
        """Validate and format Zendesk ID - must be numerical only."""
        zd_id = str(zd_id).strip()

        # If it starts with ZD- or zd-, extract the number part
        if zd_id.upper().startswith('ZD-'):
            zd_number = zd_id[3:]
        else:
            zd_number = zd_id

        # Validate that it's purely numerical
        if not zd_number.isdigit():
            raise ValueError("Invalid Zendesk ID: must be numerical only (e.g., 145980 or ZD-145980)")

        if len(zd_number) == 0:
            raise ValueError("Invalid Zendesk ID: cannot be empty")

        return f"ZD-{zd_number}"

    @staticmethod
    def validate_jira_id(jira_id):
        """Validate and format Jira ID - must be RED-# or MOD-# with numerical suffix."""
        # Check if it matches RED-# or MOD-# format
        jira_id = jira_id.upper().strip()

        # If it's just a number, we need to know the prefix
        if jira_id.isdigit():
            raise ValueError("Jira ID must include prefix (RED- or MOD-)")

        # Add hyphen if missing (e.g., RED172041 -> RED-172041)
        match = re.match(r'^(RED|MOD)(\d+)$', jira_id)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

        # Validate full format - must be RED-# or MOD-# with numerical suffix only
        if not re.match(r'^(RED|MOD)-\d+$', jira_id):
            raise ValueError("Invalid Jira ID: must be in format RED-# or MOD-# with numerical suffix (e.g., RED-172041 or MOD-12345)")

        return jira_id

    @staticmethod
    def validate_file_path(file_path: str | None) -> str | None:
        """Validate that the file path exists in the filesystem.

        Returns:
            str: The expanded file path if valid
            None: If file_path is empty or None

        Raises:
            ValueError: If the file doesn't exist or isn't a file
        """
        if not file_path:
            return None

        file_path = str(file_path).strip()
        if not file_path:
            return None

        # Expand user paths like ~/
        expanded_path = os.path.expanduser(file_path)

        # Check if file exists
        if not os.path.exists(expanded_path):
            # Show both original and expanded paths if they differ
            if expanded_path != file_path:
                raise ValueError(f"File does not exist: {file_path} (expanded to: {expanded_path})")
            else:
                raise ValueError(f"File does not exist: {file_path}")

        # Check if it's actually a file (not a directory)
        if not os.path.isfile(expanded_path):
            # Show both original and expanded paths if they differ
            if expanded_path != file_path:
                raise ValueError(f"Path is not a file: {file_path} (expanded to: {expanded_path})")
            else:
                raise ValueError(f"Path is not a file: {file_path}")

        return expanded_path

    @staticmethod
    def validate_directory_path(dir_path: str | None) -> str | None:
        """Validate that the directory path exists in the filesystem.

        Returns:
            str: The expanded directory path if valid
            None: If dir_path is empty or None

        Raises:
            ValueError: If the directory doesn't exist or isn't a directory
        """
        if not dir_path:
            return None

        dir_path = str(dir_path).strip()
        if not dir_path:
            return None

        # Expand user paths like ~/
        expanded_path = os.path.expanduser(dir_path)

        # Check if directory exists
        if not os.path.exists(expanded_path):
            # Show both original and expanded paths if they differ
            if expanded_path != dir_path:
                raise ValueError(f"Directory does not exist: {dir_path} (expanded to: {expanded_path})")
            else:
                raise ValueError(f"Directory does not exist: {dir_path}")

        # Check if it's actually a directory (not a file)
        if not os.path.isdir(expanded_path):
            # Show both original and expanded paths if they differ
            if expanded_path != dir_path:
                raise ValueError(f"Path is not a directory: {dir_path} (expanded to: {expanded_path})")
            else:
                raise ValueError(f"Path is not a directory: {dir_path}")

        return expanded_path

    @staticmethod
    def discover_files_in_directory(dir_path: str, include_patterns: Optional[list] = None,
                                   exclude_patterns: Optional[list] = None):
        """Recursively discover all files in a directory with pattern filtering.

        Args:
            dir_path: Root directory to scan
            include_patterns: List of glob patterns to include (e.g., ['*.tar.gz', '*.zip'])
            exclude_patterns: List of glob patterns to exclude (e.g., ['*.log', '*.tmp'])

        Returns:
            list: List of file paths relative to dir_path
        """
        import fnmatch

        discovered_files = []
        dir_path = os.path.abspath(dir_path)

        for root, dirs, files in os.walk(dir_path):
            # Filter directories if needed (to skip excluded dirs entirely)
            if exclude_patterns:
                dirs[:] = [d for d in dirs if not any(
                    fnmatch.fnmatch(d, pattern) for pattern in exclude_patterns
                )]

            for filename in files:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, dir_path)

                # Check exclude patterns first
                if exclude_patterns:
                    if any(fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(relative_path, pattern)
                           for pattern in exclude_patterns):
                        continue

                # Check include patterns
                if include_patterns:
                    if not any(fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(relative_path, pattern)
                              for pattern in include_patterns):
                        continue

                discovered_files.append(full_path)

        return discovered_files

    def generate_s3_path(self, zd_id, jira_id=None):
        """Generate the S3 bucket path.

        If jira_id is provided: s3://gt-logs/exa-to-gt/ZD-#-JIRA-#/
        If jira_id is None: s3://gt-logs/zendesk-tickets/ZD-#/
        """
        zd_formatted = self.validate_zendesk_id(zd_id)

        if jira_id:
            jira_formatted = self.validate_jira_id(jira_id)
            return f"{self.BUCKET_BASE}/{zd_formatted}-{jira_formatted}/"
        else:
            # ZD-only path for tickets without Jira
            return f"s3://gt-logs/zendesk-tickets/{zd_formatted}/"

    def generate_aws_command(self, zd_id, jira_id=None, support_package_path=None,
                           aws_profile=None):
        """Generate the full AWS CLI command."""
        s3_base_path = self.generate_s3_path(zd_id, jira_id)

        # Determine AWS profile with fallback to gt-logs
        if aws_profile is None:
            aws_profile = self.get_default_aws_profile() or "gt-logs"

        # Build command
        if support_package_path:
            # Validate file path - will raise ValueError if file doesn't exist
            validated_path = self.validate_file_path(support_package_path)

            # Type narrowing: validate_file_path returns str when input is non-empty
            # Use cast to tell type checker the value is definitely str here
            assert validated_path is not None, "validate_file_path should not return None for non-empty input"
            validated_path = cast(str, validated_path)

            package_path = Path(validated_path)
            package_name = package_path.name
            s3_full_path = f"{s3_base_path}{package_name}"

            cmd = f"aws s3 cp {validated_path} {s3_full_path}"
        else:
            s3_full_path = f"{s3_base_path}<support_package_name>"
            cmd = f"aws s3 cp <support_package_path> {s3_full_path}"

        # Add profile if specified
        if aws_profile:
            cmd += f" --profile {aws_profile}"

        return cmd, s3_full_path

    @staticmethod
    def check_sso_cache(aws_profile, debug=False):
        """Check if SSO token exists in local cache and is not expired.

        This is a fast local check that avoids network calls.

        Args:
            aws_profile: AWS profile name to check
            debug: Enable debug output

        Returns:
            True if valid cached token exists, False if no cache or expired, None if unsure
        """
        start_time = time.time()
        try:
            # Read AWS config to find SSO session
            config_path = Path.home() / '.aws' / 'config'
            if not config_path.exists():
                if debug:
                    print(f"   [DEBUG] No AWS config file found at {config_path} ({time.time() - start_time:.3f}s)")
                return None

            config = configparser.ConfigParser()
            config.read(config_path)

            # Profile name in config file is "profile <name>" for non-default profiles
            profile_section = f'profile {aws_profile}' if aws_profile != 'default' else 'default'

            if profile_section not in config:
                if debug:
                    print(f"   [DEBUG] Profile '{aws_profile}' not found in config ({time.time() - start_time:.3f}s)")
                return None

            # Check if this is an SSO profile
            if 'sso_session' not in config[profile_section]:
                if debug:
                    print(f"   [DEBUG] Profile '{aws_profile}' is not an SSO profile ({time.time() - start_time:.3f}s)")
                return None

            # Check SSO cache directory
            cache_dir = Path.home() / '.aws' / 'sso' / 'cache'
            if not cache_dir.exists():
                if debug:
                    print(f"   [DEBUG] SSO cache directory not found ({time.time() - start_time:.3f}s)")
                return False

            # Check all cache files for valid tokens
            now = datetime.now(timezone.utc)
            for cache_file in cache_dir.glob('*.json'):
                try:
                    with open(cache_file) as f:
                        cache_data = json.load(f)

                    # Check if token exists and hasn't expired
                    if 'accessToken' in cache_data and 'expiresAt' in cache_data:
                        # expiresAt is in ISO format like "2025-01-17T12:34:56Z"
                        expires_at = datetime.fromisoformat(cache_data['expiresAt'].replace('Z', '+00:00'))

                        if expires_at > now:
                            if debug:
                                print(f"   [DEBUG] Valid SSO token found in cache (expires {cache_data['expiresAt']}) ({time.time() - start_time:.3f}s)")
                            return True
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Skip invalid cache files
                    continue

            if debug:
                print(f"   [DEBUG] No valid SSO tokens found in cache ({time.time() - start_time:.3f}s)")
            return False

        except Exception as e:
            if debug:
                print(f"   [DEBUG] Error checking SSO cache: {e} ({time.time() - start_time:.3f}s)")
            return None

    @staticmethod
    def check_aws_authentication(aws_profile, debug=False):
        """Check if AWS profile is authenticated.

        Uses a two-step approach:
        1. Fast local SSO cache check (no network call)
        2. Network call to AWS STS if cache check is inconclusive

        Args:
            aws_profile: AWS profile name to check
            debug: Enable debug output

        Returns:
            True if authenticated, False otherwise
        """
        overall_start = time.time()
        if debug:
            print("   [DEBUG] Starting authentication check...")

        try:
            # Step 1: Check SSO cache first (fast, no network)
            cache_start = time.time()
            cache_result = GTLogsHelper.check_sso_cache(aws_profile, debug=debug)
            cache_time = time.time() - cache_start

            if cache_result is True:
                if debug:
                    print(f"   [DEBUG] ✓ Authenticated via SSO cache check (total: {time.time() - overall_start:.3f}s)")
                return True
            elif cache_result is False:
                if debug:
                    print(f"   [DEBUG] ✗ SSO cache expired or invalid (cache check: {cache_time:.3f}s)")
                return False

            # Step 2: Cache check inconclusive, fall back to network call
            if debug:
                print(f"   [DEBUG] SSO cache check inconclusive ({cache_time:.3f}s), trying network call...")

            network_start = time.time()
            cmd = ['aws', 'sts', 'get-caller-identity']
            if aws_profile:
                cmd.extend(['--profile', aws_profile])

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5  # Reduced from 10s to 5s
            )
            network_time = time.time() - network_start

            # Check if profile doesn't exist
            if result.returncode != 0 and b"could not be found" in result.stderr.lower():
                print(f"⚠️  AWS profile '{aws_profile}' does not exist.")
                print(f"   Please configure it with: aws configure sso --profile {aws_profile}")
                print(f"   Or use a different profile with -p flag")

            auth_status = result.returncode == 0
            if debug:
                status_symbol = "✓" if auth_status else "✗"
                print(f"   [DEBUG] {status_symbol} Network auth check complete (network: {network_time:.3f}s, total: {time.time() - overall_start:.3f}s)")

            return auth_status

        except subprocess.TimeoutExpired:
            timeout_msg = f"⚠️  Timeout while checking AWS authentication"
            if debug:
                timeout_msg += f" (after {time.time() - overall_start:.3f}s)"
            print(timeout_msg)
            return False
        except FileNotFoundError:
            print("❌ AWS CLI not found. Please install AWS CLI first.")
            return False

    @staticmethod
    def aws_sso_login(aws_profile):
        """Execute AWS SSO login for the specified profile.

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n🔐 Authenticating with AWS SSO (profile: {aws_profile})...")
            cmd = ['aws', 'sso', 'login', '--profile', aws_profile]

            result = subprocess.run(cmd, check=False)

            if result.returncode == 0:
                print("✓ AWS SSO authentication successful\n")
                return True
            else:
                print("❌ AWS SSO authentication failed\n")
                return False
        except FileNotFoundError:
            print("❌ AWS CLI not found. Please install AWS CLI first.\n")
            return False
        except Exception as e:
            print(f"❌ Error during AWS SSO login: {e}\n")
            return False

    def verify_s3_upload(self, s3_path, local_path, aws_profile):
        """Verify file was uploaded successfully to S3.

        Args:
            s3_path: Full S3 path (s3://bucket/key)
            local_path: Local file path
            aws_profile: AWS profile to use

        Returns:
            True if file exists in S3 and size matches, False otherwise
        """
        try:
            # Check if file exists in S3 and get its size
            cmd = f"aws s3 ls {s3_path} --profile {aws_profile}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return False

            # Parse S3 ls output: "2025-11-14 10:30:00    1048576 filename.tar.gz"
            # Extract file size
            try:
                parts = result.stdout.strip().split()
                if len(parts) >= 3:
                    s3_size = int(parts[2])
                    local_size = os.path.getsize(local_path)
                    return s3_size == local_size
            except (ValueError, OSError):
                pass

            return False
        except (subprocess.TimeoutExpired, Exception):
            return False

    def upload_with_retry(self, aws_command, s3_path=None, local_path=None,
                         aws_profile=None, max_retries=None, verify=False):
        """Execute S3 upload with automatic retry and exponential backoff.

        Args:
            aws_command: AWS CLI command to execute
            s3_path: Full S3 destination path (for verification)
            local_path: Local file path (for verification)
            aws_profile: AWS profile (for verification)
            max_retries: Maximum retry attempts (defaults to self.MAX_RETRIES)
            verify: Whether to verify upload after completion

        Returns:
            True if successful, False otherwise
        """
        if max_retries is None:
            max_retries = self.MAX_RETRIES

        for attempt in range(1, max_retries + 1):
            success = self.execute_s3_upload(aws_command)

            if success:
                # Optionally verify upload
                if verify and s3_path and local_path and aws_profile:
                    print("   🔍 Verifying upload...")
                    if self.verify_s3_upload(s3_path, local_path, aws_profile):
                        print("   ✅ Upload verified")
                        return True
                    else:
                        print("   ⚠️  Verification failed - file may not have uploaded correctly")
                        if attempt < max_retries:
                            success = False  # Force retry
                        else:
                            return False
                else:
                    return True

            if not success and attempt < max_retries:
                delay = min(self.INITIAL_RETRY_DELAY * (2 ** (attempt - 1)), 60)  # Max 60s
                print(f"   ⚠️  Upload failed. Retrying in {delay}s... (attempt {attempt}/{max_retries})")
                time.sleep(delay)
            elif not success:
                print(f"   ❌ Upload failed after {max_retries} attempts")
                return False

        return False

    @staticmethod
    def execute_s3_upload(aws_command):
        """Execute the AWS S3 cp command with progress tracking.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract filename for display
            filename = "file"
            if " -f " in aws_command or ".tar.gz" in aws_command or ".zip" in aws_command:
                parts = aws_command.split()
                for i, part in enumerate(parts):
                    if part == "cp" and i + 1 < len(parts):
                        filepath = parts[i + 1]
                        filename = os.path.basename(filepath.strip('"'))
                        break

            print(f"\n📤 Uploading: {filename}")
            print(f"   Command: {aws_command}\n")

            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                aws_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            last_progress = None
            output_lines = []

            # Read output line by line
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    output_lines.append(line)

                    # Parse progress from AWS CLI output
                    completed, total, speed_str = parse_aws_progress(line)

                    if completed and total:
                        # Display progress bar
                        display_progress_bar(completed, total, speed_str or "")
                        last_progress = (completed, total, speed_str or "")
                    elif last_progress:
                        # Continue showing last known progress
                        completed, total, speed_str = last_progress
                        display_progress_bar(completed, total, speed_str)

            # Wait for process to complete
            return_code = process.wait()

            # Ensure we show 100% on success
            if return_code == 0 and last_progress:
                _, total, speed_str = last_progress
                display_progress_bar(total, total, speed_str)

            print()  # New line after progress bar

            if return_code == 0:
                print("✅ Upload successful!\n")
                return True
            else:
                print(f"❌ Upload failed with exit code {return_code}\n")
                # Show last few lines of output for debugging
                if output_lines:
                    print("Last output:")
                    for line in output_lines[-5:]:
                        print(f"   {line.rstrip()}")
                    print()
                return False

        except Exception as e:
            print(f"\n❌ Error during upload: {e}\n")
            return False

    def execute_batch_upload(self, file_paths, zd_id, jira_id, aws_profile,
                            max_retries=None, verify=False, save_state=True):
        """Execute batch upload of multiple files to the same S3 destination.

        Args:
            file_paths: List of file paths to upload
            zd_id: Zendesk ticket ID (formatted)
            jira_id: Jira ticket ID (formatted, can be None)
            aws_profile: AWS profile to use
            max_retries: Maximum retry attempts per file (default: 3)
            verify: Verify uploads after completion (default: False)
            save_state: Save state for resume capability (default: True)

        Returns:
            tuple: (success_count, failure_count, results)
        """
        total_files = len(file_paths)
        success_count = 0
        failure_count = 0
        results = []

        # Generate S3 path (same for all files)
        s3_path = self.generate_s3_path(zd_id, jira_id)

        # Create or load state
        if save_state:
            files_info = []
            for fp in file_paths:
                try:
                    files_info.append({
                        'path': fp,
                        'filename': os.path.basename(fp),
                        'size': os.path.getsize(fp)
                    })
                except OSError:
                    files_info.append({
                        'path': fp,
                        'filename': os.path.basename(fp),
                        'size': 0
                    })

            self.current_state = self._create_operation_state('upload', s3_path, files_info)
            self._save_state()

        print(f"\n{'='*70}")
        print(f"Batch Upload: {total_files} file(s)")
        print(f"{'='*70}\n")
        print(f"S3 Destination: {s3_path}\n")

        for i, file_path in enumerate(file_paths, 1):
            filename = os.path.basename(file_path)
            print(f"[{i}/{total_files}] Uploading: {filename}")
            print(f"            From: {file_path}")

            # Update state
            if save_state and self.current_state:
                self.current_state['files'][i-1]['status'] = 'in_progress'
                self.current_state['files'][i-1]['attempts'] += 1
                self._save_state()

            # Generate command and S3 destination for this specific file
            cmd, file_s3_path = self.generate_aws_command(zd_id, jira_id, file_path, aws_profile)

            # Execute upload with retry
            success = self.upload_with_retry(
                cmd,
                s3_path=file_s3_path,
                local_path=file_path,
                aws_profile=aws_profile,
                max_retries=max_retries,
                verify=verify
            )

            if success:
                success_count += 1
                results.append(('success', filename))
                if save_state and self.current_state:
                    self.current_state['files'][i-1]['status'] = 'completed'
                    if verify:
                        self.current_state['files'][i-1]['checksum'] = self._calculate_file_md5(file_path)
                    self._save_state()
            else:
                failure_count += 1
                results.append(('failure', filename))
                if save_state and self.current_state:
                    self.current_state['files'][i-1]['status'] = 'failed'
                    self.current_state['files'][i-1]['last_error'] = 'Upload failed after retries'
                    self._save_state()

            # Add separator between uploads (except after last one)
            if i < total_files:
                print(f"{'-'*70}\n")

        # Print summary
        print(f"{'='*70}")
        print(f"Batch Upload Summary")
        print(f"{'='*70}")
        print(f"✅ Successful: {success_count}/{total_files}")
        print(f"❌ Failed: {failure_count}/{total_files}")

        if failure_count > 0:
            print(f"\nFailed files:")
            for status, filename in results:
                if status == 'failure':
                    print(f"  - {filename}")
        else:
            # Clean up state on complete success
            if save_state:
                self._clean_state()

        print(f"{'='*70}\n")

        return success_count, failure_count, results

    def execute_directory_upload(self, dir_path: str, zd_id: str, jira_id: Optional[str], aws_profile: str,
                                 include_patterns: Optional[list] = None, exclude_patterns: Optional[list] = None,
                                 dry_run: bool = False, max_retries: Optional[int] = None, verify: bool = False):
        """Execute upload of an entire directory to S3, preserving structure.

        Args:
            dir_path: Root directory to upload
            zd_id: Zendesk ticket ID (formatted)
            jira_id: Jira ticket ID (formatted, can be None)
            aws_profile: AWS profile to use
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
            dry_run: If True, only show what would be uploaded without uploading
            max_retries: Maximum retry attempts per file (default: 3)
            verify: Verify uploads after completion (default: False)

        Returns:
            tuple: (success_count, failure_count, results)
        """
        # Validate directory
        validated_dir = self.validate_directory_path(dir_path)
        if not validated_dir:
            print("❌ Invalid directory path\n")
            return 0, 0, []

        # Discover files
        print(f"\n🔍 Discovering files in: {validated_dir}")
        if include_patterns:
            print(f"   Include patterns: {', '.join(include_patterns)}")
        if exclude_patterns:
            print(f"   Exclude patterns: {', '.join(exclude_patterns)}")
        print()

        discovered_files = self.discover_files_in_directory(
            validated_dir, include_patterns, exclude_patterns
        )

        if not discovered_files:
            print("❌ No files found in directory\n")
            return 0, 0, []

        total_files = len(discovered_files)
        print(f"✅ Found {total_files} file(s)\n")

        # Generate S3 base path
        s3_base_path = self.generate_s3_path(zd_id, jira_id)

        # Get directory name for S3 structure
        dir_name = os.path.basename(os.path.abspath(validated_dir))

        # Show preview
        print(f"{'='*70}")
        print(f"Directory Upload {'(DRY RUN)' if dry_run else ''}")
        print(f"{'='*70}\n")
        print(f"Local directory: {validated_dir}")
        print(f"S3 destination: {s3_base_path}{dir_name}/")
        print(f"Total files: {total_files}\n")

        if dry_run:
            print("Files to be uploaded:")
            for file_path in discovered_files:
                # Calculate relative path for S3
                rel_path = os.path.relpath(file_path, os.path.dirname(validated_dir))
                s3_path = f"{s3_base_path}{rel_path}"
                file_size = os.path.getsize(file_path)
                print(f"  {format_size(file_size):>10} → {rel_path}")
            print(f"\n{'='*70}\n")
            print("🔍 Dry run complete. No files were uploaded.\n")
            return 0, 0, []

        # Ask for confirmation if not dry run
        print("Proceed with upload? (Y/n): ", end='', flush=True)
        try:
            response = input_with_esc_detection(prompt="")
            if response and response.lower() not in ['y', 'yes', '']:
                print("\n❌ Upload cancelled\n")
                return 0, 0, []
        except (UserExitException, KeyboardInterrupt):
            print("\n👋 Upload cancelled\n")
            return 0, 0, []

        # Upload files
        success_count = 0
        failure_count = 0
        results = []

        print(f"\n{'='*70}")
        print(f"Uploading {total_files} file(s)...")
        print(f"{'='*70}\n")

        for i, file_path in enumerate(discovered_files, 1):
            # Calculate relative path for S3 structure
            rel_path = os.path.relpath(file_path, os.path.dirname(validated_dir))
            s3_full_path = f"{s3_base_path}{rel_path}"

            print(f"[{i}/{total_files}] {rel_path}")
            print(f"            Local: {file_path}")
            print(f"            S3: {s3_full_path}")

            # Build upload command
            cmd = f'aws s3 cp "{file_path}" "{s3_full_path}" --profile {aws_profile}'

            # Execute upload with retry
            success = self.upload_with_retry(
                cmd,
                s3_path=s3_full_path,
                local_path=file_path,
                aws_profile=aws_profile,
                max_retries=max_retries,
                verify=verify
            )

            if success:
                success_count += 1
                results.append(('success', rel_path))
            else:
                failure_count += 1
                results.append(('failure', rel_path))

            # Add separator between uploads (except after last one)
            if i < total_files:
                print(f"{'-'*70}\n")

        # Print summary
        print(f"{'='*70}")
        print(f"Directory Upload Summary")
        print(f"{'='*70}")
        print(f"✅ Successful: {success_count}/{total_files}")
        print(f"❌ Failed: {failure_count}/{total_files}")

        if failure_count > 0:
            print(f"\nFailed files:")
            for status, filepath in results:
                if status == 'failure':
                    print(f"  - {filepath}")

        print(f"{'='*70}\n")

        return success_count, failure_count, results

    # ========== DOWNLOAD FUNCTIONALITY ==========

    @staticmethod
    def extract_ticket_id_from_url(url: str) -> Optional[str]:
        """Extract Zendesk ticket ID from a Zendesk URL.

        Args:
            url: Zendesk ticket URL (e.g., https://redislabs.zendesk.com/agent/tickets/150002)

        Returns:
            Ticket ID string (e.g., "150002") or None if not a valid Zendesk URL
        """
        # Match Zendesk URL patterns
        # Examples:
        #   https://redislabs.zendesk.com/agent/tickets/150002
        #   https://redislabs.zendesk.com/tickets/150002
        #   https://company.zendesk.com/agent/tickets/12345
        zendesk_pattern = r'zendesk\.com/(?:agent/)?tickets/(\d+)'
        match = re.search(zendesk_pattern, url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def detect_input_format(input_str: str) -> dict:
        """Detect the format of pasted input and provide analysis.

        Args:
            input_str: User input (could be URL, ID, path, etc.)

        Returns:
            dict with keys: 'format', 'description', 'value', 'valid'
        """
        # Clean input
        cleaned = input_str.strip()

        # URL-decode first
        decoded = urllib.parse.unquote(cleaned)

        # Check for Zendesk URL
        if "zendesk.com" in decoded.lower() and "/tickets/" in decoded.lower():
            ticket_id = GTLogsHelper.extract_ticket_id_from_url(decoded)
            if ticket_id:
                # Format the ticket ID with ZD- prefix
                formatted_id = GTLogsHelper.validate_zendesk_id(ticket_id)
                return {
                    'format': 'zendesk_url',
                    'description': 'Zendesk ticket URL',
                    'value': formatted_id,
                    'valid': True
                }

        # Check for Jira URL
        if "/browse/" in decoded.lower():
            jira_id = GTLogsHelper.extract_jira_id_from_url(decoded)
            if jira_id:
                return {
                    'format': 'jira_url',
                    'description': 'Jira ticket URL',
                    'value': jira_id,
                    'valid': True
                }

        # Check for full S3 URI
        if decoded.startswith("s3://"):
            return {
                'format': 's3_uri',
                'description': 'Full S3 URI',
                'value': decoded,
                'valid': True
            }

        # Check for partial S3 path (key-only)
        if decoded.startswith("zendesk-tickets/") or decoded.startswith("exa-to-gt/"):
            return {
                'format': 'partial_s3_path',
                'description': 'Partial S3 path (key-only)',
                'value': decoded,
                'valid': True
            }

        # Check for combined ZD+Jira ID
        if "-RED-" in decoded.upper() or "-MOD-" in decoded.upper():
            return {
                'format': 'combined_id',
                'description': 'Combined Zendesk + Jira ID',
                'value': decoded,
                'valid': True
            }

        # Check for Zendesk ID (formatted or numeric)
        try:
            zd_id = GTLogsHelper.validate_zendesk_id(decoded)
            return {
                'format': 'zendesk_id',
                'description': 'Zendesk ticket ID',
                'value': zd_id,
                'valid': True
            }
        except:
            pass

        # Check for Jira ID
        try:
            jira_id = GTLogsHelper.validate_jira_id(decoded)
            return {
                'format': 'jira_id',
                'description': 'Jira ticket ID',
                'value': jira_id,
                'valid': True
            }
        except:
            pass

        # Unknown format
        return {
            'format': 'unknown',
            'description': 'Unknown format',
            'value': decoded,
            'valid': False
        }

    @staticmethod
    def extract_jira_id_from_url(url: str) -> Optional[str]:
        """Extract Jira ticket ID from a Jira URL.

        Args:
            url: Jira ticket URL (e.g., https://jira.redis.com/browse/RED-172041)

        Returns:
            Jira ID string (e.g., "RED-172041") or None if not a valid Jira URL
        """
        # Match Jira URL patterns
        # Examples:
        #   https://jira.redis.com/browse/RED-172041
        #   https://jira.company.com/browse/MOD-12345
        #   https://company.atlassian.net/browse/RED-99999
        jira_pattern = r'/browse/(RED|MOD)-(\d+)'
        match = re.search(jira_pattern, url, re.IGNORECASE)
        if match:
            prefix = match.group(1).upper()
            number = match.group(2)
            return f"{prefix}-{number}"
        return None

    @staticmethod
    def is_jira_only_input(input_str: str) -> Optional[str]:
        """Check if input is Jira-only (not combined with Zendesk ID).

        Args:
            input_str: User input string

        Returns:
            Jira ID if input is Jira-only, None otherwise
        """
        cleaned = input_str.strip()

        # Check for Jira URL first
        if "/browse/" in cleaned.lower():
            jira_id = GTLogsHelper.extract_jira_id_from_url(cleaned)
            if jira_id:
                return jira_id

        # Check for Jira ID format (RED-#### or MOD-####)
        # But NOT combined format (ZD-####-RED-#### or ####-RED-####)
        jira_pattern = r'^(RED|MOD)-\d+$'
        match = re.search(jira_pattern, cleaned, re.IGNORECASE)
        if match:
            # Validate it's a proper Jira ID
            try:
                jira_id = GTLogsHelper.validate_jira_id(cleaned)
                return jira_id
            except:
                pass

        return None

    @staticmethod
    def parse_s3_path(s3_path: str):
        """Parse an S3 path or partial path to extract bucket and key.

        Args:
            s3_path: Full S3 path, partial path (e.g., ZD-145980), or Zendesk URL

        Returns:
            tuple: (bucket, key) or (None, None) if invalid
        """
        # Clean input: strip whitespace
        s3_path = s3_path.strip()

        # URL-decode the path first to handle special characters
        # Example: file%20with%20spaces.tar.gz → file with spaces.tar.gz
        s3_path = urllib.parse.unquote(s3_path)

        # Handle Zendesk URLs - extract ticket ID first
        if "zendesk.com" in s3_path.lower():
            ticket_id = GTLogsHelper.extract_ticket_id_from_url(s3_path)
            if ticket_id:
                # Treat it as a ticket ID input
                s3_path = ticket_id
            else:
                # Invalid Zendesk URL
                return None, None

        # Handle full S3 paths
        if s3_path.startswith("s3://"):
            parts = s3_path[5:].split("/", 1)
            if len(parts) >= 1:
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
                return bucket, key

        # Handle partial paths (ZD-only or ZD+Jira)
        # Check if it contains combined ZD+Jira format first
        if "-RED-" in s3_path.upper() or "-MOD-" in s3_path.upper():
            try:
                # Extract Jira part
                jira_match = re.search(r'(RED|MOD)-\d+', s3_path.upper())
                if jira_match:
                    jira_id = jira_match.group()
                    # Extract ZD part (everything before the Jira ID)
                    zd_part = s3_path[:jira_match.start()].rstrip('-')
                    zd_id = GTLogsHelper.validate_zendesk_id(zd_part)
                    # ZD+Jira path
                    return "gt-logs", f"exa-to-gt/{zd_id}-{jira_id}/"
            except:
                pass

        # Try to validate as ZD-only path
        try:
            zd_id = GTLogsHelper.validate_zendesk_id(s3_path)
            # ZD-only path
            return "gt-logs", f"zendesk-tickets/{zd_id}/"
        except:
            pass

        # Check for known path prefixes (key-only format)
        # Examples: zendesk-tickets/ZD-145980/file.tar.gz
        #           exa-to-gt/ZD-145980-RED-172041/debuginfo.tar.gz
        if s3_path.startswith("zendesk-tickets/") or s3_path.startswith("exa-to-gt/"):
            return "gt-logs", s3_path

        # Try to parse as direct bucket/key format
        # IMPORTANT: Only do this if it doesn't look like a URL
        if "/" in s3_path and not s3_path.startswith("/") and not s3_path.startswith("http"):
            parts = s3_path.split("/", 1)
            return parts[0], parts[1]

        return None, None

    def find_s3_path_by_jira_id(self, jira_id: str, aws_profile: str = "gt-logs"):
        """Find S3 path by searching for directories containing the Jira ID.

        Args:
            jira_id: Jira ticket ID (e.g., RED-177450)
            aws_profile: AWS profile to use

        Returns:
            tuple: (status, data) where:
                - status is "found", "multiple", "none", or "error"
                - data is the path string (for "found"), list of paths
                  (for "multiple"), or error message (for "error"/"none")
        """
        # Validate Jira ID
        try:
            jira_id = GTLogsHelper.validate_jira_id(jira_id)
        except ValueError as e:
            return "error", str(e)

        # List all directories in exa-to-gt/
        cmd = [
            "aws", "s3", "ls",
            "s3://gt-logs/exa-to-gt/",
            "--profile", aws_profile
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return "error", f"Failed to list S3 directories: {result.stderr}"

            # Parse output to find matching directories
            # Output format: "PRE ZD-150015-RED-177450/"
            matching_paths = []
            for line in result.stdout.splitlines():
                if line.strip().startswith("PRE "):
                    # Extract directory name
                    dir_name = line.strip()[4:].rstrip('/')
                    # Check if it ends with the Jira ID
                    if dir_name.endswith(f"-{jira_id}"):
                        matching_paths.append(f"exa-to-gt/{dir_name}/")

            if len(matching_paths) == 0:
                return "none", f"No S3 paths found for Jira ID {jira_id}"
            elif len(matching_paths) == 1:
                return "found", matching_paths[0]
            else:
                return "multiple", matching_paths

        except subprocess.TimeoutExpired:
            return "error", "Timeout while searching S3"
        except Exception as e:
            return "error", f"Error searching S3: {str(e)}"

    def find_s3_path_by_zendesk_id(self, zd_id: str, aws_profile: str = "gt-logs"):
        """Find S3 path in exa-to-gt by searching for directories starting with ZD ID.

        Args:
            zd_id: Zendesk ticket ID (e.g., ZD-150015 or 150015)
            aws_profile: AWS profile to use

        Returns:
            tuple: (status, data) where:
                - status is "found", "multiple", "none", or "error"
                - data is the path string (for "found"), list of paths
                  (for "multiple"), or error message (for "error"/"none")
        """
        # Validate Zendesk ID
        try:
            zd_id = GTLogsHelper.validate_zendesk_id(zd_id)
        except ValueError as e:
            return "error", str(e)

        # List all directories in exa-to-gt/
        cmd = [
            "aws", "s3", "ls",
            "s3://gt-logs/exa-to-gt/",
            "--profile", aws_profile
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return "error", f"Failed to list S3 directories: {result.stderr}"

            # Parse output to find matching directories
            # Output format: "PRE ZD-150015-RED-177450/"
            matching_paths = []
            for line in result.stdout.splitlines():
                if line.strip().startswith("PRE "):
                    # Extract directory name
                    dir_name = line.strip()[4:].rstrip('/')
                    # Check if it starts with the Zendesk ID
                    if dir_name.startswith(f"{zd_id}-"):
                        matching_paths.append(f"exa-to-gt/{dir_name}/")

            if len(matching_paths) == 0:
                return "none", f"No S3 paths found for Zendesk ID {zd_id} in exa-to-gt/"
            elif len(matching_paths) == 1:
                return "found", matching_paths[0]
            else:
                return "multiple", matching_paths

        except subprocess.TimeoutExpired:
            return "error", "Timeout while searching S3"
        except Exception as e:
            return "error", f"Error searching S3: {str(e)}"

    def list_s3_files(self, bucket, prefix, aws_profile="gt-logs"):
        """List files in an S3 bucket with given prefix.

        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix
            aws_profile: AWS profile to use

        Returns:
            list: List of file keys or empty list if error
        """
        cmd = [
            "aws", "s3", "ls",
            f"s3://{bucket}/{prefix}",
            "--profile", aws_profile,
            "--recursive"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"❌ Error listing files: {result.stderr}")
                return []

            # Parse the output to get file paths
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    # AWS S3 ls format: "2024-01-15 10:30:45  12345678  path/to/file.tar.gz"
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        file_key = parts[3]
                        files.append(file_key)

            return files

        except subprocess.TimeoutExpired:
            print("❌ Timeout while listing S3 files")
            return []
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return []

    def download_from_s3(self, bucket, key, local_path=None, aws_profile="gt-logs"):
        """Download a file from S3 with progress tracking.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            local_path: Local destination path (optional, defaults to current directory)
            aws_profile: AWS profile to use

        Returns:
            bool: True if successful, False otherwise
        """
        if local_path is None:
            # Use current directory with the filename from the key
            local_path = os.path.basename(key)

        # Ensure local directory exists
        local_dir = os.path.dirname(local_path)
        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        # Convert to absolute path for display
        abs_path = os.path.abspath(local_path)

        # Build AWS CLI command
        cmd = f'aws s3 cp "s3://{bucket}/{key}" "{local_path}" --profile {aws_profile}'

        try:
            # Extract filename for display
            filename = os.path.basename(key)

            print(f"\n📥 Downloading: {filename}")
            print(f"   Source: s3://{bucket}/{key}")
            print(f"   Destination: {abs_path}\n")

            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            last_progress = None
            output_lines = []

            # Read output line by line
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    output_lines.append(line)

                    # Parse progress from AWS CLI output
                    completed, total, speed_str = parse_aws_progress(line)

                    if completed and total:
                        # Display progress bar
                        display_progress_bar(completed, total, speed_str or "")
                        last_progress = (completed, total, speed_str or "")
                    elif last_progress:
                        # Continue showing last known progress
                        completed, total, speed_str = last_progress
                        display_progress_bar(completed, total, speed_str)

            # Wait for process to complete
            return_code = process.wait()

            # Ensure we show 100% on success
            if return_code == 0 and last_progress:
                _, total, speed_str = last_progress
                display_progress_bar(total, total, speed_str)

            print()  # New line after progress bar

            if return_code == 0:
                print(f"✅ Download successful! File saved to: {abs_path}\n")
                return True
            else:
                print(f"❌ Download failed with exit code {return_code}\n")
                # Show last few lines of output for debugging
                if output_lines:
                    print("Last output:")
                    for line in output_lines[-5:]:
                        print(f"   {line.rstrip()}")
                    print()
                return False

        except Exception as e:
            print(f"\n❌ Error during download: {e}\n")
            return False

    def generate_download_command(self, s3_path, local_path=None, aws_profile="gt-logs"):
        """Generate AWS CLI download command.

        Args:
            s3_path: S3 path to download from
            local_path: Local destination path (optional)
            aws_profile: AWS profile to use

        Returns:
            str: AWS CLI command or None if invalid path
        """
        bucket, key = self.parse_s3_path(s3_path)
        if not bucket or not key:
            return None

        if local_path is None:
            local_path = "."

        # Check if downloading a directory (ends with /)
        if key.endswith("/"):
            return f'aws s3 sync "s3://{bucket}/{key}" "{local_path}" --profile {aws_profile}'
        else:
            return f'aws s3 cp "s3://{bucket}/{key}" "{local_path}" --profile {aws_profile}'


def getch_timeout(timeout=None, fd=None, restore_settings=True):
    """Read a single character from stdin without waiting for Enter.

    Args:
        timeout: Optional timeout in seconds. Returns None if no input within timeout.
        fd: File descriptor (if already in raw mode, reuse it)
        restore_settings: Whether to restore terminal settings after read
    """
    if not IMMEDIATE_INPUT_AVAILABLE:
        return None

    try:
        if fd is None:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)
            should_restore = True
        else:
            old_settings = None
            should_restore = restore_settings

        try:
            if timeout is not None:
                import select
                ready = select.select([sys.stdin], [], [], timeout)
                if not ready[0]:
                    return None  # Timeout

            ch = sys.stdin.read(1)
            return ch
        finally:
            if should_restore and old_settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (OSError, termios.error):
        # Fall back if terminal operations not supported
        return None


def getch():
    """Read a single character from stdin without waiting for Enter."""
    return getch_timeout(timeout=None)


def input_with_esc_detection(prompt: str, history_list: Optional[list] = None, auto_submit_chars: Optional[list] = None) -> str:
    """Enhanced input that detects ESC key immediately without requiring Enter.

    Args:
        prompt: The input prompt to display
        history_list: Optional list of historical values for up/down arrow navigation
        auto_submit_chars: Optional list of characters that auto-submit (e.g., ['y', 'n'])

    Returns:
        User input string
    """
    # Check if we're in an interactive terminal
    try:
        if not IMMEDIATE_INPUT_AVAILABLE or not sys.stdin.isatty():
            # Fallback to regular input if termios not available or not interactive
            return input(prompt)
    except:
        return input(prompt)

    print(prompt, end='', flush=True)
    user_input = []
    history_index = -1  # -1 means not navigating history, 0+ means index in history_list

    # Enter raw mode ONCE and stay in it for the entire input
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def clear_line_from_prompt():
        """Clear the current input line and reposition cursor after prompt."""
        # Move cursor to start of line, clear line, reprint prompt
        print('\r\033[K' + prompt, end='', flush=True)

    def display_input():
        """Display the current user_input."""
        clear_line_from_prompt()
        print(''.join(user_input), end='', flush=True)

    try:
        tty.setraw(fd)
        import select

        while True:
            # Read one character while in raw mode
            ch = sys.stdin.read(1)

            # If read fails, fall back to empty input
            if not ch:
                return ""

            # ESC key pressed - check if it's a standalone ESC or part of an escape sequence
            if ch == '\x1b':
                # Arrow keys send: ESC [ A/B/C/D (as 3 separate character events!)
                # Use termios VTIME/VMIN to set a read timeout on the file descriptor
                # This distinguishes standalone ESC from escape sequences

                # Get current settings
                tty_attr = termios.tcgetattr(fd)
                # Set timeout: VTIME = 2 (0.2 seconds), VMIN = 0 (return immediately if no data)
                # termios.tcgetattr returns: [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
                # cc is index 6, VTIME and VMIN are accessed within cc
                tty_attr[6][termios.VTIME] = 2  # 0.2 second timeout
                tty_attr[6][termios.VMIN] = 0   # Don't wait for any characters
                termios.tcsetattr(fd, termios.TCSANOW, tty_attr)

                # Try to read the next character with timeout
                next_ch = sys.stdin.read(1)

                # Restore raw mode (VMIN=1, VTIME=0 for normal operation)
                tty.setraw(fd)

                if next_ch:
                    # Got another character - this is an escape sequence (arrow key, etc.)
                    if next_ch == '[' or next_ch == 'O':
                        # Standard escape sequence - read the final character
                        # Set timeout again for the final character
                        tty_attr = termios.tcgetattr(fd)
                        tty_attr[6][termios.VTIME] = 2
                        tty_attr[6][termios.VMIN] = 0
                        termios.tcsetattr(fd, termios.TCSANOW, tty_attr)

                        final_ch = sys.stdin.read(1)

                        # Restore raw mode
                        tty.setraw(fd)

                        # Handle arrow keys (if history is available)
                        if history_list and final_ch in ('A', 'B'):
                            if final_ch == 'A':  # Up arrow
                                if history_index < len(history_list) - 1:
                                    history_index += 1
                                    user_input = list(history_list[history_index])
                                    display_input()
                            elif final_ch == 'B':  # Down arrow
                                if history_index > 0:
                                    history_index -= 1
                                    user_input = list(history_list[history_index])
                                    display_input()
                                elif history_index == 0:
                                    # Move past most recent to empty input
                                    history_index = -1
                                    user_input = []
                                    display_input()

                        # Ignore other escape sequences (left/right arrows, etc.)
                        continue
                    else:
                        # Unknown escape sequence, ignore it
                        continue
                else:
                    # Timeout - no more characters, this is a standalone ESC key press
                    # Restore terminal settings BEFORE exiting
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    # Use ANSI escape to clear line from cursor to end, then print exit message
                    print("\r\033[K")
                    # Raise exception instead of sys.exit() to allow cleanup in calling code
                    raise UserExitException()

            # Backspace
            elif ch in ('\x7f', '\x08'):
                if user_input:
                    user_input.pop()
                    # Reset history navigation when user edits
                    history_index = -1
                    # Erase character from terminal
                    print('\b \b', end='', flush=True)

            # Enter key
            elif ch in ('\r', '\n'):
                # Explicitly output carriage return + newline for proper cursor positioning in raw mode
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                result = ''.join(user_input)
                # Check for exit commands
                if result.lower() in ['exit', 'quit', 'q']:
                    raise UserExitException()
                return result

            # Ctrl+C
            elif ch == '\x03':
                # Explicitly output carriage return + newline for proper cursor positioning in raw mode
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                raise KeyboardInterrupt

            # Ctrl+U (update check)
            elif ch == '\x15':
                # Explicitly output carriage return + newline for proper cursor positioning in raw mode
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                raise UpdateCheckException()

            # Regular printable characters
            elif ch.isprintable():
                # Reset history navigation when user types
                history_index = -1
                user_input.append(ch)
                print(ch, end='', flush=True)

                # Auto-submit if character is in auto_submit_chars
                if auto_submit_chars and ch.lower() in auto_submit_chars:
                    # Output newline and return immediately
                    sys.stdout.write('\r\n')
                    sys.stdout.flush()
                    result = ''.join(user_input)
                    # Check for exit commands
                    if result.lower() in ['exit', 'quit', 'q']:
                        raise UserExitException()
                    return result

    finally:
        # Always restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Safety fallback (should never reach here as while loop always returns or raises)
    return ""


def check_exit_input(user_input):
    """Check if user wants to exit (exit commands only - ESC handled in input_with_esc_detection).

    Note: This function is now redundant as exit checking is done in input_with_esc_detection(),
    but kept for backward compatibility.
    """
    if not user_input:
        return False
    # Check for exit commands (handled by UserExitException in input_with_esc_detection now)
    if user_input.lower() in ['exit', 'quit', 'q']:
        raise UserExitException()
    return False


def interactive_mode(debug=False):
    """Run the helper in interactive mode with mode selection."""
    print("\n" + "="*70)
    print(f"GT Logs Helper v{VERSION} - Interactive Mode")
    print("="*70)
    print("\nUpload and download Redis Support packages to/from S3")
    if IMMEDIATE_INPUT_AVAILABLE:
        print("Press ESC to exit, Ctrl+C, or type 'exit'/'q' at any prompt")
        print("Use UP/DOWN arrows for input history, Ctrl+U to check for updates\n")
    else:
        print("Press Ctrl+C to exit, or type 'exit' or 'q' at any prompt\n")

    # Mode selection
    print("Select operation mode:")
    print("☁️ ⬆️  1 or U: UPLOAD to S3 (generate links and upload files)")
    print("☁️ ⬇️  2 or D: DOWNLOAD from S3 (retrieve files from existing paths)")
    print()

    try:
        while True:
            mode_input = input_with_esc_detection("Your choice: ", auto_submit_chars=['1', 'u', '2', 'd']).strip().lower()
            check_exit_input(mode_input)

            # Default to upload (1) if user presses Enter
            if not mode_input:
                mode_input = '1'

            if mode_input in ["1", "u"]:
                interactive_upload_mode(debug=debug)
                break
            elif mode_input in ["2", "d"]:
                interactive_download_mode(debug=debug)
                break
            else:
                print("❌ Invalid choice. Please enter 1/U or 2/D\n")
        return 0
    except UserExitException:
        print("👋 Exiting...\n")
        return 0
    except UpdateCheckException:
        print("🔍 Checking for updates...")
        update_info = check_for_updates()
        if update_info and update_info['available']:
            if prompt_for_update(update_info):
                # Update was installed, exit so user can restart
                return 0
            else:
                # User chose 'n', return to interactive mode
                print("Returning to interactive mode...\n")
                return interactive_mode(debug=debug)
        elif update_info:
            print(f"✓ You're up to date! (v{update_info['current_version']})\n")
            print("Returning to interactive mode...\n")
            return interactive_mode()
        else:
            print("⚠️  Could not check for updates (offline or API error)\n")
            print("Returning to interactive mode...\n")
            return interactive_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...\n")
        return 0


def interactive_upload_mode(debug=False):
    """Run the upload functionality in interactive mode."""
    generator = GTLogsHelper(debug=debug)

    print("\n" + "-"*50)
    print("Upload Mode - Generate S3 URLs and upload files")
    print("-"*50 + "\n")

    try:
        # Get Zendesk ID
        while True:
            zd_history = generator.get_history('zendesk_id')
            zd_input = input_with_esc_detection("Enter Zendesk ticket ID (e.g., 145980): ", zd_history).strip()
            check_exit_input(zd_input)
            if not zd_input:
                print("❌ Zendesk ID is required\n")
                continue
            try:
                zd_formatted = generator.validate_zendesk_id(zd_input)
                print(f"\n✓ Using: {zd_formatted}\n")
                # Add to history immediately after validation
                generator.add_to_history('zendesk_id', zd_formatted)
                break
            except ValueError as e:
                print(f"❌ {e}\n")

        # Get Jira ID (optional)
        jira_formatted = None
        while True:
            jira_history = generator.get_history('jira_id')
            jira_input = input_with_esc_detection("Enter Jira ID or URL (e.g., RED-172041, MOD-12345, or https://jira.../browse/RED-172041, press Enter to skip): ", jira_history).strip()
            check_exit_input(jira_input)
            if not jira_input:
                print("\n✓ No Jira ID - will use zendesk-tickets path\n")
                break

            # Check if input is a Jira URL
            if "/browse/" in jira_input.lower():
                jira_from_url = generator.extract_jira_id_from_url(jira_input)
                if jira_from_url:
                    print(f"\n✓ Extracted from URL: {jira_from_url}")
                    jira_input = jira_from_url
                else:
                    print(f"❌ Could not extract Jira ID from URL: {jira_input}\n")
                    continue

            try:
                jira_formatted = generator.validate_jira_id(jira_input)
                print(f"\n✓ Using: {jira_formatted}\n")
                # Add to history immediately after validation
                generator.add_to_history('jira_id', jira_formatted)
                break
            except ValueError as e:
                print(f"❌ {e}\n")

        # Get support package path(s) (optional)
        package_paths = []
        while True:
            path_history = generator.get_history('file_path')
            if not package_paths:
                prompt = "Enter support package path(s) (comma-separated for multiple, press Enter to skip): "
            else:
                prompt = f"Add another file? (press Enter to continue with {len(package_paths)} file(s)): "

            package_path = input_with_esc_detection(prompt, path_history).strip()
            check_exit_input(package_path)

            if not package_path:
                if not package_paths:
                    print("\n✓ Will generate template command\n")
                else:
                    print(f"\n✓ Proceeding with {len(package_paths)} file(s)\n")
                break

            # Split by comma for multiple paths
            paths_to_validate = [p.strip() for p in package_path.split(',')]

            for path in paths_to_validate:
                if not path:
                    continue
                try:
                    validated_path = generator.validate_file_path(path)
                    if validated_path not in package_paths:  # Avoid duplicates
                        package_paths.append(validated_path)
                        print(f"✓ File {len(package_paths)}: {validated_path}")
                        # Add to history immediately after validation
                        generator.add_to_history('file_path', validated_path)
                    else:
                        print(f"⚠️  Skipping duplicate: {validated_path}")
                except ValueError as e:
                    print(f"❌ {e}")
                    retry = input_with_esc_detection("Try again? (y/n): ").strip().lower()
                    check_exit_input(retry)
                    if retry not in ['y', 'yes']:
                        if not package_paths:
                            print("✓ Skipping file path, will generate template command\n")
                        break
                    print()
                    break  # Break inner loop to retry the same input
            else:
                # If we processed all paths successfully, ask for more
                continue

            # If retry was 'n', break outer loop
            if not package_paths:
                break

        # Convert to None if empty list for backward compatibility
        package_path = package_paths if package_paths else None

        # Get AWS profile
        default_profile = generator.get_default_aws_profile()
        if default_profile:
            profile_prompt = f"Enter AWS profile (press Enter for default '{default_profile}'): "
        else:
            profile_prompt = "Enter AWS profile (optional, press Enter to skip): "

        profile_history = generator.get_history('aws_profile')
        aws_profile_input = input_with_esc_detection(profile_prompt, profile_history).strip()
        check_exit_input(aws_profile_input)

        if aws_profile_input:
            aws_profile = aws_profile_input
            # Add to history immediately
            generator.add_to_history('aws_profile', aws_profile)
            # Ask if they want to save as default
            save_default = input_with_esc_detection(f"\nSave '{aws_profile}' as default profile? (y/n): ").strip().lower()
            check_exit_input(save_default)
            if save_default in ['y', 'yes']:
                generator._save_config(aws_profile)
                print()
        elif default_profile:
            aws_profile = default_profile
            print(f"\n✓ Using default profile: {default_profile}\n")
        else:
            # Use gt-logs as fallback when no profile is configured
            aws_profile = "gt-logs"
            print("\n✓ Using default profile: gt-logs\n")

        # Handle single vs multiple files
        if package_path:
            # We have file path(s)
            if isinstance(package_path, list) and len(package_path) > 1:
                # Multiple files - use batch upload
                s3_path = generator.generate_s3_path(zd_formatted, jira_formatted)

                # Display batch upload info
                print("="*70)
                print("Batch Upload Configuration")
                print("="*70)
                print(f"\nS3 Destination:\n  {s3_path}")
                print(f"\nFiles to upload ({len(package_path)}):")
                for i, fpath in enumerate(package_path, 1):
                    print(f"  {i}. {os.path.basename(fpath)}")
                print("\n" + "="*70)

                # Offer to execute
                print()
                execute_now = input_with_esc_detection("Execute batch upload now? (Y/n): ").strip().lower()
                check_exit_input(execute_now)

                # Default to 'yes' if user just presses Enter
                if execute_now == '' or execute_now in ['y', 'yes']:
                    # Check authentication
                    is_authenticated = generator.check_aws_authentication(aws_profile, debug=generator.debug)

                    if not is_authenticated:
                        print(f"\n⚠️  AWS profile '{aws_profile}' is not authenticated")
                        # Automatically run AWS SSO login
                        if not generator.aws_sso_login(aws_profile):
                            print("❌ Cannot proceed without authentication\n")
                            return 1
                    else:
                        print(f"\n✓ AWS profile '{aws_profile}' is already authenticated\n")

                    # Execute batch upload
                    success_count, failure_count, _ = generator.execute_batch_upload(
                        package_path, zd_formatted, jira_formatted, aws_profile
                    )
                    return 0 if failure_count == 0 else 1
                else:
                    print()
            else:
                # Single file - use original logic
                single_path = package_path[0] if isinstance(package_path, list) else package_path
                cmd, s3_path = generator.generate_aws_command(
                    zd_input,
                    jira_formatted,  # Can be None for ZD-only uploads
                    single_path,
                    aws_profile
                )

                # Display results
                print("="*70)
                print("Generated Output")
                print("="*70)
                print(f"\nS3 Path:\n  {s3_path}")
                print(f"\nAWS CLI Command:\n  {cmd}")
                print("\n" + "="*70)

                # Offer to execute
                print()
                execute_now = input_with_esc_detection("Execute this command now? (Y/n): ").strip().lower()
                check_exit_input(execute_now)

                # Default to 'yes' if user just presses Enter
                if execute_now == '' or execute_now in ['y', 'yes']:
                    # Check authentication
                    is_authenticated = generator.check_aws_authentication(aws_profile, debug=generator.debug)

                    if not is_authenticated:
                        print(f"\n⚠️  AWS profile '{aws_profile}' is not authenticated")
                        # Automatically run AWS SSO login
                        if not generator.aws_sso_login(aws_profile):
                            print("❌ Cannot proceed without authentication\n")
                            return 1
                    else:
                        print(f"\n✓ AWS profile '{aws_profile}' is already authenticated\n")

                    # Execute the upload
                    success = generator.execute_s3_upload(cmd)
                    return 0 if success else 1
                else:
                    print()
        else:
            # Show AWS SSO login reminder if profile is specified (templated command)
            if aws_profile:
                print(f"\n💡 Reminder: Authenticate with AWS SSO before running the command:")
                print(f"   aws sso login --profile {aws_profile}\n")
            else:
                print(f"\n💡 Reminder: Authenticate with AWS SSO before running the command:")
                print(f"   aws sso login --profile <your-aws-profile>\n")

        # Save history before exiting
        generator._save_history()
        return 0

    except UserExitException:
        print("👋 Exiting...\n")
        # Save history when user exits via ESC or exit command
        generator._save_history()
        return 0
    except UpdateCheckException:
        print("🔍 Checking for updates...")
        update_info = check_for_updates()
        if update_info and update_info['available']:
            if prompt_for_update(update_info):
                # Update was installed, need to restart to use new version
                # Message already printed by perform_self_update()
                generator._save_history()
                return 0
            else:
                # User chose 'n', return to interactive mode
                print("Returning to interactive mode...\n")
                return interactive_mode(debug=debug)
        elif update_info:
            print(f"✓ You're up to date! (v{update_info['current_version']})\n")
            print("Returning to interactive mode...\n")
            # Return to start of interactive mode by recursively calling
            return interactive_mode()
        else:
            print("⚠️  Could not check for updates (offline or API error)\n")
            print("Returning to interactive mode...\n")
            # Return to start of interactive mode by recursively calling
            return interactive_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...\n")
        # Save history even on Ctrl+C
        generator._save_history()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}\n", file=sys.stderr)
        # Save history even on error
        generator._save_history()
        return 1


def interactive_download_mode(debug=False):
    """Run the download functionality in interactive mode."""
    helper = GTLogsHelper(debug=debug)

    print("\n" + "-"*50)
    print("Download Mode - Retrieve files from S3")
    print("-"*50 + "\n")

    try:
        # Get S3 path or identifier
        print("Enter S3 path to download from.")
        print("Examples:")
        print("  - Full path: s3://gt-logs/zendesk-tickets/ZD-145980/file.tar.gz")
        print("  - Ticket ID: ZD-145980 (will list available files)")
        print("  - Ticket + Jira: ZD-145980-RED-172041")
        print("  - Zendesk URL: https://redislabs.zendesk.com/agent/tickets/150002")
        print("  - Jira URL: https://redislabs.atlassian.net/browse/RED-177450")
        print("  - Jira ID: RED-177450 (searches for associated support packages)")
        print()

        while True:
            s3_history = helper.get_history('s3_path')
            s3_input = input_with_esc_detection("Enter S3 path, ticket ID, Zendesk URL, or Jira URL: ", s3_history).strip()
            check_exit_input(s3_input)

            if not s3_input:
                print("❌ S3 path or ticket ID is required\n")
                continue

            # Check if input is Jira-only (URL or ID)
            jira_id = GTLogsHelper.is_jira_only_input(s3_input)
            if jira_id:
                # Need to get AWS profile first for S3 search
                print(f"\n🔍 Detected Jira ticket: {jira_id}")
                print("Searching S3 for associated support packages...\n")

                # Get AWS profile (needed for search)
                default_profile = helper.get_default_aws_profile()
                if default_profile:
                    search_profile = default_profile
                else:
                    search_profile = "gt-logs"

                # Search for S3 paths matching this Jira ID
                status, data = helper.find_s3_path_by_jira_id(jira_id, search_profile)

                if status == "found":
                    # Single match found
                    print(f"✓ Found S3 path: s3://gt-logs/{data}\n")
                    s3_input = f"s3://gt-logs/{data}"
                elif status == "multiple":
                    # Multiple matches found - let user choose
                    print(f"Found {len(data)} S3 paths for {jira_id}:\n")
                    for i, path in enumerate(data, 1):
                        # Extract ZD ticket from path for display
                        zd_match = re.search(r'(ZD-\d+)', path)
                        zd_ticket = zd_match.group(1) if zd_match else "Unknown"
                        print(f"  {i}. {zd_ticket}: s3://gt-logs/{path}")

                    print()
                    choice = input_with_esc_detection("Select path number (or press Enter to cancel): ").strip()
                    check_exit_input(choice)

                    if not choice:
                        print("Cancelled\n")
                        continue

                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(data):
                            s3_input = f"s3://gt-logs/{data[idx]}"
                            print(f"\n✓ Selected: {s3_input}\n")
                        else:
                            print("❌ Invalid selection\n")
                            continue
                    except ValueError:
                        print("❌ Invalid selection\n")
                        continue
                elif status == "none":
                    print(f"❌ {data}")
                    print(f"   No support packages found for Jira ticket {jira_id}\n")
                    continue
                else:  # error
                    print(f"❌ {data}\n")
                    continue

            # Parse the S3 path
            bucket, key = helper.parse_s3_path(s3_input)
            if not bucket or not key:
                if "zendesk.com" in s3_input.lower():
                    print(f"❌ Invalid Zendesk URL: Could not extract ticket ID from {s3_input}\n")
                else:
                    print(f"❌ Invalid S3 path or ticket ID: {s3_input}\n")
                continue

            helper.add_to_history('s3_path', s3_input)

            # Show what was extracted if input was a Zendesk URL
            if "zendesk.com" in s3_input.lower():
                ticket_id = helper.extract_ticket_id_from_url(s3_input)
                print(f"\n✓ Extracted ticket ID: ZD-{ticket_id}")

            print(f"✓ Parsed: s3://{bucket}/{key}")
            break

        # Get AWS profile
        default_profile = helper.get_default_aws_profile()
        if default_profile:
            profile_prompt = f"Enter AWS profile (press Enter for default '{default_profile}'): "
        else:
            profile_prompt = "Enter AWS profile (default: gt-logs): "

        profile_history = helper.get_history('aws_profile')
        aws_profile_input = input_with_esc_detection(profile_prompt, profile_history).strip()
        check_exit_input(aws_profile_input)

        if aws_profile_input:
            aws_profile = aws_profile_input
            helper.add_to_history('aws_profile', aws_profile)
        elif default_profile:
            aws_profile = default_profile
            print(f"\n✓ Using default profile: {default_profile}")
        else:
            aws_profile = "gt-logs"
            print(f"\n✓ Using default profile: gt-logs")

        # Check authentication
        print(f"\nChecking AWS authentication...")
        is_authenticated = helper.check_aws_authentication(aws_profile, debug=helper.debug)

        if not is_authenticated:
            print(f"⚠️  AWS profile '{aws_profile}' is not authenticated")
            if not helper.aws_sso_login(aws_profile):
                print("❌ Cannot proceed without authentication\n")
                return 1
        else:
            print(f"✓ AWS profile '{aws_profile}' is authenticated")

        # If the key is a directory (ends with /), list files
        if key.endswith("/"):
            print(f"\n🔍 Listing files in s3://{bucket}/{key}...\n")
            files = helper.list_s3_files(bucket, key, aws_profile)

            if not files:
                # Check if this is a zendesk-tickets path - if so, try exa-to-gt fallback
                if key.startswith("zendesk-tickets/"):
                    # Extract ZD ID from the key
                    zd_match = re.search(r'(ZD-\d+)', key)
                    if zd_match:
                        zd_id = zd_match.group(1)
                        print(f"❌ No files found in s3://{bucket}/{key}")
                        print(f"🔍 Checking exa-to-gt/ for {zd_id} with Jira tickets...\n")

                        # Search exa-to-gt for this ZD ID
                        status, data = helper.find_s3_path_by_zendesk_id(zd_id, aws_profile)

                        if status == "found":
                            # Single match found
                            print(f"✓ Found alternative path: s3://gt-logs/{data}")
                            use_alt = input_with_esc_detection("Use this path instead? (Y/n): ").strip().lower()
                            check_exit_input(use_alt)

                            if use_alt == '' or use_alt in ['y', 'yes']:
                                bucket = "gt-logs"
                                key = data
                                print(f"\n🔍 Listing files in s3://{bucket}/{key}...\n")
                                files = helper.list_s3_files(bucket, key, aws_profile)
                                if not files:
                                    print(f"❌ No files found in s3://{bucket}/{key}")
                                    return 1
                            else:
                                return 1
                        elif status == "multiple":
                            # Multiple matches found
                            print(f"✓ Found {len(data)} alternative path(s):\n")
                            for i, path in enumerate(data, 1):
                                # Extract Jira ID from path for display
                                jira_match = re.search(r'(RED|MOD)-\d+', path)
                                jira_id = jira_match.group(0) if jira_match else "Unknown"
                                print(f"  {i}. {jira_id}: s3://gt-logs/{path}")

                            print()
                            choice = input_with_esc_detection("Select path number (or press Enter to cancel): ").strip()
                            check_exit_input(choice)

                            if not choice:
                                return 1

                            try:
                                idx = int(choice) - 1
                                if 0 <= idx < len(data):
                                    bucket = "gt-logs"
                                    key = data[idx]
                                    print(f"\n🔍 Listing files in s3://{bucket}/{key}...\n")
                                    files = helper.list_s3_files(bucket, key, aws_profile)
                                    if not files:
                                        print(f"❌ No files found in s3://{bucket}/{key}")
                                        return 1
                                else:
                                    print("❌ Invalid selection")
                                    return 1
                            except ValueError:
                                print("❌ Invalid selection")
                                return 1
                        else:
                            # No matches in exa-to-gt either
                            print(f"❌ No files found in exa-to-gt/ for {zd_id}")
                            return 1
                    else:
                        print(f"❌ No files found in s3://{bucket}/{key}")
                        return 1
                else:
                    print(f"❌ No files found in s3://{bucket}/{key}")
                    return 1

            print(f"Found {len(files)} file(s):")
            for i, file in enumerate(files, 1):
                print(f"  {i}. {file}")

            # Ask which file(s) to download
            print("\nSelect files to download:")
            print("  - Enter file number(s) separated by commas (e.g., 1,3,5)")
            print("  - Enter 'all' or 'a' to download all files")
            print("  - Press Enter to cancel")
            print()

            selection = input_with_esc_detection("Your selection: ").strip()
            check_exit_input(selection)

            if not selection:
                print("\nDownload cancelled\n")
                return 0

            files_to_download = []
            if selection.lower() in ['all', 'a']:
                files_to_download = files
            else:
                try:
                    indices = [int(x.strip()) - 1 for x in selection.split(',')]
                    files_to_download = [files[i] for i in indices if 0 <= i < len(files)]
                except (ValueError, IndexError):
                    print("❌ Invalid selection\n")
                    return 1

            if not files_to_download:
                print("❌ No valid files selected\n")
                return 1

            # Get local directory - use smart path if configured
            print("\nWhere to save the files?")
            smart_path, zd_number = helper.get_smart_download_path(key)
            if smart_path:
                smart_dir = os.path.dirname(smart_path)
                print(f"💡 Suggested: {smart_dir}")
                local_dir = input_with_esc_detection(f"Local directory (press Enter to use suggested): ").strip()
            else:
                local_dir = input_with_esc_detection("Local directory (press Enter for current directory): ").strip()
            check_exit_input(local_dir)

            if not local_dir:
                if smart_path:
                    local_dir = smart_dir
                    print(f"✓ Using: {local_dir}")
                else:
                    local_dir = "."
            else:
                # Expand ~ if present
                local_dir = os.path.expanduser(local_dir)

            # Create directory if it doesn't exist
            if local_dir != "." and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
                print(f"✓ Created directory: {local_dir}")

            # Download selected files
            print(f"\n📥 Downloading {len(files_to_download)} file(s)...\n")
            success_count = 0
            for file in files_to_download:
                local_path = os.path.join(local_dir, os.path.basename(file))
                if helper.download_from_s3(bucket, file, local_path, aws_profile):
                    success_count += 1

            print(f"\n✅ Downloaded {success_count}/{len(files_to_download)} file(s) successfully")

        else:
            # Single file download
            print(f"\n📥 Downloading s3://{bucket}/{key}...")

            # Get local path - use smart path if configured
            default_name = os.path.basename(key) if key else "download"
            smart_path, zd_number = helper.get_smart_download_path(key)
            if smart_path:
                print(f"💡 Suggested: {smart_path}")
                local_path = input_with_esc_detection(f"Save as (press Enter to use suggested): ").strip()
            else:
                local_path = input_with_esc_detection(f"Save as (press Enter for '{default_name}'): ").strip()
            check_exit_input(local_path)

            if not local_path:
                if smart_path:
                    local_path = smart_path
                    # Create parent directory if needed
                    parent_dir = os.path.dirname(local_path)
                    if parent_dir and not os.path.exists(parent_dir):
                        os.makedirs(parent_dir, exist_ok=True)
                        print(f"✓ Created directory: {parent_dir}")
                    print(f"✓ Using: {local_path}")
                else:
                    local_path = default_name
            else:
                # Expand ~ if present
                local_path = os.path.expanduser(local_path)

            # Download the file
            if not helper.download_from_s3(bucket, key, local_path, aws_profile):
                # Check if it might be a directory (missing trailing slash)
                if not key.endswith("/"):
                    print(f"\n💡 File download failed. Checking if this is a directory...\n")
                    dir_key = key + "/"
                    files = helper.list_s3_files(bucket, dir_key, aws_profile)

                    if files:
                        # It's a directory! Let user select files
                        print(f"✓ Found {len(files)} file(s) in directory:\n")
                        for i, file in enumerate(files, 1):
                            print(f"  {i}. {file}")

                        # Ask which file(s) to download
                        print("\nSelect files to download:")
                        print("  - Enter file number(s) separated by commas (e.g., 1,3,5)")
                        print("  - Enter 'all' or 'a' to download all files")
                        print("  - Press Enter to cancel")
                        print()

                        selection = input_with_esc_detection("Your selection: ").strip()
                        check_exit_input(selection)

                        if not selection:
                            print("\nDownload cancelled\n")
                            return 0

                        files_to_download = []
                        if selection.lower() in ['all', 'a']:
                            files_to_download = files
                        else:
                            try:
                                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                                files_to_download = [files[i] for i in indices if 0 <= i < len(files)]
                            except (ValueError, IndexError):
                                print("❌ Invalid selection\n")
                                return 1

                        if not files_to_download:
                            print("❌ No valid files selected\n")
                            return 1

                        # Get download directory - use smart path if configured
                        smart_path, zd_number = helper.get_smart_download_path(dir_key)
                        if smart_path:
                            smart_dir = os.path.dirname(smart_path)
                            print(f"💡 Suggested: {smart_dir}")
                            local_dir = input_with_esc_detection(f"Local directory (press Enter to use suggested): ").strip()
                        else:
                            local_dir = input_with_esc_detection("Local directory (press Enter for current directory): ").strip()
                        check_exit_input(local_dir)

                        if not local_dir:
                            if smart_path:
                                local_dir = smart_dir
                                print(f"✓ Using: {local_dir}")
                            else:
                                local_dir = "."
                        else:
                            local_dir = os.path.expanduser(local_dir)

                        if local_dir != "." and not os.path.exists(local_dir):
                            os.makedirs(local_dir, exist_ok=True)
                            print(f"✓ Created directory: {local_dir}")

                        # Download selected files
                        print(f"\n📥 Downloading {len(files_to_download)} file(s)...\n")
                        success_count = 0
                        for file in files_to_download:
                            local_file_path = os.path.join(local_dir, os.path.basename(file))
                            if helper.download_from_s3(bucket, file, local_file_path, aws_profile):
                                success_count += 1

                        print(f"\n✅ Downloaded {success_count}/{len(files_to_download)} file(s) successfully")
                    else:
                        print("❌ Download failed")
                        return 1
                else:
                    print("❌ Download failed")
                    return 1

        # Save history
        helper._save_history()
        return 0

    except UserExitException:
        print("👋 Exiting...\n")
        helper._save_history()
        return 0
    except KeyboardInterrupt:
        print("\n👋 Exiting...\n")
        helper._save_history()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}\n", file=sys.stderr)
        helper._save_history()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='GT Logs Helper - Upload and download Redis Support packages to/from S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (no arguments) - Choose between upload/download
  %(prog)s

  # UPLOAD MODE:
  # Generate S3 path only
  %(prog)s 145980 RED-172041

  # Upload single file
  %(prog)s 145980 RED-172041 -f /path/to/support_package.tar.gz --execute

  # Batch upload multiple files
  %(prog)s 145980 RED-172041 -f file1.tar.gz -f file2.tar.gz -f file3.tar.gz --execute

  # Upload entire directory (preserves structure)
  %(prog)s 145980 RED-172041 --dir /path/to/directory --execute

  # Upload directory with pattern filtering
  %(prog)s 145980 RED-172041 --dir /path/to/directory --include "*.tar.gz" --exclude "*.log" --execute

  # Dry run (preview what would be uploaded)
  %(prog)s 145980 RED-172041 --dir /path/to/directory --dry-run

  # DOWNLOAD MODE:
  # Download from S3 path
  %(prog)s --download s3://gt-logs/zendesk-tickets/ZD-145980/file.tar.gz

  # Download using ticket ID (lists files, use 'a' to download all)
  %(prog)s --download ZD-145980

  # Download with custom output path
  %(prog)s --download ZD-145980 --output ~/Downloads/

  # CONFIG:
  # Use specific AWS profile
  %(prog)s 145980 RED-172041 -p my-aws-profile

  # Set default AWS profile
  %(prog)s --set-profile my-aws-profile
        """
    )

    parser.add_argument('zendesk_id', nargs='?',
                       help='Zendesk ticket ID (e.g., 145980 or ZD-145980)')
    parser.add_argument('jira_id', nargs='?',
                       help='Jira ticket ID (optional, e.g., RED-172041 or MOD-12345)')
    parser.add_argument('-f', '--file', dest='support_package', action='append',
                       help='Path to support package file (can be used multiple times for batch uploads)')
    parser.add_argument('-p', '--profile', dest='aws_profile',
                       help='AWS profile to use (overrides default)')
    parser.add_argument('--set-profile', dest='set_profile',
                       help='Set default AWS profile')
    parser.add_argument('--set-download-dir', dest='set_download_dir',
                       help='Set default download directory (files organized by ZD ticket)')
    parser.add_argument('--show-config', action='store_true',
                       help='Show current configuration')
    parser.add_argument('-v', '--version', action='store_true',
                       help='Show version and check for updates')
    parser.add_argument('-i', '--interactive', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('-e', '--execute', action='store_true',
                       help='Execute the AWS S3 upload command (requires non-templated file path)')

    # Directory upload arguments
    parser.add_argument('-D', '--dir', '--directory', dest='directory',
                       help='Upload entire directory (preserves directory structure in S3)')
    parser.add_argument('--include', dest='include_patterns', action='append',
                       help='Include only files matching pattern (e.g., *.tar.gz, can be used multiple times)')
    parser.add_argument('--exclude', dest='exclude_patterns', action='append',
                       help='Exclude files matching pattern (e.g., *.log, can be used multiple times)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be uploaded without actually uploading')

    # Download mode arguments
    parser.add_argument('-d', '--download', dest='download_path',
                       help='Download from S3 (provide S3 path or ticket ID)')
    parser.add_argument('-o', '--output', dest='output_path',
                       help='Output directory for downloads (default: current directory)')

    # Resume and retry arguments
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum retry attempts for failed uploads/downloads (default: 3)')
    parser.add_argument('--verify', action='store_true',
                       help='Verify uploads after completion (checks file size in S3)')
    parser.add_argument('--no-resume', action='store_true',
                       help='Ignore any saved state and start fresh')
    parser.add_argument('--clean-state', action='store_true',
                       help='Clean up state file and exit')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug output (shows timing and authentication details)')

    args = parser.parse_args()

    helper = GTLogsHelper(debug=args.debug)

    # Handle clean-state command
    if args.clean_state:
        if os.path.exists(helper.STATE_FILE):
            helper._clean_state()
            print(f"✅ State file cleaned: {helper.STATE_FILE}")
        else:
            print(f"ℹ️  No state file found: {helper.STATE_FILE}")
        return 0

    # Check for resume (unless --no-resume is specified)
    resume_state = None
    if not args.no_resume and not args.download_path:  # Don't check for download mode yet
        resume_state = helper.check_and_prompt_resume()

    # Handle config commands
    if args.set_profile:
        helper._save_config(args.set_profile)
        return 0

    if args.set_download_dir:
        download_dir = os.path.expanduser(args.set_download_dir)
        if not os.path.isdir(download_dir):
            print(f"⚠️  Directory does not exist: {download_dir}")
            create = input("Create it? (Y/n): ").strip().lower()
            if create in ['', 'y', 'yes']:
                os.makedirs(download_dir, exist_ok=True)
                print(f"✓ Created directory: {download_dir}")
            else:
                print("❌ Cancelled")
                return 1
        helper._save_download_dir(download_dir)
        print(f"  └─ Downloads will be organized into ZD ticket subfolders")
        print(f"  └─ Example: {download_dir}/150576/debuginfo.tar.gz")
        return 0

    if args.show_config:
        default_profile = helper.get_default_aws_profile()
        default_download_dir = helper.get_default_download_dir()
        print(f"Configuration file: {helper.CONFIG_FILE}")
        print(f"Default AWS profile: {default_profile if default_profile else '(not set)'}")
        print(f"Default download dir: {default_download_dir if default_download_dir else '(not set)'}")
        if default_download_dir:
            print(f"  └─ Downloads will be organized into ZD ticket subfolders")
        return 0

    if args.version:
        print(f"GT Logs Helper v{VERSION}")
        print("\n🔍 Checking for updates...")
        update_info = check_for_updates()
        if update_info and update_info['available']:
            print(f"📦 Update available: v{update_info['current_version']} → v{update_info['latest_version']}")
            if update_info['release_notes']:
                print("   Changes:")
                for note in update_info['release_notes']:
                    print(f"   - {note}")
            print("\nRun the script in interactive mode to update, or press Ctrl+U during runtime.\n")
        elif update_info:
            print(f"✓ You're up to date!\n")
        else:
            print("⚠️  Could not check for updates (offline or API error)\n")
        return 0

    # Handle download mode
    if args.download_path:
        download_input = args.download_path

        # Check if input is Jira-only (URL or ID)
        jira_id = GTLogsHelper.is_jira_only_input(download_input)
        if jira_id:
            print(f"\n🔍 Detected Jira ticket: {jira_id}")
            print("Searching S3 for associated support packages...\n")

            # Determine AWS profile for search
            aws_profile = args.aws_profile or helper.get_default_aws_profile() or "gt-logs"

            # Search for S3 paths matching this Jira ID
            status, data = helper.find_s3_path_by_jira_id(jira_id, aws_profile)

            if status == "found":
                # Single match found
                print(f"✓ Found S3 path: s3://gt-logs/{data}\n")
                download_input = f"s3://gt-logs/{data}"
            elif status == "multiple":
                # Multiple matches found - show and error (non-interactive)
                print(f"❌ Multiple S3 paths found for {jira_id}:")
                for i, path in enumerate(data, 1):
                    # Extract ZD ticket from path for display
                    zd_match = re.search(r'(ZD-\d+)', path)
                    zd_ticket = zd_match.group(1) if zd_match else "Unknown"
                    print(f"  {i}. {zd_ticket}: s3://gt-logs/{path}")
                print("\nPlease specify the full S3 path or use interactive mode (-i)")
                return 1
            elif status == "none":
                print(f"❌ {data}")
                print(f"   No support packages found for Jira ticket {jira_id}")
                return 1
            else:  # error
                print(f"❌ {data}")
                return 1

        # Parse the S3 path
        bucket, key = helper.parse_s3_path(download_input)
        if not bucket or not key:
            print(f"❌ Invalid S3 path or ticket ID: {download_input}")
            return 1

        # Determine AWS profile
        aws_profile = args.aws_profile or helper.get_default_aws_profile() or "gt-logs"

        # Check authentication
        print(f"Checking AWS authentication...")
        if not helper.check_aws_authentication(aws_profile, debug=helper.debug):
            print(f"⚠️  AWS profile '{aws_profile}' is not authenticated")
            if not helper.aws_sso_login(aws_profile):
                print("❌ Cannot proceed without authentication")
                return 1

        # Determine output path - use smart path if configured and no explicit output
        if args.output_path:
            output_path = os.path.expanduser(args.output_path)
        else:
            # Try smart path based on ZD ticket
            smart_path, zd_number = helper.get_smart_download_path(key)
            if smart_path:
                output_path = os.path.dirname(smart_path)
                print(f"💡 Using configured download directory: {output_path}")
                if not os.path.exists(output_path):
                    os.makedirs(output_path, exist_ok=True)
                    print(f"✓ Created directory: {output_path}")
            else:
                output_path = "."

        # If downloading a directory, list and prompt
        if key.endswith("/"):
            print(f"\n🔍 Listing files in s3://{bucket}/{key}...\n")
            files = helper.list_s3_files(bucket, key, aws_profile)
            if not files:
                # Check if this is a zendesk-tickets path - if so, try exa-to-gt fallback
                if key.startswith("zendesk-tickets/"):
                    # Extract ZD ID from the key
                    zd_match = re.search(r'(ZD-\d+)', key)
                    if zd_match:
                        zd_id = zd_match.group(1)
                        print(f"❌ No files found in s3://{bucket}/{key}")
                        print(f"🔍 Checking exa-to-gt/ for {zd_id} with Jira tickets...\n")

                        # Search exa-to-gt for this ZD ID
                        status, data = helper.find_s3_path_by_zendesk_id(zd_id, aws_profile)

                        if status == "found":
                            # Single match found - use it automatically in CLI mode
                            print(f"✓ Found alternative path: s3://gt-logs/{data}")
                            bucket = "gt-logs"
                            key = data
                            print(f"\n🔍 Listing files in s3://{bucket}/{key}...\n")
                            files = helper.list_s3_files(bucket, key, aws_profile)
                            if not files:
                                print(f"❌ No files found in s3://{bucket}/{key}")
                                return 1
                        elif status == "multiple":
                            # Multiple matches found - show and error (CLI mode)
                            print(f"❌ Multiple alternative paths found for {zd_id}:")
                            for i, path in enumerate(data, 1):
                                # Extract Jira ID from path for display
                                jira_match = re.search(r'(RED|MOD)-\d+', path)
                                jira_id = jira_match.group(0) if jira_match else "Unknown"
                                print(f"  {i}. {jira_id}: s3://gt-logs/{path}")
                            print("\nPlease specify the full S3 path or use interactive mode (-i)")
                            return 1
                        else:
                            # No matches in exa-to-gt either
                            print(f"❌ No files found in exa-to-gt/ for {zd_id}")
                            return 1
                    else:
                        print(f"❌ No files found")
                        return 1
                else:
                    print(f"❌ No files found")
                    return 1

            print(f"Found {len(files)} file(s). Downloading all...")
            for file in files:
                local_path = os.path.join(output_path, os.path.basename(file))
                helper.download_from_s3(bucket, file, local_path, aws_profile)
        else:
            # Single file download
            local_path = os.path.join(output_path, os.path.basename(key))
            if helper.download_from_s3(bucket, key, local_path, aws_profile):
                print(f"✅ Downloaded to: {local_path}")
            else:
                # Check if it might be a directory (missing trailing slash)
                if not key.endswith("/"):
                    print(f"\n💡 File download failed. Checking if this is a directory...\n")
                    dir_key = key + "/"
                    files = helper.list_s3_files(bucket, dir_key, aws_profile)

                    if files:
                        # It's a directory! Download all files
                        print(f"✓ Found {len(files)} file(s) in directory. Downloading all...\n")
                        for file in files:
                            file_local_path = os.path.join(output_path, os.path.basename(file))
                            helper.download_from_s3(bucket, file, file_local_path, aws_profile)
                    else:
                        return 1
                else:
                    return 1
        return 0

    # Handle directory upload mode
    if args.directory:
        # Require Zendesk ID for directory upload
        if not args.zendesk_id:
            print("❌ Error: Directory upload requires a Zendesk ID")
            parser.print_help()
            return 1

        try:
            # Validate Zendesk ID
            zd_formatted = helper.validate_zendesk_id(args.zendesk_id)

            # Validate Jira ID if provided
            jira_formatted = None
            if args.jira_id:
                jira_formatted = helper.validate_jira_id(args.jira_id)

            # Determine AWS profile
            default_profile = helper.get_default_aws_profile()
            used_profile = args.aws_profile or default_profile or "gt-logs"

            # Check authentication (unless dry-run)
            if not args.dry_run:
                print(f"\nChecking AWS authentication...")
                is_authenticated = helper.check_aws_authentication(used_profile)

                if not is_authenticated:
                    print(f"⚠️  AWS profile '{used_profile}' is not authenticated")
                    if not helper.aws_sso_login(used_profile):
                        print("❌ Cannot proceed without authentication\n")
                        return 1
                else:
                    print(f"✓ AWS profile '{used_profile}' is already authenticated\n")

            # Execute directory upload
            success_count, failure_count, _ = helper.execute_directory_upload(
                args.directory,
                zd_formatted,
                jira_formatted,
                used_profile,
                include_patterns=args.include_patterns,
                exclude_patterns=args.exclude_patterns,
                dry_run=args.dry_run,
                max_retries=args.max_retries,
                verify=args.verify
            )

            return 0 if failure_count == 0 else 1

        except ValueError as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            return 1

    # Interactive mode if no arguments or -i flag
    if args.interactive or (not args.zendesk_id and not args.jira_id and not args.download_path):
        # Check for updates before starting interactive mode
        print("🔍 Checking for updates...")
        update_info = check_for_updates()
        if update_info and update_info['available']:
            if prompt_for_update(update_info):
                # Update was installed, exit so user can restart
                return 0
        elif update_info:
            # Up to date, continue silently
            pass
        # If check failed (offline), continue silently

        return interactive_mode(debug=args.debug)

    # Require at least Zendesk ID for upload mode (Jira is optional)
    if not args.zendesk_id:
        parser.print_help()
        return 1

    try:
        default_profile = helper.get_default_aws_profile()
        # Use fallback to gt-logs if no profile is specified
        used_profile = args.aws_profile or default_profile or "gt-logs"

        # Validate Zendesk ID
        zd_formatted = helper.validate_zendesk_id(args.zendesk_id)

        # Validate Jira ID if provided
        jira_formatted = None
        if args.jira_id:
            # Check if it's a Jira URL
            if "/browse/" in args.jira_id.lower():
                jira_from_url = helper.extract_jira_id_from_url(args.jira_id)
                if jira_from_url:
                    args.jira_id = jira_from_url
                else:
                    print(f"❌ Could not extract Jira ID from URL: {args.jira_id}")
                    return 1
            jira_formatted = helper.validate_jira_id(args.jira_id)

        # Validate and collect file paths
        file_paths = []
        if args.support_package:
            for fpath in args.support_package:
                validated = helper.validate_file_path(fpath)
                file_paths.append(validated)

        # Handle multiple files vs single file
        if file_paths and len(file_paths) > 1:
            # Batch upload mode
            s3_path = helper.generate_s3_path(zd_formatted, jira_formatted)

            # Display batch upload info
            print("\n" + "="*70)
            print("GT Logs Helper - Batch Upload")
            print("="*70)
            print(f"\nS3 Destination:\n  {s3_path}")
            print(f"\nFiles to upload ({len(file_paths)}):")
            for i, fpath in enumerate(file_paths, 1):
                print(f"  {i}. {os.path.basename(fpath)}")
            print("\n" + "="*70)

            # Show profile info
            if not args.aws_profile and not default_profile:
                print("\nℹ️  Tip: Set a default AWS profile with --set-profile")
                print(f"ℹ️  Using fallback AWS profile: gt-logs")
            elif default_profile and not args.aws_profile:
                print(f"\nℹ️  Using default AWS profile: {default_profile}")

            # Handle --execute flag
            if args.execute:
                if not used_profile:
                    print("\n❌ Error: --execute requires an AWS profile (use -p or --set-profile)\n")
                    return 1

                print()

                # Check authentication
                is_authenticated = helper.check_aws_authentication(used_profile)

                if not is_authenticated:
                    print(f"⚠️  AWS profile '{used_profile}' is not authenticated")
                    # Automatically run AWS SSO login
                    if not helper.aws_sso_login(used_profile):
                        print("❌ Cannot proceed without authentication\n")
                        return 1
                else:
                    print(f"✓ AWS profile '{used_profile}' is already authenticated\n")

                # Execute batch upload
                success_count, failure_count, _ = helper.execute_batch_upload(
                    file_paths, zd_formatted, jira_formatted, used_profile,
                    max_retries=args.max_retries,
                    verify=args.verify
                )
                return 0 if failure_count == 0 else 1
            else:
                # Show AWS SSO login reminder
                if used_profile:
                    print(f"\n💡 Reminder: Authenticate with AWS SSO before running uploads:")
                    print(f"   aws sso login --profile {used_profile}")
                print()
                return 0

        else:
            # Single file or no file (template mode)
            single_file = file_paths[0] if file_paths else None

            cmd, s3_path = helper.generate_aws_command(
                args.zendesk_id,
                args.jira_id,
                single_file,
                args.aws_profile
            )

            # Display results
            print("\n" + "="*70)
            print("GT Logs Helper")
            print("="*70)
            print(f"\nS3 Path:\n  {s3_path}")
            print(f"\nAWS CLI Command:\n  {cmd}")
            print("\n" + "="*70)

            # Show helpful info
            if not single_file:
                print("\nℹ️  Tip: Use -f to specify the support package file path")
                print("ℹ️  Tip: Use -f multiple times for batch uploads (e.g., -f file1.tar.gz -f file2.tar.gz)")

            if not args.aws_profile and not default_profile:
                print("ℹ️  Tip: Set a default AWS profile with --set-profile")
                print(f"ℹ️  Using fallback AWS profile: gt-logs")
            elif default_profile and not args.aws_profile:
                print(f"ℹ️  Using default AWS profile: {default_profile}")

            # Handle --execute flag (only if we have a real file path)
            if args.execute:
                if not single_file:
                    print("\n❌ Error: --execute requires a file path (-f/--file)\n")
                    return 1

                if not used_profile:
                    print("\n❌ Error: --execute requires an AWS profile (use -p or --set-profile)\n")
                    return 1

                print()

                # Check authentication
                is_authenticated = helper.check_aws_authentication(used_profile)

                if not is_authenticated:
                    print(f"⚠️  AWS profile '{used_profile}' is not authenticated")
                    # Automatically run AWS SSO login
                    if not helper.aws_sso_login(used_profile):
                        print("❌ Cannot proceed without authentication\n")
                        return 1
                else:
                    print(f"✓ AWS profile '{used_profile}' is already authenticated\n")

                # Execute the upload
                success = helper.execute_s3_upload(cmd)
                return 0 if success else 1

            # Show AWS SSO login reminder (when not executing)
            if used_profile:
                print(f"\n💡 Reminder: Authenticate with AWS SSO before running the command:")
                print(f"   aws sso login --profile {used_profile}")
            else:
                print(f"\n💡 Reminder: Authenticate with AWS SSO before running the command:")
                print(f"   aws sso login --profile <your-aws-profile>")

            print()
            return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
