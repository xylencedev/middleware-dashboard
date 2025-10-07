from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any
import os
from dotenv import load_dotenv
from datetime import datetime

# Import controllers
from controllers.HyperBotController import HyperBotController
from controllers.HyperBotAnalyticsController import HyperBotAnalyticsController

# Import routes
from routes.apiv1_routes import router as apiv1_router

# Load environment variables
load_dotenv()

app = FastAPI(
    title="XyDevs Dashboard MongoDB Backend",
    description="Direct MongoDB API for user data and analytics",
    version="2.0.0"
)

# CORS configuration - Allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "https://dashboard.xydevs.com",  # Production frontend
        "https://*.xydevs.com"  # All xydevs subdomains
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# MongoDB configuration - Use remote database
DB_URL = os.getenv("DB_URL")
DB_NAME = os.getenv("DB_NAME", "UsersDatabase")

# Global variables
client = None
database = None
controllers = {}

async def get_controllers():
    """Get controllers instance"""
    return controllers

# Database connection events
@app.on_event("startup")
async def startup_db_client():
    global client, database, controllers
    
    # Connect to remote MongoDB
    if not DB_URL:
        raise ValueError("DB_URL environment variable is required for remote database connection")
    
    client = AsyncIOMotorClient(DB_URL)
    database = client[DB_NAME]
    
    # Initialize controllers
    controllers["hyperbot"] = HyperBotController(database)
    controllers["hyperbot_analytics"] = HyperBotAnalyticsController(database)
    
    # Test remote connection
    try:
        await client.admin.command('ping')
        print(f"✅ Connected to remote MongoDB: {DB_NAME}")
        print(f"🌐 Database URL: {DB_URL[:50]}...")
    except Exception as e:
        print(f"❌ Failed to connect to remote MongoDB: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_db_client():
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed")

# Include API v1 routes
app.include_router(apiv1_router, prefix="")

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "XyDevs Dashboard MongoDB Backend", 
        "status": "running",
        "version": "2.0.0",
        "environment": "remote_database",
        "jwt_secret_configured": bool(os.getenv("JWT_SECRET") and os.getenv("JWT_SECRET") != "default_secret_key"),
        "endpoints": [
            "/apiv1/hyperbot/users",
            "/apiv1/hyperbot/users/search", 
            "/apiv1/hyperbot/analytics",
            "/apiv1/hyperbot/stats",
            "/apiv1/hyperbot/analytics/overview",
            "/apiv1/hyperbot/analytics/users",
            "/apiv1/hyperbot/analytics/commands",
            "/apiv1/hyperbot/analytics/urls",
            "/apiv1/hyperbot/analytics/summary",
            "/apiv1/hyperbot/analytics/debug",
            "/apiv1/hyperbot/analytics/create-sample",
            "/debug/auth",
            "/health"
        ]
    }

@app.get("/debug/auth")
async def debug_auth(request: Request):
    """Debug endpoint to check authentication"""
    from utils import extract_jwt_from_request
    
    token = extract_jwt_from_request(request)
    
    return {
        "cookies": dict(request.cookies) if hasattr(request, 'cookies') else "No cookies",
        "headers": dict(request.headers),
        "token_found": bool(token),
        "token_preview": f"{token[:20]}..." if token else None,
        "jwt_secret_configured": bool(os.getenv("JWT_SECRET") and os.getenv("JWT_SECRET") != "8f3a1c2e7b4d5f6a9c0e2b1d3f7a6e4c")
    }

@app.get("/health")
async def health_check():
    try:
        if client:
            await client.admin.command('ping')
        return {
            "status": "healthy", 
            "database": "connected",
            "database_type": "remote",
            "timestamp": datetime.utcnow().isoformat(),
            "database_name": DB_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Remote database connection failed: {str(e)}")

# Debug endpoint for JWT testing
@app.get("/debug/jwt")
async def debug_jwt_get(request: Request):
    """Debug endpoint to check JWT token reception (GET version for easier testing)"""
    headers = dict(request.headers)
    cookies = request.cookies
    
    # Try to extract token like main backend does
    from utils import extract_jwt_from_request
    token = extract_jwt_from_request(request)
    
    # Try to decode if token exists
    jwt_payload = None
    jwt_error = None
    if token:
        try:
            import jwt as pyjwt
            jwt_payload = pyjwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        except Exception as e:
            jwt_error = str(e)
    
    return {
        "cookies": cookies,
        "extracted_token": token[:50] + "..." if token else None,
        "jwt_secret_configured": bool(os.getenv("JWT_SECRET")),
        "jwt_secret_preview": os.getenv("JWT_SECRET", "NOT_SET")[:10] + "..." if os.getenv("JWT_SECRET") else "NOT_SET",
        "jwt_payload": jwt_payload,
        "jwt_error": jwt_error,
        "headers_cookie": headers.get('cookie', 'No cookie header')
    }

@app.post("/debug/jwt/test")
async def test_jwt_verification(request: Request):
    """Test JWT verification directly"""
    try:
        from utils import verify_jwt_token
        user = await verify_jwt_token(request)
        return {
            "success": True,
            "message": "JWT verification successful",
            "user": user
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

@app.post("/debug/jwt")
async def debug_jwt(request: Request):
    """Debug endpoint to check JWT token reception"""
    headers = dict(request.headers)
    cookies = request.cookies
    
    # Try to extract token like main backend does
    from utils import extract_jwt_from_request
    token = extract_jwt_from_request(request)
    
    # Try to decode if token exists
    jwt_payload = None
    jwt_error = None
    if token:
        try:
            import jwt as pyjwt
            jwt_payload = pyjwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        except Exception as e:
            jwt_error = str(e)
    
    return {
        "cookies": cookies,
        "extracted_token": token[:50] + "..." if token else None,
        "jwt_secret_configured": bool(os.getenv("JWT_SECRET")),
        "jwt_secret_preview": os.getenv("JWT_SECRET", "NOT_SET")[:10] + "..." if os.getenv("JWT_SECRET") else "NOT_SET",
        "jwt_payload": jwt_payload,
        "jwt_error": jwt_error,
        "headers_cookie": headers.get('cookie', 'No cookie header')
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host=os.getenv("HOST", "0.0.0.0"), 
        port=int(os.getenv("PORT", 8000)), 
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )
