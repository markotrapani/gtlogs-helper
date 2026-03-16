# GT Logs Helper - Testing Documentation

**Current Version:** v1.9.4
**Last Updated:** 2026-03-15
**Test Status:** Automated tests passing (16/16) ✅ | Manual tests passing ✅

---

## Overview

This document covers comprehensive testing for GT Logs Helper v1.9.4, including:

- **Lightning-fast UX** (v1.5.x) - Auto-submit prompts and smart defaults
- **Enhanced terminal experience** (v1.4.x) - Cursor positioning and exit handling
- Upload mode with batch upload support (v1.2.0)
- Download mode with 'a' shortcut for all files (v1.2.0)
- Input validation and error handling
- AWS SSO authentication
- Keyboard controls (ESC, Ctrl+C, Ctrl+U, arrow keys)
- Auto-update mechanism

---

## Quick Test Commands

```bash
# Version and help
./gtlogs-helper.py --version
./gtlogs-helper.py -h

# Configuration
./gtlogs-helper.py --show-config
./gtlogs-helper.py --set-profile my-profile

# Interactive mode
./gtlogs-helper.py

# CLI upload (single file)
./gtlogs-helper.py 145980 RED-172041 -f file.tar.gz

# CLI upload (batch - NEW v1.2.0)
./gtlogs-helper.py 145980 -f file1.tar.gz -f file2.tar.gz -f file3.tar.gz --execute

# CLI download
./gtlogs-helper.py --download ZD-145980
```

---

## Test Categories

### 1. Basic Functionality

#### 1.1 Version and Help Display

```bash
./gtlogs-helper.py --version    # Should show v1.3.0
./gtlogs-helper.py -h           # Should show help with upload/download options
```

**Expected:**

- ✅ Version displays: "GT Logs Helper v1.3.0"
- ✅ Help text mentions batch upload and download features
- ✅ All command-line flags documented

#### 1.2 Configuration Management

```bash
./gtlogs-helper.py --show-config
./gtlogs-helper.py --set-profile my-profile
./gtlogs-helper.py --show-config  # Verify saved
```

**Expected:**

- ✅ Configuration saved to ~/.gtlogs-config.ini
- ✅ Default profile displayed correctly
- ✅ Profile persists across sessions

---

### 2. Upload Mode

#### 2.1 Single File Upload (Legacy Mode)

```bash
# ZD-only path
./gtlogs-helper.py 145980 -f test.tar.gz

# ZD + Jira path
./gtlogs-helper.py 145980 RED-172041 -f test.tar.gz

# With execution
echo "test" > test.txt
./gtlogs-helper.py 145980 -f test.txt --execute
rm test.txt
```

**Expected:**

- ✅ Generates correct S3 paths (zendesk-tickets/ or exa-to-gt/)
- ✅ AWS command properly formatted
- ✅ File validation works
- ✅ Execution triggers AWS CLI

#### 2.2 Batch Upload - CLI Mode (NEW v1.2.0)

```bash
# Create test files
echo "file1" > /tmp/test1.tar.gz
echo "file2" > /tmp/test2.tar.gz
echo "file3" > /tmp/test3.tar.gz

# Multiple -f flags
./gtlogs-helper.py 145980 RED-172041 \
  -f /tmp/test1.tar.gz \
  -f /tmp/test2.tar.gz \
  -f /tmp/test3.tar.gz \
  --execute

# Cleanup
rm /tmp/test1.tar.gz /tmp/test2.tar.gz /tmp/test3.tar.gz
```

**Expected:**

- ✅ All files validated before upload
- ✅ Progress tracking shows X/Y files
- ✅ Success/failure summary at end
- ✅ Duplicate files detected and skipped
- ✅ Individual file errors don't stop batch

#### 2.3 Batch Upload - Interactive Mode (NEW v1.2.0)

