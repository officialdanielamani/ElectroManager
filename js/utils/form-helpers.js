// js/utils/form-helpers.js

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
    generateCellGrid: function(drawer, filteredCells, selectedCells, handleCellToggle, UI, readOnly = false) {
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
     * Format storage info object consistently
     * @param {Object} storageInfo - Raw storage info from component data
     * @returns {Object} Properly formatted storage info
     */
    formatStorageInfo: function(storageInfo) {
        // Handle null/malformed storageInfo
        if (!storageInfo || typeof storageInfo === 'string' || storageInfo === '[object Object]') {
            return { locationId: '', drawerId: '', cells: [] };
        }
        
        // Ensure all required fields exist
        return {
            locationId: storageInfo.locationId || '',
            drawerId: storageInfo.drawerId || '',
            cells: Array.isArray(storageInfo.cells) ? storageInfo.cells : []
        };
    },
    
    /**
     * Format location info object consistently
     * @param {Object} locationInfo - Raw location info from component data
     * @returns {Object} Properly formatted location info
     */
    formatLocationInfo: function(locationInfo) {
        // Handle null/malformed locationInfo
        if (!locationInfo || typeof locationInfo === 'string' || locationInfo === '[object Object]') {
            return { locationId: '', details: '' };
        }
        
        return locationInfo;
    },
    
    /**
     * Get filtered drawers based on selected location
     * @param {string} locationId - Selected location ID
     * @param {Array} allDrawers - All available drawers
     * @returns {Array} Filtered drawers for this location
     */
    getFilteredDrawers: function(locationId, allDrawers) {
        if (!locationId) return [];
        return allDrawers.filter(drawer => drawer.locationId === locationId);
    },
    
    /**
     * Get filtered cells for a drawer
     * @param {string} drawerId - Selected drawer ID
     * @param {Array} allCells - All available cells
     * @returns {Array} Filtered cells for this drawer
     */
    getFilteredCells: function(drawerId, allCells) {
        if (!drawerId) return [];
        return allCells.filter(cell => cell.drawerId === drawerId);
    },
    
    /**
     * Render drawer selector UI section
     * @param {Object} options - Various options and data for the drawer selector
     * @returns {React.Element} Drawer selector UI
     */
    renderDrawerSelector: function(options) {
        const {
            UI,
            storageInfo,
            locations,
            filteredDrawers,
            selectedDrawerId,
            filteredCells,
            selectedCells,
            handleStorageLocationChange,
            handleDrawerChange,
            handleCellToggle,
            readOnly = false
        } = options;
        
        const themeColors = UI.getThemeColors();
        // Store reference to this object for helper methods
        const helpers = this;
        
        return React.createElement('div', {
            className: `mb-4 p-3 border rounded bg-${themeColors.background}`
        },
            React.createElement('h4', {
                className: `text-sm font-medium mb-2 text-${themeColors.textSecondary}`
            }, readOnly ? "Drawer Storage Location" : "Drawer Storage Assignment"),

            // Location dropdown for storage
            React.createElement('div', { className: "mb-3" },
                React.createElement('label', { htmlFor: "storage-location", className: UI.forms.label }, 
                    "Storage Location"),
                readOnly ? 
                    // View-only mode
                    React.createElement('div', { 
                        className: `p-2 border border-${themeColors.border} rounded bg-${themeColors.cardBackground}`
                    }, helpers.getLocationName(storageInfo.locationId, locations) || "Not assigned") :
                    // Edit mode
                    React.createElement('select', {
                        id: "storage-location",
                        name: "locationId",
                        className: UI.forms.select,
                        value: storageInfo.locationId || '',
                        onChange: handleStorageLocationChange,
                        disabled: readOnly
                    },
                        React.createElement('option', { value: "" }, "-- Select location --"),
                        locations.map(loc => React.createElement('option', { key: loc.id, value: loc.id }, loc.name))
                    )
            ),

            // Drawer dropdown (filtered by location)
            storageInfo.locationId && React.createElement('div', { className: "mb-3" },
                React.createElement('label', { htmlFor: "storage-drawer", className: UI.forms.label }, "Drawer"),
                filteredDrawers.length === 0 ?
                    React.createElement('p', {
                        className: `text-sm text-${themeColors.textMuted} italic`
                    }, "No drawers found for this location.") :
                    readOnly ?
                        // View-only mode
                        React.createElement('div', { 
                            className: `p-2 border border-${themeColors.border} rounded bg-${themeColors.cardBackground}`
                        }, helpers.getDrawerName(storageInfo.drawerId, filteredDrawers) || "Not assigned") :
                        // Edit mode
                        React.createElement('select', {
                            id: "storage-drawer",
                            name: "drawerId",
                            className: UI.forms.select,
                            value: selectedDrawerId,
                            onChange: handleDrawerChange,
                            disabled: readOnly
                        },
                            React.createElement('option', { value: "" }, "-- Select drawer --"),
                            filteredDrawers.map(drawer => React.createElement('option', { key: drawer.id, value: drawer.id }, drawer.name))
                        )
            ),

            // Cell grid for selection (when drawer is selected)
            selectedDrawerId && React.createElement('div', { className: "mb-3" },
                React.createElement('label', { className: UI.forms.label }, readOnly ? "Selected Cell(s)" : "Select Cell(s)"),
                filteredCells.length === 0 ?
                    React.createElement('p', {
                        className: `text-sm text-${themeColors.textMuted} italic`
                    }, "No cells defined for this drawer yet.") :
                    React.createElement('div', null,
                        // Cell selection instructions (not shown in view-only mode)
                        !readOnly && React.createElement('p', {
                            className: `text-xs text-${themeColors.textMuted} mb-2`
                        }, "Click on cells to select/deselect. Multiple cells can be selected."),

                        // Display the grid
                        React.createElement('div', {
                            className: `inline-block border border-${themeColors.border} bg-${themeColors.cardBackground} p-1`
                        },
                            helpers.generateCellGrid(
                                filteredDrawers.find(d => d.id === selectedDrawerId),
                                filteredCells,
                                selectedCells,
                                handleCellToggle,
                                UI,
                                readOnly
                            )
                        ),

                        // Selected cells display
                        React.createElement('div', { className: "mt-2" },
                            React.createElement('p', { className: `text-xs text-${themeColors.textSecondary}` }, "Selected Cells: ",
                                selectedCells.length === 0
                                    ? React.createElement('span', { className: `italic text-${themeColors.textMuted}` }, "None")
                                    : selectedCells.map(cellId => {
                                        const cell = filteredCells.find(c => c.id === cellId);
                                        return cell ? (cell.nickname || cell.coordinate) : cellId;
                                    }).join(', ')
                            )
                        )
                    )
            )
        );
    },
    
    /**
     * Get location name by ID
     * @param {string} locationId - Location ID
     * @param {Array} locations - All available locations
     * @returns {string} Location name or empty string
     */
    getLocationName: function(locationId, locations) {
        if (!locationId) return '';
        const location = locations.find(loc => loc.id === locationId);
        return location ? location.name : '';
    },
    
    /**
     * Get drawer name by ID
     * @param {string} drawerId - Drawer ID
     * @param {Array} drawers - Available drawers
     * @returns {string} Drawer name or empty string
     */
    getDrawerName: function(drawerId, drawers) {
        if (!drawerId) return '';
        const drawer = drawers.find(d => d.id === drawerId);
        return drawer ? drawer.name : '';
    }
};

