// js/components/LocationPage.js - Updated for IndexedDB compatibility

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Location Management Page.
 */
window.App.components.LocationPage = ({
    // Props
    locations, // Array: List of location objects
    components, // Array: All component objects
    drawers, // Array: List of drawer objects
    // Callbacks
    onAddLocation, // Function(newLocation): Called to add a new location
    onEditLocation, // Function(locationId, updatedLocation): Called to edit a location
    onDeleteLocation, // Function(locationId): Called to delete a location
    onEditComponent, // Function: Pass-through to edit component
    onNavigateToDrawer, // Function to navigate to the drawer page with a specific drawer
}) => {
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;
    const { LocationManager } = window.App.components;

    const [viewingDrawerId, setViewingDrawerId] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // Find the current drawer and its location if viewing a drawer
    const currentDrawer = drawers.find(drawer => drawer.id === viewingDrawerId);
    
    const currentLocation = currentDrawer
        ? locations.find(loc => loc.id === currentDrawer.locationId)
        : null;

    // Handler for viewing a drawer
    const handleViewDrawer = (drawerId) => {
        if (onNavigateToDrawer) {
            setIsLoading(true);
            
            // Simulate a small delay to show loading state
            setTimeout(() => {
                onNavigateToDrawer(drawerId);
                setIsLoading(false);
            }, 100);
        }
    };

    // Handler for returning to location list
    const handleBackToLocations = () => {
        setViewingDrawerId(null);
    };

    // Handler for adding a location with proper IndexedDB normalization
    const handleAddLocation = (newLocation) => {
        // Use the helper to normalize the location data if available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeLocation === 'function') {
            newLocation = window.App.utils.helpers.normalizeLocation(newLocation);
        }
        
        // Call the parent handler
        onAddLocation(newLocation);
    };

    // Handler for editing a location with proper IndexedDB normalization
    const handleEditLocation = (locationId, updatedLocation) => {
        // Use the helper to normalize the location data if available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeLocation === 'function') {
            updatedLocation = window.App.utils.helpers.normalizeLocation(updatedLocation);
            // Preserve the original ID
            updatedLocation.id = locationId;
        }
        
        // Call the parent handler
        onEditLocation(locationId, updatedLocation);
    };

    // Render logic for the LocationPage component
    return React.createElement('div', { className: "space-y-6" },
        React.createElement('h2', { className: UI.typography.heading.h2 }, "Location Management"),
        React.createElement('p', { className: UI.typography.body },
            "Manage physical storage locations for your components."
        ),

        // Show loading state if navigating
        isLoading && React.createElement('div', { 
            className: `p-4 text-center ${UI.colors.background.alt} rounded-lg border border-${UI.getThemeColors().border}`
        },
            React.createElement('div', { 
                className: "w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" 
            }),
            React.createElement('p', null, "Loading drawer view...")
        ),

        !isLoading && React.createElement(LocationManager, {
            locations,
            components,
            drawers,
            onAddLocation: handleAddLocation,
            onEditLocation: handleEditLocation,
            onDeleteLocation,
            onEditComponent,
            onNavigateToDrawer: handleViewDrawer,
            handleBackToLocations, 
        })
    );
};

console.log("LocationPage component loaded with IndexedDB compatibility.");