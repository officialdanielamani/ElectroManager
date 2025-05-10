// js/utils/storage.js - Modified to work with ES5 for compatibility
console.log("Loading storage.js...");

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Storage utilities with IndexedDB for core data and localStorage for settings
 */
window.App.utils.storage = {
    // Flag to track if IndexedDB is available
    useIndexedDB: null,
    
    /**
     * Initialize storage and check IndexedDB availability
     */
    init: function() {
        var self = this;
        
        // Only run once
        if (this.useIndexedDB !== null) {
            return Promise.resolve(this.useIndexedDB);
        }
        
        // Check for idb object
        var idb = window.App.utils.idb;
        if (!idb || typeof idb.init !== 'function') {
            console.log("IndexedDB utility not available, using localStorage for all data");
            this.useIndexedDB = false;
            return Promise.resolve(false);
        }
        
        // Try to initialize IndexedDB
        return idb.init()
            .then(function(initialized) {
                self.useIndexedDB = initialized;
                console.log("Storage initialized:", initialized ? "Using IndexedDB" : "Using localStorage");
                return initialized;
            })
            .catch(function(err) {
                console.error("Error initializing storage:", err);
                self.useIndexedDB = false;
                return false;
            });
    },
    
    /*** COMPONENTS ***/
    
    loadComponents: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadComponents()
                        .catch(function(err) {
                            console.error("Error loading components from IndexedDB:", err);
                            return self._loadComponentsFromLocalStorage();
                        });
                }
                
                // Otherwise use localStorage
                return self._loadComponentsFromLocalStorage();
            });
    },
    
    _loadComponentsFromLocalStorage: function() {
        try {
            var json = localStorage.getItem('electronicsComponents');
            var components = json ? JSON.parse(json) : [];
            console.log("Loaded", components.length, "components from localStorage");
            return components;
        } catch (err) {
            console.error("Error loading components from localStorage:", err);
            return [];
        }
    },
    
    saveComponents: function(components) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveComponents(components)
                        .catch(function(err) {
                            console.error("Error saving components to IndexedDB:", err);
                            return self._saveComponentsToLocalStorage(components);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveComponentsToLocalStorage(components);
            });
    },
    
    _saveComponentsToLocalStorage: function(components) {
        try {
            localStorage.setItem('electronicsComponents', JSON.stringify(components));
            console.log("Saved", components.length, "components to localStorage");
            return true;
        } catch (err) {
            console.error("Error saving components to localStorage:", err);
            return false;
        }
    },
    
    /*** LOCATIONS ***/
    
    loadLocations: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadLocations()
                        .catch(function(err) {
                            console.error("Error loading locations from IndexedDB:", err);
                            return self._loadLocationsFromLocalStorage();
                        });
                }
                
                // Otherwise use localStorage
                return self._loadLocationsFromLocalStorage();
            });
    },
    
    _loadLocationsFromLocalStorage: function() {
        try {
            var json = localStorage.getItem('electronicsLocations');
            var locations = json ? JSON.parse(json) : [];
            console.log("Loaded", locations.length, "locations from localStorage");
            return locations;
        } catch (err) {
            console.error("Error loading locations from localStorage:", err);
            return [];
        }
    },
    
    saveLocations: function(locations) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveLocations(locations)
                        .catch(function(err) {
                            console.error("Error saving locations to IndexedDB:", err);
                            return self._saveLocationsToLocalStorage(locations);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveLocationsToLocalStorage(locations);
            });
    },
    
    _saveLocationsToLocalStorage: function(locations) {
        try {
            localStorage.setItem('electronicsLocations', JSON.stringify(locations));
            console.log("Saved", locations.length, "locations to localStorage");
            return true;
        } catch (err) {
            console.error("Error saving locations to localStorage:", err);
            return false;
        }
    },
    
    /*** DRAWERS ***/
    
    loadDrawers: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadDrawers()
                        .catch(function(err) {
                            console.error("Error loading drawers from IndexedDB:", err);
                            return self._loadDrawersFromLocalStorage();
                        });
                }
                
                // Otherwise use localStorage
                return self._loadDrawersFromLocalStorage();
            });
    },
    
    _loadDrawersFromLocalStorage: function() {
        try {
            var json = localStorage.getItem('electronicsDrawers');
            var drawers = json ? JSON.parse(json) : [];
            console.log("Loaded", drawers.length, "drawers from localStorage");
            return drawers;
        } catch (err) {
            console.error("Error loading drawers from localStorage:", err);
            return [];
        }
    },
    
    saveDrawers: function(drawers) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveDrawers(drawers)
                        .catch(function(err) {
                            console.error("Error saving drawers to IndexedDB:", err);
                            return self._saveDrawersToLocalStorage(drawers);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveDrawersToLocalStorage(drawers);
            });
    },
    
    _saveDrawersToLocalStorage: function(drawers) {
        try {
            localStorage.setItem('electronicsDrawers', JSON.stringify(drawers));
            console.log("Saved", drawers.length, "drawers to localStorage");
            return true;
        } catch (err) {
            console.error("Error saving drawers to localStorage:", err);
            return false;
        }
    },
    
    /*** CELLS ***/
    
    loadCells: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadCells()
                        .catch(function(err) {
                            console.error("Error loading cells from IndexedDB:", err);
                            return self._loadCellsFromLocalStorage();
                        });
                }
                
                // Otherwise use localStorage
                return self._loadCellsFromLocalStorage();
            });
    },
    
    _loadCellsFromLocalStorage: function() {
        try {
            var json = localStorage.getItem('electronicsCells');
            var cells = json ? JSON.parse(json) : [];
            
            // Ensure all cells have the 'available' property
            cells = cells.map(function(cell) {
                return {
                    available: true,  // Default value
                    ...cell
                };
            });
            
            console.log("Loaded", cells.length, "cells from localStorage");
            return cells;
        } catch (err) {
            console.error("Error loading cells from localStorage:", err);
            return [];
        }
    },
    
    saveCells: function(cells) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveCells(cells)
                        .catch(function(err) {
                            console.error("Error saving cells to IndexedDB:", err);
                            return self._saveCellsToLocalStorage(cells);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveCellsToLocalStorage(cells);
            });
    },
    
    _saveCellsToLocalStorage: function(cells) {
        try {
            localStorage.setItem('electronicsCells', JSON.stringify(cells));
            console.log("Saved", cells.length, "cells to localStorage");
            return true;
        } catch (err) {
            console.error("Error saving cells to localStorage:", err);
            return false;
        }
    },
    
    /*** CONFIG - Always use localStorage ***/
    
    loadConfig: function() {
        // Create default config object
        var defaultConfig = {
            categories: [],
            viewMode: 'table',
            lowStockConfig: {},
            currencySymbol: 'RM',
            showTotalValue: false,
            footprints: [],
            itemsPerPage: 'all',
            theme: 'dark'
        };

        try {
            // Load categories
            var savedCategories = localStorage.getItem('electronicsCategories');
            if (savedCategories) {
                defaultConfig.categories = JSON.parse(savedCategories);
            }

            // Load view mode
            var savedViewMode = localStorage.getItem('electronicsViewMode');
            if (savedViewMode && (savedViewMode === 'table' || savedViewMode === 'card')) {
                defaultConfig.viewMode = savedViewMode;
            }

            // Load low stock configuration
            var savedLowStockConfig = localStorage.getItem('electronicsLowStockConfig');
            if (savedLowStockConfig) {
                defaultConfig.lowStockConfig = JSON.parse(savedLowStockConfig);
            }

            // Load currency symbol
            var savedCurrency = localStorage.getItem('electronicsCurrencySymbol');
            if (savedCurrency) {
                defaultConfig.currencySymbol = savedCurrency;
            }

            // Load footprints
            var savedFootprints = localStorage.getItem('electronicsFootprints');
            if (savedFootprints) {
                defaultConfig.footprints = JSON.parse(savedFootprints);
            }

            // Load items per page setting
            var savedItemsPerPage = localStorage.getItem('electronicsItemsPerPage');
            if (savedItemsPerPage) {
                defaultConfig.itemsPerPage = JSON.parse(savedItemsPerPage);
            }

            // Load show total value setting
            var savedShowTotalValue = localStorage.getItem('electronicsShowTotalValue');
            // Check for 'true' string as localStorage stores strings
            defaultConfig.showTotalValue = savedShowTotalValue === 'true';

            // Load theme setting
            var savedTheme = localStorage.getItem('electronicsTheme');
            if (savedTheme) {
                defaultConfig.theme = savedTheme;
            }
            
            console.log("Config loaded from localStorage");
            return defaultConfig;
        } catch (err) {
            console.error("Error loading config from localStorage:", err);
            return defaultConfig;
        }
    },
    
    saveConfig: function(config) {
        try {
            if (config && typeof config === 'object') {
                // Save categories
                if (Array.isArray(config.categories)) {
                    localStorage.setItem('electronicsCategories', JSON.stringify(config.categories));
                }

                // Save view mode
                if (config.viewMode === 'table' || config.viewMode === 'card') {
                    localStorage.setItem('electronicsViewMode', config.viewMode);
                }

                // Save low stock configuration
                if (config.lowStockConfig && typeof config.lowStockConfig === 'object') {
                    localStorage.setItem('electronicsLowStockConfig', JSON.stringify(config.lowStockConfig));
                }

                // Save currency symbol
                if (config.currencySymbol && typeof config.currencySymbol === 'string') {
                    localStorage.setItem('electronicsCurrencySymbol', config.currencySymbol);
                }

                // Save show total value setting
                if (typeof config.showTotalValue === 'boolean') {
                    // Store boolean as string 'true' or 'false'
                    localStorage.setItem('electronicsShowTotalValue', config.showTotalValue.toString());
                }

                // Save theme setting
                if (config.theme && typeof config.theme === 'string') {
                    localStorage.setItem('electronicsTheme', config.theme);
                }

                // Save footprints
                if (Array.isArray(config.footprints)) {
                    localStorage.setItem('electronicsFootprints', JSON.stringify(config.footprints));
                }

                // Save items per page setting
                if (config.itemsPerPage !== undefined) {
                    localStorage.setItem('electronicsItemsPerPage', JSON.stringify(config.itemsPerPage));
                }

                console.log("Config saved to localStorage");
                return true;
            }
        } catch (err) {
            console.error("Error saving config to localStorage:", err);
        }
        return false;
    },
    
    /*** UTILITY FUNCTIONS ***/
    
    clearStorage: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                var promises = [];
                
                // Clear IndexedDB if available
                if (useIndexedDB) {
                    promises.push(window.App.utils.idb.clearAll());
                }
                
                // Always clear localStorage (synchronous)
                try {
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
                    console.log("LocalStorage cleared");
                } catch (err) {
                    console.error("Error clearing localStorage:", err);
                    return false;
                }
                
                // Wait for all promises to resolve
                return Promise.all(promises)
                    .then(function() {
                        console.log("All storage cleared");
                        return true;
                    })
                    .catch(function(err) {
                        console.error("Error clearing all storage:", err);
                        return false;
                    });
            });
    },
    
    migrateToIndexedDB: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                if (!useIndexedDB) {
                    console.log("IndexedDB not available for migration");
                    return false;
                }
                
                var promises = [];
                var idb = window.App.utils.idb;
                
                // Migrate components
                var components = self._loadComponentsFromLocalStorage();
                if (components.length > 0) {
                    promises.push(idb.saveComponents(components)
                        .then(function(success) {
                            return { type: 'components', count: components.length, success: success };
                        }));
                }
                
                // Migrate locations
                var locations = self._loadLocationsFromLocalStorage();
                if (locations.length > 0) {
                    promises.push(idb.saveLocations(locations)
                        .then(function(success) {
                            return { type: 'locations', count: locations.length, success: success };
                        }));
                }
                
                // Migrate drawers
                var drawers = self._loadDrawersFromLocalStorage();
                if (drawers.length > 0) {
                    promises.push(idb.saveDrawers(drawers)
                        .then(function(success) {
                            return { type: 'drawers', count: drawers.length, success: success };
                        }));
                }
                
                // Migrate cells
                var cells = self._loadCellsFromLocalStorage();
                if (cells.length > 0) {
                    promises.push(idb.saveCells(cells)
                        .then(function(success) {
                            return { type: 'cells', count: cells.length, success: success };
                        }));
                }
                
                // Wait for all migrations to complete
                return Promise.all(promises)
                    .then(function(results) {
                        console.log("Migration results:", results);
                        return results.some(function(r) { return r.success; });
                    })
                    .catch(function(err) {
                        console.error("Error during migration:", err);
                        return false;
                    });
            });
    }
};

console.log("storage.js loaded successfully");