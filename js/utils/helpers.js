// js/utils/helpers.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Helper functions for the Electronics Inventory App.
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

    getSortedFootprints: function () {
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
     * Build an array of cell objects for a new drawer.
     * Each cell has:
     *    id        "drawer-{drawerId}-r{row}-c{col}"
     *    drawerId  reference to parent drawer
     *    row, col  1-based indices
     */
    generateCellsForDrawer: (drawer) => {
        const rows = drawer.grid?.rows || 3;
        const cols = drawer.grid?.cols || 3;
        const now = Date.now();
        const cells = [];

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                cells.push({
                    id: `cell-${now}-${r}-${c}`,
                    drawerId: drawer.id,
                    coordinate: `${String.fromCharCode(65 + c)}${r + 1}`, // A1, B1 …
                    nickname: '',
                    available: true
                });
            }
        }
        return cells;
    },

    /**
 * Sync the cell grid with a resized drawer.
 * - Adds any NEW coordinates that now fit inside the grid.
 * - Removes cells that fall outside the grid *only if they are empty*.
 *   (If they hold components, they stay but get marked `orphan: true` so the
 *    UI can highlight them and you can drag-move the parts later.)
 *
 * @param {Object} drawer   –– the updated drawer (already has new rows/cols)
 * @param {Array}  allCells –– entire cells array from state / storage
 * @param {Array}  components –– components array so we can check occupancy
 * @return {Array}          –– new cells array (ready for setCells + saveCells)
 */
    syncCellsWithDrawer(drawer, allCells, components) {
        const helpers = window.App.utils.helpers;

        const wanted = new Set();
        for (let r = 1; r <= drawer.rows; r++) {
            for (let c = 1; c <= drawer.cols; c++) {
                wanted.add(`${r}-${c}`);
            }
        }

        const keep = [];
        const add = [];

        // 1️⃣ iterate current cells for this drawer
        for (const cell of allCells) {
            if (cell.drawerId !== drawer.id) {
                keep.push(cell);                     // belongs to another drawer
                continue;
            }

            const key = `${cell.row}-${cell.col}`;

            if (wanted.has(key)) {
                keep.push({ ...cell, orphan: false });   // still inside grid
                wanted.delete(key);                      // mark as satisfied
            } else {
                // Cell is now outside the grid
                const occupied = components.some(c => c.locationInfo?.cellId === cell.id);
                if (occupied) {
                    // keep it but mark orphaned
                    keep.push({ ...cell, orphan: true });
                    console.warn(`Cell ${cell.id} now outside drawer – marked orphan`);
                }
                // else drop it entirely
            }
        }

        // 2️⃣ create any coordinates still missing
        for (const key of wanted) {
            const [row, col] = key.split('-').map(Number);
            add.push({
                id: `cell-${drawer.id}-${row}-${col}`,
                drawerId: drawer.id,
                row,
                col,
                coordinate: `${String.fromCharCode(64 + col)}${row}`, // A1, B3 …
                nickname: '',
                available: true,
                orphan: false
            });
        }

        return [...keep, ...add];
    },



};

// Create a sanitize helper function that works safely
window.App.utils.helpers.sanitize = function(value) {
    // Return non-string values unchanged
    if (typeof value !== 'string') return value;
    
    // If DOMPurify exists, sanitize the string
    if (window.DOMPurify) {
        return window.DOMPurify.sanitize(value);
    }
    
    // Fallback - basic HTML tag removal if DOMPurify not available
    // This is not as secure as DOMPurify but better than nothing
    return value.replace(/<[^>]*>?/gm, '');
};

// Modify parseParameters to sanitize inputs
window.App.utils.helpers.parseParameters = (text) => {
    if (!text || typeof text !== 'string') return {};
    const params = {};
    text.split('\n').forEach(line => {
        const separatorIndex = line.indexOf(':');
        if (separatorIndex > 0) { // Ensure colon exists and is not the first character
            // Sanitize both key and value
            const key = window.App.utils.helpers.sanitize(
                line.substring(0, separatorIndex).trim()
            );
            const value = window.App.utils.helpers.sanitize(
                line.substring(separatorIndex + 1).trim()
            );

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
};

// Modify formatDatasheets to sanitize URLs
window.App.utils.helpers.formatDatasheets = (datasheets) => {
    if (!datasheets || typeof datasheets !== 'string') return [];
    return datasheets.split(/[\n,]+/) // Split by newline or comma
        .map(url => window.App.utils.helpers.sanitize(url.trim())) // Trim and sanitize
        .filter(url => url && (url.startsWith('http://') || url.startsWith('https://'))); // Basic URL validation
};

// Add sanitization to any function that generates IDs
window.App.utils.helpers.generateId = () => {
    const rawId = `comp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return window.App.utils.helpers.sanitize(rawId);
};

console.log("InventoryHelpers loaded."); // For debugging
