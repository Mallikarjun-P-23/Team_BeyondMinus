"""
Monitoring API Endpoints for Observer Agent
Provides real-time system monitoring and error tracking
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from app.services.observer_agent import get_observer, ErrorCategory, SeverityLevel

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def get_system_health():
    """Get current system health status"""
    observer = get_observer()
    health = await observer.get_system_health()
    return health


@router.get("/errors/summary")
async def get_error_summary():
    """Get summary of recent errors"""
    observer = get_observer()
    summary = observer.get_error_summary()
    return summary


@router.get("/errors")
async def list_errors(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=500)
):
    """List recent errors with filtering"""
    observer = get_observer()
    errors = observer.error_buffer[-limit:]
    
    # Apply filters
    if severity:
        errors = [e for e in errors if e.severity.value == severity.lower()]
    if category:
        errors = [e for e in errors if e.category.value == category.lower()]
    
    return {
        "count": len(errors),
        "errors": [e.to_dict() for e in errors]
    }


@router.get("/errors/{error_id}")
async def get_error_details(error_id: str):
    """Get detailed information about a specific error"""
    observer = get_observer()
    
    # Find error in buffer
    error = next((e for e in observer.error_buffer if e.error_id == error_id), None)
    
    if not error:
        raise HTTPException(status_code=404, detail="Error not found in recent buffer")
    
    return error.to_dict()


@router.get("/stats")
async def get_monitoring_stats():
    """Get monitoring statistics"""
    observer = get_observer()
    
    return {
        "error_counts": dict(observer.error_counts),
        "total_errors": len(observer.error_buffer),
        "monitoring_active": observer.monitoring_active,
        "buffer_size": len(observer.error_buffer),
        "max_buffer_size": observer.max_buffer_size,
        "errors_by_category": observer._get_errors_by_category()
    }


@router.post("/errors/clear")
async def clear_error_buffer():
    """Clear the error buffer (admin only)"""
    observer = get_observer()
    count = len(observer.error_buffer)
    observer.error_buffer.clear()
    observer.error_counts = {
        SeverityLevel.CRITICAL: 0,
        SeverityLevel.ERROR: 0,
        SeverityLevel.WARNING: 0
    }
    return {
        "message": f"Cleared {count} errors from buffer",
        "cleared_count": count
    }


@router.get("/categories")
async def list_error_categories():
    """List available error categories"""
    return {
        "categories": [c.value for c in ErrorCategory]
    }


@router.get("/severities")
async def list_severity_levels():
    """List available severity levels"""
    return {
        "severities": [s.value for s in SeverityLevel]
    }
