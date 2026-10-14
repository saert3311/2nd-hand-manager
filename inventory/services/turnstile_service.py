import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

CLOUDFLARE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Official Cloudflare dummy testing secret keys
DUMMY_SECRET_ALWAYS_PASS = "1x0000000000000000000000000000000AA"
DUMMY_SECRET_ALWAYS_FAIL = "2x0000000000000000000000000000000AB"


def verify_turnstile_token(token: Optional[str], remote_ip: Optional[str] = None) -> bool:
    """
    Verifies a Cloudflare Turnstile challenge token against Cloudflare's siteverify API.

    Returns:
        bool: True if the token is valid, False otherwise.
              Enforces a strict fail-closed policy (returns False on timeouts,
              network errors, or missing secrets).
    """
    if not token or not token.strip():
        logger.warning("Turnstile verification rejected: Missing or empty token.")
        return False

    secret_key = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret_key:
        logger.error("Turnstile verification failed: TURNSTILE_SECRET_KEY is not configured.")
        return False

    # Check Cloudflare official dummy testing keys to bypass network calls in tests/dev
    if secret_key == DUMMY_SECRET_ALWAYS_PASS:
        logger.info("Turnstile verification passed via Cloudflare dummy pass key.")
        return True
    if secret_key == DUMMY_SECRET_ALWAYS_FAIL:
        logger.warning("Turnstile verification rejected via Cloudflare dummy fail key.")
        return False

    payload = {
        "secret": secret_key,
        "response": token.strip(),
    }
    if remote_ip:
        payload["remoteip"] = remote_ip.strip()

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        CLOUDFLARE_SITEVERIFY_URL,
        data=data,
        headers={
            "User-Agent": "2ndHand-Staging-Turnstile/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    timeout = float(getattr(settings, "TURNSTILE_TIMEOUT", 5.0))

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                logger.error("Cloudflare siteverify returned HTTP status %s", response.status)
                return False

            raw_body = response.read().decode("utf-8")
            result = json.loads(raw_body)
            success = bool(result.get("success", False))

            if not success:
                logger.warning(
                    "Cloudflare Turnstile token validation failed: error_codes=%s",
                    result.get("error-codes", []),
                )
            return success

    except TimeoutError as exc:
        logger.error("Cloudflare siteverify timed out after %.1fs: %s", timeout, exc)
        return False
    except urllib.error.HTTPError as exc:
        logger.error("Cloudflare siteverify HTTP error %s: %s", exc.code, exc.reason)
        return False
    except urllib.error.URLError as exc:
        logger.error("Cloudflare siteverify connection error: %s", exc.reason)
        return False
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode Cloudflare siteverify JSON response: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during Cloudflare siteverify: %s", exc)
        return False
