-- FlowRemote 0007: local-first synchronization, revisions and devices.

ALTER TABLE tasks ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;
ALTER TABLE exceptions ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS sync_clock (
    id           TEXT PRIMARY KEY,
    next_sequence INTEGER NOT NULL CHECK (next_sequence > 0)
);

INSERT INTO sync_clock (id, next_sequence) VALUES ('global', 1);

CREATE TABLE IF NOT EXISTS sync_changes (
    sequence      INTEGER PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    entity_type   TEXT NOT NULL CHECK (entity_type IN ('task', 'exception')),
    entity_id     TEXT NOT NULL,
    task_id       TEXT NOT NULL REFERENCES tasks(id),
    revision      INTEGER NOT NULL CHECK (revision > 0),
    changed_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_changes_user_sequence
    ON sync_changes (user_id, sequence);

CREATE TABLE IF NOT EXISTS devices (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    label         TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_devices_user
    ON devices (user_id, last_seen_at);
