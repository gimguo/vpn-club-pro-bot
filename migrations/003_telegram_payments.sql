-- Migration: Add telegram_payments table
-- Created: 2025-07-13
-- Description: Adds support for Telegram Payments API (Stars and bank cards)
-- Database: PostgreSQL

CREATE TABLE telegram_payments (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- User relationship
    user_id INTEGER NOT NULL,
    
    -- Payment identifiers
    telegram_payment_charge_id VARCHAR(255) UNIQUE NOT NULL,
    provider_payment_charge_id VARCHAR(255),
    telegram_user_id VARCHAR(50) NOT NULL,
    
    -- Payment details
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'XTR',  -- XTR for Telegram Stars, USD for cards
    tariff_type VARCHAR(50) NOT NULL,
    
    -- Payment type and status
    payment_type VARCHAR(20) NOT NULL,  -- 'stars' or 'card'
    status VARCHAR(50) DEFAULT 'pending',  -- pending, succeeded, canceled
    
    -- Additional data
    invoice_payload TEXT,  -- Payload for payment identification
    order_info TEXT,  -- Additional order information
    
    -- Foreign key constraint
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Create indexes for better performance
CREATE INDEX idx_telegram_payments_user_id ON telegram_payments (user_id);
CREATE INDEX idx_telegram_payments_status ON telegram_payments (status);
CREATE INDEX idx_telegram_payments_created_at ON telegram_payments (created_at);
CREATE INDEX idx_telegram_payments_charge_id ON telegram_payments (telegram_payment_charge_id);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_telegram_payments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER telegram_payments_updated_at_trigger
    BEFORE UPDATE ON telegram_payments
    FOR EACH ROW
    EXECUTE FUNCTION update_telegram_payments_updated_at();

-- Verification queries
-- SELECT COUNT(*) FROM telegram_payments; -- Should return 0 initially
-- SELECT tablename FROM pg_tables WHERE tablename = 'telegram_payments'; -- Should return 'telegram_payments' 