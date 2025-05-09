// js/components/DrawerPage.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Drawer Management Page.
 * This page handles both the list of drawers and viewing individual drawers.
 * Updated to support IndexedDB operations.
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
    const [loading, setLoading] = useState(false);
    
    // Find the current drawer and its location if viewing a drawer
    const currentDrawer = drawers.find(drawer => drawer.id === viewingDrawerId);
    const currentLocation = currentDrawer 
        ? locations.find(loc => loc.id === currentDrawer.locationId) 
        : null;

    // Handler for viewing a drawer
    const handleViewDrawer = (drawerId) => {
        setLoading(true);
        setTimeout(() => {
            setViewingDrawerId(drawerId);
            setLoading(false);
        }, 300);
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
            setLoading(true);
            
            if (viewingDrawerId === drawerId) {
                setViewingDrawerId(null); // Navigate back to drawer list if deleting current drawer
            }
            
            // Use short timeout to show loading state
            setTimeout(() => {
                onDeleteDrawer(drawerId);
                setLoading(false);
            }, 300);
        }
    };

    // Handler for deleting a cell with confirmation
    const handleDeleteCell = (cellId) => {
        // Check if any components are assigned to this cell
        const assignedComponents = components.filter(comp => 
            comp.storageInfo && 
            (comp.storageInfo.cellId === cellId || 
             (comp.storageInfo.cells && Array.isArray(comp.storageInfo.cells) && 
              comp.storageInfo.cells.includes(cellId)))
        );

        // Confirm deletion with warning if components are assigned
        const message = assignedComponents.length > 0
            ? `This cell has ${assignedComponents.length} component(s) assigned to it. Removing it will clear the cell from these components. Continue?`
            : 'Are you sure you want to delete this cell?';

        if (window.confirm(message)) {
            setLoading(true);
            
            // Use short timeout to show loading state
            setTimeout(() => {
                onDeleteCell(cellId);
                setLoading(false);
            }, 300);
        }
    };
    
    // Updated handlers for drawer operations
    const handleAddDrawer = (newDrawer) => {
        setLoading(true);
        
        // Normalize drawer data if helper is available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeDrawer === 'function') {
            newDrawer = window.App.utils.helpers.normalizeDrawer(newDrawer);
        }
        
        // Add the drawer with a short delay to show loading state
        setTimeout(() => {
            onAddDrawer(newDrawer);
            setLoading(false);
        }, 300);
    };
    
    const handleEditDrawer = (drawerId, updatedDrawer) => {
        setLoading(true);
        
        // Normalize drawer data if helper is available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeDrawer === 'function') {
            updatedDrawer = window.App.utils.helpers.normalizeDrawer(updatedDrawer);
            // Preserve the original ID
            updatedDrawer.id = drawerId;
        }
        
        // Edit the drawer with a short delay to show loading state
        setTimeout(() => {
            onEditDrawer(drawerId, updatedDrawer);
            setLoading(false);
        }, 300);
    };
    
    // Updated handlers for cell operations
    const handleAddCell = (newCell) => {
        setLoading(true);
        
        // Normalize cell data if helper is available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeCell === 'function') {
            newCell = window.App.utils.helpers.normalizeCell(newCell);
        }
        
        // Add the cell with a short delay to show loading state
        setTimeout(() => {
            onAddCell(newCell);
            setLoading(false);
        }, 300);
    };
    
    const handleEditCell = (cellId, updatedCell) => {
        setLoading(true);
        
        // Normalize cell data if helper is available
        if (window.App.utils.helpers && typeof window.App.utils.helpers.normalizeCell === 'function') {
            updatedCell = window.App.utils.helpers.normalizeCell(updatedCell);
            // Preserve the original ID
            updatedCell.id = cellId;
        }
        
        // Edit the cell with a short delay to show loading state
        setTimeout(() => {
            onEditCell(cellId, updatedCell);
            setLoading(false);
        }, 300);
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
        // Loading overlay
        loading && React.createElement('div', { 
            className: "fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-50" 
        },
            React.createElement('div', { 
                className: "bg-white p-4 rounded-lg shadow-xl" 
            },
                React.createElement('div', { 
                    className: "w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" 
                })
            )
        ),
        
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
                onAddCell: handleAddCell,
                onEditCell: handleEditCell,
                onDeleteCell: handleDeleteCell,
                onEditComponent: onEditComponent,
                onBackToDrawers: () => setViewingDrawerId(null)
            })
            // Otherwise render drawer management view
            : React.createElement(DrawerManager, {
                locations: locations,
                drawers: drawers,
                components: components,
                onAddDrawer: handleAddDrawer,
                onEditDrawer: handleEditDrawer,
                onDeleteDrawer: handleDeleteDrawer,
                onViewDrawer: handleViewDrawer,
                onEditComponent: onEditComponent,
                onBackToDrawers: () => setViewingDrawerId(null)
            })
    );
};

console.log("DrawerPage component loaded with IndexedDB compatibility.");