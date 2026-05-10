"""
Blood Request Service
Handles patient blood requests with emergency notifications
"""
from typing import Any, List, Dict, Optional
from datetime import datetime, timezone
from app.services import postgres_service as db


def create_blood_request(
    patient_id: str,
    patient_name: str,
    blood_group: str,
    location: str,
    needed_by_date: str,
    contact_number: str,
    is_emergency: bool = False,
    units_needed: int = 1,
    reason: str | None = None,
    medical_condition: str | None = None,
    hospital_name: str | None = None,
    alternative_contact: str | None = None,
    doctor_id: str | None = None,
    notes: str | None = None,
) -> Dict[str, Any]:
    """Create a new blood request from a patient"""
    
    request_data = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "blood_group": blood_group.upper(),
        "units_needed": units_needed,
        "location": location,
        "needed_by_date": needed_by_date,
        "contact_number": contact_number,
        "is_emergency": is_emergency,
        "reason": reason,
        "medical_condition": medical_condition,
        "hospital_name": hospital_name,
        "alternative_contact": alternative_contact,
        "doctor_id": doctor_id,
        "notes": notes,
        "status": "pending",
    }
    
    request = db._insert_row("blood_requests", request_data)
    
    # If a specific doctor was selected, create a notification for them
    if doctor_id:
        db._insert_row("blood_request_notifications", {
            "blood_request_id": request["id"],
            "doctor_id": doctor_id,
            "notification_type": "emergency" if is_emergency else "status_change",
            "title": "🩸 New Blood Request" if not is_emergency else "🚨 EMERGENCY Blood Request",
            "message": f"Blood request from {patient_name}: {blood_group.upper()} needed at {location}",
            "is_read": False
        })
    
    # Emergency requests automatically trigger notifications via database trigger for ALL doctors
    # (The above code handles the specific doctor if provided, the trigger handles others)
    
    return request


