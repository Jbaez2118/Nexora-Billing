import os, uuid
import jwt
from jwt import PyJWKClient
from fastapi import Depends, Header, HTTPException

_jwks = PyJWKClient(os.environ["KEYCLOAK_JWKS_URL"], cache_keys=True, lifespan=3600)
_issuers = [i.strip() for i in os.environ["KEYCLOAK_ISSUERS"].split(",")]
CLIENT_ID = "nexora-app"

def current_claims(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "token requerido")
    token = authorization[7:]
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"],
                            options={"verify_aud": False, "require": ["exp", "iss"]})
    except Exception:
        raise HTTPException(401, "token inválido")
    if claims.get("iss") not in _issuers or claims.get("azp") != CLIENT_ID:
        raise HTTPException(401, "emisor o cliente no permitido")
    return claims

def current_tenant(claims: dict = Depends(current_claims)) -> uuid.UUID:
    try:
        return uuid.UUID(claims["tenant_id"])
    except (KeyError, ValueError):
        raise HTTPException(403, "usuario sin tenant")
