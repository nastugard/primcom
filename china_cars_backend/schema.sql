CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'listing_status') THEN
    CREATE TYPE listing_status AS ENUM ('new', 'active', 'inactive', 'error', 'deleted');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS listing_sources (
  id SMALLSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS listings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  source_id SMALLINT NOT NULL REFERENCES listing_sources(id),
  source_listing_id TEXT NOT NULL,
  original_url TEXT NOT NULL,

  scraped_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status listing_status NOT NULL DEFAULT 'new',

  ad_hash TEXT NOT NULL,
  content_checksum TEXT,

  brand TEXT,
  model TEXT,
  year INT,
  first_registration_date DATE,
  mileage_km INT,
  engine_type TEXT,
  engine_volume_l NUMERIC(6, 3),
  power_hp INT,
  transmission TEXT,
  drive_type TEXT,
  price_cny NUMERIC(14, 2),
  currency TEXT NOT NULL DEFAULT 'CNY',
  city TEXT,
  region TEXT,
  vin TEXT,
  owners_count INT,
  eco_standard TEXT,

  title_original TEXT,
  description_original TEXT,
  equipment_original TEXT,
  seller_comments_original TEXT,

  raw_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE listings ADD COLUMN IF NOT EXISTS color TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS trim TEXT;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS interior_material TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_listings_source_unique
  ON listings(source_id, source_listing_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_listings_ad_hash
  ON listings(ad_hash);

CREATE INDEX IF NOT EXISTS ix_listings_scraped_at
  ON listings(scraped_at DESC);

CREATE INDEX IF NOT EXISTS ix_listings_brand_model
  ON listings(brand, model);

CREATE INDEX IF NOT EXISTS ix_listings_year
  ON listings(year);

CREATE INDEX IF NOT EXISTS ix_listings_price_cny
  ON listings(price_cny);

CREATE INDEX IF NOT EXISTS ix_listings_mileage_km
  ON listings(mileage_km);

CREATE INDEX IF NOT EXISTS ix_listings_city
  ON listings(city);

CREATE INDEX IF NOT EXISTS ix_listings_drive_type
  ON listings(drive_type);

CREATE INDEX IF NOT EXISTS ix_listings_engine_type
  ON listings(engine_type);

CREATE INDEX IF NOT EXISTS ix_listings_color
  ON listings(color);

CREATE INDEX IF NOT EXISTS ix_listings_vin
  ON listings(vin);

CREATE TABLE IF NOT EXISTS listing_images (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  position INT NOT NULL,
  source_url TEXT NOT NULL,
  local_path TEXT,
  checksum TEXT,
  width INT,
  height INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_images_listing_position
  ON listing_images(listing_id, position);

CREATE INDEX IF NOT EXISTS ix_listing_images_listing
  ON listing_images(listing_id);

CREATE TABLE IF NOT EXISTS listing_price_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  price_cny NUMERIC(14, 2) NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_listing_price_history_listing_recorded
  ON listing_price_history(listing_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS listing_translations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,

  field TEXT NOT NULL,
  source_language TEXT NOT NULL,
  target_language TEXT NOT NULL,
  original_text TEXT NOT NULL,
  translated_text TEXT NOT NULL,
  translated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  translator TEXT NOT NULL,
  checksum TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_translations_unique
  ON listing_translations(listing_id, field, checksum);

CREATE INDEX IF NOT EXISTS ix_listing_translations_listing
  ON listing_translations(listing_id);

INSERT INTO listing_sources (code, name, base_url)
VALUES
  ('che168', 'Che168', 'https://www.che168.com'),
  ('dongchedi', 'Dongchedi', 'https://www.dongchedi.com'),
  ('guazi', 'Guazi', 'https://www.guazi.com')
ON CONFLICT (code) DO NOTHING;
