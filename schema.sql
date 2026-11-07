-- Local SQLite demo catalog.

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS official_domains (
    id INTEGER PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brands(id),
    domain TEXT NOT NULL UNIQUE,
    verification_source TEXT NOT NULL,
    verified_at DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS brand_aliases (
    brand_id INTEGER NOT NULL REFERENCES brands(id),
    alias TEXT NOT NULL,
    normalized_alias TEXT PRIMARY KEY,
    verification_source TEXT NOT NULL,
    reviewed_at DATE
);

CREATE TABLE IF NOT EXISTS scam_examples (
    id INTEGER PRIMARY KEY,
    message_text TEXT NOT NULL,
    expected_label TEXT NOT NULL CHECK (expected_label IN ('critical', 'suspicious', 'uncertain')),
    scenario_type TEXT NOT NULL UNIQUE,
    reviewed BOOLEAN NOT NULL DEFAULT FALSE
);
