// js/components/FootprintManager.js

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

    // Handle adding a new footprint
    const handleAddSubmit = (e) => {
        e.preventDefault();
        onAddFootprint(newFootprint);
        setNewFootprint(''); // Clear the input after submission
    };

    // Start editing a footprint
    const handleStartEdit = (footprint) => {
        setEditingFootprint(footprint);
        setEditedFootprintName(footprint);
    };

    // Save the edited footprint
    const handleSaveEdit = () => {
        onEditFootprint(editingFootprint, editedFootprintName);
        setEditingFootprint(null);
        setEditedFootprintName('');
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingFootprint(null);
        setEditedFootprintName('');
    };

    return React.createElement('div', { className: "space-y-4" },
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
                    className: UI.buttons.primary
                }, "Add")
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
                                            onKeyDown: (e) => e.key === 'Enter' && handleSaveEdit()
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
                                                title: "Save"
                                            }, "Save"),
                                            React.createElement('button', {
                                                onClick: handleCancelEdit,
                                                className: UI.buttons.small.secondary,
                                                title: "Cancel"
                                            }, "Cancel")
                                        ) :
                                        // Normal Mode Actions
                                        React.createElement('div', { className: "flex justify-center space-x-2" },
                                            React.createElement('button', {
                                                onClick: () => handleStartEdit(footprint),
                                                className: UI.buttons.small.primary,
                                                title: "Edit"
                                            }, "Edit"),
                                            React.createElement('button', {
                                                onClick: () => onDeleteFootprint(footprint),
                                                className: UI.buttons.small.danger,
                                                title: "Delete"
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
                onClick: onRestoreDefaults,
                className: UI.buttons.secondary
            }, "Restore Default Footprints")
        )
    );
};

console.log("FootprintManager component loaded with theme-aware styling."); // For debugging