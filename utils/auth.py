import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "default_secret_key")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify JWT token and return user data
    Raises HTTPException if token is invalid
    """
    try:
        # Decode the JWT token
        payload = jwt.decode(
            credentials.credentials, 
            JWT_SECRET, 
            algorithms=[JWT_ALGORITHM]
        )
        
        # Check if required fields exist
        if not payload.get("user_id"):
            raise HTTPException(
                status_code=401, 
                detail="Invalid token: missing user_id"
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, 
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, 
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Token verification failed: {str(e)}"
        )

def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """
    Create a JWT token with user data
    """
    try:
        payload = {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email", ""),
            # Add expiration if needed
            # "exp": datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Token creation failed: {str(e)}"
        )
