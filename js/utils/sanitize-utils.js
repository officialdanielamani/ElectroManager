// js/utils/sanitize-utils.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Comprehensive sanitization utilities for the Electronics Inventory App.
 * Provides consistent methods to sanitize input and prevent XSS attacks.
 */
window.App.utils.sanitize = {
    // Define constants for all character limits
    LIMITS: {
        // Component fields
        COMPONENT_NAME: 32,
        COMPONENT_MODEL: 128, // For the "type" field 
        COMPONENT_INFO: 128,
        CATEGORY: 32,
        FOOTPRINT: 32,

        // Location fields
        LOCATION_NAME: 32,
        LOCATION_DESCRIPTION: 64,

        // Drawer fields
        DRAWER_NAME: 32,
        DRAWER_NICKNAME: 16,
        DRAWER_DESCRIPTION: 64,

        // Cell fields
        CELL_NICKNAME: 16
    },

    // Add regex pattern for allowed characters: A-Z, a-z, 0-9, comma, dot, dash, underscore, space
    ALLOWED_CHARS_PATTERN: /^[A-Za-z0-9,.\-_@\/ ]*$/,

    /**
     * Sanitizes a string value using DOMPurify
     * @param {any} value - The value to sanitize
     * @returns {any} - The sanitized value if string, otherwise unchanged
     */
    value: function (value) {
        // Return non-string values unchanged
        if (value === null || value === undefined || typeof value !== 'string') {
            return value;
        }

        // If DOMPurify exists, sanitize the string
        if (window.DOMPurify) {
            return window.DOMPurify.sanitize(value);
        }

        // Fallback - basic HTML tag removal if DOMPurify not available
        return value.replace(/<[^>]*>?/gm, '');
    },

    /**
     * Validates and filters input for allowed characters only
     * @param {string} value - The string to validate
     * @returns {string} - String with only allowed characters
     */
    validateAllowedChars: function (value) {
        if (typeof value !== 'string') return '';

        // First sanitize the value
        const sanitized = this.value(value);

        // Then filter out any disallowed characters
        return sanitized.split('')
            .filter(char => this.ALLOWED_CHARS_PATTERN.test(char))
            .join('');
    },

    /**
     * Validates string length and allowed characters
     * @param {string} value - The string to validate
     * @param {number} maxLength - Maximum length allowed
     * @param {string} defaultValue - Default value if invalid
     * @returns {string} - Validated string
     */
    validateLength: function (value, maxLength, defaultValue = '') {
        if (typeof value !== 'string') return defaultValue;

        // First sanitize the value
        const sanitized = this.value(value);

        // Then filter allowed characters
        const filtered = sanitized.split('')
            .filter(char => this.ALLOWED_CHARS_PATTERN.test(char))
            .join('');

        // Finally, check length and truncate if needed
        return filtered.length <= maxLength ? filtered : filtered.substring(0, maxLength);
    },

    /**
     * Check if a string contains only valid characters
     * @param {string} value - The string to check
     * @returns {boolean} - True if valid, false if contains invalid chars
     */
    isValidString: function (value) {
        if (typeof value !== 'string') return false;

        // Check each character in the string
        for (let i = 0; i < value.length; i++) {
            if (!this.ALLOWED_CHARS_PATTERN.test(value[i])) {
                return false;
            }
        }

        return true;
    },

    /**
     * Get array of invalid characters in a string
     * @param {string} value - The string to check
     * @returns {Array} - Array of invalid characters
     */
    getInvalidChars: function (value) {
        if (typeof value !== 'string') return [];

        const invalidChars = new Set();

        for (let i = 0; i < value.length; i++) {
            if (!this.ALLOWED_CHARS_PATTERN.test(value[i])) {
                invalidChars.add(value[i]);
            }
        }

        return Array.from(invalidChars);
    },

    /**
     * Sanitizes all string properties in an object (recursive)
     * @param {Object} obj - The object to sanitize
     * @returns {Object} - A new object with all string values sanitized
     */
    object: function (obj) {
        if (!obj || typeof obj !== 'object') {
            return this.value(obj);
        }

        // Handle arrays
        if (Array.isArray(obj)) {
            return obj.map(item => this.object(item));
        }

        // Handle regular objects
        const sanitized = {};
        for (const key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
                const value = obj[key];

                if (typeof value === 'object' && value !== null) {
                    sanitized[key] = this.object(value);
                } else {
                    sanitized[key] = this.value(value);
                }
            }
        }
        return sanitized;
    },

    /**
     * Sanitizes form input data from an event
     * @param {Event} event - DOM event with target input
     * @returns {string} - Sanitized input value
     */
    input: function (event) {
        if (!event || !event.target) return '';
        return this.value(event.target.value);
    },

    /**
     * Field-specific validators - Fixed to use proper this context
     */
    componentName: function (name) {
        return this.validateLength(name, this.LIMITS.COMPONENT_NAME);
    },

    componentModel: function (model) {
        return this.validateLength(model, this.LIMITS.COMPONENT_MODEL);
    },

    componentInfo: function (info) {
        return this.validateLength(info, this.LIMITS.COMPONENT_INFO);
    },

    category: function (category) {
        return this.validateLength(category, this.LIMITS.CATEGORY);
    },

    footprint: function (footprint) {
        return this.validateLength(footprint, this.LIMITS.FOOTPRINT);
    },

    locationName: function (name) {
        return this.validateLength(name, this.LIMITS.LOCATION_NAME);
    },

    locationDescription: function (desc) {
        return this.validateLength(desc, this.LIMITS.LOCATION_DESCRIPTION);
    },

    drawerName: function (name) {
        return this.validateLength(name, this.LIMITS.DRAWER_NAME);
    },

    drawerNickname: function (nickname) {
        return this.validateLength(nickname, this.LIMITS.DRAWER_NICKNAME);
    },

    drawerDescription: function (desc) {
        return this.validateLength(desc, this.LIMITS.DRAWER_DESCRIPTION);
    },

    cellNickname: function (nickname) {
        return this.validateLength(nickname, this.LIMITS.CELL_NICKNAME);
    },

    /**
     * Sanitizes all properties of a component object
     * @param {Object} component - The component object to sanitize
     * @returns {Object} - A sanitized copy of the component
     */
 component: function (component) {
    if (!component || typeof component !== 'object') {
        return {};
    }

    const sanitized = { ...component };

    // Process standard string fields
    if (typeof sanitized.name === 'string') {
        sanitized.name = this.componentName(sanitized.name);
    }

    if (typeof sanitized.type === 'string') {
        sanitized.type = this.componentModel(sanitized.type);
    }

    if (typeof sanitized.info === 'string') {
        sanitized.info = this.componentInfo(sanitized.info);
    }

    if (typeof sanitized.category === 'string') {
        sanitized.category = this.category(sanitized.category);
    }

    if (typeof sanitized.footprint === 'string') {
        sanitized.footprint = this.footprint(sanitized.footprint);
    }

    // Other string fields
    const otherStringFields = [
        'datasheets', 'image', 'customCategory', 'customFootprint'
    ];

    otherStringFields.forEach(field => {
        if (typeof sanitized[field] === 'string') {
            sanitized[field] = this.value(sanitized[field]);
        }
    });

    // NEW: Sanitize unified storage object
        if (sanitized.storage && typeof sanitized.storage === 'object') {
        sanitized.storage = this.storage(sanitized.storage);
    } else {
        // Initialize with empty storage if missing
        sanitized.storage = {
            locationId: '',
            details: '',
            drawerId: '',
            cells: []
        };
    }

    // Preserve the ap (additional parameters) structure
    if (sanitized.ap && Array.isArray(sanitized.ap)) {
        sanitized.ap = sanitized.ap.map(paramObj => {
            if (paramObj && typeof paramObj === 'object') {
                const cleanParams = {};
                for (const key in paramObj) {
                    if (Object.prototype.hasOwnProperty.call(paramObj, key)) {
                        cleanParams[key] = typeof paramObj[key] === 'string' 
                            ? this.value(paramObj[key]) 
                            : paramObj[key];
                    }
                }
                return cleanParams;
            }
            return {};
        });
    } else {
        sanitized.ap = [];
    }

    return sanitized;
},


