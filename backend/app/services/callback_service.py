"""
Callback Service
Handles automatic callback scheduling and triggering when patients disconnect
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class CallbackService:
    """Service for managing automatic callbacks to patients"""
    
    def __init__(self, db_pool, elevenlabs_service):
        self.db = db_pool
        self.elevenlabs = elevenlabs_service
    
    async def create_callback_request(
        self,
        call_log_id: UUID,
        patient_phone: str,
        trigger_type: str = "auto_disconnect",
        delay_seconds: int = 30,
        doctor_id: Optional[str] = None,
        patient_id: Optional[UUID] = None,
        patient_name: Optional[str] = None,
        reason: Optional[str] = None,
        priority: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Create a callback request that will be automatically triggered after delay
        
        Args:
            call_log_id: Original call log ID
            patient_phone: Patient's phone number
            trigger_type: Type of trigger (auto_disconnect, no_answer, interrupted)
            delay_seconds: Delay before callback (default 30s)
            doctor_id: Doctor ID if available
            patient_id: Patient UUID if available
            patient_name: Patient name if available
            reason: Reason for callback
            priority: Priority level (0=normal, 1=high, 2=urgent)
            metadata: Additional metadata
        
        Returns:
            UUID of created callback request
        """
        scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        query = """
            INSERT INTO callback_requests (
                call_log_id, patient_phone, doctor_id, patient_id, patient_name,
                reason, trigger_type, auto_trigger_delay_seconds, 
                scheduled_callback_at, status, priority, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'scheduled', $10, $11)
            RETURNING id
        """
        
        async with self.db.acquire() as conn:
            callback_id = await conn.fetchval(
                query,
                call_log_id,
                patient_phone,
                doctor_id,
                patient_id,
                patient_name,
                reason or f"Auto callback after {trigger_type}",
                trigger_type,
                delay_seconds,
                scheduled_at,
                priority,
                metadata or {}
            )
        
        logger.info(
            f"Created callback request {callback_id} for {patient_phone}, "
            f"scheduled at {scheduled_at} (in {delay_seconds}s)"
        )
        
        return callback_id
    
    async def process_due_callbacks(self):
        """
        Process all callback requests that are due to be triggered
        Should be run by a background worker
        """
        query = """
            SELECT id, call_log_id, patient_phone, doctor_id, patient_id, 
                   patient_name, reason, attempt_count, max_attempts, metadata
            FROM callback_requests
            WHERE status = 'scheduled'
              AND scheduled_callback_at <= NOW()
              AND attempt_count < max_attempts
            ORDER BY priority DESC, scheduled_callback_at ASC
            LIMIT 10
        """
        
        async with self.db.acquire() as conn:
            callbacks = await conn.fetch(query)
        
        if not callbacks:
            return
        
        logger.info(f"Processing {len(callbacks)} due callback requests")
        
        for callback in callbacks:
            await self._trigger_callback(dict(callback))
    
    async def _trigger_callback(self, callback: Dict[str, Any]):
        """
        Trigger an individual callback by initiating a new call
        
        Args:
            callback: Callback request record
        """
        callback_id = callback['id']
        patient_phone = callback['patient_phone']
        
        try:
            # Update status to in_progress
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE callback_requests
                    SET status = 'in_progress',
                        callback_attempted_at = NOW(),
                        attempt_count = attempt_count + 1,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    callback_id
                )
            
            logger.info(f"Triggering callback {callback_id} to {patient_phone}")
            
            # Get agent configuration for this doctor
            agent_config = await self._get_agent_config(callback['doctor_id'])
            
            if not agent_config:
                raise Exception(f"No agent configuration found for doctor {callback['doctor_id']}")
            
            # Initiate the callback via ElevenLabs
            call_result = await self._initiate_elevenlabs_call(
                patient_phone=patient_phone,
                agent_id=agent_config['agent_id'],
                callback_id=callback_id,
                metadata=callback.get('metadata', {})
            )
            
            # Update with new call log reference
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE callback_requests
                    SET new_call_log_id = $1,
                        status = 'completed',
                        callback_completed_at = NOW(),
                        updated_at = NOW(),
                        metadata = metadata || $2::jsonb
                    WHERE id = $3
                    """,
                    call_result.get('call_log_id'),
                    {'elevenlabs_call_id': call_result.get('call_id')},
                    callback_id
                )
            
            logger.info(f"Callback {callback_id} successfully triggered")
            
        except Exception as e:
            logger.error(f"Error triggering callback {callback_id}: {str(e)}")
            
            # Update with error, possibly reschedule
            should_retry = callback['attempt_count'] + 1 < callback['max_attempts']
            new_status = 'scheduled' if should_retry else 'failed'
            
            # If retrying, schedule for 5 minutes later
            next_scheduled = None
            if should_retry:
                next_scheduled = datetime.utcnow() + timedelta(minutes=5)
            
            async with self.db.acquire() as conn:
                if next_scheduled:
                    await conn.execute(
                        """
                        UPDATE callback_requests
                        SET status = $1,
                            last_error = $2,
                            scheduled_callback_at = $3,
                            updated_at = NOW()
                        WHERE id = $4
                        """,
                        new_status,
                        str(e),
                        next_scheduled,
                        callback_id
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE callback_requests
                        SET status = $1,
                            last_error = $2,
                            updated_at = NOW()
                        WHERE id = $3
                        """,
                        new_status,
                        str(e),
                        callback_id
                    )
    
    async def _get_agent_config(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        """Get agent configuration for a doctor"""
        if not doctor_id:
            return None
        
        query = """
            SELECT agent_id, phone_number_id, worker_name
            FROM call_worker_pools
            WHERE doctor_id = $1 AND is_active = TRUE
            LIMIT 1
        """
        
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(query, doctor_id)
        
        return dict(result) if result else None
    
    async def _initiate_elevenlabs_call(
        self,
        patient_phone: str,
        agent_id: str,
        callback_id: UUID,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initiate a call via ElevenLabs API
        
        Returns:
            Dict with call_id and call_log_id
        """
        # Format phone number
        if not patient_phone.startswith('+'):
            patient_phone = f'+91{patient_phone.lstrip("0")}'
        
        # Create call log entry first
        call_log_id = None
        async with self.db.acquire() as conn:
            call_log_id = await conn.fetchval(
                """
                INSERT INTO call_logs (
                    phone_number, direction, status, 
                    metadata, created_at
                ) VALUES ($1, 'outbound', 'initiated', $2, NOW())
                RETURNING id
                """,
                patient_phone,
                {
                    'callback_request_id': str(callback_id),
                    'is_callback': True,
                    **metadata
                }
            )
        
        # Initiate call via ElevenLabs service
        call_response = await self.elevenlabs.create_call(
            agent_id=agent_id,
            phone_number=patient_phone,
            metadata={
                'callback_request_id': str(callback_id),
                'call_log_id': str(call_log_id),
                'is_callback': True
            }
        )
        
        # Update call log with ElevenLabs call ID
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE call_logs
                SET external_call_id = $1,
                    metadata = metadata || $2::jsonb,
                    updated_at = NOW()
                WHERE id = $3
                """,
                call_response.get('call_id'),
                {'elevenlabs_response': call_response},
                call_log_id
            )
        
        return {
            'call_id': call_response.get('call_id'),
            'call_log_id': call_log_id
        }
    
    async def cancel_callback(self, callback_id: UUID, reason: str = "Cancelled by user"):
        """Cancel a pending callback request"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE callback_requests
                SET status = 'cancelled',
                    notes = COALESCE(notes || ' | ', '') || $1,
                    updated_at = NOW()
                WHERE id = $2 AND status IN ('pending', 'scheduled')
                """,
                reason,
                callback_id
            )
        
        logger.info(f"Cancelled callback request {callback_id}: {reason}")
    
    async def get_callback_status(self, callback_id: UUID) -> Optional[Dict[str, Any]]:
        """Get status of a callback request"""
        query = """
            SELECT id, call_log_id, patient_phone, doctor_id, status,
                   trigger_type, scheduled_callback_at, callback_attempted_at,
                   callback_completed_at, new_call_log_id, attempt_count,
                   max_attempts, last_error, created_at, updated_at
            FROM callback_requests
            WHERE id = $1
        """
        
        async with self.db.acquire() as conn:
            result = await conn.fetchrow(query, callback_id)
        
        return dict(result) if result else None
