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

    // Create keydown handler to prevent disallowed characters
    const handleKeyDown = window.App.utils.sanitize.createKeyDownHandler();

    // Create change handler for allowed characters
    const handleChange = (setter) => (e) => {
        const sanitizedValue = window.App.utils.sanitize.validateAllowedChars(e.target.value);
        setter(sanitizedValue);
    };

    // Handle adding a new location
    const handleAddSubmit = (e) => {
        e.preventDefault();
        
        // Final sanitization before submission
        const trimmedName = window.App.utils.sanitize.locationName(newLocationName);
        const trimmedDescription = window.App.utils.sanitize.locationDescription(newLocationDescription);
        
        if (!trimmedName) {
            alert("Location name cannot be empty.");
            return;
        }
        
        // Check for duplicate location names
        if (locations.some(loc => loc.name.toLowerCase() === trimmedName.toLowerCase())) {
            alert(`Location "${trimmedName}" already exists.`);
            return;
        }
        
        // Create sanitized location object
        const newLocation = window.App.utils.sanitize.location({
            id: `loc-${Date.now()}`,
            name: trimmedName,
            description: trimmedDescription
        });
        
        onAddLocation(newLocation);
        // Reset form
        setNewLocationName('');
        setNewLocationDescription('');
        setShowAddLocationForm(false);
    };

    // Start editing a location
    const handleStartEdit = (location) => {
        // Sanitize the location data before setting state
        const sanitizedLocation = window.App.utils.sanitize.location(location);
        
        setEditingLocationId(sanitizedLocation.id);
        setEditLocationName(sanitizedLocation.name);
        setEditLocationDescription(sanitizedLocation.description || '');
    };

    // Save the edited location
    const handleSaveEdit = () => {
        // Final sanitization before saving
        const trimmedName = window.App.utils.sanitize.locationName(editLocationName);
        const trimmedDescription = window.App.utils.sanitize.locationDescription(editLocationDescription);
        
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
        
        // Create sanitized updated location object
        const updatedLocation = window.App.utils.sanitize.location({
            id: editingLocationId,
            name: trimmedName,
            description: trimmedDescription
        });
        
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
        comp.storage && comp.storage.locationId === locationId
    );
};

    // Get drawers for a specific location
    const getDrawersForLocation = (locationId) => {
        return drawers.filter(drawer => drawer.locationId === locationId);
    };

    return React.createElement('div', { className: "space-y-6" },
        // Add new location form
        React.createElement('div', { className: `mb-6 ${UI.cards.container}` },
            // Clickable header with toggle arrow
            React.createElement('div', { 
                className: `flex justify-between items-center cursor-pointer ${UI.cards.header}`,
                onClick: () => {
                    console.log("Toggle location form visibility", !showAddLocationForm);
                    setShowAddLocationForm(!showAddLocationForm);
                }
            },
                React.createElement('h4', { className: `font-medium text-${UI.getThemeColors().textSecondary}` }, "Add New Location"),
                React.createElement('span', { className: `text-${UI.getThemeColors().textMuted}` },
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
            showAddLocationForm && React.createElement('div', { className: UI.cards.body },
                React.createElement('form', { onSubmit: handleAddSubmit, className: "space-y-3" },
                    // Name input with validation
                    React.createElement('div', { className: "relative" },
                        React.createElement('label', { 
                            htmlFor: "new-location-name", 
                            className: UI.forms.label 
                        }, "Location Name"),
                        React.createElement('input', {
                            id: "new-location-name",
                            type: "text",
                            value: newLocationName,
                            onChange: handleChange(setNewLocationName),
                            onKeyDown: handleKeyDown,
                            maxLength: window.App.utils.sanitize.LIMITS.LOCATION_NAME,
                            pattern: "[A-Za-z0-9,.\-_ ]*",
                            placeholder: "e.g., Lab Room 101",
                            className: UI.forms.input,
                            required: true
                        }),
                        React.createElement('p', { className: UI.forms.hint },
                            `Location name. (A-Z a-z 0-9 . , - _ space @ /) (max ${window.App.utils.sanitize.LIMITS.LOCATION_NAME} chars)`
                        ),
                        // Character counter
                        React.createElement('div', {
                            className: `absolute bottom-1 right-2 text-xs ${
                                newLocationName.length > window.App.utils.sanitize.LIMITS.LOCATION_NAME * 0.8 
                                    ? 'text-orange-500' 
                                    : `text-${UI.getThemeColors().textMuted}`
                            }`
                        }, `${newLocationName.length}/${window.App.utils.sanitize.LIMITS.LOCATION_NAME}`)
                    ),
                    // Description input with validation
                    React.createElement('div', { className: "relative" },
                        React.createElement('label', { 
                            htmlFor: "new-location-description", 
                            className: UI.forms.label
                        }, "Description (Optional)"),
                        React.createElement('input', {
                            id: "new-location-description",
                            type: "text",
                            value: newLocationDescription,
                            onChange: handleChange(setNewLocationDescription),
                            onKeyDown: handleKeyDown,
                            maxLength: window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION,
                            pattern: "[A-Za-z0-9,.\-_ ]*",
                            placeholder: "e.g., Main electronics workbench",
                            className: UI.forms.input
                        }),
                        React.createElement('p', { className: UI.forms.hint },
                            `Location description. (A-Z a-z 0-9 . , - _ space @ /) (max ${window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION} chars)`
                        ),
                        // Character counter
                        React.createElement('div', {
                            className: `absolute bottom-1 right-2 text-xs ${
                                newLocationDescription.length > window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION * 0.8 
                                    ? 'text-orange-500' 
                                    : `text-${UI.getThemeColors().textMuted}`
                            }`
                        }, `${newLocationDescription.length}/${window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION}`)
                    ),
                    // Submit button
                    React.createElement('div', null,
                        React.createElement('button', {
                            type: "submit",
                            className: UI.buttons.primary,
                            disabled: !newLocationName.trim()
                        }, "Add Location")
                    )
                )
            )
        ),
        
        // Locations list
        React.createElement('div', { className: UI.cards.container },
            React.createElement('h4', { className: `${UI.typography.sectionTitle} ${UI.cards.header}` }, "Location List"),
            
            React.createElement('div', { className: UI.cards.body },
                locations.length === 0 ?
                    React.createElement('p', { className: `text-${UI.getThemeColors().textMuted} italic` }, "No locations defined yet.") :
                    
                    // Locations accordion list
                    React.createElement('div', { className: `divide-y divide-${UI.getThemeColors().border}` },
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
                                                React.createElement('span', { className: `font-medium text-${UI.getThemeColors().textPrimary}` }, location.name),
                                                location.description && React.createElement('span', { className: `ml-2 text-sm text-${UI.getThemeColors().textMuted}` }, `(${location.description})`)
                                            ) :
                                            // Edit form inline with validation
                                            React.createElement('div', { className: "flex-1 flex space-x-2" },
                                                React.createElement('div', { className: "relative flex-grow max-w-xs" },
                                                    React.createElement('input', {
                                                        type: "text",
                                                        value: editLocationName,
                                                        onChange: handleChange(setEditLocationName),
                                                        onKeyDown: handleKeyDown,
                                                        maxLength: window.App.utils.sanitize.LIMITS.LOCATION_NAME,
                                                        pattern: "[A-Za-z0-9,.\-_ ]*",
                                                        className: "p-1 border border-gray-300 rounded text-sm w-full",
                                                        placeholder: "Location name"
                                                    }),
                                                    React.createElement('div', {
                                                        className: `absolute -bottom-5 right-0 text-xs ${
                                                            editLocationName.length > window.App.utils.sanitize.LIMITS.LOCATION_NAME * 0.8 
                                                                ? 'text-orange-500' 
                                                                : 'text-gray-400'
                                                        }`
                                                    }, `${editLocationName.length}/${window.App.utils.sanitize.LIMITS.LOCATION_NAME}`)
                                                ),
                                                React.createElement('div', { className: "relative flex-grow" },
                                                    React.createElement('input', {
                                                        type: "text",
                                                        value: editLocationDescription,
                                                        onChange: handleChange(setEditLocationDescription),
                                                        onKeyDown: handleKeyDown,
                                                        maxLength: window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION,
                                                        pattern: "[A-Za-z0-9,.\-_ ]*",
                                                        className: "p-1 border border-gray-300 rounded text-sm w-full",
                                                        placeholder: "Description (optional)"
                                                    }),
                                                    React.createElement('div', {
                                                        className: `absolute -bottom-5 right-0 text-xs ${
                                                            editLocationDescription.length > window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION * 0.8 
                                                                ? 'text-orange-500' 
                                                                : 'text-gray-400'
                                                        }`
                                                    }, `${editLocationDescription.length}/${window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION}`)
                                                )
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
                                
                                // Components and drawers in this location (collapsible)
                                isExpanded && !isEditing && React.createElement('div', { 
                                    className: `mt-2 ml-7 pl-2 border-l-2 border-${UI.getThemeColors().borderLight}`
                                },
                                    // Components Section
                                    React.createElement('h5', { className: `text-sm font-medium text-${UI.getThemeColors().textSecondary} mb-1` }, 
                                        `Components in this location (${locationComponents.length})`
                                    ),
                                    locationComponents.length === 0 ?
                                        React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textMuted} italic mb-3` }, 
                                            "No components assigned to this location."
                                        ) :
                                        React.createElement('ul', { className: "space-y-1 mb-3" },
                                            locationComponents.slice(0, 5).map(comp => 
                                                React.createElement('li', { key: comp.id, className: "flex justify-between items-center" },
                                                    React.createElement('span', { className: "text-sm" }, comp.name),
                                                    React.createElement('button', {
                                                        onClick: () => onEditComponent(comp),
                                                        className: `text-xs ${UI.colors.info.text} hover:${UI.colors.info.hover}`,
                                                        title: "Edit Component"
                                                    }, "Edit")
                                                )
                                            ),
                                            locationComponents.length > 5 && React.createElement('li', { className: `text-xs text-${UI.getThemeColors().textMuted} italic` },
                                                `... and ${locationComponents.length - 5} more component(s)`
                                            )
                                        ),
                                    
                                    // Drawers Section
                                    React.createElement('h5', { className: `text-sm font-medium text-${UI.getThemeColors().textSecondary} mb-1 mt-3` }, 
                                        `Drawers in this location (${locationDrawers.length})`
                                    ),
                                    locationDrawers.length === 0 ?
                                        React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textMuted} italic` }, 
                                            "No drawers defined for this location."
                                        ) :
                                        React.createElement('ul', { className: "space-y-1" },
                                            locationDrawers.map(drawer => 
                                                React.createElement('li', { key: drawer.id, className: "flex justify-between items-center" },
                                                    React.createElement('div', { className: "flex items-center" },
                                                        React.createElement('span', { className: "text-sm" }, drawer.name),
                                                        drawer.description && React.createElement('span', { className: `text-xs text-${UI.getThemeColors().textMuted} ml-2` }, 
                                                            `(${drawer.description})`
                                                        )
                                                    ),
                                                    React.createElement('button', {
                                                        onClick: () => onNavigateToDrawer(drawer.id),
                                                        className: UI.buttons.small.success,
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
        )
    );
};

console.log("LocationManager loaded"); // For debugging