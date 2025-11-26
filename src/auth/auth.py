"""
Authentication utilities for JWT token generation and validation.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import warnings

# Suppress bcrypt version warnings (known compatibility issue with newer bcrypt versions)
warnings.filterwarnings("ignore", category=UserWarning, module="passlib")
warnings.filterwarnings("ignore", message=".*bcrypt.*")

# Try to use passlib, but fall back to bcrypt directly if there are compatibility issues
USE_PASSLIB = False
pwd_context = None

try:
    from passlib.context import CryptContext
    # Test if bcrypt is accessible and compatible
    import bcrypt as _bcrypt_test
    # Try to create a context - this will fail if bcrypt version is incompatible
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12,
    )
    # Test that it actually works by trying to hash a test password
    try:
        _test_hash = pwd_context.hash("test")
        USE_PASSLIB = True
        print("✓ Using passlib for password hashing")
    except (AttributeError, Exception) as test_e:
        # If the test fails, especially with __about__ error, skip passlib
        if "__about__" in str(test_e) or "bcrypt version" in str(test_e).lower():
            print(f"Warning: bcrypt version incompatible with passlib, using bcrypt directly")
            USE_PASSLIB = False
            pwd_context = None
        else:
            raise
except (AttributeError, ImportError, Exception) as e:
    error_msg = str(e)
    if "__about__" in error_msg or "bcrypt version" in error_msg.lower():
        print(f"Warning: bcrypt version incompatible with passlib, using bcrypt directly")
    else:
        print(f"Warning: Could not initialize passlib, using bcrypt directly: {e}")
    USE_PASSLIB = False
    pwd_context = None

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
# Token expiration: 3 hours (180 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 180


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    if USE_PASSLIB and pwd_context is not None:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except (AttributeError, Exception) as e:
            # Fall back to bcrypt directly if passlib fails
            error_msg = str(e)
            if "__about__" in error_msg or "bcrypt version" in error_msg.lower():
                print(f"Passlib verify failed due to bcrypt version issue, using bcrypt directly")
            else:
                print(f"Passlib verify failed, using bcrypt directly: {e}")
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    else:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Bcrypt has a 72-byte limit, so we need to validate and handle this
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
        byte_length = len(password_bytes)
        if byte_length > 72:
            char_length = len(password)
            raise ValueError(
                f"Password is too long. Your password is {char_length} characters long, "
                f"but when encoded it is {byte_length} bytes. "
                f"Bcrypt can only handle passwords up to 72 bytes. "
                f"Please use a shorter password or avoid special characters/emojis."
            )
    
    try:
        if USE_PASSLIB and pwd_context is not None:
            # Try passlib first
            try:
                hashed = pwd_context.hash(password)
                return hashed
            except (AttributeError, Exception) as e:
                # If passlib fails due to bcrypt version issues, fall back to bcrypt directly
                error_msg = str(e)
                if "__about__" in error_msg or "bcrypt version" in error_msg.lower():
                    print(f"Passlib bcrypt version issue detected, using bcrypt directly: {error_msg}")
                    # Fall through to use bcrypt directly
                else:
                    raise
        
        # Use bcrypt directly (either as fallback or primary method)
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except ValueError as e:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        # Handle other errors
        error_msg = str(e)
        print(f"Password hashing error: {error_msg}")
        
        if "72 bytes" in error_msg or "truncate" in error_msg.lower():
            raise ValueError(
                "Password is too long for bcrypt. Please use a password that is 72 bytes or less when encoded."
            )
        raise ValueError(f"Error hashing password: {error_msg}")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Debug: Log expiration time
    print(f"DEBUG: Creating token with expiration: {expire} (in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes from now)")
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Debug: Log token expiration info
        if "exp" in payload:
            exp_timestamp = payload["exp"]
            exp_datetime = datetime.utcfromtimestamp(exp_timestamp)  # Use UTC for consistency
            now = datetime.utcnow()
            time_remaining = exp_datetime - now
            print(f"DEBUG: Token valid. Expires at: {exp_datetime} UTC, Time remaining: {time_remaining}")
        return payload
    except JWTError as e:
        error_msg = str(e)
        print(f"DEBUG: JWT decode error: {type(e).__name__}: {error_msg}")
        # Try to decode without verification to see expiration
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            if "exp" in unverified:
                exp_timestamp = unverified["exp"]
                exp_datetime = datetime.utcfromtimestamp(exp_timestamp)  # Use UTC for consistency
                now = datetime.utcnow()
                print(f"DEBUG: Token expiration was: {exp_datetime} UTC, Current time: {now} UTC, Expired: {exp_datetime < now}")
        except:
            pass
        return None
    except Exception as e:
        print(f"DEBUG: Unexpected error decoding token: {type(e).__name__}: {str(e)}")
        return None