```bash
./gtlogs-helper.py
# Choose: 1 (Upload)
# Enter ZD: 145980
# Enter Jira: RED-172041
# Files: /tmp/test1.tar.gz, /tmp/test2.tar.gz, /tmp/test3.tar.gz
# Or add files iteratively
```

**Expected:**

- ✅ Comma-separated paths accepted
- ✅ Option to add more files after initial input
- ✅ 'done' command completes file selection
- ✅ Duplicate detection warns user
- ✅ Shows file count before upload

#### 2.4 Edge Cases

```bash
# Spaces in filenames
touch "test file with spaces.tar.gz"
./gtlogs-helper.py 145980 -f "test file with spaces.tar.gz"

# Special characters
touch "test@file#2024.tar.gz"
./gtlogs-helper.py 145980 -f "test@file#2024.tar.gz"

# Symlinks
ln -s test.txt test-link.txt
./gtlogs-helper.py 145980 -f test-link.txt

# Non-existent file (should fail)
./gtlogs-helper.py 145980 -f /nonexistent/file.tar.gz

# Directory instead of file (should fail)
./gtlogs-helper.py 145980 -f /tmp
```

**Expected:**

- ✅ Spaces handled correctly
- ✅ Special characters handled
- ✅ Symlinks followed and validated
- ❌ Non-existent files rejected with clear error
- ❌ Directories rejected with clear error

---

### 3. Download Mode

#### 3.1 File Listing

```bash
# List files from ZD-only path
./gtlogs-helper.py --download ZD-145980

# List files from ZD+Jira path
./gtlogs-helper.py --download ZD-145980-RED-172041

# Direct S3 path
./gtlogs-helper.py --download s3://gt-logs/zendesk-tickets/ZD-145980/
```

**Expected:**

- ✅ All files in directory listed
- ✅ File sizes shown (if available)
- ✅ Numbered list for selection
- ✅ Invalid paths rejected with clear error

#### 3.2 File Selection

```bash
./gtlogs-helper.py --download ZD-145980
# Select: 1,2,3        (multiple files)
# Select: all          (all files)
# Select: a            (shortcut for all - NEW v1.2.0)
# Select: 1            (single file)
```

**Expected:**

- ✅ Comma-separated numbers work
- ✅ 'all' selects all files
- ✅ 'a' shortcut works (NEW v1.2.0)
- ✅ Invalid numbers rejected
- ✅ Duplicate numbers handled

#### 3.3 Output Directory

```bash
# Default (current directory)
./gtlogs-helper.py --download ZD-145980 --output .

# Custom directory
./gtlogs-helper.py --download ZD-145980 --output ~/Downloads/

# Tilde expansion
./gtlogs-helper.py --download ZD-145980 --output ~/test/
```

**Expected:**

- ✅ Default to current directory
- ✅ Custom paths respected
- ✅ Tilde expansion works
- ✅ Directory created if doesn't exist (or error shown)

---

### 4. Input Validation

#### 4.1 Zendesk ID Validation

```bash
# Valid inputs
./gtlogs-helper.py 145980              # ✅ Numerical only
./gtlogs-helper.py ZD-145980           # ✅ Pre-formatted
./gtlogs-helper.py zd-145980           # ✅ Lowercase prefix

# Invalid inputs (should reject)
./gtlogs-helper.py 145980abc           # ❌ Letters in number
./gtlogs-helper.py abc145980           # ❌ Letters in number
./gtlogs-helper.py ZD-abc              # ❌ Non-numerical after prefix
```

**Expected:**

- ✅ Accepts numerical IDs with or without ZD- prefix
- ✅ Normalizes to ZD-###### format
- ❌ Rejects any non-numerical characters in ID
- ✅ Clear error message on rejection

#### 4.2 Jira ID Validation

```bash
# Valid inputs
./gtlogs-helper.py 145980 RED-172041   # ✅ RED- prefix
./gtlogs-helper.py 145980 MOD-12345    # ✅ MOD- prefix
./gtlogs-helper.py 145980 RED172041    # ✅ Auto-adds hyphen

# Invalid inputs (should reject)
./gtlogs-helper.py 145980 ABC-12345    # ❌ Invalid prefix
./gtlogs-helper.py 145980 RED-abc      # ❌ Non-numerical suffix
./gtlogs-helper.py 145980 12345        # ❌ Missing prefix
```

