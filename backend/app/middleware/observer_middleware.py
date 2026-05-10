"""
Observer Middleware - Automatically monitors all requests and catches errors
"""
import time
import traceback
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.services.observer_agent import get_observer, ErrorCategory


class ObserverMiddleware(BaseHTTPMiddleware):
    """
    Middleware that monitors all HTTP requests and automatically
    captures errors for the Observer Agent
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.observer = get_observer()
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Build context
        context = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log slow requests as warnings
            if duration > 5.0:  # 5 seconds threshold
                print(f"⚠️  Slow request detected: {request.url.path} took {duration:.2f}s")
                context["duration_seconds"] = duration
                context["warning"] = "slow_request"
            
            return response
            
        except Exception as e:
            # Capture error
            context["duration_seconds"] = time.time() - start_time
            context["endpoint"] = request.url.path
            
            # Determine category from path
            category = ErrorCategory.API
            if "/elevenlabs" in request.url.path or "/conversations" in request.url.path:
                category = ErrorCategory.ELEVENLABS
            elif "/callbacks" in request.url.path:
                category = ErrorCategory.CALLBACK
            elif "/workflows" in request.url.path:
                category = ErrorCategory.WORKFLOW
            elif "/auth" in request.url.path:
                category = ErrorCategory.AUTHENTICATION
            
            # Capture with observer
            await self.observer.capture_error(e, context=context, category=category)
            
            # Re-raise to let FastAPI handle it
            raise
