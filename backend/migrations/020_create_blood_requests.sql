-- Create blood requests table for patient blood requirement requests
-- Migration: 020_create_blood_requests.sql

CREATE TABLE IF NOT EXISTS blood_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctors(id) ON DELETE SET NULL,
    
    -- Request details
    patient_name TEXT NOT NULL,
    blood_group TEXT NOT NULL CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    units_needed INTEGER NOT NULL DEFAULT 1 CHECK (units_needed > 0),
    location TEXT NOT NULL,
    needed_by_date TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Emergency and status
    is_emergency BOOLEAN NOT NULL DEFAULT FALSE,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'acknowledged', 'arranged', 'fulfilled', 'cancelled', 'expired')),
    
    -- Additional information
    reason TEXT,
    medical_condition TEXT,
    hospital_name TEXT,
    contact_number TEXT NOT NULL,
    alternative_contact TEXT,
    
    -- Tracking
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by UUID REFERENCES doctors(id) ON DELETE SET NULL,
    fulfilled_at TIMESTAMP WITH TIME ZONE,
    fulfilled_by UUID REFERENCES doctors(id) ON DELETE SET NULL,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancellation_reason TEXT,
    
    -- Metadata
    notes TEXT,
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_blood_requests_patient ON blood_requests(patient_id);
CREATE INDEX IF NOT EXISTS idx_blood_requests_doctor ON blood_requests(doctor_id);
CREATE INDEX IF NOT EXISTS idx_blood_requests_status ON blood_requests(status);
CREATE INDEX IF NOT EXISTS idx_blood_requests_emergency ON blood_requests(is_emergency);
CREATE INDEX IF NOT EXISTS idx_blood_requests_priority ON blood_requests(priority);
CREATE INDEX IF NOT EXISTS idx_blood_requests_blood_group ON blood_requests(blood_group);
CREATE INDEX IF NOT EXISTS idx_blood_requests_needed_date ON blood_requests(needed_by_date);
CREATE INDEX IF NOT EXISTS idx_blood_requests_created ON blood_requests(created_at DESC);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_blood_requests_status_emergency ON blood_requests(status, is_emergency, created_at DESC);

-- Create notifications table for emergency alerts
CREATE TABLE IF NOT EXISTS blood_request_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blood_request_id UUID NOT NULL REFERENCES blood_requests(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctors(id) ON DELETE CASCADE,
    
    notification_type TEXT NOT NULL CHECK (notification_type IN ('emergency', 'reminder', 'status_change', 'acknowledgement')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    sent_via TEXT[] DEFAULT ARRAY['in_app'],  -- Could be: in_app, email, sms, push
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blood_notifications_doctor ON blood_request_notifications(doctor_id, is_read);
CREATE INDEX IF NOT EXISTS idx_blood_notifications_request ON blood_request_notifications(blood_request_id);
CREATE INDEX IF NOT EXISTS idx_blood_notifications_created ON blood_request_notifications(created_at DESC);

-- Function to automatically set priority based on emergency status and date
CREATE OR REPLACE FUNCTION set_blood_request_priority()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_emergency = TRUE THEN
        NEW.priority := 'critical';
    ELSIF NEW.needed_by_date <= NOW() + INTERVAL '24 hours' THEN
        NEW.priority := 'high';
    ELSIF NEW.needed_by_date <= NOW() + INTERVAL '3 days' THEN
        NEW.priority := 'normal';
    ELSE
        NEW.priority := 'low';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to set priority automatically
DROP TRIGGER IF EXISTS trigger_set_blood_request_priority ON blood_requests;
CREATE TRIGGER trigger_set_blood_request_priority
    BEFORE INSERT OR UPDATE OF is_emergency, needed_by_date
    ON blood_requests
    FOR EACH ROW
    EXECUTE FUNCTION set_blood_request_priority();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_blood_request_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update timestamp
DROP TRIGGER IF EXISTS trigger_update_blood_request_timestamp ON blood_requests;
CREATE TRIGGER trigger_update_blood_request_timestamp
    BEFORE UPDATE ON blood_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_blood_request_timestamp();

-- Function to create emergency notifications for doctors
CREATE OR REPLACE FUNCTION notify_doctors_blood_emergency()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_emergency = TRUE AND OLD.is_emergency IS DISTINCT FROM NEW.is_emergency THEN
        -- Notify all active doctors (you can customize this logic)
        INSERT INTO blood_request_notifications (blood_request_id, doctor_id, notification_type, title, message)
        SELECT 
            NEW.id,
            d.id,
            'emergency',
            '🚨 EMERGENCY Blood Request',
            'Urgent blood needed: ' || NEW.blood_group || ' for ' || NEW.patient_name || ' at ' || NEW.location
        FROM doctors d
        WHERE d.is_available = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for emergency notifications
DROP TRIGGER IF EXISTS trigger_notify_emergency_blood_request ON blood_requests;
CREATE TRIGGER trigger_notify_emergency_blood_request
    AFTER INSERT OR UPDATE OF is_emergency
    ON blood_requests
    FOR EACH ROW
    EXECUTE FUNCTION notify_doctors_blood_emergency();

-- Grant permissions
GRANT ALL ON blood_requests TO postgres;
GRANT ALL ON blood_request_notifications TO postgres;

-- Add sample comment
COMMENT ON TABLE blood_requests IS 'Patient blood requests with emergency handling and priority management';
COMMENT ON TABLE blood_request_notifications IS 'Real-time notifications for doctors about blood requests';