**Expected:**

- ✅ Accepts RED- and MOD- prefixes only
- ✅ Auto-formats RED172041 to RED-172041
- ❌ Rejects invalid prefixes
- ❌ Rejects non-numerical suffixes
- ✅ Clear error message on rejection

#### 4.3 S3 Path Parsing (Download Mode)

```bash
# Valid inputs
./gtlogs-helper.py --download s3://gt-logs/zendesk-tickets/ZD-145980/
./gtlogs-helper.py --download s3://gt-logs/exa-to-gt/ZD-145980-RED-172041/
./gtlogs-helper.py --download ZD-145980
./gtlogs-helper.py --download ZD-145980-RED-172041
./gtlogs-helper.py --download 145980

# Invalid inputs (should reject)
./gtlogs-helper.py --download invalid-path
./gtlogs-helper.py --download s3://wrong-bucket/path/
```

**Expected:**

- ✅ Full S3 paths parsed correctly
- ✅ Ticket IDs converted to paths
- ✅ Both ZD-only and ZD+Jira formats work
- ❌ Invalid paths rejected with helpful error

---

### 5. Interactive Mode

#### 5.1 Mode Selection

```bash
./gtlogs-helper.py
```

**Test:**

- Press 1 → Should enter upload mode
- Press 2 → Should enter download mode
- Press invalid (3, abc) → Should prompt retry
- Press ESC → Should exit
- Press Ctrl+C → Should exit gracefully
- Type 'exit' → Should exit

**Expected:**

- ✅ Mode selection menu displays
- ✅ Valid selections work
- ✅ Invalid selections prompt retry
- ✅ All exit methods work

#### 5.2 Interactive Upload Workflow

```bash
./gtlogs-helper.py
# Choose: 1
```

**Test flow:**

1. Enter Zendesk ID (validate)
2. Enter Jira ID (optional, validate)
3. Enter file path(s) (validate, batch support)
4. AWS profile (default or custom)
5. Execute confirmation

**Expected:**

- ✅ Each step validates input
- ✅ Invalid input offers retry
- ✅ Optional fields can be skipped
- ✅ Batch file entry works
- ✅ Execute confirmation works

#### 5.3 Interactive Download Workflow

```bash
./gtlogs-helper.py
# Choose: 2
```

**Test flow:**

1. Enter S3 path or ticket ID
2. View file listing
3. Select files (numbers, 'all', 'a')
4. Choose output directory
5. Execute confirmation

**Expected:**

- ✅ Path parsing works
- ✅ File listing displays
- ✅ Selection methods work
- ✅ Output directory validated
- ✅ Execute confirmation works

---

### 6. UX Enhancements (v1.4.x - v1.5.x)

#### 6.1 Auto-Submit Prompts (v1.5.x)

**Test update prompt:**

```bash
# Start from older version and check for updates
./gtlogs-helper.py
# Press Ctrl+U or wait for auto-check
```

Expected auto-submit behavior:

- Type 'y' → Immediately proceeds with update (no Enter needed)
- Type 'Y' → Immediately proceeds with update (no Enter needed)
- Type 'n' → Immediately cancels update (no Enter needed)
- Type 'N' → Immediately cancels update (no Enter needed)
- Press Enter alone → Defaults to 'Y' and proceeds with update
- Type invalid char (e.g., 'x') → Waits for Enter, then shows error and re-prompts
- Press ESC → Shows "\n\n👋 Exiting..." and exits gracefully
- Press Ctrl+C → Shows "\n\n👋 Exiting..." and exits gracefully

**Test mode selection:**

```bash
./gtlogs-helper.py
```

Expected auto-submit behavior:

