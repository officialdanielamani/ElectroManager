// js/components/FootprintManager.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing component footprints
 */
window.App.components.FootprintManager = ({
    footprints = [], // Array: List of footprint strings
    onAddFootprint, // Function(footprint): Add new footprint
    onEditFootprint, // Function(oldFootprint, newFootprint): Edit existing footprint
    onDeleteFootprint, // Function(footprint): Delete footprint
    onRestoreDefaults, // Function(): Restore default footprints
    onDeleteAll // Function(): Delete all footprints (NEW)
}) => {
    const { UI } = window.App.utils;
    const { useState } = React;

    // State for new footprint input
    const [newFootprint, setNewFootprint] = useState('');
    
    // State for editing
    const [editingFootprint, setEditingFootprint] = useState(null);
    const [editFootprintName, setEditFootprintName] = useState('');

    // Handle adding new footprint
    const handleAddFootprint = () => {
        const trimmed = newFootprint.trim();
        if (trimmed && onAddFootprint) {
            onAddFootprint(trimmed);
            setNewFootprint('');
        }
    };

    // Start editing a footprint
    const handleStartEdit = (footprint) => {
        setEditingFootprint(footprint);
        setEditFootprintName(footprint);
    };

    // Save edited footprint
    const handleSaveEdit = () => {
        const trimmed = editFootprintName.trim();
        if (trimmed && trimmed !== editingFootprint && onEditFootprint) {
            onEditFootprint(editingFootprint, trimmed);
        }
        setEditingFootprint(null);
        setEditFootprintName('');
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingFootprint(null);
        setEditFootprintName('');
    };

    return (
        React.createElement('div', { className: "space-y-6" },
            // Add New Footprint Section
            React.createElement('div', { className: `p-4 ${UI.colors.background.alt} ${UI.utils.rounded}` },
                React.createElement('h4', { className: UI.typography.sectionTitle }, "Add New Footprint"),
                React.createElement('div', { className: "flex gap-3" },
                    React.createElement('input', {
                        type: "text",
                        value: newFootprint,
                        onChange: (e) => setNewFootprint(e.target.value),
                        className: UI.forms.input + " flex-grow",
                        placeholder: "Enter footprint name...",
                        onKeyDown: (e) => e.key === 'Enter' && handleAddFootprint()
                    }),
                    React.createElement('button', {
                        onClick: handleAddFootprint,
                        className: UI.buttons.primary,
                        disabled: !newFootprint.trim()
                    }, "Add")
                )
            ),

            // Footprints Table
            React.createElement('div', { className: "overflow-x-auto" },
                React.createElement('table', { className: UI.tables.container },
                    React.createElement('thead', { className: UI.tables.header.row },
                        React.createElement('tr', null,
                            React.createElement('th', { className: UI.tables.header.cell }, "Footprint Name"),
                            React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                        )
                    ),
                    React.createElement('tbody', { className: "bg-white divide-y divide-gray-200" },
                        footprints.length === 0 ?
                            React.createElement('tr', null,
                                React.createElement('td', { colSpan: "2", className: "py-4 px-4 text-center text-gray-500 italic" }, 
                                    "No footprints defined."
                                )
                            ) :
                            footprints.sort().map(footprint => 
                                React.createElement('tr', { key: footprint, className: UI.tables.body.row },
                                    // Footprint Name (editable)
                                    React.createElement('td', { className: UI.tables.body.cell },
                                        editingFootprint === footprint ?
                                            React.createElement('input', {
                                                type: "text",
                                                value: editFootprintName,
                                                onChange: (e) => setEditFootprintName(e.target.value),
                                                className: UI.forms.input,
                                                autoFocus: true,
                                                onKeyDown: (e) => e.key === 'Enter' && handleSaveEdit()
                                            }) :
                                            React.createElement('span', null, footprint)
                                    ),
                                    // Actions
                                    React.createElement('td', { className: UI.tables.body.cellAction },
                                        editingFootprint === footprint ?
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
                                            React.createElement('div', { className: "flex justify-center space-x-2" },
                                                React.createElement('button', {
                                                    onClick: () => handleStartEdit(footprint),
                                                    className: UI.buttons.small.primary,
                                                    title: "Edit"
                                                }, "Edit"),
                                                React.createElement('button', {
                                                    onClick: () => onDeleteFootprint && onDeleteFootprint(footprint),
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

            // Restore Default and Delete All buttons
            React.createElement('div', { className: "flex gap-3" },
                React.createElement('button', {
                    onClick: onRestoreDefaults,
                    className: UI.buttons.secondary,
                    disabled: !onRestoreDefaults
                }, 'Restore Default Footprints'),
                React.createElement('button', {
                    onClick: onDeleteAll,
                    className: UI.buttons.danger,
                    disabled: !onDeleteAll
                }, 'Delete All Footprints')
            )
        )
    );
};

console.log("FootprintManager component updated with consistent UI!");