// Add new storage sanitization function
storage: function(storage) {
    if (!storage || typeof storage !== 'object') {
        return {
            locationId: '',
            details: '',
            drawerId: '',
            cells: []
        };
    }
    
    return {
        locationId: this.value(storage.locationId || ''),
        details: this.value(storage.details || ''),
        drawerId: this.value(storage.drawerId || ''),
        cells: Array.isArray(storage.cells) 
            ? storage.cells.map(cell => this.value(cell))
            : []
    };
},
    /**
     * Sanitizes a location object
     * @param {Object} location - Location object to sanitize
     * @returns {Object} - Sanitized location object
     */
    location: function (location) {
        if (!location || typeof location !== 'object') {
            return {};
        }

        return {
            id: this.value(location.id),
            name: this.locationName(location.name || ''),
            description: this.locationDescription(location.description || '')
        };
    },

    /**
     * Sanitizes a drawer object
     * @param {Object} drawer - Drawer object to sanitize
     * @returns {Object} - Sanitized drawer object
     */
    drawer: function (drawer) {
        if (!drawer || typeof drawer !== 'object') {
            return {};
        }

        const sanitized = {
            id: this.value(drawer.id),
            locationId: this.value(drawer.locationId),
            name: this.drawerName(drawer.name || ''),
            description: this.drawerDescription(drawer.description || '')
        };

        // Handle grid dimensions
        if (drawer.grid && typeof drawer.grid === 'object') {
            sanitized.grid = {
                rows: parseInt(drawer.grid.rows, 10) || 3,
                cols: parseInt(drawer.grid.cols, 10) || 3
            };
        } else {
            sanitized.grid = { rows: 3, cols: 3 };
        }

        return sanitized;
    },

    /**
     * Sanitizes a cell object
     * @param {Object} cell - Cell object to sanitize
     * @returns {Object} - Sanitized cell object
     */
    cell: function (cell) {
        if (!cell || typeof cell !== 'object') {
            return {};
        }

        return {
            id: this.value(cell.id),
            drawerId: this.value(cell.drawerId),
            coordinate: this.value(cell.coordinate),
            nickname: this.cellNickname(cell.nickname || ''),
            available: typeof cell.available === 'boolean' ? cell.available : true
        };
    },

    /**
     * Sanitizes an array of objects (like components, locations, etc.)
     * @param {Array} items - Array of objects to sanitize
     * @param {Function} sanitizeFn - Sanitization function to apply to each item
     * @returns {Array} - Sanitized array of objects
     */
    array: function (items, sanitizeFn) {
        if (!Array.isArray(items)) {
            return [];
        }

        return items.map(item =>
            typeof sanitizeFn === 'function'
                ? sanitizeFn(item)
                : this.object(item)
        );
    },

    /**
     * Parse parameters from string format to object, with sanitization
     * @param {string} text - Parameter text in format "key: value"
     * @returns {Object} - Sanitized parameters object
     */
    parseParameters: function (text) {
        if (!text || typeof text !== 'string') return { ap: [] };

    // Create an object to hold key-value pairs
    const params = {};
    let hasValidParams = false;

    // Split by lines and process each line
    text.split('\n').forEach(line => {
        // Find the first colon (not any colon) to separate key from value
        const separatorIndex = line.indexOf(':');
        
        if (separatorIndex > 0) { // Ensure colon exists and is not the first character
            const key = line.substring(0, separatorIndex).trim();
            // Take everything after the first colon as the value (including any other colons)
            const value = line.substring(separatorIndex + 1).trim();

            // Skip special system fields
            if (key === 'storage' ||
                key === 'favorite' || key === 'bookmark' || key === 'star' ||
                key === '<object>' || value === '<object>' ||
                key === 'ap') { // Skip ap key itself
                return;
            }

            if (key) { // Ensure key is not empty
                params[key] = value;
                hasValidParams = true;
            }
        }
    });

    // Return an object with ap array containing our parameters object
    // This is the format expected by the component storage
    return { ap: hasValidParams ? [params] : [] };
},

    /**
     * Creates a safe version of react's setState that sanitizes input
     * @param {Function} setState - React's setState function
     * @returns {Function} - Sanitized setState wrapper
     */
    createSafeSetState: function (setState) {
        const sanitizeUtils = this;
        return function (value) {
            // If value is a function (functional update), wrap it
            if (typeof value === 'function') {
                setState(prevState => {
                    const nextState = value(prevState);
                    return sanitizeUtils.object(nextState);
                });
            } else {
                // Otherwise sanitize and set directly
                setState(sanitizeUtils.object(value));
            }
        };
    },

    /**
     * Creates a keydown handler that prevents disallowed characters
     * @returns {Function} - Keydown event handler
     */
    createKeyDownHandler: function () {
        const sanitizeUtils = this;
        return function (e) {
            // Allow control keys (backspace, delete, arrows, etc.)
            if (e.ctrlKey || e.metaKey || e.altKey ||
                e.key === 'Backspace' || e.key === 'Delete' ||
                e.key === 'ArrowLeft' || e.key === 'ArrowRight' ||
                e.key === 'Home' || e.key === 'End' ||
                e.key === 'Tab') {
                return; // Allow these keys
            }

            // Check if the key is an allowed character
            if (!sanitizeUtils.ALLOWED_CHARS_PATTERN.test(e.key)) {
                e.preventDefault(); // Prevent typing disallowed characters
            }
        };
    },

    /**
     * Creates a change handler that filters input for allowed characters
     * @param {Function} setFormData - State setter function
     * @returns {Function} - Change event handler
     */
    createAllowedCharsChangeHandler: function (setFormData) {
        const sanitizeUtils = this;
        return function (e) {
            const { name, value, type, checked } = e.target;
            // For checkbox inputs, use the 'checked' property as the value
            let newValue = type === 'checkbox' ? checked : value;

            // Filter input for allowed characters if it's a string
            if (typeof newValue === 'string') {
                // Sanitize and filter characters
                newValue = sanitizeUtils.validateAllowedChars(newValue);
            }

            setFormData(prevData => ({
                ...prevData,
                [name]: newValue
            }));
        };
    }
};

console.log("Sanitize-utilis loaded");