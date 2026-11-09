-- FlowRemote 0008: first-run onboarding, AI/RPA controls and usage tracking.

CREATE TABLE IF NOT EXISTS user_onboarding (
    user_id       TEXT PRIMARY KEY REFERENCES users(id),
    current_step  TEXT NOT NULL DEFAULT 'welcome',
    completed_at  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

INSERT INTO user_onboarding (user_id, current_step, completed_at, created_at, updated_at)
SELECT id, 'complete', created_at, created_at, created_at FROM users;

CREATE TABLE IF NOT EXISTS user_automation_settings (
    user_id              TEXT PRIMARY KEY REFERENCES users(id),
    ai_enabled           INTEGER NOT NULL DEFAULT 1 CHECK (ai_enabled IN (0, 1)),
    rpa_enabled          INTEGER NOT NULL DEFAULT 1 CHECK (rpa_enabled IN (0, 1)),
    max_records_per_task INTEGER NOT NULL DEFAULT 10000 CHECK (max_records_per_task > 0),
    ai_daily_limit       INTEGER NOT NULL DEFAULT 100 CHECK (ai_daily_limit >= 0),
    rpa_daily_limit      INTEGER NOT NULL DEFAULT 10 CHECK (rpa_daily_limit >= 0),
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rpa_connections (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    kind         TEXT NOT NULL CHECK (kind IN ('local_excel', 'local_http')),
    name         TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    config_json  TEXT NOT NULL DEFAULT '{}',
    health       TEXT NOT NULL DEFAULT 'available',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (user_id, kind)
);

CREATE TABLE IF NOT EXISTS usage_events (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id),
    event_type   TEXT NOT NULL,
    provider     TEXT,
    model        TEXT,
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    duration_ms  INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    success      INTEGER NOT NULL CHECK (success IN (0, 1)),
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_events_user_time
    ON usage_events (user_id, created_at);
