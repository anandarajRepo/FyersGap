"""
FyersGap — Fyers API v3 authentication helper.

Fyers uses an OAuth 2.0 authorization-code flow:
  Step 1: Generate an authorization URL and open it in a browser.
  Step 2: User logs in and is redirected to redirect_uri with ?auth_code=...&state=...
  Step 3: Exchange the auth_code for an access_token.
  Step 4: Use the access_token for all subsequent API calls.

Credentials required (via .env):
  FYERS_APP_ID       App ID from the Fyers API portal (format: APPID-100)
  FYERS_SECRET_KEY   Secret key from the Fyers API portal
  FYERS_REDIRECT_URI Redirect URI registered in the Fyers app

Token caching
-------------
The access_token is persisted back to the project `.env` file under
FYERS_ACCESS_TOKEN (with FYERS_ACCESS_TOKEN_SAVED_AT tracking the issue time)
and reused for up to 23 hours — Fyers tokens are valid until 6:00 AM IST the
following day.

Usage
-----
  from utils.auth_helper import get_fyers_client
  fyers = get_fyers_client()     # returns an authenticated FyersModel instance
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("auth_helper", settings.ops.log_level, settings.ops.log_file)

_ENV_FILE = Path(".env")
_TOKEN_KEY = "FYERS_ACCESS_TOKEN"
_TOKEN_SAVED_AT_KEY = "FYERS_ACCESS_TOKEN_SAVED_AT"

# ---------------------------------------------------------------------------
# .env read/write helpers
# ---------------------------------------------------------------------------

def _upsert_env_var(path: Path, key: str, value: str) -> None:
    """
    Set `key=value` inside the given .env file.

    If the key already exists (commented or not), its line is replaced in-place
    so the surrounding order/comments are preserved. Otherwise the key is
    appended at the end of the file. The file is created if missing.
    """
    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()

    new_line = f"{key}={value}"
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        # Match both "KEY=..." and "# KEY=..." so a commented placeholder gets filled.
        candidate = stripped.lstrip("#").lstrip()
        if candidate.startswith(f"{key}="):
            lines[i] = new_line
            replaced = True
            break

    if not replaced:
        lines.append(new_line)

    path.write_text("\n".join(lines) + "\n")


def _load_cached_token() -> Optional[str]:
    """Return a cached access_token from the environment if one exists."""
    token = os.getenv(_TOKEN_KEY, "").strip()
    if not token:
        return None
    logger.info("Using cached Fyers token")
    return token


def _save_token(access_token: str) -> None:
    """Persist the access_token into the project .env file."""
    now_iso = datetime.now().isoformat(timespec="seconds")
    try:
        _upsert_env_var(_ENV_FILE, _TOKEN_KEY, access_token)
        _upsert_env_var(_ENV_FILE, _TOKEN_SAVED_AT_KEY, now_iso)
    except Exception as exc:
        logger.warning("Could not persist token to %s: %s", _ENV_FILE, exc)
        return

    # Update the current process environment so subsequent reads see the new token
    # without requiring a restart.
    os.environ[_TOKEN_KEY] = access_token
    os.environ[_TOKEN_SAVED_AT_KEY] = now_iso
    settings.broker.access_token = access_token
    settings.broker.access_token_saved_at = now_iso
    logger.info("Fyers access token written to %s", _ENV_FILE)


# ---------------------------------------------------------------------------
# Interactive auth flow
# ---------------------------------------------------------------------------

def _do_auth_flow(app_id: str, secret_key: str, redirect_uri: str) -> str:
    """
    Run the Fyers authorization-code flow interactively.

    1. Generate the auth URL and print it for the user.
    2. User logs in and lands on redirect_uri?auth_code=...
    3. User pastes the full redirect URL (or just the auth_code).
    4. Exchange the auth_code for an access_token via SessionModel.

    Returns the access_token string.
    """
    try:
        from fyers_apiv3 import fyersModel
    except ImportError as exc:
        raise RuntimeError(
            "fyers-apiv3 not installed. Run: pip install fyers-apiv3"
        ) from exc

    session = fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )

    auth_url = session.generate_authcode()
    print("\n" + "=" * 70)
    print("Fyers Authentication")
    print("=" * 70)
    print("Open the following URL in your browser and log in with your")
    print("Fyers credentials:")
    print()
    print(f"  {auth_url}")
    print()
    print("After login you will be redirected to your redirect_uri.")
    print("Copy the FULL redirect URL from the browser address bar")
    print("(or just the auth_code= value) and paste it below.")
    print("=" * 70 + "\n")

    raw_input = input("Paste redirect URL or auth_code: ").strip()

    # Accept either the full redirect URL or just the code
    if "auth_code=" in raw_input:
        auth_code = raw_input.split("auth_code=")[1].split("&")[0].strip()
    else:
        auth_code = raw_input.strip()

    if not auth_code:
        raise ValueError("No auth_code provided — authentication aborted.")

    logger.info("Exchanging auth_code for access_token…")
    session.set_token(auth_code)
    response = session.generate_token()

    if not isinstance(response, dict) or response.get("s") != "ok":
        raise RuntimeError(f"Token exchange failed: {response}")

    access_token = response.get("access_token", "")
    if not access_token:
        raise RuntimeError(f"No access_token in response: {response}")

    logger.info("Fyers authentication successful.")
    return access_token


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_fyers_client(force_new_token: bool = False):
    """
    Return an authenticated Fyers API v3 client (FyersModel instance).

    Loads a cached token from the .env file if valid; otherwise runs the
    interactive OAuth flow and writes the new token back to .env for
    subsequent runs.

    Parameters
    ----------
    force_new_token : bool
        When True, skip the cached token and always run a fresh OAuth flow.

    Returns
    -------
    fyersModel.FyersModel   — ready for history(), quotes(), place_order(), etc.
    """
    try:
        from fyers_apiv3 import fyersModel
    except ImportError as exc:
        raise RuntimeError(
            "fyers-apiv3 not installed. Run: pip install fyers-apiv3"
        ) from exc

    cfg = settings.broker

    if not cfg.app_id:
        raise RuntimeError(
            "FYERS_APP_ID is not set. Copy .env.example → .env and fill in your credentials."
        )
    if not cfg.secret_key:
        raise RuntimeError(
            "FYERS_SECRET_KEY is not set. Copy .env.example → .env and fill in your credentials."
        )

    access_token = None if force_new_token else _load_cached_token()
    if not access_token:
        access_token = _do_auth_flow(cfg.app_id, cfg.secret_key, cfg.redirect_uri)
        _save_token(access_token)

    fyers = fyersModel.FyersModel(
        client_id=cfg.app_id,
        token=access_token,
        log_path="",       # suppress fyers-apiv3 internal log files
        is_async=False,
    )
    return fyers


def refresh_if_needed(fyers_client) -> None:
    """
    Re-authenticate if the token is nearing expiry.
    Call this at the start of each trading day.
    """
    if _load_cached_token() is None:
        logger.info("Token refresh required — re-authenticating")
        get_fyers_client()
