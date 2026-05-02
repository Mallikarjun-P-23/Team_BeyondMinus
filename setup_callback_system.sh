#!/bin/bash

# Quick Start Script for Automatic Callback System
# Run this to set up and test the callback feature

set -e  # Exit on error

echo "=========================================="
echo "Automatic Callback System - Quick Start"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "backend/migrations/018_create_callback_requests.sql" ]; then
    echo "❌ Error: Please run this script from the HF26-44 directory"
    exit 1
fi

# Step 1: Check database connection
echo "📊 Step 1: Checking database connection..."
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable is not set"
    echo "   Set it with: export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    exit 1
fi
echo "✅ Database URL configured"
echo ""

# Step 2: Run migration
echo "📁 Step 2: Running database migration..."
echo "   Executing: 018_create_callback_requests.sql"
psql "$DATABASE_URL" -f backend/migrations/018_create_callback_requests.sql
if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully"
else
    echo "❌ Migration failed"
    exit 1
fi
echo ""

# Step 3: Verify table creation
echo "🔍 Step 3: Verifying callback_requests table..."
TABLE_EXISTS=$(psql "$DATABASE_URL" -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'callback_requests');")
if [ "$TABLE_EXISTS" = "t" ]; then
    echo "✅ callback_requests table created"
    # Show table structure
    echo ""
    echo "   Table structure:"
    psql "$DATABASE_URL" -c "\d callback_requests" | head -20
else
    echo "❌ Table creation failed"
    exit 1
fi
echo ""

# Step 4: Check Python dependencies
echo "🐍 Step 4: Checking Python dependencies..."
cd backend
if python -c "import asyncpg" 2>/dev/null; then
    echo "✅ asyncpg installed"
else
    echo "⚠️  asyncpg not found - installing..."
    pip install asyncpg
fi

if python -c "import asyncio" 2>/dev/null; then
    echo "✅ asyncio available"
fi
cd ..
echo ""

# Step 5: Show callback worker status
echo "🔧 Step 5: Callback worker status..."
WORKER_PID=$(ps aux | grep '[c]allback_worker.py' | awk '{print $2}')
if [ -z "$WORKER_PID" ]; then
    echo "⚠️  Callback worker is not running"
    echo ""
    echo "   To start the worker, run:"
    echo "   cd backend && python callback_worker.py"
    echo ""
    echo "   Or in a separate terminal:"
    echo "   cd backend && nohup python callback_worker.py > callback_worker.log 2>&1 &"
else
    echo "✅ Callback worker is running (PID: $WORKER_PID)"
fi
echo ""

# Step 6: Test query
echo "📊 Step 6: Testing callback requests table..."
CALLBACK_COUNT=$(psql "$DATABASE_URL" -tAc "SELECT COUNT(*) FROM callback_requests;")
echo "   Current callback requests: $CALLBACK_COUNT"
echo ""

# Step 7: Show integration status
echo "🔗 Step 7: Integration checklist..."
echo ""
echo "   [ ] Add imports to backend/app/api/endpoints.py"
echo "       from app.api.callback_helper import trigger_callback_if_disconnected"
echo "       from app.services.callback_service import CallbackService"
echo ""
echo "   [ ] Add callback trigger in elevenlabs_webhook() function"
echo "       See: CALLBACK_INTEGRATION_SNIPPET.py for exact code"
echo ""
echo "   [ ] Start callback worker"
echo "       cd backend && python callback_worker.py"
echo ""
echo "   [ ] Test with a disconnected call"
echo ""

# Final summary
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📚 Next Steps:"
echo "   1. Review: AUTOMATIC_CALLBACK_SYSTEM.md for detailed documentation"
echo "   2. Integrate: Follow steps in CALLBACK_INTEGRATION_SNIPPET.py"
echo "   3. Start worker: cd backend && python callback_worker.py"
echo "   4. Test: Simulate a call disconnection"
echo ""
echo "📊 Monitor callbacks:"
echo "   psql \$DATABASE_URL -c \"SELECT * FROM callback_requests ORDER BY created_at DESC LIMIT 10;\""
echo ""
echo "🔍 Check worker logs:"
echo "   tail -f backend/callback_worker.log"
echo ""

# Optional: Show sample callback data
echo "📝 Sample Callback Request Query:"
echo "   SELECT id, patient_phone, status, trigger_type,"
echo "          scheduled_callback_at, attempt_count"
echo "   FROM callback_requests"
echo "   WHERE status = 'scheduled'"
echo "   ORDER BY priority DESC, scheduled_callback_at ASC;"
echo ""

exit 0