// Update formatStorageInfo to sanitize inputs
window.App.utils.formHelpers.formatStorageInfo = function(storageInfo) {
    // Simply use the centralized sanitization utility
    return window.App.utils.sanitize.object({
        locationId: storageInfo?.locationId || '',
        drawerId: storageInfo?.drawerId || '',
        cells: Array.isArray(storageInfo?.cells) ? storageInfo.cells : []
    });
};

// Update formatLocationInfo to sanitize inputs
window.App.utils.formHelpers.formatLocationInfo = function(locationInfo) {
    // Use the centralized sanitization utility
    return window.App.utils.sanitize.object({
        locationId: locationInfo?.locationId || '',
        details: locationInfo?.details || ''
    });
};

// Update getLocationName to sanitize output
window.App.utils.formHelpers.getLocationName = function(locationId, locations) {
    if (!locationId) return '';
    const location = locations.find(loc => loc.id === locationId);
    return location ? window.App.utils.sanitize.value(location.name) : '';
};

// Update getDrawerName to sanitize output  
window.App.utils.formHelpers.getDrawerName = function(drawerId, drawers) {
    if (!drawerId) return '';
    const drawer = drawers.find(d => d.id === drawerId);
    return drawer ? window.App.utils.sanitize.value(drawer.name) : '';
};