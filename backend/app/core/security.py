import os
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
import bcrypt
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from backend.app.core.config import settings

# Ensure certs directory exists and keys are generated
def ensure_rsa_keys():
    private_path = settings.RSA_PRIVATE_KEY_PATH
    public_path = settings.RSA_PUBLIC_KEY_PATH

    # Check if absolute path is needed (paths are relative to backend)
    # Since we run from backend/, relative paths will resolve nicely
    # Let's ensure directories exist
    os.makedirs(os.path.dirname(private_path), exist_ok=True)
    os.makedirs(os.path.dirname(public_path), exist_ok=True)

    if not os.path.exists(private_path) or not os.path.exists(public_path):
        print("Generating RSA key pair for JWT RS256 signatures...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        pem_public = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        with open(private_path, "wb") as f:
            f.write(pem_private)
        with open(public_path, "wb") as f:
            f.write(pem_public)
        print("RSA key pair generated successfully.")

# Initialize keys
ensure_rsa_keys()

# Load keys
with open(settings.RSA_PRIVATE_KEY_PATH, "r") as f:
    RSA_PRIVATE_KEY = f.read()

with open(settings.RSA_PUBLIC_KEY_PATH, "r") as f:
    RSA_PUBLIC_KEY = f.read()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, RSA_PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, RSA_PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        decoded_payload = jwt.decode(token, RSA_PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
        return decoded_payload
    except jwt.PyJWTError:
        return {}
