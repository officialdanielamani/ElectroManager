// js/components/shared/LocationSelector.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.components.shared = window.App.components.shared || {};

/**
* LocationSelector - Comprehensive location and storage assignment component
* Handles location, drawer, and cell selection in a unified interface
*/
window.App.components.shared.LocationSelector = ({
   // Storage data
   locationInfo = {},
   storageInfo = {},
   locations = [],
   drawers = [],
   cells = [],
   
   // Event handlers
   onLocationChange,
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
    const [selectedCells, setSelectedCells] = useState(storageInfo.cells || []);

    // Memoize normalized objects to prevent recreation on every render
    const normalizedStorageInfo = useMemo(() =>
        formHelpers.formatStorageInfo(storageInfo),
        [storageInfo.locationId, storageInfo.drawerId, storageInfo.cells?.length, storageInfo.cells?.join('')]
    );

    const normalizedLocationInfo = useMemo(() =>
        formHelpers.formatLocationInfo(locationInfo),
        [locationInfo.locationId, locationInfo.details]
    );

    // Memoize handlers to prevent recreation on every render
    const handleStorageUpdate = useCallback((newStorageInfo) => {
        if (onStorageChange) {
            onStorageChange(newStorageInfo);
        }
    }, [onStorageChange]);

    const handleLocationUpdate = useCallback((newLocationInfo) => {
        if (onLocationChange) {
            onLocationChange(newLocationInfo);
        }
    }, [onLocationChange]);

    // Update filtered drawers when storage location changes
    useEffect(() => {
        if (normalizedStorageInfo.locationId) {
            const filtered = formHelpers.getFilteredDrawers(normalizedStorageInfo.locationId, drawers);
            setFilteredDrawers(filtered);

            // Reset drawer if it doesn't belong to new location
            if (normalizedStorageInfo.drawerId &&
                !filtered.some(drawer => drawer.id === normalizedStorageInfo.drawerId)) {
                handleStorageUpdate({
                    ...normalizedStorageInfo,
                    drawerId: '',
                    cells: []
                });
                setSelectedCells([]);
            }
        } else {
            setFilteredDrawers([]);
        }
    }, [normalizedStorageInfo.locationId, normalizedStorageInfo.drawerId, handleStorageUpdate]);

    // Update filtered cells when drawer changes
    useEffect(() => {
        if (normalizedStorageInfo.drawerId) {
            const filtered = formHelpers.getFilteredCells(normalizedStorageInfo.drawerId, cells);
            setFilteredCells(filtered);
        } else {
            setFilteredCells([]);
            setSelectedCells([]);
        }
    }, [normalizedStorageInfo.drawerId]);

    // Sync selected cells with storage info
    useEffect(() => {
        const cells = normalizedStorageInfo.cells || [];
        if (JSON.stringify(selectedCells) !== JSON.stringify(cells)) {
            setSelectedCells(cells);
        }
    }, [normalizedStorageInfo.cells?.length, normalizedStorageInfo.cells?.join(''), selectedCells]);

    // Handle basic location change
    const handleLocationChange = useCallback((e) => {
        const { name, value } = e.target;
        const sanitizedValue = window.App.utils.sanitize.validateAllowedChars(value);

        if (name === 'locationId') {
            handleLocationUpdate({
                ...normalizedLocationInfo,
                locationId: sanitizedValue
            });
        } else if (name === 'details') {
            handleLocationUpdate({
                ...normalizedLocationInfo,
                details: sanitizedValue
            });
        }
    }, [normalizedLocationInfo, handleLocationUpdate]);

    // Handle storage location change
    const handleStorageLocationChange = useCallback((e) => {
        const { name, value } = e.target;
        const sanitizedValue = window.App.utils.sanitize.validateAllowedChars(value);

        if (name === 'locationId') {
            handleStorageUpdate({
                locationId: sanitizedValue,
                drawerId: '',
                cells: []
            });
        }
    }, [handleStorageUpdate]);

    // Handle drawer selection
    const handleDrawerChange = useCallback((e) => {
        const drawerId = window.App.utils.sanitize.validateAllowedChars(e.target.value);

        handleStorageUpdate({
            ...normalizedStorageInfo,
            drawerId: drawerId,
            cells: []
        });
        setSelectedCells([]);
    }, [normalizedStorageInfo, handleStorageUpdate]);

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
            ...normalizedStorageInfo,
            cells: updatedCells
        });
    }, [readOnly, filteredCells, allowMultipleCells, selectedCells, normalizedStorageInfo, handleStorageUpdate]);

    // Handle validated input changes
    const handleLocationDetailsChange = useCallback((value) => {
        handleLocationUpdate({
            ...normalizedLocationInfo,
            details: value
        });
    }, [normalizedLocationInfo, handleLocationUpdate]);

    // Find selected drawer for grid display
    const selectedDrawer = useMemo(() =>
        filteredDrawers.find(d => d.id === normalizedStorageInfo.drawerId),
        [filteredDrawers, normalizedStorageInfo.drawerId]
    );

    return React.createElement('div', {
        className: `border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().background} p-4`
    },
        // Header with optional toggle for drawer section
        React.createElement('div', { className: "flex justify-between items-center mb-4" },
            React.createElement('h3', {
                className: `text-md font-medium text-${UI.getThemeColors().textSecondary}`
            }, label),
            !hideToggle && showDrawerSelector && !readOnly && React.createElement('button', {
                type: "button",
                className: `text-${UI.getThemeColors().primary} text-sm hover:underline`,
                onClick: () => setShowStorageSection(!showStorageSection)
            }, showStorageSection ? "Hide Drawer Selector" : "Show Drawer Selector")
        ),

        // Basic Location Section - Only show if showLocationDetails is true
        showLocationDetails && React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-4" },
            // Location dropdown
            React.createElement('div', null,
                React.createElement('label', { htmlFor: "location-select", className: UI.forms.label }, "Location"),
                readOnly ?
                    React.createElement('div', {
                        className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                    }, formHelpers.getLocationName(normalizedLocationInfo.locationId, locations) || "Not assigned") :
                    React.createElement('select', {
                        id: "location-select",
                        name: "locationId",
                        className: UI.forms.select,
                        value: normalizedLocationInfo.locationId || '',
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
            React.createElement('div', null,
                React.createElement(window.App.components.shared.ValidatedInput, {
                    name: "details",
                    value: normalizedLocationInfo.details || '',
                    onChange: handleLocationDetailsChange,
                    fieldType: "locationDescription",
                    label: "Location Details (Optional)",
                    placeholder: "e.g., Shelf 3, Box A",
                    readOnly,
                    showCharCounter: !readOnly
                })
            )
        ),

        // Drawer Storage Section
        (showStorageSection || readOnly) && showDrawerSelector && React.createElement('div', {
            className: `border-t border-${UI.getThemeColors().borderLight} pt-4 mt-4`
        },
            React.createElement('h4', {
                className: `text-sm font-medium mb-3 text-${UI.getThemeColors().textSecondary}`
            }, readOnly ? "Assigned Drawer Storage" : "Drawer Storage Assignment"),

            // Storage location dropdown
            React.createElement('div', { className: "mb-3" },
                React.createElement('label', { htmlFor: "storage-location", className: UI.forms.label },
                    "Storage Location"),
                readOnly ?
                    React.createElement('div', {
                        className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                    }, formHelpers.getLocationName(normalizedStorageInfo.locationId, locations) || "Not assigned") :
                    React.createElement('select', {
                        id: "storage-location",
                        name: "locationId",
                        className: UI.forms.select,
                        value: normalizedStorageInfo.locationId || '',
                        onChange: handleStorageLocationChange,
                        disabled: readOnly
                    },
                        React.createElement('option', { value: "" }, "-- Select storage location --"),
                        locations.map(loc =>
                            React.createElement('option', { key: loc.id, value: loc.id }, loc.name)
                        )
                    )
            ),

            // Drawer selection
            normalizedStorageInfo.locationId && React.createElement('div', { className: "mb-3" },
                React.createElement('label', { htmlFor: "drawer-select", className: UI.forms.label }, "Drawer"),
                filteredDrawers.length === 0 ?
                    React.createElement('p', {
                        className: `text-sm text-${UI.getThemeColors().textMuted} italic`
                    }, "No drawers found for this location.") :
                    readOnly ?
                        React.createElement('div', {
                            className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                        }, formHelpers.getDrawerName(normalizedStorageInfo.drawerId, filteredDrawers) || "Not assigned") :
                        React.createElement('select', {
                            id: "drawer-select",
                            name: "drawerId",
                            className: UI.forms.select,
                            value: normalizedStorageInfo.drawerId || '',
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
            normalizedStorageInfo.drawerId && showCellGrid && React.createElement('div', { className: "mb-3" },
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

        // Usage hint - FIXED: Changed hideLocationSection to showLocationDetails
        !readOnly && showLocationDetails && React.createElement('p', { className: UI.forms.hint },
            "Specify where this component is physically stored. Location is for general placement, drawer storage is for precise cell-level organization."
        )
    );
};

console.log("LocationSelector component loaded with comprehensive location and storage management.");