- Type '1' → Immediately enters Upload mode (no Enter needed)
- Type 'u' or 'U' → Immediately enters Upload mode (no Enter needed)
- Type '2' → Immediately enters Download mode (no Enter needed)
- Type 'd' or 'D' → Immediately enters Download mode (no Enter needed)
- Press Enter alone → Defaults to '1' (Upload mode)
- Type invalid char (e.g., 'x') → Waits for Enter, then shows error and re-prompts
- Press ESC → Shows "👋 Exiting..." and exits gracefully

**Verification:**

- ✅ Y/n choices auto-submit instantly
- ✅ 1/U/2/D choices auto-submit instantly
- ✅ Enter key uses smart defaults (Y for update, 1 for upload)
- ✅ Invalid input shows error and re-prompts
- ✅ ESC/Ctrl+C exit gracefully with proper spacing

#### 6.2 Terminal Cursor Positioning (v1.4.x)

**Test cursor positioning:**

```bash
./gtlogs-helper.py
# At mode selection, type invalid input
Your choice: x[Enter]
❌ Invalid choice. Please enter 1/U or 2/D
                  ↑ Should be left-aligned, not indented
```

Expected behavior:

- All output after user input should be left-aligned
- No weird indentation or tabbing over
- Proper carriage returns (`\r\n`) in raw terminal mode

**Verification:**

- ✅ Error messages appear left-aligned
- ✅ Progress indicators appear left-aligned
- ✅ No cursor positioning artifacts
- ✅ Clean output throughout entire session

#### 6.3 Visual Enhancements (v1.4.x)

**Test mode selection display:**

```bash
./gtlogs-helper.py
```

Expected display:

```text
Select operation mode:
☁️ ⬆️  1 or U: UPLOAD to S3 (generate links and upload files)
☁️ ⬇️  2 or D: DOWNLOAD from S3 (retrieve files from existing paths)

Your choice:
```

**Verification:**

- ✅ Cloud emoji icons display correctly
- ✅ Proper spacing between emojis
- ✅ Clear visual distinction between upload/download
- ✅ Keyboard shortcuts (U/D) clearly indicated

---

### 7. Keyboard Controls

#### 7.1 ESC Key Detection

**Test in interactive mode:**

- Standalone ESC → Should exit immediately
- Arrow keys → Should NOT exit (properly ignored)
- ESC in escape sequence → Should be distinguished

**Expected:**

- ✅ ESC exits immediately (no Enter needed)
- ✅ Arrow keys don't trigger exit
- ✅ Terminal remains in normal state after exit

#### 7.2 Input History (Arrow Keys)

**Test:**

1. Run interactive mode
2. Enter Zendesk ID: 145980
3. Exit and restart
4. Press UP arrow at Zendesk prompt

**Expected:**

- ✅ UP arrow shows previous input (145980)
- ✅ DOWN arrow cycles forward
- ✅ History persists across sessions
- ✅ History file: ~/.gtlogs-history.json

#### 7.3 Special Controls

**Test in interactive mode:**

- Backspace → Should delete character
- Ctrl+C → Should exit cleanly
- Ctrl+U → Should check for updates
- Type 'exit', 'quit', 'q' → Should exit

**Expected:**

- ✅ Backspace deletes characters
- ✅ Ctrl+C exits gracefully
- ✅ Ctrl+U triggers update check
- ✅ Exit commands work

---

### 8. AWS Authentication

#### 7.1 Authenticated Profile

```bash
# Login first
aws sso login --profile gt-logs

# Test upload
./gtlogs-helper.py 145980 -f test.txt --execute
```

**Expected:**

- ✅ Authentication check passes
- ✅ No SSO login prompt
- ✅ Upload executes directly

#### 7.2 Unauthenticated Profile

```bash
# Logout (if possible)
aws sso logout --profile gt-logs

# Test upload
./gtlogs-helper.py 145980 -f test.txt --execute
```

**Expected:**

