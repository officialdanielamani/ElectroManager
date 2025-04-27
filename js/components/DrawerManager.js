// js/components/DrawerManager.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing drawers within locations.
 */
window.App.components.DrawerManager = ({
    // Props
    locations, // Array: List of location objects
    drawers, // Array: List of drawer objects
    components, // Array: All component objects
    // Callbacks
    onAddDrawer, // Function(newDrawer): Called to add a new drawer
    onEditDrawer, // Function(drawerId, updatedDrawer): Called to edit a drawer
    onDeleteDrawer, // Function(drawerId): Called to delete a drawer
    onViewDrawer, // Function(drawerId): Called to view a drawer's contents
    onEditComponent, // Function: Pass-through to edit component
}) => {
    const { useState } = React;
    const { UI } = window.App.utils;

    // Internal state
    const [selectedLocationId, setSelectedLocationId] = useState('');
    const [newDrawerName, setNewDrawerName] = useState('');
    const [newDrawerDescription, setNewDrawerDescription] = useState('');
    const [newDrawerRows, setNewDrawerRows] = useState(3);
    const [newDrawerCols, setNewDrawerCols] = useState(3);
    const [editingDrawerId, setEditingDrawerId] = useState(null);
    const [editDrawerName, setEditDrawerName] = useState('');
    const [editDrawerDescription, setEditDrawerDescription] = useState('');
    const [editDrawerRows, setEditDrawerRows] = useState(3);
    const [editDrawerCols, setEditDrawerCols] = useState(3);
    const [expandedDrawers, setExpandedDrawers] = useState({});
    const [showAddDrawerForm, setShowAddDrawerForm] = useState(false);

    // Handle adding a new drawer
    function handleAddSubmit(e) {
        e.preventDefault();
        const trimmedName = newDrawerName.trim();
        const trimmedDescription = newDrawerDescription.trim();

        if (!selectedLocationId) {
            alert("Please select a location for this drawer.");
            return;
        }

        if (!trimmedName) {
            alert("Drawer name cannot be empty.");
            return;
        }

        // Check for duplicate drawer names within the same location
        if (drawers.some(drawer => drawer.locationId === selectedLocationId &&
            drawer.name.toLowerCase() === trimmedName.toLowerCase()
        )) {
            alert(`Drawer "${trimmedName}" already exists in this location.`);
            return;
        }

        // Fix: Use parseInt with base 10 instead of base 16
        const newDrawer = {
            id: `drawer-${Date.now()}`,
            locationId: selectedLocationId,
            name: trimmedName,
            description: trimmedDescription,
            grid: {
                rows: parseInt(newDrawerRows, 10) || 3,
                cols: parseInt(newDrawerCols, 10) || 3
            }
        };

        onAddDrawer(newDrawer);

        // Reset form
        setNewDrawerName('');
        setNewDrawerDescription('');
        setNewDrawerRows(3);
        setNewDrawerCols(3);
    }

    // Start editing a drawer
    const handleStartEdit = (drawer) => {
        setEditingDrawerId(drawer.id);
        setEditDrawerName(drawer.name);
        setEditDrawerDescription(drawer.description || '');
        setEditDrawerRows(drawer.grid?.rows || 3);
        setEditDrawerCols(drawer.grid?.cols || 3);
    };

    // Save the edited drawer
    const handleSaveEdit = () => {
        const trimmedName = editDrawerName.trim();
        const trimmedDescription = editDrawerDescription.trim();

        if (!trimmedName) {
            alert("Drawer name cannot be empty.");
            return;
        }

        // Get the current drawer to check location
        const currentDrawer = drawers.find(d => d.id === editingDrawerId);
        if (!currentDrawer) return;

        // Check for duplicate names in the same location, excluding the current drawer
        if (drawers.some(drawer =>
            drawer.id !== editingDrawerId &&
            drawer.locationId === currentDrawer.locationId &&
            drawer.name.toLowerCase() === trimmedName.toLowerCase()
        )) {
            alert(`Drawer "${trimmedName}" already exists in this location.`);
            return;
        }

        // Fix: Use parseInt with base 10 instead of base 16
        const updatedDrawer = {
            ...currentDrawer,
            name: trimmedName,
            description: trimmedDescription,
            grid: {
                rows: parseInt(editDrawerRows, 10) || 3,
                cols: parseInt(editDrawerCols, 10) || 3
            }
        };

        onEditDrawer(editingDrawerId, updatedDrawer);
        setEditingDrawerId(null);
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingDrawerId(null);
    };

    // Toggle expanded state for a drawer
    const toggleDrawerExpanded = (drawerId) => {
        setExpandedDrawers(prev => ({
            ...prev,
            [drawerId]: !prev[drawerId]
        }));
    };

    // Get components for a specific drawer (regardless of cell)
    const getComponentsForDrawer = (drawerId) => {
        return components.filter(comp =>
            comp.storageInfo &&
            comp.storageInfo.drawerId === drawerId
        );
    };

    // Filter drawers by location
    const filteredDrawers = selectedLocationId
        ? drawers.filter(drawer => drawer.locationId === selectedLocationId)
        : drawers;

    // Get location name by ID
    const getLocationName = (locationId) => {
        const location = locations.find(loc => loc.id === locationId);
        return location ? location.name : 'Unknown Location';
    };

    return React.createElement('div', { className: "space-y-6" },
        // Location selection dropdown 
        React.createElement('div', { className: "mb-4" },
            React.createElement('label', {
                htmlFor: "location-select",
                className: "block mb-1 text-sm font-medium text-gray-700"
            }, "Filter by Location"),
            React.createElement('select', {
                id: "location-select",
                value: selectedLocationId,
                onChange: (e) => setSelectedLocationId(e.target.value),
                className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
            },
                React.createElement('option', { value: "" }, "-- All Locations --"),
                locations.map(location =>
                    React.createElement('option', { key: location.id, value: location.id }, location.name)
                )
            )
        ),

        // Then replace the entire "Add new drawer form" section with this
        React.createElement('div', { className: "mb-6 bg-white p-4 rounded-lg shadow border border-gray-200" },
            // Clickable header with toggle arrow
            React.createElement('div', {
                className: "flex justify-between items-center cursor-pointer",
                onClick: () => {
                    console.log("Toggle form visibility", !showAddDrawerForm);
                    setShowAddDrawerForm(!showAddDrawerForm);
                }
            },
                React.createElement('h4', { className: "font-medium text-gray-700" }, "Add New Drawer"),
                React.createElement('span', { className: "text-gray-500" },
                    React.createElement('svg', {
                        xmlns: "http://www.w3.org/2000/svg",
                        className: `h-5 w-5 transition-transform ${showAddDrawerForm ? 'transform rotate-180' : ''}`,
                        fill: "none",
                        viewBox: "0 0 24 24",
                        stroke: "currentColor"
                    },
                        React.createElement('path', {
                            strokeLinecap: "round",
                            strokeLinejoin: "round",
                            strokeWidth: 2,
                            d: showAddDrawerForm ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"
                        })
                    )
                )
            ),

            // Form (conditionally rendered based on state)
            showAddDrawerForm && React.createElement('div', { className: "mt-3" },
                React.createElement('form', { onSubmit: handleAddSubmit, className: "space-y-3" },
                    // Location selection for new drawer
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-location",
                            className: "block mb-1 text-sm font-medium text-gray-700"
                        }, "Location"),
                        React.createElement('select', {
                            id: "new-drawer-location",
                            value: selectedLocationId,
                            onChange: (e) => setSelectedLocationId(e.target.value),
                            className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500",
                            required: true
                        },
                            React.createElement('option', { value: "" }, "-- Select Location --"),
                            locations.map(location =>
                                React.createElement('option', { key: location.id, value: location.id }, location.name)
                            )
                        )
                    ),
                    // Rest of the form elements...
                    // (Include the rest of your form here)
                    // Name input
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-name",
                            className: "block mb-1 text-sm font-medium text-gray-700"
                        }, "Drawer Name"),
                        React.createElement('input', {
                            id: "new-drawer-name",
                            type: "text",
                            value: newDrawerName,
                            onChange: (e) => setNewDrawerName(e.target.value),
                            placeholder: "e.g., Drawer A2",
                            className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500",
                            required: true
                        })
                    ),
                    // Description input
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-description",
                            className: "block mb-1 text-sm font-medium text-gray-700"
                        }, "Description (Optional)"),
                        React.createElement('input', {
                            id: "new-drawer-description",
                            type: "text",
                            value: newDrawerDescription,
                            onChange: (e) => setNewDrawerDescription(e.target.value),
                            placeholder: "e.g., Top Left",
                            className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        })
                    ),
                    // Grid size inputs
                    React.createElement('div', { className: "grid grid-cols-2 gap-4" },
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "new-drawer-rows",
                                className: "block mb-1 text-sm font-medium text-gray-700"
                            }, "Number of Rows"),
                            React.createElement('input', {
                                id: "new-drawer-rows",
                                type: "number",
                                min: "1",
                                max: "16",
                                value: newDrawerRows,
                                onChange: (e) => setNewDrawerRows(e.target.value),
                                className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                            })
                        ),
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "new-drawer-cols",
                                className: "block mb-1 text-sm font-medium text-gray-700"
                            }, "Number of Columns"),
                            React.createElement('input', {
                                id: "new-drawer-cols",
                                type: "number",
                                min: "1",
                                max: "16",
                                value: newDrawerCols,
                                onChange: (e) => setNewDrawerCols(e.target.value),
                                className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                            })
                        )
                    ),
                    // Submit button
                    React.createElement('div', null,
                        React.createElement('button', {
                            type: "submit",
                            className: "px-4 py-2 bg-blue-500 text-white rounded shadow hover:bg-blue-600 transition duration-150 ease-in-out",
                            disabled: !selectedLocationId
                        }, "Add Drawer")
                    )
                )
            )
        ),

        // Drawers list
        React.createElement('div', { className: "bg-white p-4 rounded-lg shadow border border-gray-200" },
            React.createElement('h4', { className: UI.typography.sectionTitle },
                selectedLocationId
                    ? `Drawers in ${getLocationName(selectedLocationId)}`
                    : "All Drawers"
            ),

            filteredDrawers.length === 0 ?
                React.createElement('p', { className: "text-gray-500 italic" },
                    selectedLocationId
                        ? "No drawers defined for this location yet."
                        : "No drawers defined yet."
                ) :

                // Drawers accordion list
                React.createElement('div', { className: "divide-y divide-gray-200" },
                    filteredDrawers.map(drawer => {
                        const isEditing = editingDrawerId === drawer.id;
                        const isExpanded = expandedDrawers[drawer.id];
                        const drawerComponents = getComponentsForDrawer(drawer.id);

                        return React.createElement('div', {
                            key: drawer.id,
                            className: "py-2"
                        },
                            // Drawer header (name, description, actions)
                            React.createElement('div', { className: "flex items-center justify-between" },
                                // Expand/collapse button and name
                                React.createElement('div', {
                                    className: "flex items-center cursor-pointer",
                                    onClick: () => !isEditing && toggleDrawerExpanded(drawer.id)
                                },
                                    React.createElement('button', {
                                        className: "mr-2 text-gray-500 hover:text-gray-700",
                                        title: isExpanded ? "Collapse" : "Expand"
                                    },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: `h-5 w-5 transition-transform ${isExpanded ? 'transform rotate-90' : ''}`,
                                            fill: "none",
                                            viewBox: "0 0 24 24",
                                            stroke: "currentColor"
                                        },
                                            React.createElement('path', {
                                                strokeLinecap: "round",
                                                strokeLinejoin: "round",
                                                strokeWidth: 2,
                                                d: "M9 5l7 7-7 7"
                                            })
                                        )
                                    ),
                                    !isEditing ?
                                        React.createElement('div', null,
                                            React.createElement('span', { className: "font-medium text-gray-800" }, drawer.name),
                                            drawer.description && React.createElement('span', { className: "ml-2 text-sm text-gray-500" }, `(${drawer.description})`),
                                            !selectedLocationId && React.createElement('span', { className: "ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded" }, getLocationName(drawer.locationId))
                                        ) :
                                        // Edit form inline
                                        React.createElement('div', { className: "flex-1 space-y-2" },
                                            React.createElement('div', { className: "flex space-x-2" },
                                                React.createElement('input', {
                                                    type: "text",
                                                    value: editDrawerName,
                                                    onChange: (e) => setEditDrawerName(e.target.value),
                                                    className: "p-1 border border-gray-300 rounded text-sm w-full max-w-xs",
                                                    placeholder: "Drawer name"
                                                }),
                                                React.createElement('input', {
                                                    type: "text",
                                                    value: editDrawerDescription,
                                                    onChange: (e) => setEditDrawerDescription(e.target.value),
                                                    className: "p-1 border border-gray-300 rounded text-sm w-full",
                                                    placeholder: "Description (optional)"
                                                })
                                            ),
                                            React.createElement('div', { className: "flex space-x-2" },
                                                React.createElement('div', { className: "flex items-center" },
                                                    React.createElement('span', { className: "text-xs mr-1" }, "Rows:"),
                                                    React.createElement('input', {
                                                        type: "number",
                                                        min: "1",
                                                        max: "16",
                                                        value: editDrawerRows,
                                                        onChange: (e) => setEditDrawerRows(e.target.value),
                                                        className: "p-1 border border-gray-300 rounded text-sm w-16"
                                                    })
                                                ),
                                                React.createElement('div', { className: "flex items-center" },
                                                    React.createElement('span', { className: "text-xs mr-1" }, "Columns:"),
                                                    React.createElement('input', {
                                                        type: "number",
                                                        min: "1",
                                                        max: "16",
                                                        value: editDrawerCols,
                                                        onChange: (e) => setEditDrawerCols(e.target.value),
                                                        className: "p-1 border border-gray-300 rounded text-sm w-16"
                                                    })
                                                )
                                            )
                                        )
                                ),

                                // Action buttons
                                React.createElement('div', { className: "flex space-x-2" },
                                    !isEditing ?
                                        React.createElement(React.Fragment, null,
                                            React.createElement('button', {
                                                onClick: () => onViewDrawer(drawer.id),
                                                className: "px-2 py-1 bg-green-500 text-white text-xs rounded shadow hover:bg-green-600",
                                                title: "View Drawer Contents"
                                            }, "View"),
                                            React.createElement('button', {
                                                onClick: () => handleStartEdit(drawer),
                                                className: UI.buttons.small.primary,
                                                title: "Edit Drawer"
                                            }, "Edit"),
                                            React.createElement('button', {
                                                onClick: () => onDeleteDrawer(drawer.id),
                                                className: UI.buttons.small.danger,
                                                title: "Delete Drawer"
                                            }, "Delete")
                                        ) :
                                        React.createElement(React.Fragment, null,
                                            React.createElement('button', {
                                                onClick: handleSaveEdit,
                                                className: "px-2 py-1 bg-green-500 text-white text-xs rounded shadow hover:bg-green-600",
                                                title: "Save Changes"
                                            }, "Save"),
                                            React.createElement('button', {
                                                onClick: handleCancelEdit,
                                                className: "px-2 py-1 bg-gray-300 text-gray-700 text-xs rounded shadow hover:bg-gray-400",
                                                title: "Cancel Editing"
                                            }, "Cancel")
                                        )
                                )
                            ),

                            // Components in this drawer (collapsible)
                            isExpanded && !isEditing && React.createElement('div', {
                                className: "mt-2 ml-7 pl-2 border-l-2 border-gray-200"
                            },
                                React.createElement('h5', { className: "text-sm font-medium text-gray-700 mb-1" },
                                    `${drawer.grid?.rows || 3}×${drawer.grid?.cols || 3} grid with ${drawerComponents.length} component(s)`
                                ),
                                React.createElement('div', { className: "flex space-x-2 mt-2" },
                                    React.createElement('button', {
                                        onClick: () => onViewDrawer(drawer.id),
                                        className: "px-3 py-1 bg-indigo-500 text-white text-xs rounded shadow hover:bg-indigo-600",
                                        title: "View Drawer Contents"
                                    }, "View Drawer Contents")
                                ),
                                drawerComponents.length > 0 && React.createElement('div', { className: "mt-2" },
                                    React.createElement('h6', { className: "text-xs font-medium text-gray-600 mb-1" }, "Components in this drawer:"),
                                    React.createElement('ul', { className: "space-y-1 max-h-40 overflow-y-auto" },
                                        drawerComponents.slice(0, 5).map(comp =>
                                            React.createElement('li', { key: comp.id, className: "flex justify-between items-center" },
                                                React.createElement('span', { className: "text-sm" }, comp.name),
                                                React.createElement('button', {
                                                    onClick: () => onEditComponent(comp),
                                                    className: "text-xs text-blue-500 hover:text-blue-700",
                                                    title: "Edit Component"
                                                }, "Edit")
                                            )
                                        ),
                                        drawerComponents.length > 5 && React.createElement('li', { className: "text-xs text-gray-500 italic" },
                                            `... and ${drawerComponents.length - 5} more component(s)`
                                        )
                                    )
                                )
                            )
                        );
                    })
                )
        )
    );
};

console.log("DrawerManager component loaded."); // For debugging