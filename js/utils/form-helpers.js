// js/utils/form-helpers.js - Updated for unified storage system

window.App = window.App || {};
window.App.utils = window.App.utils || {};
window.App.utils.formHelpers = {
    /**
     * Generate a grid of cells for a drawer
     * @param {Object} drawer - The drawer object
     * @param {Array} filteredCells - Cells belonging to this drawer
     * @param {Array} selectedCells - Currently selected cell IDs
     * @param {Function} handleCellToggle - Function to handle cell toggle (optional for view-only mode)
     * @param {Object} UI - UI constants object
     * @param {boolean} readOnly - Whether the grid is in view-only mode
     * @returns {Array} Grid elements for rendering
     */
    generateCellGrid: function (drawer, filteredCells, selectedCells, handleCellToggle, UI, readOnly = false) {
        if (!drawer) return null;

        const themeColors = UI.getThemeColors();
        const rows = drawer.grid?.rows || 3;
        const cols = drawer.grid?.cols || 3;
        const gridElements = [];

        // Generate column headers (A, B, C, ...)
        const headerRow = [React.createElement('div', {
            key: 'corner',
            className: `w-8 h-8 bg-${themeColors.background} text-center font-medium`
        })];

        for (let c = 0; c < cols; c++) {
            const colLabel = String.fromCharCode(65 + c); // A=65 in ASCII
            headerRow.push(
                React.createElement('div', {
                    key: `col-${c}`,
                    className: `w-8 h-8 bg-${themeColors.background} text-center font-medium`
                }, colLabel)
            );
        }

        gridElements.push(React.createElement('div', { key: 'header-row', className: "flex" }, headerRow));

        // Generate rows with cells
        for (let r = 0; r < rows; r++) {
            const rowElements = [
                // Row header (1, 2, 3, ...)
                React.createElement('div', {
                    key: `row-${r}`,
                    className: `w-8 h-8 bg-${themeColors.background} text-center font-medium flex items-center justify-center`
                }, r + 1)
            ];

            // Generate cells for this row
            for (let c = 0; c < cols; c++) {
                const coordinate = `${String.fromCharCode(65 + c)}${r + 1}`; // e.g., "A1", "B2"
                const cell = filteredCells.find(cell => cell.coordinate === coordinate);

                // Cell might not exist in the database yet
                const cellId = cell ? cell.id : null;
                const isSelected = cellId && selectedCells.includes(cellId);

                // Safely check available property with a default to true
                const isAvailable = cell ? (cell.available !== false) : true;

                // Determine cell classes based on state
                const cellClasses = `w-8 h-8 border flex items-center justify-center 
                    ${isSelected ? `bg-${themeColors.primary.replace('500', '100').replace('400', '900')} border-${themeColors.primary}` : `bg-${themeColors.cardBackground} hover:bg-${themeColors.background}`}
                    ${!isAvailable ? `bg-${themeColors.secondary} opacity-70 cursor-not-allowed` : ''}
                    ${!readOnly && cellId && isAvailable ? 'cursor-pointer' : ''}`;

                rowElements.push(
                    React.createElement('div', {
                        key: `cell-${r}-${c}`,
                        className: cellClasses,
                        onClick: (!readOnly && cellId && isAvailable && handleCellToggle) ?
                            () => handleCellToggle(cellId) : undefined,
                        title: cell ?
                            (cell.nickname || coordinate) + (isAvailable ? '' : ' (Unavailable)') :
                            coordinate
                    },
                        isSelected ? '✓' : ''
                    )
                );
            }

            gridElements.push(React.createElement('div', { key: `row-${r}`, className: "flex" }, rowElements));
        }

        return gridElements;
    },

    /**
     * Format and validate storage object structure
     * @param {Object} storage - Storage object to format
     * @returns {Object} Properly formatted storage object
     */
    formatStorage: function (storage) {
        // Handle null/malformed storage
        if (!storage || typeof storage === 'string' || storage === '[object Object]') {
            return { locationId: '', details: '', drawerId: '', cells: [] };
        }

        // Ensure all required fields exist with proper types
        return {
            locationId: typeof storage.locationId === 'string' ? storage.locationId : '',
            details: typeof storage.details === 'string' ? storage.details : '',
            drawerId: typeof storage.drawerId === 'string' ? storage.drawerId : '',
            cells: Array.isArray(storage.cells) ? storage.cells : []
        };
    },

    /**
     * Get filtered drawers based on selected location
     * @param {string} locationId - Selected location ID
     * @param {Array} allDrawers - All available drawers
     * @returns {Array} Filtered drawers for this location
     */
    getFilteredDrawers: function (locationId, allDrawers) {
        if (!locationId || !Array.isArray(allDrawers)) return [];
        return allDrawers.filter(drawer => drawer.locationId === locationId);
    },

    /**
     * Get filtered cells for a drawer
     * @param {string} drawerId - Selected drawer ID
     * @param {Array} allCells - All available cells
     * @returns {Array} Filtered cells for this drawer
     */
    getFilteredCells: function (drawerId, allCells) {
        if (!drawerId || !Array.isArray(allCells)) return [];
        return allCells.filter(cell => cell.drawerId === drawerId);
    },

    /**
     * Get components assigned to a specific location (unified storage)
     * @param {string} locationId - Location ID to filter by
     * @param {Array} components - Array of all components
     * @returns {Array} Components assigned to this location
     */
    getComponentsForLocation: function (locationId, components) {
        if (!locationId || !Array.isArray(components)) return [];
        return components.filter(comp => 
            comp.storage && comp.storage.locationId === locationId
        );
    },

    /**
     * Get components assigned to a specific drawer (unified storage)
     * @param {string} drawerId - Drawer ID to filter by
     * @param {Array} components - Array of all components
     * @returns {Array} Components assigned to this drawer
     */
    getComponentsForDrawer: function (drawerId, components) {
        if (!drawerId || !Array.isArray(components)) return [];
        return components.filter(comp =>
            comp.storage && comp.storage.drawerId === drawerId
        );
    },

    /**
     * Get components assigned to a specific cell (unified storage)
     * @param {string} cellId - Cell ID to filter by
     * @param {Array} components - Array of all components
     * @returns {Array} Components assigned to this cell
     */
    getComponentsForCell: function (cellId, components) {
        if (!cellId || !Array.isArray(components)) return [];
        return components.filter(comp =>
            comp.storage && 
            comp.storage.cells && 
            Array.isArray(comp.storage.cells) && 
            comp.storage.cells.includes(cellId)
        );
    },

    /**
     * Get location name by ID with sanitization
     * @param {string} locationId - Location ID
     * @param {Array} locations - All available locations
     * @returns {string} Location name or empty string
     */
    getLocationName: function (locationId, locations) {
        if (!locationId || !Array.isArray(locations)) return '';
        const location = locations.find(loc => loc.id === locationId);
        return location ? window.App.utils.sanitize.value(location.name) : '';
    },

    /**
     * Get drawer name by ID with sanitization
     * @param {string} drawerId - Drawer ID
     * @param {Array} drawers - Available drawers
     * @returns {string} Drawer name or empty string
     */
    getDrawerName: function (drawerId, drawers) {
        if (!drawerId || !Array.isArray(drawers)) return '';
        const drawer = drawers.find(d => d.id === drawerId);
        return drawer ? window.App.utils.sanitize.value(drawer.name) : '';
    },

    /**
     * Get cell coordinate or nickname by ID
     * @param {string} cellId - Cell ID
     * @param {Array} cells - Available cells
     * @returns {string} Cell coordinate/nickname or empty string
     */
    getCellName: function (cellId, cells) {
        if (!cellId || !Array.isArray(cells)) return '';
        const cell = cells.find(c => c.id === cellId);
        if (!cell) return '';
        return cell.nickname || cell.coordinate || '';
    },

    /**
     * Format storage location for display
     * @param {Object} storage - Storage object
     * @param {Array} locations - Available locations
     * @param {Array} drawers - Available drawers
     * @param {Array} cells - Available cells
     * @returns {string} Formatted storage location string
     */
    formatStorageDisplay: function (storage, locations, drawers, cells) {
        if (!storage || typeof storage !== 'object') return 'Not assigned';

        const parts = [];

        // Add location
        if (storage.locationId) {
            const locationName = this.getLocationName(storage.locationId, locations);
            if (locationName) {
                parts.push(locationName);
            }
        }

        // Add location details
        if (storage.details) {
            parts.push(`(${storage.details})`);
        }

        // Add drawer
        if (storage.drawerId) {
            const drawerName = this.getDrawerName(storage.drawerId, drawers);
            if (drawerName) {
                parts.push(`→ ${drawerName}`);
                
                // Add cells
                if (storage.cells && Array.isArray(storage.cells) && storage.cells.length > 0) {
                    const cellNames = storage.cells.map(cellId => 
                        this.getCellName(cellId, cells)
                    ).filter(name => name);
                    
                    if (cellNames.length > 0) {
                        parts.push(`[${cellNames.join(', ')}]`);
                    }
                }
            }
        }

        return parts.length > 0 ? parts.join(' ') : 'Not assigned';
    },

    /**
     * Validate storage assignment
     * @param {Object} storage - Storage object to validate
     * @param {Array} locations - Available locations
     * @param {Array} drawers - Available drawers
     * @param {Array} cells - Available cells
     * @returns {Object} Validation result with isValid and errors array
     */
    validateStorage: function (storage, locations, drawers, cells) {
        const errors = [];
        const formattedStorage = this.formatStorage(storage);

        // Check location exists
        if (formattedStorage.locationId) {
            const location = locations.find(loc => loc.id === formattedStorage.locationId);
            if (!location) {
                errors.push('Selected location does not exist');
            }
        }

        // Check drawer exists and belongs to location
        if (formattedStorage.drawerId) {
            const drawer = drawers.find(d => d.id === formattedStorage.drawerId);
            if (!drawer) {
                errors.push('Selected drawer does not exist');
            } else if (formattedStorage.locationId && drawer.locationId !== formattedStorage.locationId) {
                errors.push('Selected drawer does not belong to the selected location');
            }
        }

        // Check cells exist and belong to drawer
        if (formattedStorage.cells && formattedStorage.cells.length > 0) {
            if (!formattedStorage.drawerId) {
                errors.push('Cells selected but no drawer specified');
            } else {
                const invalidCells = [];
                formattedStorage.cells.forEach(cellId => {
                    const cell = cells.find(c => c.id === cellId);
                    if (!cell) {
                        invalidCells.push(cellId);
                    } else if (cell.drawerId !== formattedStorage.drawerId) {
                        invalidCells.push(`${cellId} (wrong drawer)`);
                    }
                });
                
                if (invalidCells.length > 0) {
                    errors.push(`Invalid cells: ${invalidCells.join(', ')}`);
                }
            }
        }

        return {
            isValid: errors.length === 0,
            errors: errors,
            formattedStorage: formattedStorage
        };
    },

    /**
     * Clear storage assignment from components
     * @param {Array} components - Components array
     * @param {string} type - Type of clearing: 'location', 'drawer', 'cell'
     * @param {string} id - ID of the location/drawer/cell being cleared
     * @returns {Array} Updated components array
     */
    clearStorageAssignments: function (components, type, id) {
        if (!Array.isArray(components) || !type || !id) return components;

        return components.map(comp => {
            if (!comp.storage) return comp;

            const updatedComp = { ...comp };
            const storage = { ...comp.storage };

            switch (type) {
                case 'location':
                    if (storage.locationId === id) {
                        // Clear entire storage when location is removed
                        updatedComp.storage = { locationId: '', details: '', drawerId: '', cells: [] };
                    }
                    break;

                case 'drawer':
                    if (storage.drawerId === id) {
                        // Clear drawer and cells, keep location
                        storage.drawerId = '';
                        storage.cells = [];
                        updatedComp.storage = storage;
                    }
                    break;

                case 'cell':
                    if (storage.cells && Array.isArray(storage.cells)) {
                        const filteredCells = storage.cells.filter(cellId => cellId !== id);
                        if (filteredCells.length !== storage.cells.length) {
                            storage.cells = filteredCells;
                            updatedComp.storage = storage;
                        }
                    }
                    break;
            }

            return updatedComp;
        });
    },

    /**
     * Get storage statistics for a location
     * @param {string} locationId - Location ID
     * @param {Array} components - All components
     * @param {Array} drawers - All drawers
     * @param {Array} cells - All cells
     * @returns {Object} Storage statistics
     */
    getLocationStorageStats: function (locationId, components, drawers, cells) {
        const locationComponents = this.getComponentsForLocation(locationId, components);
        const locationDrawers = this.getFilteredDrawers(locationId, drawers);
        
        let totalCells = 0;
        let occupiedCells = 0;

        locationDrawers.forEach(drawer => {
            const drawerCells = this.getFilteredCells(drawer.id, cells);
            totalCells += drawerCells.length;
            
            drawerCells.forEach(cell => {
                const cellComponents = this.getComponentsForCell(cell.id, components);
                if (cellComponents.length > 0) {
                    occupiedCells++;
                }
            });
        });

        return {
            totalComponents: locationComponents.length,
            totalDrawers: locationDrawers.length,
            totalCells: totalCells,
            occupiedCells: occupiedCells,
            freeCells: totalCells - occupiedCells,
            occupancyRate: totalCells > 0 ? Math.round((occupiedCells / totalCells) * 100) : 0
        };
    }
};

console.log("Form helpers updated with unified storage system.");