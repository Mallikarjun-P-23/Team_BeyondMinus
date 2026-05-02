"""
Rejection Logger Service
Logs all LLM rejections to a universal text file for developer review
"""
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

# Universal rejection log file
REJECTION_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
REJECTION_LOG_FILE = REJECTION_LOG_DIR / "workflow_rejections.txt"


def ensure_log_directory():
    """Ensure the logs directory exists"""
    REJECTION_LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_workflow_rejection(
    *,
    doctor_id: Optional[str] = None,
    user_prompt: str,
    rejection_reason: str,
    rejection_message: str,
    missing_context: list[str] = None,
    clarification_turns: int = 0,
    additional_info: Optional[Dict[str, Any]] = None
) -> str:
    """
    Log a workflow rejection to the universal text file
    
    Args:
        doctor_id: The doctor who attempted to create the workflow
        user_prompt: The original prompt/input from the user
        rejection_reason: Technical reason for rejection
        rejection_message: User-facing rejection message
        missing_context: List of missing context items
        clarification_turns: Number of clarification attempts made
        additional_info: Any additional metadata to log
    
    Returns:
        The rejection log entry ID (timestamp-based)
    """
    ensure_log_directory()
    
    timestamp = datetime.now(timezone.utc)
    rejection_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")
    
    # Format the log entry
    separator = "=" * 80
    log_entry = f"\n{separator}\n"
    log_entry += f"🚫 WORKFLOW GENERATION REJECTED\n"
    log_entry += f"{separator}\n"
    log_entry += f"Rejection ID: {rejection_id}\n"
    log_entry += f"Timestamp: {timestamp.isoformat()}\n"
    log_entry += f"Doctor ID: {doctor_id or 'N/A'}\n"
    log_entry += f"Clarification Turns: {clarification_turns}\n"
    log_entry += f"\n--- USER PROMPT ---\n"
    log_entry += f"{user_prompt}\n"
    log_entry += f"\n--- REJECTION REASON (Technical) ---\n"
    log_entry += f"{rejection_reason}\n"
    log_entry += f"\n--- REJECTION MESSAGE (User-Facing) ---\n"
    log_entry += f"{rejection_message}\n"
    
    if missing_context:
        log_entry += f"\n--- MISSING CONTEXT ---\n"
        for item in missing_context:
            log_entry += f"  • {item}\n"
    
    if additional_info:
        log_entry += f"\n--- ADDITIONAL INFO ---\n"
        log_entry += json.dumps(additional_info, indent=2)
        log_entry += "\n"
    
    log_entry += f"{separator}\n\n"
    
    try:
        # Append to the universal log file
        with open(REJECTION_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        logger.info(f"Logged workflow rejection {rejection_id} to {REJECTION_LOG_FILE}")
        
        # Also log to console for immediate developer visibility
        print("\n" + "!" * 80)
        print("🚫 WORKFLOW REJECTION LOGGED")
        print("!" * 80)
        print(f"Rejection ID: {rejection_id}")
        print(f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Doctor: {doctor_id or 'Unknown'}")
        print(f"Prompt: {user_prompt[:100]}{'...' if len(user_prompt) > 100 else ''}")
        print(f"Reason: {rejection_reason}")
        print(f"Log file: {REJECTION_LOG_FILE}")
        print("!" * 80 + "\n")
        
        return rejection_id
        
    except Exception as e:
        logger.error(f"Failed to write rejection log: {e}")
        # Print to console as fallback
        print(f"\n⚠️  FAILED TO LOG REJECTION: {e}")
        print(log_entry)
        return rejection_id


def get_rejection_stats() -> Dict[str, Any]:
    """
    Get statistics about workflow rejections
    
    Returns:
        Dictionary with rejection statistics
    """
    if not REJECTION_LOG_FILE.exists():
        return {
            "total_rejections": 0,
            "log_file": str(REJECTION_LOG_FILE),
            "log_exists": False
        }
    
    try:
        with open(REJECTION_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Count rejection entries
        rejection_count = content.count("🚫 WORKFLOW GENERATION REJECTED")
        
        # Get file size
        file_size = REJECTION_LOG_FILE.stat().st_size
        
        return {
            "total_rejections": rejection_count,
            "log_file": str(REJECTION_LOG_FILE),
            "log_exists": True,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Failed to read rejection stats: {e}")
        return {
            "total_rejections": 0,
            "log_file": str(REJECTION_LOG_FILE),
            "log_exists": False,
            "error": str(e)
        }


def get_recent_rejections(limit: int = 10) -> list[str]:
    """
    Get the most recent rejection entries
    
    Args:
        limit: Maximum number of rejections to return
    
    Returns:
        List of recent rejection log entries
    """
    if not REJECTION_LOG_FILE.exists():
        return []
    
    try:
        with open(REJECTION_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split by separator
        entries = content.split("=" * 80)
        
        # Filter out empty entries and get last N
        valid_entries = [e.strip() for e in entries if "WORKFLOW GENERATION REJECTED" in e]
        
        return valid_entries[-limit:][::-1]  # Reverse to show most recent first
        
    except Exception as e:
        logger.error(f"Failed to read recent rejections: {e}")
        return []
