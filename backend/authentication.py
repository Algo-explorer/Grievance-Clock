"""Verify Clerk session JWTs in the API, independently of frontend guards."""
import os
from functools import lru_cache
from urllib.parse import urlparse
import jwt
from fastapi import HTTPException, Request

def mode():
    value=os.getenv('AUTH_MODE','clerk')
    if value not in ('clerk','local'): raise RuntimeError('AUTH_MODE must be clerk or local')
    if value=='local' and os.getenv('APP_ENV')=='production':
        raise RuntimeError('Anonymous local sessions are disabled in production')
    return value

def issuer():
    value=os.getenv('CLERK_ISSUER_URL','').rstrip('/')
    parsed=urlparse(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise HTTPException(503,'Account sign-in has not been configured.')
    return value

@lru_cache(maxsize=4)
def key_client(url):
    return jwt.PyJWKClient(url+'/.well-known/jwks.json',cache_jwk_set=True,lifespan=300,timeout=5)

def clerk_owner(request: Request):
    url=issuer()
    header=request.headers.get('authorization','')
    if header:
        if not header.startswith('Bearer '): raise HTTPException(401,'Please sign in again.')
        token=header[7:]
    else: token=request.cookies.get('__session')
    if not token or len(token)>16384: raise HTTPException(401,'Sign in to access your complaints.')
    try:
        key=key_client(url).get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=['RS256'],issuer=url,
            options={'require':['exp','iat','nbf','iss','sub','sid','azp'],'verify_aud':False},leeway=5)
        allowed={v.strip().rstrip('/') for v in os.getenv('ALLOWED_ORIGINS','http://127.0.0.1:3000,http://localhost:3000').split(',') if v.strip()}
        if claims['azp'] not in allowed or not isinstance(claims['sub'],str) or not claims['sub'].startswith('user_'):
            raise jwt.InvalidTokenError('Invalid subject or authorized party')
        # Clerk's pending sessions have not completed required account setup.
        if claims.get('sts')=='pending': raise jwt.InvalidTokenError('Pending session')
        if not isinstance(claims['sid'],str) or not claims['sid']:
            raise jwt.InvalidTokenError('Invalid session')
        return claims['sub']
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503,'Sign-in verification is temporarily unavailable. Please try again.') from None
    except (jwt.PyJWTError,ValueError,TypeError):
        raise HTTPException(401,'Your session is invalid or expired. Please sign in again.') from None
