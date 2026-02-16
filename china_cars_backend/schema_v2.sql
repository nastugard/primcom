CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core runtime telemetry
CREATE TABLE IF NOT EXISTS scrape_runs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_code TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
  fetched INT NOT NULL DEFAULT 0,
  upserted INT NOT NULL DEFAULT 0,
  skipped INT NOT NULL DEFAULT 0,
  errors_json JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_scrape_runs_source_started_at
  ON scrape_runs(source_code, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_scrape_runs_status
  ON scrape_runs(status);

CREATE TABLE IF NOT EXISTS raw_listings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  run_id UUID NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
  source_id SMALLINT NOT NULL REFERENCES listing_sources(id),
  source_listing_id TEXT NOT NULL,
  content_checksum TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_raw_listings_run
  ON raw_listings(run_id);
CREATE INDEX IF NOT EXISTS ix_raw_listings_source_listing
  ON raw_listings(source_id, source_listing_id);

-- Translation cache (DB as source of truth)
CREATE TABLE IF NOT EXISTS translation_cache (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  source_text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  lang_from TEXT NOT NULL DEFAULT 'zh',
  lang_to TEXT NOT NULL DEFAULT 'en',
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  checksum TEXT NOT NULL,
  hits INT NOT NULL DEFAULT 0,
  last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(source_text, lang_from, lang_to)
);

CREATE INDEX IF NOT EXISTS ix_translation_cache_hits ON translation_cache(hits DESC);

-- Canonical vehicle layer
CREATE TABLE IF NOT EXISTS vehicle_make (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vehicle_model (
  id BIGSERIAL PRIMARY KEY,
  make_id BIGINT NOT NULL REFERENCES vehicle_make(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(make_id, name)
);

CREATE TABLE IF NOT EXISTS vehicle_generation (
  id BIGSERIAL PRIMARY KEY,
  model_id BIGINT NOT NULL REFERENCES vehicle_model(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(model_id, name)
);

CREATE TABLE IF NOT EXISTS vehicle_trim (
  id BIGSERIAL PRIMARY KEY,
  generation_id BIGINT NOT NULL REFERENCES vehicle_generation(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(generation_id, name)
);

CREATE TABLE IF NOT EXISTS vehicle_aliases (
  id BIGSERIAL PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('make', 'model', 'generation', 'trim')),
  entity_id BIGINT NOT NULL,
  lang TEXT NOT NULL,
  alias TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(entity_type, entity_id, lang, alias)
);

CREATE TABLE IF NOT EXISTS listing_vehicle_map (
  listing_id UUID PRIMARY KEY REFERENCES listings(id) ON DELETE CASCADE,
  make_id BIGINT REFERENCES vehicle_make(id) ON DELETE SET NULL,
  model_id BIGINT REFERENCES vehicle_model(id) ON DELETE SET NULL,
  generation_id BIGINT REFERENCES vehicle_generation(id) ON DELETE SET NULL,
  trim_id BIGINT REFERENCES vehicle_trim(id) ON DELETE SET NULL,
  mapped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_listing_vehicle_map_make ON listing_vehicle_map(make_id);
CREATE INDEX IF NOT EXISTS ix_listing_vehicle_map_model ON listing_vehicle_map(model_id);
