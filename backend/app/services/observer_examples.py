"""
Observer Integration Examples
Shows how to use the Observer Agent to monitor different parts of your system
"""
import asyncio
from functools import wraps
from app.services.observer_agent import get_observer, ErrorCategory


# ==============================================================================
# DECORATOR METHOD - Easy way to monitor any function
# ==============================================================================

def monitor_with_observer(category: ErrorCategory = ErrorCategory.UNKNOWN):
    """
    Decorator to automatically monitor function execution
    
    Usage:
        @monitor_with_observer(category=ErrorCategory.ELEVENLABS)
        async def make_elevenlabs_call(phone: str):
            # Your code here
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            observer = get_observer()
            context = {
                "function": func.__name__,
                "module": func.__module__,
            }
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await observer.capture_error(e, context=context, category=category)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            observer = get_observer()
            context = {
                "function": func.__name__,
                "module": func.__module__,
            }
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # For sync functions, we need to handle async capture
                asyncio.create_task(observer.capture_error(e, context=context, category=category))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# ==============================================================================
# CONTEXT MANAGER METHOD - For specific code blocks
# ==============================================================================

class ObserverContext:
    """
    Context manager for monitoring code blocks
    
    Usage:
        async with ObserverContext(ErrorCategory.DATABASE, {"operation": "insert"}):
            await db.execute(query)
    """
    def __init__(self, category: ErrorCategory, context: dict = None):
        self.category = category
        self.context = context or {}
        self.observer = get_observer()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            await self.observer.capture_error(
                exc_val, 
                context=self.context, 
                category=self.category
            )
        return False  # Don't suppress exception


# ==============================================================================
# MANUAL MONITORING - Explicit error capture
# ==============================================================================

async def monitor_elevenlabs_call(func, *args, **kwargs):
    """Example: Monitor ElevenLabs API calls"""
    observer = get_observer()
    context = {
        "service": "elevenlabs",
        "operation": func.__name__,
        "args_provided": len(args) > 0
    }
    
    try:
        result = await func(*args, **kwargs)
        return result
    except Exception as e:
        # Check for specific ElevenLabs errors
        error_str = str(e).lower()
        if "credit" in error_str or "quota" in error_str:
            context["error_type"] = "credit_exhausted"
            context["critical_alert"] = True
        elif "unauthorized" in error_str:
            context["error_type"] = "authentication_failed"
        elif "rate limit" in error_str:
            context["error_type"] = "rate_limited"
        
        await observer.capture_error(e, context=context, category=ErrorCategory.ELEVENLABS)
        raise


async def monitor_database_operation(func, *args, **kwargs):
    """Example: Monitor database operations"""
    observer = get_observer()
    context = {
        "service": "database",
        "operation": func.__name__
    }
    
    try:
        result = await func(*args, **kwargs)
        return result
    except Exception as e:
        # Database errors are always critical
        await observer.capture_error(
            e, 
            context=context, 
            category=ErrorCategory.DATABASE
        )
        raise


async def monitor_callback_system(func, *args, **kwargs):
    """Example: Monitor callback system"""
    observer = get_observer()
    context = {
        "service": "callback",
        "operation": func.__name__
    }
    
    try:
        result = await func(*args, **kwargs)
        return result
    except Exception as e:
        await observer.capture_error(e, context=context, category=ErrorCategory.CALLBACK)
        raise


# ==============================================================================
# INTEGRATION EXAMPLES
# ==============================================================================

# Example 1: Using decorator on ElevenLabs function
@monitor_with_observer(category=ErrorCategory.ELEVENLABS)
async def make_elevenlabs_call(agent_id: str, phone: str):
    """This function is automatically monitored"""
    # Your ElevenLabs call code here
    pass


# Example 2: Using context manager
async def process_callback_request(callback_id: str):
    """Monitor a specific code block"""
    async with ObserverContext(
        ErrorCategory.CALLBACK, 
        {"callback_id": callback_id}
    ):
        # Your callback processing code
        pass


# Example 3: Manual monitoring with custom context
async def execute_workflow_with_monitoring(workflow_id: str, patient_id: str):
    """Explicitly monitor with rich context"""
    observer = get_observer()
    
    context = {
        "workflow_id": workflow_id,
        "patient_id": patient_id,
        "operation": "execute_workflow",
        "timestamp": "2026-05-03T10:30:00Z"
    }
    
    try:
        # Your workflow execution code
        result = await execute_workflow(workflow_id, patient_id)
        return result
    except Exception as e:
        await observer.capture_error(e, context=context, category=ErrorCategory.WORKFLOW)
        raise


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

async def check_elevenlabs_credits():
    """
    Proactively check ElevenLabs credits and alert if low
    Call this periodically to monitor credit status
    """
    observer = get_observer()
    
    try:
        # Check credits API (implement based on your setup)
        # credits_remaining = await elevenlabs_api.get_credits()
        
        credits_remaining = 100  # Example
        
        if credits_remaining < 50:
            # Create a warning
            await observer.capture_error(
                Exception(f"ElevenLabs credits low: {credits_remaining} remaining"),
                context={
                    "credits_remaining": credits_remaining,
                    "warning_type": "low_credits",
                    "service": "elevenlabs"
                },
                category=ErrorCategory.ELEVENLABS
            )
    except Exception as e:
        await observer.capture_error(e, category=ErrorCategory.ELEVENLABS)


async def monitor_system_resources():
    """
    Monitor system resources (CPU, memory, etc.)
    Call this periodically
    """
    import psutil
    observer = get_observer()
    
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 90:
            await observer.capture_error(
                Exception(f"High CPU usage: {cpu_percent}%"),
                context={"cpu_percent": cpu_percent, "alert_type": "high_cpu"},
                category=ErrorCategory.SYSTEM
            )
        
        if memory_percent > 90:
            await observer.capture_error(
                Exception(f"High memory usage: {memory_percent}%"),
                context={"memory_percent": memory_percent, "alert_type": "high_memory"},
                category=ErrorCategory.SYSTEM
            )
    except Exception as e:
        await observer.capture_error(e, category=ErrorCategory.SYSTEM)
