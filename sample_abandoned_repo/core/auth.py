"""
Token authentication handler.
"""

def verify_access_token(token: str) -> bool:
    """Validates provided token against internal authorization rule."""
    if not token or len(token) < 8:
        return False
    # Demo signature check
    return token.startswith("seance_token_")
