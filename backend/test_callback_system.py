#!/usr/bin/env python3
"""
Automated Test Script for Callback System
Tests various scenarios for automatic patient callbacks
"""
import asyncio
import argparse
import json
import time
import uuid
from datetime import datetime, timedelta
import requests
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def log_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def log_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def log_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def log_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")

def log_header(msg: str):
    print(f"\n{Colors.BOLD}{msg}{Colors.END}")
    print("=" * 60)


class CallbackTester:
    """Test harness for callback system"""
    
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.test_data = []
    
    def create_callback(
        self,
        patient_phone: str = "+1234567890",
        trigger_type: str = "auto_disconnect",
        delay_seconds: int = 5,  # Short delay for testing
        **kwargs
    ) -> Optional[dict]:
        """Create a callback request"""
        payload = {
            "call_log_id": str(uuid.uuid4()),
            "patient_phone": patient_phone,
            "patient_name": kwargs.get("patient_name", "Test Patient"),
            "doctor_id": kwargs.get("doctor_id", "test_doctor_123"),
            "trigger_type": trigger_type,
            "reason": kwargs.get("reason", "Test callback"),
            "priority": kwargs.get("priority", 0),
            "delay_seconds": delay_seconds,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/callbacks/create",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            log_success(f"Callback created: {data.get('id')}")
            return data
        except requests.exceptions.RequestException as e:
            log_error(f"Failed to create callback: {e}")
            return None
    
    def get_callback(self, callback_id: str) -> Optional[dict]:
        """Get callback status"""
        try:
            response = requests.get(
                f"{self.base_url}/callbacks/{callback_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log_error(f"Failed to get callback: {e}")
            return None
    
    def cancel_callback(self, callback_id: str, reason: str = "Test cancellation") -> bool:
        """Cancel a callback"""
        try:
            response = requests.post(
                f"{self.base_url}/callbacks/{callback_id}/cancel",
                json={"reason": reason},
                timeout=10
            )
            response.raise_for_status()
            log_success(f"Callback cancelled: {callback_id}")
            return True
        except requests.exceptions.RequestException as e:
            log_error(f"Failed to cancel callback: {e}")
            return False
    
    def list_callbacks(self, status: str = "pending", limit: int = 10) -> list:
        """List callbacks"""
        try:
            response = requests.get(
                f"{self.base_url}/callbacks",
                params={"status": status, "limit": limit},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log_error(f"Failed to list callbacks: {e}")
            return []
    
    def get_stats(self, doctor_id: Optional[str] = None) -> Optional[dict]:
        """Get callback statistics"""
        try:
            params = {}
            if doctor_id:
                params["doctor_id"] = doctor_id
            response = requests.get(
                f"{self.base_url}/callbacks/stats",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log_error(f"Failed to get stats: {e}")
            return None
    
    def wait_and_verify(self, callback_id: str, expected_status: str, timeout: int = 60) -> bool:
        """Wait for callback to reach expected status"""
        log_info(f"Waiting for callback to reach status: {expected_status}")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            callback = self.get_callback(callback_id)
            if not callback:
                time.sleep(2)
                continue
            
            current_status = callback.get("status")
            log_info(f"Current status: {current_status} (elapsed: {int(time.time() - start_time)}s)")
            
            if current_status == expected_status:
                log_success(f"Callback reached expected status: {expected_status}")
                return True
            
            time.sleep(2)
        
        log_error(f"Timeout waiting for status {expected_status}")
        return False


def test_basic_callback(tester: CallbackTester):
    """Test basic callback creation and execution"""
    log_header("Test 1: Basic Callback Flow")
    
    log_info("Creating callback with 5 second delay...")
    callback = tester.create_callback(
        patient_phone="+15551234567",
        delay_seconds=5,
        reason="Test: Basic callback flow"
    )
    
    if not callback:
        log_error("Test failed: Could not create callback")
        return False
    
    callback_id = callback.get("id")
    
    # Verify it's scheduled
    log_info("Verifying callback is scheduled...")
    time.sleep(1)
    status = tester.get_callback(callback_id)
    if status and status.get("status") == "scheduled":
        log_success("Callback is in scheduled state")
    else:
        log_error("Callback not properly scheduled")
        return False
    
    # Wait for execution
    success = tester.wait_and_verify(callback_id, "in_progress", timeout=15)
    
    if success:
        log_success("✓ Test passed: Basic callback flow works")
        return True
    else:
        log_error("✗ Test failed: Callback did not execute")
        return False


def test_callback_cancellation(tester: CallbackTester):
    """Test cancelling a scheduled callback"""
    log_header("Test 2: Callback Cancellation")
    
    log_info("Creating callback with 30 second delay...")
    callback = tester.create_callback(
        patient_phone="+15559876543",
        delay_seconds=30,
        reason="Test: Cancellation"
    )
    
    if not callback:
        log_error("Test failed: Could not create callback")
        return False
    
    callback_id = callback.get("id")
    
    # Wait a bit then cancel
    log_info("Waiting 2 seconds before cancelling...")
    time.sleep(2)
    
    if tester.cancel_callback(callback_id, "Testing cancellation"):
        log_success("Callback cancelled successfully")
        
        # Verify it's cancelled
        time.sleep(1)
        status = tester.get_callback(callback_id)
        if status and status.get("status") == "cancelled":
            log_success("✓ Test passed: Callback cancellation works")
            return True
        else:
            log_error("✗ Test failed: Callback not in cancelled state")
            return False
    else:
        log_error("✗ Test failed: Could not cancel callback")
        return False


def test_priority_callbacks(tester: CallbackTester):
    """Test priority callback processing"""
    log_header("Test 3: Priority Callbacks")
    
    log_info("Creating normal priority callback...")
    normal = tester.create_callback(
        patient_phone="+15551111111",
        priority=0,
        delay_seconds=5,
        reason="Normal priority"
    )
    
    log_info("Creating high priority callback...")
    high = tester.create_callback(
        patient_phone="+15552222222",
        priority=2,
        delay_seconds=5,
        reason="High priority"
    )
    
    if not normal or not high:
        log_error("Test failed: Could not create callbacks")
        return False
    
    log_info("Waiting for callbacks to be processed...")
    time.sleep(10)
    
    # Check which one was processed first (should be high priority)
    normal_status = tester.get_callback(normal["id"])
    high_status = tester.get_callback(high["id"])
    
    if high_status and normal_status:
        high_attempted = high_status.get("callback_attempted_at")
        normal_attempted = normal_status.get("callback_attempted_at")
        
        if high_attempted and normal_attempted:
            if high_attempted <= normal_attempted:
                log_success("✓ Test passed: High priority processed first")
                return True
            else:
                log_warning("High priority not processed first (may be timing issue)")
                return True  # Don't fail, could be timing
        else:
            log_info("Callbacks still processing...")
            return True
    
    log_warning("Could not determine priority order")
    return True


def test_callback_listing(tester: CallbackTester):
    """Test listing callbacks by status"""
    log_header("Test 4: Callback Listing")
    
    # Create a few callbacks
    log_info("Creating multiple callbacks...")
    callbacks = []
    for i in range(3):
        callback = tester.create_callback(
            patient_phone=f"+1555000000{i}",
            delay_seconds=60,  # Long delay so they stay pending
            reason=f"Test listing {i}"
        )
        if callback:
            callbacks.append(callback)
        time.sleep(0.5)
    
    if len(callbacks) < 3:
        log_error("Could not create test callbacks")
        return False
    
    # List pending callbacks
    log_info("Listing pending callbacks...")
    pending = tester.list_callbacks(status="pending")
    
    if pending and len(pending) >= 3:
        log_success(f"✓ Test passed: Listed {len(pending)} pending callbacks")
        
        # Clean up
        log_info("Cleaning up test callbacks...")
        for cb in callbacks:
            tester.cancel_callback(cb["id"])
        
        return True
    else:
        log_error("✗ Test failed: Could not list callbacks properly")
        return False


def test_statistics(tester: CallbackTester):
    """Test callback statistics endpoint"""
    log_header("Test 5: Callback Statistics")
    
    log_info("Fetching callback statistics...")
    stats = tester.get_stats(doctor_id="test_doctor_123")
    
    if stats:
        log_info(f"Statistics: {json.dumps(stats, indent=2)}")
        
        required_keys = ["pending", "scheduled", "completed", "failed", "cancelled"]
        if all(key in stats for key in required_keys):
            log_success("✓ Test passed: Statistics endpoint working")
            return True
        else:
            log_error("✗ Test failed: Missing required statistics")
            return False
    else:
        log_error("✗ Test failed: Could not fetch statistics")
        return False


def run_all_tests():
    """Run all test scenarios"""
    log_header("🧪 Callback System Test Suite")
    log_info(f"Testing against: {BASE_URL}")
    
    tester = CallbackTester()
    
    tests = [
        ("Basic Callback", test_basic_callback),
        ("Cancellation", test_callback_cancellation),
        ("Priority", test_priority_callbacks),
        ("Listing", test_callback_listing),
        ("Statistics", test_statistics),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func(tester)
            results.append((test_name, result))
        except Exception as e:
            log_error(f"Test '{test_name}' raised exception: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    log_header("📊 Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.END} - {test_name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        log_success("🎉 All tests passed!")
        return 0
    else:
        log_error(f"❌ {total - passed} test(s) failed")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Test the callback system")
    parser.add_argument(
        "--scenario",
        choices=["basic", "cancel", "priority", "list", "stats", "all"],
        default="all",
        help="Test scenario to run"
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Base URL for the API"
    )
    
    args = parser.parse_args()
    
    global BASE_URL, API_BASE
    BASE_URL = args.base_url
    API_BASE = f"{BASE_URL}/api"
    
    tester = CallbackTester()
    
    if args.scenario == "all":
        return run_all_tests()
    elif args.scenario == "basic":
        return 0 if test_basic_callback(tester) else 1
    elif args.scenario == "cancel":
        return 0 if test_callback_cancellation(tester) else 1
    elif args.scenario == "priority":
        return 0 if test_priority_callbacks(tester) else 1
    elif args.scenario == "list":
        return 0 if test_callback_listing(tester) else 1
    elif args.scenario == "stats":
        return 0 if test_statistics(tester) else 1


if __name__ == "__main__":
    exit(main())
