"""
System Observer Agent - Monitors entire system and reports errors
"""
import asyncio
import logging
import traceback
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SeverityLevel(str, Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories of errors"""
    DATABASE = "database"
    API = "api"
    ELEVENLABS = "elevenlabs"
    TWILIO = "twilio"
    WORKFLOW = "workflow"
    CALLBACK = "callback"
    WEBHOOK = "webhook"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class SystemError:
    """Structured error information"""
    
    def __init__(
        self,
        error_id: str,
        category: ErrorCategory,
        severity: SeverityLevel,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.error_id = error_id
        self.category = category
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.stack_trace = stack_trace
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class ObserverAgent:
    """
    System Observer Agent
    Monitors all system operations and reports errors in real-time
    """
    
    def __init__(self, db_connection=None, smtp_service=None):
        self.db = db_connection
        self.smtp = smtp_service
        self.error_buffer: List[SystemError] = []
        self.max_buffer_size = 100
        self.alert_threshold = {
            SeverityLevel.CRITICAL: 1,  # Alert immediately
            SeverityLevel.ERROR: 3,      # Alert after 3 errors
            SeverityLevel.WARNING: 10    # Alert after 10 warnings
        }
        self.error_counts = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.ERROR: 0,
            SeverityLevel.WARNING: 0
        }
        self.monitoring_active = True
        self.websocket_manager = None  # Will be set by monitoring_websocket
    
    def generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid
        return f"ERR-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    
    def detect_error_category(self, error: Exception, context: Dict[str, Any]) -> ErrorCategory:
        """Auto-detect error category from exception and context"""
        error_str = str(error).lower()
        
        # Check context first
        if "elevenlabs" in str(context).lower():
            return ErrorCategory.ELEVENLABS
        if "twilio" in str(context).lower():
            return ErrorCategory.TWILIO
        if "callback" in str(context).lower():
            return ErrorCategory.CALLBACK
        if "workflow" in str(context).lower():
            return ErrorCategory.WORKFLOW
        
        # Check error message
        if "database" in error_str or "psycopg" in error_str or "sql" in error_str:
            return ErrorCategory.DATABASE
        if "api" in error_str or "request" in error_str or "http" in error_str:
            return ErrorCategory.API
        if "elevenlabs" in error_str or "agent" in error_str:
            return ErrorCategory.ELEVENLABS
        if "twilio" in error_str or "phone" in error_str:
            return ErrorCategory.TWILIO
        if "auth" in error_str or "token" in error_str or "permission" in error_str:
            return ErrorCategory.AUTHENTICATION
        if "validation" in error_str or "invalid" in error_str:
            return ErrorCategory.VALIDATION
        
        return ErrorCategory.UNKNOWN
    
    def detect_severity(self, error: Exception, category: ErrorCategory) -> SeverityLevel:
        """Auto-detect severity level"""
        error_str = str(error).lower()
        
        # Critical conditions
        if category == ErrorCategory.DATABASE:
            return SeverityLevel.CRITICAL
        if "credit" in error_str or "quota" in error_str or "limit exceeded" in error_str:
            return SeverityLevel.CRITICAL
        if "connection refused" in error_str or "timeout" in error_str:
            return SeverityLevel.ERROR
        if "not found" in error_str or "404" in error_str:
            return SeverityLevel.WARNING
        if "unauthorized" in error_str or "401" in error_str or "403" in error_str:
            return SeverityLevel.ERROR
        
        # Default to ERROR for exceptions
        if isinstance(error, Exception):
            return SeverityLevel.ERROR
        
        return SeverityLevel.WARNING
    
    async def capture_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[SeverityLevel] = None
    ) -> SystemError:
        """
        Capture and process an error
        
        Args:
            error: The exception that occurred
            context: Additional context (function name, user, etc)
            category: Override auto-detection of category
            severity: Override auto-detection of severity
        
        Returns:
            SystemError object
        """
        context = context or {}
        
        # Auto-detect if not provided
        if category is None:
            category = self.detect_error_category(error, context)
        if severity is None:
            severity = self.detect_severity(error, category)
        
        # Create error object
        system_error = SystemError(
            error_id=self.generate_error_id(),
            category=category,
            severity=severity,
            message=str(error),
            details={
                "error_type": type(error).__name__,
                "error_module": type(error).__module__
            },
            stack_trace=traceback.format_exc(),
            context=context
        )
        
        # Log the error
        self._log_error(system_error)
        
        # Store in buffer
        self.error_buffer.append(system_error)
        if len(self.error_buffer) > self.max_buffer_size:
            self.error_buffer.pop(0)
        
        # Update counts
        if severity in self.error_counts:
            self.error_counts[severity] += 1
        
        # Store in database
        await self._store_error_in_db(system_error)
        
        # Broadcast to WebSocket clients
        await self._broadcast_error(system_error)
        
        # Check if we should alert
        await self._check_alert_threshold(system_error)
        
        return system_error
    
    def _log_error(self, error: SystemError):
        """Log error to console with formatting"""
        separator = "=" * 80
        
        # Color codes for terminal
        colors = {
            SeverityLevel.CRITICAL: "\033[91m",  # Red
            SeverityLevel.ERROR: "\033[91m",      # Red
            SeverityLevel.WARNING: "\033[93m",    # Yellow
            SeverityLevel.INFO: "\033[94m",       # Blue
            SeverityLevel.DEBUG: "\033[90m"       # Gray
        }
        reset = "\033[0m"
        
        color = colors.get(error.severity, "")
        
        # Print formatted error
        print(f"\n{color}{separator}{reset}")
        print(f"{color}🚨 SYSTEM ERROR DETECTED 🚨{reset}")
        print(f"{color}{separator}{reset}")
        print(f"{color}Error ID:{reset} {error.error_id}")
        print(f"{color}Severity:{reset} {error.severity.value.upper()}")
        print(f"{color}Category:{reset} {error.category.value}")
        print(f"{color}Timestamp:{reset} {error.timestamp.isoformat()}")
        print(f"{color}Message:{reset} {error.message}")
        
        if error.context:
            print(f"\n{color}Context:{reset}")
            for key, value in error.context.items():
                print(f"  • {key}: {value}")
        
        if error.details:
            print(f"\n{color}Details:{reset}")
            for key, value in error.details.items():
                print(f"  • {key}: {value}")
        
        if error.stack_trace and error.severity in [SeverityLevel.CRITICAL, SeverityLevel.ERROR]:
            print(f"\n{color}Stack Trace:{reset}")
            print(error.stack_trace)
        
        print(f"{color}{separator}{reset}\n")
        
        # Also use standard logger
        log_method = {
            SeverityLevel.CRITICAL: logger.critical,
            SeverityLevel.ERROR: logger.error,
            SeverityLevel.WARNING: logger.warning,
            SeverityLevel.INFO: logger.info,
            SeverityLevel.DEBUG: logger.debug
        }.get(error.severity, logger.error)
        
        log_method(
            f"[{error.category.value.upper()}] {error.message}",
            extra={"error_id": error.error_id, "context": error.context}
        )
    
    async def _store_error_in_db(self, error: SystemError):
        """Store error in database for persistence"""
        if not self.db:
            return
        
        try:
            query = """
                INSERT INTO system_errors 
                (error_id, category, severity, message, details, stack_trace, context, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            await self.db.execute(
                query,
                error.error_id,
                error.category.value,
                error.severity.value,
                error.message,
                json.dumps(error.details),
                error.stack_trace,
                json.dumps(error.context),
                error.timestamp
            )
        except Exception as e:
            logger.error(f"Failed to store error in database: {e}")
    
    async def _check_alert_threshold(self, error: SystemError):
        """Check if alert threshold reached and send notifications"""
        severity = error.severity
        
        if severity not in self.alert_threshold:
            return
        
        threshold = self.alert_threshold[severity]
        count = self.error_counts[severity]
        
        if count >= threshold:
            await self._send_developer_alert(error)
            # Reset count after alert
            self.error_counts[severity] = 0
    
    async def _send_developer_alert(self, error: SystemError):
        """Send alert to developers"""
        try:
            # Console alert (always)
            print("\n" + "!" * 80)
            print("⚠️  DEVELOPER ALERT - ERROR THRESHOLD REACHED ⚠️")
            print("!" * 80)
            print(f"Error ID: {error.error_id}")
            print(f"Severity: {error.severity.value.upper()}")
            print(f"Category: {error.category.value}")
            print(f"Count: {self.error_counts[error.severity]} errors")
            print("!" * 80 + "\n")
            
            # Email alert (if configured)
            if self.smtp:
                await self._send_email_alert(error)
            
            # Slack/Discord webhook (if configured)
            # await self._send_webhook_alert(error)
            
        except Exception as e:
            logger.error(f"Failed to send developer alert: {e}")
    
    async def _broadcast_error(self, error: SystemError):
        """Broadcast error to WebSocket clients"""
        if self.websocket_manager:
            try:
                await self.websocket_manager.broadcast_error(error)
            except Exception as e:
                logger.error(f"Failed to broadcast error to WebSocket clients: {e}")
    
    def set_websocket_manager(self, manager):
        """Set the WebSocket connection manager for real-time broadcasting"""
        self.websocket_manager = manager
        logger.info("WebSocket manager connected to Observer Agent")
