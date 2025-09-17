
import json
import os
import time
import uuid
import base64
import hashlib
import secrets
import mimetypes
from typing import Optional, Tuple, List, Dict

import requests
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session
from urllib.parse import urlparse, parse_qs
from django.conf import settings
from requests.auth import HTTPBasicAuth
from PIL import Image, UnidentifiedImageError
from tempfile import NamedTemporaryFile

# Pull config from settings.py 
TOKEN_STORE_PATH = settings.TWITTER_TOKEN_PATH 

#Tweet Length
MAX_TWEET_CHARS = 250


# API endpoints
AUTH_URL = "https://x.com/i/oauth2/authorize" 
TOKEN_URL = "https://api.x.com/2/oauth2/token"
TWEET_URL = "https://api.x.com/2/tweets"
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
MEDIA_STATUS_URL = "https://api.x.com/2/media/upload?command=STATUS&media_id={id}"
MEDIA_INIT_URL = "https://api.x.com/2/media/upload/initialize"
MEDIA_APPEND_URL_TMPL = "https://api.x.com/2/media/upload/{media_id}/append"
MEDIA_FINALIZE_URL_TMPL = "https://api.x.com/2/media/upload/{media_id}/finalize"


# --- add state storage  ---
_STATE_PATH = os.getenv("TW_STATE_PATH", ".twitter_oauth_state.txt")


