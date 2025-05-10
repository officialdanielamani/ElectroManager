/* ------------------------------------------------------------------------
 * js/utils/idb.js
 * Tiny promise‑based wrapper around IndexedDB for the Electronics Inventory
 * app.  It exposes four high‑level async helpers that mirror the old
 * LocalStorage API you had in storage.js:
 *
 *   await idb.loadComponents()   → Array of components
 *   await idb.saveComponents(arr)
 *   await idb.loadLocations()    → Array of locations
 *   await idb.saveLocations(arr)
 *
 * Internally it just opens one DB ("electronicsInventory") with two object
 * stores: "components" and "locations" – both keyed by `id`.
 * --------------------------------------------------------------------- */

const DB_NAME = 'electronicsInventory';
const DB_VERSION = 1;
const STORES = ['components', 'locations'];

// -----------------------------------------------------------------------------
// Open the database (singleton)
// -----------------------------------------------------------------------------
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      // Create object stores if they don't yet exist
      STORES.forEach((store) => {
        if (!db.objectStoreNames.contains(store)) {
          db.createObjectStore(store, { keyPath: 'id' });
        }
      });
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror   = () => reject(request.error);
  });
}

const dbPromise = openDB();

// -----------------------------------------------------------------------------
// Low‑level helper: run a callback inside a transaction
// -----------------------------------------------------------------------------
function withStore(storeName, mode, fn) {
  return dbPromise.then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx    = db.transaction(storeName, mode);
        const store = tx.objectStore(storeName);
        const res   = fn(store);
        tx.oncomplete = () => resolve(res);
        tx.onerror    = () => reject(tx.error);
      })
  );
}

// Utility helpers used by the public API
async function clearStore(storeName) {
  await withStore(storeName, 'readwrite', (store) => store.clear());
}

async function bulkPut(storeName, items) {
  await withStore(storeName, 'readwrite', (store) => {
    items.forEach((item) => store.put(item));
  });
}

// -----------------------------------------------------------------------------
// Public API – mirrors the old LocalStorage interface but async
// -----------------------------------------------------------------------------
 const idb = {
  /* Generic helpers ------------------------------------------------------ */
  async getAll(storeName) {
    return withStore(storeName, 'readonly', (store) => store.getAll());
  },

  async setAll(storeName, array) {
    await clearStore(storeName);
    await bulkPut(storeName, array);
    return true;
  },

  /* Convenience wrappers ------------------------------------------------- */
  loadComponents() {
    return this.getAll('components');
  },

  saveComponents(array) {
    return this.setAll('components', array);
  },

  loadLocations() {
    return this.getAll('locations');
  },

  saveLocations(array) {
    return this.setAll('locations', array);
  },
};

export default idb;
