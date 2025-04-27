// js/utils/storage.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Storage utility functions for the Electronics Inventory App.
 * Handles saving and loading data from localStorage.
 */
window.App.utils.storage = {
    /**
     * Load components from localStorage.
     * @returns {Array} Array of component objects or empty array if none found.
     */
    loadComponents: () => {
        try {
            const savedComponents = localStorage.getItem('electronicsComponents');
            if (savedComponents) {
                const parsedComponents = JSON.parse(savedComponents);
                // Ensure all objects have proper structure and types
                const componentsWithValidValues = parsedComponents.map(comp => {
                    // Create base component with standard fields
                    const updatedComp = {
                        ...comp,
                        price: typeof comp.price === 'number' ? comp.price : Number(comp.price) || 0,
                        quantity: typeof comp.quantity === 'number' ? comp.quantity : Number(comp.quantity) || 0,
                        // Initialize flag fields if they don't exist
                        favorite: comp.favorite || false,
                        bookmark: comp.bookmark || false,
                        star: comp.star || false
                    };
    
                    // Ensure locationInfo is properly formatted
                    if (!comp.locationInfo || typeof comp.locationInfo === 'string' || comp.locationInfo === '[object Object]') {
                        updatedComp.locationInfo = { locationId: '', details: '' };
                    }
    
                    // Ensure storageInfo is properly formatted
                    if (!comp.storageInfo || typeof comp.storageInfo === 'string' || comp.storageInfo === '[object Object]') {
                        updatedComp.storageInfo = { locationId: '', drawerId: '', cells: [] };
                    } else {
                        // Handle partial storageInfo object (may be missing 'cells' array)
                        updatedComp.storageInfo = {
                            locationId: comp.storageInfo.locationId || '',
                            drawerId: comp.storageInfo.drawerId || '',
                            cells: Array.isArray(comp.storageInfo.cells) ? comp.storageInfo.cells : []
                        };
                        
                        // Handle backward compatibility - if cellId exists but cells array doesn't include it
                        if (comp.storageInfo.cellId && 
                            !updatedComp.storageInfo.cells.includes(comp.storageInfo.cellId)) {
                            updatedComp.storageInfo.cells.push(comp.storageInfo.cellId);
                        }
                    }
    
                    return updatedComp;
                });
                
                console.log('Loaded components from localStorage:', componentsWithValidValues.length);
                return componentsWithValidValues;
            }
        } catch (e) {
            console.error("Error parsing saved components:", e);
            // Don't remove storage on error, just return empty array
        }
        return []; // Default to empty array if nothing valid found
    },

    /**
     * Save components to localStorage.
     * @param {Array} components Array of component objects to save.
     * @returns {boolean} True if saved successfully, false otherwise.
     */
    saveComponents: (components) => {
        try {
            if (Array.isArray(components)) {
                // Make sure price and quantity are properly formatted before saving
                const componentsToSave = components.map(comp => ({
                    ...comp,
                    price: Number(comp.price) || 0,
                    quantity: Number(comp.quantity) || 0
                }));

                // Save to localStorage
                localStorage.setItem('electronicsComponents', JSON.stringify(componentsToSave));
                console.log('Saved components to localStorage:', componentsToSave.length);
                return true;
            }
        } catch (e) {
            console.error("Error saving components to localStorage:", e);
        }
        return false;
    },

    /**
 * Load locations from localStorage.
 * @returns {Array} Array of location objects or empty array if none found.
 */
    loadLocations: () => {
        try {
            const savedLocations = localStorage.getItem('electronicsLocations');
            if (savedLocations) {
                return JSON.parse(savedLocations);
            }
        } catch (e) {
            console.error("Error parsing saved locations:", e);
        }
        return []; // Default to empty array if nothing valid found
    },

    /**
     * Save locations to localStorage.
     * @param {Array} locations Array of location objects to save.
     * @returns {boolean} True if saved successfully, false otherwise.
     */
    saveLocations: (locations) => {
        try {
            if (Array.isArray(locations)) {
                localStorage.setItem('electronicsLocations', JSON.stringify(locations));
                console.log('Saved locations to localStorage:', locations.length);
                return true;
            }
        } catch (e) {
            console.error("Error saving locations to localStorage:", e);
        }
        return false;
    },


    /**
     * Load configuration (categories, view mode, etc.) from localStorage.
     * @returns {Object} Configuration object with default values if none found.
     */
    loadConfig: () => {
        // Create default config object
        const defaultConfig = {
            categories: [],
            viewMode: 'table',
            lowStockConfig: {},
            currencySymbol: 'RM',
            showTotalValue: false,
            footprints: [],
            itemsPerPage: 'all' 
        };

        try {
            // Load categories
            const savedCategories = localStorage.getItem('electronicsCategories');
            if (savedCategories) {
                defaultConfig.categories = JSON.parse(savedCategories);
            }

            // Load view mode
            const savedViewMode = localStorage.getItem('electronicsViewMode');
            if (savedViewMode && (savedViewMode === 'table' || savedViewMode === 'card')) {
                defaultConfig.viewMode = savedViewMode;
            }

            // Load low stock configuration
            const savedLowStockConfig = localStorage.getItem('electronicsLowStockConfig');
            if (savedLowStockConfig) {
                defaultConfig.lowStockConfig = JSON.parse(savedLowStockConfig);
            }

            // Load locations
            const savedLocations = localStorage.getItem('electronicsLocations');
            if (savedLocations) {
                defaultConfig.locations = JSON.parse(savedLocations);
            }

            // Load currency symbol
            const savedCurrency = localStorage.getItem('electronicsCurrencySymbol');
            if (savedCurrency) {
                defaultConfig.currencySymbol = savedCurrency;
            }

            // Load footprints
            const savedFootprints = localStorage.getItem('electronicsFootprints');
            if (savedFootprints) {
                defaultConfig.footprints = JSON.parse(savedFootprints);
            }

            // Load items per page setting
            const savedItemsPerPage = localStorage.getItem('electronicsItemsPerPage');
            if (savedItemsPerPage) {
                defaultConfig.itemsPerPage = JSON.parse(savedItemsPerPage);
            }

            // Load show total value setting
            const savedShowTotalValue = localStorage.getItem('electronicsShowTotalValue');
            // Check for 'true' string as localStorage stores strings
            defaultConfig.showTotalValue = savedShowTotalValue === 'true';

            console.log('Loaded config from localStorage');
            return defaultConfig;
        } catch (e) {
            console.error("Error loading config from localStorage:", e);
            return defaultConfig;
        }
    },

    /**
     * Save configuration to localStorage.
     * @param {Object} config Configuration object to save.
     * @returns {boolean} True if saved successfully, false otherwise.
     */
    saveConfig: (config) => {
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

                // Save footprints
                if (Array.isArray(config.footprints)) {
                    localStorage.setItem('electronicsFootprints', JSON.stringify(config.footprints));
                }

                // Save items per page setting
                if (config.itemsPerPage !== undefined) {
                    localStorage.setItem('electronicsItemsPerPage', JSON.stringify(config.itemsPerPage));
                }

                console.log('Saved config to localStorage');
                return true;
            }
        } catch (e) {
            console.error("Error saving config to localStorage:", e);
        }
        return false;
    },

    // Add to window.App.utils.storage
    loadDrawers: () => {
        try {
            const savedDrawers = localStorage.getItem('electronicsDrawers');
            if (savedDrawers) {
                return JSON.parse(savedDrawers);
            }
        } catch (e) {
            console.error("Error parsing saved drawers:", e);
        }
        return []; // Default to empty array
    },

    saveDrawers: (drawers) => {
        try {
            if (Array.isArray(drawers)) {
                localStorage.setItem('electronicsDrawers', JSON.stringify(drawers));
                console.log('Saved drawers to localStorage:', drawers.length);
                return true;
            }
        } catch (e) {
            console.error("Error saving drawers to localStorage:", e);
        }
        return false;
    },

    loadCells: () => {
        try {
            const savedCells = localStorage.getItem('electronicsCells');
            if (savedCells) {
                const parsedCells = JSON.parse(savedCells);
                // Set default availability for any cell that doesn't have it
                return parsedCells.map(cell => ({
                    ...cell,
                    available: cell.available !== undefined ? cell.available : true
                }));
            }
        } catch (e) {
            console.error("Error parsing saved cells:", e);
        }
        return []; // Default to empty array
    },

    saveCells: (cells) => {
        try {
            if (Array.isArray(cells)) {
                localStorage.setItem('electronicsCells', JSON.stringify(cells));
                console.log('Saved cells to localStorage:', cells.length);
                return true;
            }
        } catch (e) {
            console.error("Error saving cells to localStorage:", e);
        }
        return false;
    },

    /**
     * Clear all electronics inventory related data from localStorage.
     * @returns {boolean} True if cleared successfully, false otherwise.
     */
    clearStorage: () => {
        try {
            // Clear all related items one by one
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

            console.log('All localStorage items cleared');
            return true;
        } catch (e) {
            console.error("Error clearing localStorage:", e);
            return false;
        }
    },

    /**
     * For debugging - dump all electronics-related localStorage contents to console
     */
    debugStorage: () => {
        try {
            console.log('==== Electronics Inventory localStorage Debug ====');
            console.log('Components:', localStorage.getItem('electronicsComponents'));
            console.log('Categories:', localStorage.getItem('electronicsCategories'));
            console.log('View Mode:', localStorage.getItem('electronicsViewMode'));
            console.log('Low Stock Config:', localStorage.getItem('electronicsLowStockConfig'));
            console.log('Currency Symbol:', localStorage.getItem('electronicsCurrencySymbol'));
            console.log('Show Total Value:', localStorage.getItem('electronicsShowTotalValue'));
            console.log('Locations:', localStorage.getItem('electronicsLocations'));
            console.log('=================================================');
        } catch (e) {
            console.error("Error debugging localStorage:", e);
        }
    }
};

console.log("Storage utilities loaded."); // For debugging