- ✅ Authentication check fails
- ✅ Automatic SSO login triggered
- ✅ User prompted to authenticate
- ✅ Upload proceeds after auth

#### 7.3 Invalid Profile

```bash
./gtlogs-helper.py 145980 -p nonexistent-profile -f test.txt --execute
```

**Expected:**

- ❌ Clear error about invalid profile
- ✅ Helpful message about profile configuration
- ❌ Upload doesn't proceed

#### 7.4 No Configuration (Fallback)

```bash
# Backup config
mv ~/.gtlogs-config.ini ~/.gtlogs-config.ini.backup

# Test
./gtlogs-helper.py 145980 -f test.txt

# Restore
mv ~/.gtlogs-config.ini.backup ~/.gtlogs-config.ini
```

**Expected:**

- ✅ Falls back to 'gt-logs' profile
- ✅ No crash or error
- ✅ Clear message about using default profile

---

### 9. Auto-Update Mechanism

#### 8.1 Version Check

```bash
./gtlogs-helper.py --version
```

**Expected:**

- ✅ Shows current version: v1.2.0
- ✅ Checks GitHub for updates (5 second timeout)
- ✅ If update available: shows version and release notes
- ✅ If up to date: "✓ You're up to date!"
- ✅ If offline: graceful failure with warning

#### 8.2 Ctrl+U in Interactive Mode

```bash
./gtlogs-helper.py
# Press Ctrl+U at any prompt
```

**Expected:**

- ✅ Update check triggers
- ✅ Shows update prompt if available
- ✅ 'y' downloads and installs
- ✅ 'n' returns to interactive mode
- ✅ Script exits after update
- ✅ Message to restart appears

#### 8.3 Update Execution

**Test when update available:**

1. Trigger update check
2. Choose 'y' to update

**Expected:**

- ✅ Backup created: gtlogs-helper.py.backup
- ✅ New version downloaded
- ✅ File permissions preserved (executable)
- ✅ Success message displayed
- ✅ Script exits with restart message
- ✅ After restart: new version active

#### 8.4 Update Failure and Rollback

**Simulate failure:**

- Network disconnects during download
- File permission issues
- Corrupted download

**Expected:**

- ✅ Error message displayed
- ✅ Rollback to previous version
- ✅ Backup restored if needed
- ✅ Script remains functional
- ✅ Clear recovery instructions

---

### 10. Performance Tests

#### 9.1 Large File Upload

```bash
# Create 100MB test file
dd if=/dev/zero of=/tmp/large_test.bin bs=1M count=100

# Upload
./gtlogs-helper.py 145980 -f /tmp/large_test.bin --execute

# Cleanup
rm /tmp/large_test.bin
```

**Expected:**

- ✅ File validated successfully
- ✅ Upload command generated
- ✅ AWS CLI handles large file
- ✅ No timeout or memory issues

#### 9.2 Batch Upload (Many Files)

```bash
# Create 20 small test files
for i in {1..20}; do echo "test$i" > /tmp/test$i.tar.gz; done

# Batch upload
./gtlogs-helper.py 145980 \
  $(for i in {1..20}; do echo "-f /tmp/test$i.tar.gz"; done) --execute

# Cleanup
rm /tmp/test*.tar.gz
```

**Expected:**

- ✅ All files validated
- ✅ Progress tracking accurate
- ✅ No performance degradation
- ✅ Summary shows all files

#### 9.3 Download from Large Directory

```bash
# Test with S3 directory containing many files
./gtlogs-helper.py --download ZD-145980
```

**Expected:**

- ✅ Listing completes quickly
- ✅ All files shown
- ✅ Selection works smoothly
- ✅ No timeout issues

---

## Latest Test Results

**Test Date:** November 13, 2024 (v1.1.0)
**Test Date:** January 14, 2025 (v1.2.0 - pending)
**Platform:** macOS
**Python:** 3.x

### Automated Test Results: ✅ ALL PASSED (17/17)

#### Phase 1: Basic Functionality ✅

