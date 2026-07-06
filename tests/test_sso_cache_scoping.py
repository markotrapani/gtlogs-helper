#!/usr/bin/env python3
"""Regression tests for SSO cache scoping in check_sso_cache().

Bug (pre-v1.11.2): check_sso_cache() looped over EVERY *.json in
~/.aws/sso/cache/ and returned True as soon as it found any non-expired
access token — regardless of which SSO session that token belonged to.

Symptom: a valid token for an unrelated profile/session (e.g. 'markot')
caused the tool to report "✓ authenticated" for 'gt-logs', then the actual
S3 operation failed with:
    fatal error: Error when retrieving token from sso:
    Token has expired and refresh failed

These tests build a fake $HOME with an .aws/config + .aws/sso/cache and
assert the check only trusts the token belonging to the profile's own SSO
session (matched by the startUrl field inside each cache file).

Run directly:  python3 tests/test_sso_cache_scoping.py
"""

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_module():
    """Import gtlogs-helper.py (hyphenated filename -> importlib)."""
    here = Path(__file__).resolve().parent
    module_path = here.parent / "gtlogs-helper.py"
    spec = importlib.util.spec_from_file_location("gtlogs_helper", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GT_LOGS_URL = "https://d-90675fffd4.awsapps.com/start"
OTHER_URL = "https://d-9a672d5d56.awsapps.com/start"

CONFIG = """\
[profile gt-logs]
sso_session = gt-logs
sso_account_id = 168085023892
sso_role_name = s3_gt_logs_access
region = us-east-1
output = json

[sso-session gt-logs]
sso_start_url = {gt_logs_url}
sso_region = us-east-1
sso_registration_scopes = sso:account:access

[sso-session markot]
sso_start_url = {other_url}
sso_region = us-east-2
sso_registration_scopes = sso:account:access
""".format(gt_logs_url=GT_LOGS_URL, other_url=OTHER_URL)


def _iso(dt):
    # Match the AWS CLI cache format: "...Z"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_home(tmp, token_files):
    """Create tmp/.aws/{config,sso/cache/*.json}. token_files: list of dicts."""
    aws = Path(tmp) / ".aws"
    cache = aws / "sso" / "cache"
    cache.mkdir(parents=True)
    (aws / "config").write_text(CONFIG)
    for i, data in enumerate(token_files):
        (cache / f"token_{i}.json").write_text(json.dumps(data))
    return tmp


def _run(module, token_files):
    with tempfile.TemporaryDirectory() as tmp:
        _build_home(tmp, token_files)
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = tmp
        try:
            return module.GTLogsHelper.check_sso_cache("gt-logs")
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


def main():
    module = _load_module()
    future = datetime.now(timezone.utc) + timedelta(hours=4)
    past = datetime.now(timezone.utc) - timedelta(hours=4)

    results = []

    def check(name, actual, expected):
        ok = actual is expected
        results.append(ok)
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"{status} - {name} (got {actual!r}, expected {expected!r})")

    # THE BUG: gt-logs token expired, an unrelated session's token still valid.
    # Must NOT report authenticated for gt-logs.
    check(
        "expired gt-logs token + valid unrelated token -> not authenticated",
        _run(module, [
            {"accessToken": "x", "startUrl": GT_LOGS_URL, "expiresAt": _iso(past)},
            {"accessToken": "y", "startUrl": OTHER_URL, "expiresAt": _iso(future)},
        ]),
        False,
    )

    # Positive control: gt-logs' own token is valid -> authenticated.
    check(
        "valid gt-logs token -> authenticated",
        _run(module, [
            {"accessToken": "x", "startUrl": GT_LOGS_URL, "expiresAt": _iso(future)},
        ]),
        True,
    )

    # Trailing-slash normalization: cache stores start URL with trailing slash.
    check(
        "valid gt-logs token with trailing-slash startUrl -> authenticated",
        _run(module, [
            {"accessToken": "x", "startUrl": GT_LOGS_URL + "/", "expiresAt": _iso(future)},
        ]),
        True,
    )

    # No token for gt-logs' session at all -> not a confident True.
    # (None = inconclusive, defer to network check; False also acceptable.
    #  The only unacceptable answer is True.)
    only_other = _run(module, [
        {"accessToken": "y", "startUrl": OTHER_URL, "expiresAt": _iso(future)},
    ])
    check(
        "only unrelated valid token -> must not be True",
        only_other is not True,
        True,
    )

    print()
    if all(results):
        print(f"All {len(results)} tests passed.")
        return 0
    print(f"{results.count(False)}/{len(results)} tests FAILED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
