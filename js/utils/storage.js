// js/utils/storage.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Storage utility functions for the Electronics Inventory App.
 * Handles saving and loading data from IndexedDB.
 */
window.App.utils.storage = (() => {
    // Database name and version
    const DB_NAME = 'ElectroManager';
    const DB_VERSION = 1;
    
    // Store names for different data types
    const STORES = {
        COMPONENTS: 'components',
        CONFIG: 'config',
        LOCATIONS: 'locations',
        DRAWERS: 'drawers',
        CELLS: 'cells'
    };
    
    // Config keys
    const CONFIG_KEYS = {
        CATEGORIES: 'categories',
        VIEW_MODE: 'viewMode',
        LOW_STOCK_CONFIG: 'lowStockConfig',
        CURRENCY_SYMBOL: 'currencySymbol',
        SHOW_TOTAL_VALUE: 'showTotalValue',
        FOOTPRINTS: 'footprints',
        ITEMS_PER_PAGE: 'itemsPerPage',
        THEME: 'theme'
    };
    
    // Private methods for database operations
    const _db = {
        // Reference to the database
        instance: null,
        
        /**
         * Open the database connection
         * @returns {Promise<IDBDatabase>} The database instance
         */
        open() {
            return new Promise((resolve, reject) => {
                if (this.instance) {
                    resolve(this.instance);
                    return;
                }
                
                const request = indexedDB.open(DB_NAME, DB_VERSION);
                
                // Handle upgrade needed (first time or version change)
                request.onupgradeneeded = (event) => {
                    const db = event.target.result;
                    
                    // Create object stores if they don't exist
                    if (!db.objectStoreNames.contains(STORES.COMPONENTS)) {
                        const componentsStore = db.createObjectStore(STORES.COMPONENTS, { keyPath: 'id' });
                        // Create indexes for faster queries
                        componentsStore.createIndex('category', 'category', { unique: false });
                        componentsStore.createIndex('type', 'type', { unique: false });
                    }
                    
                    if (!db.objectStoreNames.contains(STORES.CONFIG)) {
                        db.createObjectStore(STORES.CONFIG, { keyPath: 'key' });
                    }
                    
                    if (!db.objectStoreNames.contains(STORES.LOCATIONS)) {
                        db.createObjectStore(STORES.LOCATIONS, { keyPath: 'id' });
                    }
                    
                    if (!db.objectStoreNames.contains(STORES.DRAWERS)) {
                        const drawersStore = db.createObjectStore(STORES.DRAWERS, { keyPath: 'id' });
                        drawersStore.createIndex('locationId', 'locationId', { unique: false });
                    }
                    
                    if (!db.objectStoreNames.contains(STORES.CELLS)) {
                        const cellsStore = db.createObjectStore(STORES.CELLS, { keyPath: 'id' });
                        cellsStore.createIndex('drawerId', 'drawerId', { unique: false });
                    }
                };
                
                request.onsuccess = (event) => {
                    this.instance = event.target.result;
                    console.log('IndexedDB connection opened successfully');
                    resolve(this.instance);
                };
                
                request.onerror = (event) => {
                    console.error('Error opening IndexedDB:', event.target.error);
                    reject(event.target.error);
                };
            });
        },
        
        /**
         * Close the database connection
         */
        close() {
            if (this.instance) {
                this.instance.close();
                this.instance = null;
                console.log('IndexedDB connection closed');
            }
        },
        
        /**
         * Get all items from a store
         * @param {string} storeName The name of the store
         * @returns {Promise<Array>} Array of items
         */
        getAll(storeName) {
            return this.open()
                .then(db => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readonly');
                        const store = transaction.objectStore(storeName);
                        const request = store.getAll();
                        
                        request.onsuccess = () => {
                            resolve(request.result);
                        };
                        
                        request.onerror = (event) => {
                            console.error(`Error getting all items from ${storeName}:`, event.target.error);
                            reject(event.target.error);
                        };
                    });
                })
                .catch(error => {
                    console.error(`Failed to get items from ${storeName}:`, error);
                    return [];
                });
        },
        
        /**
         * Get an item by key from a store
         * @param {string} storeName The name of the store
         * @param {string|number} key The key to look up
         * @returns {Promise<Object|null>} The item or null if not found
         */
        getByKey(storeName, key) {
            return this.open()
                .then(db => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readonly');
                        const store = transaction.objectStore(storeName);
                        const request = store.get(key);
                        
                        request.onsuccess = () => {
                            resolve(request.result);
                        };
                        
                        request.onerror = (event) => {
                            console.error(`Error getting item by key from ${storeName}:`, event.target.error);
                            reject(event.target.error);
                        };
                    });
                })
                .catch(error => {
                    console.error(`Failed to get item by key from ${storeName}:`, error);
                    return null;
                });
        },
        
        /**
         * Put (add or update) items in a store
         * @param {string} storeName The name of the store
         * @param {Array|Object} items The item(s) to put
         * @returns {Promise<boolean>} True if successful
         */
        putItems(storeName, items) {
            const itemsArray = Array.isArray(items) ? items : [items];
            
            if (itemsArray.length === 0) {
                return Promise.resolve(true);
            }
            
            return this.open()
                .then(db => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readwrite');
                        const store = transaction.objectStore(storeName);
                        
                        // Set up transaction event handlers
                        transaction.oncomplete = () => {
                            resolve(true);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error(`Error putting items in ${storeName}:`, event.target.error);
                            reject(event.target.error);
                        };
                        
                        // Add each item to the store
                        itemsArray.forEach(item => {
                            store.put(item);
                        });
                    });
                })
                .catch(error => {
                    console.error(`Failed to put items in ${storeName}:`, error);
                    return false;
                });
        },
        
        /**
         * Delete items from a store by keys
         * @param {string} storeName The name of the store
         * @param {Array|string|number} keys The key(s) to delete
         * @returns {Promise<boolean>} True if successful
         */
        deleteItems(storeName, keys) {
            const keysArray = Array.isArray(keys) ? keys : [keys];
            
            if (keysArray.length === 0) {
                return Promise.resolve(true);
            }
            
            return this.open()
                .then(db => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readwrite');
                        const store = transaction.objectStore(storeName);
                        
                        // Set up transaction event handlers
                        transaction.oncomplete = () => {
                            resolve(true);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error(`Error deleting items from ${storeName}:`, event.target.error);
                            reject(event.target.error);
                        };
                        
                        // Delete each item from the store
                        keysArray.forEach(key => {
                            store.delete(key);
                        });
                    });
                })
                .catch(error => {
                    console.error(`Failed to delete items from ${storeName}:`, error);
                    return false;
                });
        },
        
        /**
         * Clear a store (delete all items)
         * @param {string} storeName The name of the store
         * @returns {Promise<boolean>} True if successful
         */
        clearStore(storeName) {
            return this.open()
                .then(db => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readwrite');
                        const store = transaction.objectStore(storeName);
                        const request = store.clear();
                        
                        request.onsuccess = () => {
                            resolve(true);
                        };
                        
                        request.onerror = (event) => {
                            console.error(`Error clearing store ${storeName}:`, event.target.error);
                            reject(event.target.error);
                        };
                    });
                })
                .catch(error => {
                    console.error(`Failed to clear store ${storeName}:`, error);
                    return false;
                });
        }
    };
    
    // Migration functions to help with transition from localStorage
    const _migration = {
        /**
         * Check if data exists in localStorage
         * @returns {boolean} True if localStorage has data
         */
        hasLocalStorageData() {
            return !!localStorage.getItem('electronicsComponents') ||
                   !!localStorage.getItem('electronicsCategories') ||
                   !!localStorage.getItem('electronicsLocations') ||
                   !!localStorage.getItem('electronicsDrawers') ||
                   !!localStorage.getItem('electronicsCells');
        },
        
        /**
         * Migrate data from localStorage to IndexedDB
         * @returns {Promise<boolean>} True if migration was successful
         */
        migrateFromLocalStorage() {
            console.log('Starting migration from localStorage to IndexedDB...');
            
            // Helper to safely parse JSON from localStorage
            const safeParseJSON = (key, defaultValue = null) => {
                try {
                    const value = localStorage.getItem(key);
                    return value ? JSON.parse(value) : defaultValue;
                } catch (e) {
                    console.error(`Error parsing localStorage key ${key}:`, e);
                    return defaultValue;
                }
            };
            
            // Migrate components
            const components = safeParseJSON('electronicsComponents', []);
            
            // Migrate configuration
            const configItems = [
                { key: CONFIG_KEYS.CATEGORIES, value: safeParseJSON('electronicsCategories', []) },
                { key: CONFIG_KEYS.VIEW_MODE, value: localStorage.getItem('electronicsViewMode') || 'table' },
                { key: CONFIG_KEYS.LOW_STOCK_CONFIG, value: safeParseJSON('electronicsLowStockConfig', {}) },
                { key: CONFIG_KEYS.CURRENCY_SYMBOL, value: localStorage.getItem('electronicsCurrencySymbol') || '$' },
                { key: CONFIG_KEYS.SHOW_TOTAL_VALUE, value: localStorage.getItem('electronicsShowTotalValue') === 'true' },
                { key: CONFIG_KEYS.FOOTPRINTS, value: safeParseJSON('electronicsFootprints', []) },
                { key: CONFIG_KEYS.ITEMS_PER_PAGE, value: safeParseJSON('electronicsItemsPerPage', 'all') },
                { key: CONFIG_KEYS.THEME, value: localStorage.getItem('electronicsTheme') || 'light' }
            ];
            
            // Migrate locations, drawers, and cells
            const locations = safeParseJSON('electronicsLocations', []);
            const drawers = safeParseJSON('electronicsDrawers', []);
            const cells = safeParseJSON('electronicsCells', []);
            
            // Normalize components for storage
            const normalizedComponents = components.map(comp => {
                // Create a new object for each component
                const normalizedComp = { ...comp };
                
                // Ensure price and quantity are numbers
                normalizedComp.price = Number(comp.price) || 0;
                normalizedComp.quantity = Number(comp.quantity) || 0;
                
                // Ensure flag fields exist
                normalizedComp.favorite = !!comp.favorite;
                normalizedComp.bookmark = !!comp.bookmark;
                normalizedComp.star = !!comp.star;
                
                // Ensure locationInfo is properly formatted
                if (!comp.locationInfo || typeof comp.locationInfo === 'string' || comp.locationInfo === '[object Object]') {
                    normalizedComp.locationInfo = { locationId: '', details: '' };
                }
                
                // Ensure storageInfo is properly formatted
                if (!comp.storageInfo || typeof comp.storageInfo === 'string' || comp.storageInfo === '[object Object]') {
                    normalizedComp.storageInfo = { locationId: '', drawerId: '', cells: [] };
                } else {
                    // Handle partial storageInfo object (may be missing 'cells' array)
                    normalizedComp.storageInfo = {
                        locationId: comp.storageInfo.locationId || '',
                        drawerId: comp.storageInfo.drawerId || '',
                        cells: Array.isArray(comp.storageInfo.cells) ? comp.storageInfo.cells : []
                    };
                    
                    // Handle backward compatibility - convert cellId to cells array
                    if (comp.storageInfo.cellId && !normalizedComp.storageInfo.cells.includes(comp.storageInfo.cellId)) {
                        normalizedComp.storageInfo.cells.push(comp.storageInfo.cellId);
                    }
                }
                
                return normalizedComp;
            });
            
            // Normalize cells for storage
            const normalizedCells = cells.map(cell => ({
                ...cell,
                available: cell.available !== undefined ? cell.available : true
            }));
            
            // Save all migrated data to IndexedDB
            return Promise.all([
                _db.putItems(STORES.COMPONENTS, normalizedComponents),
                _db.putItems(STORES.CONFIG, configItems),
                _db.putItems(STORES.LOCATIONS, locations),
                _db.putItems(STORES.DRAWERS, drawers),
                _db.putItems(STORES.CELLS, normalizedCells)
            ])
                .then(() => {
                    console.log('Migration from localStorage to IndexedDB completed successfully!');
                    return true;
                })
                .catch(error => {
                    console.error('Failed to migrate data from localStorage:', error);
                    return false;
                });
        }
    };
    
    // Public API
    return {
        /**
         * Initialize the storage system
         * @returns {Promise<boolean>} True if initialization is successful
         */
        init() {
            return _db.open()
                .then(() => {
                    // Check if we need to migrate data from localStorage
                    if (_migration.hasLocalStorageData()) {
                        return _migration.migrateFromLocalStorage();
                    }
                    return true;
                })
                .catch(error => {
                    console.error('Failed to initialize storage:', error);
                    return false;
                });
        },
        
        /**
         * Load components from IndexedDB
         * @returns {Promise<Array>} Array of component objects or empty array if none found
         */
        loadComponents() {
            return _db.getAll(STORES.COMPONENTS)
                .then(components => {
                    console.log('Loaded components from IndexedDB:', components.length);
                    return components;
                });
        },
        
        /**
         * Save components to IndexedDB
         * @param {Array} components Array of component objects to save
         * @returns {Promise<boolean>} True if saved successfully, false otherwise
         */
        saveComponents(components) {
            if (!Array.isArray(components)) {
                console.error('saveComponents: Expected an array, got:', typeof components);
                return Promise.resolve(false);
            }
            
            // Ensure proper formatting before saving
            const componentsToSave = components.map(comp => ({
                ...comp,
                price: Number(comp.price) || 0,
                quantity: Number(comp.quantity) || 0
            }));
            
            return _db.putItems(STORES.COMPONENTS, componentsToSave)
                .then(success => {
                    if (success) {
                        console.log('Saved components to IndexedDB:', componentsToSave.length);
                    }
                    return success;
                });
        },
        
        /**
         * Load locations from IndexedDB
         * @returns {Promise<Array>} Array of location objects or empty array if none found
         */
        loadLocations() {
            return _db.getAll(STORES.LOCATIONS)
                .then(locations => {
                    console.log('Loaded locations from IndexedDB:', locations.length);
                    return locations;
                });
        },
        
        /**
         * Save locations to IndexedDB
         * @param {Array} locations Array of location objects to save
         * @returns {Promise<boolean>} True if saved successfully, false otherwise
         */
        saveLocations(locations) {
            if (!Array.isArray(locations)) {
                console.error('saveLocations: Expected an array, got:', typeof locations);
                return Promise.resolve(false);
            }
            
            return _db.putItems(STORES.LOCATIONS, locations)
                .then(success => {
                    if (success) {
                        console.log('Saved locations to IndexedDB:', locations.length);
                    }
                    return success;
                });
        },
        
        /**
         * Load drawers from IndexedDB
         * @returns {Promise<Array>} Array of drawer objects or empty array if none found
         */
        loadDrawers() {
            return _db.getAll(STORES.DRAWERS)
                .then(drawers => {
                    console.log('Loaded drawers from IndexedDB:', drawers.length);
                    return drawers;
                });
        },
        
        /**
         * Save drawers to IndexedDB
         * @param {Array} drawers Array of drawer objects to save
         * @returns {Promise<boolean>} True if saved successfully, false otherwise
         */
        saveDrawers(drawers) {
            if (!Array.isArray(drawers)) {
                console.error('saveDrawers: Expected an array, got:', typeof drawers);
                return Promise.resolve(false);
            }
            
            return _db.putItems(STORES.DRAWERS, drawers)
                .then(success => {
                    if (success) {
                        console.log('Saved drawers to IndexedDB:', drawers.length);
                    }
                    return success;
                });
        },
        
        /**
         * Load cells from IndexedDB
         * @returns {Promise<Array>} Array of cell objects or empty array if none found
         */
        loadCells() {
            return _db.getAll(STORES.CELLS)
                .then(cells => {
                    // Ensure all cells have the available property
                    const normalizedCells = cells.map(cell => ({
                        ...cell,
                        available: cell.available !== undefined ? cell.available : true
                    }));
                    
                    console.log('Loaded cells from IndexedDB:', normalizedCells.length);
                    return normalizedCells;
                });
        },
        
        /**
         * Save cells to IndexedDB
         * @param {Array} cells Array of cell objects to save
         * @returns {Promise<boolean>} True if saved successfully, false otherwise
         */
        saveCells(cells) {
            if (!Array.isArray(cells)) {
                console.error('saveCells: Expected an array, got:', typeof cells);
                return Promise.resolve(false);
            }
            
            return _db.putItems(STORES.CELLS, cells)
                .then(success => {
                    if (success) {
                        console.log('Saved cells to IndexedDB:', cells.length);
                    }
                    return success;
                });
        },
        
        /**
         * Load configuration (categories, view mode, etc.) from IndexedDB
         * @returns {Promise<Object>} Configuration object with default values if none found
         */
        loadConfig() {
            // Create default config object
            const defaultConfig = {
                categories: [],
                viewMode: 'table',
                lowStockConfig: {},
                currencySymbol: 'RM',
                showTotalValue: false,
                footprints: [],
                itemsPerPage: 'all',
                theme: 'dark'
            };
            
            return _db.getAll(STORES.CONFIG)
                .then(configItems => {
                    if (!configItems || configItems.length === 0) {
                        console.log('No config found in IndexedDB, using defaults');
                        return defaultConfig;
                    }
                    
                    // Convert array of {key, value} objects to a config object
                    const config = { ...defaultConfig };
                    configItems.forEach(item => {
                        config[item.key] = item.value;
                    });
                    
                    console.log('Loaded config from IndexedDB');
                    return config;
                })
                .catch(error => {
                    console.error('Error loading config from IndexedDB:', error);
                    return defaultConfig;
                });
        },
        
        /**
         * Save configuration to IndexedDB
         * @param {Object} config Configuration object to save
         * @returns {Promise<boolean>} True if saved successfully, false otherwise
         */
        saveConfig(config) {
            if (!config || typeof config !== 'object') {
                console.error('saveConfig: Expected an object, got:', typeof config);
                return Promise.resolve(false);
            }
            
            // Convert config object to array of {key, value} objects
            const configItems = [];
            
            if (Array.isArray(config.categories)) {
                configItems.push({ key: CONFIG_KEYS.CATEGORIES, value: config.categories });
            }
            
            if (config.viewMode === 'table' || config.viewMode === 'card') {
                configItems.push({ key: CONFIG_KEYS.VIEW_MODE, value: config.viewMode });
            }
            
            if (config.lowStockConfig && typeof config.lowStockConfig === 'object') {
                configItems.push({ key: CONFIG_KEYS.LOW_STOCK_CONFIG, value: config.lowStockConfig });
            }
            
            if (config.currencySymbol && typeof config.currencySymbol === 'string') {
                configItems.push({ key: CONFIG_KEYS.CURRENCY_SYMBOL, value: config.currencySymbol });
            }
            
            if (typeof config.showTotalValue === 'boolean') {
                configItems.push({ key: CONFIG_KEYS.SHOW_TOTAL_VALUE, value: config.showTotalValue });
            }
            
            if (config.theme && typeof config.theme === 'string') {
                configItems.push({ key: CONFIG_KEYS.THEME, value: config.theme });
            }
            
            if (Array.isArray(config.footprints)) {
                configItems.push({ key: CONFIG_KEYS.FOOTPRINTS, value: config.footprints });
            }
            
            if (config.itemsPerPage !== undefined) {
                configItems.push({ key: CONFIG_KEYS.ITEMS_PER_PAGE, value: config.itemsPerPage });
            }
            
            return _db.putItems(STORES.CONFIG, configItems)
                .then(success => {
                    if (success) {
                        console.log('Saved config to IndexedDB');
                    }
                    return success;
                });
        },
        
        /**
         * Clear all electronics inventory related data from IndexedDB
         * @returns {Promise<boolean>} True if cleared successfully, false otherwise
         */
        clearStorage() {
            const clearAllStores = [
                _db.clearStore(STORES.COMPONENTS),
                _db.clearStore(STORES.CONFIG),
                _db.clearStore(STORES.LOCATIONS),
                _db.clearStore(STORES.DRAWERS),
                _db.clearStore(STORES.CELLS)
            ];
            
            return Promise.all(clearAllStores)
                .then(() => {
                    console.log('All IndexedDB stores cleared');
                    // Also clear any remaining localStorage data
                    localStorage.removeItem('electronicsComponents');
                    localStorage.removeItem('electronicsCategories');
                    localStorage.removeItem('electronicsViewMode');
                    localStorage.removeItem('electronicsLowStockConfig');
                    localStorage.removeItem('electronicsCurrencySymbol');
                    localStorage.removeItem('electronicsShowTotalValue');
                    localStorage.removeItem('electronicsFootprints');
                    localStorage.removeItem('electronicsLocations');
                    localStorage.removeItem('electronicsDrawers');
                    localStorage.removeItem('electronicsCells');
                    localStorage.removeItem('electronicsItemsPerPage');
                    localStorage.removeItem('electronicsTheme');
                    return true;
                })
                .catch(error => {
                    console.error('Error clearing IndexedDB storage:', error);
                    return false;
                });
        },
        
        /**
         * For debugging - dump all IndexedDB store information to console
         */
        debugStorage() {
            console.log('==== Electronics Inventory IndexedDB Debug ====');
            
            Promise.all([
                _db.getAll(STORES.COMPONENTS),
                _db.getAll(STORES.CONFIG),
                _db.getAll(STORES.LOCATIONS),
                _db.getAll(STORES.DRAWERS),
                _db.getAll(STORES.CELLS)
            ])
                .then(([components, config, locations, drawers, cells]) => {
                    console.log('Components:', components);
                    console.log('Config:', config);
                    console.log('Locations:', locations);
                    console.log('Drawers:', drawers);
                    console.log('Cells:', cells);
                    console.log('=================================================');
                })
                .catch(error => {
                    console.error('Error debugging IndexedDB storage:', error);
                });
        }
    };
})();

// Initialize the storage system when the script loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing IndexedDB storage...');
    window.App.utils.storage.init()
        .then(success => {
            if (success) {
                console.log('IndexedDB storage initialized successfully');
            } else {
                console.warn('IndexedDB storage initialization had issues');
            }
        });
});

console.log("IndexedDB storage utilities loaded.");