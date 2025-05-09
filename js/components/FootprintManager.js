// js/components/FootprintManager.js - Updated for IndexedDB compatibility

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing footprints.
 */
window.App.components.FootprintManager = ({
    // Props
    footprints, // Array: List of footprint strings
    // Callbacks
    onAddFootprint, // Function(newFootprint): Called to add a new footprint
    onEditFootprint, // Function(oldFootprint, newFootprint): Called to rename a footprint
    onDeleteFootprint, // Function(footprint): Called to delete a footprint
    onRestoreDefaults, // Function: Called to restore default footprints
}) => {
    const { UI } = window.App.utils;
    const { useState } = React;

    // Internal state
    const [newFootprint, setNewFootprint] = useState('');
    const [editingFootprint, setEditingFootprint] = useState(null);
    const [editedFootprintName, setEditedFootprintName] = useState('');
    const [loading, setLoading] = useState(false);

    // Handle adding a new footprint
    const handleAddSubmit = (e) => {
        e.preventDefault();
        // Show loading indicator
        setLoading(true);
        
        // Trim the footprint name
        const trimmedFootprint = newFootprint.trim();
        
        // Validate footprint name
        if (!trimmedFootprint) {
            alert("Footprint name cannot be empty.");
            setLoading(false);
            return;
        }
        
        // Check for duplicates
        if (footprints.includes(trimmedFootprint)) {
            alert(`Footprint "${trimmedFootprint}" already exists.`);
            setLoading(false);
            return;
        }
        
        // Add the footprint
        onAddFootprint(trimmedFootprint);
        
        // Clear input and loading state after a short delay
        setTimeout(() => {
            setNewFootprint(''); // Clear the input after submission
            setLoading(false);
        }, 300);
    };

    // Start editing a footprint
    const handleStartEdit = (footprint) => {
        setEditingFootprint(footprint);
        setEditedFootprintName(footprint);
    };

    // Save the edited footprint
    const handleSaveEdit = () => {
        // Show loading indicator
        setLoading(true);
        
        // Trim the footprint name
        const trimmedName = editedFootprintName.trim();
        
        // Validate the new name
        if (!trimmedName) {
            alert("Footprint name cannot be empty.");
            setLoading(false);
            return;
        }
        
        // Check for duplicates, excluding the current footprint
        if (footprints.includes(trimmedName) && trimmedName !== editingFootprint) {
            alert(`Footprint "${trimmedName}" already exists.`);
            setLoading(false);
            return;
        }
        
        // Save the edit
        onEditFootprint(editingFootprint, trimmedName);
        
        // Reset state after a short delay
        setTimeout(() => {
            setEditingFootprint(null);
            setEditedFootprintName('');
            setLoading(false);
        }, 300);
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingFootprint(null);
        setEditedFootprintName('');
    };
    
    // Handle deleting a footprint
    const handleDelete = (footprint) => {
        // Show loading indicator
        setLoading(true);
        
        // Delete the footprint
        onDeleteFootprint(footprint);
        
        // Clear loading state after a short delay
        setTimeout(() => {
            setLoading(false);
        }, 300);
    };
    
    // Handle restoring default footprints
    const handleRestoreDefaults = () => {
        // Show loading indicator
        setLoading(true);
        
        // Restore defaults
        onRestoreDefaults();
        
        // Clear loading state after a short delay
        setTimeout(() => {
            setLoading(false);
        }, 500);
    };

    return React.createElement('div', { className: "space-y-4" },
        // Loading overlay
        loading && React.createElement('div', { 
            className: "fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50" 
        },
            React.createElement('div', { 
                className: "bg-white p-4 rounded-lg shadow-xl" 
            },
                React.createElement('div', { 
                    className: "w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" 
                })
            )
        ),
        
        // Add new footprint form
        React.createElement('div', { className: "mb-4" },
            React.createElement('h4', { className: UI.typography.sectionTitle }, "Add New Footprint"),
            React.createElement('form', { onSubmit: handleAddSubmit, className: "flex gap-2" },
                React.createElement('input', {
                    type: "text",
                    value: newFootprint,
                    onChange: (e) => setNewFootprint(e.target.value),
                    placeholder: "Enter footprint name",
                    className: UI.forms.input
                }),
                React.createElement('button', {
                    type: "submit",
                    className: UI.buttons.primary,
                    disabled: loading
                }, loading ? "Adding..." : "Add")
            )
        ),
        
        // Footprints list
        React.createElement('div', { className: "overflow-x-auto" },
            React.createElement('table', { className: UI.tables.container },
                React.createElement('thead', { className: `${UI.tables.header.row} sticky top-0` },
                    React.createElement('tr', null,
                        React.createElement('th', { className: UI.tables.header.cell }, "Footprint"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Action")
                    )
                ),
                React.createElement('tbody', { 
                    className: `divide-y divide-${UI.getThemeColors().border} bg-${UI.getThemeColors().cardBackground}` 
                },
                    footprints.length === 0 ?
                        React.createElement('tr', null,
                            React.createElement('td', { 
                                colSpan: "2", 
                                className: `py-4 px-4 text-center text-${UI.getThemeColors().textMuted} italic` 
                            }, 
                            "No footprints defined.")
                        ) :
                        footprints.sort().map(footprint =>
                            React.createElement('tr', { key: footprint, className: UI.tables.body.row },
                                // Footprint Name (editable)
                                React.createElement('td', { className: UI.tables.body.cell },
                                    editingFootprint === footprint ?
                                        React.createElement('input', {
                                            type: "text",
                                            value: editedFootprintName,
                                            onChange: (e) => setEditedFootprintName(e.target.value),
                                            className: UI.forms.input,
                                            autoFocus: true,
                                            onKeyDown: (e) => e.key === 'Enter' && handleSaveEdit(),
                                            disabled: loading
                                        }) :
                                        React.createElement('span', { 
                                            className: `text-sm text-${UI.getThemeColors().textSecondary}` 
                                        }, 
                                        footprint)
                                ),
                                // Actions
                                React.createElement('td', { className: UI.tables.body.cellAction },
                                    editingFootprint === footprint ?
                                        // Edit Mode Actions
                                        React.createElement('div', { className: "flex justify-center space-x-2" },
                                            React.createElement('button', {
                                                onClick: handleSaveEdit,
                                                className: UI.buttons.small.success,
                                                title: "Save",
                                                disabled: loading
                                            }, loading ? "Saving..." : "Save"),
                                            React.createElement('button', {
                                                onClick: handleCancelEdit,
                                                className: UI.buttons.small.secondary,
                                                title: "Cancel",
                                                disabled: loading
                                            }, "Cancel")
                                        ) :
                                        // Normal Mode Actions
                                        React.createElement('div', { className: "flex justify-center space-x-2" },
                                            React.createElement('button', {
                                                onClick: () => handleStartEdit(footprint),
                                                className: UI.buttons.small.primary,
                                                title: "Edit",
                                                disabled: loading
                                            }, "Edit"),
                                            React.createElement('button', {
                                                onClick: () => handleDelete(footprint),
                                                className: UI.buttons.small.danger,
                                                title: "Delete",
                                                disabled: loading
                                            }, "Delete")
                                        )
                                )
                            )
                        )
                )
            )
        ),
        
        // Restore defaults button
        React.createElement('div', { className: "mt-4 text-right" },
            React.createElement('button', {
                onClick: handleRestoreDefaults,
                className: UI.buttons.secondary,
                disabled: loading
            }, loading ? "Restoring..." : "Restore Default Footprints")
        )
    );
};

console.log("FootprintManager component loaded with IndexedDB compatibility.");