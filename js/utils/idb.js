// js/utils/idb.js - Fixed version for ultra-compact storage

console.log("Loading idb.js...");

window.App = window.App || {};
window.App.utils = window.App.utils || {};

window.App.utils.idb = {
  db: null,
  dbName: 'electronicsInventory',
  dbVersion: 2, // Increased version for new compact format
  stores: ['components', 'locations', 'drawers', 'cells', 'categories', 'footprints', 'lowStockConfig'],

  init() {
    console.log("Initializing IndexedDB...");

    if (this.db) {
      console.log("DB already initialized");
      return Promise.resolve(true);
    }

    if (!window.indexedDB) {
      console.log("IndexedDB not supported");
      return Promise.resolve(false);
    }

    const self = this;

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(self.dbName, self.dbVersion);

      request.onupgradeneeded = function(event) {
        console.log(`Upgrading database from version ${event.oldVersion} to ${event.newVersion}`);
        const db = event.target.result;

        // Create stores if they don't exist
        self.stores.forEach(storeName => {
          if (!db.objectStoreNames.contains(storeName)) {
            console.log(`Creating store: ${storeName}`);
            db.createObjectStore(storeName, { keyPath: 'id' });
          }
        });
      };

      request.onsuccess = function(event) {
        self.db = event.target.result;
        console.log("IndexedDB initialized successfully");
        resolve(true);
      };

      request.onerror = function(event) {
        console.error("IndexedDB initialization error:", event.target.error);
        resolve(false);
      };

      request.onblocked = function(event) {
        console.warn("IndexedDB blocked - close other tabs");
        resolve(false);
      };
    });
  },

  // Generic load method
  _loadFromStore(storeName) {
    const self = this;

    return this.init().then(initialized => {
      if (!initialized || !self.db) {
        console.log(`IndexedDB not available for loading ${storeName}`);
        return [];
      }

      return new Promise((resolve, reject) => {
        const transaction = self.db.transaction(storeName, 'readonly');
        const store = transaction.objectStore(storeName);
        const request = store.getAll();

        request.onsuccess = function() {
          const result = request.result || [];
          console.log(`Loaded ${result.length} items from ${storeName}:`, result);

          // Handle special stores
          if (storeName === 'categories' || storeName === 'footprints') {
            const names = result.map(item => item.name).filter(Boolean);
            console.log(`Converted ${storeName} to names:`, names);
            resolve(names);
          } else {
            resolve(result);
          }
        };

        request.onerror = function(event) {
          console.error(`Error loading from ${storeName}:`, event.target.error);
          resolve([]);
        };

        transaction.onerror = function(event) {
          console.error(`Transaction error loading ${storeName}:`, event.target.error);
          resolve([]);
        };
      });
    });
  },

  // Generic save method
  _saveToStore(storeName, items) {
    const self = this;

    return this.init().then(initialized => {
      if (!initialized || !self.db) {
        console.log(`IndexedDB not available for saving ${storeName}`);
        return false;
      }

      if (!Array.isArray(items)) {
        console.error(`Items must be an array for ${storeName}`);
        return false;
      }

      console.log(`Saving ${items.length} items to ${storeName}:`, items);

      return new Promise((resolve, reject) => {
        const transaction = self.db.transaction(storeName, 'readwrite');
        const store = transaction.objectStore(storeName);

        // Clear existing data first
        const clearRequest = store.clear();

        clearRequest.onsuccess = function() {
          console.log(`Cleared ${storeName}, now adding ${items.length} items`);
          
          // Add all items
          let addedCount = 0;
          const errors = [];

          if (items.length === 0) {
            resolve(true);
            return;
          }

          items.forEach((item, index) => {
            // Handle compact format - components have 'i' instead of 'id'
            let processedItem = item;
            
            // For components store, if item has 'i' but no 'id', create a proper keyPath
            if (storeName === 'components' && item.i && !item.id) {
              processedItem = { ...item, id: item.i };
            }
            
            if (!processedItem || (typeof processedItem === 'object' && !processedItem.id && storeName !== 'categories' && storeName !== 'footprints')) {
              console.warn(`Skipping invalid item at index ${index}:`, item);
              addedCount++;
              checkComplete();
              return;
            }

            const addRequest = store.put(processedItem);
            
            addRequest.onsuccess = function() {
              addedCount++;
              checkComplete();
            };

            addRequest.onerror = function(event) {
              console.error(`Error adding item to ${storeName}:`, event.target.error, processedItem);
              errors.push(event.target.error);
              addedCount++;
              checkComplete();
            };
          });

          function checkComplete() {
            if (addedCount === items.length) {
              if (errors.length > 0) {
                console.warn(`Completed ${storeName} save with ${errors.length} errors`);
              } else {
                console.log(`Successfully saved ${items.length} items to ${storeName}`);
              }
              resolve(errors.length === 0);
            }
          }
        };

        clearRequest.onerror = function(event) {
          console.error(`Error clearing ${storeName}:`, event.target.error);
          resolve(false);
        };

        transaction.onerror = function(event) {
          console.error(`Transaction error saving ${storeName}:`, event.target.error);
          resolve(false);
        };
      });
    });
  },

  // Public API methods
  loadComponents() { return this._loadFromStore('components'); },
  saveComponents(components) { return this._saveToStore('components', components); },

  loadLocations() { return this._loadFromStore('locations'); },
  saveLocations(locations) { return this._saveToStore('locations', locations); },

  loadDrawers() { return this._loadFromStore('drawers'); },
  saveDrawers(drawers) { return this._saveToStore('drawers', drawers); },

  loadCells() { return this._loadFromStore('cells'); },
  saveCells(cells) { return this._saveToStore('cells', cells); },

  loadCategories() { return this._loadFromStore('categories'); },
  saveCategories(categories) {
    // Convert array of strings to objects with id and name
    const categoryObjects = categories.map((name, index) => ({
      id: `cat-${index}`,
      name: name
    }));
    return this._saveToStore('categories', categoryObjects);
  },

  loadFootprints() { return this._loadFromStore('footprints'); },
  saveFootprints(footprints) {
    // Convert array of strings to objects with id and name
    const footprintObjects = footprints.map((name, index) => ({
      id: `fp-${index}`,
      name: name
    }));
    return this._saveToStore('footprints', footprintObjects);
  },

  loadLowStockConfig() {
    return this._loadFromStore('lowStockConfig').then(configItems => {
      // Convert array back to config object
      const config = {};
      configItems.forEach(item => {
        if (item.category && item.threshold !== undefined) {
          config[item.category] = item.threshold;
        }
      });
      return config;
    });
  },

  saveLowStockConfig(config) {
    // Convert config object to array
    const configArray = Object.entries(config).map(([category, threshold]) => ({
      id: `lowstock-${category.replace(/[^a-zA-Z0-9-_]/g, '_')}`,
      category,
      threshold
    }));
    return this._saveToStore('lowStockConfig', configArray);
  },

  // Clear single store
  clearStore(storeName) {
    const self = this;

    return this.init().then(initialized => {
      if (!initialized || !self.db) {
        console.log(`IndexedDB not available for clearing ${storeName}`);
        return false;
      }

      return new Promise((resolve, reject) => {
        const transaction = self.db.transaction(storeName, 'readwrite');
        const store = transaction.objectStore(storeName);
        const request = store.clear();

        transaction.oncomplete = function() {
          console.log(`Cleared ${storeName}`);
          resolve(true);
        };

        transaction.onerror = function(event) {
          console.error(`Error clearing ${storeName}:`, event.target.error);
          resolve(false);
        };
      });
    });
  },

  // Clear all stores
  clearAll() {
    const promises = this.stores.map(storeName => this.clearStore(storeName));
    return Promise.all(promises).then(results => 
      results.every(result => result === true)
    );
  }
};

console.log("idb.js loaded successfully with enhanced logging");