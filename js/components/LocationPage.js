// js/components/LocationPage.js

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

    // Find the current drawer and its location if viewing a drawer
    const currentDrawer = drawers.find(drawer => drawer.id === viewingDrawerId);
    
    const currentLocation = currentDrawer
        ? locations.find(loc => loc.id === currentDrawer.locationId)
        : null;

    // Handler for viewing a drawer
    const handleViewDrawer = (drawerId) => {
        if (onNavigateToDrawer) {
            onNavigateToDrawer(drawerId);
        }
    };

    // Handler for returning to location list
    const handleBackToLocations = () => {
        setViewingDrawerId(null);
    };

    // Render logic for the LocationPage component
    return React.createElement('div', { className: "space-y-6" },
        React.createElement('h2', { className: UI.typography.heading.h2 }, "Location Management"),
        React.createElement('p', { className: UI.typography.body },
            "Manage physical storage locations for your components."
        ),

        React.createElement(LocationManager, {
            locations,
            components,
            drawers,
            onAddLocation,
            onEditLocation,
            onDeleteLocation,
            onEditComponent,
            onNavigateToDrawer: handleViewDrawer,
            handleBackToLocations, 
        })
    );
};

console.log("LocationPage component loaded with theme-aware styling."); // For debugging