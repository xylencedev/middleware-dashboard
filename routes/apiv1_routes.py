from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any
import os
from controllers.HyperBotController import HyperBotController, UserSearchRequest, UsersRequest, AnalyticsRequest
from controllers.HyperBotAnalyticsController import (
    HyperBotAnalyticsController, 
    AnalyticsTimeframeRequest, 
    AnalyticsStatsRequest, 
    AnalyticsUsersRequest
)
from utils import verify_jwt_token

router = APIRouter(prefix="/apiv1", tags=["API v1"])

# Dependency to get HyperBot controller
async def get_hyperbot_controller() -> HyperBotController:
    """Dependency to get HyperBot controller instance"""
    from main import get_controllers
    controllers = await get_controllers()
    controller = controllers.get("hyperbot")
    if not controller:
        raise HTTPException(status_code=500, detail="HyperBot controller not initialized")
    return controller

# Dependency to get HyperBot Analytics controller
async def get_hyperbot_analytics_controller() -> HyperBotAnalyticsController:
    """Dependency to get HyperBot Analytics controller instance"""
    from main import get_controllers
    controllers = await get_controllers()
    controller = controllers.get("hyperbot_analytics")
    if not controller:
        raise HTTPException(status_code=500, detail="HyperBot Analytics controller not initialized")
    return controller

# JWT authentication dependency
async def get_current_user(request: Request):
    """Get current user from JWT token"""
    print(f"🔍 get_current_user called for endpoint")
    print(f"🔍 Request URL: {request.url}")
    print(f"🔍 Request method: {request.method}")
    try:
        user = await verify_jwt_token(request)
        print(f"✅ get_current_user successful: {user.get('userId')}")
        return user
    except Exception as e:
        print(f"❌ get_current_user failed: {str(e)}")
        raise

# HyperBot Routes with JWT Authentication
@router.post("/hyperbot/users")
async def get_users_data(
    user_request: UsersRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotController = Depends(get_hyperbot_controller)
):
    """Get users data with JWT authentication - Direct MongoDB access"""
    print(f"🎯 /hyperbot/users endpoint called")
    print(f"🎯 Authenticated user: {current_user.get('userId')} ({current_user.get('email')})")
    print(f"🎯 Request payload: {user_request}")
    
    try:
        result = await controller.get_users_data(user_request)
        print(f"✅ Successfully returned {len(result.get('users', []))} users")
        return result
    except Exception as e:
        print(f"❌ Controller error: {str(e)}")
        raise

@router.post("/hyperbot/users/search")
async def search_users_data(
    user_request: UserSearchRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotController = Depends(get_hyperbot_controller)
):
    """Search users data with JWT authentication - Direct MongoDB access"""
    return await controller.search_users_data(user_request)

@router.post("/hyperbot/analytics")
async def get_analytics_data(
    analytics_request: AnalyticsRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotController = Depends(get_hyperbot_controller)
):
    """Get analytics data with JWT authentication - Direct MongoDB access"""
    return await controller.get_analytics_data(analytics_request)

@router.get("/hyperbot/stats")
async def get_quick_stats(
    current_user: dict = Depends(get_current_user),
    controller: HyperBotController = Depends(get_hyperbot_controller)
):
    """Get quick stats with JWT authentication - Direct MongoDB access"""
    return await controller.get_quick_stats()

# New Analytics Routes
@router.post("/hyperbot/analytics/overview")
async def get_analytics_overview(
    request: AnalyticsTimeframeRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Get analytics overview with timeframe filtering"""
    return await controller.get_analytics_overview(request)

@router.post("/hyperbot/analytics/users")
async def get_daily_active_users(
    request: AnalyticsUsersRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Get daily active users statistics"""
    return await controller.get_daily_active_users(request)

@router.post("/hyperbot/analytics/commands")
async def get_command_stats(
    request: AnalyticsStatsRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Get command statistics with trends"""
    return await controller.get_command_stats(request)

@router.post("/hyperbot/analytics/urls")
async def get_url_stats(
    request: AnalyticsStatsRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Get URL statistics with trends"""
    return await controller.get_url_stats(request)

@router.post("/hyperbot/analytics/summary")
async def get_analytics_summary(
    request: AnalyticsTimeframeRequest,
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Get complete analytics summary"""
    return await controller.get_analytics_summary(request)

@router.get("/hyperbot/analytics/debug")
async def debug_analytics_database(
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Debug endpoint to check database structure"""
    return await controller.debug_database_structure()

@router.post("/hyperbot/analytics/create-sample")
async def create_sample_analytics_data(
    current_user: dict = Depends(get_current_user),
    controller: HyperBotAnalyticsController = Depends(get_hyperbot_analytics_controller)
):
    """Create sample analytics data for testing"""
    return await controller.create_sample_analytics_data()
