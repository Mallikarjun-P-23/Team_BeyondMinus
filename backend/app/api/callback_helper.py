"""
Helper functions for callback request handling
Import this into endpoints.py to handle automatic callbacks
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


async def trigger_callback_if_disconnected(
    call_log: Dict[str, Any],
    call_outcome: str,
    patient_confirmed: bool,
    confirmed_date: Optional[str],
    callback_service
):
    """
    Automatically trigger a callback if patient cuts the call without booking
    
    Args:
        call_log: The call log record
        call_outcome: Outcome of the call
        patient_confirmed: Whether patient confirmed appointment
        confirmed_date: Confirmed appointment date if any
        callback_service: Instance of CallbackService
    
    Returns:
        callback_id if callback was created, None otherwise
    """
    # Don't create callback if appointment was successfully booked
    if patient_confirmed and confirmed_date:
        logger.info(f"Call {call_log['id']}: Appointment booked successfully, no callback needed")
        return None
    
    # Outcomes that should trigger auto-callback
    disconnect_outcomes = {
        "interrupted",
        "disconnected",
        "call_ended_prematurely",
        "patient_hung_up",
        "no_answer",
        "busy",
        "unreachable"
    }
    
    outcome_lower = (call_outcome or "").strip().lower()
    
    # Check if this is a disconnect situation
    should_callback = outcome_lower in disconnect_outcomes
    
    # Also check transcript for sudden disconnection
    transcript = call_log.get("transcript_ref", "")
    exec_log = call_log.get("execution_log", [])
    
    for step in exec_log:
        transcript_text = step.get("transcript", "")
        if transcript_text and any(
            phrase in transcript_text.lower() 
            for phrase in ["call ended", "disconnected", "hung up", "dropped"]
        ):
            should_callback = True
            break
    
    if not should_callback:
        logger.info(
            f"Call {call_log['id']}: Outcome '{call_outcome}' does not require callback"
        )
        return None
    
    # Extract patient information
    patient_phone = call_log.get("phone_number")
    patient_id = call_log.get("patient_id")
    doctor_id = call_log.get("doctor_id")
    
    if not patient_phone:
        logger.warning(f"Call {call_log['id']}: No patient phone number, cannot create callback")
        return None
    
    # Get patient name if available
    patient_name = None
    if patient_id:
        try:
            from app.services.postgres_service import get_patient
            patient = get_patient(patient_id)
            if patient:
                patient_name = patient.get("name")
        except Exception as e:
            logger.warning(f"Could not fetch patient name: {e}")
    
    # Create callback request with 30 second delay
    try:
        callback_id = await callback_service.create_callback_request(
            call_log_id=call_log["id"],
            patient_phone=patient_phone,
            trigger_type="auto_disconnect",
            delay_seconds=30,
            doctor_id=doctor_id,
            patient_id=patient_id,
            patient_name=patient_name,
            reason=f"Auto callback after {call_outcome} - patient disconnected before booking",
            priority=1,  # High priority for auto-callbacks
            metadata={
                "original_call_outcome": call_outcome,
                "auto_triggered": True,
                "trigger_reason": "patient_disconnected"
            }
        )
        
        logger.info(
            f"Created auto-callback {callback_id} for call {call_log['id']}, "
            f"scheduled in 30 seconds for {patient_phone}"
        )
        
        return callback_id
        
    except Exception as e:
        logger.error(f"Failed to create callback request: {str(e)}", exc_info=True)
        return None


def should_trigger_callback_for_outcome(call_outcome: str) -> bool:
    """Check if a call outcome should trigger an automatic callback"""
    disconnect_outcomes = {
        "interrupted",
        "disconnected",
        "call_ended_prematurely",
        "patient_hung_up",
        "no_answer",
        "busy",
        "unreachable",
        "callback_requested"  # Explicit callback request
    }
    
    outcome_lower = (call_outcome or "").strip().lower()
    return outcome_lower in disconnect_outcomes
