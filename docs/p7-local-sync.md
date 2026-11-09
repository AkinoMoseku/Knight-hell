# P7: local-first synchronization and PWA

## Design principle

The server is authoritative for accounts, tasks, exceptions, decisions,
approvals, execution and audit. The browser keeps a cache plus an Outbox so the
review workspace remains usable when connectivity fails.

## Data model

- `tasks.revision`: increments when task-level state changes.
- `exceptions.revision`: increments when review or AI suggestion state changes.
- `sync_clock`: portable monotonic cursor, advanced with an atomic SQL
  `UPDATE ... RETURNING`.
- `sync_changes`: append-only change notifications for incremental pull.
- `devices`: browser/device ID, label and last-seen time.

## APIs

### `GET /api/sync/bootstrap`

Registers the device from `X-Device-Id` and `X-Device-Label`, then returns the
visible task snapshot, exceptions, latest run, verified AI items, server cursor
and server timestamp.

### `GET /api/sync/pull?cursor=N`

Returns up to 500 task or exception change notifications after the supplied
cursor. The client stores the snapshot cursor in IndexedDB and polls this
endpoint periodically and when a tab becomes visible.

### `POST /api/sync/operations`

Accepts a JSON decision operation with a client operation ID, task ID, record
ID, action, base revision and optional multi-field correction.

- The decision ID is the idempotency key.
- A replayed operation returns the first stored result with `replayed=true`.
- A stale exception revision returns HTTP `409 revision_conflict`.
- Accept revalidates the active AI suggestion and order rules.
- Edit applies all supplied correction fields atomically.
- Skip excludes the record without a value.

## Browser implementation

`sync-client.js` uses IndexedDB stores:

- `snapshots/current`: authoritative snapshot plus local save time.
- `outbox`: operations waiting for network.
- `meta/cursor`: last consumed server cursor.

The Outbox intercepts decision forms only when offline. Queued rows are disabled
and marked **Queued locally** until synchronization succeeds.

The cache is bound to the signed-in user. Logout and login screens clear the
IndexedDB database to prevent another account on the same browser from reading a
previous user's tasks or AI content.

## PWA

- `/static/manifest.webmanifest` defines the installable standalone app.
- `/static/icon.svg` provides the application icon.
- `/sw.js` is served at root scope and controls all pages.
- `offline.html` and `offline-cache.js` render the last user-bound task snapshot
  when navigation fails.

The service worker caches the application shell and uses network-first for page
navigation, cache-first for static assets, and never caches state-changing
requests.

## Current boundaries

- Offline decisions are supported on an already loaded review page.
- Creating tasks and AI generation still require a server connection.
- Device rows provide identification and heartbeat groundwork, not remote
  session revocation.
- A production deployment should add CSRF protection, per-device server sessions
  and explicit device-revocation controls.

Verification: 230 repository tests pass, including eight dedicated sync tests
for bootstrap access, device registration, PWA assets, idempotent offline
decisions, stale revisions, incremental pull, AI cache content and multi-field
offline edits. Browser JavaScript files also pass Node syntax checks.
