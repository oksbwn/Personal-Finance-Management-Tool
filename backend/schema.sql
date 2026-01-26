-- Auto-generated schema from SQLAlchemy models
-- Dialect: DuckDB (compatible with PostgreSQL syntax mostly)

CREATE TABLE tenants (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	full_name VARCHAR,
	avatar VARCHAR,
	role VARCHAR DEFAULT 'ADULT' NOT NULL, 
	dob DATE,
	pan_number VARCHAR,
	scopes VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE accounts (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	owner_id VARCHAR, 
	name VARCHAR NOT NULL, 
	type VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	account_mask VARCHAR,
	balance NUMERIC(15, 2),
	credit_limit NUMERIC(15, 2),
	billing_day NUMERIC(2, 0),
	due_day NUMERIC(2, 0),
	is_verified BOOLEAN DEFAULT TRUE NOT NULL,
	import_config VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE categories (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	icon VARCHAR, 
	color VARCHAR DEFAULT '#3B82F6',
	type VARCHAR DEFAULT 'expense',
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE transactions (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	account_id VARCHAR NOT NULL, 
	type VARCHAR NOT NULL DEFAULT 'DEBIT',
	amount NUMERIC(15, 2) NOT NULL, 
	date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	description VARCHAR, 
	recipient VARCHAR, 
	category VARCHAR, 
	tags VARCHAR, 
	external_id VARCHAR, 
	is_transfer BOOLEAN DEFAULT FALSE NOT NULL,
	linked_transaction_id VARCHAR,
	source VARCHAR NOT NULL DEFAULT 'MANUAL',
	latitude DECIMAL(10, 8),
	longitude DECIMAL(11, 8),
	location_name VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE category_rules (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	keywords VARCHAR NOT NULL, 
	priority NUMERIC(5, 0) DEFAULT 0, 
	is_transfer BOOLEAN DEFAULT FALSE NOT NULL,
	to_account_id VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE budgets (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	amount_limit NUMERIC(15, 2) NOT NULL, 
	period VARCHAR DEFAULT 'MONTHLY', 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE recurring_transactions (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	amount NUMERIC(15, 2) NOT NULL, 
	type VARCHAR NOT NULL DEFAULT 'DEBIT', 
	category VARCHAR, 
	account_id VARCHAR NOT NULL, 
	frequency VARCHAR DEFAULT 'MONTHLY' NOT NULL, 
	start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	next_run_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_active BOOLEAN DEFAULT TRUE NOT NULL, 
	last_run_date TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE mutual_funds_meta (
	scheme_code VARCHAR NOT NULL, 
	scheme_name VARCHAR NOT NULL, 
	isin_growth VARCHAR, 
	isin_reinvest VARCHAR, 
	fund_house VARCHAR, 
	category VARCHAR, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (scheme_code)
);

CREATE TABLE mutual_fund_holdings (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	scheme_code VARCHAR NOT NULL, 
	folio_number VARCHAR, 
	units NUMERIC(15, 4) DEFAULT 0, 
	average_price NUMERIC(15, 4) DEFAULT 0, 
	current_value NUMERIC(15, 2), 
	last_nav NUMERIC(15, 4), 
	user_id VARCHAR,
	last_updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(scheme_code) REFERENCES mutual_funds_meta (scheme_code),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE mutual_fund_orders (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	holding_id VARCHAR, 
	scheme_code VARCHAR NOT NULL, 
	type VARCHAR DEFAULT 'BUY' NOT NULL, 
	amount NUMERIC(15, 2) NOT NULL, 
	units NUMERIC(15, 4) NOT NULL, 
	nav NUMERIC(15, 4) NOT NULL, 
	order_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	folio_number VARCHAR,
	status VARCHAR DEFAULT 'COMPLETED', 
	external_id VARCHAR, 
	import_source VARCHAR DEFAULT 'MANUAL', 
	user_id VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(scheme_code) REFERENCES mutual_funds_meta (scheme_code),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE portfolio_timeline_cache (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	snapshot_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	portfolio_hash VARCHAR NOT NULL, 
	portfolio_value NUMERIC(15, 2) NOT NULL, 
	invested_value NUMERIC(15, 2) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_timeline_cache_lookup ON portfolio_timeline_cache (tenant_id, portfolio_hash, snapshot_date);

CREATE TABLE email_configurations (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	password VARCHAR NOT NULL, 
	imap_server VARCHAR DEFAULT 'imap.gmail.com', 
	folder VARCHAR DEFAULT 'INBOX', 
	is_active BOOLEAN DEFAULT TRUE, 
	auto_sync_enabled BOOLEAN DEFAULT FALSE, 
	last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
	cas_last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE email_sync_logs (
	id VARCHAR NOT NULL, 
	config_id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR DEFAULT 'running', 
	items_processed NUMERIC(10, 0) DEFAULT 0, 
	message VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(config_id) REFERENCES email_configurations (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE pending_transactions (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	account_id VARCHAR NOT NULL, 
	amount NUMERIC(15, 2) NOT NULL, 
	date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	description VARCHAR, 
	recipient VARCHAR, 
	category VARCHAR, 
	source VARCHAR NOT NULL, 
	raw_message VARCHAR, 
	external_id VARCHAR, 
	is_transfer BOOLEAN DEFAULT FALSE NOT NULL,
	to_account_id VARCHAR,
	balance NUMERIC(15, 2),
	credit_limit NUMERIC(15, 2),
	latitude DECIMAL(10, 8),
	longitude DECIMAL(11, 8),
	location_name VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE unparsed_messages (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	source VARCHAR NOT NULL, 
	raw_content VARCHAR NOT NULL, 
	subject VARCHAR, 
	sender VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE parsing_patterns (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	pattern_type VARCHAR DEFAULT 'regex', 
	pattern_value VARCHAR NOT NULL, 
	mapping_config VARCHAR NOT NULL, 
	is_active BOOLEAN DEFAULT TRUE, 
	description VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE ai_configurations (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	provider VARCHAR DEFAULT 'gemini', 
	model_name VARCHAR DEFAULT 'gemini-pro', 
	api_key VARCHAR, 
	is_enabled BOOLEAN DEFAULT TRUE, 
	prompts_json VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE ai_call_cache (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	content_hash VARCHAR NOT NULL, 
	provider VARCHAR NOT NULL, 
	model_name VARCHAR NOT NULL, 
	response_json VARCHAR NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_ai_call_cache_content_hash ON ai_call_cache (content_hash);

-- Additional Performance Indexes
CREATE INDEX ix_accounts_tenant_owner ON accounts (tenant_id, owner_id);
CREATE INDEX ix_transactions_query ON transactions (tenant_id, account_id, date);
CREATE INDEX ix_transactions_category ON transactions (tenant_id, category);
CREATE INDEX ix_budgets_lookup ON budgets (tenant_id, category);
CREATE INDEX ix_recurring_lookup ON recurring_transactions (tenant_id, account_id, next_run_date);
CREATE INDEX ix_mf_holdings_lookup ON mutual_fund_holdings (tenant_id, scheme_code);
CREATE INDEX ix_mf_orders_lookup ON mutual_fund_orders (tenant_id, scheme_code, order_date);
CREATE INDEX ix_mf_orders_folio ON mutual_fund_orders (folio_number);
CREATE INDEX ix_email_configs_tenant ON email_configurations (tenant_id);
CREATE INDEX ix_email_logs_lookup ON email_sync_logs (tenant_id, config_id);
CREATE INDEX ix_pending_txns_lookup ON pending_transactions (tenant_id, account_id);
CREATE INDEX ix_user_tenant ON users (tenant_id);

CREATE TABLE mobile_devices (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
    user_id VARCHAR,
	device_name VARCHAR NOT NULL, 
	device_id VARCHAR NOT NULL, 
	fcm_token VARCHAR, 
	is_approved BOOLEAN DEFAULT FALSE, 
	is_enabled BOOLEAN DEFAULT TRUE, 
	is_ignored BOOLEAN DEFAULT FALSE, 
	last_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id),
    FOREIGN KEY(user_id) REFERENCES users (id),
    UNIQUE(device_id)
);
CREATE INDEX ix_mobile_devices_tenant ON mobile_devices (tenant_id);

CREATE TABLE ingestion_events (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	device_id VARCHAR, 
	event_type VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	message VARCHAR, 
	data_json TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_ingestion_events_tenant_device ON ingestion_events (tenant_id, device_id);
