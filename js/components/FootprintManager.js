// js/components/FootprintManager.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing component footprints - fully self-contained
 */
window.App.components.FootprintManager = ({
    footprints = [], // Array: List of footprint strings
    components = [], // Array: All components (to check usage)
    onUpdateFootprints, // Function(footprints): Update footprints in parent
    onUpdateComponents, // Function(components): Update components in parent
    onShowMessage // Function(message): Show success/error messages in parent
}) => {
    const { UI } = window.App.utils;
    const { useState } = React;

    // State for new footprint input
    const [newFootprint, setNewFootprint] = useState('');
    
    // State for editing
    const [editingFootprint, setEditingFootprint] = useState(null);
    const [editFootprintName, setEditFootprintName] = useState('');

    // Create keydown handler to prevent disallowed characters
    const handleKeyDown = window.App.utils.sanitize.createKeyDownHandler();

    // Create change handler for inputs with character filtering
    const createChangeHandler = (setter) => {
        return (e) => {
            const value = window.App.utils.sanitize.validateAllowedChars(e.target.value);
            setter(value);
        };
    };

    // Handle adding new footprint with sanitization
    const handleAddFootprint = () => {
        // Sanitize and validate
        const trimmed = window.App.utils.sanitize.value(newFootprint.trim());
        
        if (!trimmed) {
            onShowMessage('Footprint name cannot be empty.');
            return;
        }
        
        // Apply length limits
        const sanitizedFootprint = window.App.utils.sanitize.validateLength(
            trimmed, 
            window.App.utils.sanitize.LIMITS.FOOTPRINT
        );
        
        // Check for invalid characters
        if (!window.App.utils.sanitize.isValidString(sanitizedFootprint)) {
            const invalidChars = window.App.utils.sanitize.getInvalidChars(trimmed);
            onShowMessage(`Footprint name contains invalid characters: ${invalidChars.join(' ')}`);
            return;
        }
        
        if (footprints.includes(sanitizedFootprint)) {
            onShowMessage(`Footprint "${sanitizedFootprint}" already exists.`);
            return;
        }
        
        const updatedFootprints = [...footprints, sanitizedFootprint].sort();
        onUpdateFootprints(updatedFootprints);
        setNewFootprint('');
        onShowMessage(`Footprint "${sanitizedFootprint}" added.`);
    };

    // Start editing a footprint with sanitization
    const handleStartEdit = (footprint) => {
        // Sanitize the footprint before editing
        const sanitizedFootprint = window.App.utils.sanitize.value(footprint);
        setEditingFootprint(sanitizedFootprint);
        setEditFootprintName(sanitizedFootprint);
    };

    // Save edited footprint with sanitization
    const handleSaveEdit = () => {
        // Sanitize and validate
        const trimmed = window.App.utils.sanitize.value(editFootprintName.trim());
        
        if (!trimmed) {
            onShowMessage('Footprint name cannot be empty.');
            return;
        }
        
        // Apply length limits
        const sanitizedFootprint = window.App.utils.sanitize.validateLength(
            trimmed, 
            window.App.utils.sanitize.LIMITS.FOOTPRINT
        );
        
        // Check for invalid characters
        if (!window.App.utils.sanitize.isValidString(sanitizedFootprint)) {
            const invalidChars = window.App.utils.sanitize.getInvalidChars(trimmed);
            onShowMessage(`Footprint name contains invalid characters: ${invalidChars.join(' ')}`);
            return;
        }
        
        if (footprints.includes(sanitizedFootprint)) {
            onShowMessage(`Footprint "${sanitizedFootprint}" already exists.`);
            return;
        }
        
        // Update footprint list
        const updatedFootprints = footprints.map(fp =>
            fp === editingFootprint ? sanitizedFootprint : fp
        ).sort();
        
        onUpdateFootprints(updatedFootprints);
        
        // Update components using the old footprint
        const updatedComponents = components.map(comp =>
            comp.footprint === editingFootprint ? { ...comp, footprint: sanitizedFootprint } : comp
        );
        
        onUpdateComponents(updatedComponents);
        
        setEditingFootprint(null);
        setEditFootprintName('');
        onShowMessage(`Footprint "${editingFootprint}" renamed to "${sanitizedFootprint}".`);
    };

    // Cancel editing
    const handleCancelEdit = () => {
        setEditingFootprint(null);
        setEditFootprintName('');
    };

    // Handle deleting a footprint
    const handleDeleteFootprint = (footprintToDelete) => {
        // Sanitize the footprint to delete
        const sanitizedFootprint = window.App.utils.sanitize.value(footprintToDelete);
        
        // Check if any components are using this footprint
        const componentsUsingFootprint = components.filter(comp => comp.footprint === sanitizedFootprint);
        
        if (componentsUsingFootprint.length > 0) {
            const confirmMessage = `${componentsUsingFootprint.length} component(s) are using this footprint. Removing it will clear the footprint from these components. Continue?`;
            if (!window.confirm(confirmMessage)) {
                return;
            }
            
            // Clear footprint from components
            const updatedComponents = components.map(comp =>
                comp.footprint === sanitizedFootprint ? { ...comp, footprint: '' } : comp
            );
            
            onUpdateComponents(updatedComponents);
        }
        
        // Remove the footprint from the list
        const updatedFootprints = footprints.filter(fp => fp !== sanitizedFootprint);
        onUpdateFootprints(updatedFootprints);
        onShowMessage(`Footprint "${sanitizedFootprint}" deleted.`);
    };

    // Handle restoring default footprints
    const handleRestoreDefaultFootprints = () => {
        // Define the default footprints list (all pre-sanitized)
        const defaultFootprints = [
            "0603", "0805", "1206", "1210", "0402", "0201", "2512",
            "SOT-23", "SOT-223", "SOT-89", "SOT-143",
            "SOIC-8", "SOIC-16", "TSSOP-16", "TSSOP-20",
            "DIP-8", "DIP-14", "DIP-16", "DIP-20", "DIP-28",
            "QFP-32", "QFP-44", "QFP-64", "QFP-100",
            "QFN-16", "QFN-20", "QFN-24", "QFN-32",
            "TO-92", "TO-220", "TO-247", "TO-263", "TO-252"
        ];
        
        if (window.confirm('This will add common electronic component footprints to your list. Continue?')) {
            // Merge current footprints with defaults to avoid duplicates
            // All footprints are sanitized before storage
            const currentSanitized = footprints.map(fp => window.App.utils.sanitize.value(fp));
            const merged = [...new Set([...defaultFootprints, ...currentSanitized])].sort();
            onUpdateFootprints(merged);
            onShowMessage('Common footprints added to your list.');
        }
    };

    // Handle deleting all footprints
    const handleDeleteAllFootprints = () => {
        // Check which components have footprints
        const componentsUsingFootprints = components.filter(comp => comp.footprint && comp.footprint !== '');
        
        if (componentsUsingFootprints.length > 0) {
            const confirmMessage = `This will delete all footprints and clear the footprint from ${componentsUsingFootprints.length} component(s). Continue?`;
            if (!window.confirm(confirmMessage)) return;
            
            // Clear footprints from all components
            const updatedComponents = components.map(comp => 
                comp.footprint ? { ...comp, footprint: '' } : comp
            );
            onUpdateComponents(updatedComponents);
            onShowMessage(`All footprints deleted. Footprints cleared from ${componentsUsingFootprints.length} component(s).`);
        } else {
            if (!window.confirm('This will delete all footprints. Continue?')) return;
            onShowMessage('All footprints deleted.');
        }
        
        // Clear the footprints array
        onUpdateFootprints([]);
    };

    // Helper function to create a validation indicator
    const createValidationIndicator = (value, fieldName) => {
        if (!value) return null;
        
        const isValid = window.App.utils.sanitize.isValidString(value);
        
        if (!isValid) {
            return React.createElement('div', {
                className: `absolute right-8 top-1/2 transform -translate-y-1/2`,
                title: `${fieldName} contains invalid characters that will be removed`
            },
                React.createElement('span', {
                    className: "text-red-500 text-sm font-bold"
                }, "!")
            );
        }
        
        return null;
    };

    // Helper function to create a character counter
    const createCharCounter = (value, maxLength) => {
        const length = (value || '').length;
        const isNearLimit = length > maxLength * 0.8;
        
        return React.createElement('div', {
            className: `absolute bottom-1 right-2 text-xs ${
                isNearLimit ? 'text-orange-500' : `text-${UI.getThemeColors().textMuted}`
            }`
        }, `${length}/${maxLength}`);
    };

    return (
        React.createElement('div', { className: "space-y-4" }, // Reduced spacing from space-y-6
            // Add New Footprint Section - More compact
            React.createElement('div', { className: `p-3 ${UI.colors.background.alt} ${UI.utils.rounded}` }, // Reduced padding from p-4
                React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Add New Footprint"), // Added margin-bottom
                React.createElement('div', { className: "flex gap-2 relative" }, // Reduced gap from gap-3
                    React.createElement('div', { className: "flex-grow relative" },
                        React.createElement('input', {
                            type: "text",
                            value: newFootprint,
                            onChange: createChangeHandler(setNewFootprint),
                            onKeyDown: handleKeyDown,
                            className: UI.forms.input + " flex-grow pr-12",
                            placeholder: "Enter footprint name...",
                            maxLength: window.App.utils.sanitize.LIMITS.FOOTPRINT,
                            pattern: "[A-Za-z0-9,.\-_ ]*",
                            onKeyDown: (e) => {
                                handleKeyDown(e);
                                if (e.key === 'Enter') handleAddFootprint();
                            }
                        }),
                        createCharCounter(newFootprint, window.App.utils.sanitize.LIMITS.FOOTPRINT),
                        createValidationIndicator(newFootprint, "Footprint")
                    ),
                    React.createElement('button', {
                        onClick: handleAddFootprint,
                        className: UI.buttons.primary + " px-3 py-2", // Adjusted button padding
                        disabled: !newFootprint.trim()
                    }, "Add")
                ),
                React.createElement('p', { className: UI.forms.hint },
                    "Footprint name (A-Z a-z 0-9 . , - _ space @ /) - Max 32 characters"
                )
            ),

            // Footprints Table - More compact
            React.createElement('div', { className: "overflow-x-auto" },
                React.createElement('table', { className: UI.tables.container },
                    React.createElement('thead', { className: UI.tables.header.row },
                        React.createElement('tr', null,
                            React.createElement('th', { className: UI.tables.header.cell }, "Footprint Name"),
                            React.createElement('th', { className: UI.tables.header.cell }, "Component Count"), // NEW: Added count column
                            React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                        )
                    ),
                    React.createElement('tbody', { className: `divide-y divide-${UI.getThemeColors().border}` },
                        footprints.length === 0 ?
                            React.createElement('tr', null,
                                React.createElement('td', { colSpan: "3", className: "py-3 px-3 text-center text-gray-500 italic" }, // Reduced padding and adjusted colspan
                                    "No footprints defined."
                                )
                            ) :
                            footprints.sort().map(footprint => {
                                // Count components using this footprint
                                const componentCount = components.filter(comp => comp.footprint === footprint).length;
                                
                                return React.createElement('tr', { key: footprint, className: UI.tables.body.row },
                                    // Footprint Name (editable)
                                    React.createElement('td', { className: UI.tables.body.cell + " py-2 relative" }, // Reduced vertical padding
                                        editingFootprint === footprint ?
                                            React.createElement('div', { className: "relative" },
                                                React.createElement('input', {
                                                    type: "text",
                                                    value: editFootprintName,
                                                    onChange: createChangeHandler(setEditFootprintName),
                                                    onKeyDown: handleKeyDown,
                                                    className: UI.forms.input + " py-1 pr-12", // Smaller input height
                                                    autoFocus: true,
                                                    maxLength: window.App.utils.sanitize.LIMITS.FOOTPRINT,
                                                    pattern: "[A-Za-z0-9,.\-_ ]*",
                                                    onKeyDown: (e) => {
                                                        handleKeyDown(e);
                                                        if (e.key === 'Enter') handleSaveEdit();
                                                    }
                                                }),
                                                createCharCounter(editFootprintName, window.App.utils.sanitize.LIMITS.FOOTPRINT),
                                                createValidationIndicator(editFootprintName, "Footprint")
                                            ) :
                                            React.createElement('span', null, footprint)
                                    ),
                                    // Component Count column
                                    React.createElement('td', { className: `${UI.tables.body.cell} py-2 text-center` },
                                        componentCount
                                    ),
                                    // Actions
                                    React.createElement('td', { className: UI.tables.body.cellAction + " py-2" }, // Reduced vertical padding
                                        editingFootprint === footprint ?
                                            React.createElement('div', { className: "flex justify-center space-x-1" }, // Reduced space between buttons
                                                React.createElement('button', {
                                                    onClick: handleSaveEdit,
                                                    className: UI.buttons.small.success + " px-2 py-1 text-xs", // Smaller button
                                                    title: "Save"
                                                }, "Save"),
                                                React.createElement('button', {
                                                    onClick: handleCancelEdit,
                                                    className: UI.buttons.small.secondary + " px-2 py-1 text-xs", // Smaller button
                                                    title: "Cancel"
                                                }, "Cancel")
                                            ) :
                                            React.createElement('div', { className: "flex justify-center space-x-1" }, // Reduced space between buttons
                                                React.createElement('button', {
                                                    onClick: () => handleStartEdit(footprint),
                                                    className: UI.buttons.small.primary + " px-2 py-1 text-xs", // Smaller button
                                                    title: "Edit"
                                                }, "Edit"),
                                                React.createElement('button', {
                                                    onClick: () => handleDeleteFootprint(footprint),
                                                    className: UI.buttons.small.danger + " px-2 py-1 text-xs", // Smaller button
                                                    title: "Delete"
                                                }, "Delete")
                                            )
                                    )
                                );
                            })
                    )
                )
            ),

            // Restore Default and Delete All buttons - More compact
            React.createElement('div', { className: "flex gap-2" }, // Reduced gap from gap-3
                React.createElement('button', {
                    onClick: handleRestoreDefaultFootprints,
                    className: UI.buttons.secondary + " px-3 py-2 text-sm" // Smaller button
                }, 'Restore Default Footprints'),
                React.createElement('button', {
                    onClick: handleDeleteAllFootprints,
                    className: UI.buttons.danger + " px-3 py-2 text-sm" // Smaller button
                }, 'Delete All Footprints')
            )
        )
    );
};

console.log("FootprintManager loaded");