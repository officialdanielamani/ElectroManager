// js/utils/helpers.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Helper functions for the Electronics Inventory App.
 * Updated to work with IndexedDB compatibility.
 */
window.App.utils.helpers = {
    // Common footprints list
    commonFootprints: [],
    
    /**
     * Checks if a component is low in stock based on configuration.
     * @param {object} component - The component object.
     * @param {object} lowStockConfig - The low stock configuration { category: threshold }.
     * @returns {boolean} - True if the component is low in stock, false otherwise.
     */
    isLowStock: (component, lowStockConfig) => {
        if (!component || !component.category || !lowStockConfig || typeof lowStockConfig !== 'object' || !lowStockConfig[component.category]) {
            return false;
        }
        const quantity = Number(component.quantity) || 0;
        const threshold = Number(lowStockConfig[component.category]) || 0;
        // Ensure threshold is positive, otherwise low stock doesn't make sense
        return threshold > 0 && quantity < threshold;
    },

    getSortedFootprints: function() {
        return [
            { value: "", label: "-- Select footprint --" },
            { value: "__custom__", label: "Custom footprint..." },
            ...this.commonFootprints.sort().map(fp => ({ value: fp, label: fp }))
        ];
    },

    /**
     * Calculates the total quantity of items per category.
     * @param {Array<object>} comps - Array of component objects.
     * @returns {Array<Array<string, number>>} - Sorted array of [category, count] pairs.
     */
    calculateCategoryCounts: (comps) => {
        const counts = {};
        if (!Array.isArray(comps)) return [];
        comps.forEach(comp => {
            const category = comp.category || "Uncategorized"; // Group items without category
            const quantity = Number(comp.quantity) || 0;
            counts[category] = (counts[category] || 0) + quantity;
        });
        // Return sorted array of [category, count] pairs
        return Object.entries(counts).sort(([catA], [catB]) => catA.localeCompare(catB));
    },

    /**
     * Calculates the total monetary value of the inventory.
     * @param {Array<object>} comps - Array of component objects.
     * @returns {number} - The total inventory value.
     */
    calculateTotalInventoryValue: (comps) => {
        if (!Array.isArray(comps)) return 0;
        return comps.reduce((total, comp) => {
            const price = Number(comp.price) || 0;
            const quantity = Number(comp.quantity) || 0;
            return total + (price * quantity);
        }, 0);
    },

    /**
     * Formats a numerical value as currency.
     * @param {number|string} value - The numerical value to format.
     * @param {string} [currencySymbol='$'] - The currency symbol to use.
     * @returns {string} - The formatted currency string (e.g., "$12.34").
     */
    formatCurrency: (value, currencySymbol = '$') => {
        const number = Number(value) || 0;
        // Basic formatting, ensures two decimal places
        return `${currencySymbol}${number.toFixed(2)}`;
    },

    /**
     * Parses a multi-line string of "key: value" pairs into an object.
     * Ignores lines without a colon or where the key is empty.
     * @param {string} text - The string containing parameters.
     * @returns {object} - An object representing the parameters.
     */
    parseParameters: (text) => {
        if (!text || typeof text !== 'string') return {};
        const params = {};
        text.split('\n').forEach(line => {
            const separatorIndex = line.indexOf(':');
            if (separatorIndex > 0) { // Ensure colon exists and is not the first character
                const key = line.substring(0, separatorIndex).trim();
                const value = line.substring(separatorIndex + 1).trim();
                
                // Skip special values that should be handled separately
                if (key === 'locationInfo' || key === 'storageInfo' || 
                    key === 'favorite' || key === 'bookmark' || key === 'star' ||
                    key === '<object>' || value === '<object>') {
                    return;
                }
                
                if (key) { // Ensure key is not empty
                    params[key] = value;
                }
            }
        });
        return params;
    },

    /**
     * Formats component data (excluding standard fields) back into a
     * multi-line "key: value" string suitable for editing in a textarea.
     * @param {object} component - The component object.
     * @returns {string} - A string representation of additional parameters.
     */
    formatParametersForEdit: (component) => {
        if (!component || typeof component !== 'object') return '';
        // List of standard fields managed by specific inputs in the form
        const standardFields = [
            'id', 'name', 'category', 'type', 'quantity', 'price',
            'footprint', 'info', 'datasheets', 'image',
            'customCategory', 'customFootprint', // Include temporary fields if they exist
            'favorite', 'bookmark', 'star', // Add flag fields
            'locationInfo', 'storageInfo', // Add location/storage info fields
            'cells', 'cellId', 'drawerId' // Add drawer-related fields
        ];
        return Object.entries(component)
            // Filter out standard fields and the 'parameters' field itself if it was added incorrectly
            .filter(([key]) => !standardFields.includes(key) && key !== 'parameters')
            .map(([key, value]) => {
                // Ensure values are properly formatted as strings
                if (typeof value === 'object') {
                    return `${key}: <object>`;  // Replace objects with placeholder
                }
                return `${key}: ${value}`;
            })
            .join('\n'); // Join lines with newline
    },

    /**
     * Formats a datasheet string (newline or comma-separated) into an array of valid URLs.
     * @param {string} datasheets - The string containing datasheet URLs.
     * @returns {Array<string>} - An array of valid datasheet URLs.
     */
    formatDatasheets: (datasheets) => {
        if (!datasheets || typeof datasheets !== 'string') return [];
        return datasheets.split(/[\n,]+/) // Split by newline or comma
            .map(url => url.trim()) // Trim whitespace
            .filter(url => url && (url.startsWith('http://') || url.startsWith('https://'))); // Basic URL validation
    },

    /**
     * Generates a reasonably unique ID.
     * @returns {string} A unique ID string.
     */
    generateId: () => {
        return `comp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    },
    
    /**
     * Creates a properly formatted component object with default values for missing fields
     * @param {object} comp - Component object to normalize
     * @returns {object} - Component with all required fields and proper structure
     */
    normalizeComponent: (comp) => {
        if (!comp || typeof comp !== 'object') {
            comp = {}; // Start with empty object if invalid
        }
        
        // Create base component with standard fields and defaults
        const normalizedComp = {
            id: comp.id || window.App.utils.helpers.generateId(),
            name: comp.name || '',
            category: comp.category || '',
            type: comp.type || '',
            quantity: Number(comp.quantity) || 0,
            price: Number(comp.price) || 0,
            footprint: comp.footprint || '',
            info: comp.info || '',
            datasheets: comp.datasheets || '',
            image: comp.image || '',
            // Initialize flag fields 
            favorite: !!comp.favorite,
            bookmark: !!comp.bookmark,
            star: !!comp.star
        };

        // Ensure locationInfo is properly formatted
        if (!comp.locationInfo || typeof comp.locationInfo === 'string' || comp.locationInfo === '[object Object]') {
            normalizedComp.locationInfo = { locationId: '', details: '' };
        } else {
            normalizedComp.locationInfo = {
                locationId: comp.locationInfo.locationId || '',
                details: comp.locationInfo.details || ''
            };
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

            // Handle backward compatibility - if cellId exists but cells array doesn't include it
            if (comp.storageInfo.cellId && !normalizedComp.storageInfo.cells.includes(comp.storageInfo.cellId)) {
                normalizedComp.storageInfo.cells.push(comp.storageInfo.cellId);
            }
        }
        
        return normalizedComp;
    },
    
    /**
     * Normalizes cells data to ensure all required fields are present
     * @param {object} cell - Cell object to normalize
     * @returns {object} - Cell with all required fields
     */
    normalizeCell: (cell) => {
        if (!cell || typeof cell !== 'object') {
            cell = {}; // Start with empty object if invalid
        }
        
        return {
            id: cell.id || `cell-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            drawerId: cell.drawerId || '',
            coordinate: cell.coordinate || '',
            nickname: cell.nickname || '',
            available: cell.available !== undefined ? cell.available : true
        };
    },
    
    /**
     * Normalizes drawer data to ensure all required fields are present
     * @param {object} drawer - Drawer object to normalize
     * @returns {object} - Drawer with all required fields
     */
    normalizeDrawer: (drawer) => {
        if (!drawer || typeof drawer !== 'object') {
            drawer = {}; // Start with empty object if invalid
        }
        
        return {
            id: drawer.id || `drawer-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            locationId: drawer.locationId || '',
            name: drawer.name || '',
            description: drawer.description || '',
            grid: {
                rows: parseInt(drawer.grid?.rows || 3, 10),
                cols: parseInt(drawer.grid?.cols || 3, 10)
            }
        };
    },
    
    /**
     * Normalizes location data to ensure all required fields are present
     * @param {object} location - Location object to normalize
     * @returns {object} - Location with all required fields
     */
    normalizeLocation: (location) => {
        if (!location || typeof location !== 'object') {
            location = {}; // Start with empty object if invalid
        }
        
        return {
            id: location.id || `loc-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            name: location.name || '',
            description: location.description || ''
        };
    },
    
    /**
     * Gets database status - for debugging or displaying in the UI
     * @param {IDBDatabase} db - The IndexedDB database instance
     * @returns {object} - Status information including object store counts
     */
    getDatabaseStatus: async () => {
        if (!window.indexedDB) {
            return { supported: false, message: "IndexedDB not supported in this browser" };
        }
        
        try {
            const status = {
                supported: true,
                stores: {}
            };
            
            // Get components count
            if (window.App.utils.storage && typeof window.App.utils.storage.loadComponents === 'function') {
                const components = await window.App.utils.storage.loadComponents();
                status.stores.components = components ? components.length : 0;
            }
            
            // Get other store counts if needed
            // ...
            
            return status;
        } catch (error) {
            return {
                supported: true,
                error: error.message
            };
        }
    }
};

console.log("InventoryHelpers loaded with IndexedDB compatibility.");