def list_blood_requests(
    doctor_id: str | None = None,
    patient_id: str | None = None,
    status: str | None = None,
    is_emergency: bool | None = None,
    blood_group: str | None = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List blood requests with filters"""
    
    query = """
        SELECT 
            br.*,
            p.name as patient_full_name,
            p.phone as patient_phone,
            d.name as doctor_name,
            ack_doc.name as acknowledged_by_name,
            ful_doc.name as fulfilled_by_name
        FROM blood_requests br
        LEFT JOIN patients p ON br.patient_id = p.id
        LEFT JOIN doctors d ON br.doctor_id = d.id
        LEFT JOIN doctors ack_doc ON br.acknowledged_by = ack_doc.id
        LEFT JOIN doctors ful_doc ON br.fulfilled_by = ful_doc.id
        WHERE 1=1
    """
    
    params = []
    
    if doctor_id:
        query += " AND (br.doctor_id = %s OR br.is_emergency = TRUE)"
        params.append(doctor_id)
    
    if patient_id:
        query += " AND br.patient_id = %s"
        params.append(patient_id)
    
    if status:
        query += " AND br.status = %s"
        params.append(status)
    
    if is_emergency is not None:
        query += " AND br.is_emergency = %s"
        params.append(is_emergency)
    
    if blood_group:
        query += " AND br.blood_group = %s"
        params.append(blood_group.upper())
    
    query += " ORDER BY br.is_emergency DESC, br.priority DESC, br.created_at DESC LIMIT %s"
    params.append(limit)
    
    with db._cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def get_blood_request(request_id: str) -> Dict[str, Any] | None:
    """Get a single blood request by ID"""
    query = """
        SELECT 
            br.*,
            p.name as patient_full_name,
            p.phone as patient_phone,
            p.email as patient_email,
            d.name as doctor_name,
            ack_doc.name as acknowledged_by_name,
            ful_doc.name as fulfilled_by_name
        FROM blood_requests br
        LEFT JOIN patients p ON br.patient_id = p.id
        LEFT JOIN doctors d ON br.doctor_id = d.id
        LEFT JOIN doctors ack_doc ON br.acknowledged_by = ack_doc.id
        LEFT JOIN doctors ful_doc ON br.fulfilled_by = ful_doc.id
        WHERE br.id = %s
    """
    
    with db._cursor() as cur:
        cur.execute(query, (request_id,))
        result = cur.fetchone()
        return dict(result) if result else None


def update_blood_request_status(
    request_id: str,
    status: str,
    doctor_id: str | None = None,
    notes: str | None = None,
) -> Dict[str, Any]:
    """Update blood request status"""
    
    update_data: Dict[str, Any] = {"status": status}
    
    if notes:
        update_data["admin_notes"] = notes
    
    if status == "acknowledged" and doctor_id:
        update_data["acknowledged_by"] = doctor_id
        update_data["acknowledged_at"] = datetime.now(timezone.utc)
    
    if status == "fulfilled" and doctor_id:
        update_data["fulfilled_by"] = doctor_id
        update_data["fulfilled_at"] = datetime.now(timezone.utc)
    
    if status == "cancelled":
        update_data["cancelled_at"] = datetime.now(timezone.utc)
        if notes:
            update_data["cancellation_reason"] = notes
    
    return db._update_row("blood_requests", request_id, update_data)


def acknowledge_blood_request(request_id: str, doctor_id: str) -> Dict[str, Any]:
    """Doctor acknowledges a blood request"""
    return update_blood_request_status(request_id, "acknowledged", doctor_id)


def fulfill_blood_request(request_id: str, doctor_id: str, notes: str | None = None) -> Dict[str, Any]:
    """Mark blood request as fulfilled"""
    return update_blood_request_status(request_id, "fulfilled", doctor_id, notes)


def cancel_blood_request(request_id: str, reason: str | None = None) -> Dict[str, Any]:
    """Cancel a blood request"""
    return update_blood_request_status(request_id, "cancelled", notes=reason)


def get_emergency_blood_requests(doctor_id: str | None = None) -> List[Dict[str, Any]]:
    """Get all active emergency blood requests"""
    return list_blood_requests(
        doctor_id=doctor_id,
        is_emergency=True,
        status="pending",
        limit=50
    )


def get_blood_request_stats(doctor_id: str | None = None) -> Dict[str, Any]:
    """Get statistics for blood requests"""
    
    base_query = """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
            COUNT(*) FILTER (WHERE status = 'acknowledged') as acknowledged_count,
            COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled_count,
            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_count,
            COUNT(*) FILTER (WHERE is_emergency = TRUE AND status = 'pending') as emergency_count,
            COUNT(*) FILTER (WHERE priority = 'critical') as critical_count,
            COUNT(*) FILTER (WHERE priority = 'high') as high_count,
            COUNT(*) as total_count
        FROM blood_requests
        WHERE 1=1
    """
    
    params = []
    if doctor_id:
        base_query += " AND (doctor_id = %s OR is_emergency = TRUE)"
        params.append(doctor_id)
    
    with db._cursor() as cur:
        cur.execute(base_query, params)
        result = cur.fetchone()
        return dict(result) if result else {}


def get_doctor_blood_notifications(doctor_id: str, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """Get blood request notifications for a doctor"""
    
    query = """
        SELECT 
            brn.*,
            br.patient_name,
            br.blood_group,
            br.location,
            br.is_emergency,
            br.status as request_status
        FROM blood_request_notifications brn
        LEFT JOIN blood_requests br ON brn.blood_request_id = br.id
        WHERE brn.doctor_id = %s
    """
    
    params = [doctor_id]
    
    if unread_only:
        query += " AND brn.is_read = FALSE"
    
    query += " ORDER BY brn.created_at DESC LIMIT %s"
    params.append(limit)
    
    with db._cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def mark_notification_as_read(notification_id: str) -> bool:
    """Mark a notification as read"""
    try:
        db._update_row("blood_request_notifications", notification_id, {
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })
        return True
    except Exception:
        return False


def mark_all_notifications_as_read(doctor_id: str) -> int:
    """Mark all notifications as read for a doctor"""
    query = """
        UPDATE blood_request_notifications
        SET is_read = TRUE, read_at = %s
        WHERE doctor_id = %s AND is_read = FALSE
        RETURNING id
    """
    with db._cursor() as cur:
        cur.execute(query, (datetime.now(timezone.utc), doctor_id))
        results = cur.fetchall()
        return len(results)


def get_unread_notification_count(doctor_id: str) -> int:
    """Get count of unread notifications for a doctor"""
    query = """
        SELECT COUNT(*) as count
        FROM blood_request_notifications
        WHERE doctor_id = %s AND is_read = FALSE
    """
    
    with db._cursor() as cur:
        cur.execute(query, (doctor_id,))
        result = cur.fetchone()
        return result["count"] if result else 0
