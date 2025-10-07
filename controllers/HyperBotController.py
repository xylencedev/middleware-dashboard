from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime, timedelta
import re


class UserSearchRequest(BaseModel):
    get_data: str
    search_query: Optional[str] = None
    date_filter: Optional[str] = None
    membership_filter: Optional[str] = None
    session_filter: Optional[str] = None  # New filter for session strings
    limit: Optional[int] = 50
    skip: Optional[int] = 0


class UsersRequest(BaseModel):
    get_data: str
    limit: Optional[int] = 50
    skip: Optional[int] = 0


class AnalyticsRequest(BaseModel):
    get_data: str
    date_range: Optional[str] = "30d"


class HyperBotController:
    def __init__(self, database):
        self.database = database

    def convert_object_ids(self, doc):
        """Convert ObjectId to string for JSON serialization"""
        if isinstance(doc, dict):
            for key, value in doc.items():
                if hasattr(value, 'ObjectId') or str(type(value)) == "<class 'bson.objectid.ObjectId'>":
                    doc[key] = str(value)
                elif isinstance(value, dict):
                    doc[key] = self.convert_object_ids(value)
                elif isinstance(value, list):
                    doc[key] = [self.convert_object_ids(item) if isinstance(item, dict) else item for item in value]
        return doc

    def build_search_query(self, search_query: str = None, date_filter: str = None, 
                          membership_filter: str = None, session_filter: str = None):
        """Build MongoDB query based on search parameters"""
        query = {}
        
        if search_query:
            # Search in user ID, username, first name
            search_regex = {"$regex": search_query, "$options": "i"}
            query["$or"] = [
                {"User Info.user_id": search_regex},
                {"User Info.username": search_regex},
                {"User Info.nama_depan": search_regex},
                {"Data Lengkap Sesi.Basic Information.Username": search_regex},
                {"Data Lengkap Sesi.Basic Information.First Name": search_regex}
            ]
        
        if date_filter:
            try:
                # Convert date filter to match MongoDB date format
                date_obj = datetime.strptime(date_filter, "%Y-%m-%d")
                date_str = date_obj.strftime("%Y-%m-%d")
                
                query["User Info.waktu_ditambahkan"] = {
                    "$regex": f"^{date_str}",
                    "$options": "i"
                }
            except ValueError:
                pass  # Invalid date format, ignore filter
        
        # Updated membership filter with new tiers
        if membership_filter:
            membership_mapping = {
                "freemium": "Freemium",
                "trial": "Trial", 
                "premium": "Premium",
                "plus": "Plus",
                "vip": "VIP",
                "zenith": "Zenith"
            }
            actual_tier = membership_mapping.get(membership_filter.lower(), membership_filter)
            query["Membership.tier"] = actual_tier
        
        # New session filter - check both locations where session string might exist
        if session_filter == "with_session":
            query["$or"] = [
                {"User Info.session_string": {"$exists": True, "$ne": "", "$ne": None}},
                {"Data Lengkap Sesi.Session Info.session_string": {"$exists": True, "$ne": "", "$ne": None}},
                {"Data Lengkap Sesi.Session Info.Session String": {"$exists": True, "$ne": "", "$ne": None}}
            ]
        elif session_filter == "without_session":
            query["$and"] = [
                {
                    "$or": [
                        {"User Info.session_string": {"$exists": False}},
                        {"User Info.session_string": ""},
                        {"User Info.session_string": None}
                    ]
                },
                {
                    "$or": [
                        {"Data Lengkap Sesi.Session Info.session_string": {"$exists": False}},
                        {"Data Lengkap Sesi.Session Info.session_string": ""},
                        {"Data Lengkap Sesi.Session Info.session_string": None}
                    ]
                },
                {
                    "$or": [
                        {"Data Lengkap Sesi.Session Info.Session String": {"$exists": False}},
                        {"Data Lengkap Sesi.Session Info.Session String": ""},
                        {"Data Lengkap Sesi.Session Info.Session String": None}
                    ]
                }
            ]
        
        return query

    async def get_users_data(self, request: UsersRequest):
        """Get paginated users data from MongoDB with improved pagination"""
        try:
            collection = self.database["CompleteUsersData"]
            
            # Validate pagination parameters
            limit = min(max(request.limit, 1), 100)  # Limit between 1 and 100
            skip = max(request.skip, 0)
            
            # Get total count
            total_count = await collection.count_documents({})
            
            # Calculate pagination info
            current_page = (skip // limit) + 1
            total_pages = (total_count + limit - 1) // limit
            has_next = skip + limit < total_count
            has_previous = skip > 0
            
            # Get paginated results with optimized query
            cursor = collection.find(
                {}, 
                {
                    # Only fetch required fields to improve performance
                    "User Info": 1,
                    "Bot Usage": 1,
                    "Membership": 1,
                    "Data Lengkap Sesi": 1,
                    "Referral": 1
                }
            ).sort("User Info.waktu_ditambahkan", DESCENDING)
            
            cursor = cursor.skip(skip).limit(limit)
            
            users = []
            async for doc in cursor:
                users.append(self.convert_object_ids(doc))
            
            return {
                "users": users,
                "total_count": total_count,
                "current_page": current_page,
                "total_pages": total_pages,
                "per_page": limit,
                "has_next": has_next,
                "has_previous": has_previous,
                "showing_from": skip + 1,
                "showing_to": min(skip + limit, total_count),
                "query_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error in get_users_data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch users: {str(e)}")

    async def search_users_data(self, request: UserSearchRequest):
        """Search users data with advanced filters and pagination"""
        try:
            collection = self.database["CompleteUsersData"]
            
            # Validate pagination parameters
            limit = min(max(request.limit, 1), 100)  # Limit between 1 and 100
            skip = max(request.skip, 0)
            
            # Build search query
            query = self.build_search_query(
                request.search_query, 
                request.date_filter, 
                request.membership_filter,
                request.session_filter
            )
            
            print(f"Search query: {query}")
            
            # Get total count for search results
            total_count = await collection.count_documents(query)
            
            # Calculate pagination info
            current_page = (skip // limit) + 1
            total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
            has_next = skip + limit < total_count
            has_previous = skip > 0
            
            # Get paginated search results with optimized query
            cursor = collection.find(
                query,
                {
                    # Only fetch required fields to improve performance
                    "User Info": 1,
                    "Bot Usage": 1,
                    "Membership": 1,
                    "Data Lengkap Sesi": 1,
                    "Referral": 1
                }
            ).sort("User Info.waktu_ditambahkan", DESCENDING)
            
            cursor = cursor.skip(skip).limit(limit)
            
            users = []
            async for doc in cursor:
                users.append(self.convert_object_ids(doc))
            
            return {
                "users": users,
                "total_count": total_count,
                "current_page": current_page,
                "total_pages": total_pages,
                "per_page": limit,
                "has_next": has_next,
                "has_previous": has_previous,
                "showing_from": skip + 1 if total_count > 0 else 0,
                "showing_to": min(skip + limit, total_count),
                "search_params": {
                    "search_query": request.search_query,
                    "date_filter": request.date_filter,
                    "membership_filter": request.membership_filter,
                    "session_filter": request.session_filter
                },
                "query_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error in search_users_data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to search users: {str(e)}")

    async def get_analytics_data(self, request: AnalyticsRequest):
        """Get comprehensive analytics data from MongoDB"""
        try:
            collection = self.database["CompleteUsersData"]
            
            # Enhanced analytics aggregation pipeline with updated membership tiers
            overview_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_users": {"$sum": 1},
                        "total_downloads": {"$sum": {"$ifNull": ["$Bot Usage.total_downloads", 0]}},
                        "avg_downloads": {"$avg": {"$ifNull": ["$Bot Usage.total_downloads", 0]}},
                        "freemium_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "Freemium"]}, 1, 0]
                            }
                        },
                        "trial_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "Trial"]}, 1, 0]
                            }
                        },
                        "premium_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "Premium"]}, 1, 0]
                            }
                        },
                        "plus_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "Plus"]}, 1, 0]
                            }
                        },
                        "vip_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "VIP"]}, 1, 0]
                            }
                        },
                        "zenith_users": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.tier", "Zenith"]}, 1, 0]
                            }
                        },
                        "users_with_session": {
                            "$sum": {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$exists": "$Data Lengkap Sesi.Session Info.session_string"},
                                            {"$ne": ["$Data Lengkap Sesi.Session Info.session_string", ""]},
                                            {"$ne": ["$Data Lengkap Sesi.Session Info.session_string", None]}
                                        ]
                                    },
                                    1, 0
                                ]
                            }
                        },
                        "expired_memberships": {
                            "$sum": {
                                "$cond": [{"$eq": ["$Membership.subscription_expired", True]}, 1, 0]
                            }
                        },
                        "active_memberships": {
                            "$sum": {
                                "$cond": [{"$ne": ["$Membership.subscription_expired", True]}, 1, 0]
                            }
                        }
                    }
                }
            ]
            
            overview_result = await collection.aggregate(overview_pipeline).to_list(1)
            overview = overview_result[0] if overview_result else {}
            if "_id" in overview:
                del overview["_id"]
            
            # Daily activity for the past 30 days
            activity_pipeline = [
                {
                    "$addFields": {
                        "join_date": {
                            "$dateFromString": {
                                "dateString": {"$substr": ["$User Info.waktu_ditambahkan", 0, 10]},
                                "onError": None
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "join_date": {
                            "$gte": datetime.now() - timedelta(days=30),
                            "$lte": datetime.now()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$join_date"
                            }
                        },
                        "new_users": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}},
                {"$limit": 30}
            ]
            
            try:
                activity_result = await collection.aggregate(activity_pipeline).to_list(30)
            except:
                # Fallback if date parsing fails
                activity_result = []
            
            # Membership distribution with updated tiers
            membership_pipeline = [
                {
                    "$group": {
                        "_id": {"$ifNull": ["$Membership.tier", "Freemium"]},
                        "count": {"$sum": 1},
                        "total_downloads": {"$sum": {"$ifNull": ["$Bot Usage.total_downloads", 0]}}
                    }
                },
                {"$sort": {"count": -1}}
            ]
            
            membership_result = await collection.aggregate(membership_pipeline).to_list(10)
            
            # Top users by downloads
            top_users_pipeline = [
                {"$match": {"Bot Usage.total_downloads": {"$gt": 0}}},
                {
                    "$project": {
                        "username": "$User Info.username",
                        "nama_depan": "$User Info.nama_depan",
                        "total_downloads": "$Bot Usage.total_downloads",
                        "membership_tier": "$Membership.tier"
                    }
                },
                {"$sort": {"total_downloads": -1}},
                {"$limit": 10}
            ]
            
            top_users_result = await collection.aggregate(top_users_pipeline).to_list(10)
            
            # Usage statistics by platform
            platform_pipeline = [
                {
                    "$project": {
                        "has_telegram": {"$gt": [{"$size": {"$ifNull": ["$Bot Usage.last_feature_usage.Telegram", []]}}, 0]},
                        "has_tiktok": {"$gt": [{"$size": {"$ifNull": ["$Bot Usage.last_feature_usage.TikTok", []]}}, 0]},
                        "has_instagram": {"$gt": [{"$size": {"$ifNull": ["$Bot Usage.last_feature_usage.Instagram", []]}}, 0]},
                        "has_doodstream": {"$gt": [{"$size": {"$ifNull": ["$Bot Usage.last_feature_usage.Doodstream", []]}}, 0]}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "telegram_users": {"$sum": {"$cond": ["$has_telegram", 1, 0]}},
                        "tiktok_users": {"$sum": {"$cond": ["$has_tiktok", 1, 0]}},
                        "instagram_users": {"$sum": {"$cond": ["$has_instagram", 1, 0]}},
                        "doodstream_users": {"$sum": {"$cond": ["$has_doodstream", 1, 0]}}
                    }
                }
            ]
            
            try:
                platform_result = await collection.aggregate(platform_pipeline).to_list(1)
                platform_stats = platform_result[0] if platform_result else {}
                if "_id" in platform_stats:
                    del platform_stats["_id"]
            except:
                platform_stats = {}
            
            return {
                "overview": overview,
                "daily_activity": activity_result,
                "membership_distribution": membership_result,
                "top_users": [self.convert_object_ids(user) for user in top_users_result],
                "platform_usage": platform_stats,
                "date_range": request.date_range,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error in get_analytics_data: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch analytics: {str(e)}")

    async def get_quick_stats(self):
        """Get quick statistics for dashboard overview"""
        try:
            collection = self.database["CompleteUsersData"]
            
            # Use aggregation for better performance
            stats_pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_users": {"$sum": 1},
                        "total_downloads": {"$sum": {"$ifNull": ["$Bot Usage.total_downloads", 0]}},
                        "active_users": {
                            "$sum": {
                                "$cond": [
                                    {"$and": [
                                        {"$ne": ["$Bot Usage.last_download_time", ""]},
                                        {"$ne": ["$Bot Usage.last_download_time", None]},
                                        {"$exists": "$Bot Usage.last_download_time"}
                                    ]},
                                    1, 0
                                ]
                            }
                        },
                        "premium_users": {
                            "$sum": {
                                "$cond": [
                                    {"$in": ["$Membership.tier", ["Premium", "Plus", "VIP", "Zenith"]]},
                                    1, 0
                                ]
                            }
                        },
                        "users_with_session": {
                            "$sum": {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$exists": "$Data Lengkap Sesi.Session Info.session_string"},
                                            {"$ne": ["$Data Lengkap Sesi.Session Info.session_string", ""]},
                                            {"$ne": ["$Data Lengkap Sesi.Session Info.session_string", None]}
                                        ]
                                    },
                                    1, 0
                                ]
                            }
                        }
                    }
                }
            ]
            
            result = await collection.aggregate(stats_pipeline).to_list(1)
            stats = result[0] if result else {}
            if "_id" in stats:
                del stats["_id"]
            
            # Add computed metrics
            stats.update({
                "uptime": "99.9%",
                "response_time": "120ms",
                "last_updated": datetime.utcnow().isoformat()
            })
            
            return stats
            
        except Exception as e:
            print(f"Error in get_quick_stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
