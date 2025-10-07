from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING, ASCENDING
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime, timedelta
import re
import pytz
from collections import defaultdict


class AnalyticsTimeframeRequest(BaseModel):
    timeframe: str = "7d"  # 1d, 3d, 7d, 30d, 90d
    
class AnalyticsStatsRequest(BaseModel):
    timeframe: str = "7d"
    stats_type: str = "commands"  # commands, urls
    
class AnalyticsUsersRequest(BaseModel):
    timeframe: str = "7d"
    unique_only: bool = True


class HyperBotAnalyticsController:
    def __init__(self, database):
        self.database = database
        self.client = database.client  # Store client reference for cross-database access
        self.wib_tz = pytz.timezone('Asia/Jakarta')

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

    def get_timeframe_filter(self, timeframe: str) -> datetime:
        """Get datetime filter based on timeframe"""
        now = datetime.now(self.wib_tz)
        
        timeframe_map = {
            "1d": timedelta(days=1),
            "3d": timedelta(days=3),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90)
        }
        
        if timeframe not in timeframe_map:
            raise HTTPException(status_code=400, detail="Invalid timeframe")
            
        return now - timeframe_map[timeframe]

    def get_date_grouping(self, timeframe: str) -> str:
        """Get appropriate date grouping format based on timeframe"""
        if timeframe in ["1d", "3d"]:
            return "%Y-%m-%d %H:00"  # Group by hour
        elif timeframe in ["7d", "30d"]:
            return "%Y-%m-%d"  # Group by day
        else:  # 90d
            return "%Y-%m"  # Group by month

    async def debug_database_structure(self) -> Dict[str, Any]:
        """Debug method to check database structure and sample data"""
        try:
            # Check current database in use
            current_db_name = self.database.name
            print(f"Current database in use: {current_db_name}")
            
            # List all databases
            databases = await self.database.client.list_database_names()
            print(f"Available databases: {databases}")
            
            # Check the main database we're connected to
            main_db = self.database
            main_collections = await main_db.list_collection_names()
            print(f"Collections in {current_db_name}: {main_collections}")
            
            # Check if Analytics database exists
            analytics_exists = "Analytics" in databases
            print(f"Analytics database exists: {analytics_exists}")
            
            debug_info = {
                "current_database": current_db_name,
                "available_databases": databases,
                "collections_in_current_db": main_collections,
                "analytics_db_exists": analytics_exists
            }
            
            if analytics_exists:
                # Check Analytics database specifically
                analytics_db = self.database.client["Analytics"]
                analytics_collections = await analytics_db.list_collection_names()
                print(f"Collections in Analytics database: {analytics_collections}")
                
                debug_info["analytics_collections"] = analytics_collections
                
                # Check if general_users collection exists in Analytics
                if "general_users" in analytics_collections:
                    analytics_collection = analytics_db["general_users"]
                    total_docs = await analytics_collection.count_documents({})
                    print(f"Total documents in Analytics.general_users: {total_docs}")
                    
                    debug_info["analytics_general_users_count"] = total_docs
                    
                    if total_docs > 0:
                        # Get sample documents
                        sample_docs = await analytics_collection.find({}).limit(3).to_list(None)
                        debug_info["sample_analytics_docs"] = sample_docs[:2]
                        print(f"Sample analytics documents: {sample_docs}")
                else:
                    print("❌ general_users collection not found in Analytics database!")
                    debug_info["error"] = "general_users collection not found in Analytics database"
            
            # Also check if there are any analytics-related collections in the main database
            analytics_like_collections = [col for col in main_collections if 'analytic' in col.lower() or 'general' in col.lower()]
            if analytics_like_collections:
                print(f"Analytics-like collections in main DB: {analytics_like_collections}")
                debug_info["analytics_like_collections_in_main_db"] = analytics_like_collections
                
                # Sample data from first analytics-like collection
                if analytics_like_collections:
                    first_collection = main_db[analytics_like_collections[0]]
                    sample_count = await first_collection.count_documents({})
                    print(f"Sample count in {analytics_like_collections[0]}: {sample_count}")
                    debug_info[f"sample_count_{analytics_like_collections[0]}"] = sample_count
            
            return debug_info
            
        except Exception as e:
            print(f"Error in debug_database_structure: {str(e)}")
            return {"error": str(e)}

    async def create_sample_analytics_data(self) -> Dict[str, Any]:
        """Create sample analytics data for testing"""
        try:
            # Get or create Analytics database
            analytics_db = self.database.client["Analytics"]
            analytics_collection = analytics_db["general_users"]
            
            # Sample data based on the format you provided
            sample_data = []
            
            # Create data for the last 30 days
            for i in range(30):
                date = datetime.now(self.wib_tz) - timedelta(days=i)
                
                # Create multiple entries per day with different patterns
                for j in range(5 + (i % 10)):  # Varying number of entries per day
                    user_id = f"762248265{j % 10}"  # Simulate different users
                    
                    # Mix of commands and URLs
                    if j % 3 == 0:
                        description = f"/start"
                    elif j % 3 == 1:
                        description = f"/mode"
                    else:
                        description = f"https://d-s.io/e/h7ecgw5oqn8{j % 100}"
                    
                    sample_entry = {
                        "user_id": user_id,
                        "description": description,
                        "timestamp": date.strftime('%d-%m-%Y %H:%M WIB'),
                        "created_at": date  # Store as datetime object
                    }
                    sample_data.append(sample_entry)
            
            # Insert sample data
            if sample_data:
                result = await analytics_collection.insert_many(sample_data)
                inserted_count = len(result.inserted_ids)
                
                return {
                    "success": True,
                    "message": f"Created {inserted_count} sample analytics documents",
                    "sample_count": inserted_count,
                    "date_range": f"Last 30 days from {datetime.now(self.wib_tz).strftime('%Y-%m-%d')}"
                }
            else:
                return {"error": "No sample data created"}
                
        except Exception as e:
            print(f"Error creating sample data: {str(e)}")
            return {"error": str(e)}

    async def get_analytics_overview(self, request: AnalyticsTimeframeRequest) -> Dict[str, Any]:
        """Get analytics overview with total visitors, unique visitors, and total analytics"""
        try:
            analytics_collection = self.client["Analytics"]["general_users"]
            
            start_date = self.get_timeframe_filter(request.timeframe)
            date_format = self.get_date_grouping(request.timeframe)
            
            # Debug: Check if collection exists and has data
            total_docs = await analytics_collection.count_documents({})
            print(f"Total documents in collection: {total_docs}")
            
            # Check documents with created_at field
            docs_with_created_at = await analytics_collection.count_documents({"created_at": {"$exists": True}})
            print(f"Documents with created_at field: {docs_with_created_at}")
            
            # Sample document to check structure
            sample_doc = await analytics_collection.find_one({})
            if sample_doc:
                print(f"Sample document structure: {sample_doc}")
            
            # Modified pipeline to handle both string timestamps and ISO dates
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"created_at": {"$gte": start_date}},
                            {"created_at": {"$type": "string"}}  # Handle string dates
                        ]
                    }
                },
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "date": {"$dateToString": {"format": date_format, "date": "$parsed_date", "timezone": "Asia/Jakarta"}},
                            "user_id": "$user_id"
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$group": {
                        "_id": "$_id.date",
                        "unique_visitors": {"$sum": 1},
                        "total_analytics": {"$sum": "$count"}
                    }
                },
                {
                    "$sort": {"_id": 1}
                }
            ]
            
            results = await analytics_collection.aggregate(pipeline).to_list(None)
            
            # Calculate totals
            total_unique_visitors = 0
            total_analytics = 0
            chart_data = []
            
            for result in results:
                total_unique_visitors += result["unique_visitors"]
                total_analytics += result["total_analytics"]
                chart_data.append({
                    "date": result["_id"],
                    "unique_visitors": result["unique_visitors"],
                    "total_analytics": result["total_analytics"]
                })
            
            # Get unique visitors for entire period
            unique_visitors_pipeline = [
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id"
                    }
                },
                {
                    "$count": "total"
                }
            ]
            
            unique_result = await analytics_collection.aggregate(unique_visitors_pipeline).to_list(None)
            period_unique_visitors = unique_result[0]["total"] if unique_result else 0
            
            print(f"Query results: {len(results)} time periods found")
            print(f"Period unique visitors: {period_unique_visitors}")
            print(f"Total analytics: {total_analytics}")
            
            return {
                "timeframe": request.timeframe,
                "period_unique_visitors": period_unique_visitors,
                "period_total_analytics": total_analytics,
                "chart_data": chart_data
            }
            
        except Exception as e:
            print(f"Error getting analytics overview: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get analytics overview: {str(e)}")

    async def get_daily_active_users(self, request: AnalyticsUsersRequest) -> Dict[str, Any]:
        """Get daily active users statistics"""
        try:
            analytics_collection = self.client["Analytics"]["general_users"]
            
            # Get today's date in WIB
            now = datetime.now(self.wib_tz)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Unique active users today with date handling
            unique_today_pipeline = [
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": today_start, "$lte": today_end}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id"
                    }
                },
                {
                    "$count": "total"
                }
            ]
            
            unique_today_result = await analytics_collection.aggregate(unique_today_pipeline).to_list(None)
            unique_active_today = unique_today_result[0]["total"] if unique_today_result else 0
            
            # Total active users today (including duplicates) with date handling
            total_today_pipeline = [
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": today_start, "$lte": today_end}
                    }
                },
                {
                    "$count": "total"
                }
            ]
            
            total_today_result = await analytics_collection.aggregate(total_today_pipeline).to_list(None)
            total_active_today = total_today_result[0]["total"] if total_today_result else 0
            
            return {
                "unique_active_today": unique_active_today,
                "total_active_today": total_active_today,
                "date": now.strftime("%Y-%m-%d")
            }
            
        except Exception as e:
            print(f"Error getting daily active users: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get daily active users: {str(e)}")

    async def get_command_stats(self, request: AnalyticsStatsRequest) -> Dict[str, Any]:
        """Get command statistics (messages starting with / like /start, /mode)"""
        try:
            analytics_collection = self.client["Analytics"]["general_users"]
            
            start_date = self.get_timeframe_filter(request.timeframe)
            
            # Pipeline to get command statistics with date handling
            pipeline = [
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": start_date},
                        "description": {"$regex": "^/", "$options": "i"}
                    }
                },
                {
                    "$group": {
                        "_id": "$description",
                        "count": {"$sum": 1},
                        "unique_users": {"$addToSet": "$user_id"}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "count": 1,
                        "unique_users": {"$size": "$unique_users"}
                    }
                },
                {
                    "$sort": {"count": -1}
                },
                {
                    "$limit": 10
                }
            ]
            
            results = await analytics_collection.aggregate(pipeline).to_list(None)
            
            # Get trend data for each command
            command_trends = []
            for result in results:
                command = result["_id"]
                
                # Get daily trend for this command with date handling
                trend_pipeline = [
                    {
                        "$addFields": {
                            "parsed_date": {
                                "$cond": {
                                    "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                    "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                    "else": "$created_at"
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "parsed_date": {"$gte": start_date},
                            "description": command
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": "$parsed_date",
                                    "timezone": "Asia/Jakarta"
                                }
                            },
                            "count": {"$sum": 1}
                        }
                    },
                    {
                        "$sort": {"_id": 1}
                    }
                ]
                
                trend_data = await analytics_collection.aggregate(trend_pipeline).to_list(None)
                trend_values = [item["count"] for item in trend_data]
                
                command_trends.append({
                    "command": command,
                    "total_count": result["count"],
                    "unique_users": result["unique_users"],
                    "trend_data": trend_values,
                    "trend_dates": [item["_id"] for item in trend_data]
                })
            
            return {
                "timeframe": request.timeframe,
                "commands": command_trends,
                "total_commands": len(results)
            }
            
        except Exception as e:
            print(f"Error getting command stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get command stats: {str(e)}")

    async def get_url_stats(self, request: AnalyticsStatsRequest) -> Dict[str, Any]:
        """Get URL statistics (messages starting with https)"""
        try:
            analytics_collection = self.client["Analytics"]["general_users"]
            
            start_date = self.get_timeframe_filter(request.timeframe)
            
            # Pipeline to get URL statistics with date handling
            pipeline = [
                {
                    "$addFields": {
                        "parsed_date": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                "else": "$created_at"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "parsed_date": {"$gte": start_date},
                        "description": {"$regex": "^https", "$options": "i"}
                    }
                },
                {
                    "$group": {
                        "_id": "$description",
                        "count": {"$sum": 1},
                        "unique_users": {"$addToSet": "$user_id"}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "count": 1,
                        "unique_users": {"$size": "$unique_users"}
                    }
                },
                {
                    "$sort": {"count": -1}
                },
                {
                    "$limit": 10
                }
            ]
            
            results = await analytics_collection.aggregate(pipeline).to_list(None)
            
            # Get trend data for each URL
            url_trends = []
            for result in results:
                url = result["_id"]
                
                # Get daily trend for this URL with date handling
                trend_pipeline = [
                    {
                        "$addFields": {
                            "parsed_date": {
                                "$cond": {
                                    "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                                    "then": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
                                    "else": "$created_at"
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "parsed_date": {"$gte": start_date},
                            "description": url
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": "$parsed_date",
                                    "timezone": "Asia/Jakarta"
                                }
                            },
                            "count": {"$sum": 1}
                        }
                    },
                    {
                        "$sort": {"_id": 1}
                    }
                ]
                
                trend_data = await analytics_collection.aggregate(trend_pipeline).to_list(None)
                trend_values = [item["count"] for item in trend_data]
                
                # Extract domain from URL for better display
                domain = re.search(r'https?://([^/]+)', url)
                display_url = domain.group(1) if domain else url
                
                url_trends.append({
                    "url": url,
                    "display_url": display_url,
                    "total_count": result["count"],
                    "unique_users": result["unique_users"],
                    "trend_data": trend_values,
                    "trend_dates": [item["_id"] for item in trend_data]
                })
            
            return {
                "timeframe": request.timeframe,
                "urls": url_trends,
                "total_urls": len(results)
            }
            
        except Exception as e:
            print(f"Error getting URL stats: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get URL stats: {str(e)}")

    async def get_analytics_summary(self, request: AnalyticsTimeframeRequest) -> Dict[str, Any]:
        """Get complete analytics summary combining all data"""
        try:
            # Get all data in parallel
            overview_task = self.get_analytics_overview(request)
            users_task = self.get_daily_active_users(AnalyticsUsersRequest(timeframe=request.timeframe))
            commands_task = self.get_command_stats(AnalyticsStatsRequest(timeframe=request.timeframe, stats_type="commands"))
            urls_task = self.get_url_stats(AnalyticsStatsRequest(timeframe=request.timeframe, stats_type="urls"))
            
            # Wait for all tasks to complete
            import asyncio
            overview, users, commands, urls = await asyncio.gather(
                overview_task, users_task, commands_task, urls_task
            )
            
            return {
                "timeframe": request.timeframe,
                "overview": overview,
                "daily_users": users,
                "top_commands": commands,
                "top_urls": urls,
                "generated_at": datetime.now(self.wib_tz).isoformat()
            }
            
        except Exception as e:
            print(f"Error getting analytics summary: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get analytics summary: {str(e)}")
