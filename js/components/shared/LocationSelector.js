// js/components/shared/LocationSelector.js

window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.components.shared = window.App.components.shared || {};

/**
 * LocationSelector - Comprehensive location and storage assignment component
 * Updated to use unified storage object
 */
window.App.components.shared.LocationSelector = ({
    // Storage data
    storage = {},
    locations = [],
    drawers = [],
    cells = [],
    
    // Event handlers
    onStorageChange,
    
    // UI configuration
    showDrawerSelector = true,
    showLocationDetails = true,
    readOnly = false,
    label = "Storage Location",
    required = false,
    hideToggle = false,
    
    // Advanced options
    allowMultipleCells = true,
    showCellGrid = true,
    expandedByDefault = false
}) => {
    const { UI } = window.App.utils;
    const { formHelpers } = window.App.utils;
    const { useState, useEffect, useMemo, useCallback } = React;

    // Local state
    const [showStorageSection, setShowStorageSection] = useState(expandedByDefault);
    const [filteredDrawers, setFilteredDrawers] = useState([]);
    const [filteredCells, setFilteredCells] = useState([]);
    const [selectedCells, setSelectedCells] = useState([]);

    // Memoize normalized storage object to prevent recreation on every render
    const normalizedStorage = useMemo(() =>
        formHelpers.formatStorage(storage),
        [storage.locationId, storage.drawerId, storage.cells?.length, storage.cells?.join(''), storage.details]
    );

    // Memoize handler to prevent recreation on every render
    const handleStorageUpdate = useCallback((updates) => {
        if (onStorageChange) {
            onStorageChange({
                ...normalizedStorage,
                ...updates
            });
        }
    }, [normalizedStorage, onStorageChange]);

    // Update filtered drawers when location changes
    useEffect(() => {
        if (normalizedStorage.locationId) {
            const filtered = formHelpers.getFilteredDrawers(normalizedStorage.locationId, drawers);
            setFilteredDrawers(filtered);

            // Reset drawer if it doesn't belong to new location
            if (normalizedStorage.drawerId &&
                !filtered.some(drawer => drawer.id === normalizedStorage.drawerId)) {
                handleStorageUpdate({
                    drawerId: '',
                    cells: []
                });
                setSelectedCells([]);
            }
        } else {
            setFilteredDrawers([]);
        }
    }, [normalizedStorage.locationId, normalizedStorage.drawerId, drawers, handleStorageUpdate]);

    // Update filtered cells when drawer changes
    useEffect(() => {
        if (normalizedStorage.drawerId) {
            const filtered = formHelpers.getFilteredCells(normalizedStorage.drawerId, cells);
            setFilteredCells(filtered);
        } else {
            setFilteredCells([]);
            setSelectedCells([]);
        }
    }, [normalizedStorage.drawerId, cells]);

    // Sync selected cells with storage
    useEffect(() => {
        const cells = normalizedStorage.cells || [];
        if (JSON.stringify(selectedCells) !== JSON.stringify(cells)) {
            setSelectedCells(cells);
        }
    }, [normalizedStorage.cells?.length, normalizedStorage.cells?.join(''), selectedCells]);

    // Handle location change
    const handleLocationChange = useCallback((e) => {
        const locationId = window.App.utils.sanitize.validateAllowedChars(e.target.value);
        
        handleStorageUpdate({
            locationId: locationId,
            drawerId: '',  // Reset drawer when location changes
            cells: []      // Reset cells when location changes
        });
    }, [handleStorageUpdate]);

    // Handle location details change
    const handleDetailsChange = useCallback((value) => {
        handleStorageUpdate({
            details: value
        });
    }, [handleStorageUpdate]);

    // Handle drawer selection
    const handleDrawerChange = useCallback((e) => {
        const drawerId = window.App.utils.sanitize.validateAllowedChars(e.target.value);

        handleStorageUpdate({
            drawerId: drawerId,
            cells: []  // Reset cells when drawer changes
        });
        setSelectedCells([]);
    }, [handleStorageUpdate]);

    // Handle cell toggle
    const handleCellToggle = useCallback((cellId) => {
        if (readOnly) return;

        const sanitizedCellId = window.App.utils.sanitize.validateAllowedChars(cellId);
        const cell = filteredCells.find(c => c.id === sanitizedCellId);

        // Don't allow toggling unavailable cells
        if (!cell || cell.available === false) return;

        let updatedCells;

        if (allowMultipleCells) {
            // Multiple cell selection
            updatedCells = selectedCells.includes(sanitizedCellId)
                ? selectedCells.filter(id => id !== sanitizedCellId)
                : [...selectedCells, sanitizedCellId];
        } else {
            // Single cell selection
            updatedCells = selectedCells.includes(sanitizedCellId) ? [] : [sanitizedCellId];
        }

        setSelectedCells(updatedCells);
        handleStorageUpdate({
            cells: updatedCells
        });
    }, [readOnly, filteredCells, allowMultipleCells, selectedCells, handleStorageUpdate]);

    // Find selected drawer for grid display
    const selectedDrawer = useMemo(() =>
        filteredDrawers.find(d => d.id === normalizedStorage.drawerId),
        [filteredDrawers, normalizedStorage.drawerId]
    );

    return React.createElement('div', {
        className: `border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().background} p-4`
    },
        // Header with optional toggle for drawer section
        React.createElement('div', { className: "flex justify-between items-center mb-4" },
            React.createElement('h3', {
                className: `text-md font-medium text-${UI.getThemeColors().textSecondary}`
            }, label),
        ),

        // Basic Location Section
        React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-4" },
            // Location dropdown
            React.createElement('div', null,
                React.createElement('label', { htmlFor: "location-select", className: UI.forms.label }, "Location"),
                readOnly ?
                    React.createElement('div', {
                        className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                    }, formHelpers.getLocationName(normalizedStorage.locationId, locations) || "Not assigned") :
                    React.createElement('select', {
                        id: "location-select",
                        name: "locationId",
                        className: UI.forms.select,
                        value: normalizedStorage.locationId || '',
                        onChange: handleLocationChange,
                        required,
                        disabled: readOnly
                    },
                        React.createElement('option', { value: "" }, "-- No location assigned --"),
                        locations.map(loc =>
                            React.createElement('option', { key: loc.id, value: loc.id }, loc.name)
                        )
                    )
            ),

            // Location details
            showLocationDetails && React.createElement('div', null,
                React.createElement(window.App.components.shared.ValidatedInput, {
                    name: "details",
                    value: normalizedStorage.details || '',
                    onChange: handleDetailsChange,
                    fieldType: "locationDescription",
                    label: "Location Details (Optional)",
                    placeholder: "e.g., Shelf 3, Box A",
                    readOnly,
                    showCharCounter: !readOnly
                })
            )
        ),

        // Drawer Storage Section
        (showDrawerSelector && normalizedStorage.locationId) && 
React.createElement('div', {
    className: `border-t border-${UI.getThemeColors().borderLight} pt-4 mt-4`
},
    React.createElement('h4', {
        className: `text-sm font-medium mb-3 text-${UI.getThemeColors().textSecondary}`
    }, readOnly ? "Assigned Drawer Storage" : "Drawer Storage Assignment"),


            // Drawer selection
            React.createElement('div', { className: "mb-3" },
                React.createElement('label', { htmlFor: "drawer-select", className: UI.forms.label }, "Drawer"),
                filteredDrawers.length === 0 ?
                    React.createElement('p', {
                        className: `text-sm text-${UI.getThemeColors().textMuted} italic`
                    }, "No drawers found for this location.") :
                    readOnly ?
                        React.createElement('div', {
                            className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                        }, formHelpers.getDrawerName(normalizedStorage.drawerId, filteredDrawers) || "Not assigned") :
                        React.createElement('select', {
                            id: "drawer-select",
                            name: "drawerId",
                            className: UI.forms.select,
                            value: normalizedStorage.drawerId || '',
                            onChange: handleDrawerChange,
                            disabled: readOnly
                        },
                            React.createElement('option', { value: "" }, "-- Select drawer --"),
                            filteredDrawers.map(drawer =>
                                React.createElement('option', { key: drawer.id, value: drawer.id }, drawer.name)
                            )
                        )
            ),

            // Cell selection
            normalizedStorage.drawerId && showCellGrid && React.createElement('div', { className: "mb-3" },
                React.createElement('label', { className: UI.forms.label },
                    readOnly ? "Assigned Cell(s)" : "Select Cell(s)"),
                filteredCells.length === 0 ?
                    React.createElement('p', {
                        className: `text-sm text-${UI.getThemeColors().textMuted} italic`
                    }, "No cells defined for this drawer yet.") :
                    React.createElement('div', null,
                        // Grid instructions
                        !readOnly && React.createElement('p', {
                            className: `text-xs text-${UI.getThemeColors().textMuted} mb-2`
                        }, allowMultipleCells ?
                            "Click cells to select/deselect. Multiple cells can be selected." :
                            "Click a cell to select it. Only one cell can be selected."
                        ),

                        // Cell grid with proper scrollable container
                        React.createElement('div', {
                            className: "overflow-auto max-w-full",
                            style: {
                                scrollbarWidth: 'thin',
                                scrollbarColor: '#cbd5e0 #edf2f7'
                            }
                        },
                            React.createElement('div', {
                                className: `inline-block border border-${UI.getThemeColors().border} bg-${UI.getThemeColors().cardBackground} p-2`
                            },
                                formHelpers.generateCellGrid(
                                    selectedDrawer,
                                    filteredCells,
                                    selectedCells,
                                    handleCellToggle,
                                    UI,
                                    readOnly
                                )
                            )
                        ),

                        // Selected cells display
                        React.createElement('div', { className: "mt-2" },
                            React.createElement('p', {
                                className: `text-xs text-${UI.getThemeColors().textSecondary}`
                            },
                                allowMultipleCells ? "Selected Cells: " : "Selected Cell: ",
                                selectedCells.length === 0 ?
                                    React.createElement('span', {
                                        className: `italic text-${UI.getThemeColors().textMuted}`
                                    }, "None") :
                                    selectedCells.map(cellId => {
                                        const cell = filteredCells.find(c => c.id === cellId);
                                        return cell ? (cell.nickname || cell.coordinate) : cellId;
                                    }).join(', ')
                            )
                        )
                    )
            )
        ),

        // Usage hint
        !readOnly && showLocationDetails && React.createElement('p', { className: UI.forms.hint },
            "Specify where this component is physically stored. Location is for general placement, drawer storage is for precise cell-level organization."
        )
    );
};

console.log("LocationSelector loaded");