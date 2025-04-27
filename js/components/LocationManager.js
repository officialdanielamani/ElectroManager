// js/components/LocationManager.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing locations.
 */
window.App.components.LocationManager = ({
    // Props
    locations, // Array: List of location objects
    components, // Array: All component objects
    drawers, // Array: List of drawer objects
    // Callbacks
    onAddLocation, // Function(newLocation): Called to add a new location
    onEditLocation, // Function(oldLocationId, updatedLocation): Called to edit a location
    onDeleteLocation, // Function(locationId): Called to delete a location
    onEditComponent, // Function: Pass-through to edit component
    onNavigateToDrawer, // Function: Navigate to drawer view
}) => {
    const { useState } = React;
    const { UI } = window.App.utils;

    // Internal state
    const [newLocationName, setNewLocationName] = useState('');
    const [newLocationDescription, setNewLocationDescription] = useState('');
    const [editingLocationId, setEditingLocationId] = useState(null);
    const [editLocationName, setEditLocationName] = useState('');
    const [editLocationDescription, setEditLocationDescription] = useState('');
    const [expandedLocations, setExpandedLocations] = useState({});
    const [showAddLocationForm, setShowAddLocationForm] = useState(false);

    // Handle adding a new location
    const handleAddSubmit = (e) => {
        e.preventDefault();
        const trimmedName = newLocationName.trim();
        const trimmedDescription = newLocationDescription.trim();
        
        if (!trimmedName) {
            alert("Location name cannot be empty.");
            return;
        }
        
        // Check for duplicate location names
        if (locations.some(loc => loc.name.toLowerCase() === trimmedName.toLowerCase())) {
            alert(`Location "${trimmedName}" already exists.`);
            return;
        }
        
        const newLocation = {
            id: `loc-${Date.now()}`,
            name: trimmedName,
            description: trimmedDescription
        };
        
        onAddLocation(newLocation);
        setNewLocationName('');
        setNewLocationDescription('');
    };

    // Start editing a location
    const handleStartEdit = (location) => {
        setEditingLocationId(location.id);
        setEditLocationName(location.name);
        setEditLocationDescription(location.description || '');
    };

    // Save the edited location
    const handleSaveEdit = () => {
        const trimmedName = editLocationName.trim();
        const trimmedDescription = editLocationDescription.trim();
        
        if (!trimmedName) {
            alert("Location name cannot be empty.");
            return;
        }
        
        // Check for duplicate names, excluding the current location
        if (locations.some(loc => 
            loc.id !== editingLocationId && 
            loc.name.toLowerCase() === trimmedName.toLowerCase()
        )) {
            alert(`Location "${trimmedName}" already exists.`);
            return;
        }
        
        const updatedLocation = {
            id: editingLocationId,
            name: trimmedName,
            description: trimmedDescription
        };
        
        onEditLocation(editingLocationId, updatedLocation);
        setEditingLocationId(null);
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingLocationId(null);
    };

    // Toggle expanded state for a location
    const toggleLocationExpanded = (locationId) => {
        setExpandedLocations(prev => ({
            ...prev,
            [locationId]: !prev[locationId]
        }));
    };

    // Get components for a specific location
    const getComponentsForLocation = (locationId) => {
        return components.filter(comp => 
            comp.locationInfo && comp.locationInfo.locationId === locationId
        );
    };

    // Get drawers for a specific location
    const getDrawersForLocation = (locationId) => {
        return drawers.filter(drawer => drawer.locationId === locationId);
    };

    return React.createElement('div', { className: "space-y-6" },
        // Add new location form
        React.createElement('div', { className: "mb-6 bg-white p-4 rounded-lg shadow border border-gray-200" },
            // Clickable header with toggle arrow
            React.createElement('div', { 
                className: "flex justify-between items-center cursor-pointer",
                onClick: () => {
                    console.log("Toggle location form visibility", !showAddLocationForm);
                    setShowAddLocationForm(!showAddLocationForm);
                }
            },
                React.createElement('h4', { className: "font-medium text-gray-700" }, "Add New Location"),
                React.createElement('span', { className: "text-gray-500" },
                    React.createElement('svg', {
                        xmlns: "http://www.w3.org/2000/svg",
                        className: `h-5 w-5 transition-transform ${showAddLocationForm ? 'transform rotate-180' : ''}`,
                        fill: "none",
                        viewBox: "0 0 24 24",
                        stroke: "currentColor"
                    },
                        React.createElement('path', {
                            strokeLinecap: "round",
                            strokeLinejoin: "round",
                            strokeWidth: 2,
                            d: showAddLocationForm ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"
                        })
                    )
                )
            ),
            
            // Form (conditionally rendered based on state)
            showAddLocationForm && React.createElement('div', { className: "mt-3" },
                React.createElement('form', { onSubmit: handleAddSubmit, className: "space-y-3" },
                    // Name input
                    React.createElement('div', null,
                        React.createElement('label', { 
                            htmlFor: "new-location-name", 
                            className: "block mb-1 text-sm font-medium text-gray-700" 
                        }, "Location Name"),
                        React.createElement('input', {
                            id: "new-location-name",
                            type: "text",
                            value: newLocationName,
                            onChange: (e) => setNewLocationName(e.target.value),
                            placeholder: "e.g., Lab Room 101",
                            className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        })
                    ),
                    // Description input
                    React.createElement('div', null,
                        React.createElement('label', { 
                            htmlFor: "new-location-description", 
                            className: "block mb-1 text-sm font-medium text-gray-700" 
                        }, "Description (Optional)"),
                        React.createElement('input', {
                            id: "new-location-description",
                            type: "text",
                            value: newLocationDescription,
                            onChange: (e) => setNewLocationDescription(e.target.value),
                            placeholder: "e.g., Main electronics workbench",
                            className: "w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        })
                    ),
                    // Submit button
                    React.createElement('div', null,
                        React.createElement('button', {
                            type: "submit",
                            className: "px-4 py-2 bg-blue-500 text-white rounded shadow hover:bg-blue-600 transition duration-150 ease-in-out"
                        }, "Add Location")
                    )
                )
            )
        ),
        
        // Locations list
        React.createElement('div', { className: "bg-white p-4 rounded-lg shadow border border-gray-200" },
            React.createElement('h4', { className: UI.typography.sectionTitle }, "Location List"),
            
            locations.length === 0 ?
                React.createElement('p', { className: "text-gray-500 italic" }, "No locations defined yet.") :
                
                // Locations accordion list
                React.createElement('div', { className: "divide-y divide-gray-200" },
                    locations.map(location => {
                        const isEditing = editingLocationId === location.id;
                        const isExpanded = expandedLocations[location.id];
                        const locationComponents = getComponentsForLocation(location.id);
                        const locationDrawers = getDrawersForLocation(location.id);
                        
                        return React.createElement('div', { 
                            key: location.id, 
                            className: "py-2"
                        },
                            // Location header (name, description, actions)
                            React.createElement('div', { className: "flex items-center justify-between" },
                                // Expand/collapse button and name
                                React.createElement('div', { 
                                    className: "flex items-center cursor-pointer",
                                    onClick: () => !isEditing && toggleLocationExpanded(location.id)
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
                                            React.createElement('span', { className: "font-medium text-gray-800" }, location.name),
                                            location.description && React.createElement('span', { className: "ml-2 text-sm text-gray-500" }, `(${location.description})`)
                                        ) :
                                        // Edit form inline
                                        React.createElement('div', { className: "flex-1 flex space-x-2" },
                                            React.createElement('input', {
                                                type: "text",
                                                value: editLocationName,
                                                onChange: (e) => setEditLocationName(e.target.value),
                                                className: "p-1 border border-gray-300 rounded text-sm w-full max-w-xs",
                                                placeholder: "Location name"
                                            }),
                                            React.createElement('input', {
                                                type: "text",
                                                value: editLocationDescription,
                                                onChange: (e) => setEditLocationDescription(e.target.value),
                                                className: "p-1 border border-gray-300 rounded text-sm w-full",
                                                placeholder: "Description (optional)"
                                            })
                                        )
                                ),
                                
                                // Action buttons
                                React.createElement('div', { className: "flex space-x-2" },
                                    !isEditing ?
                                        React.createElement(React.Fragment, null,
                                            React.createElement('button', {
                                                onClick: () => handleStartEdit(location),
                                                className: UI.buttons.small.primary,
                                                title: "Edit Location"
                                            }, "Edit"),
                                            React.createElement('button', {
                                                onClick: () => onDeleteLocation(location.id),
                                                className: UI.buttons.small.danger,
                                                title: "Delete Location"
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
                            
                            // Components and drawers in this location (collapsible)
                            isExpanded && !isEditing && React.createElement('div', { 
                                className: "mt-2 ml-7 pl-2 border-l-2 border-gray-200"
                            },
                                // Components Section
                                React.createElement('h5', { className: "text-sm font-medium text-gray-700 mb-1" }, 
                                    `Components in this location (${locationComponents.length})`
                                ),
                                locationComponents.length === 0 ?
                                    React.createElement('p', { className: "text-sm text-gray-500 italic mb-3" }, 
                                        "No components assigned to this location."
                                    ) :
                                    React.createElement('ul', { className: "space-y-1 mb-3" },
                                        locationComponents.slice(0, 5).map(comp => 
                                            React.createElement('li', { key: comp.id, className: "flex justify-between items-center" },
                                                React.createElement('span', { className: "text-sm" }, comp.name),
                                                React.createElement('button', {
                                                    onClick: () => onEditComponent(comp),
                                                    className: "text-xs text-blue-500 hover:text-blue-700",
                                                    title: "Edit Component"
                                                }, "Edit")
                                            )
                                        ),
                                        locationComponents.length > 5 && React.createElement('li', { className: "text-xs text-gray-500 italic" },
                                            `... and ${locationComponents.length - 5} more component(s)`
                                        )
                                    ),
                                
                                // Drawers Section
                                React.createElement('h5', { className: "text-sm font-medium text-gray-700 mb-1 mt-3" }, 
                                    `Drawers in this location (${locationDrawers.length})`
                                ),
                                locationDrawers.length === 0 ?
                                    React.createElement('p', { className: "text-sm text-gray-500 italic" }, 
                                        "No drawers defined for this location."
                                    ) :
                                    React.createElement('ul', { className: "space-y-1" },
                                        locationDrawers.map(drawer => 
                                            React.createElement('li', { key: drawer.id, className: "flex justify-between items-center" },
                                                React.createElement('div', { className: "flex items-center" },
                                                    React.createElement('span', { className: "text-sm" }, drawer.name),
                                                    drawer.description && React.createElement('span', { className: "text-xs text-gray-500 ml-2" }, 
                                                        `(${drawer.description})`
                                                    )
                                                ),
                                                React.createElement('button', {
                                                    onClick: () => onNavigateToDrawer(drawer.id),
                                                    className: "px-2 py-1 bg-green-500 text-white text-xs rounded shadow hover:bg-green-600",
                                                    title: "View Drawer"
                                                }, "View")
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

console.log("LocationManager component loaded."); // For debugging