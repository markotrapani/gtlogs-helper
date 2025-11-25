# GT Logs Helper

A lightning-fast command-line tool for uploading and downloading Redis Support
packages to/from AWS S3. Streamline your workflow with automatic
authentication, batch operations, and intelligent path generation.

**Current Version:** v1.7.4 |
**[View Wiki](https://github.com/markotrapani/gtlogs-helper/wiki)** |
**[Changelog](#whats-new)**

---

## Quick Start

```bash
# Interactive mode (recommended for first-time users)
./gtlogs-helper.py

# Upload a file (auto-executes with AWS SSO)
./gtlogs-helper.py 145980 RED-172041 -f /path/to/package.tar.gz --execute

# Upload entire directory with pattern filtering
./gtlogs-helper.py 145980 --dir /path/to/directory \
  --include "*.tar.gz" --exclude "*.log" --execute

# Download files from a ticket
./gtlogs-helper.py --download ZD-145980
```

**[➜ See More Examples](https://github.com/markotrapani/gtlogs-helper/wiki/Usage-Examples)**
|
**[➜ Full Command Reference](https://github.com/markotrapani/gtlogs-helper/wiki/Command-Reference)**

---

## Key Features

- ⚡ **Lightning-fast UX** - Auto-submit prompts, smart defaults, instant feedback
- 📤 **Upload Mode** - Generate S3 paths for ZD-only or ZD+Jira scenarios
- 📥 **Download Mode** - List, select, and download files from S3
- 🎯 **Jira-based Download** - Paste Jira URL or ID to auto-find support packages
- 📂 **Smart Download Paths** - Auto-organize downloads into ZD ticket subfolders
- 📁 **Directory Upload** - Upload entire directories with pattern filtering
  and dry-run mode
- 🔄 **Batch Operations** - Upload/download multiple files simultaneously
- 🔐 **Auto-Authentication** - Automatic AWS SSO login handling
- 📝 **Input History** - Arrow key navigation through previous inputs
- ⌨️ **Keyboard Controls** - ESC to exit, Ctrl+U to update, UP/DOWN for
  history
- ✅ **Input Validation** - Strict validation for Zendesk IDs, Jira IDs, and
  file paths

**[➜ Full Feature List](https://github.com/markotrapani/gtlogs-helper/wiki#key-features)**

---

## Installation

```bash
# Clone the repository
git clone https://github.com/markotrapani/gtlogs-helper.git
cd gtlogs-helper

# Make executable
chmod +x gtlogs-helper.py

# Optional: Add to PATH
echo "alias gtlogs='$(pwd)/gtlogs-helper.py'" >> ~/.zshrc
source ~/.zshrc
```

**Requirements:** Python 3.6+, AWS CLI, AWS SSO access to `gt-logs` bucket

**[➜ Detailed Installation Guide](https://github.com/markotrapani/gtlogs-helper/wiki/Getting-Started)**

---

## Usage

### Interactive Mode

Run without arguments for guided prompts:

```bash
./gtlogs-helper.py
```

**Keyboard controls:**

- **ESC** - Exit immediately
- **Ctrl+C** - Exit gracefully
- **Ctrl+U** - Check for updates
- **UP/DOWN** - Navigate input history
- Type `exit`, `quit`, or `q` - Exit at any prompt

### Upload Examples

```bash
# ZD-only (no Jira) - Most common
./gtlogs-helper.py 145980 -f /path/to/package.tar.gz --execute

# ZD + Jira (Engineering escalation)
./gtlogs-helper.py 145980 RED-172041 -f /path/to/package.tar.gz --execute

# Batch upload multiple files
./gtlogs-helper.py 145980 RED-172041 \
  -f file1.tar.gz -f file2.tar.gz -f file3.tar.gz --execute
```

### S3 Path Structure

**Without Jira (ZD-only):**

```text
s3://gt-logs/zendesk-tickets/ZD-145980/package.tar.gz
```

Use for Redis Cloud environments without Engineering involvement.

**With Jira (ZD + Jira):**

```text
s3://gt-logs/exa-to-gt/ZD-145980-RED-172041/package.tar.gz
```

Use for Engineering escalation via Jira tickets (RED-# or MOD-#).

### Download Examples

```bash
# Download from Zendesk ticket (lists files for selection)
./gtlogs-helper.py --download ZD-145980

# Download from Jira ticket (auto-finds associated ZD ticket)
./gtlogs-helper.py --download RED-177450

# Download from Jira URL
./gtlogs-helper.py --download https://redislabs.atlassian.net/browse/RED-177450

# Download specific file
./gtlogs-helper.py --download s3://gt-logs/zendesk-tickets/ZD-145980/file.tar.gz

# Download to custom directory
./gtlogs-helper.py --download ZD-145980 --output ~/Downloads/
```

**[➜ More Usage Examples](https://github.com/markotrapani/gtlogs-helper/wiki/Usage-Examples)**

---

## Configuration

### Set Default AWS Profile

```bash
./gtlogs-helper.py --set-profile gt-logs
```

Profile is saved to `~/.gtlogs-config.ini` and used for all operations.

### Set Default Download Directory

```bash
./gtlogs-helper.py --set-download-dir ~/Downloads/packages
```

When downloading files, they will automatically be organized into subfolders
named by Zendesk ticket number:

```text
~/Downloads/packages/
├── 150576/
│   └── debuginfo.tar.gz
├── 145980/
│   └── support-package.tar.gz
└── 172041/
    └── cluster-logs.tar.gz
```

### View Configuration

```bash
./gtlogs-helper.py --show-config
```

### Configuration Files

**Config file:** `~/.gtlogs-config.ini`

- Stores default AWS profile and download directory
- Commands: `--set-profile`, `--set-download-dir`, `--show-config`

**History file:** `~/.gtlogs-history.json`

- Stores last 20 inputs per field
- Navigate with UP/DOWN arrows in interactive mode
- Preserved on ESC/Ctrl+C exit

---

## Input Validation

All inputs are strictly validated:

- **Zendesk IDs:** Numerical ticket ID with optional 'ZD-' prefix
  - ✅ Valid: `145980`, `ZD-145980`, `zd-145980`
  - ❌ Invalid: `145980abc`, `ZD-abc`

- **Jira IDs:** Must be `RED-#` or `MOD-#` with numerical suffix
  - ✅ Valid: `RED-172041`, `MOD-12345`, `RED172041` (auto-formatted)
  - ❌ Invalid: `RED-172041abc`, `ABC-12345`, `172041`

- **File Paths:** Must exist and be files (not directories)
  - ✅ Valid: `/existing/file.tar.gz`, `~/Downloads/package.tar.gz`
  - ❌ Invalid: `/nonexistent/file.tar.gz`, `/tmp` (directory)

**[➜ Detailed Validation Rules](https://github.com/markotrapani/gtlogs-helper/wiki/Command-Reference#input-validation)**

---

## Documentation

### User Documentation

- **[Getting Started](https://github.com/markotrapani/gtlogs-helper/wiki/Getting-Started)**
  \- Installation and first-run guide
- **[Usage Examples](https://github.com/markotrapani/gtlogs-helper/wiki/Usage-Examples)**
  \- Detailed scenarios and workflows
- **[Command Reference](https://github.com/markotrapani/gtlogs-helper/wiki/Command-Reference)**
  \- Complete CLI options

### Developer Documentation

- **[Development Guide](https://github.com/markotrapani/gtlogs-helper/wiki/Development-Guide)**
  \- Contributing guidelines
- **[Testing](https://github.com/markotrapani/gtlogs-helper/wiki/Testing)**
  \- Testing documentation
- **[Roadmap](https://github.com/markotrapani/gtlogs-helper/wiki/Roadmap)**
  \- Future plans and priorities
- **[CLAUDE.md](CLAUDE.md)** - AI development instructions
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

---

## Requirements

- **Python 3.6+** (no external dependencies - uses standard library only)
- **AWS CLI** installed and configured
- **AWS SSO access** to the `gt-logs` S3 bucket

### AWS Authentication

Authenticate before first use:

```bash
aws sso login --profile gt-logs
```

Or use `--execute` mode - the tool will automatically run `aws sso login` if
needed!

### Troubleshooting Authentication

**Session Expired:**

```bash
# Error: The SSO session associated with this profile has expired
# Solution: Re-authenticate
aws sso login --profile gt-logs
```

**Permission Errors:**

```bash
# Error: Access Denied or 403 Forbidden
# Solutions:
# 1. Verify you have permissions to write to the gt-logs bucket
# 2. Check you're using the correct AWS profile
# 3. Ensure your SSO session is still valid
aws sso login --profile gt-logs
aws sts get-caller-identity --profile gt-logs  # Verify identity
```

---

## Self-Update

The tool automatically checks for updates on startup. You can also:

```bash
# Check version and updates
./gtlogs-helper.py --version

# Or press Ctrl+U during interactive mode
```

Updates are installed with your permission. Your previous version is
automatically backed up.

### Update Process Details

**What happens:**

1. Downloads latest release from GitHub
2. Creates backup: `gtlogs-helper.py.backup`
3. Replaces current script with new version
4. Sets executable permissions
5. On failure: automatically restores from backup

**Manual rollback:**

```bash
mv gtlogs-helper.py.backup gtlogs-helper.py
chmod +x gtlogs-helper.py
```

---

## Command Reference

### Running Modes

```bash
./gtlogs-helper.py                    # Interactive mode (choose upload/download)
./gtlogs-helper.py -i                 # Force interactive mode
./gtlogs-helper.py <zd> [jira]        # Upload mode (CLI)
./gtlogs-helper.py --download <path>  # Download mode (CLI)
```

### Common Commands

```bash
# Upload
./gtlogs-helper.py 145980 -f file.tar.gz --execute
./gtlogs-helper.py 145980 RED-172041 -f file.tar.gz -e

# Batch upload
./gtlogs-helper.py 145980 -f file1.tar.gz -f file2.tar.gz -f file3.tar.gz -e

# Download
./gtlogs-helper.py --download ZD-145980
./gtlogs-helper.py -d ZD-145980 --output ~/Downloads/

# Configuration
./gtlogs-helper.py --set-profile gt-logs
./gtlogs-helper.py --show-config

# Debug & Troubleshooting
./gtlogs-helper.py --debug  # Show timing and authentication details

# Version/Help
./gtlogs-helper.py --version
./gtlogs-helper.py --help
```

**[➜ Complete Command Reference](https://github.com/markotrapani/gtlogs-helper/wiki/Command-Reference)**

---

## Testing

The project includes comprehensive automated testing:

```bash
# Run test suite
python3 tests/test_suite.py

# Expected: 62/62 tests passing
```

**Test coverage:**

- Input validation (Zendesk IDs, Jira IDs, file paths)
- S3 path generation (ZD-only, ZD+Jira)
- AWS authentication handling
- Batch operations (upload/download)
- Directory upload (dry-run, patterns, error handling)
- Resume/retry functionality
- Smart download directory (v1.7.3+)
- Configuration management

**[➜ Testing Documentation](https://github.com/markotrapani/gtlogs-helper/wiki/Testing)**

---

## What's New

### v1.7.4 - Progress Bar Fix

- 🐛 **Fixed progress bar newline bug** - Progress bar now correctly overwrites
  the same line instead of printing each update on a new line

### v1.7.3 - Smart Download Directory

- 📂 **Configurable download directory** - Set a default download location with
  `--set-download-dir ~/Downloads/packages`
- 🎯 **Auto-organized by Zendesk ticket** - Downloads automatically go into
  subfolders named by ticket number (e.g., `~/Downloads/packages/150576/`)
- 💡 **Smart path suggestions** - Interactive mode suggests the configured path,
  just press Enter to accept

### v1.7.2 - Progress Bar Display Fix

- 🐛 **Fixed progress bar artifacts** - Resolved issue where ETA text would
  overlap (e.g., "3sss44s" instead of "3s") during downloads by properly
  clearing previous line content

### v1.7.1 - Jira-Based Download & Smart Fallback

- 🎯 **Jira-based download** - Download packages using just Jira URL or ID,
  automatically finds associated Zendesk ticket
- 🔍 **Smart S3 search** - Searches both `zendesk-tickets/` and `exa-to-gt/`
  locations for ZD tickets
- 📂 **Directory auto-detection** - Handles paths without trailing slashes,
  automatically retries as directory on 404
- 🔧 **Multiple match handling** - Interactive selection when multiple packages
  found for same Jira ticket

### v1.7.0 - Smart Input Detection & URL Decoding

- 🎯 **Smart clipboard detection** - Automatic format recognition with helpful
  feedback for pasted input (Zendesk URLs, Jira URLs, S3 URIs, ticket IDs)
- 🔓 **URL decoding** - Handles special characters like `%20` (space),
  `%2B` (+) in S3 paths copied from browsers
- 🧠 **Enhanced input validation** - Better error messages showing detected
  format and expected formats

### v1.6.2 - Enhanced Input Format Support

- 🔗 **Jira URL support** - Paste Jira ticket URLs directly:
  `https://jira.company.com/browse/RED-172041`
- 📂 **Partial S3 path support** - Paste S3 keys without full URIs:
  `zendesk-tickets/ZD-145980/file.tar.gz` → auto-prepends `gt-logs` bucket
- 🐛 **Tilde expansion fix** - `~` character now correctly expands to home
  directory in download paths
- 🔧 **Improved parsing** - Better handling of combined ZD+Jira ID formats

### v1.6.1 - Performance & UX Improvements

- ⚡ **Fast SSO auth check** - Local cache check (<100ms) before network call,
  dramatically faster authentication
- 🐛 **Debug flag** - New `--debug` flag shows timing and authentication
  details when troubleshooting
- 🔗 **Zendesk URL support** - Paste ticket URLs directly:
  `https://redislabs.zendesk.com/agent/tickets/150002`
- 📍 **Full path display** - Downloads now show complete absolute path to
  saved files
- 🔧 **Type safety** - Fixed all Pylance warnings for better IDE support
- 📅 **Datetime fix** - Resolved deprecation warning for Python 3.11+
  compatibility

### v1.6.0 - Upload/Download Resume with Retry and Verification

- 🔄 **Resume capability** - Automatically resume interrupted
  uploads/downloads
- 🔁 **Automatic retry** - Exponential backoff retry for failed transfers
  (configurable attempts)
- ✅ **Upload verification** - S3 file size validation after upload
- 💾 **State management** - Persistent state tracking across interruptions
- 🎛️ **New CLI arguments** - `--max-retries`, `--verify`, `--no-resume`,
  `--clean-state`
- 🐛 **Critical bug fix** - Auto-update now uses proper semantic versioning
  (prevents downgrades)

### v1.5.3 - Directory Upload with Pattern Filtering

- 📁 **Directory upload** - Upload entire directories with preserved structure
- 🎯 **Pattern filtering** - Include/exclude files with wildcard patterns
- 👀 **Dry-run mode** - Preview uploads before execution
- 📊 **Batch progress** - Track upload progress for all files in directory

### Previous Releases

#### v1.5.2 - Real-Time Progress Tracking

- 📊 **Progress bars** - Visual progress for uploads and downloads with speed
  and ETA
- 📈 **File size tracking** - See completed/total bytes in real-time
- ⚡ **Transfer speed** - Live speed indicators (MB/s)
- ⏱️  **ETA calculation** - Estimated time remaining for transfers

#### v1.5.1 - Lightning-Fast Interactive Experience

- ⚡ **Auto-submit inputs** - Type 'y', 'n', '1', 'u', '2', or 'd' without
  pressing Enter
- 🎯 **Smart defaults** - Enter key defaults to "Yes" for updates, "Upload"
  for mode selection
- ✨ **Enhanced UI** - Cloud emoji icons (☁️ ⬆️  / ☁️ ⬇️ ) and cleaner
  displays
- 👋 **Graceful exits** - Consistent ESC/Ctrl+C handling across all prompts

#### v1.4.x - UX Polish

- Fixed terminal cursor positioning in raw mode
- Improved error message clarity with grouped equivalent choices
- Enhanced mode selection with U/D keyboard shortcuts

#### v1.3.0 - Testing Infrastructure

- Comprehensive test suite with 16 automated tests (100% pass rate)
- End-to-end testing with real S3 bucket access
- Automatic AWS SSO authentication in tests
- MIT License and CONTRIBUTING.md for open collaboration

#### v1.2.0 - Batch Operations

- Batch upload multiple files to same S3 destination
- Interactive mode: Comma-separated paths or iterative addition
- CLI mode: Multiple `-f` flags
- Download UX: Press `a` to download all files

#### v1.1.0 - Download Support

- Complete S3 download functionality
- Mode selection (Upload/Download)
- Batch download support
- Self-update capability with version checking
- Input history with arrow key navigation

#### v1.0.0 - Initial Release

- Upload mode with ZD-only and ZD+Jira paths
- Input validation (Zendesk IDs, Jira IDs, file paths)
- Interactive and CLI modes
- AWS SSO authentication handling
- Configuration persistence

**[➜ Full Roadmap](https://github.com/markotrapani/gtlogs-helper/wiki/Roadmap)**

---

## Contributing

Contributions are welcome! Please see:

- **[Contributing Guide](CONTRIBUTING.md)** - Guidelines and workflow
- **[Development Guide](https://github.com/markotrapani/gtlogs-helper/wiki/Development-Guide)**
  \- Architecture and coding standards
- **[Roadmap](https://github.com/markotrapani/gtlogs-helper/wiki/Roadmap)**
  \- Planned features

### Quick Contribution Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes following coding standards
4. Run tests: `python3 tests/test_suite.py`
5. Lint markdown: `markdownlint '**/*.md' --ignore node_modules --ignore venv`
6. Commit: `git commit -m "feat: Your feature description"`
7. Push and create pull request

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Support

**Questions or Issues?**

- **Contact:** <marko.trapani@redis.com>
- **GitHub Issues:** [github.com/markotrapani/gtlogs-helper/issues](https://github.com/markotrapani/gtlogs-helper/issues)
- **Wiki:** [github.com/markotrapani/gtlogs-helper/wiki](https://github.com/markotrapani/gtlogs-helper/wiki)

---

## Acknowledgments

Built with [Claude Code](https://claude.com/claude-code) for Redis Support Engineering.
