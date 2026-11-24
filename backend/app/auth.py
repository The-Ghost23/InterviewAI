"""Validate access tokens with the configured Supabase Auth service."""
from uuid import UUID
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import settings

bearer = HTTPBearer(auto_error=False)

async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    url = settings.supabase_url.rstrip('/')
    if not url.startswith('https://') or not settings.supabase_publishable_key:
        raise HTTPException(503, "Authentication is not configured. Set the backend Supabase URL and publishable key.")
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(url + '/auth/v1/user', headers={
                'apikey': settings.supabase_publishable_key,
                'Authorization': 'Bearer ' + credentials.credentials,
            })
        if response.status_code in (401, 403):
            raise HTTPException(401, "Your session is invalid or expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
        if response.status_code != 200:
            raise HTTPException(503, "Authentication service is unavailable. Please retry.")
        return UUID(response.json()['id'])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Authentication service is unavailable. Please retry.") from None
