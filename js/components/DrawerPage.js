// js/components/DrawerPage.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Drawer Management Page.
 * This page handles both the list of drawers and viewing individual drawers.
 */
window.App.components.DrawerPage = ({
    // Props
    locations, // Array: List of location objects
    drawers, // Array: List of drawer objects
    cells, // Array: List of cell objects
    components, // Array: All component objects
    // Callbacks
    onAddDrawer, // Function(newDrawer): Called to add a new drawer
    onEditDrawer, // Function(drawerId, updatedDrawer): Called to edit a drawer
    onDeleteDrawer, // Function(drawerId): Called to delete a drawer
    onAddCell, // Function(newCell): Called to add a new cell
    onEditCell, // Function(cellId, updatedCell): Called to edit a cell
    onDeleteCell, // Function(cellId): Called to delete a cell
    onEditComponent, // Function: Pass-through to edit component
    initialDrawerId,
}) => {
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;
    const { DrawerManager, DrawerView } = window.App.components;

    // Internal state
    const [viewingDrawerId, setViewingDrawerId] = useState(initialDrawerId || null);
    
    // Find the current drawer and its location if viewing a drawer
    const currentDrawer = drawers.find(drawer => drawer.id === viewingDrawerId);
    const currentLocation = currentDrawer 
        ? locations.find(loc => loc.id === currentDrawer.locationId) 
        : null;

    // Handler for viewing a drawer
    const handleViewDrawer = (drawerId) => {
        setViewingDrawerId(drawerId);
    };

    // Handler for deleting a drawer with confirmation
    const handleDeleteDrawer = (drawerId) => {
        // Check if any components are assigned to this drawer
        const assignedComponents = components.filter(comp => 
            comp.storageInfo && comp.storageInfo.drawerId === drawerId
        );

        // Confirm deletion with warning if components are assigned
        const message = assignedComponents.length > 0
            ? `This drawer has ${assignedComponents.length} component(s) assigned to it. Removing it will clear the drawer from these components. Continue?`
            : 'Are you sure you want to delete this drawer?';

        if (window.confirm(message)) {
            if (viewingDrawerId === drawerId) {
                setViewingDrawerId(null); // Navigate back to drawer list if deleting current drawer
            }
            onDeleteDrawer(drawerId);
        }
    };

    // Handler for deleting a cell with confirmation
    const handleDeleteCell = (cellId) => {
        // Check if any components are assigned to this cell
        const assignedComponents = components.filter(comp => 
            comp.storageInfo && comp.storageInfo.cellId === cellId
        );

        // Confirm deletion with warning if components are assigned
        const message = assignedComponents.length > 0
            ? `This cell has ${assignedComponents.length} component(s) assigned to it. Removing it will clear the cell from these components. Continue?`
            : 'Are you sure you want to delete this cell?';

        if (window.confirm(message)) {
            onDeleteCell(cellId);
        }
    };
    
    // Reset the viewing drawer when initialDrawerId changes or when navigating to the page
    useEffect(() => {
        if (initialDrawerId) {
            setViewingDrawerId(initialDrawerId);
        } else {
            // Reset to drawer list when returning to the page without an initialDrawerId
            setViewingDrawerId(null);
        }
    }, [initialDrawerId]);
    
    // Additional hook to reset viewingDrawerId when the page changes
    useEffect(() => {
        // This will run on component mount and cleanup
        return () => {
            // Reset when leaving the DrawerPage
            setViewingDrawerId(null);
        };
    }, []);

    // Render
    return React.createElement('div', { className: "space-y-6" },
        React.createElement('h2', { className: UI.typography.heading.h2 }, "Drawer Management"),
        React.createElement('p', { className: UI.typography.body },
            "Manage drawer organization and cell assignments for your electronic components."
        ),

        viewingDrawerId && currentDrawer
            // Render drawer view if a drawer is selected
            ? React.createElement(DrawerView, {
                drawer: currentDrawer,
                cells: cells,
                components: components,
                location: currentLocation,
                onAddCell: onAddCell,
                onEditCell: onEditCell,
                onDeleteCell: handleDeleteCell,
                onEditComponent: onEditComponent,
                onBackToDrawers: () => setViewingDrawerId(null)
            })
            // Otherwise render drawer management view
            : React.createElement(DrawerManager, {
                locations: locations,
                drawers: drawers,
                components: components,
                onAddDrawer: onAddDrawer,
                onEditDrawer: onEditDrawer,
                onDeleteDrawer: handleDeleteDrawer,
                onViewDrawer: handleViewDrawer,
                onEditComponent: onEditComponent,
                onBackToDrawers: () => setViewingDrawerId(null)
            })
    );
};

console.log("DrawerPage component loaded with theme-aware styling."); // For debugging