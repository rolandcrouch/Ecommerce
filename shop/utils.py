import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from .models import ResetToken


def _hash_token(raw: str) -> str:
    # Store as hex sha256; raw token never persisted
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_reset_token(user) -> str:
    """
    Create a single-use reset token for a user.
    Returns the RAW token (caller sends it to the user).
    Old tokens for this user are deleted to reduce surface.
    """
    # Clean up existing (optional, but simplest for UX)
    ResetToken.objects.filter(user=user, used_at__isnull=True).delete()

    raw = secrets.token_urlsafe(32)  # ~256 bits before encoding; robust
    token_hash = _hash_token(raw)
    ttl = getattr(settings, "PASSWORD_RESET_TOKEN_TTL_MINUTES", 15)
    expires_at = timezone.now() + timedelta(minutes=ttl)

    ResetToken.objects.create(
        user=user,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    return raw


def build_reset_url(request, raw_token: str) -> str:
    """
    Build absolute URL with the RAW token in path.
    """
    path = reverse("reset_user_password", args=[raw_token])
    # Respect proxies / SECURE_PROXY_SSL_HEADER as configured
    return request.build_absolute_uri(path)


def validate_and_consume_token(raw_token: str):
    """
    Return (user, token_obj) if valid and not expired/used; marks as used.
    Return (None, None) if invalid.
    """
    token_hash = _hash_token(raw_token)
    rt = (
        ResetToken.objects.select_related("user")
        .filter(token_hash=token_hash, used_at__isnull=True)
        .first()
    )
    if not rt or rt.is_expired():
        # Clean up if expired to limit DB growth
        if rt and rt.is_expired():
            rt.delete()
        return None, None

    rt.used_at = timezone.now()
    rt.save(update_fields=["used_at"])
    return rt.user, rt


def lookup_reset_token(raw_token: str):
    """
    Validate existence/expiry/unused WITHOUT consuming it.
    Returns (user, rt) if valid; (None, None) otherwise.
    """
    token_hash = _hash_token(raw_token)
    rt = (
        ResetToken.objects.select_related("user")
        .filter(token_hash=token_hash, used_at__isnull=True)
        .first()
    )
    if not rt:
        return None, None

    # Support either field name if you're mid-migration
    expires_at = getattr(rt, "expires_at", None) or getattr(rt, "expiry_date", None)
    if not expires_at or timezone.now() >= expires_at:
        # Optional tidy-up if expired
        if expires_at and timezone.now() >= expires_at:
            rt.delete()
        return None, None

    return rt.user, rt


def consume_reset_token(rt):
    """Mark the token as used (single-use)."""
    rt.used_at = timezone.now()
    rt.save(update_fields=["used_at"])