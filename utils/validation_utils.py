def validate_required_fields(data, fields):
    """Raise ValueError if any required key is missing or empty in data dict."""
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def normalize_email(email):
    """Lowercase and strip an email address."""
    return email.strip().lower() if email else ''


def get_client_ip(request):
    """Extract client IP from X-Forwarded-For header or REMOTE_ADDR fallback."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr
