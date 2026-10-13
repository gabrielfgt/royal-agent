CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS brokers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL CHECK (specialty IN ('residencial', 'investimento')),
    zones TEXT[] NOT NULL DEFAULT '{}'
);

ALTER TABLE brokers ADD COLUMN IF NOT EXISTS kinds TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS properties (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('venda', 'aluguel')),
    kind TEXT NOT NULL,
    neighborhood TEXT NOT NULL,
    neighborhood_key TEXT NOT NULL,
    city TEXT NOT NULL,
    price NUMERIC(14, 2) NOT NULL,
    condo_fee NUMERIC(10, 2) NOT NULL DEFAULT 0,
    iptu_monthly NUMERIC(10, 2) NOT NULL DEFAULT 0,
    area_m2 INT NOT NULL,
    bedrooms INT NOT NULL,
    suites INT NOT NULL DEFAULT 0,
    bathrooms INT NOT NULL,
    parking INT NOT NULL DEFAULT 0,
    features TEXT[] NOT NULL DEFAULT '{}',
    description TEXT NOT NULL,
    estimated_rent NUMERIC(10, 2),
    pet_friendly BOOLEAN NOT NULL DEFAULT TRUE,
    furnished BOOLEAN NOT NULL DEFAULT FALSE,
    embedding vector(1536)
);

ALTER TABLE properties DROP COLUMN IF EXISTS zone CASCADE;
ALTER TABLE properties DROP COLUMN IF EXISTS near_subway;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS city_key TEXT NOT NULL DEFAULT '';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'SP';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS condominium TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS condominium_key TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS street TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS postal_code TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS geo_precision TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS area_total_m2 INT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS year_built INT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS nearby TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS photos JSONB NOT NULL DEFAULT '[]';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS video_url TEXT;

CREATE INDEX IF NOT EXISTS properties_filter_idx ON properties (purpose, kind, price);
CREATE INDEX IF NOT EXISTS properties_embedding_idx ON properties USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL
);

CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel TEXT NOT NULL CHECK (channel IN ('web', 'telegram')),
    external_id TEXT NOT NULL,
    display_name TEXT,
    profile JSONB NOT NULL DEFAULT '{}',
    stage TEXT NOT NULL DEFAULT 'novo',
    score INT NOT NULL DEFAULT 0,
    temperature TEXT NOT NULL DEFAULT 'frio',
    summary JSONB,
    summary_updated_at TIMESTAMPTZ,
    handoff_reason TEXT,
    ai_paused BOOLEAN NOT NULL DEFAULT FALSE,
    opted_out BOOLEAN NOT NULL DEFAULT FALSE,
    followup_count INT NOT NULL DEFAULT 0,
    reengaged_count INT NOT NULL DEFAULT 0,
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    crm_contact_id TEXT,
    crm_deal_id TEXT,
    crm_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel, external_id)
);

CREATE INDEX IF NOT EXISTS leads_followup_idx ON leads (stage, last_outbound_at) WHERE NOT opted_out AND NOT ai_paused;

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('lead', 'agent', 'system')),
    content TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'text',
    agent TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_lead_idx ON messages (lead_id, id);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    broker_id TEXT NOT NULL REFERENCES brokers (id),
    property_code TEXT REFERENCES properties (code),
    kind TEXT NOT NULL CHECK (kind IN ('visita', 'reuniao', 'reuniao_especialista')),
    starts_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'agendado' CHECK (status IN ('agendado', 'remarcado', 'cancelado')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS appointments_broker_slot_idx ON appointments (broker_id, starts_at) WHERE status = 'agendado';
CREATE INDEX IF NOT EXISTS appointments_lead_idx ON appointments (lead_id, starts_at);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    lead_id UUID REFERENCES leads (id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_lead_idx ON events (lead_id, id);
CREATE INDEX IF NOT EXISTS events_type_idx ON events (type, created_at);

CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    hits INT NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);

CREATE TABLE IF NOT EXISTS telegram_updates (
    update_id BIGINT PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone_key TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_channel TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_external_id TEXT;
CREATE INDEX IF NOT EXISTS leads_phone_key_idx ON leads (phone_key) WHERE phone_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS lead_identities (
    channel TEXT NOT NULL,
    external_id TEXT NOT NULL,
    lead_id UUID NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (channel, external_id)
);

CREATE INDEX IF NOT EXISTS lead_identities_lead_idx ON lead_identities (lead_id);

INSERT INTO lead_identities (channel, external_id, lead_id)
SELECT channel, external_id, id FROM leads
ON CONFLICT DO NOTHING;
