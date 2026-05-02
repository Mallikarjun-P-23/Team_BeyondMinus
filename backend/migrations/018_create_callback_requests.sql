-- ============================================================
-- Migration 018: Callback Requests Table
-- ============================================================
-- Tracks patient requests for callbacks when they cannot
-- complete appointment booking during the initial call.
-- Safe to re-run using IF NOT EXISTS semantics.
-- ============================================================

CREATE TABLE IF NOT EXISTS callback_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_log_id UUID NOT NULL REFERENCES call_logs(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES patients(id) ON DELETE SET NULL,
    doctor_id TEXT,
    patient_phone TEXT NOT NULL,
    patient_name TEXT,
    reason TEXT,
    preferred_callback_time TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    auto_trigger_delay_seconds INTEGER DEFAULT 30,
    scheduled_callback_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    callback_attempted_at TIMESTAMPTZ,
    callback_completed_at TIMESTAMPTZ,
    new_call_log_id UUID REFERENCES call_logs(id) ON DELETE SET NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    CONSTRAINT chk_callback_status CHECK (status IN ('pending', 'scheduled', 'in_progress', 'completed', 'cancelled', 'failed')),
    CONSTRAINT chk_trigger_type CHECK (trigger_type IN ('manual', 'auto_disconnect', 'no_answer', 'interrupted'))
);

CREATE INDEX IF NOT EXISTS idx_callback_requests_status
    ON callback_requests (status, priority DESC, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_callback_requests_doctor
    ON callback_requests (doctor_id, status);

CREATE INDEX IF NOT EXISTS idx_callback_requests_patient
    ON callback_requests (patient_id, status);

CREATE INDEX IF NOT EXISTS idx_callback_requests_call_log
    ON callback_requests (call_log_id);

CREATE INDEX IF NOT EXISTS idx_callback_requests_scheduled
    ON callback_requests (status, scheduled_callback_at) 
    WHERE status = 'scheduled' AND scheduled_callback_at IS NOT NULL;

-- ============================================================
-- Comments
-- ============================================================
COMMENT ON TABLE callback_requests IS 'Tracks patient callback requests when appointment booking cannot be completed immediately';
COMMENT ON COLUMN callback_requests.status IS 'Status: pending, scheduled, in_progress, completed, cancelled, failed';
COMMENT ON COLUMN callback_requests.priority IS 'Priority level (0=normal, 1=high, 2=urgent)';
COMMENT ON COLUMN callback_requests.preferred_callback_time IS 'Patient preferred time for callback (free text or structured)';
COMMENT ON COLUMN callback_requests.trigger_type IS 'Trigger type: manual, auto_disconnect (patient cuts call), no_answer, interrupted';
COMMENT ON COLUMN callback_requests.auto_trigger_delay_seconds IS 'Delay in seconds before triggering auto callback (default 30s)';
COMMENT ON COLUMN callback_requests.scheduled_callback_at IS 'Exact timestamp when callback should be triggered';
COMMENT ON COLUMN callback_requests.new_call_log_id IS 'Reference to the new call initiated for this callback';
