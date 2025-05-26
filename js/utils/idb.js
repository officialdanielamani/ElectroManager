// js/utils/idb.js - Bare minimum implementation
console.log("Loading idb.js...");

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

// Create a very simple IDB implementation
window.App.utils.idb = {
  db: null,
  dbName: 'electronicsInventory',
  dbVersion: 1, // Increase version number to trigger upgrade
  stores: ['components', 'locations', 'drawers', 'cells', 'categories', 'footprints', 'lowStockConfig'],

  // Initialize the database
  init: function () {

    // Check for IndexedDB support
    if (!window.indexedDB) {
      console.log("IndexedDB not supported in this browser");
      return Promise.resolve(false);
    }

    var self = this;

    // Return a promise for the database connection
    return new Promise(function (resolve, reject) {
      try {
        var request = indexedDB.open(self.dbName, self.dbVersion);

        // Handle database upgrades
        request.onupgradeneeded = function (event) {
          console.log("Upgrading database from version", event.oldVersion, "to", event.newVersion);
          var db = event.target.result;

          // Create object stores if they don't exist
          self.stores.forEach(function (storeName) {
            if (!db.objectStoreNames.contains(storeName)) {
              console.log("Creating store:", storeName);
              db.createObjectStore(storeName, { keyPath: 'id' });
            }
          });
        };

        // Handle successful connection
        request.onsuccess = function (event) {
          self.db = event.target.result;
          resolve(true);
        };

        // Handle connection errors
        request.onerror = function (event) {
          console.error("IndexedDB initialization error:", event.target.error);
          resolve(false);
        };
      } catch (err) {
        console.error("Error in IndexedDB initialization:", err);
        resolve(false);
      }
    });
  },

  // Load components from IndexedDB
  loadComponents: function () {
    return this._loadFromStore('components');
  },

  // Save components to IndexedDB
  saveComponents: function (components) {
    return this._saveToStore('components', components);
  },

  // Load locations from IndexedDB
  loadLocations: function () {
    return this._loadFromStore('locations');
  },

  // Save locations to IndexedDB
  saveLocations: function (locations) {
    return this._saveToStore('locations', locations);
  },

  // Load drawers from IndexedDB
  loadDrawers: function () {
    return this._loadFromStore('drawers');
  },

  // Save drawers to IndexedDB
  saveDrawers: function (drawers) {
    return this._saveToStore('drawers', drawers);
  },

  // Load cells from IndexedDB
  loadCells: function () {
    return this._loadFromStore('cells');
  },

  // Save cells to IndexedDB
  saveCells: function (cells) {
    return this._saveToStore('cells', cells);
  },

  // Load categories from IndexedDB
  loadCategories: function () {
    return this._loadFromStore('categories');
  },


  // Save categories to IndexedDB
  saveCategories: function (categories) {
    // Convert array of strings to array of objects with id property
    var categoryObjects = Array.isArray(categories) ? categories.map(function (name, index) {
      return { id: 'cat-' + index, name: name };
    }) : [];

    return this._saveToStore('categories', categoryObjects);
  },


  loadLowStockConfig: function () {
    return this._loadFromStore('lowStockConfig')
      .then(function (configItems) {
        // Convert array of items to configuration object
        var config = {};
        if (configItems && configItems.length > 0) {
          configItems.forEach(function (item) {
            if (item.category && item.threshold !== undefined) {
              config[item.category] = item.threshold;
            }
          });
        }
        return config;
      });
  },

  saveLowStockConfig: function (config) {
    // Convert object to array of entries with IDs for IndexedDB
    var configArray = [];

    for (var category in config) {
      if (config.hasOwnProperty(category) && category) {
        configArray.push({
          id: 'lowstock-' + category.replace(/[^a-zA-Z0-9-_]/g, '_'),  // Create a unique ID for each entry
          category: category,
          threshold: config[category]
        });
      }
    }

    return this._saveToStore('lowStockConfig', configArray);
  },


  // Load footprints from IndexedDB
  loadFootprints: function () {
    return this._loadFromStore('footprints');
  },

  // Save footprints to IndexedDB
  saveFootprints: function (footprints) {
    // Convert array of strings to array of objects with id property
    var footprintObjects = Array.isArray(footprints) ? footprints.map(function (name, index) {
      return { id: 'fp-' + index, name: name };
    }) : [];

    return this._saveToStore('footprints', footprintObjects);
  },

  // Generic method to load data from a store
  _loadFromStore: function (storeName) {
    var self = this;

    // Make sure DB is initialized
    return this.init()
      .then(function (initialized) {
        if (!initialized || !self.db) {
          console.log("IndexedDB not available for loading", storeName);
          return Promise.resolve([]);
        }

        return new Promise(function (resolve, reject) {
          try {
            var transaction = self.db.transaction(storeName, 'readonly');
            var store = transaction.objectStore(storeName);
            var request = store.getAll();

            request.onsuccess = function () {
              console.log("Loaded", request.result.length, "items from", storeName);

              // For categories and footprints, convert objects to strings array
              if (storeName === 'categories' || storeName === 'footprints') {
                var result = request.result.map(function (item) {
                  return item.name;
                });
                resolve(result);
              } else {
                resolve(request.result);
              }
            };

            request.onerror = function (event) {
              console.error("Error loading from", storeName, event.target.error);
              resolve([]);
            };

            transaction.onerror = function (event) {
              console.error("Transaction error when loading", storeName, event.target.error);
              resolve([]);
            };
          } catch (err) {
            console.error("Error in _loadFromStore for", storeName, err);
            resolve([]);
          }
        });
      });
  },

  // Generic method to save data to a store
  _saveToStore: function (storeName, items) {
    var self = this;

    // Make sure DB is initialized
    return this.init()
      .then(function (initialized) {
        if (!initialized || !self.db) {
          console.log("IndexedDB not available for saving", storeName);
          return Promise.resolve(false);
        }

        if (!Array.isArray(items)) {
          console.error("Items must be an array for", storeName);
          return Promise.resolve(false);
        }

        return new Promise(function (resolve, reject) {
          try {
            var transaction = self.db.transaction(storeName, 'readwrite');
            var store = transaction.objectStore(storeName);

            // Clear existing items
            var clearRequest = store.clear();

            clearRequest.onsuccess = function () {
              // Add all items
              items.forEach(function (item) {
                if (item && (item.id || storeName === 'categories' || storeName === 'footprints')) {
                  store.put(item);
                }
              });
            };

            transaction.oncomplete = function () {
              console.log("Saved", items.length, "items to", storeName);
              resolve(true);
            };

            transaction.onerror = function (event) {
              console.error("Transaction error when saving", storeName, event.target.error);
              resolve(false);
            };
          } catch (err) {
            console.error("Error in _saveToStore for", storeName, err);
            resolve(false);
          }
        });
      });
  },

  // Clear all data from a store
  clearStore: function (storeName) {
    var self = this;

    // Make sure DB is initialized
    return this.init()
      .then(function (initialized) {
        if (!initialized || !self.db) {
          console.log("IndexedDB not available for clearing", storeName);
          return Promise.resolve(false);
        }

        return new Promise(function (resolve, reject) {
          try {
            var transaction = self.db.transaction(storeName, 'readwrite');
            var store = transaction.objectStore(storeName);
            var request = store.clear();

            transaction.oncomplete = function () {
              console.log("Cleared", storeName);
              resolve(true);
            };

            transaction.onerror = function (event) {
              console.error("Error clearing", storeName, event.target.error);
              resolve(false);
            };
          } catch (err) {
            console.error("Error in clearStore for", storeName, err);
            resolve(false);
          }
        });
      });
  },

  // Clear all stores
  clearAll: function () {
    var self = this;
    var promises = [];

    // Clear each store
    this.stores.forEach(function (storeName) {
      promises.push(self.clearStore(storeName));
    });

    // Return a promise that resolves when all stores are cleared
    return Promise.all(promises)
      .then(function (results) {
        return results.every(function (result) { return result; });
      });
  }
};

console.log("idb loaded");