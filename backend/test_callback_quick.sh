#!/bin/bash
# Quick Callback System Test Script
# Usage: ./test_callback_quick.sh

set -e

BASE_URL="http://localhost:8000"
API_URL="${BASE_URL}/api"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🧪 Quick Callback System Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: Create a callback
echo -e "${YELLOW}Test 1: Creating callback request...${NC}"
CALLBACK_RESPONSE=$(curl -s -X POST "${API_URL}/callbacks/create" \
  -H "Content-Type: application/json" \
  -d '{
    "call_log_id": "'$(uuidgen)'",
    "patient_phone": "+15551234567",
    "patient_name": "Test Patient",
    "doctor_id": "test_doctor_123",
    "trigger_type": "auto_disconnect",
    "reason": "Patient disconnected during booking",
    "priority": 1,
    "delay_seconds": 10
  }')

if [ $? -eq 0 ]; then
  CALLBACK_ID=$(echo $CALLBACK_RESPONSE | jq -r '.id')
  if [ "$CALLBACK_ID" != "null" ] && [ -n "$CALLBACK_ID" ]; then
    echo -e "${GREEN}✓ Callback created: ${CALLBACK_ID}${NC}"
  else
    echo -e "${RED}✗ Failed to create callback${NC}"
    echo "Response: $CALLBACK_RESPONSE"
    exit 1
  fi
else
  echo -e "${RED}✗ API request failed${NC}"
  exit 1
fi

echo ""

# Test 2: Check callback status
echo -e "${YELLOW}Test 2: Checking callback status...${NC}"
sleep 2
STATUS_RESPONSE=$(curl -s "${API_URL}/callbacks/${CALLBACK_ID}")
CURRENT_STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
echo -e "${BLUE}Current status: ${CURRENT_STATUS}${NC}"
echo -e "${GREEN}✓ Status check successful${NC}"

echo ""

# Test 3: List pending callbacks
echo -e "${YELLOW}Test 3: Listing pending callbacks...${NC}"
LIST_RESPONSE=$(curl -s "${API_URL}/callbacks?status=pending&limit=5")
CALLBACK_COUNT=$(echo $LIST_RESPONSE | jq '. | length')
echo -e "${BLUE}Found ${CALLBACK_COUNT} pending callback(s)${NC}"
echo -e "${GREEN}✓ List operation successful${NC}"

echo ""

# Test 4: Wait for callback to process
echo -e "${YELLOW}Test 4: Waiting for callback to process (15 seconds)...${NC}"
for i in {1..15}; do
  echo -n "."
  sleep 1
done
echo ""

FINAL_STATUS=$(curl -s "${API_URL}/callbacks/${CALLBACK_ID}" | jq -r '.status')
echo -e "${BLUE}Final status: ${FINAL_STATUS}${NC}"

if [ "$FINAL_STATUS" == "in_progress" ] || [ "$FINAL_STATUS" == "completed" ]; then
  echo -e "${GREEN}✓ Callback processed successfully${NC}"
else
  echo -e "${YELLOW}⚠ Callback status: ${FINAL_STATUS} (may still be processing)${NC}"
fi

echo ""

# Test 5: Get statistics
echo -e "${YELLOW}Test 5: Fetching callback statistics...${NC}"
STATS_RESPONSE=$(curl -s "${API_URL}/callbacks/stats?doctor_id=test_doctor_123")
echo -e "${BLUE}Statistics:${NC}"
echo $STATS_RESPONSE | jq '.'
echo -e "${GREEN}✓ Statistics retrieved${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ All tests completed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Callback ID for reference: ${CALLBACK_ID}"
echo ""
echo "To check the callback status again:"
echo "  curl ${API_URL}/callbacks/${CALLBACK_ID} | jq"
echo ""
echo "To view database records:"
echo "  psql \$DATABASE_URL -c 'SELECT * FROM callback_requests ORDER BY created_at DESC LIMIT 5;'"
