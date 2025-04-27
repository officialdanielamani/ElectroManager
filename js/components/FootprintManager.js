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
            React.createElement('h4', { className: "font-medium mb-2 text-gray-600" }, "Add New Footprint"),
            React.createElement('form', { onSubmit: handleAddSubmit, className: "flex gap-2" },
                React.createElement('input', {
                    type: "text",
                    value: newFootprint,
                    onChange: (e) => setNewFootprint(e.target.value),
                    placeholder: "Enter footprint name",
                    className: "flex-grow p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                }),
                React.createElement('button', {
                    type: "submit",
                    className: "px-4 py-2 bg-blue-500 text-white rounded shadow hover:bg-blue-600 transition duration-150 ease-in-out"
                }, "Add")
            )
        ),
        
        // Footprints list
        React.createElement('div', { className: "overflow-x-auto" },
            React.createElement('table', { className: "min-w-full divide-y divide-gray-200" },
                React.createElement('thead', { className: "bg-gray-50" },
                    React.createElement('tr', null,
                        React.createElement('th', { className: "py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" }, "Footprint"),
                        React.createElement('th', { className: "py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" }, "Actions")
                    )
                ),
                React.createElement('tbody', { className: "bg-white divide-y divide-gray-200" },
                    footprints.length === 0 ?
                        React.createElement('tr', null,
                            React.createElement('td', { colSpan: "2", className: "py-4 px-4 text-center text-gray-500 italic" }, "No footprints defined.")
                        ) :
                        footprints.sort().map(footprint =>
                            React.createElement('tr', { key: footprint },
                                // Footprint Name (editable)
                                React.createElement('td', { className: "py-2 px-4 whitespace-nowrap" },
                                    editingFootprint === footprint ?
                                        React.createElement('input', {
                                            type: "text",
                                            value: editedFootprintName,
                                            onChange: (e) => setEditedFootprintName(e.target.value),
                                            className: "w-full p-1 border border-blue-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500",
                                            autoFocus: true,
                                            onKeyDown: (e) => e.key === 'Enter' && handleSaveEdit()
                                        }) :
                                        React.createElement('span', { className: "text-sm text-gray-900" }, footprint)
                                ),
                                // Actions
                                React.createElement('td', { className: "py-2 px-4 text-center whitespace-nowrap" },
                                    editingFootprint === footprint ?
                                        // Edit Mode Actions
                                        React.createElement('div', { className: "flex justify-center space-x-2" },
                                            React.createElement('button', {
                                                onClick: handleSaveEdit,
                                                className: "px-2 py-1 bg-green-500 text-white text-xs rounded shadow hover:bg-green-600",
                                                title: "Save"
                                            }, "Save"),
                                            React.createElement('button', {
                                                onClick: handleCancelEdit,
                                                className: "px-2 py-1 bg-gray-300 text-gray-700 text-xs rounded shadow hover:bg-gray-400",
                                                title: "Cancel"
                                            }, "Cancel")
                                        ) :
                                        // Normal Mode Actions
                                        React.createElement('div', { className: "flex justify-center space-x-2" },
                                            React.createElement('button', {
                                                onClick: () => handleStartEdit(footprint),
                                                className: "px-2 py-1 bg-blue-500 text-white text-xs rounded shadow hover:bg-blue-600",
                                                title: "Edit"
                                            }, "Edit"),
                                            React.createElement('button', {
                                                onClick: () => onDeleteFootprint(footprint),
                                                className: "px-2 py-1 bg-red-500 text-white text-xs rounded shadow hover:bg-red-600",
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
                className: "px-4 py-2 bg-gray-500 text-white text-sm rounded shadow hover:bg-gray-600 transition duration-150"
            }, "Restore Default Footprints")
        )
    );
};

console.log("FootprintManager component loaded."); // For debugging