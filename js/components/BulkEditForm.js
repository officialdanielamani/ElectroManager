// js/components/BulkEditForm.js - Fixed with unified Physical Storage Location system

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Bulk Edit Modal Form.
 * Allows editing multiple components at once with improved validation and shared components.
 */
window.App.components.BulkEditForm = ({
    // Props
    categories, // Array: List of available category strings
    commonFootprints, // Array: List of common footprint strings
    selectedCount, // Number: How many components are selected
    locations = [], // Array: List of location objects
    drawers = [], // Array: List of drawer objects  
    cells = [], // Array: List of cell objects
    onApply, // Function: Callback when apply button clicked, passes bulk edit data
    onCancel // Function: Callback when cancel button or close icon clicked
}) => {
    // Get UI constants and helpers
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;

    // Internal state for the bulk edit form fields
    const [bulkData, setBulkData] = useState({
        category: '',
        customCategory: '',
        type: '',
        quantity: '',
        quantityAction: 'set',
        price: '',
        priceAction: 'set',
        footprint: '',
        customFootprint: '',
        favorite: null,
        bookmark: null,
        star: null,
        // FIXED: Unified storage
        storageAction: 'keep', // 'keep', 'set', 'clear'
        storage: { locationId: '', details: '', drawerId: '', cells: [] }
    });

    // Handle form field changes
    const handleFieldChange = (field, value) => {
        setBulkData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    // Handle storage action change with proper data clearing
    const handleStorageActionChange = (action) => {
        setBulkData(prev => ({
            ...prev,
            storageAction: action,
            // Clear storage info when changing actions
            storage: { locationId: '', details: '', drawerId: '', cells: [] }
        }));
    };

    // FIXED: Handle storage info changes
    const handleStorageChange = (storage) => {
        console.log("BulkEditForm - Storage changed:", storage);
        setBulkData(prev => ({
            ...prev,
            storage: storage
        }));
    };

    // Handle boolean field changes (favorite, bookmark, star)
    const handleBooleanChange = (name, value) => {
        setBulkData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    // FIXED: Apply bulk edits function
    const applyBulkEditsToComponents = (components, selectedComponents, bulkEditData, categories) => {
        let categoryToApply = bulkEditData.category;
        let footprintToApply = bulkEditData.footprint;
        let newCategoryAdded = false;
        let newCategory = null;

        // Handle custom category from bulk edit
        if (bulkEditData.category === '__custom__' && bulkEditData.customCategory) {
            categoryToApply = bulkEditData.customCategory.trim();
            if (categoryToApply && !categories.includes(categoryToApply)) {
                newCategory = categoryToApply;
                newCategoryAdded = true;
            } else if (!categoryToApply) {
                categoryToApply = '';
            }
        }

        // Handle custom footprint from bulk edit
        if (bulkEditData.footprint === '__custom__' && bulkEditData.customFootprint) {
            footprintToApply = bulkEditData.customFootprint.trim();
            if (!footprintToApply) footprintToApply = '';
        } else if (bulkEditData.footprint === '__custom__') {
            footprintToApply = '';
        }

        // Apply changes to components
        const updatedComponents = components.map(comp => {
            // Apply changes only to selected components
            if (selectedComponents.includes(comp.id)) {
                const updates = {};

                // Apply Category (if specified and valid)
                if (categoryToApply && categoryToApply !== '__custom__') {
                    updates.category = categoryToApply;
                }

                // Apply Type (if specified)
                if (bulkEditData.type.trim()) {
                    updates.type = bulkEditData.type.trim();
                }

                // Apply Footprint (if specified and valid)
                if (footprintToApply && footprintToApply !== '__custom__') {
                    updates.footprint = footprintToApply;
                }

                // Apply Quantity Adjustment
                if (bulkEditData.quantity !== '' && !isNaN(bulkEditData.quantity)) {
                    const changeValue = parseInt(bulkEditData.quantity, 10) || 0;
                    const currentQuantity = Number(comp.quantity) || 0;
                    if (bulkEditData.quantityAction === 'set') {
                        updates.quantity = Math.max(0, changeValue);
                    } else if (bulkEditData.quantityAction === 'increment') {
                        updates.quantity = currentQuantity + changeValue;
                    } else if (bulkEditData.quantityAction === 'decrement') {
                        updates.quantity = Math.max(0, currentQuantity - changeValue);
                    }
                }

                // Apply Price Adjustment
                if (bulkEditData.price !== '' && !isNaN(bulkEditData.price)) {
                    const priceChangeValue = parseFloat(bulkEditData.price) || 0;
                    const currentPrice = Number(comp.price) || 0;
                    if (bulkEditData.priceAction === 'set') {
                        updates.price = Math.max(0, priceChangeValue);
                    } else if (bulkEditData.priceAction === 'increase') {
                        updates.price = Math.max(0, currentPrice + priceChangeValue);
                    } else if (bulkEditData.priceAction === 'decrease') {
                        updates.price = Math.max(0, currentPrice - priceChangeValue);
                    }
                }

                // Apply Favorite status (if defined)
                if (bulkEditData.favorite !== null) {
                    updates.favorite = bulkEditData.favorite;
                }

                // Apply Bookmark status (if defined)
                if (bulkEditData.bookmark !== null) {
                    updates.bookmark = bulkEditData.bookmark;
                }

                // Apply Star status (if defined)
                if (bulkEditData.star !== null) {
                    updates.star = bulkEditData.star;
                }

                // FIXED: Apply Storage Updates
                if (bulkEditData.storageAction === 'clear') {
                    updates.storage = { locationId: '', details: '', drawerId: '', cells: [] };
                } else if (bulkEditData.storageAction === 'set' && bulkEditData.storage.locationId) {
                    updates.storage = bulkEditData.storage;
                }

                // Return the component with applied updates
                return { ...comp, ...updates };
            }
            // Return unchanged component if not selected
            return comp;
        });

        return {
            updatedComponents,
            newCategory
        };
    };

    // Handle applying the changes with validation
    const handleApply = () => {
        // Check for any invalid characters across text fields
        const fieldsToCheck = {
            'Type/Model': bulkData.type || '',
            'Category': bulkData.customCategory || '',
            'Footprint': bulkData.customFootprint || ''
        };

        const invalidFieldChars = {};
        let hasInvalidChars = false;

        // Check each field for invalid characters
        for (const [fieldName, fieldValue] of Object.entries(fieldsToCheck)) {
            const invalidChars = window.App.utils.sanitize.getInvalidChars(fieldValue);
            if (invalidChars.length > 0) {
                invalidFieldChars[fieldName] = invalidChars;
                hasInvalidChars = true;
            }
        }

        if (hasInvalidChars) {
            // Format a warning message about invalid characters
            let warningMessage = "The following fields contain invalid characters that will be removed:\n\n";

            for (const [fieldName, chars] of Object.entries(invalidFieldChars)) {
                warningMessage += `${fieldName}: ${chars.join(' ')}\n`;
            }

            alert(warningMessage);

            // Auto-clean the data
            const cleanedData = { ...bulkData };
            if (cleanedData.type) cleanedData.type = window.App.utils.sanitize.validateAllowedChars(cleanedData.type);
            if (cleanedData.customCategory) cleanedData.customCategory = window.App.utils.sanitize.validateAllowedChars(cleanedData.customCategory);
            if (cleanedData.customFootprint) cleanedData.customFootprint = window.App.utils.sanitize.validateAllowedChars(cleanedData.customFootprint);

            // Update form with cleaned data
            setBulkData(cleanedData);
            return;
        }

        // Validate custom category if selected
        if (bulkData.category === '__custom__' && !bulkData.customCategory.trim()) {
            alert("New category name cannot be empty when 'Add new category' is selected.");
            return;
        }

        // Validate custom footprint if selected
        if (bulkData.footprint === '__custom__' && !bulkData.customFootprint.trim()) {
            alert("Custom footprint name cannot be empty when 'Custom footprint' is selected.");
            return;
        }

        // FIXED: Validate storage action selections
        if (bulkData.storageAction === 'set' && !bulkData.storage.locationId) {
            alert("Please select a storage location or choose a different storage action.");
            return;
        }

        // Apply sanitization to the entire bulk data object
        const sanitizedData = window.App.utils.sanitize.object(bulkData);
        onApply(sanitizedData);
    };

    // Debug logging
    useEffect(() => {
        console.log("BulkEditForm - Current bulkData:", bulkData);
    }, [bulkData]);

    // --- Main Render ---
    return (
        React.createElement('div', { className: `fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4 z-30` },
            React.createElement('div', { className: `bg-${UI.getThemeColors().cardBackground} rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col` },
                // Header (Fixed at top)
                React.createElement('div', { className: `p-6 pb-3 border-b border-${UI.getThemeColors().border} flex-shrink-0` },
                    React.createElement('div', { className: "flex justify-between items-center mb-4" },
                        React.createElement('h2', { className: `text-xl font-semibold text-${UI.getThemeColors().textPrimary}` },
                            `Bulk Edit ${selectedCount} Component(s)`),
                        React.createElement('button', {
                            onClick: onCancel,
                            className: `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().textSecondary}`,
                            title: "Close"
                        },
                            React.createElement('svg', {
                                xmlns: "http://www.w3.org/2000/svg",
                                className: "h-6 w-6",
                                fill: "none",
                                viewBox: "0 0 24 24",
                                stroke: "currentColor"
                            },
                                React.createElement('path', {
                                    strokeLinecap: "round",
                                    strokeLinejoin: "round",
                                    strokeWidth: 2,
                                    d: "M6 18L18 6M6 6l12 12"
                                })
                            )
                        )
                    ),
                    React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textSecondary}` },
                        "Apply changes to selected components. Leave fields blank/unchanged to keep existing values.")
                ),

                // Scrollable Form Content
                React.createElement('div', { className: `p-6 pt-3 overflow-y-auto flex-grow` },
                    React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4" },

                        // === BASIC FIELDS SECTION ===
                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement('h3', { className: `text-lg font-medium mb-4 text-${UI.getThemeColors().textSecondary} border-b border-${UI.getThemeColors().border} pb-2` },
                                "Basic Component Fields")
                        ),

                        // Category with SelectWithCustom
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement(window.App.components.shared.SelectWithCustom, {
                                name: "category",
                                value: bulkData.category || '',
                                onChange: (value) => handleFieldChange('category', value),
                                options: categories,
                                fieldType: "category",
                                label: "Change Category To",
                                placeholder: "-- Keep existing category --",
                                customValue: bulkData.customCategory || '',
                                onCustomChange: (value) => handleFieldChange('customCategory', value),
                                customOption: { value: '__custom__', label: 'Add new category...' }
                            })
                        ),

                        // Type/Model with ValidatedInput
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement(window.App.components.shared.ValidatedInput, {
                                name: "type",
                                value: bulkData.type || '',
                                onChange: (value) => handleFieldChange('type', value),
                                fieldType: "componentModel",
                                label: "Change Type To",
                                placeholder: "Leave blank to keep existing type",
                                hint: "Leave blank to keep existing value"
                            })
                        ),

                        // Footprint with SelectWithCustom
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement(window.App.components.shared.SelectWithCustom, {
                                name: "footprint",
                                value: bulkData.footprint || '',
                                onChange: (value) => handleFieldChange('footprint', value),
                                options: commonFootprints,
                                fieldType: "footprint",
                                label: "Change Footprint To",
                                placeholder: "-- Keep existing footprint --",
                                customValue: bulkData.customFootprint || '',
                                onCustomChange: (value) => handleFieldChange('customFootprint', value),
                                customOption: { value: '__custom__', label: 'Custom footprint...' }
                            })
                        ),

                        // === QUANTITY AND PRICE SECTION ===
                        React.createElement('div', { className: "md:col-span-2 mt-6" },
                            React.createElement('h3', { className: `text-lg font-medium mb-4 text-${UI.getThemeColors().textSecondary} border-b border-${UI.getThemeColors().border} pb-2` },
                                "Quantity and Price Adjustments")
                        ),

                        // Quantity Adjustment
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { className: UI.forms.label }, "Adjust Quantity"),
                            React.createElement('div', { className: "flex space-x-2" },
                                React.createElement('select', {
                                    name: "quantityAction",
                                    className: UI.forms.select,
                                    value: bulkData.quantityAction,
                                    onChange: (e) => handleFieldChange('quantityAction', e.target.value)
                                },
                                    React.createElement('option', { value: "set" }, "Set quantity to"),
                                    React.createElement('option', { value: "increment" }, "Add quantity"),
                                    React.createElement('option', { value: "decrement" }, "Subtract quantity")
                                ),
                                React.createElement('input', {
                                    name: "quantity",
                                    type: "number",
                                    min: "0",
                                    placeholder: "Value",
                                    className: UI.forms.input,
                                    value: bulkData.quantity,
                                    onChange: (e) => handleFieldChange('quantity', parseInt(e.target.value, 10) || '')
                                })
                            ),
                            React.createElement('p', { className: UI.forms.hint },
                                "Leave value blank for no quantity change.")
                        ),

                        // Price Adjustment
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { className: UI.forms.label }, "Adjust Price"),
                            React.createElement('div', { className: "flex space-x-2" },
                                React.createElement('select', {
                                    name: "priceAction",
                                    className: UI.forms.select,
                                    value: bulkData.priceAction,
                                    onChange: (e) => handleFieldChange('priceAction', e.target.value)
                                },
                                    React.createElement('option', { value: "set" }, "Set price to"),
                                    React.createElement('option', { value: "increase" }, "Increase price by"),
                                    React.createElement('option', { value: "decrease" }, "Decrease price by")
                                ),
                                React.createElement('input', {
                                    name: "price",
                                    type: "number",
                                    min: "0",
                                    step: "0.01",
                                    placeholder: "Value",
                                    className: UI.forms.input,
                                    value: bulkData.price,
                                    onChange: (e) => handleFieldChange('price', parseFloat(e.target.value) || '')
                                })
                            ),
                            React.createElement('p', { className: UI.forms.hint },
                                "Leave value blank for no price change.")
                        ),

                        // === PHYSICAL STORAGE LOCATION SECTION ===
                        React.createElement('div', { className: "md:col-span-2 mt-6" },
                            React.createElement('h3', { className: `text-lg font-medium mb-4 text-${UI.getThemeColors().textSecondary} border-b border-${UI.getThemeColors().border} pb-2` },
                                "Physical Storage Location")
                        ),

                        React.createElement('div', { className: "md:col-span-2" },
                            // Storage Action Selector
                            React.createElement('div', { className: "mb-4" },
                                React.createElement('label', { className: UI.forms.label }, "Storage Action"),
                                React.createElement('select', {
                                    name: "storageAction",
                                    className: UI.forms.select,
                                    value: bulkData.storageAction,
                                    onChange: (e) => handleStorageActionChange(e.target.value)
                                },
                                    React.createElement('option', { value: "keep" }, "Keep existing location"),
                                    React.createElement('option', { value: "set" }, "Set new storage location"),
                                    React.createElement('option', { value: "clear" }, "Clear all storage")
                                ),
                                React.createElement('p', { className: UI.forms.hint },
                                    "Choose how to update component storage: keep current, set new location, or clear all storage information."
                                )
                            ),

                            // FIXED: Show LocationSelector when action is 'set'
                            bulkData.storageAction === 'set' && React.createElement('div', { className: "mt-4" },
                                React.createElement(window.App.components.shared.LocationSelector, {
                                    storage: bulkData.storage,
                                    locations: locations,
                                    drawers: drawers,
                                    cells: cells,
                                    onStorageChange: handleStorageChange,
                                    showDrawerSelector: true,
                                    showLocationDetails: true,
                                    allowMultipleCells: true,
                                    showCellGrid: true,
                                    expandedByDefault: false,
                                    hideToggle: true,
                                    label: "Bulk Storage Assignment"
                                })
                            ),

                            // Show Clear Confirmation for Clear Action
                            bulkData.storageAction === 'clear' && React.createElement('div', { className: `mt-4 p-3 bg-${UI.getThemeColors().warning.replace('500', '50').replace('400', '950')} border border-${UI.getThemeColors().warning.replace('500', '200').replace('400', '800')} rounded` },
                                React.createElement('div', { className: "flex items-center" },
                                    React.createElement('svg', {
                                        xmlns: "http://www.w3.org/2000/svg",
                                        className: `h-5 w-5 text-${UI.getThemeColors().warning} mr-2`,
                                        viewBox: "0 0 20 20",
                                        fill: "currentColor"
                                    },
                                        React.createElement('path', {
                                            fillRule: "evenodd",
                                            d: "M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z",
                                            clipRule: "evenodd"
                                        })
                                    ),
                                    React.createElement('span', { className: `text-${UI.getThemeColors().warning.replace('500', '800').replace('400', '300')} font-medium` },
                                        "This will remove all location and drawer information from selected components.")
                                )
                            )
                        ),

                        // === COMPONENT MARKS SECTION ===
                        React.createElement('div', { className: "md:col-span-2 mt-6" },
                            React.createElement('h3', { className: `text-lg font-medium mb-4 text-${UI.getThemeColors().textSecondary} border-b border-${UI.getThemeColors().border} pb-2` },
                                "Component Marks")
                        ),

                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-3 gap-4" },
                                // Favorite Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-red-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                fillRule: "evenodd",
                                                d: "M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z",
                                                clipRule: "evenodd"
                                            })
                                        ),
                                        "Favorite"
                                    ),
                                    React.createElement('select', {
                                        name: "favorite",
                                        className: UI.forms.select,
                                        value: bulkData.favorite === null ? '' : bulkData.favorite.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange("favorite", value === '' ? null : value === 'true');
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Mark as Favorite"),
                                        React.createElement('option', { value: "false" }, "Remove Favorite mark")
                                    )
                                ),

                                // Bookmark Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-blue-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                d: "M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
                                            })
                                        ),
                                        "Bookmark"
                                    ),
                                    React.createElement('select', {
                                        name: "bookmark",
                                        className: UI.forms.select,
                                        value: bulkData.bookmark === null ? '' : bulkData.bookmark.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange("bookmark", value === '' ? null : value === 'true');
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Add Bookmark"),
                                        React.createElement('option', { value: "false" }, "Remove Bookmark")
                                    )
                                ),

                                // Star Option
                                React.createElement('div', null,
                                    React.createElement('label', { className: `block mb-1 text-sm font-medium text-${UI.getThemeColors().textSecondary} flex items-center` },
                                        React.createElement('svg', {
                                            xmlns: "http://www.w3.org/2000/svg",
                                            className: "h-5 w-5 mr-1 text-yellow-500",
                                            viewBox: "0 0 20 20",
                                            fill: "currentColor"
                                        },
                                            React.createElement('path', {
                                                d: "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                                            })
                                        ),
                                        "Star"
                                    ),
                                    React.createElement('select', {
                                        name: "star",
                                        className: UI.forms.select,
                                        value: bulkData.star === null ? '' : bulkData.star.toString(),
                                        onChange: (e) => {
                                            const value = e.target.value;
                                            handleBooleanChange("star", value === '' ? null : value === 'true');
                                        }
                                    },
                                        React.createElement('option', { value: "" }, "-- No change --"),
                                        React.createElement('option', { value: "true" }, "Add Star"),
                                        React.createElement('option', { value: "false" }, "Remove Star")
                                    )
                                )
                            )
                        )
                    )
                ),

                // Action Buttons (Fixed at bottom)
                React.createElement('div', {
                    className: `flex justify-end space-x-3 p-4 border-t border-${UI.getThemeColors().border} bg-${UI.getThemeColors().background} rounded-b-lg flex-shrink-0`
                },
                    React.createElement('button', {
                        className: UI.buttons.secondary,
                        onClick: onCancel
                    }, "Cancel"),
                    React.createElement('button', {
                        className: UI.buttons.primary,
                        onClick: handleApply
                    }, "Apply Changes")
                )
            ) // End Modal Content
        ) // End Modal Backdrop
    );
};

console.log("BulkEditForm loaded");