- ✅ Version display shows correct version
- ✅ Help display shows upload/download description
- ✅ Configuration display works

#### Phase 2: Upload Mode ✅

- ✅ ZD-only path generation correct
- ✅ ZD+Jira path generation correct
- ✅ File path inclusion works
- ✅ Custom profile specification works

#### Phase 3: Input Validation ✅

- ✅ Invalid Zendesk ID rejected (letters)
- ✅ Invalid Jira ID rejected (wrong prefix)
- ✅ Non-existent file rejected
- ✅ Directory rejected when file expected

#### Phase 4: Download Mode ✅

- ✅ Download mode activates with --download flag
- ✅ Authentication check triggers

#### Phase 5: AWS Profile Handling ✅

- ✅ Fallback to 'gt-logs' when no config exists
- ✅ Profile properly added to commands

#### Phase 6: Edge Cases ✅

- ✅ Files with spaces handled correctly
- ✅ Pre-formatted ZD IDs accepted
- ✅ MOD Jira prefix supported

#### Phase 7: Path Parsing ✅

- ✅ Full S3 paths parsed correctly
- ✅ Ticket IDs converted to paths
- ✅ Invalid paths rejected

### v1.3.0 Automated Test Results

**Test Suite:** `tests/test_suite.py` (16 tests, 16 passed)
**Test Date:** January 15, 2025
**Pass Rate:** 100% ✅
**Version:** v1.3.0

**Batch Upload (v1.2.0):**

- ✅ Multiple -f flags in CLI mode
- ✅ Comma-separated paths in interactive mode
- ✅ Iterative file addition support
- ✅ Duplicate file handling (accepts duplicates in CLI mode)
- ✅ Progress tracking
- ✅ Success/failure summary

**Download 'a' Shortcut (v1.2.0):**

- ✅ Download mode activates correctly
- ✅ 'a' shortcut works with real S3 (E2E test)
- ✅ 'a' behaves identically to 'all'

**Error Handling:**

- ✅ Invalid file detection in batch uploads
- ✅ Execute flag with batch operations

---

## Manual Testing Checklist

Use this checklist for comprehensive manual testing:

### Basic Features

- [ ] Version display correct
- [ ] Help text complete and accurate
- [ ] Configuration save/load works
- [ ] Default profile persists

### Upload Mode

- [ ] Single file upload works
- [ ] Batch upload (CLI) works
- [ ] Batch upload (interactive) works
- [ ] Duplicate detection works
- [ ] Progress tracking accurate
- [ ] Success/failure summary correct

### Download Mode

- [ ] File listing works
- [ ] Single file selection works
- [ ] Multiple file selection works
- [ ] 'all' command works
- [ ] 'a' shortcut works (v1.2.0)
- [ ] Output directory selection works

### Input Validation

- [ ] ZD ID validation strict
- [ ] Jira ID validation strict
- [ ] File path validation works
- [ ] S3 path parsing correct
- [ ] Error messages helpful

### Interactive Mode

- [ ] Mode selection works
- [ ] Upload workflow complete
- [ ] Download workflow complete
- [ ] ESC key exits immediately
- [ ] Arrow keys don't trigger exit
- [ ] Input history works
- [ ] Ctrl+C exits cleanly
- [ ] Ctrl+U triggers update check

### AWS Authentication

- [ ] Authenticated profile works
- [ ] Unauthenticated triggers SSO
- [ ] Invalid profile shows error
- [ ] Fallback to default works

### Auto-Update

- [ ] Version check works
- [ ] Ctrl+U works in interactive mode
- [ ] Update download works
- [ ] Backup created
- [ ] Rollback on failure works
- [ ] Offline behavior graceful

### Edge Cases

- [ ] Spaces in filenames work
- [ ] Special characters handled
- [ ] Symlinks followed
- [ ] Large files work
- [ ] Many files in batch work
- [ ] Network timeout handled

---

## Known Issues & Limitations

### Current Limitations (v1.2.0)

