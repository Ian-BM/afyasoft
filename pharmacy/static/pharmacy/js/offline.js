/**
 * IndexedDB: pending offline sales + catalog snapshot.
 */
(function () {
  const DB_NAME = "afyasoft-offline";
  const DB_VER = 1;
  const PENDING = "pending_sales";
  const META = "meta";

  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VER);
      req.onerror = () => reject(req.error);
      req.onsuccess = () => resolve(req.result);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(PENDING)) {
          db.createObjectStore(PENDING, { keyPath: "offlineUuid" });
        }
        if (!db.objectStoreNames.contains(META)) {
          db.createObjectStore(META, { keyPath: "key" });
        }
      };
    });
  }

  window.AfyaOffline = {
    savePending(record) {
      return openDb().then(
        (db) =>
          new Promise((resolve, reject) => {
            const t = db.transaction(PENDING, "readwrite");
            t.oncomplete = () => resolve();
            t.onerror = () => reject(t.error);
            t.objectStore(PENDING).put(record);
          })
      );
    },

    removePending(offlineUuid) {
      return openDb().then(
        (db) =>
          new Promise((resolve, reject) => {
            const t = db.transaction(PENDING, "readwrite");
            t.oncomplete = () => resolve();
            t.onerror = () => reject(t.error);
            t.objectStore(PENDING).delete(offlineUuid);
          })
      );
    },

    listPending() {
      return openDb().then(
        (db) =>
          new Promise((resolve, reject) => {
            const t = db.transaction(PENDING, "readonly");
            const store = t.objectStore(PENDING);
            const out = [];
            const req = store.openCursor();
            req.onerror = () => reject(req.error);
            req.onsuccess = (e) => {
              const c = e.target.result;
              if (c) {
                out.push(c.value);
                c.continue();
              } else resolve(out);
            };
          })
      );
    },

    pendingCount() {
      return window.AfyaOffline.listPending().then((a) => a.length);
    },

    saveCatalogSnapshot(medicines) {
      return openDb().then(
        (db) =>
          new Promise((resolve, reject) => {
            const t = db.transaction(META, "readwrite");
            t.oncomplete = () => resolve();
            t.onerror = () => reject(t.error);
            t.objectStore(META).put({
              key: "medicines",
              data: medicines,
              updatedAt: Date.now(),
            });
          })
      );
    },

    loadCatalogSnapshot() {
      return openDb().then(
        (db) =>
          new Promise((resolve, reject) => {
            const t = db.transaction(META, "readonly");
            const req = t.objectStore(META).get("medicines");
            req.onerror = () => reject(req.error);
            req.onsuccess = () => resolve(req.result ? req.result.data : null);
          })
      );
    },
  };
})();
