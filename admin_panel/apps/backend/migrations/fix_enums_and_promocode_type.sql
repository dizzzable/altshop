-- Migration: Fix enum types and add missing columns
-- Date: 2025-12-11
-- Description: Adds missing enum values for transaction_status, subscription_status,
--              creates promocode_type enum, and adds type column to promocodes table

-- ============================================
-- 1. Fix transaction_status enum
-- ============================================

-- Check if enum exists and add missing values
DO $$
BEGIN
    -- Check if the enum type exists
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_status') THEN
        -- Add 'pending' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'pending' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transaction_status')) THEN
            ALTER TYPE transaction_status ADD VALUE 'pending';
        END IF;
        
        -- Add 'completed' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'completed' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transaction_status')) THEN
            ALTER TYPE transaction_status ADD VALUE 'completed';
        END IF;
        
        -- Add 'failed' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'failed' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transaction_status')) THEN
            ALTER TYPE transaction_status ADD VALUE 'failed';
        END IF;
        
        -- Add 'refunded' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'refunded' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transaction_status')) THEN
            ALTER TYPE transaction_status ADD VALUE 'refunded';
        END IF;
    ELSE
        -- Create the enum type if it doesn't exist
        CREATE TYPE transaction_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
    END IF;
END$$;

-- ============================================
-- 2. Fix subscription_status enum
-- ============================================

DO $$
BEGIN
    -- Check if the enum type exists
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status') THEN
        -- Add 'active' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'active' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_status')) THEN
            ALTER TYPE subscription_status ADD VALUE 'active';
        END IF;
        
        -- Add 'expired' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expired' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_status')) THEN
            ALTER TYPE subscription_status ADD VALUE 'expired';
        END IF;
        
        -- Add 'disabled' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'disabled' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_status')) THEN
            ALTER TYPE subscription_status ADD VALUE 'disabled';
        END IF;
        
        -- Add 'limited' if not exists
        IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'limited' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_status')) THEN
            ALTER TYPE subscription_status ADD VALUE 'limited';
        END IF;
    ELSE
        -- Create the enum type if it doesn't exist
        CREATE TYPE subscription_status AS ENUM ('active', 'expired', 'disabled', 'limited');
    END IF;
END$$;

-- ============================================
-- 3. Create promocode_type enum and add column
-- ============================================

DO $$
BEGIN
    -- Create promocode_type enum if not exists
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'promocode_type') THEN
        CREATE TYPE promocode_type AS ENUM ('discount', 'bonus', 'trial');
    END IF;
END$$;

-- Add type column to promocodes table if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'promocodes' AND column_name = 'type'
    ) THEN
        ALTER TABLE promocodes ADD COLUMN type promocode_type DEFAULT 'discount';
    END IF;
END$$;

-- ============================================
-- 4. Create transaction_type enum if needed
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_type') THEN
        CREATE TYPE transaction_type AS ENUM ('purchase', 'renewal', 'upgrade', 'refund');
    END IF;
END$$;

-- ============================================
-- Verification queries (optional, for debugging)
-- ============================================

-- SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'transaction_status');
-- SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'subscription_status');
-- SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'promocode_type');
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'promocodes';