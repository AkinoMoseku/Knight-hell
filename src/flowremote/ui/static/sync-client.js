const SYNC_DB = "flowremote-local";
const SYNC_VERSION = 1;

function syncOpenDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SYNC_DB, SYNC_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("snapshots")) {
        db.createObjectStore("snapshots");
      }
      if (!db.objectStoreNames.contains("outbox")) {
        db.createObjectStore("outbox", { keyPath: "operation_id" });
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function syncRequest(store, mode, action) {
  return new Promise((resolve, reject) => {
    const request = action(store);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function syncRead(storeName, key) {
  const db = await syncOpenDb();
  const result = await syncRequest(
    db.transaction(storeName, "readonly").objectStore(storeName),
    "readonly",
    (store) => store.get(key)
  );
  db.close();
  return result;
}

async function syncWrite(storeName, value, key) {
  const db = await syncOpenDb();
  await syncRequest(
    db.transaction(storeName, "readwrite").objectStore(storeName),
    "readwrite",
    (store) => key === undefined ? store.put(value) : store.put(value, key)
  );
  db.close();
}

async function syncDelete(storeName, key) {
  const db = await syncOpenDb();
  await syncRequest(
    db.transaction(storeName, "readwrite").objectStore(storeName),
    "readwrite",
    (store) => store.delete(key)
  );
  db.close();
}

async function syncOutbox() {
  const db = await syncOpenDb();
  const operations = await syncRequest(
    db.transaction("outbox", "readonly").objectStore("outbox"),
    "readonly",
    (store) => store.getAll()
  );
  db.close();
  return operations;
}

function syncStatus(text, state) {
  const badge = document.getElementById("sync-status");
  if (!badge) return;
  badge.textContent = text;
  badge.dataset.state = state;
}

function syncDeviceId() {
  const key = "flowremote.deviceId";
  let value = localStorage.getItem(key);
  if (!value) {
    value = crypto.randomUUID ? crypto.randomUUID() : `device-${Date.now()}-${Math.random()}`;
    localStorage.setItem(key, value);
  }
  return value;
}

async function saveSnapshot(payload) {
  await syncWrite("snapshots", {
    ...payload,
    user_id: document.body.dataset.userId || "",
    saved_at: new Date().toISOString(),
  }, "current");
  await syncWrite("meta", { key: "cursor", value: payload.cursor });
}

async function bootstrapSync() {
  const response = await fetch("/api/sync/bootstrap", {
    headers: {
      Accept: "application/json",
      "X-Device-Id": syncDeviceId(),
      "X-Device-Label": `${navigator.platform || "Browser"} · ${navigator.userAgent.split(" ").slice(-2).join(" ")}`,
    },
  });
  if (!response.ok) throw new Error("sync bootstrap failed");
  const payload = await response.json();
  await saveSnapshot(payload);
  const pending = (await syncOutbox()).length;
  syncStatus(pending ? `${pending} queued` : "Synced", pending ? "pending" : "online");
  return payload;
}

async function pullSync() {
  if (!navigator.onLine) return;
  const cursor = await syncRead("meta", "cursor");
  const response = await fetch(`/api/sync/pull?cursor=${Number(cursor?.value || 0)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) return;
  const payload = await response.json();
  if (payload.changes?.length) {
    await bootstrapSync();
    syncStatus("Updates saved", "online");
  }
}

function formOperation(form, submitter) {
  const action = submitter?.value || "";
  const data = new FormData(form);
  const parts = new URL(form.action, window.location.href).pathname.split("/");
  const taskIndex = parts.indexOf("tasks");
  const exceptionIndex = parts.indexOf("exceptions");
  const correction = {};
  for (const [key, value] of data.entries()) {
    if (key.startsWith("field_")) correction[key.slice(6)] = String(value);
  }
  return {
    type: "decision",
    operation_id: String(data.get("decision_id") || crypto.randomUUID()),
    task_id: parts[taskIndex + 1],
    record_id: parts[exceptionIndex + 1],
    action,
    value: String(data.get("value") || ""),
    base_revision: Number(data.get("base_revision") || 0) || undefined,
    correction: Object.keys(correction).length ? correction : undefined,
  };
}

async function queueDecision(form, submitter) {
  const operation = formOperation(form, submitter);
  if (!operation.action) return;
  await syncWrite("outbox", {
    ...operation,
    created_at: new Date().toISOString(),
  });
  form.closest("tr")?.classList.add("offline-queued");
  form.querySelectorAll("button, input").forEach((control) => {
    control.disabled = true;
  });
  const pending = (await syncOutbox()).length;
  syncStatus(`${pending} queued`, "pending");
}

async function markQueuedOperations() {
  const pending = await syncOutbox();
  for (const operation of pending) {
    const row = document.getElementById(`exc-${operation.record_id}`);
    if (!row) continue;
    row.classList.add("offline-queued");
    row.querySelectorAll(".action-form button, .action-form input").forEach((control) => {
      control.disabled = true;
    });
  }
  return pending.length;
}

async function flushOutbox() {
  if (!navigator.onLine) {
    syncStatus("Offline", "offline");
    return;
  }
  const pending = await syncOutbox();
  if (!pending.length) {
    try {
      await bootstrapSync();
    } catch {
      syncStatus("Offline cache", "offline");
    }
    return;
  }
  let synced = 0;
  for (const operation of pending) {
    const response = await fetch("/api/sync/operations", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(operation),
    });
    const result = await response.json();
    if (response.ok) {
      await syncDelete("outbox", operation.operation_id);
      synced += 1;
      continue;
    }
    if (response.status === 409) {
      syncStatus("Conflict · reload", "conflict");
      return;
    }
    operation.last_error = result.message || "Sync rejected";
    await syncWrite("outbox", operation);
    syncStatus("Sync needs attention", "conflict");
    return;
  }
  if (synced) {
    try {
      await bootstrapSync();
    } finally {
      window.location.reload();
    }
  }
}

document.addEventListener("submit", (event) => {
  if (!(event.target instanceof HTMLFormElement) || !event.target.matches(".action-form")) return;
  if (navigator.onLine) return;
  event.preventDefault();
  queueDecision(event.target, event.submitter).catch((error) => {
    console.error(error);
    syncStatus("Offline save failed", "conflict");
  });
}, true);

document.querySelector("[data-clear-local-data]")?.addEventListener("click", () => {
  if (!window.confirm("Clear cached tasks, pending actions and AI content from this device?")) return;
  indexedDB.deleteDatabase(SYNC_DB);
  sessionStorage.removeItem("flowremote.reviewScroll");
  window.location.href = "/";
});

document.querySelector(".logout-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  sessionStorage.removeItem("flowremote.localUser");
  await new Promise((resolve) => {
    const request = indexedDB.deleteDatabase(SYNC_DB);
    request.onsuccess = request.onerror = request.onblocked = () => resolve();
  });
  event.target.submit();
}, true);

window.addEventListener("online", flushOutbox);
window.addEventListener("offline", () => syncStatus("Offline", "offline"));
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && navigator.onLine) pullSync().catch(() => {});
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((error) => {
    console.warn("Service worker registration failed", error);
  });
}

const localUser = document.body.dataset.userId || "";
if (!localUser) {
  sessionStorage.removeItem("flowremote.localUser");
  indexedDB.deleteDatabase(SYNC_DB);
} else {
  sessionStorage.setItem("flowremote.localUser", localUser);
}

if (document.getElementById("sync-status")) {
  bootstrapSync()
    .then(markQueuedOperations)
    .then((pending) => {
      if (pending) return flushOutbox();
      return undefined;
    })
    .catch(async () => {
      const pending = await markQueuedOperations().catch(() => 0);
      syncStatus(
        pending ? `${pending} queued · offline` : (navigator.onLine ? "Sync unavailable" : "Offline cache"),
        "offline"
      );
    });
  window.setInterval(() => pullSync().catch(() => {}), 30_000);
}