1. **Windows Support for ESC Detection**
   - termios/tty unavailable on Windows
   - Falls back to regular input() (no immediate ESC)
   - Exit via Ctrl+C or typing "exit" still works

2. **AWS CLI Required**
   - Tool generates commands but requires AWS CLI installed
   - No built-in S3 upload/download capability
   - Relies on user's AWS SSO configuration

3. **Directory Upload Not Supported**
   - Can upload multiple individual files (v1.2.0)
   - No recursive directory upload
   - Files must be specified individually

4. **No Upload Progress Bars**
   - AWS CLI shows its own progress
   - Tool only shows file count progress (X/Y files)
   - Large file uploads have no intermediate progress

### Bug Fixes in v1.2.0

**AWS Profile Crash (Fixed in v1.1.0):**

- Issue: Script crashed when no default AWS profile configured
- Root cause: aws_profile was set to None
- Fix: Added consistent fallback to 'gt-logs' profile

---

## Success Criteria

The tool is considered production-ready when:

✅ **Core functionality:** All upload/download operations work
✅ **Input validation:** Strict validation prevents errors
✅ **Batch operations:** Multiple files upload successfully (v1.2.0)
✅ **Download UX:** 'a' shortcut works as expected (v1.2.0)
✅ **AWS integration:** Authentication and execution reliable
✅ **Keyboard controls:** ESC, arrows, history all work
✅ **Auto-update:** Update check and installation work
✅ **Error handling:** Clear messages for all failures
✅ **Cross-platform:** Works on macOS and Linux (Windows partial)

---

## Test Environment

### Recommended Setup

- **OS:** macOS or Linux (Windows partial support)
- **Python:** 3.6+ (for f-strings and type hints)
- **AWS CLI:** Latest version installed and configured
- **Network:** Internet connection for S3 and update checks
- **Terminal:** Standard terminal emulator (Terminal.app, iTerm2, gnome-terminal)

### Test Data

```bash
# Create test files
echo "test1" > /tmp/test1.tar.gz
echo "test2" > /tmp/test2.tar.gz
echo "test3" > /tmp/test3.tar.gz

# Test Zendesk IDs
145980, 123456, ZD-145980

# Test Jira IDs
RED-172041, MOD-12345, RED172041

# Test S3 paths
s3://gt-logs/zendesk-tickets/ZD-145980/
s3://gt-logs/exa-to-gt/ZD-145980-RED-172041/
```

---

## Debugging Tips

### Enable Debug Output

Add debug prints to key functions when troubleshooting:

```python
# In validate_zendesk_id()
print(f"[DEBUG] Input ZD: '{zd_id}', Number part: '{zd_number}'")

# In check_aws_authentication()
print(f"[DEBUG] Running: {' '.join(cmd)}")
print(f"[DEBUG] Return code: {result.returncode}")

# In input_with_esc_detection()
print(f"[DEBUG] Raw char: {repr(ch)}")
```

### Common Issues

**Issue:** Arrow keys trigger exit
**Fix:** Increase VTIME in terminal settings (gtlogs-helper.py:349)

**Issue:** Terminal broken after crash
**Fix:** Run `reset` command to restore terminal

**Issue:** AWS authentication fails silently
**Fix:** Check timeout in check_aws_authentication() (gtlogs-helper.py:206)

**Issue:** File validation fails on valid paths
**Fix:** Check os.path.expanduser() and os.path.exists() results

**Issue:** Batch upload stops on first error
**Fix:** Verify error handling continues to next file

---

## References

- [README.md](../README.md) - User documentation
- [CLAUDE.md](CLAUDE.md) - Development guidelines
- [ROADMAP.md](ROADMAP.md) - Future enhancements
- AWS CLI Documentation: <https://docs.aws.amazon.com/cli/>
- Python termios: <https://docs.python.org/3/library/termios.html>

---

**Document Version:** 2.0 (v1.2.0)
**Author:** Claude Code
**Maintainer:** <marko.trapani@redis.com>
