// js/components/CategoryManager.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for managing component categories - fully self-contained
 */
window.App.components.CategoryManager = ({
    categories = [], // Array: List of category strings
    components = [], // Array: All components (to check usage)
    lowStockConfig = {}, // Object: Low stock thresholds { category: threshold }
    onUpdateCategories, // Function(categories): Update categories in parent
    onUpdateComponents, // Function(components): Update components in parent
    onUpdateLowStockConfig, // Function(config): Update low stock config in parent
    onShowMessage // Function(message): Show success/error messages in parent
}) => {
    const { UI } = window.App.utils;
    const { useState } = React;

    // State for new category input
    const [newCategory, setNewCategory] = useState('');
    
    // State for editing
    const [editingCategory, setEditingCategory] = useState(null);
    const [newCategoryName, setNewCategoryName] = useState('');

    // Create keydown handler to prevent disallowed characters
    const handleKeyDown = window.App.utils.sanitize.createKeyDownHandler();

    // Create change handler for inputs with character filtering
    const createChangeHandler = (setter) => {
        return (e) => {
            const value = window.App.utils.sanitize.validateAllowedChars(e.target.value);
            setter(value);
        };
    };

    // Handle adding new category with sanitization
    const handleAddNewCategory = () => {
        // Sanitize and validate
        const trimmedCategory = window.App.utils.sanitize.value(newCategory.trim());
        
        if (!trimmedCategory) {
            onShowMessage("Category name cannot be empty.");
            return;
        }
        
        // Apply length limits
        const sanitizedCategory = window.App.utils.sanitize.validateLength(
            trimmedCategory, 
            window.App.utils.sanitize.LIMITS.CATEGORY
        );
        
        // Check for invalid characters
        if (!window.App.utils.sanitize.isValidString(sanitizedCategory)) {
            const invalidChars = window.App.utils.sanitize.getInvalidChars(trimmedCategory);
            onShowMessage(`Category name contains invalid characters: ${invalidChars.join(' ')}`);
            return;
        }
        
        if (categories.includes(sanitizedCategory)) {
            onShowMessage(`Category "${sanitizedCategory}" already exists.`);
            return;
        }
        
        const updatedCategories = [...categories, sanitizedCategory].sort();
        onUpdateCategories(updatedCategories);
        setNewCategory('');
        onShowMessage(`Category "${sanitizedCategory}" added.`);
    };

    // Start editing category with sanitization
    const handleStartEditCategory = (category) => {
        // Sanitize the category before editing
        const sanitizedCategory = window.App.utils.sanitize.value(category);
        setEditingCategory(sanitizedCategory);
        setNewCategoryName(sanitizedCategory);
    };

    // Save edited category name with sanitization
    const handleSaveCategory = () => {
        // Sanitize and validate
        const trimmedNewName = window.App.utils.sanitize.value(newCategoryName.trim());
        
        // Validate
        if (!trimmedNewName) {
            onShowMessage("Category name cannot be empty.");
            return;
        }
        
        // Apply length limits
        const sanitizedCategory = window.App.utils.sanitize.validateLength(
            trimmedNewName, 
            window.App.utils.sanitize.LIMITS.CATEGORY
        );
        
        // Check for invalid characters
        if (!window.App.utils.sanitize.isValidString(sanitizedCategory)) {
            const invalidChars = window.App.utils.sanitize.getInvalidChars(trimmedNewName);
            onShowMessage(`Category name contains invalid characters: ${invalidChars.join(' ')}`);
            return;
        }
        
        if (sanitizedCategory === editingCategory) {
            // No change, just cancel
            setEditingCategory(null);
            setNewCategoryName('');
            return;
        }
        
        if (categories.includes(sanitizedCategory)) {
            onShowMessage(`Category "${sanitizedCategory}" already exists.`);
            return;
        }
        
        // Update category list
        const updatedCategories = categories.map(cat =>
            cat === editingCategory ? sanitizedCategory : cat
        ).sort();
        
        onUpdateCategories(updatedCategories);
        
        // Update components using the old category name
        const updatedComponents = components.map(comp =>
            comp.category === editingCategory ? { ...comp, category: sanitizedCategory } : comp
        );
        
        onUpdateComponents(updatedComponents);
        
        // Update low stock config if the category existed there
        if (lowStockConfig.hasOwnProperty(editingCategory)) {
            const newConfig = { ...lowStockConfig };
            newConfig[sanitizedCategory] = newConfig[editingCategory];
            delete newConfig[editingCategory];
            onUpdateLowStockConfig(newConfig);
        }
        
        setEditingCategory(null);
        setNewCategoryName('');
        onShowMessage(`Category "${editingCategory}" renamed to "${sanitizedCategory}".`);
    };

    // Cancel category editing
    const handleCancelCategoryEdit = () => {
        setEditingCategory(null);
        setNewCategoryName('');
    };

    // Delete a category with sanitization
    const handleDeleteCategory = (categoryToDelete) => {
        // Sanitize the category to delete
        const sanitizedCategory = window.App.utils.sanitize.value(categoryToDelete);
        const defaultCategoryName = "Default";
        
        // Ensure the default category exists if we need to move items to it
        let updatedCategories = categories;
        if (!categories.includes(defaultCategoryName)) {
            updatedCategories = [...categories, defaultCategoryName].sort();
            onUpdateCategories(updatedCategories);
        }
        
        // Remove the category from the list
        updatedCategories = updatedCategories.filter(cat => cat !== sanitizedCategory);
        onUpdateCategories(updatedCategories);
        
        // Reassign components from the deleted category to the default one
        const updatedComponents = components.map(comp =>
            comp.category === sanitizedCategory ? { ...comp, category: defaultCategoryName } : comp
        );
        
        onUpdateComponents(updatedComponents);
        
        // Remove the category from low stock config if it exists
        if (lowStockConfig.hasOwnProperty(sanitizedCategory)) {
            const newConfig = { ...lowStockConfig };
            delete newConfig[sanitizedCategory];
            onUpdateLowStockConfig(newConfig);
        }
        
        onShowMessage(`Category "${sanitizedCategory}" deleted. Components moved to "${defaultCategoryName}".`);
    };

    // Restore default categories
    const handleRestoreDefaultCategories = () => {
        // Pre-sanitized default categories (all following allowed character pattern)
        const defaultCategories = [
            "Resistors", "Capacitors", "Inductors", "Diodes", "Transistors",
            "ICs", "Connectors", "Switches", "LEDs", "Sensors", "Modules",
            "Passive", "Active", "Mechanical", "Power", "RF", "Analog", "Digital"
        ];
        
        if (window.confirm('This will add common electronic component categories to your list. Continue?')) {
            // Merge current categories with defaults to avoid duplicates
            // All categories are sanitized before storage
            const currentSanitized = categories.map(cat => window.App.utils.sanitize.value(cat));
            const merged = [...new Set([...currentSanitized, ...defaultCategories])].sort();
            onUpdateCategories(merged);
            onShowMessage('Common categories added to your list.');
        }
    };

    // Delete all categories
    const handleDeleteAllCategories = () => {
        const defaultCategoryName = "Default";
        const componentsCount = components.filter(comp => comp.category && comp.category !== defaultCategoryName).length;
        
        if (componentsCount > 0) {
            const confirmMessage = `This will delete all categories except "${defaultCategoryName}" and move ${componentsCount} component(s) to "${defaultCategoryName}" category. Continue?`;
            if (!window.confirm(confirmMessage)) return;
        } else {
            if (!window.confirm(`This will delete all categories except "${defaultCategoryName}". Continue?`)) return;
        }
        
        // Move all components to Default category
        const updatedComponents = components.map(comp => {
            if (comp.category && comp.category !== defaultCategoryName) {
                return { ...comp, category: defaultCategoryName };
            }
            return comp;
        });
        
        onUpdateComponents(updatedComponents);
        
        // Keep only Default category
        onUpdateCategories([defaultCategoryName]);
        
        // Clear low stock config
        onUpdateLowStockConfig({});
        
        onShowMessage(`All categories deleted except "${defaultCategoryName}". ${componentsCount} component(s) moved to "${defaultCategoryName}".`);
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
        React.createElement('div', { className: "space-y-4" }, // Reduced spacing for compact UI
            // Add New Category Section
            React.createElement('div', { className: `p-3 ${UI.colors.background.alt} ${UI.utils.rounded}` },
                React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Add New Category"),
                React.createElement('div', { className: "flex gap-2 relative" },
                    React.createElement('div', { className: "flex-grow relative" },
                        React.createElement('input', {
                            type: "text",
                            value: newCategory,
                            onChange: createChangeHandler(setNewCategory),
                            onKeyDown: handleKeyDown,
                            className: UI.forms.input + " flex-grow pr-12",
                            placeholder: "Enter category name...",
                            maxLength: window.App.utils.sanitize.LIMITS.CATEGORY,
                            pattern: "[A-Za-z0-9,.\-_ ]*",
                            onKeyDown: (e) => {
                                handleKeyDown(e);
                                if (e.key === 'Enter') handleAddNewCategory();
                            }
                        }),
                        createCharCounter(newCategory, window.App.utils.sanitize.LIMITS.CATEGORY),
                        createValidationIndicator(newCategory, "Category")
                    ),
                    React.createElement('button', {
                        onClick: handleAddNewCategory,
                        className: UI.buttons.primary + " px-3 py-2",
                        disabled: !newCategory.trim()
                    }, "Add")
                ),
                React.createElement('p', { className: UI.forms.hint },
                    "Category name (A-Z a-z 0-9 . , - _ space) - Max 32 characters"
                )
            ),

            // Categories Table
            React.createElement('div', { className: "overflow-x-auto" },
                React.createElement('table', { className: UI.tables.container },
                    React.createElement('thead', { className: UI.tables.header.row },
                        React.createElement('tr', null,
                            React.createElement('th', { className: UI.tables.header.cell }, "Category Name"),
                            React.createElement('th', { className: UI.tables.header.cell }, "Component Count"),
                            React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                        )
                    ),
                    React.createElement('tbody', { className: `divide-y divide-${UI.getThemeColors().border}` },
                        categories.length === 0 ?
                            React.createElement('tr', null,
                                React.createElement('td', { colSpan: "3", className: "py-3 px-3 text-center text-gray-500 italic" }, 
                                    "No categories defined."
                                )
                            ) :
                            categories.sort().map(category => {
                                const componentCount = components.filter(comp => comp.category === category).length;
                                return React.createElement('tr', { key: category, className: UI.tables.body.row },
                                    React.createElement('td', { className: UI.tables.body.cell + " py-2 relative" },
                                        editingCategory === category ?
                                            React.createElement('div', { className: "relative" },
                                                React.createElement('input', {
                                                    type: "text",
                                                    value: newCategoryName,
                                                    onChange: createChangeHandler(setNewCategoryName),
                                                    onKeyDown: handleKeyDown,
                                                    className: UI.forms.input + " py-1 pr-12",
                                                    autoFocus: true,
                                                    maxLength: window.App.utils.sanitize.LIMITS.CATEGORY,
                                                    pattern: "[A-Za-z0-9,.\-_ ]*",
                                                    onKeyDown: (e) => {
                                                        handleKeyDown(e);
                                                        if (e.key === 'Enter') handleSaveCategory();
                                                    }
                                                }),
                                                createCharCounter(newCategoryName, window.App.utils.sanitize.LIMITS.CATEGORY),
                                                createValidationIndicator(newCategoryName, "Category")
                                            ) :
                                            React.createElement('span', null, category)
                                    ),
                                    React.createElement('td', { className: `${UI.tables.body.cell} py-2 text-center` },
                                        componentCount
                                    ),
                                    React.createElement('td', { className: UI.tables.body.cellAction + " py-2" },
                                        editingCategory === category ?
                                            React.createElement('div', { className: "flex justify-center space-x-1" },
                                                React.createElement('button', {
                                                    onClick: handleSaveCategory,
                                                    className: UI.buttons.small.success + " px-2 py-1 text-xs",
                                                    title: "Save"
                                                }, "Save"),
                                                React.createElement('button', {
                                                    onClick: handleCancelCategoryEdit,
                                                    className: UI.buttons.small.secondary + " px-2 py-1 text-xs",
                                                    title: "Cancel"
                                                }, "Cancel")
                                            ) :
                                            React.createElement('div', { className: "flex justify-center space-x-1" },
                                                React.createElement('button', {
                                                    onClick: () => handleStartEditCategory(category),
                                                    className: UI.buttons.small.primary + " px-2 py-1 text-xs",
                                                    title: "Edit"
                                                }, "Edit"),
                                                React.createElement('button', {
                                                    onClick: () => handleDeleteCategory(category),
                                                    className: UI.buttons.small.danger + " px-2 py-1 text-xs",
                                                    title: "Delete",
                                                    disabled: category === 'Default'
                                                }, "Delete")
                                            )
                                    )
                                );
                            })
                    )
                )
            ),

            // Restore Default and Delete All buttons
            React.createElement('div', { className: "flex gap-2" },
                React.createElement('button', {
                    onClick: handleRestoreDefaultCategories,
                    className: UI.buttons.secondary + " px-3 py-2 text-sm"
                }, 'Restore Default Categories'),
                React.createElement('button', {
                    onClick: handleDeleteAllCategories,
                    className: UI.buttons.danger + " px-3 py-2 text-sm"
                }, 'Delete All Categories')
            )
        )
    );
};

console.log("CategoryManager loaded");