def _load_tokens() -> Optional[dict]:
    """Return saved token dict or None."""
    try:
        with open(TOKEN_STORE_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None  # optionally log


def _save_tokens(tokens: dict) -> None:
    """Persist token dict to disk."""
    parent = os.path.dirname(TOKEN_STORE_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(TOKEN_STORE_PATH, "w") as f:
        json.dump(tokens, f)


def _save_state(value: str) -> None:
    with open(_STATE_PATH, "w") as f:
        f.write(value)


def _load_state() -> Optional[str]:
    try:
        with open(_STATE_PATH, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _clear_state():
    try:
        os.remove(_STATE_PATH)
    except Exception:
        pass


def safe_text(text: str) -> str:
    if len(text) > MAX_TWEET_CHARS:
        return text[:MAX_TWEET_CHARS - 1] + "…"  # trim + ellipsis
    return text


# --- PKCE helpers ---
def _make_code_verifier_challenge() -> Tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


class TwitterAPI:
    def __init__(self):
        self.client_id = settings.TWITTER_CLIENT_ID
        self.client_secret = settings.TWITTER_CLIENT_SECRET
        self.redirect_uri = settings.TWITTER_REDIRECT_URI  # <- use settings
        self.scopes = settings.TWITTER_SCOPES
        self.token = _load_tokens()
        self.session: Optional[OAuth2Session] = None
        self.code_verifier: Optional[str] = None

        if not self.client_id:
            raise RuntimeError("TW_CLIENT_ID is not set")

        if self.token:
            self._build_session_with_token(self.token)

# ---------- OAuth 2.0 PKCE ----------
    def begin_oauth(self) -> str:
        self.code_verifier, code_challenge = _make_code_verifier_challenge()
        self.session = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scopes,
            )
        state = str(uuid.uuid4())
        self._state = state  # <- keep a copy so the view can store it in session
        auth_url, _ = self.session.authorization_url(
            AUTH_URL,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            state=state,
            )
        return auth_url

    def finish_oauth(self, redirect_response_url: str, expected_state: str | None = None) -> dict:
        # Recreate the OAuth2Session on this fresh instance if needed
        if self.session is None:
            self.session = OAuth2Session(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                scope=self.scopes,
                )

        if not self.code_verifier:
            raise RuntimeError("Missing PKCE code_verifier; restore it from session before calling finish_oauth().")

        # Optional but recommended state check
        returned_state = (parse_qs(urlparse(redirect_response_url).query).get("state") or [""])[0]
        if expected_state is not None and returned_state != expected_state:
            raise RuntimeError("OAuth state mismatch (possible CSRF)")

        # Build fetch_token kwargs
        fetch_kwargs = dict(
            token_url=TOKEN_URL,  # "https://api.twitter.com/2/oauth2/token"
            authorization_response=redirect_response_url,
            code_verifier=self.code_verifier,
            timeout=20,  # nice to have
                )
        if getattr(self, "client_secret", None):
            # Confidential client → send Basic Authorization header
            fetch_kwargs["auth"] = HTTPBasicAuth(self.client_id, self.client_secret)
        else:
            # Public client (pure PKCE) → include client_id in body
            fetch_kwargs["include_client_id"] = True

        try:
            token = self.session.fetch_token(**fetch_kwargs)
        except OAuth2Error as e:
            # Surface helpful details
            raise RuntimeError(f"OAuth2 token exchange failed: {getattr(e, 'error', 'error')} {getattr(e, 'description', '')}".strip()) from e
        except requests.RequestException as e:
            raise RuntimeError(f"Network error during token exchange: {e}") from e

        _save_tokens(token)
        self.token = token
        self._build_session_with_token(token)  # ensures auto-refresh is configured
        self.code_verifier = None
        return token

    def _validate_state(self, redirect_response_url: str, expected_state: Optional[str]):
        # naive parse to extract state; in Django use request.GET['state']
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(redirect_response_url).query)
        returned = (q.get("state") or [""])[0]
        if not expected_state or returned != expected_state:
            raise RuntimeError("OAuth state mismatch (possible CSRF)")

    def _build_session_with_token(self, token: dict):
        """
        Create an OAuth2Session that can auto-refresh 
        using HTTP Basic when confidential.
        """
        auto_refresh_kwargs = {"client_id": self.client_id}
        if getattr(self, "client_secret", None):
            auto_refresh_kwargs["client_secret"] = self.client_secret
            auto_refresh_kwargs["auth"] = HTTPBasicAuth(self.client_id, self.client_secret)

        self.session = OAuth2Session(
            client_id=self.client_id,
            token=token,
            redirect_uri=self.redirect_uri,
            scope=self.scopes,
            auto_refresh_url=TOKEN_URL,
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=_save_tokens,
                )

    def _ensure_session(self):
        if self.session:
            return
        if not self.token:
            raise RuntimeError("Not authenticated. Call begin_oauth() then finish_oauth().")
        self._build_session_with_token(self.token)

    # Small helper to call requests with timeout
    def _post(self, url, **kwargs):
        self._ensure_session()
        kwargs.setdefault("timeout", 15)
        return self.session.post(url, **kwargs)

    def _get(self, url, **kwargs):
        self._ensure_session()
        kwargs.setdefault("timeout", 15)
        return self.session.get(url, **kwargs)


    # ---------- Media handling (v1.1) ----------
    def _reencode_to_jpeg(self, path_or_file) -> str:
        path = path_or_file.path if hasattr(path_or_file, "path") and path_or_file.path else str(path_or_file)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")

        tmp = NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            with Image.open(path) as im:
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
                    to_save = bg
                else:
                    to_save = im.convert("RGB")
                to_save.save(tmp_path, "JPEG", quality=90, optimize=True)
        except UnidentifiedImageError as e:
            try: os.remove(tmp_path)
            except Exception: pass
            raise RuntimeError(f"Could not read image: {e}")

        if os.path.getsize(tmp_path) <= 0:
            try: os.remove(tmp_path)
            except Exception: pass
            raise RuntimeError("Converted JPEG is empty.")
        return tmp_path

    def _check_2xx(resp, label):
        if resp.status_code // 100 != 2:
            raise RuntimeError(f"{label} failed: {resp.status_code} {resp.text}")

    def upload_media(self, image, media_category: str = "tweet_image", timeout_s: int = 30) -> str:
        """
        v2 subpaths flow: initialize (JSON) → append (multipart) → finalize.
        Requires OAuth2 user token with 'media.write'.
        """
        import os, time, mimetypes

        self._ensure_session()

        # Resolve path and normalize to JPEG (handles alpha)
        path = image.path if hasattr(image, "path") and image.path else str(image)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")
        tmp_path = self._reencode_to_jpeg(path)

        try:
            media_type = mimetypes.guess_type(tmp_path)[0] or "image/jpeg"
            total_bytes = os.path.getsize(tmp_path)

            # 1) INIT (JSON)
            init = self.session.post(
                MEDIA_INIT_URL,
                json={"media_type": media_type, "total_bytes": total_bytes, "media_category": media_category},
                timeout=timeout_s,
                )
            if init.status_code // 100 != 2:
                raise RuntimeError(f"INIT failed: {init.status_code} {init.text}")
            media_id = init.json()["data"]["id"]

            # 2) APPEND (multipart)
            with open(tmp_path, "rb") as f:
                append = self.session.post(
                    MEDIA_APPEND_URL_TMPL.format(media_id=media_id),
                    files={"media": (os.path.basename(tmp_path), f, media_type)},
                    data={"segment_index": 0},
                    timeout=timeout_s,
                    )
            if append.status_code // 100 != 2:
                raise RuntimeError(f"APPEND failed: {append.status_code} {append.text}")

            # 3) FINALIZE (no body)
            finalize = self.session.post(
                MEDIA_FINALIZE_URL_TMPL.format(media_id=media_id),
                timeout=timeout_s,
                )
            if finalize.status_code // 100 != 2:
                raise RuntimeError(f"FINALIZE failed: {finalize.status_code} {finalize.text}")

            # Optional: poll STATUS if finalize returns processing_info (mainly video)
            proc = finalize.json().get("data", {}).get("processing_info")
            if proc:
                start = time.time()
                while time.time() - start < timeout_s:
                    st = self.session.get(
                        "https://api.x.com/2/media/upload",
                        params={"command": "STATUS", "media_id": media_id},
                        timeout=10,
                        )
                    if st.status_code // 100 != 2:
                        break
                    proc = st.json().get("data", {}).get("processing_info")
                    if not proc or proc.get("state") in ("succeeded", "failed"):
                        break
                    time.sleep(min(2, proc.get("check_after_secs", 2)))

            return str(media_id)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # ---------- Tweet creation ----------
    def post_tweet(self, text: str, media_ids: Optional[List[str]] = None,
                   reply_to_id: Optional[str] = None) -> dict:
        self._ensure_session()
        text = safe_text(text)
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

        resp = self._post(TWEET_URL, json=payload)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        print("DEBUG /2/tweets status:", resp.status_code, json.dumps(body, indent=2))

        if resp.status_code not in (200, 201):
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}
            raise RuntimeError(f"Tweet failed: HTTP {resp.status_code} {json.dumps(body, indent=2)}")
        return resp.json()
