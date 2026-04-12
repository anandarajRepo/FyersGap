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
The access_token is persisted to .fyers_token.json and reused for up to
23 hours (Fyers tokens are valid until 6:00 AM IST the following day).

Usage
-----
  from utils.auth_helper import get_fyers_client
  fyers = get_fyers_client()     # returns an authenticated FyersModel instance
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import settings
from utils.logger import get_logger

logger = get_logger("auth_helper", settings.ops.log_level, settings.ops.log_file)

_TOKEN_FILE = Path(".fyers_token.json")
_TOKEN_EXPIRY_HOURS = 23  # Conservative: Fyers tokens valid until 6 AM IST next day


# ---------------------------------------------------------------------------
# Token cache helpers
# ---------------------------------------------------------------------------

def _load_cached_token() -> Optional[str]:
    """Return a cached access_token string if still valid, else None."""
    if not _TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(_TOKEN_FILE.read_text())
        saved_at = datetime.fromisoformat(data["saved_at"])
        if datetime.now() - saved_at < timedelta(hours=_TOKEN_EXPIRY_HOURS):
            logger.info("Using cached Fyers token (saved %s)", saved_at.strftime("%H:%M"))
            return data["access_token"]
        logger.info("Cached Fyers token expired — re-authenticating")
    except Exception as exc:
        logger.warning("Failed to read cached token: %s", exc)
    return None


def _save_token(access_token: str) -> None:
    try:
        _TOKEN_FILE.write_text(json.dumps({
            "access_token": access_token,
            "saved_at": datetime.now().isoformat(),
        }))
        logger.info("Fyers access token cached to %s", _TOKEN_FILE)
    except Exception as exc:
        logger.warning("Could not persist token: %s", exc)


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

def get_fyers_client():
    """
    Return an authenticated Fyers API v3 client (FyersModel instance).

    Loads a cached token if valid; otherwise runs the interactive OAuth flow
    and caches the new token for subsequent runs.

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

    access_token = _load_cached_token()
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
