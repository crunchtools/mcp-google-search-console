"""OAuth2 browser-based authentication flow.

Handles consent URL generation, authorization code exchange,
and file-based credential storage. Uses httpx directly —
no google-auth library dependency.
"""

import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters"
CREDENTIALS_FILENAME = "credentials.json"
STATE_TTL_SECONDS = 600

_pending_states: dict[str, float] = {}


def build_consent_url(client_id: str, redirect_uri: str) -> str:
    """Build the Google OAuth consent URL."""
    state = secrets.token_hex(16)
    _pending_states[state] = time.time()
    _prune_expired_states()

    params = (
        f"client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={GSC_SCOPE}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )
    return f"{GOOGLE_AUTH_ENDPOINT}?{params}"


def validate_state(state: str) -> bool:
    """Validate and consume a CSRF state token."""
    _prune_expired_states()
    created = _pending_states.pop(state, None)
    if created is None:
        return False
    return (time.time() - created) < STATE_TTL_SECONDS


def _prune_expired_states() -> None:
    now = time.time()
    expired = [s for s, t in _pending_states.items() if (now - t) >= STATE_TTL_SECONDS]
    for s in expired:
        del _pending_states[s]


async def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

    if not response.is_success:
        raise RuntimeError(f"Token exchange failed ({response.status_code}): {response.text[:200]}")

    data = response.json()
    expiry = datetime.now(timezone.utc).timestamp() + data.get("expires_in", 3600)
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_uri": GOOGLE_TOKEN_ENDPOINT,
        "scope": GSC_SCOPE,
        "expiry": datetime.fromtimestamp(expiry, tz=timezone.utc).isoformat(),
    }


def load_credentials(credentials_dir: str) -> dict[str, Any] | None:
    """Load credentials from file. Returns None if file is missing or corrupt."""
    path = Path(credentials_dir) / CREDENTIALS_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load credentials: %s", e)
        return None

    if not isinstance(data, dict) or "refresh_token" not in data:
        logger.warning("Credential file missing refresh_token, ignoring")
        return None
    return data


def save_credentials(credentials_dir: str, data: dict[str, Any]) -> None:
    """Atomically save credentials with 0o600 permissions."""
    dir_path = Path(credentials_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    target = dir_path / CREDENTIALS_FILENAME
    tmp = dir_path / f"{CREDENTIALS_FILENAME}.tmp"
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    logger.info("Credentials saved to %s", target)
