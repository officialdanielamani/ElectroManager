// js/components/BulkEditForm.js - With improved theme support

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Bulk Edit Modal Form.
 */
window.App.components.BulkEditForm = ({
    // Props
    categories, // Array: List of available category strings
    commonFootprints, // Array: List of common footprint strings
    selectedCount, // Number: How many components are selected
    locations, // Array: List of location objects
    drawers, // Array: List of drawer objects
    cells, // Array: List of cell objects
    onApply, // Function: Callback when apply button clicked, passes bulk edit data
    onCancel // Function: Callback when cancel button or close icon clicked
}) => {
    // Get UI constants
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;
    const { formHelpers } = window.App.utils;

    // Internal state for the bulk edit form fields
    const [bulkData, setBulkData] = useState({
        category: '',
        customCategory: '',
        type: '',
        quantity: '',
        quantityAction: 'set', // 'set', 'increment', 'decrement'
        price: '',
        priceAction: 'set', // 'set', 'increase', 'decrease'
        footprint: '',
        customFootprint: '',
        // Flag fields
        favorite: null, // null = no change, true/false = set value
        bookmark: null,
        star: null,
        // Location fields
        locationAction: 'keep', // 'keep', 'set', 'clear'
        locationId: '',
        locationDetails: '',
        // Storage/drawer fields
        storageAction: 'keep', // 'keep', 'set', 'clear'
        storageLocationId: '',
        drawerId: '',
        selectedCells: [], // Array of cell IDs
    });

    // State for UI components
    const [showDrawerSelector, setShowDrawerSelector] = useState(true);
    const [filteredDrawers, setFilteredDrawers] = useState([]);
    const [filteredCells, setFilteredCells] = useState([]);
    const [selectedDrawer, setSelectedDrawer] = useState(null);

    // Update filtered drawers when storage location changes
    useEffect(() => {
        if (bulkData.storageLocationId) {
            const filtered = formHelpers.getFilteredDrawers(bulkData.storageLocationId, drawers);
            setFilteredDrawers(filtered);
    
            // Reset drawer selection if the current drawer doesn't belong to the new location
            if (bulkData.drawerId && !filtered.some(drawer => drawer.id === bulkData.drawerId)) {
                setBulkData(prev => ({
                    ...prev,
                    drawerId: '',
                    selectedCells: []
                }));
                setSelectedDrawer(null);
            }
        } else {
            setFilteredDrawers([]);
            setBulkData(prev => ({
                ...prev,
                drawerId: '',
                selectedCells: []
            }));
            setSelectedDrawer(null);
        }
    }, [bulkData.storageLocationId, drawers]);

    // Update drawer and cells when drawer selection changes
    useEffect(() => {
        if (bulkData.drawerId) {
            const drawer = drawers.find(d => d.id === bulkData.drawerId);
            setSelectedDrawer(drawer);
            setFilteredCells(formHelpers.getFilteredCells(bulkData.drawerId, cells));
        } else {
            setSelectedDrawer(null);
            setFilteredCells([]);
            setBulkData(prev => ({
                ...prev,
                selectedCells: []
            }));
        }
    }, [bulkData.drawerId, drawers, cells]);

    // Handle input changes
    const handleChange = (e) => {
        const { name, value } = e.target;
        setBulkData(prevData => ({
            ...prevData,
            [name]: value
        }));
    };

    // Handle checkbox changes
    const handleCheckboxChange = (e) => {
        const { name, checked } = e.target;
        setBulkData(prevData => ({
            ...prevData,
            [name]: checked
        }));
    };

    // Handle category selection, including "Add new..."
    const handleCategoryChange = (e) => {
        const value = e.target.value;
        setBulkData(prevData => ({
            ...prevData,
            category: value,
            // Reset custom category if a standard one is selected
            customCategory: value === '__custom__' ? prevData.customCategory : ''
        }));
    };

    // Handle footprint selection, including "Custom..."
    const handleFootprintChange = (e) => {
        const value = e.target.value;
        setBulkData(prevData => ({
            ...prevData,
            footprint: value,
            // Reset custom footprint if a standard one is selected
            customFootprint: value === '__custom__' ? prevData.customFootprint : ''
        }));
    };

    // Handle cell selection/deselection
    const handleCellToggle = (cellId) => {
        // Find the cell from filtered cells
        const cell = filteredCells.find(c => c.id === cellId);

        // Don't allow toggling unavailable cells
        if (!cell || cell.available === false) {
            return;
        }

        setBulkData(prevData => {
            const updatedCells = [...prevData.selectedCells];

            // Toggle selected state
            if (updatedCells.includes(cellId)) {
                // Remove cell if already selected
                return {
                    ...prevData,
                    selectedCells: updatedCells.filter(id => id !== cellId)
                };
            } else {
                // Add cell if not already selected
                return {
                    ...prevData,
                    selectedCells: [...updatedCells, cellId]
                };
            }
        });
    };

    // Add new handler for toggle switch changes
    const handleBooleanChange = (name, value) => {
        setBulkData(prevData => ({
            ...prevData,
            [name]: value
        }));
    };

    // Handle applying the changes
    const handleApply = () => {
        onApply(bulkData); // Pass the current bulk edit state to the parent handler
    };

    const generateCellGrid = () => {
        if (!selectedDrawer) return null;
        return formHelpers.generateCellGrid(
            selectedDrawer,
            filteredCells,
            bulkData.selectedCells,
            handleCellToggle,
            UI
        );
    };

    // Get selected cells information
    const getSelectedCellsInfo = () => {
        if (bulkData.selectedCells.length === 0) return "";

        return bulkData.selectedCells.map(cellId => {
            const cell = cells.find(c => c.id === cellId);
            // Only include available cells in the info
            if (cell && cell.available !== false) {
                return cell.nickname || cell.coordinate;
            }
            return cellId;
        }).filter(Boolean).join(", "); // Filter out any undefined values
    };

    // --- Main Render ---
    return (
        React.createElement('div', { className: `fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4 z-30` },
            React.createElement('div', { className: `bg-${UI.getThemeColors().cardBackground} rounded-lg shadow-xl max-w-xl w-full max-h-[90vh] flex flex-col` },
                // Header (Fixed at top)
                React.createElement('div', { className: `p-6 pb-3 border-b border-${UI.getThemeColors().border} flex-shrink-0` },
                    React.createElement('div', { className: "flex justify-between items-center mb-4" },
                        React.createElement('h2', { className: `text-xl font-semibold text-${UI.getThemeColors().textPrimary}` }, `Bulk Edit ${selectedCount} Component(s)`),
                        React.createElement('button', {
                            onClick: onCancel,
                            className: `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().textSecondary}`,
                            title: "Close"
                        },
                            React.createElement('svg', {
                                xmlns: "http://www.w3.org/2000/svg",
                                className: "h-6 w-6",
                                fill: "none",
                                viewBox: "0 0 24 24",
                                stroke: "currentColor"
                            },
                                React.createElement('path', {
                                    strokeLinecap: "round",
                                    strokeLinejoin: "round",
                                    strokeWidth: 2,
                                    d: "M6 18L18 6M6 6l12 12"
                                })
                            )
                        )
                    ),
                    React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textSecondary}` }, "Apply changes to selected components. Leave fields blank/unchanged to keep existing values.")
                ),

                // Scrollable Form Content
                React.createElement('div', { className: `p-6 pt-3 overflow-y-auto flex-grow` },
                    // Form Fields
                    React.createElement('div', { className: "space-y-4" },
                        // Category
                        React.createElement('div', null,
                            React.createElement('label', { className: UI.forms.label }, "Change Category To"),
                            React.createElement('select', {
                                name: "category",
                                className: UI.forms.select,
                                value: bulkData.category,
                                onChange: handleCategoryChange
                            },
                                React.createElement('option', { value: "" }, "-- Keep existing category --"),
                                (categories || []).sort().map(cat => React.createElement('option', { key: cat, value: cat }, cat)),
                                React.createElement('option', { value: "__custom__" }, "Add new category...")
                            ),
                            bulkData.category === '__custom__' && React.createElement('input', {
                                name: "customCategory",
                                type: "text",
                                placeholder: "Enter new category name",
                                className: UI.forms.input,
                                value: bulkData.customCategory || '',
                                onChange: handleChange
                            })
                        ),
                        // Type
                        React.createElement('div', null,
                            React.createElement('label', { className: UI.forms.label }, "Change Type To"),
                            React.createElement('input', {
                                name: "type",
                                type: "text",
                                placeholder: "Leave blank to keep existing type",
                                className: UI.forms.input,
                                value: bulkData.type,
                                onChange: handleChange
                            })
                        ),
                        // Quantity Adjustment
                        React.createElement('div', null,
                            React.createElement('label', { className: UI.forms.label }, "Adjust Quantity"),
                            React.createElement('div', { className: "flex space-x-2" },
                                React.createElement('select', {
                                    name: "quantityAction",
                                    className: UI.forms.select,
                                    value: bulkData.quantityAction,
                                    onChange: handleChange
                                },
                                    React.createElement('option', { value: "set" }, "Set quantity to"),
                                    React.createElement('option', { value: "increment" }, "Add quantity"),
                                    React.createElement('option', { value: "decrement" }, "Subtract quantity")
                                ),
                                React.createElement('input', {
                                    name: "quantity",
                                    type: "number",
                                    min: "0",
                                    placeholder: "Value",
                                    className: UI.forms.input,
                                    value: bulkData.quantity,
                                    onChange: handleChange
                                })
                            ),
                            React.createElement('p', { className: UI.forms.hint }, "Leave value blank for no quantity change.")
                        ),
                        // Price Adjustment
                        React.createElement('div', null,
                            React.createElement('label', { className: UI.forms.label }, "Adjust Price"),
                            React.createElement('div', { className: "flex space-x-2" },
                                React.createElement('select', {
                                    name: "priceAction",
                                    className: UI.forms.select,
                                    value: bulkData.priceAction,
                                    onChange: handleChange
                                },
                                    React.createElement('option', { value: "set" }, "Set price to"),
                                    React.createElement('option', { value: "increase" }, "Increase price by"),
                                    React.createElement('option', { value: "decrease" }, "Decrease price by")
                                ),
                                React.createElement('input', {
                                    name: "price",
                                    type: "number",
                                    min: "0",
                                    step: "0.01",
                                    placeholder: "Value",
                                    className: UI.forms.input,
                                    value: bulkData.price,
                                    onChange: handleChange
                                })
                            ),
                            React.createElement('p', { className: UI.forms.hint }, "Leave value blank for no price change.")
                        ),
                        // Footprint Adjustment
                        React.createElement('div', null,
                            React.createElement('label', { className: UI.forms.label }, "Change Footprint To"),
                            React.createElement('select', {
                                name: "footprint",
                                className: UI.forms.select,
                                value: bulkData.footprint,
                                onChange: handleFootprintChange
                            },
                                React.createElement('option', { value: "" }, "-- Keep existing footprint --"),
                                React.createElement('option', { value: "__custom__" }, "Custom footprint..."),
                                (commonFootprints || []).map(fp => React.createElement('option', { key: fp, value: fp }, fp)),
                            ),
                            bulkData.footprint === '__custom__' && React.createElement('input', {
                                name: "customFootprint",
                                type: "text",
                                placeholder: "Enter custom footprint",
                                className: UI.forms.input,
                                value: bulkData.customFootprint || '',
                                onChange: handleChange
                            })
                        ),

                        // --- Storage Location Section ---
                        React.createElement('div', { className: `bg-${UI.getThemeColors().background} p-4 rounded border border-${UI.getThemeColors().border} mt-6` },
    React.createElement('div', { className: "flex justify-between items-center" },
        React.createElement('h3', { className: `text-md font-medium mb-1 text-${UI.getThemeColors().textSecondary}` }, "Storage Location"),
        React.createElement('button', {
            type: "button",
            className: `${UI.colors.primary.text} text-sm`,
            onClick: () => setShowDrawerSelector(!showDrawerSelector)
        }, showDrawerSelector ? "Hide Drawer Selector" : "Show Drawer Selector")
    ),

                            // Location Action
                            React.createElement('div', { className: "mb-3" },
                                React.createElement('label', { className: UI.forms.label }, "Location Action"),
                                React.createElement('select', {
                                    name: "locationAction",
                                    className: UI.forms.select,
                                    value: bulkData.locationAction,
                                    onChange: handleChange
                                },
                                    React.createElement('option', { value: "keep" }, "Keep existing location"),
                                    React.createElement('option', { value: "set" }, "Set new location"),
                                    React.createElement('option', { value: "clear" }, "Clear location")
                                )
                            ),

                            // Show location selection if "set" is selected
                            bulkData.locationAction === 'set' && React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-3" },
                                // Location Dropdown
                                React.createElement('div', null,
                                    React.createElement('label', { className: UI.forms.label }, "Location"),
                                    React.createElement('select', {
                                        name: "locationId",
                                        className: UI.forms.select,
                                        value: bulkData.locationId,
                                        onChange: handleChange
                                    },
                                        React.createElement('option', { value: "" }, "-- Select location --"),
                                        (locations || []).map(loc => React.createElement('option', { key: loc.id, value: loc.id }, loc.name))
                                    )
                                ),
                                // Location Details
                                React.createElement('div', null,
                                    React.createElement('label', { className: UI.forms.label }, "Location Details (Optional)"),
                                    React.createElement('input', {
                                        name: "locationDetails",
                                        type: "text",
                                        placeholder: "e.g., Shelf 3, Box A",
                                        className: UI.forms.input,
                                        value: bulkData.locationDetails,
                                        onChange: handleChange
                                    })
                                )
                            ),

                            // Drawer Storage Section (expandable)
                            showDrawerSelector && React.createElement('div', {
                                className: `mt-4 border-t border-${UI.getThemeColors().borderLight} pt-4`
                            },
                                React.createElement('h4', {
                                    className: `font-medium mb-2 text-${UI.getThemeColors().textSecondary}`
                                }, "Drawer Storage Assignment"),

                                // Storage Action
                                React.createElement('div', { className: "mb-3" },
                                    React.createElement('label', { className: UI.forms.label }, "Drawer Action"),
                                    React.createElement('select', {
                                        name: "storageAction",
                                        className: UI.forms.select,
                                        value: bulkData.storageAction,
                                        onChange: handleChange
                                    },
                                        React.createElement('option', { value: "keep" }, "Keep existing drawer"),
                                        React.createElement('option', { value: "set" }, "Set new drawer"),
                                        React.createElement('option', { value: "clear" }, "Clear drawer assignment")
                                    )
                                ),

                                // Show drawer selection when "set" is selected
                                bulkData.storageAction === 'set' && formHelpers.renderDrawerSelector({
                                    UI,
                                    storageInfo: {
                                        locationId: bulkData.storageLocationId || '',
                                        drawerId: bulkData.drawerId || '',
                                        cells: bulkData.selectedCells || []
                                    },
                                    locations,
                                    filteredDrawers,
                                    selectedDrawerId: bulkData.drawerId,
                                    filteredCells,
                                    selectedCells: bulkData.selectedCells,
                                    handleStorageLocationChange: (e) => {
                                        const { name, value } = e.target;
                                        if (name === 'locationId') {
                                            setBulkData(prev => ({
                                                ...prev,
                                                storageLocationId: value,
                                                drawerId: '',
                                                selectedCells: []
                                            }));
                                        }
                                    },
                                    handleDrawerChange: (e) => {
                                        setBulkData(prev => ({
                                            ...prev,
                                            drawerId: e.target.value,
                                            selectedCells: []
                                        }));
                                    },
                                    handleCellToggle
                                })
                            )
                        ),

                        // --- Favorite, Bookmark, Star Options ---
                        React.createElement('div', { className: `border-t border-${UI.getThemeColors().border} pt-4 mt-4` },
                            React.createElement('div', { className: UI.typography.sectionTitle }, "Mark Components As:"),
                            React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-3 gap-4" },
                                // Favorite Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-red-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                fillRule: "evenodd",
                                                d: "M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z",
                                                clipRule: "evenodd"
                                            })
                                        ),
                                        "Favorite"
                                    ),
                                    React.createElement('select', {
                                        name: "favorite",
                                        className: UI.forms.select,
                                        value: bulkData.favorite === null ? '' : bulkData.favorite.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange(
                                                "favorite",
                                                value === '' ? null : value === 'true'
                                            );
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Mark as Favorite"),
                                        React.createElement('option', { value: "false" }, "Remove Favorite mark")
                                    )
                                ),

                                // Bookmark Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-blue-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                d: "M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
                                            })
                                        ),
                                        "Bookmark"
                                    ),
                                    React.createElement('select', {
                                        name: "bookmark",
                                        className: UI.forms.select,
                                        value: bulkData.bookmark === null ? '' : bulkData.bookmark.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange(
                                                "bookmark",
                                                value === '' ? null : value === 'true'
                                            );
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Add Bookmark"),
                                        React.createElement('option', { value: "false" }, "Remove Bookmark")
                                    )
                                ),

                                // Star Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-yellow-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                d: "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                                            })
                                        ),
                                        "Star"
                                    ),
                                    React.createElement('select', {
                                        name: "star",
                                        className: UI.forms.select,
                                        value: bulkData.star === null ? '' : bulkData.star.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange(
                                                "star",
                                                value === '' ? null : value === 'true'
                                            );
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Add Star"),
                                        React.createElement('option', { value: "false" }, "Remove Star")
                                    )
                                )
                            )
                        )
                    ) // End Form Fields
                ),

                // Action Buttons (Fixed at bottom)
                React.createElement('div', {
                    className: `flex justify-end space-x-3 p-4 border-t border-${UI.getThemeColors().border} bg-${UI.getThemeColors().background} rounded-b-lg flex-shrink-0`
                },
                    React.createElement('button', {
                        className: UI.buttons.secondary,
                        onClick: onCancel
                    }, "Cancel"),
                    React.createElement('button', {
                        className: UI.buttons.primary,
                        onClick: handleApply
                    }, "Apply Changes")
                )
            ) // End Modal Content
        ) // End Modal Backdrop
    );
};

console.log("BulkEditForm component loaded with theme-aware styling."); // For debugging