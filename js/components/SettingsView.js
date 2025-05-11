// js/components/SettingsView.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Settings Page View.
 * Provides access to import/export, category management, low stock config, and display settings.
 */
window.App.components.SettingsView = ({
    // Props
    categories, // Array: List of category strings
    lowStockConfig, // Object: Low stock thresholds { category: threshold }
    currencySymbol, // String: Currency symbol
    showTotalValue, // Boolean: Whether to show total value in summary
    footprints, // Array: List of footprint strings
    jsonData, // String: Text content for import/export text area
    importError, // String: Error or success message after import
    exportMessage, // String: Message after export/save attempt
    theme, // String: Current UI theme
    // Callbacks
    onExportComponents, // Function: Called when Export Components button is clicked
    onExportConfig, // Function: Called when Export Config button is clicked
    onImportComponentsFile, // Function(event): Called when component file is selected for import
    onImportConfigFile, // Function(event): Called when config file is selected for import
    onDownloadJson, // Function: Called when Download JSON button is clicked
    onCopyJson, // Function: Called when Copy JSON button is clicked
    onClearJsonArea, // Function: Called when Clear Area button is clicked
    onChangeCurrency, // Function(event): Called when currency input changes
    onChangeShowTotalValue, // Function(event): Called when show total value checkbox changes
    onAddLowStock, // Function(category, threshold): Called to add/update low stock threshold
    onRemoveLowStock, // Function(category): Called to remove low stock threshold
    onEditCategory, // Function(oldName, newName): Called to rename a category
    onDeleteCategory, // Function(category): Called to delete a category
    onAddDefaultCategory, // Function: Called to add a "Default" category
    onSaveComponentsLS, // Function: Called to force save components to localStorage
    onSaveConfig, // Function: Called to force save config to localStorage
    onClearStorage, // Function: Called to clear all localStorage
    onAddFootprint, // Function(newFootprint): Called to add a new footprint
    onEditFootprint, // Function(oldFootprint, newFootprint): Called to rename a footprint
    onDeleteFootprint, // Function(footprint): Called to delete a footprint
    onExportLocations, // Function: Called when Export Locations button is clicked
    onImportLocationsFile, // Function(event): Called when locations file is selected for import
    onRestoreDefaultFootprints, // Function: Called to restore default footprints
    onChangeTheme, // Function(theme): Called when theme is changed
}) => {

    // Ensure we have the UI object
    const { UI } = window.App.utils;
    const { useState } = React;
    const { FootprintManager } = window.App.components;

    // Internal state for settings form controls
    const [editingCategory, setEditingCategory] = useState(null); // Category being edited
    const [newCategoryName, setNewCategoryName] = useState(''); // New name for edited category
    const [newLowStockCategory, setNewLowStockCategory] = useState(''); // Category for new low stock threshold
    const [newLowStockThreshold, setNewLowStockThreshold] = useState(5); // Threshold value

    // --- Event Handlers ---

    // Handle low stock threshold submission
    const handleAddLowStock = () => {
        // Sanitize the category input
        const category = window.App.utils.sanitize.value(newLowStockCategory);
        // Parse and validate the threshold value
        const threshold = parseInt(window.App.utils.sanitize.value(newLowStockThreshold), 10) || 5;    
        if (!category || threshold < 1) {
            alert("Please select a category and enter a threshold greater than 0.");
            return;
        }
        onAddLowStock(category, threshold);
        // Reset the form
        setNewLowStockThreshold(5);
    };

    // Start editing category
    const handleStartEditCategory = (category) => {
        // Sanitize the category before setting state
        const sanitizedCategory = window.App.utils.sanitize.value(category);
        setEditingCategory(sanitizedCategory);
        setNewCategoryName(sanitizedCategory);
    };

    // Save edited category name
    const handleSaveCategory = () => {
        // Sanitize the new name
        const sanitizedOldName = window.App.utils.sanitize.value(editingCategory);
        const trimmedNewName = window.App.utils.sanitize.value(newCategoryName.trim());
        // Validate
        if (!trimmedNewName) {
            alert("Category name cannot be empty.");
            return;
        }
        if (trimmedNewName === sanitizedOldName) {
            // No change, just cancel
            setEditingCategory(null);
            setNewCategoryName('');
            return;
        }
        if (categories.includes(trimmedNewName)) {
            alert(`Category "${trimmedNewName}" already exists.`);
            return;
        }
        // Call parent handler and reset state
        onEditCategory(sanitizedOldName, trimmedNewName);
        setEditingCategory(null);
        setNewCategoryName('');
    };
    
    // Cancel category editing
    const handleCancelCategoryEdit = () => {
        setEditingCategory(null);
        setNewCategoryName('');
    };

    // Handle low stock category selection, also update threshold if already configured
    const handleLowStockCategoryChange = (e) => {
        const category = e.target.value;
        setNewLowStockCategory(category);
        // If there's already a threshold for this category, load it
        if (category && lowStockConfig && lowStockConfig[category]) {
            setNewLowStockThreshold(lowStockConfig[category]);
        } else {
            // Otherwise reset to default
            setNewLowStockThreshold(5);
        }
    };

    // --- Render ---
    return (
        React.createElement('div', { className: "space-y-8" },

            // --- System Info Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "System Information"),

                // Version information
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('h3', { className: UI.typography.heading.h3 }, "Electro Manager"),
                    React.createElement('div', { className: "flex items-center mb-3" },
                        React.createElement('span', { className: `${UI.typography.weight.semibold} ${UI.colors.primary.text}` }, "Version 0.1.7beta"),
                        React.createElement('span', { className: `ml-2 px-2 py-1 ${UI.colors.success.bg} text-white text-xs rounded-full` }, "Latest Update")
                    ),
                    // Update date
                    "Updated: 26 April 2025",

                    // Changes in this version 
                    React.createElement('div', { className: "mb-4 mt-4" },
                        React.createElement('h4', { className: UI.typography.sectionTitle }, "Changes in this version:"),
                        React.createElement('ul', { className: "list-disc list-inside text-sm space-y-1 ml-2" },
                            React.createElement('li', null, "Adding advanced filtering option for better search"),
                            React.createElement('li', null, "Remap some UI for more consistancy"),
                            React.createElement('li', null, "Add function to assign component Location and Drawers"),
                            React.createElement('li', null, "Import and Export the location and drawers data"),
                            React.createElement('li', null, "Fixed error on save data for drawers and cells"),
                            React.createElement('li', null, "Added ability to mark cells as unavailable in drawers"),
                            React.createElement('li', null, "Added function to clear all components from a cell at once"),
                            React.createElement('li', null, "Added view of drawer list for specific locations"),
                            React.createElement('li', null, "Note: Card View in holding development"),
                        )
                    ),

                    React.createElement('div', { className: `mb-4 pt-4 ${UI.utils.borderTop}` },
                        React.createElement('h4', { className: UI.typography.sectionTitle }, "Info:"),
                        React.createElement('ul', { className: "list-disc list-inside text-sm text-red-500 space-y-1 ml-2" },
                            React.createElement('li', null, "All data is store on your browser session, not save in cloud or 3rd party"),
                            React.createElement('li', null, "Clear data, change browser profile or incognito will effect your file"),
                            React.createElement('li', null, "Please export the JSON data of Component and Location for your own backup"),
                            React.createElement('li', null, "This software is BETA development, don't use for mission critical application"),
                            React.createElement('li', null, "We don't held responsibilities for any data loss, harm or damage while and if using this application"),
                        ),
                    ),
                    // Credits & Info
                    React.createElement('div', { className: `mt-6 pt-4 ${UI.utils.borderTop} ${UI.typography.small}` },
                        React.createElement('p', null, "Electro Manager an Electronics Inventory System by DANP-EDNA"),
                        React.createElement('p', { className: "mt-1" }, "Built with React and TailwindCSS"),
                    )
                )
            ),
            //-- End of System Info

            // --- Import/Export Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Import / Export Data"),
                React.createElement('div', { className: UI.cards.body },
                    // Messages (Error, Success, Info)
                    importError && React.createElement('div', {
                        className: `p-3 rounded mb-4 text-sm ${importError.includes('success') || importError.includes('finished') ? UI.status.success : UI.status.error}`
                    }, importError),
                    exportMessage && !importError && React.createElement('div', {
                        className: UI.status.info
                    }, exportMessage),
                    // Components & Config Export/Import Buttons
                    React.createElement('p', { className: UI.forms.hint }, "Please save the JSON file for backup as you may accidentally clear all data"),
                    React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-6 mb-6" },
                        // Components Data Section
                        React.createElement('div', null,
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Components Data"),
                            React.createElement('div', { className: "flex flex-wrap gap-2" },
                                React.createElement('button', {
                                    onClick: onExportComponents,
                                    className: UI.buttons.primary
                                }, "Export Components"),
                                React.createElement('input', {
                                    type: "file",
                                    id: "import-components-file",
                                    accept: ".json",
                                    onChange: onImportComponentsFile,
                                    className: "hidden"
                                }),
                                React.createElement('label', {
                                    htmlFor: "import-components-file",
                                    className: UI.buttons.success
                                }, "Import Components")
                            ),
                            React.createElement('p', { className: UI.forms.hint }, "Import replaces components. Export generates JSON below.")
                        ),
                        // Configuration Section
                        React.createElement('div', null,
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Configuration"),
                            React.createElement('div', { className: "flex flex-wrap gap-2" },
                                React.createElement('button', {
                                    onClick: onExportConfig,
                                    className: UI.buttons.info
                                }, "Export Config"),
                                React.createElement('input', {
                                    type: "file",
                                    id: "import-config-file",
                                    accept: ".json",
                                    onChange: onImportConfigFile,
                                    className: "hidden"
                                }),
                                React.createElement('label', {
                                    htmlFor: "import-config-file",
                                    className: UI.buttons.accent
                                }, "Import Config")
                            ),
                            React.createElement('p', { className: UI.forms.hint }, "Includes categories, settings. Import merges/overwrites.")
                        )
                    ),

                    //Import/Export Location & Drawers
                    React.createElement('div', null,
                        React.createElement('h4', { className: UI.typography.sectionTitle }, "Locations & Drawers"),
                        React.createElement('div', { className: "flex flex-wrap gap-2" },
                            React.createElement('button', {
                                onClick: onExportLocations,
                                className: UI.buttons.warning
                            }, "Export Locations & Drawers"),
                            React.createElement('input', {
                                type: "file",
                                id: "import-locations-file",
                                accept: ".json",
                                onChange: onImportLocationsFile,
                                className: "hidden"
                            }),
                            React.createElement('label', {
                                htmlFor: "import-locations-file",
                                className: UI.buttons.warning
                            }, "Import Locations & Drawers")
                        ),
                        React.createElement('p', { className: UI.forms.hint }, "Export/import locations, drawers and cells.")
                    ),

                    // Add Force Save Buttons here
                    React.createElement('div', { className: `border-t pt-4 mb-4` },
                        React.createElement('h4', { className: UI.typography.sectionTitle }, "Local Storage"),
                        React.createElement('p', { className: "text-xs text-red-500 mt-2" }, "Warn: The data is stored on browser session, if you clear browser data or incognito mode, this will wipe the data."),
                        React.createElement('div', { className: "flex flex-wrap gap-3" },
                            React.createElement('button', {
                                onClick: onSaveComponentsLS,
                                className: UI.buttons.primary
                            }, "Force Save Components"),
                            React.createElement('button', {
                                onClick: onSaveConfig,
                                className: UI.buttons.info
                            }, "Force Save Configuration")
                        ),
                        React.createElement('p', { className: UI.forms.hint }, "Data is auto-saved. Use buttons above to force save.")
                    ),

                    // JSON Text Area (conditional)
                    jsonData && React.createElement('div', { className: `mt-4 ${UI.utils.borderTop} pt-4` },
                        React.createElement('label', {
                            htmlFor: "json-data-area",
                            className: UI.forms.label
                        }, "Generated JSON Data:"),
                        React.createElement('textarea', {
                            id: "json-data-area",
                            readOnly: true,
                            className: `w-full p-2 border border-${UI.getThemeColors().border} rounded h-40 font-mono text-xs bg-${UI.getThemeColors().background.replace('gray-900', 'gray-800').replace('gray-100', 'gray-50')}`,
                            value: jsonData
                        }),
                        React.createElement('div', { className: "flex flex-wrap gap-2 mt-2" },
                            React.createElement('button', {
                                onClick: onDownloadJson,
                                className: UI.buttons.accent
                            }, "Download JSON"),
                            React.createElement('button', {
                                onClick: onCopyJson,
                                className: UI.buttons.secondary
                            }, "Copy JSON"),
                            React.createElement('button', {
                                onClick: onClearJsonArea,
                                className: UI.buttons.warning
                            }, "Clear Area")
                        )
                    )
                )
            ), // End Import/Export Section

            // Theme Configuration Section
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', {
                    className: `${UI.typography.heading.h2} ${UI.cards.header}`
                },
                    "Theme Configuration"
                ),
                React.createElement('div', { className: UI.cards.body },
                    // This is your ThemeSwitcher component
                    React.createElement(
                        window.App.components.ThemeSwitcher,
                        {
                            currentTheme: theme,
                            onThemeChange: onChangeTheme
                        }
                    )
                )
            ),

            // --- Category Management Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Category Management"),
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('p', { className: `mb-4 ${UI.typography.body}` },
                        `Edit or delete categories. Deleting moves components to "${categories.includes('Default') ? 'Default' : 'Uncategorized'}".`
                    ),
                    React.createElement('div', { className: "overflow-x-auto" },
                        React.createElement('table', { className: UI.tables.container },
                            React.createElement('thead', { className: UI.tables.header.row },
                                React.createElement('tr', null,
                                    React.createElement('th', { className: UI.tables.header.cell }, "Category Name"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Component Count"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                                )
                            ),
                            React.createElement('tbody', { className: "bg-white divide-y divide-gray-200" },
                                categories.length === 0 ?
                                    React.createElement('tr', null,
                                        React.createElement('td', { colSpan: "3", className: "py-4 px-4 text-center text-gray-500 italic" }, "No categories defined.")
                                    ) :
                                    categories.sort().map(category =>
                                        React.createElement('tr', { key: category, className: UI.tables.body.row },
                                            // Category Name (editable)
                                            React.createElement('td', { className: UI.tables.body.cell },
                                                editingCategory === category ?
                                                    React.createElement('input', {
                                                        type: "text",
                                                        value: newCategoryName,
                                                        onChange: (e) => setNewCategoryName(e.target.value),
                                                        className: UI.forms.input,
                                                        autoFocus: true,
                                                        onKeyDown: (e) => e.key === 'Enter' && handleSaveCategory()
                                                    }) :
                                                    React.createElement('span',  { className: UI.tables.body.cell }, category)
                                            ),
                                            // Component Count
                                            React.createElement('td', { className: `${UI.tables.body.cell} text-center` },
                                                categories.length > 0 ? categories.filter(cat => cat === category).length : 0
                                            ),
                                            // Actions
                                            React.createElement('td', { className: UI.tables.body.cellAction },
                                                editingCategory === category ?
                                                    // Edit Mode Actions
                                                    React.createElement('div', { className: "flex justify-center space-x-2" },
                                                        React.createElement('button', {
                                                            onClick: handleSaveCategory,
                                                            className: UI.buttons.small.success,
                                                            title: "Save"
                                                        }, "Save"),
                                                        React.createElement('button', {
                                                            onClick: handleCancelCategoryEdit,
                                                            className: UI.buttons.small.secondary,
                                                            title: "Cancel"
                                                        }, "Cancel")
                                                    ) :
                                                    // Normal Mode Actions
                                                    React.createElement('div', { className: "flex justify-center space-x-2" },
                                                        React.createElement('button', {
                                                            onClick: () => handleStartEditCategory(category),
                                                            className: UI.buttons.small.primary,
                                                            title: "Edit"
                                                        }, "Edit"),
                                                        React.createElement('button', {
                                                            onClick: () => onDeleteCategory(category),
                                                            className: UI.buttons.small.danger,
                                                            title: "Delete",
                                                            disabled: category === 'Default' && categories.some(c => c === 'Default')
                                                        }, "Delete")
                                                    )
                                            )
                                        )
                                    )
                            )
                        )
                    ),
                    React.createElement('div', { className: "mt-4" },
                        React.createElement('button', {
                            onClick: onAddDefaultCategory,
                            className: UI.buttons.secondary,
                            disabled: categories.includes('Default')
                        }, 'Ensure "Default" Category Exists')
                    )
                )
            ), // End Category Management Section

            // --- Footprint Management Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Footprint Management"),
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('p', { className: `mb-4 ${UI.typography.body}` },
                        "Manage the list of footprints available for components. These will appear in the dropdown when adding or editing components."
                    ),
                    React.createElement(FootprintManager, {
                        footprints,
                        onAddFootprint,
                        onEditFootprint,
                        onDeleteFootprint,
                        onRestoreDefaults: onRestoreDefaultFootprints
                    })
                )
            ), // End Footprint Management Section

            // --- Low Stock Configuration Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Low Stock Thresholds"),
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('p', { className: `mb-4 ${UI.typography.body}` }, "Set quantity thresholds for categories to highlight low stock items."),
                    React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-8" },
                        // Set Threshold Section
                        React.createElement('div', null,
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Set Threshold"),
                            React.createElement('div', { className: "space-y-3" },
                                // Category Dropdown
                                React.createElement('div', null,
                                    React.createElement('label', {
                                        htmlFor: "low-stock-category",
                                        className: UI.forms.label
                                    }, "Category"),
                                    React.createElement('select', {
                                        id: "low-stock-category",
                                        className: UI.forms.select,
                                        value: newLowStockCategory,
                                        onChange: handleLowStockCategoryChange
                                    },
                                        React.createElement('option', { value: "" }, "-- Select category --"),
                                        categories.sort().map(category => React.createElement('option', { key: category, value: category },
                                            `${category} ${lowStockConfig[category] ? `(Current: ${lowStockConfig[category]})` : ''}`
                                        ))
                                    )
                                ),
                                // Threshold Input
                                React.createElement('div', null,
                                    React.createElement('label', {
                                        htmlFor: "low-stock-threshold",
                                        className: UI.forms.label
                                    }, "Threshold Quantity"),
                                    React.createElement('input', {
                                        id: "low-stock-threshold",
                                        type: "number",
                                        min: "1",
                                        className: UI.forms.input,
                                        value: newLowStockThreshold,
                                        onChange: (e) => setNewLowStockThreshold(Math.max(1, parseInt(e.target.value, 10) || 1)),
                                        placeholder: "e.g., 5"
                                    })
                                ),
                                // Add/Update Button
                                React.createElement('div', null,
                                    React.createElement('button', {
                                        onClick: handleAddLowStock,
                                        disabled: !newLowStockCategory,
                                        className: !newLowStockCategory ? `${UI.buttons.secondary} cursor-not-allowed` : UI.buttons.primary
                                    }, lowStockConfig[newLowStockCategory] ? 'Update Threshold' : 'Add Threshold')
                                )
                            )
                        ),
                        // Current Thresholds Section
                        React.createElement('div', null,
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Current Thresholds"),
                            Object.keys(lowStockConfig).length === 0 ?
                                React.createElement('p', { className: "text-gray-500 italic text-sm" }, "No thresholds configured.") :
                                React.createElement('div', { className: `border ${UI.utils.rounded} max-h-60 overflow-y-auto` },
                                    React.createElement('table', { className: UI.tables.container },
                                        React.createElement('thead', { className: `${UI.tables.header.row} sticky top-0` },
                                            React.createElement('tr', null,
                                                React.createElement('th', { className: UI.tables.header.cell }, "Category"),
                                                React.createElement('th', { className: UI.tables.header.cell }, "Threshold"),
                                                React.createElement('th', { className: UI.tables.header.cell }, "Action")
                                            )
                                        ),
                                        React.createElement('tbody', { 
                                            className: `divide-y divide-${UI.getThemeColors().border} bg-${UI.getThemeColors().cardBackground}` 
                                        },
                                            Object.entries(lowStockConfig).sort(([catA], [catB]) => catA.localeCompare(catB)).map(([category, threshold]) =>
                                                React.createElement('tr', { key: category, className: UI.tables.body.row },
                                                    React.createElement('td', { className: UI.tables.body.cell }, category),
                                                    React.createElement('td', { className: `${UI.tables.body.cell} text-center` }, threshold),
                                                    React.createElement('td', { className: UI.tables.body.cellAction },
                                                        React.createElement('button', {
                                                            onClick: () => onRemoveLowStock(category),
                                                            className: `${UI.colors.danger.text} hover:text-red-800 text-xs`,
                                                            title: "Remove threshold"
                                                        }, "Remove")
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                        )
                    )
                )
            ),

            // --- Display Settings Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Display Settings"),
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-6" },
                        // Currency Symbol Input
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "currency-symbol",
                                className: UI.forms.label
                            }, "Currency Symbol"),
                            React.createElement('input', {
                                id: "currency-symbol",
                                type: "text",
                                value: currencySymbol,
                                onChange: onChangeCurrency,
                                className: "w-full md:w-1/2 p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500",
                                placeholder: "e.g., $, €, MYR, SDG"
                            }),
                            React.createElement('p', { className: UI.forms.hint }, "Symbol used for displaying prices.")
                        ),
                        // Show Total Value Toggle
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "show-total-value",
                                className: "flex items-center space-x-2 text-sm font-medium text-gray-700 cursor-pointer"
                            },
                                React.createElement('input', {
                                    id: "show-total-value",
                                    type: "checkbox",
                                    checked: showTotalValue,
                                    onChange: onChangeShowTotalValue,
                                    className: UI.forms.checkbox
                                }),
                                React.createElement('span', { className: UI.typography.body }, "Show Total Inventory Value in Summary")
                            ),
                            React.createElement('p', { className: UI.forms.hint }, "Calculates and displays the sum of (price * quantity) for all components.")
                        )
                    )
                )
            ), // End Display Settings Section

            // --- Storage Management Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Storage Management"),
                React.createElement('div', { className: UI.cards.body },

                    React.createElement('p', { className: `mb-4 ${UI.typography.body}` }, "Data is auto-saved. Use buttons below to force save or clear all data."),

                    // Force Save Buttons
                    React.createElement('div', { className: "flex flex-wrap gap-3 mb-4" },
                        React.createElement('button', {
                            onClick: onSaveComponentsLS,
                            className: UI.buttons.primary
                        }, "Force Save Components"),
                        React.createElement('button', {
                            onClick: onSaveConfig,
                            className: UI.buttons.info
                        }, "Force Save Configuration"),
                    ),

                    // Backup Recommendations
                    React.createElement('div', { className: `mb-4 p-3 ${UI.colors.background.alt} ${UI.utils.rounded} ${UI.utils.border}` },
                        React.createElement('h5', { className: `${UI.typography.weight.medium} mb-2` }, "Backup Recommendations"),
                        React.createElement('p', { className: `${UI.typography.body}` },
                            "Regular backups help prevent data loss. We recommend:"
                        ),
                        React.createElement('ul', { className: `list-disc list-inside ${UI.typography.body} space-y-1 ml-2` },
                            React.createElement('li', null, "Export components data at least once per week"),
                            React.createElement('li', null, "Export locations and drawers after making changes"),
                            React.createElement('li', null, "Keep backup files in multiple locations"),
                            React.createElement('li', null, "Test imports occasionally to verify backup integrity")
                        )
                    ),

                    // Danger Zone -
                    React.createElement('div', { className: `mt-6 pt-4 ${UI.utils.borderTop}` },
                        React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-4" },
                            // Clear All Data
                            React.createElement('div', { className: "border border-red-200 rounded p-3 bg-red-50" },
                                React.createElement('h5', { className: "font-medium text-red-700 mb-2" }, "Danger Zone | Delete all data"),
                                React.createElement('p', { className: `text-red-700 ${UI.typography.body} mb-2` },
                                    "Warning: Deletes all item in database, and clear all settings (LocalStorage & IndexedDB). There is no way back"
                                ),
                                React.createElement('button', {
                                    onClick: onClearStorage,
                                    className: UI.buttons.danger
                                }, "Clear All Data"),
                                React.createElement('p', { className: "text-xs text-red-600 mt-1" }, "I am aware what I am doing when clicking the button above"),
                            ),
                        )
                    )
                )
            ),
        )
    )
}