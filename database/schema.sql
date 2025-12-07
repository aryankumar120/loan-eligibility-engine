-- Create database tables for Loan Eligibility Engine

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    monthly_income DECIMAL(12, 2),
    credit_score INTEGER,
    employment_status VARCHAR(100),
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_credit_score CHECK (credit_score >= 300 AND credit_score <= 850),
    CONSTRAINT check_age CHECK (age >= 18 AND age <= 100),
    CONSTRAINT check_monthly_income CHECK (monthly_income >= 0)
);

-- Loan products table
CREATE TABLE IF NOT EXISTS loan_products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    provider VARCHAR(255),
    interest_rate DECIMAL(5, 2),
    min_income DECIMAL(12, 2),
    max_income DECIMAL(12, 2),
    min_credit_score INTEGER,
    max_credit_score INTEGER,
    min_age INTEGER,
    max_age INTEGER,
    employment_required VARCHAR(100),
    loan_amount_min DECIMAL(12, 2),
    loan_amount_max DECIMAL(12, 2),
    source_url TEXT,
    eligibility_criteria JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_interest_rate CHECK (interest_rate >= 0 AND interest_rate <= 100)
);

-- Matches table (linking users to eligible products)
CREATE TABLE IF NOT EXISTS matches (
    match_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    match_score DECIMAL(5, 2),
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES loan_products(product_id) ON DELETE CASCADE,
    UNIQUE(user_id, product_id)
);

-- CSV Upload tracking table
CREATE TABLE IF NOT EXISTS csv_uploads (
    upload_id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    total_records INTEGER,
    processed_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_credit_score ON users(credit_score);
CREATE INDEX IF NOT EXISTS idx_users_monthly_income ON users(monthly_income);

CREATE INDEX IF NOT EXISTS idx_loan_products_provider ON loan_products(provider);
CREATE INDEX IF NOT EXISTS idx_loan_products_min_credit_score ON loan_products(min_credit_score);
CREATE INDEX IF NOT EXISTS idx_loan_products_min_income ON loan_products(min_income);

CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_product_id ON matches(product_id);
CREATE INDEX IF NOT EXISTS idx_matches_notification_sent ON matches(notification_sent);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_loan_products_updated_at BEFORE UPDATE ON loan_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View for easy matching queries
CREATE OR REPLACE VIEW eligible_matches AS
SELECT
    u.user_id,
    u.email,
    u.monthly_income,
    u.credit_score,
    u.employment_status,
    u.age,
    lp.product_id,
    lp.product_name,
    lp.provider,
    lp.interest_rate,
    lp.loan_amount_min,
    lp.loan_amount_max
FROM users u
CROSS JOIN loan_products lp
WHERE
    (lp.min_income IS NULL OR u.monthly_income >= lp.min_income)
    AND (lp.max_income IS NULL OR u.monthly_income <= lp.max_income)
    AND (lp.min_credit_score IS NULL OR u.credit_score >= lp.min_credit_score)
    AND (lp.max_credit_score IS NULL OR u.credit_score <= lp.max_credit_score)
    AND (lp.min_age IS NULL OR u.age >= lp.min_age)
    AND (lp.max_age IS NULL OR u.age <= lp.max_age)
    AND (lp.employment_required IS NULL OR u.employment_status = lp.employment_required);

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;
