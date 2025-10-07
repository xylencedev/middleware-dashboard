from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re
import jwt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-production-jwt-secret-key-here-should-be-64-chars-long")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

def extract_jwt_from_request(request: Request) -> str:
    """
    Extract JWT token from Authorization header or cookies
    Priority: Authorization header first, then cookies (for backward compatibility)
    """
    print(f"🔍 Starting JWT extraction...")
    print(f"🔍 Request headers: {dict(request.headers)}")
    
    # Try Authorization header first (preferred method)
    auth_header = request.headers.get('authorization', '')
    print(f"🔍 Authorization header: {auth_header}")
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        print(f"✅ Found JWT token in Authorization header: {token[:30]}...{token[-10:]}")
        return token
    
    # Fallback to cookies for backward compatibility
    cookie_header = request.headers.get('cookie', '')
    print(f"🔍 Cookie header: {cookie_header}")
    
    if cookie_header:
        # Look for auth-token cookie
        token_match = re.search(r'auth-token=([^;]+)', cookie_header)
        if token_match:
            token = token_match.group(1)
            print(f"✅ Found JWT token in cookies: {token[:30]}...{token[-10:]}")
            return token
        else:
            print(f"❌ No auth-token found in cookies")
    
    print(f"❌ No JWT token found in Authorization header or cookies")
    return None
async def verify_jwt_token(request: Request) -> Dict[str, Any]:
    """
    Verify JWT token from cookies or Authorization header
    Compatible with main backend JWT implementation (jose library)
    Raises HTTPException if token is invalid
    """
    print(f"🔍 Starting JWT verification process...")
    print(f"🔍 JWT_SECRET configured: {bool(JWT_SECRET)}")
    print(f"🔍 JWT_SECRET preview: {JWT_SECRET[:10]}...{JWT_SECRET[-10:] if len(JWT_SECRET) > 20 else JWT_SECRET}")
    print(f"🔍 JWT_ALGORITHM: {JWT_ALGORITHM}")
    
    # Extract token from request
    token = extract_jwt_from_request(request)
    
    if not token:
        print(f"❌ JWT extraction failed - no token found")
        raise HTTPException(
            status_code=401, 
            detail="No authentication token found. Please login first."
        )
    
    print(f"🔍 Token extracted successfully, length: {len(token)}")
    print(f"🔍 Token preview: {token[:50]}...{token[-20:]}")
    
    try:
        print(f"🔍 Attempting to decode JWT with PyJWT...")
        
        # Decode the JWT token using same algorithm as main backend
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=[JWT_ALGORITHM]
        )
        
        print(f"✅ JWT decoded successfully!")
        print(f"🔍 JWT payload: {payload}")
        print(f"🔍 Payload keys: {list(payload.keys())}")
        
        # Check if required fields exist (main backend uses 'userId' in JWT)
        user_id = payload.get("userId")
        print(f"🔍 Checking for userId in payload...")
        print(f"🔍 userId value: {user_id}")
        
        if not user_id:
            print(f"❌ Missing userId in JWT payload")
            print(f"❌ Available fields: {list(payload.keys())}")
            raise HTTPException(
                status_code=401, 
                detail="Invalid token: missing userId"
            )
        
        print(f"✅ JWT verification successful for user: {user_id}")
        return payload
        
    except jwt.ExpiredSignatureError as e:
        print(f"❌ JWT expired: {str(e)}")
        raise HTTPException(
            status_code=401, 
            detail="Token has expired. Please login again."
        )
    except jwt.InvalidTokenError as e:
        print(f"❌ JWT invalid token error: {str(e)}")
        print(f"❌ Token that failed: {token[:50]}...{token[-20:]}")
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid token: {str(e)}"
        )
    except jwt.InvalidSignatureError as e:
        print(f"❌ JWT invalid signature: {str(e)}")
        print(f"❌ This usually means JWT_SECRET is wrong")
        print(f"❌ Current JWT_SECRET: {JWT_SECRET[:10]}...{JWT_SECRET[-10:]}")
        raise HTTPException(
            status_code=401, 
            detail="Invalid token signature. JWT_SECRET mismatch."
        )
    except Exception as e:
        print(f"❌ Unexpected JWT verification error: {type(e).__name__}: {str(e)}")
        print(f"❌ Token: {token[:50]}...{token[-20:]}")
        print(f"❌ Secret: {JWT_SECRET[:10]}...{JWT_SECRET[-10:]}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=401, 
            detail=f"Token verification failed: {str(e)}"
        )

def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """
    Create a JWT token with user data (compatible with main backend format)
    """
    try:
        # Create payload exactly like main backend
        payload = {
            "userId": user_data.get("userId") or user_data.get("id"),
            "email": user_data.get("email", ""),
            "username": user_data.get("username", ""),
            "iat": int(datetime.utcnow().timestamp()),
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Token creation failed: {str(e)}"
        )

