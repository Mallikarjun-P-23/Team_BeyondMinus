-- ============================================================
-- Migration 021: Update Blood Donors Schema
-- ============================================================

ALTER TABLE blood_donors 
ADD COLUMN IF NOT EXISTS age INTEGER,
ADD COLUMN IF NOT EXISTS email TEXT,
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS state TEXT,
ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'India',
ADD COLUMN IF NOT EXISTS total_donations INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS eligible_for_donation BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS medical_condition TEXT,
ADD COLUMN IF NOT EXISTS weight_kg NUMERIC(5, 2),
ADD COLUMN IF NOT EXISTS hemoglobin_g_dL NUMERIC(4, 2),
ADD COLUMN IF NOT EXISTS address TEXT;

-- Registration date is already covered by created_at, but we can add an explicit one if needed
-- For now we'll stick with created_at or use an alias in views.
