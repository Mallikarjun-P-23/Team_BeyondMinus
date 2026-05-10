-- ============================================================
-- Migration 019: System Error Monitoring Tables
-- ============================================================
-- Creates tables for the Observer Agent to store system errors
-- and monitor application health
-- ============================================================

CREATE TABLE IF NOT EXISTS system_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_id TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    stack_trace TEXT,
    context JSONB DEFAULT '{}'::jsonb,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_severity CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_category CHECK (category IN (
        'database', 'api', 'elevenlabs', 'twilio', 'workflow', 
        'callback', 'webhook', 'authentication', 'validation', 'system', 'unknown'
    ))
);

CREATE TABLE IF NOT EXISTS system_health_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL,
    critical_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_status CHECK (status IN ('healthy', 'warning', 'degraded', 'critical'))
);

CREATE TABLE IF NOT EXISTS developer_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_id TEXT REFERENCES system_errors(error_id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    delivery_status TEXT DEFAULT 'sent',
    delivery_error TEXT,
    CONSTRAINT chk_alert_type CHECK (alert_type IN ('email', 'sms', 'slack', 'webhook'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_system_errors_severity 
    ON system_errors (severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_errors_category 
    ON system_errors (category, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_errors_unresolved 
    ON system_errors (resolved, created_at DESC) 
    WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS idx_system_errors_created 
    ON system_errors (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_snapshots_created 
    ON system_health_snapshots (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_developer_alerts_error 
    ON developer_alerts (error_id, sent_at DESC);

-- Function to auto-create health snapshots
CREATE OR REPLACE FUNCTION record_health_snapshot()
RETURNS void AS $$
DECLARE
    v_critical_count INTEGER;
    v_error_count INTEGER;
    v_warning_count INTEGER;
    v_status TEXT;
BEGIN
    -- Count recent errors (last hour)
    SELECT 
        COUNT(*) FILTER (WHERE severity = 'critical'),
        COUNT(*) FILTER (WHERE severity = 'error'),
        COUNT(*) FILTER (WHERE severity = 'warning')
    INTO v_critical_count, v_error_count, v_warning_count
    FROM system_errors
    WHERE created_at > NOW() - INTERVAL '1 hour';
    
    -- Determine status
    IF v_critical_count > 0 THEN
        v_status := 'critical';
    ELSIF v_error_count > 5 THEN
        v_status := 'degraded';
    ELSIF v_error_count > 0 OR v_warning_count > 10 THEN
        v_status := 'warning';
    ELSE
        v_status := 'healthy';
    END IF;
    
    -- Insert snapshot
    INSERT INTO system_health_snapshots (
        status, critical_count, error_count, warning_count, metrics
    ) VALUES (
        v_status, v_critical_count, v_error_count, v_warning_count,
        jsonb_build_object(
            'total_errors', v_critical_count + v_error_count + v_warning_count,
            'timestamp', NOW()
        )
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Comments for documentation
-- ============================================================
COMMENT ON TABLE system_errors IS 'Stores all system errors captured by Observer Agent';
COMMENT ON TABLE system_health_snapshots IS 'Periodic snapshots of system health status';
COMMENT ON TABLE developer_alerts IS 'Log of alerts sent to developers';
COMMENT ON COLUMN system_errors.error_id IS 'Unique error identifier (ERR-YYYYMMDD-HHMMSS-UUID)';
COMMENT ON COLUMN system_errors.severity IS 'Error severity: debug, info, warning, error, critical';
COMMENT ON COLUMN system_errors.category IS 'Error category for grouping and filtering';
COMMENT ON COLUMN system_errors.resolved IS 'Whether error has been acknowledged/fixed';
