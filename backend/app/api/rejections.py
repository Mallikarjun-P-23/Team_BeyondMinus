"""
Rejection Monitoring API Endpoints
Provides access to workflow rejection logs and statistics
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.rejection_logger import (
    get_rejection_stats,
    get_recent_rejections,
    REJECTION_LOG_FILE
)

router = APIRouter(prefix="/rejections", tags=["rejections"])


@router.get("/stats")
async def get_rejection_statistics():
    """Get statistics about workflow rejections"""
    return get_rejection_stats()


@router.get("/recent")
async def list_recent_rejections(
    limit: int = Query(10, ge=1, le=100, description="Number of recent rejections to return")
):
    """List recent workflow rejections"""
    rejections = get_recent_rejections(limit=limit)
    return {
        "count": len(rejections),
        "rejections": rejections,
        "log_file": str(REJECTION_LOG_FILE)
    }


@router.get("/log")
async def download_rejection_log():
    """Get the full rejection log file content"""
    if not REJECTION_LOG_FILE.exists():
        raise HTTPException(status_code=404, detail="Rejection log file not found")
    
    try:
        with open(REJECTION_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "log_file": str(REJECTION_LOG_FILE),
            "content": content,
            "size_bytes": len(content)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read rejection log: {str(e)}"
        )
