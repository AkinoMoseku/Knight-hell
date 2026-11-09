const OFFLINE_DB = "flowremote-local";
const OFFLINE_VERSION = 1;

function openOfflineDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(OFFLINE_DB, OFFLINE_VERSION);
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

function readOfflineValue(db, store, key) {
  return new Promise((resolve, reject) => {
    const request = db.transaction(store, "readonly").objectStore(store).get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function renderOfflineCache() {
  const container = document.getElementById("offline-tasks");
  const updated = document.getElementById("offline-updated");
  const db = await openOfflineDb();
  const snapshot = await readOfflineValue(db, "snapshots", "current");
  db.close();
  const localUser = sessionStorage.getItem("flowremote.localUser");
  if (!snapshot) {
    updated.textContent = "No cached work state exists on this device yet.";
    container.append(element("p", "muted", "Reconnect once to populate the offline cache."));
    return;
  }
  if (!localUser || snapshot.user_id !== localUser) {
    updated.textContent = "The local copy belongs to a signed-out account.";
    container.append(element("p", "muted", "Sign in again to restore your server-side work state."));
    return;
  }
  updated.textContent = `Saved ${new Date(snapshot.saved_at).toLocaleString()} · cursor ${snapshot.cursor}`;
  if (!snapshot.tasks.length) {
    container.append(element("p", "muted", "No tasks are available in the cached snapshot."));
    return;
  }
  for (const task of snapshot.tasks) {
    const card = element("article", "task-card");
    card.append(element("span", "task-id", task.id));
    card.append(element("h2", "", task.workflow));
    card.append(element(
      "p",
      "task-file",
      `${task.batch_size} records · ${task.status.replaceAll("_", " ")} · revision ${task.revision}`
    ));
    const list = element("div", "offline-exceptions");
    for (const exception of task.exceptions.slice(0, 8)) {
      const row = element("div", "offline-exception");
      row.append(element("strong", "mono", exception.record_id));
      row.append(element("span", "muted", ` ${exception.status.replaceAll("_", " ")}`));
      if (exception.suggestion) {
        row.append(element("div", "small", `AI suggestion: ${exception.suggestion}`));
      }
      if (exception.ai_items?.length) {
        row.append(element(
          "div",
          "small muted",
          exception.ai_items.map((item) => `${item.field}=${item.value} (${Math.round(item.confidence * 100)}%)`).join(" · ")
        ));
      }
      list.append(row);
    }
    if (task.exceptions.length > 8) {
      list.append(element("p", "small muted", `+${task.exceptions.length - 8} more exceptions`));
    }
    card.append(list);
    container.append(card);
  }
}

renderOfflineCache().catch((error) => {
  document.getElementById("offline-updated").textContent = "Could not read the local cache.";
  console.error(error);
});
