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
    
    /*** CATEGORIES ***/
    
    loadCategories: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadCategories()
                        .catch(function(err) {
                            console.error("Error loading categories from IndexedDB:", err);
                            return [];
                        });
                }
                
                // Otherwise use empty array (no localStorage fallback)
                return [];
            });
    },
    
    saveCategories: function(categories) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveCategories(categories)
                        .catch(function(err) {
                            console.error("Error saving categories to IndexedDB:", err);
                            return false;
                        });
                }
                
                // Otherwise just return false (no localStorage fallback)
                return false;
            });
    },
    
    /*** FOOTPRINTS ***/
    
    loadFootprints: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadFootprints()
                        .catch(function(err) {
                            console.error("Error loading footprints from IndexedDB:", err);
                            return [];
                        });
                }
                
                // Otherwise use empty array (no localStorage fallback)
                return [];
            });
    },
    
    saveFootprints: function(footprints) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveFootprints(footprints)
                        .catch(function(err) {
                            console.error("Error saving footprints to IndexedDB:", err);
                            return false;
                        });
                }
                
                // Otherwise just return false (no localStorage fallback)
                return false;
            });
    },

    /*** LOW STOCK ***/
    loadLowStockConfig: function() {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Use IndexedDB if available
                if (useIndexedDB) {
                    return window.App.utils.idb.loadLowStockConfig();
                }
                
                // If IndexedDB not available, return empty object
                console.warn("IndexedDB not available for low stock config");
                return {};
            });
    },
    
    // Save low stock configuration to IndexedDB only
    saveLowStockConfig: function(config) {
        var self = this;
        
        return this.init()
            .then(function(useIndexedDB) {
                // Use IndexedDB if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveLowStockConfig(config);
                }
                
                // If IndexedDB not available, warn and return false
                console.warn("IndexedDB not available for saving low stock config");
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
        
        // Sanitize components before saving
        const sanitizedComponents = Array.isArray(components) 
            ? components.map(comp => window.App.utils.sanitize.component(comp))
            : [];
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveComponents(sanitizedComponents)
                        .catch(function(err) {
                            console.error("Error saving components to IndexedDB:", err);
                            return self._saveComponentsToLocalStorage(sanitizedComponents);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveComponentsToLocalStorage(sanitizedComponents);
            });
    },
    
    _saveComponentsToLocalStorage: function(components) {
        try {
            localStorage.setItem('electronicsComponents', JSON.stringify(components));
            console.log("Saved", components.length, "sanitized components to localStorage");
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
        
        // Sanitize locations before saving
        const sanitizedLocations = Array.isArray(locations)
            ? locations.map(loc => window.App.utils.sanitize.location(loc))
            : [];
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveLocations(sanitizedLocations)
                        .catch(function(err) {
                            console.error("Error saving locations to IndexedDB:", err);
                            return self._saveLocationsToLocalStorage(sanitizedLocations);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveLocationsToLocalStorage(sanitizedLocations);
            });
    },
    
    _saveLocationsToLocalStorage: function(locations) {
        try {
            localStorage.setItem('electronicsLocations', JSON.stringify(locations));
            console.log("Saved", locations.length, "sanitized locations to localStorage");
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
        
        // Sanitize drawers before saving
        const sanitizedDrawers = Array.isArray(drawers)
            ? drawers.map(drawer => window.App.utils.sanitize.drawer(drawer))
            : [];
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveDrawers(sanitizedDrawers)
                        .catch(function(err) {
                            console.error("Error saving drawers to IndexedDB:", err);
                            return self._saveDrawersToLocalStorage(sanitizedDrawers);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveDrawersToLocalStorage(sanitizedDrawers);
            });
    },
    
    _saveDrawersToLocalStorage: function(drawers) {
        try {
            localStorage.setItem('electronicsDrawers', JSON.stringify(drawers));
            console.log("Saved", drawers.length, "sanitized drawers to localStorage");
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
        
        // Sanitize cells before saving
        const sanitizedCells = Array.isArray(cells)
            ? cells.map(cell => window.App.utils.sanitize.cell(cell))
            : [];
        
        return this.init()
            .then(function(useIndexedDB) {
                // Try IndexedDB first if available
                if (useIndexedDB) {
                    return window.App.utils.idb.saveCells(sanitizedCells)
                        .catch(function(err) {
                            console.error("Error saving cells to IndexedDB:", err);
                            return self._saveCellsToLocalStorage(sanitizedCells);
                        });
                }
                
                // Otherwise use localStorage
                return self._saveCellsToLocalStorage(sanitizedCells);
            });
    },
    
    _saveCellsToLocalStorage: function(cells) {
        try {
            localStorage.setItem('electronicsCells', JSON.stringify(cells));
            console.log("Saved", cells.length, "sanitized cells to localStorage");
            return true;
        } catch (err) {
            console.error("Error saving cells to localStorage:", err);
            return false;
        }
    },
    
    /*** CONFIG - Other settings still use localStorage ***/
    
    loadConfig: function() {
        // Create default config object
        var defaultConfig = {
            viewMode: 'table',
            currencySymbol: 'RM',
            showTotalValue: true,
            itemsPerPage: 'all',
            theme: 'light'
        };

        try {
            // Load view mode
            var savedViewMode = localStorage.getItem('electronicsViewMode');
            if (savedViewMode && (savedViewMode === 'table' || savedViewMode === 'card')) {
                defaultConfig.viewMode = savedViewMode;
            }

            // Load currency symbol
            var savedCurrency = localStorage.getItem('electronicsCurrencySymbol');
            if (savedCurrency) {
                defaultConfig.currencySymbol = savedCurrency;
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
                // Save view mode
                if (config.viewMode === 'table' || config.viewMode === 'card') {
                    localStorage.setItem('electronicsViewMode', config.viewMode);
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
                    localStorage.removeItem('electronicsViewMode');
                    localStorage.removeItem('electronicsCurrencySymbol');
                    localStorage.removeItem('electronicsShowTotalValue');
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
    }
};

console.log("storage.js loaded successfully");