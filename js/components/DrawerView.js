// js/components/DrawerView.js - Updated for IndexedDB compatibility

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for viewing and managing the contents of a drawer.
 * Displays a grid of cells with the ability to name cells and view/edit components in cells.
 * Modified to support IndexedDB operations.
 */
window.App.components.DrawerView = ({
    // Props
    drawer, // Object: The drawer being viewed
    cells, // Array: Cell objects for this drawer
    components, // Array: All component objects
    location, // Object: The location this drawer belongs to
    // Callbacks
    onAddCell, // Function(newCell): Called to add/update a cell
    onEditCell, // Function(cellId, updatedCell): Called to edit a cell
    onDeleteCell, // Function(cellId): Called to delete a cell
    onEditComponent, // Function(component): Called to edit a component
    onBackToDrawers, // Function: Called when "Back to Drawers" button is clicked
}) => {
    // Get UI constants
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;

    // Internal state
    const [selectedCellId, setSelectedCellId] = useState(null);
    const [editingCellId, setEditingCellId] = useState(null);
    const [editCellNickname, setEditCellNickname] = useState('');
    const [loading, setLoading] = useState(false);

    // Grid dimensions
    const rows = drawer?.grid?.rows || 3;
    const cols = drawer?.grid?.cols || 3;

    // Get all cells for this drawer
    const drawerCells = cells.filter(cell => cell.drawerId === drawer.id);

    // Create a mapping of coordinate to cell
    const cellMap = {};
    drawerCells.forEach(cell => {
        cellMap[cell.coordinate] = cell;
    });

    // Generate alphabetical column headers (A, B, C, ...)
    const getColLabel = (index) => {
        // For indices beyond 25 (Z), use AA, AB, etc.
        if (index <= 25) {
            return String.fromCharCode(65 + index); // A=65 in ASCII
        } else {
            const firstChar = String.fromCharCode(65 + Math.floor(index / 26) - 1);
            const secondChar = String.fromCharCode(65 + (index % 26));
            return `${firstChar}${secondChar}`;
        }
    };

    // Get components for a specific cell
    const getComponentsForCell = (cellId) => {
        if (!cellId) return [];
        return components.filter(comp => {
            if (!comp.storageInfo) return false;

            // Check for the new format (cells array)
            if (comp.storageInfo.cells && Array.isArray(comp.storageInfo.cells)) {
                return comp.storageInfo.cells.includes(cellId);
            }

            // Fallback to old format (single cellId)
            return comp.storageInfo.cellId === cellId;
        });
    };

    // Handle editing a cell nickname
    const handleEditCellNickname = (cell) => {
        if (!cell || !cell.id) return;
        setEditingCellId(cell.id);
        setEditCellNickname(cell.nickname || '');
    };

    // Handle saving a cell nickname
    const handleSaveCellNickname = () => {
        setLoading(true);
        
        const cellToUpdate = drawerCells.find(cell => cell.id === editingCellId);
        if (!cellToUpdate) {
            setLoading(false);
            return;
        }

        const trimmedNickname = editCellNickname.trim();

        // Check for duplicate nicknames in this drawer
        const isDuplicate = drawerCells.some(cell =>
            cell.id !== editingCellId &&
            cell.nickname &&
            cell.nickname.toLowerCase() === trimmedNickname.toLowerCase()
        );

        if (isDuplicate && trimmedNickname) {
            alert(`Nickname "${trimmedNickname}" is already used in this drawer.`);
            setLoading(false);
            return;
        }

        const updatedCell = {
            ...cellToUpdate,
            nickname: trimmedNickname,
            available: cellToUpdate.available !== undefined ? cellToUpdate.available : true
        };

        onEditCell(editingCellId, updatedCell);
        
        setTimeout(() => {
            setEditingCellId(null);
            setEditCellNickname('');
            setLoading(false);
        }, 300);
    };

    // Handle toggling cell availability
    const handleToggleAvailability = (cellId) => {
        if (!cellId) return;
        setLoading(true);
        
        const cellToToggle = drawerCells.find(cell => cell.id === cellId);
        if (!cellToToggle) {
            setLoading(false);
            return;
        }

        const updatedCell = {
            ...cellToToggle,
            available: cellToToggle.available === false ? true : false // Toggle the value
        };

        onEditCell(cellId, updatedCell);
        
        setTimeout(() => {
            setLoading(false);
        }, 300);
    };

    // Handle emptying a cell by removing all component associations
    const handleEmptyCell = (cellId) => {
        if (!cellId) return;
        setLoading(true);
        
        // Find components assigned to this cell
        const cellComponents = getComponentsForCell(cellId);
        
        if (cellComponents.length === 0) {
            alert("This cell is already empty.");
            setLoading(false);
            return;
        }

        if (window.confirm(`Remove ${cellComponents.length} component(s) from this cell?`)) {
            // We need to make a copy of the components array to update
            let updatedComponents = [...components];
            
            // For each component in the cell, update its storage info
            const updatePromises = cellComponents.map(component => {
                // Find the component in our components array
                const index = updatedComponents.findIndex(c => c.id === component.id);
                if (index !== -1) {
                    // Make a copy of the component to update
                    const updatedComponent = {...updatedComponents[index]};
                    
                    // Make sure storageInfo exists and is properly formatted
                    if (!updatedComponent.storageInfo || typeof updatedComponent.storageInfo === 'string') {
                        updatedComponent.storageInfo = { locationId: '', drawerId: '', cells: [] };
                    }
                    
                    // Handle new format (cells array)
                    if (updatedComponent.storageInfo.cells && Array.isArray(updatedComponent.storageInfo.cells)) {
                        updatedComponent.storageInfo.cells = updatedComponent.storageInfo.cells.filter(id => id !== cellId);
                    }
                    
                    // Handle legacy format (cellId)
                    if (updatedComponent.storageInfo.cellId === cellId) {
                        updatedComponent.storageInfo.cellId = '';
                    }
                    
                    // Update the component in our array
                    updatedComponents[index] = updatedComponent;
                    
                    // Call onEditComponent
                    return onEditComponent(updatedComponent);
                }
                return Promise.resolve();
            });
            
            // Wait for all updates to complete
            Promise.all(updatePromises)
                .then(() => {
                    setLoading(false);
                    alert(`Successfully removed ${cellComponents.length} component(s) from this cell.`);
                })
                .catch(error => {
                    console.error("Error emptying cell:", error);
                    setLoading(false);
                    alert("Error emptying cell. Please try again.");
                });
        } else {
            setLoading(false);
        }
    };
    
    // Handle clicking on a cell
    const handleCellClick = (cell) => {
        if (!cell) return;
        
        // If we're editing a cell, save before selecting a new one
        if (editingCellId && cell.id !== editingCellId) {
            handleSaveCellNickname();
        }

        setSelectedCellId(cell.id);
    };

    // Handle creating a new cell
    const handleCreateCell = (rowIndex, colIndex) => {
        setLoading(true);
        const coordinate = `${String.fromCharCode(65 + colIndex)}${rowIndex + 1}`;

        // Check if a cell already exists for this coordinate
        const existingCell = drawerCells.find(cell => cell.coordinate === coordinate);
        if (existingCell) {
            setSelectedCellId(existingCell.id);
            setLoading(false);
            return;
        }

        // Create a new cell with a unique ID
        const newCell = {
            id: `cell-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            drawerId: drawer.id,
            coordinate: coordinate,
            nickname: '',
            available: true // Add this property with default value true
        };

        onAddCell(newCell);
        
        setTimeout(() => {
            setSelectedCellId(newCell.id);
            setLoading(false);
        }, 300);
    };
    
    // Handle deleting a cell
    const handleDeleteCell = (cellId) => {
        if (!cellId) return;
        setLoading(true);
        
        onDeleteCell(cellId);
        
        setTimeout(() => {
            if (selectedCellId === cellId) {
                setSelectedCellId(null);
            }
            setLoading(false);
        }, 300);
    };

    // Generate grid elements
    const generateGrid = () => {
        const gridElements = [];

        // Column headers row
        const headerRow = [
            // Empty cell for row header column (top-left corner)
            React.createElement('div', {
                key: 'corner',
                className: `sticky left-0 top-0 z-10 bg-${UI.getThemeColors().background} p-2 font-medium border border-${UI.getThemeColors().border} text-center w-[40px] h-[40px]`
            })
        ];

        // Add column headers (A, B, C, ...)
        for (let c = 0; c < cols; c++) {
            headerRow.push(
                React.createElement('div', {
                    key: `col-${c}`,
                    className: `sticky top-0 z-10 bg-${UI.getThemeColors().background} p-2 font-medium border border-${UI.getThemeColors().border} text-center w-[100px] h-[40px]`
                }, getColLabel(c))
            );
        }

        gridElements.push(
            React.createElement('div', {
                key: 'header-row',
                className: "flex"
            }, headerRow)
        );

        // Generate rows
        for (let r = 0; r < rows; r++) {
            const rowElements = [
                // Row header (1, 2, 3, ...)
                React.createElement('div', {
                    key: `row-${r}`,
                    className: `sticky left-0 z-10 bg-${UI.getThemeColors().background} p-2 font-medium border border-${UI.getThemeColors().border} text-center w-[40px] h-[100px] flex items-center justify-center`
                }, r + 1)
            ];

            // Generate cells for this row
            for (let c = 0; c < cols; c++) {
                const coordinate = `${String.fromCharCode(65 + c)}${r + 1}`; // e.g., "A1", "B2"
                const cell = drawerCells.find(cell => cell.coordinate === coordinate);
                
                const cellComponents = cell && cell.id ? getComponentsForCell(cell.id) : [];
                const isSelected = cell && cell.id === selectedCellId;
                const isEditing = cell && cell.id === editingCellId;
                
                // Safely check available property with a default to true
                const isAvailable = cell ? (cell.available !== false) : true;
            
                const cellElement = React.createElement('div', {
                    key: `cell-${r}-${c}`,
                    className: `border border-${UI.getThemeColors().border} p-2 w-[100px] h-[100px] 
                        ${isSelected ? `bg-${UI.getThemeColors().primary.replace('500', '100').replace('400', '900')} border-${UI.getThemeColors().primary}` : `bg-${UI.getThemeColors().cardBackground}`} 
                        ${!isAvailable ? `bg-${UI.getThemeColors().background} opacity-70` : ''} 
                        ${cell && cell.id ? 'cursor-pointer' : 'cursor-default'} 
                        ${cellComponents.length > 0 ? `bg-${UI.getThemeColors().success.replace('500', '100').replace('400', '900')}` : ''}`,
                    onClick: () => cell && cell.id ? handleCellClick(cell) : handleCreateCell(r, c)
                },
                    // Cell content
                    React.createElement('div', { className: "flex flex-col h-full" },
                        // Nickname or coordinate display
                        isEditing ?
                            React.createElement('input', {
                                type: "text",
                                value: editCellNickname,
                                onChange: (e) => setEditCellNickname(e.target.value),
                                onBlur: handleSaveCellNickname,
                                onKeyDown: (e) => e.key === 'Enter' && handleSaveCellNickname(),
                                className: "w-full p-1 text-sm border border-gray-300 rounded",
                                autoFocus: true,
                                disabled: loading
                            }) :
                            React.createElement('div', { className: "font-medium text-sm" },
                                cell ? (cell.nickname || cell.coordinate) : coordinate, // Show coordinate if cell doesn't exist
                                cell && !cell.id && React.createElement('span', { className: `text-${UI.getThemeColors().textMuted} text-xs italic block` }, "Click to create"),
                                cell && cell.id && !isAvailable && React.createElement('span', { className: "text-red-500 text-xs italic block" }, "Unavailable")
                            ),

                        cellComponents.length > 0 && React.createElement('div', { className: `text-xs mt-1 text-${UI.getThemeColors().textSecondary}` },
                            `${cellComponents.length} component${cellComponents.length !== 1 ? 's' : ''}`
                        )
                    )
                );

                rowElements.push(cellElement);
            }

            gridElements.push(
                React.createElement('div', {
                    key: `row-${r}`,
                    className: "flex"
                }, rowElements)
            );
        }

        return gridElements;
    };

    // Selected cell details
    const selectedCell = drawerCells.find(cell => cell.id === selectedCellId);
    const selectedCellComponents = selectedCell ? getComponentsForCell(selectedCell.id) : [];

    return React.createElement('div', { className: "space-y-4" },
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
        
        // Header with back button
        React.createElement('div', { className: "flex justify-between items-center mb-4" },
            React.createElement('h2', { className: UI.typography.heading.h2 },
                `Drawer: ${drawer.name}`,
                drawer.description && React.createElement('span', { className: `ml-2 text-sm text-${UI.getThemeColors().textMuted} font-normal` }, `(${drawer.description})`)
            ),
            React.createElement('button', {
                onClick: onBackToDrawers,
                className: `px-3 py-1 bg-${UI.getThemeColors().secondary} text-${UI.getThemeColors().textSecondary} rounded flex items-center hover:bg-${UI.getThemeColors().secondaryHover}`,
                disabled: loading
            },
                React.createElement('svg', {
                    xmlns: "http://www.w3.org/2000/svg",
                    className: "h-4 w-4 mr-1",
                    fill: "none",
                    viewBox: "0 0 24 24",
                    stroke: "currentColor"
                },
                    React.createElement('path', {
                        strokeLinecap: "round",
                        strokeLinejoin: "round",
                        strokeWidth: 2,
                        d: "M10 19l-7-7m0 0l7-7m-7 7h18"
                    })
                ),
                "Back to Drawers"
            )
        ),

        // Location info
        React.createElement('div', { className: `bg-${UI.getThemeColors().background} p-3 rounded-lg border border-${UI.getThemeColors().border}` },
            React.createElement('div', { className: `text-sm text-${UI.getThemeColors().textSecondary}` },
                React.createElement('span', { className: "font-medium" }, "Location: "),
                location?.name || "Unknown Location"
            ),
            React.createElement('div', { className: `text-sm text-${UI.getThemeColors().textSecondary} mt-1` },
                React.createElement('span', { className: "font-medium" }, "Grid Size: "),
                `${rows} × ${cols}`
            ),
            React.createElement('div', { className: `text-sm text-${UI.getThemeColors().textSecondary} mt-1` },
                React.createElement('span', { className: "font-medium" }, "Total Components: "),
                components.filter(comp => comp.storageInfo && comp.storageInfo.drawerId === drawer.id).length
            )
        ),

        // Grid view with responsive container
        React.createElement('div', { className: `bg-${UI.getThemeColors().cardBackground} p-4 rounded-lg shadow border border-${UI.getThemeColors().border}` },
            React.createElement('h3', { className: `text-lg font-medium mb-4 text-${UI.getThemeColors().textSecondary}` }, "Drawer Grid"),
            // Instructions
            React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textSecondary} mb-4` },
                "Click on a cell to select it. Click on an empty coordinate to create a new cell. Cells with components are highlighted in green."
            ),
            // Grid container with scroll capabilities
            React.createElement('div', {
                className: "overflow-auto max-w-full",
                style: {
                    scrollbarWidth: 'thin',
                    scrollbarColor: '#cbd5e0 #edf2f7'
                }
            },
                // Inner grid container
                React.createElement('div', {
                    className: "inline-block"
                }, generateGrid())
            )
        ),

        // Selected cell details - Only show if a cell is selected
        selectedCell && React.createElement('div', null,
            React.createElement('div', { className: "flex space-x-2" },
                React.createElement('button', {
                    onClick: () => handleToggleAvailability(selectedCell.id),
                    className: `px-2 py-1 text-xs ${selectedCell.available !== false ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-green-500 hover:bg-green-600'} text-white rounded`,
                    title: selectedCell.available !== false ? "Mark as Unavailable" : "Mark as Available",
                    disabled: loading
                }, selectedCell.available !== false ? "Mark Unavailable" : "Mark Available"),

                React.createElement('button', {
                    onClick: () => handleEmptyCell(selectedCell.id),
                    className: "px-2 py-1 text-xs bg-orange-500 text-white rounded hover:bg-orange-600",
                    disabled: loading
                }, "Empty Cell"),

                React.createElement('button', {
                    onClick: () => handleEditCellNickname(selectedCell),
                    className: UI.buttons.small.info,
                    disabled: loading
                }, "Rename Cell"),

                React.createElement('button', {
                    onClick: () => handleDeleteCell(selectedCell.id),
                    className: UI.buttons.small.danger,
                    disabled: loading
                }, "Delete Cell")
            ),

            // Components in this cell
            React.createElement('h4', { className: `font-medium text-${UI.getThemeColors().textSecondary} mt-4 mb-2` },
                `Components in ${selectedCell.nickname || selectedCell.coordinate}`
            ),
            selectedCellComponents.length === 0 ?
                React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textMuted} italic` }, "No components in this cell.") :
                React.createElement('div', { className: "space-y-2 max-h-60 overflow-y-auto" },
                    selectedCellComponents.map(comp =>
                        React.createElement('div', {
                            key: comp.id,
                            className: `flex justify-between items-center p-2 bg-${UI.getThemeColors().background} rounded border border-${UI.getThemeColors().border}`
                        },
                            React.createElement('div', null,
                                React.createElement('div', { className: "font-medium" }, comp.name),
                                React.createElement('div', { className: `text-xs text-${UI.getThemeColors().textSecondary}` },
                                    `${comp.category} • Model/Type: ${comp.type || ""}`
                                )
                            ),
                            React.createElement('button', {
                                onClick: () => onEditComponent(comp),
                                className: UI.buttons.small.primary,
                                disabled: loading
                            }, "Edit")
                        )
                    )
                )
        )
    );
};

console.log("DrawerView component loaded with IndexedDB compatibility.");