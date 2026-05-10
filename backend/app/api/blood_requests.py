"""
Blood Request API Endpoints
Patient blood request management with emergency notifications
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.services import blood_request_service as brs
from app.services import postgres_service as db

router = APIRouter(prefix="/blood-requests", tags=["blood-requests"])


# Pydantic Models
class BloodRequestCreate(BaseModel):
    patient_id: str
    patient_name: str
    blood_group: str = Field(pattern="^(A|B|AB|O)[+-]$")
    location: str
    needed_by_date: str  # ISO format datetime
    contact_number: str
    is_emergency: bool = False
    units_needed: int = Field(default=1, ge=1, le=20)
    reason: Optional[str] = None
    medical_condition: Optional[str] = None
    hospital_name: Optional[str] = None
    alternative_contact: Optional[str] = None
    doctor_id: Optional[str] = None
    notes: Optional[str] = None


class BloodRequestUpdate(BaseModel):
    status: str = Field(pattern="^(pending|acknowledged|arranged|fulfilled|cancelled|expired)$")
    notes: Optional[str] = None


class BloodRequestAcknowledge(BaseModel):
    doctor_id: str


class BloodRequestFulfill(BaseModel):
    doctor_id: str
    notes: Optional[str] = None


class BloodRequestCancel(BaseModel):
    reason: Optional[str] = None


# API Endpoints

@router.post("/", status_code=201)
async def create_blood_request(body: BloodRequestCreate):
    """
    Create a new blood request from a patient.
    Emergency requests automatically notify all available doctors.
    """
    try:
        # Verify patient exists
        patient = db.get_patient(body.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Verify doctor if provided
        if body.doctor_id:
            doctor = db.get_doctor(body.doctor_id)
            if not doctor:
                raise HTTPException(status_code=404, detail="Doctor not found")
        
        request = brs.create_blood_request(
            patient_id=body.patient_id,
            patient_name=body.patient_name,
            blood_group=body.blood_group,
            location=body.location,
            needed_by_date=body.needed_by_date,
            contact_number=body.contact_number,
            is_emergency=body.is_emergency,
            units_needed=body.units_needed,
            reason=body.reason,
            medical_condition=body.medical_condition,
            hospital_name=body.hospital_name,
            alternative_contact=body.alternative_contact,
            doctor_id=body.doctor_id,
            notes=body.notes,
        )
        
        return {
            "success": True,
            "message": "Blood request created successfully" + (" - Emergency notifications sent!" if body.is_emergency else ""),
            "request": request
        }
    
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create blood request: {exc}")


@router.get("/")
async def list_blood_requests(
    doctor_id: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_emergency: Optional[bool] = Query(None),
    blood_group: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List blood requests with optional filters"""
    try:
        requests = brs.list_blood_requests(
            doctor_id=doctor_id,
            patient_id=patient_id,
            status=status,
            is_emergency=is_emergency,
            blood_group=blood_group,
            limit=limit,
        )
        return {
            "count": len(requests),
            "requests": requests
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch blood requests: {exc}")


@router.get("/emergency")
async def get_emergency_requests(doctor_id: Optional[str] = Query(None)):
    """Get all active emergency blood requests"""
    try:
        requests = brs.get_emergency_blood_requests(doctor_id=doctor_id)
        return {
            "count": len(requests),
            "emergency_requests": requests
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emergency requests: {exc}")


@router.get("/stats")
async def get_blood_request_statistics(doctor_id: Optional[str] = Query(None)):
    """Get statistics for blood requests"""
    try:
        stats = brs.get_blood_request_stats(doctor_id=doctor_id)
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {exc}")


@router.get("/{request_id}")
async def get_blood_request(request_id: str):
    """Get a single blood request by ID"""
    request = brs.get_blood_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Blood request not found")
    return request


@router.put("/{request_id}")
async def update_blood_request(request_id: str, body: BloodRequestUpdate):
    """Update blood request status"""
    try:
        # Verify request exists
        existing = brs.get_blood_request(request_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Blood request not found")
        
        updated = brs.update_blood_request_status(
            request_id=request_id,
            status=body.status,
            notes=body.notes,
        )
        
        return {
            "success": True,
            "message": f"Blood request status updated to {body.status}",
            "request": updated
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update blood request: {exc}")


@router.post("/{request_id}/acknowledge")
async def acknowledge_blood_request(request_id: str, body: BloodRequestAcknowledge):
    """Doctor acknowledges a blood request"""
    try:
        # Verify doctor exists
        doctor = db.get_doctor(body.doctor_id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        # Verify request exists
        existing = brs.get_blood_request(request_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Blood request not found")
        
        updated = brs.acknowledge_blood_request(request_id, body.doctor_id)
        
        return {
            "success": True,
            "message": "Blood request acknowledged successfully",
            "request": updated
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge request: {exc}")


@router.post("/{request_id}/fulfill")
async def fulfill_blood_request(request_id: str, body: BloodRequestFulfill):
    """Mark blood request as fulfilled"""
    try:
        # Verify doctor exists
        doctor = db.get_doctor(body.doctor_id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        # Verify request exists
        existing = brs.get_blood_request(request_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Blood request not found")
        
        updated = brs.fulfill_blood_request(request_id, body.doctor_id, body.notes)
        
        return {
            "success": True,
            "message": "Blood request marked as fulfilled",
            "request": updated
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fulfill request: {exc}")


@router.post("/{request_id}/cancel")
async def cancel_blood_request(request_id: str, body: BloodRequestCancel):
    """Cancel a blood request"""
    try:
        # Verify request exists
        existing = brs.get_blood_request(request_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Blood request not found")
        
        updated = brs.cancel_blood_request(request_id, body.reason)
        
        return {
            "success": True,
            "message": "Blood request cancelled",
            "request": updated
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to cancel request: {exc}")


# Notification Endpoints

@router.get("/notifications/doctor/{doctor_id}")
async def get_doctor_notifications(
    doctor_id: str,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """Get blood request notifications for a doctor"""
    try:
        # Verify doctor exists
        doctor = db.get_doctor(doctor_id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        notifications = brs.get_doctor_blood_notifications(
            doctor_id=doctor_id,
            unread_only=unread_only,
            limit=limit
        )
        
        unread_count = brs.get_unread_notification_count(doctor_id)
        
        return {
            "count": len(notifications),
            "unread_count": unread_count,
            "notifications": notifications
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notifications: {exc}")


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read"""
    try:
        success = brs.mark_notification_as_read(notification_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {
            "success": True,
            "message": "Notification marked as read"
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update notification: {exc}")


@router.get("/notifications/doctor/{doctor_id}/unread-count")
async def get_unread_count(doctor_id: str):
    """Get count of unread notifications for a doctor"""
    try:
        count = brs.get_unread_notification_count(doctor_id)
        return {
            "doctor_id": doctor_id,
            "unread_count": count
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unread count: {exc}")


@router.post("/notifications/doctor/{doctor_id}/read-all")
async def mark_all_read(doctor_id: str):
    """Mark all notifications as read for a doctor"""
    try:
        # Verify doctor exists
        doctor = db.get_doctor(doctor_id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        count = brs.mark_all_notifications_as_read(doctor_id)
        
        return {
            "success": True,
            "message": f"Marked {count} notifications as read",
            "marked_count": count
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to mark all as read: {exc}")
