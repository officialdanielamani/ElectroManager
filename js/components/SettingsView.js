// js/components/SettingsView.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Settings Page View.
 * Provides access to import/export, category management, low stock config, and display settings.
 */
window.App.components.SettingsView = ({
    // Data props
    categories = [], // Array: List of category strings
    lowStockConfig = {}, // Object: Low stock thresholds { category: threshold }
    footprints = [], // Array: List of footprint strings
    components = [], // Array: All components
    locations = [], // Array: All locations
    drawers = [], // Array: All drawers
    cells = [], // Array: All cells

    // Configuration props
    currencySymbol = 'RM', // String: Currency symbol
    showTotalValue = false, // Boolean: Whether to show total value in summary
    theme = 'light', // String: Current UI theme

    // Callbacks that update parent state
    onUpdateCategories, // Function(categories): Update categories in parent
    onUpdateLowStockConfig, // Function(config): Update lowStockConfig in parent
    onUpdateComponents, // Function(components): Update components in parent
    onUpdateLocations, // Function(locations): Update locations in parent
    onUpdateDrawers, // Function(drawers): Update drawers in parent
    onUpdateCells, // Function(cells): Update cells in parent
    onUpdateFootprints, // Function(footprints): Update footprints in parent

    // Configuration update callbacks
    onChangeCurrency, // Function(e): Called when currency input changes
    onChangeShowTotalValue, // Function(e): Called when show total value checkbox changes
    onChangeTheme, // Function(theme): Called when theme is changed

}) => {
    // Get UI constants and required hooks
    const { UI } = window.App.utils;
    const { storage } = window.App.utils;
    const { useState } = React;
    const { FootprintManager } = window.App.components;

    // Internal state for settings form controls
    const [editingCategory, setEditingCategory] = useState(null); // Category being edited
    const [newCategoryName, setNewCategoryName] = useState(''); // New name for edited category
    const [newLowStockCategory, setNewLowStockCategory] = useState(''); // Category for new low stock threshold
    const [newLowStockThreshold, setNewLowStockThreshold] = useState(5); // Threshold value
    const [viewMode, setViewMode] = useState('table'); // 'table' or 'card'
    const [itemsPerPage, setItemsPerPage] = useState('all'); //
    const [newCategory, setNewCategory] = useState('');

    // State for import/export
    const [importError, setImportError] = useState(''); // Error or success message after import
    const [exportMessage, setExportMessage] = useState(''); // Message after export/save attempt

    // --- Helper Functions ---

    // Clear status messages
    const clearStatusMessages = () => {
        setImportError('');
        setExportMessage('');
    };

    // --- Category Management Functions ---

    // Handle adding a default category
    const handleAddDefaultCategory = () => {
        clearStatusMessages();
        const defaultCategoryName = "Default";
        if (!categories.includes(defaultCategoryName)) {
            const updatedCategories = [...categories, defaultCategoryName].sort();
            onUpdateCategories(updatedCategories);
            setExportMessage(`"${defaultCategoryName}" category added.`);
        } else {
            setExportMessage(`"${defaultCategoryName}" category already exists.`);
        }
    };

    // Start editing category
    const handleStartEditCategory = (category) => {
        clearStatusMessages();
        setEditingCategory(category);
        setNewCategoryName(category);
    };

    // Save edited category name
    const handleSaveCategory = () => {
        clearStatusMessages();
        const trimmedNewName = newCategoryName.trim();

        // Validate
        if (!trimmedNewName) {
            alert("Category name cannot be empty.");
            return;
        }

        if (trimmedNewName === editingCategory) {
            // No change, just cancel
            setEditingCategory(null);
            setNewCategoryName('');
            return;
        }

        if (categories.includes(trimmedNewName)) {
            alert(`Category "${trimmedNewName}" already exists.`);
            return;
        }

        // Update category list
        const updatedCategories = categories.map(cat =>
            cat === editingCategory ? trimmedNewName : cat
        ).sort();

        onUpdateCategories(updatedCategories);

        // Update components using the old category name
        const updatedComponents = components.map(comp =>
            comp.category === editingCategory ? { ...comp, category: trimmedNewName } : comp
        );

        onUpdateComponents(updatedComponents);

        // Update low stock config if the category existed there
        if (lowStockConfig.hasOwnProperty(editingCategory)) {
            const newConfig = { ...lowStockConfig };
            newConfig[trimmedNewName] = newConfig[editingCategory];
            delete newConfig[editingCategory];
            onUpdateLowStockConfig(newConfig);
        }

        setEditingCategory(null);
        setNewCategoryName('');
        setExportMessage(`Category "${editingCategory}" renamed to "${trimmedNewName}".`);
    };

    // Add these functions after existing category management functions
    const handleRestoreDefaultCategories = () => {
        clearStatusMessages();

        const defaultCategories = [
            "Resistors", "Capacitors", "Inductors", "Diodes", "Transistors",
            "ICs", "Connectors", "Switches", "LEDs", "Sensors", "Modules",
            "Passive", "Active", "Mechanical", "Power", "RF", "Analog", "Digital"
        ];

        if (window.confirm('This will add common electronic component categories to your list. Continue?')) {
            // Merge current categories with defaults to avoid duplicates
            const merged = [...new Set([...categories, ...defaultCategories])].sort();
            onUpdateCategories(merged);
            setExportMessage('Common categories added to your list.');
        }
    };

    const handleDeleteAllCategories = () => {
        clearStatusMessages();

        const componentsCount = components.filter(comp => comp.category && comp.category !== 'Default').length;

        if (componentsCount > 0) {
            const confirmMessage = `This will delete all categories except "Default" and move ${componentsCount} component(s) to "Default" category. Continue?`;
            if (!window.confirm(confirmMessage)) return;
        } else {
            if (!window.confirm('This will delete all categories except "Default". Continue?')) return;
        }

        // Move all components to Default category
        const updatedComponents = components.map(comp => {
            if (comp.category && comp.category !== 'Default') {
                return { ...comp, category: 'Default' };
            }
            return comp;
        });

        onUpdateComponents(updatedComponents);

        // Keep only Default category
        onUpdateCategories(['Default']);

        // Clear low stock config
        onUpdateLowStockConfig({});

        setExportMessage(`All categories deleted except "Default". ${componentsCount} component(s) moved to "Default".`);
    };

    const handleAddNewCategory = () => {
        clearStatusMessages();
        const trimmedCategory = newCategory.trim();

        if (!trimmedCategory) {
            alert("Category name cannot be empty.");
            return;
        }

        if (categories.includes(trimmedCategory)) {
            alert(`Category "${trimmedCategory}" already exists.`);
            return;
        }

        const updatedCategories = [...categories, trimmedCategory].sort();
        onUpdateCategories(updatedCategories);
        setNewCategory('');
        setExportMessage(`Category "${trimmedCategory}" added.`);
    };

    // Cancel category editing
    const handleCancelCategoryEdit = () => {
        setEditingCategory(null);
        setNewCategoryName('');
    };

    // Delete a category
    const handleDeleteCategory = (categoryToDelete) => {
        clearStatusMessages();
        const defaultCategoryName = "Default";

        // Ensure the default category exists if we need to move items to it
        if (!categories.includes(defaultCategoryName)) {
            onUpdateCategories([...categories, defaultCategoryName].sort());
        }

        // Remove the category from the list
        const updatedCategories = categories.filter(cat => cat !== categoryToDelete);
        onUpdateCategories(updatedCategories);

        // Reassign components from the deleted category to the default one
        const updatedComponents = components.map(comp =>
            comp.category === categoryToDelete ? { ...comp, category: defaultCategoryName } : comp
        );

        onUpdateComponents(updatedComponents);

        // Remove the category from low stock config if it exists
        if (lowStockConfig.hasOwnProperty(categoryToDelete)) {
            const newConfig = { ...lowStockConfig };
            delete newConfig[categoryToDelete];
            onUpdateLowStockConfig(newConfig);
        }

        setExportMessage(`Category "${categoryToDelete}" deleted. Components moved to "${defaultCategoryName}".`);
    };

    // --- Low Stock Configuration Functions ---

    // Handle low stock category selection
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

    // Handle adding a low stock threshold
    const handleAddLowStock = () => {
        clearStatusMessages();

        if (!newLowStockCategory || newLowStockThreshold < 1) {
            alert("Please select a category and enter a threshold greater than 0.");
            return;
        }

        const updatedConfig = { ...lowStockConfig, [newLowStockCategory]: newLowStockThreshold };
        onUpdateLowStockConfig(updatedConfig);
        setExportMessage(`Low stock threshold ${lowStockConfig[newLowStockCategory] ? 'updated' : 'added'} for ${newLowStockCategory}.`);
    };

    // Handle removing a low stock threshold
    const handleRemoveLowStock = (category) => {
        clearStatusMessages();

        const updatedConfig = { ...lowStockConfig };
        delete updatedConfig[category];

        onUpdateLowStockConfig(updatedConfig);
        setExportMessage(`Low stock threshold removed for ${category}.`);
    };

    // --- Footprint Management Functions ---

    // Handle adding a footprint
    const handleAddFootprint = (newFootprint) => {
        clearStatusMessages();
        const trimmedFootprint = newFootprint.trim();

        if (!trimmedFootprint) {
            setExportMessage('Footprint name cannot be empty.');
            return;
        }

        if (footprints.includes(trimmedFootprint)) {
            setExportMessage(`Footprint "${trimmedFootprint}" already exists.`);
            return;
        }

        const updatedFootprints = [...footprints, trimmedFootprint].sort();
        onUpdateFootprints(updatedFootprints);
        setExportMessage(`Footprint "${trimmedFootprint}" added.`);
    };

    // Handle editing a footprint
    const handleEditFootprint = (oldFootprint, newFootprint) => {
        clearStatusMessages();
        const trimmedNewFootprint = newFootprint.trim();

        if (!trimmedNewFootprint) {
            setExportMessage('Footprint name cannot be empty.');
            return;
        }

        if (footprints.includes(trimmedNewFootprint)) {
            setExportMessage(`Footprint "${trimmedNewFootprint}" already exists.`);
            return;
        }

        // Update footprint list
        const updatedFootprints = footprints.map(fp =>
            fp === oldFootprint ? trimmedNewFootprint : fp
        ).sort();

        onUpdateFootprints(updatedFootprints);

        // Update components using the old footprint
        const updatedComponents = components.map(comp =>
            comp.footprint === oldFootprint ? { ...comp, footprint: trimmedNewFootprint } : comp
        );

        onUpdateComponents(updatedComponents);
        setExportMessage(`Footprint "${oldFootprint}" renamed to "${trimmedNewFootprint}".`);
    };

    // Handle deleting a footprint
    const handleDeleteFootprint = (footprintToDelete) => {
        clearStatusMessages();

        // Check if any components are using this footprint
        const componentsUsingFootprint = components.filter(comp => comp.footprint === footprintToDelete);

        if (componentsUsingFootprint.length > 0) {
            const confirmMessage = `${componentsUsingFootprint.length} component(s) are using this footprint. Removing it will clear the footprint from these components. Continue?`;
            if (!window.confirm(confirmMessage)) {
                return;
            }

            // Clear footprint from components
            const updatedComponents = components.map(comp =>
                comp.footprint === footprintToDelete ? { ...comp, footprint: '' } : comp
            );

            onUpdateComponents(updatedComponents);
        }

        // Remove the footprint from the list
        const updatedFootprints = footprints.filter(fp => fp !== footprintToDelete);
        onUpdateFootprints(updatedFootprints);
        setExportMessage(`Footprint "${footprintToDelete}" deleted.`);
    };

    // Handle restoring default footprints
    const handleRestoreDefaultFootprints = () => {
        clearStatusMessages();

        // Define the default footprints list
        const defaultFootprints = [
            "0603", "0805", "1206", "1210", "0402", "0201", "2512",
            "SOT-23", "SOT-223", "SOT-89", "SOT-143",
            "SOIC-8", "SOIC-16", "TSSOP-16", "TSSOP-20",
            "DIP-8", "DIP-14", "DIP-16", "DIP-20", "DIP-28",
            "QFP-32", "QFP-44", "QFP-64", "QFP-100",
            "QFN-16", "QFN-20", "QFN-24", "QFN-32",
            "TO-92", "TO-220", "TO-247", "TO-263", "TO-252"
        ];

        if (window.confirm('This will add common electronic component footprints to your list. Continue?')) {
            // Merge current footprints with defaults to avoid duplicates
            const merged = [...new Set([...defaultFootprints, ...footprints])].sort();
            onUpdateFootprints(merged);
            setExportMessage('Common footprints added to your list.');
        }
    };

    const handleDeleteAllFootprints = () => {
        clearStatusMessages();

        // Check which components have footprints
        const componentsUsingFootprints = components.filter(comp => comp.footprint && comp.footprint !== '');

        if (componentsUsingFootprints.length > 0) {
            const confirmMessage = `This will delete all footprints and clear the footprint from ${componentsUsingFootprints.length} component(s). Continue?`;
            if (!window.confirm(confirmMessage)) return;

            // Clear footprints from all components
            const updatedComponents = components.map(comp =>
                comp.footprint ? { ...comp, footprint: '' } : comp
            );
            onUpdateComponents(updatedComponents);
            setExportMessage(`All footprints deleted. Footprints cleared from ${componentsUsingFootprints.length} component(s).`);
        } else {
            if (!window.confirm('This will delete all footprints. Continue?')) return;
            setExportMessage('All footprints deleted.');
        }

        // Clear the footprints array
        onUpdateFootprints([]);
    };

    // --- Storage Management Functions ---
    // Save components to storage
    const handleSaveComponentsLS = async () => {
        clearStatusMessages();
        try {
            const ok = await storage.saveComponents(components);
            if (ok) {
                setExportMessage("✅ Components saved to IndexedDB.");
            } else {
                setImportError("❌ Component save failed.");
            }
        } catch (err) {
            console.error(err);
            setImportError("❌ Component save threw an error.");
        }
    };

    // Save configuration to storage
    const handleSaveConfig = async () => {
        clearStatusMessages();

        // Create config object using local state + props
        const currentConfig = {
            categories,
            viewMode: viewMode,
            lowStockConfig,
            currencySymbol,
            showTotalValue,
            footprints,
            itemsPerPage: itemsPerPage,
            theme
        };

        try {
            const ok = await storage.saveConfig(currentConfig);
            if (ok) {
                setExportMessage("✅ Config saved to LocalStorage.");
            } else {
                setImportError("❌ Config save failed.");
            }
        } catch (err) {
            console.error(err);
            setImportError("❌ Config save threw an error.");
        }
    };

    // Clear all storage
    const handleClearStorage = async () => {
        clearStatusMessages();

        if (window.confirm('Are you sure you want to clear ALL inventory data and settings? This action cannot be undone.')) {
            try {
                const cleared = await storage.clearStorage();

                if (cleared) {
                    // Reset state values using the passed-in update callbacks
                    onUpdateComponents([]);
                    onUpdateCategories([]);
                    onUpdateLowStockConfig({});
                    onUpdateLocations([]);
                    onUpdateDrawers([]);
                    onUpdateCells([]);
                    onUpdateFootprints([]);

                    // Reset local state
                    setViewMode('table');
                    setItemsPerPage('all');

                    setExportMessage('All storage cleared successfully! Application state reset. You may need to refresh the page to see all changes.');
                } else {
                    setImportError('An error occurred while trying to clear storage.');
                }
            } catch (err) {
                console.error("Error clearing storage:", err);
                setImportError(`Error clearing storage: ${err.message}`);
            }
        }
    };

    // --- Backup & Restore Functions (New Unified Approach) ---

    // Create a complete backup of all data
    const handleCreateBackup = () => {
        clearStatusMessages();

        storage.createBackup()
            .then(function (backup) {
                try {
                    const backupJson = JSON.stringify(backup, null, 2);

                    // Create and trigger download
                    const element = document.createElement('a');
                    const file = new Blob([backupJson], { type: 'application/json' });
                    element.href = URL.createObjectURL(file);

                    // Generate a filename with current date
                    const date = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
                    element.download = `electronics_backup_${date}.json`;

                    document.body.appendChild(element);
                    element.click();
                    document.body.removeChild(element);
                    URL.revokeObjectURL(element.href);

                    setExportMessage('Backup created and downloaded successfully!');
                } catch (err) {
                    console.error("Error downloading backup:", err);
                    setImportError(`Error creating backup: ${err.message}`);
                }
            })
            .catch(function (err) {
                console.error("Error creating backup:", err);
                setImportError(`Error creating backup: ${err.message}`);
            });
    };

    // Import a backup file
    const handleFileImport = (event) => {
        clearStatusMessages();

        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const backup = JSON.parse(e.target.result);

                // Confirm import
                if (window.confirm(`This will replace your current data with the backup from ${new Date(backup.metadata.date).toLocaleString()}. Continue?`)) {
                    restoreFromBackup(backup);
                }
            } catch (err) {
                console.error("Error parsing backup file:", err);
                setImportError(`Invalid backup file: ${err.message}`);
            }
        };

        reader.onerror = (e) => {
            console.error("Error reading backup file:", e.target.error);
            setImportError(`Error reading backup file: ${e.target.error}`);
        };

        reader.readAsText(file);

        // Reset file input
        event.target.value = null;
    };

    // Restore from a backup
    const restoreFromBackup = (backup) => {
        storage.restoreBackup(backup)
            .then(function (result) {
                if (result.success) {
                    setImportError(`Backup restored successfully! ${result.message}`);

                    // Reload data after restore
                    Promise.all([
                        storage.loadComponents(),
                        storage.loadLocations(),
                        storage.loadDrawers(),
                        storage.loadCells(),
                        storage.loadCategories(),
                        storage.loadFootprints(),
                        storage.loadLowStockConfig()
                    ]).then(function (results) {
                        onUpdateComponents(results[0]);
                        onUpdateLocations(results[1]);
                        onUpdateDrawers(results[2]);
                        onUpdateCells(results[3]);
                        onUpdateCategories(results[4]);
                        onUpdateFootprints(results[5]);
                        onUpdateLowStockConfig(results[6]);
                    });
                } else {
                    setImportError(`Error restoring backup: ${result.message}`);
                }
            })
            .catch(function (err) {
                console.error("Error restoring backup:", err);
                setImportError(`Error restoring backup: ${err.message}`);
            });
    };
    // --- Render Method ---

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

            // --- Backup & Restore Section (New Unified UI) ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Backup & Restore"),
                React.createElement('div', { className: UI.cards.body },
                    // Messages (Error, Success, Info)
                    importError && React.createElement('div', {
                        className: `p-3 rounded mb-4 text-sm ${importError.includes('success') || importError.includes('finished') ? UI.status.success : UI.status.error}`
                    }, importError),
                    exportMessage && !importError && React.createElement('div', {
                        className: UI.status.info
                    }, exportMessage),

                    // Main actions - just two primary buttons
                    React.createElement('div', { className: "flex flex-col md:flex-row gap-4 mb-6" },
                        // Backup button
                        React.createElement('div', { className: "flex-grow" },
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Backup All Data"),
                            React.createElement('p', { className: "text-sm mb-2" },
                                "Create a complete backup of your inventory, including components, locations, drawers, and all settings."
                            ),
                            React.createElement('button', {
                                onClick: handleCreateBackup,
                                className: UI.buttons.primary + " w-full"
                            }, "Create & Download Backup")
                        ),

                        // Restore button
                        React.createElement('div', { className: "flex-grow" },
                            React.createElement('h4', { className: UI.typography.sectionTitle }, "Restore From Backup"),
                            React.createElement('p', { className: "text-sm mb-2" },
                                "Restore your inventory from a previously created backup file. Will replace all current data!"
                            ),
                            React.createElement('div', { className: "flex flex-col" },
                                React.createElement('input', {
                                    type: "file",
                                    id: "import-backup-file",
                                    accept: ".json",
                                    onChange: handleFileImport,
                                    className: "hidden"
                                }),
                                React.createElement('label', {
                                    htmlFor: "import-backup-file",
                                    className: UI.buttons.success + " w-full text-center cursor-pointer"
                                }, "Select Backup File")
                            )
                        )
                    )
                )
            ), // End Backup & Restore Section

            // --- Category Management Section ---
            React.createElement('div', { className: UI.cards.container },
                React.createElement('h2', { className: `${UI.typography.heading.h2} ${UI.cards.header}` }, "Category Management"),
                React.createElement('div', { className: UI.cards.body },
                    React.createElement('p', { className: `mb-4 ${UI.typography.body}` },
                        `Edit or delete categories. Deleting moves components to "Default".`
                    ),

                    // Add New Category Section
                    React.createElement('div', { className: `mb-6 p-4 ${UI.colors.background.alt} ${UI.utils.rounded}` },
                        React.createElement('h4', { className: UI.typography.sectionTitle }, "Add New Category"),
                        React.createElement('div', { className: "flex gap-3" },
                            React.createElement('input', {
                                type: "text",
                                value: newCategory,
                                onChange: (e) => setNewCategory(e.target.value),
                                className: UI.forms.input + " flex-grow",
                                placeholder: "Enter category name...",
                                onKeyDown: (e) => e.key === 'Enter' && handleAddNewCategory()
                            }),
                            React.createElement('button', {
                                onClick: handleAddNewCategory,
                                className: UI.buttons.primary,
                                disabled: !newCategory.trim()
                            }, "Add")
                        )
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
                                    categories.sort().map(category => {
                                        const componentCount = components.filter(comp => comp.category === category).length;
                                        return React.createElement('tr', { key: category, className: UI.tables.body.row },
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
                                                    React.createElement('span', { className: UI.tables.body.cell }, category)
                                            ),
                                            React.createElement('td', { className: `${UI.tables.body.cell} text-center` },
                                                componentCount
                                            ),
                                            React.createElement('td', { className: UI.tables.body.cellAction },
                                                editingCategory === category ?
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
                                                    React.createElement('div', { className: "flex justify-center space-x-2" },
                                                        React.createElement('button', {
                                                            onClick: () => handleStartEditCategory(category),
                                                            className: UI.buttons.small.primary,
                                                            title: "Edit"
                                                        }, "Edit"),
                                                        React.createElement('button', {
                                                            onClick: () => handleDeleteCategory(category),
                                                            className: UI.buttons.small.danger,
                                                            title: "Delete",
                                                            disabled: category === 'Default'
                                                        }, "Delete")
                                                    )
                                            )
                                        );
                                    })
                            )
                        )
                    ),

                    // Restore Default and Delete All buttons
                    React.createElement('div', { className: "mt-4 flex gap-3" },
                        React.createElement('button', {
                            onClick: handleRestoreDefaultCategories,
                            className: UI.buttons.secondary
                        }, 'Restore Default Categories'),
                        React.createElement('button', {
                            onClick: handleDeleteAllCategories,
                            className: UI.buttons.danger
                        }, 'Delete All Categories')
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
                        onAddFootprint: handleAddFootprint,
                        onEditFootprint: handleEditFootprint,
                        onDeleteFootprint: handleDeleteFootprint,
                        onRestoreDefaults: handleRestoreDefaultFootprints,
                        onDeleteAll: handleDeleteAllFootprints  // NEW: Add this prop
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
                                                            onClick: () => handleRemoveLowStock(category),
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
                    ),
                    // Theme Selector
                    React.createElement('div', { className: "mt-6" },
                        React.createElement('h3', { className: UI.typography.sectionTitle }, "Theme"),
                        React.createElement(window.App.components.ThemeSwitcher, {
                            currentTheme: theme,
                            onThemeChange: onChangeTheme
                        })
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
                            onClick: handleSaveComponentsLS,
                            className: UI.buttons.primary
                        }, "Force Save Components"),
                        React.createElement('button', {
                            onClick: handleSaveConfig,
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
                            React.createElement('li', null, "Create a complete backup at least once per week"),
                            React.createElement('li', null, "Backup after making significant changes"),
                            React.createElement('li', null, "Keep backup files in multiple locations"),
                            React.createElement('li', null, "Test restoring backups occasionally to verify integrity")
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
                                    onClick: handleClearStorage,
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
};

console.log("SettingsView component fully refactored and loaded!");