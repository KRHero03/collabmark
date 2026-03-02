"""Google OAuth configuration and client for login flow."""

from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def get_google_oauth():
    """Return the registered Google OAuth client for authorize/redirect flows."""
    return oauth.google