class QueryBuilder:
    """Build MongoDB aggregation pipelines for complex queries"""
    
    @staticmethod
    def build_user_search_pipeline(
        search_query: str = None,
        date_filter: str = None,
        membership_filter: str = None,
        platform_filter: str = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for user search"""
        pipeline = []
        
        # Match stage for filtering
        match_conditions = {}
        
        if search_query:
            search_regex = {"$regex": re.escape(search_query), "$options": "i"}
            match_conditions["$or"] = [
                {"User Info.user_id": search_regex},
                {"User Info.username": search_regex},
                {"User Info.nama_depan": search_regex},
                {"Data Lengkap Sesi.Basic Information.Username": search_regex},
                {"Data Lengkap Sesi.Basic Information.First Name": search_regex}
            ]
        
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, "%Y-%m-%d")
                date_str = date_obj.strftime("%Y-%m-%d")
                match_conditions["User Info.waktu_ditambahkan"] = {
                    "$regex": f"^{date_str}",
                    "$options": "i"
                }
            except ValueError:
                pass
        
        if membership_filter:
            match_conditions["Membership.tier"] = membership_filter
        
        if platform_filter:
            if platform_filter == "telegram":
                match_conditions["Bot Usage.Telegram.telegram_usage"] = {"$gt": 0}
            elif platform_filter == "tiktok":
                match_conditions["Bot Usage.TikTok.tiktok_usage"] = {"$gt": 0}
            elif platform_filter == "instagram":
                match_conditions["Bot Usage.Instagram.instagram_usage"] = {"$gt": 0}
            elif platform_filter == "doodstream":
                match_conditions["Bot Usage.Doodstream.doodstream_usage"] = {"$gt": 0}
        
        if match_conditions:
            pipeline.append({"$match": match_conditions})
        
        # Sort by registration date (newest first)
        pipeline.append({
            "$sort": {"User Info.waktu_ditambahkan": -1}
        })
        
        # Add pagination
        pipeline.extend([
            {"$skip": skip},
            {"$limit": limit}
        ])
        
        return pipeline
    
    @staticmethod
    def build_analytics_pipeline(date_range: str = "30d") -> List[Dict[str, Any]]:
        """Build aggregation pipeline for analytics"""
        pipeline = []
        
        # Add date filtering if needed
        if date_range != "all":
            days = int(date_range.replace("d", ""))
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            
            pipeline.append({
                "$match": {
                    "User Info.waktu_ditambahkan": {
                        "$regex": f"^(202[4-9]|20[3-9][0-9])-",
                        "$options": "i"
                    }
                }
            })
        
        # Main analytics aggregation
        pipeline.append({
            "$group": {
                "_id": None,
                "total_users": {"$sum": 1},
                "total_downloads": {"$sum": "$Bot Usage.total_downloads"},
                "avg_downloads": {"$avg": "$Bot Usage.total_downloads"},
                "zenith_users": {
                    "$sum": {
                        "$cond": [{"$eq": ["$Membership.tier", "Zenith"]}, 1, 0]
                    }
                },
                "premium_users": {
                    "$sum": {
                        "$cond": [{"$eq": ["$Membership.tier", "Premium"]}, 1, 0]
                    }
                },
                "free_users": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$ne": ["$Membership.tier", "Zenith"]},
                                {"$ne": ["$Membership.tier", "Premium"]}
                            ]}, 1, 0
                        ]
                    }
                },
                "telegram_users": {
                    "$sum": {
                        "$cond": [{"$gt": ["$Bot Usage.Telegram.telegram_usage", 0]}, 1, 0]
                    }
                },
                "tiktok_users": {
                    "$sum": {
                        "$cond": [{"$gt": ["$Bot Usage.TikTok.tiktok_usage", 0]}, 1, 0]
                    }
                },
                "instagram_users": {
                    "$sum": {
                        "$cond": [{"$gt": ["$Bot Usage.Instagram.instagram_usage", 0]}, 1, 0]
                    }
                },
                "doodstream_users": {
                    "$sum": {
                        "$cond": [{"$gt": ["$Bot Usage.Doodstream.doodstream_usage", 0]}, 1, 0]
                    }
                }
            }
        })
        
        return pipeline

class DataProcessor:
    """Process and transform MongoDB data"""
    
    @staticmethod
    def process_user_data(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process user data for frontend consumption"""
        processed_users = []
        
        for user in users:
            processed_user = {
                "_id": str(user.get("_id", "")),
                "user_info": user.get("User Info", {}),
                "bot_usage": user.get("Bot Usage", {}),
                "membership": user.get("Membership", {}),
                "session_info": user.get("Data Lengkap Sesi", {}).get("Basic Information", {}),
                "referral": user.get("Referral", {}),
                "downloader_usage": user.get("DownloaderUsage", {})
            }
            
            # Calculate total size safely
            total_size = user.get("Bot Usage", {}).get("total_size")
            if isinstance(total_size, dict) and "$numberLong" in total_size:
                processed_user["bot_usage"]["total_size"] = int(total_size["$numberLong"])
            elif isinstance(total_size, (int, float)):
                processed_user["bot_usage"]["total_size"] = int(total_size)
            else:
                processed_user["bot_usage"]["total_size"] = 0
            
            processed_users.append(processed_user)
        
        return processed_users
    
    @staticmethod
    def calculate_growth_rate(current: int, previous: int) -> float:
        """Calculate growth rate percentage"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
