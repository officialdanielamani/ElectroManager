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
    const handleAddSubmit = (e) => {
        e.preventDefault();
        
        // Sanitize inputs
        const trimmedName = window.App.utils.sanitize.value(newDrawerName.trim());
        const trimmedDescription = window.App.utils.sanitize.value(newDrawerDescription.trim());
        const sanitizedLocationId = window.App.utils.sanitize.value(selectedLocationId);
        
        // Sanitize and parse numeric inputs
        const rows = parseInt(window.App.utils.sanitize.value(newDrawerRows), 10) || 3;
        const cols = parseInt(window.App.utils.sanitize.value(newDrawerCols), 10) || 3;
    
        if (!sanitizedLocationId) {
            alert("Please select a location for this drawer.");
            return;
        }
    
        if (!trimmedName) {
            alert("Drawer name cannot be empty.");
            return;
        }
    
        // Check for duplicate drawer names within the same location
        if (drawers.some(drawer => drawer.locationId === sanitizedLocationId &&
            drawer.name.toLowerCase() === trimmedName.toLowerCase()
        )) {
            alert(`Drawer "${trimmedName}" already exists in this location.`);
            return;
        }
    
        // Create sanitized drawer object
        const newDrawer = window.App.utils.sanitize.drawer({
            id: `drawer-${Date.now()}`,
            locationId: sanitizedLocationId,
            name: trimmedName,
            description: trimmedDescription,
            grid: {
                rows: rows,
                cols: cols
            }
        });
    
        onAddDrawer(newDrawer);
    
        // Reset form
        setNewDrawerName('');
        setNewDrawerDescription('');
        setNewDrawerRows(3);
        setNewDrawerCols(3);
    };

    // Start editing a drawer
    const handleStartEdit = (drawer) => {
        // Sanitize drawer data
        const sanitizedDrawer = window.App.utils.sanitize.drawer(drawer);
        
        setEditingDrawerId(sanitizedDrawer.id);
        setEditDrawerName(sanitizedDrawer.name);
        setEditDrawerDescription(sanitizedDrawer.description || '');
        setEditDrawerRows(sanitizedDrawer.grid?.rows || 3);
        setEditDrawerCols(sanitizedDrawer.grid?.cols || 3);
    };

    // Save the edited drawer
    const handleSaveEdit = () => {
        // Sanitize inputs
        const trimmedName = window.App.utils.sanitize.value(editDrawerName.trim());
        const trimmedDescription = window.App.utils.sanitize.value(editDrawerDescription.trim());
        
        // Sanitize and parse numeric inputs
        const rows = parseInt(window.App.utils.sanitize.value(editDrawerRows), 10) || 3;
        const cols = parseInt(window.App.utils.sanitize.value(editDrawerCols), 10) || 3;
        
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
    
        // Create sanitized updated drawer object
        const updatedDrawer = window.App.utils.sanitize.drawer({
            ...currentDrawer,
            name: trimmedName,
            description: trimmedDescription,
            grid: {
                rows: rows,
                cols: cols
            }
        });
    
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
        comp.storage && comp.storage.drawerId === drawerId
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
                className: UI.forms.label
            }, "Filter by Location"),
            React.createElement('select', {
                id: "location-select",
                className: UI.forms.select,
                value: selectedLocationId,
                onChange: (e) => setSelectedLocationId(e.target.value)
            },
                React.createElement('option', { value: "" }, "-- All Locations --"),
                locations.map(location => React.createElement('option', { key: location.id, value: location.id }, location.name))
            )
        ),

        // Add new drawer form 
        React.createElement('div', { className: UI.cards.container + " mb-6" },
            // Clickable header with toggle arrow
            React.createElement('div', {
                className: `flex justify-between items-center cursor-pointer ${UI.cards.header}`,
                onClick: () => {
                    console.log("Toggle form visibility", !showAddDrawerForm);
                    setShowAddDrawerForm(!showAddDrawerForm);
                }
            },
                React.createElement('h4', { className: `font-medium text-${UI.getThemeColors().textSecondary}` }, "Add New Drawer"),
                React.createElement('span', { className: `text-${UI.getThemeColors().textMuted}` },
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
            showAddDrawerForm && React.createElement('div', { className: UI.cards.body },
                React.createElement('form', { onSubmit: handleAddSubmit, className: "space-y-3" },
                    // Location selection for new drawer
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-location",
                            className: UI.forms.label
                        }, "Location"),
                        React.createElement('select', {
                            id: "new-drawer-location",
                            value: selectedLocationId,
                            onChange: (e) => setSelectedLocationId(e.target.value),
                            className: UI.forms.select,
                            required: true
                        },
                            React.createElement('option', { value: "" }, "-- Select Location --"),
                            locations.map(location =>
                                React.createElement('option', { key: location.id, value: location.id }, location.name)
                            )
                        )
                    ),
                    // Name input
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-name",
                            className: UI.forms.label
                        }, "Drawer Name"),
                        React.createElement('input', {
                            id: "new-drawer-name",
                            type: "text",
                            value: newDrawerName,
                            onChange: (e) => setNewDrawerName(e.target.value),
                            placeholder: "e.g., Drawer A2",
                            className: UI.forms.input,
                            required: true
                        })
                    ),
                    // Description input
                    React.createElement('div', null,
                        React.createElement('label', {
                            htmlFor: "new-drawer-description",
                            className: UI.forms.label
                        }, "Description (Optional)"),
                        React.createElement('input', {
                            id: "new-drawer-description",
                            type: "text",
                            value: newDrawerDescription,
                            onChange: (e) => setNewDrawerDescription(e.target.value),
                            placeholder: "e.g., Top Left",
                            className: UI.forms.input
                        })
                    ),
                    // Grid size inputs
                    React.createElement('div', { className: "grid grid-cols-2 gap-4" },
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "new-drawer-rows",
                                className: UI.forms.label
                            }, "Number of Rows"),
                            React.createElement('input', {
                                id: "new-drawer-rows",
                                type: "number",
                                min: "1",
                                max: "16",
                                value: newDrawerRows,
                                onChange: (e) => setNewDrawerRows(e.target.value),
                                className: UI.forms.input
                            })
                        ),
                        React.createElement('div', null,
                            React.createElement('label', {
                                htmlFor: "new-drawer-cols",
                                className: UI.forms.label
                            }, "Number of Columns"),
                            React.createElement('input', {
                                id: "new-drawer-cols",
                                type: "number",
                                min: "1",
                                max: "16",
                                value: newDrawerCols,
                                onChange: (e) => setNewDrawerCols(e.target.value),
                                className: UI.forms.input
                            })
                        )
                    ),
                    // Submit button
                    React.createElement('div', null,
                        React.createElement('button', {
                            type: "submit",
                            className: UI.buttons.primary,
                            disabled: !selectedLocationId
                        }, "Add Drawer")
                    )
                )
            )
        ),

        // Drawers list
        React.createElement('div', { className: UI.cards.container },
            React.createElement('h4', { className: `${UI.typography.sectionTitle} ${UI.cards.header}` },
                selectedLocationId
                    ? `Drawers in ${getLocationName(selectedLocationId)}`
                    : "All Drawers"
            ),

            React.createElement('div', { className: UI.cards.body },
                filteredDrawers.length === 0 ?
                    React.createElement('p', { className: `text-${UI.getThemeColors().textMuted} italic` },
                        selectedLocationId
                            ? "No drawers defined for this location yet."
                            : "No drawers defined yet."
                    ) :

                    // Drawers accordion list
                    React.createElement('div', { className: `divide-y divide-${UI.getThemeColors().border}` },
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
                                            className: `mr-2 text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().textSecondary}`,
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
                                                React.createElement('span', { className: `font-medium text-${UI.getThemeColors().textPrimary}` }, drawer.name),
                                                drawer.description && React.createElement('span', { className: `ml-2 text-sm text-${UI.getThemeColors().textMuted}` }, `(${drawer.description})`),
                                                !selectedLocationId && React.createElement('span', { className: `ml-2 text-xs bg-${UI.getThemeColors().background} px-2 py-0.5 rounded` }, getLocationName(drawer.locationId))
                                            ) :
                                            // Edit form inline
                                            React.createElement('div', { className: "flex-1 space-y-2" },
                                                React.createElement('div', { className: "flex space-x-2" },
                                                    React.createElement('input', {
                                                        type: "text",
                                                        value: editDrawerName,
                                                        onChange: (e) => setEditDrawerName(e.target.value),
                                                        className: UI.forms.input + " max-w-xs",
                                                        placeholder: "Drawer name"
                                                    }),
                                                    React.createElement('input', {
                                                        type: "text",
                                                        value: editDrawerDescription,
                                                        onChange: (e) => setEditDrawerDescription(e.target.value),
                                                        className: UI.forms.input + " w-full",
                                                        placeholder: "Description (optional)"
                                                    })
                                                ),
                                                React.createElement('div', { className: "flex space-x-2" },
                                                    React.createElement('div', { className: "flex items-center" },
                                                        React.createElement('span', { className: `text-xs mr-1 text-${UI.getThemeColors().textSecondary}` }, "Rows:"),
                                                        React.createElement('input', {
                                                            type: "number",
                                                            min: "1",
                                                            max: "16",
                                                            value: editDrawerRows,
                                                            onChange: (e) => setEditDrawerRows(e.target.value),
                                                            className: UI.forms.input + " w-16"
                                                        })
                                                    ),
                                                    React.createElement('div', { className: "flex items-center" },
                                                        React.createElement('span', { className: `text-xs mr-1 text-${UI.getThemeColors().textSecondary}` }, "Columns:"),
                                                        React.createElement('input', {
                                                            type: "number",
                                                            min: "1",
                                                            max: "16",
                                                            value: editDrawerCols,
                                                            onChange: (e) => setEditDrawerCols(e.target.value),
                                                            className: UI.forms.input + " w-16"
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
                                                    className: UI.buttons.small.success,
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
                                                    className: UI.buttons.small.success,
                                                    title: "Save Changes"
                                                }, "Save"),
                                                React.createElement('button', {
                                                    onClick: handleCancelEdit,
                                                    className: UI.buttons.small.secondary,
                                                    title: "Cancel Editing"
                                                }, "Cancel")
                                            )
                                    )
                                ),

                                // Components in this drawer (collapsible)
                                isExpanded && !isEditing && React.createElement('div', {
                                    className: `mt-2 ml-7 pl-2 border-l-2 border-${UI.getThemeColors().borderLight}`
                                },
                                    React.createElement('h5', { className: `text-sm font-medium text-${UI.getThemeColors().textSecondary} mb-1` },
                                        `${drawer.grid?.rows || 3}×${drawer.grid?.cols || 3} grid with ${drawerComponents.length} component(s)`
                                    ),
                                    React.createElement('div', { className: "flex space-x-2 mt-2" },
                                        React.createElement('button', {
                                            onClick: () => onViewDrawer(drawer.id),
                                            className: UI.buttons.small.info,
                                            title: "View Drawer Contents"
                                        }, "View Drawer Contents")
                                    ),
                                    drawerComponents.length > 0 && React.createElement('div', { className: "mt-2" },
                                        React.createElement('h6', { className: `text-xs font-medium text-${UI.getThemeColors().textSecondary} mb-1` }, "Components in this drawer:"),
                                        React.createElement('ul', { className: "space-y-1 max-h-40 overflow-y-auto" },
                                            drawerComponents.slice(0, 5).map(comp =>
                                                React.createElement('li', { key: comp.id, className: "flex justify-between items-center" },
                                                    React.createElement('span', { className: `text-sm text-${UI.getThemeColors().textSecondary}` }, comp.name),
                                                    React.createElement('button', {
                                                        onClick: () => onEditComponent(comp),
                                                        className: `text-xs ${UI.colors.info.text} hover:${UI.colors.info.hover}`,
                                                        title: "Edit Component"
                                                    }, "Edit")
                                                )
                                            ),
                                            drawerComponents.length > 5 && React.createElement('li', { className: `text-xs text-${UI.getThemeColors().textMuted} italic` },
                                                `... and ${drawerComponents.length - 5} more component(s)`
                                            )
                                        )
                                    )
                                )
                            );
                        })
                    )
            )
        )
    );
};

console.log("DrawerManager loaded"); // For debugging