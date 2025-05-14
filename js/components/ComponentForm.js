// js/components/ComponentForm.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for the Add/Edit Component Modal Form.
 * Uses React and JSX syntax - must be processed by Babel.
 */
window.App.components.ComponentForm = ({
    // Props expected by this component
    componentData, // Object: The component being edited, or initial state for new
    categories, // Array: List of available category strings
    footprints, // Array: List of available footprint strings 
    currencySymbol, // String: Currency symbol for price field
    onSave, // Function: Callback when the save button is clicked, passes the component data
    onCancel, // Function: Callback when the cancel button or close icon is clicked
    isEditMode, // Boolean: True if editing an existing component, false if adding new
    locations = [], //  Array: List of location
    drawers = [], //  Array: List of drawers
    cells = [],  //  Array: List of drawers cells
    isViewOnly = false, // Boolean: True if component should be in view-only mode
}) => {
    // Get UI constants and helpers
    const { UI } = window.App.utils;
    const { formHelpers } = window.App.utils;

    // Use React hooks for local form state management
    const { useState, useEffect } = React;

    // Internal state to manage form inputs, initialized from props
    const [formData, setFormData] = useState(componentData || {});
    
    // Add state for managing location/drawer mode
    const [storageMode, setStorageMode] = useState('location'); // 'location' or 'drawer'

    // Image preview state - simplified to just track loading and error states
    const [imagePreview, setImagePreview] = useState({
        loading: false,
        error: false
    });

    // Initialize with proper structure for missing fields
    useEffect(() => {
        if (!componentData) return;

        // Format storage info using helper
        const storageInfo = formHelpers.formatStorageInfo(componentData.storageInfo);

        // Format location info using helper
        const locationInfo = formHelpers.formatLocationInfo(componentData.locationInfo);

        // Handle legacy format - convert single cellId to array of cells
        if (componentData.storageInfo?.cellId &&
            !storageInfo.cells.includes(componentData.storageInfo.cellId)) {
            storageInfo.cells.push(componentData.storageInfo.cellId);
        }

        // Determine initial storage mode based on existing data
        let initialMode = 'location';
if (storageInfo.drawerId) {
    initialMode = 'drawer';
} else if (locationInfo.locationId) {
    initialMode = 'location';
}

        // Set form data
        setFormData({
            ...componentData,
            locationInfo,
            storageInfo,
            favorite: componentData.favorite || false,
            bookmark: componentData.bookmark || false,
            star: componentData.star || false
        });

        setStorageMode(initialMode);

    }, [componentData]);

    // Handle storage mode change
    const handleStorageModeChange = (mode) => {
    setStorageMode(mode);
    
    // Clear the opposite data based on mode selection
    if (mode === 'location') {
        // Clear drawer data but keep location data
        setFormData(prev => ({
            ...prev,
            storageInfo: { locationId: '', drawerId: '', cells: [] }
        }));
    } else if (mode === 'drawer') {
        // Clear location data but keep drawer data
        setFormData(prev => ({
            ...prev,
            locationInfo: { locationId: '', details: '' }
        }));
    }
};

    // Handle numeric field changes with proper conversion and validation
    const handleNumericChange = (e) => {
        if (isViewOnly) return;

        const { name, value } = e.target;

        // First validate for allowed characters
        const filteredValue = window.App.utils.sanitize.validateAllowedChars(value);

        // Then convert to appropriate numeric type
        const numericValue = name === 'price'
            ? parseFloat(filteredValue) || 0
            : parseInt(filteredValue, 10) || 0;

        setFormData(prevData => ({
            ...prevData,
            [name]: numericValue
        }));
    };

    // Handle image URL changes with validation
    const handleImageUrlChange = (e) => {
        if (isViewOnly) return;

        // Use normal value without character restriction since URLs can contain special chars
        const url = window.App.utils.sanitize.value(e.target.value);

        // Update form data
        setFormData(prevData => ({
            ...prevData,
            image: url
        }));

        // Reset preview state
        if (url) {
            setImagePreview({
                loading: true,
                error: false
            });
        } else {
            setImagePreview({
                loading: false,
                error: false
            });
        }
    };

    // Handle image load events
    const handleImageLoad = () => {
        setImagePreview({
            loading: false,
            error: false
        });
    };

    // Handle image error events
    const handleImageError = () => {
        setImagePreview({
            loading: false,
            error: true
        });
    };

    const handleParametersChange = (e) => {
        if (isViewOnly) return;

        // For parameters, we don't want to restrict characters as much
        const { name, value } = e.target;

        setFormData(prevData => ({
            ...prevData,
            [name]: value // Don't filter characters for parameters
        }));
    };

    const handleDatasheetsChange = (e) => {
        if (isViewOnly) return;

        // For datasheets URLs, allow all characters since URLs contain
        // special characters like ?, &, =, %, +, #, etc.
        const { name, value } = e.target;

        setFormData(prevData => ({
            ...prevData,
            [name]: value // Don't filter characters for URLs
        }));
    };

    const handleCheckboxChange = (e) => {
        if (isViewOnly) return;

        const { name, checked } = e.target;
        setFormData(prevData => ({
            ...prevData,
            [name]: checked
        }));
    };

    // Handle form submission with validation
    const handleSubmit = (e) => {
        e.preventDefault(); // Prevent default form submission

        if (!isViewOnly) {
            // Check for any invalid characters across all fields
            const fieldsToCheck = {
                'Name': formData.name || '',
                'Type/Model': formData.type || '',
                'Info': formData.info || '',
                'Category': formData.customCategory || '',
                'Footprint': formData.customFootprint || ''
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
                const cleanedData = { ...formData };
                if (cleanedData.name) cleanedData.name = window.App.utils.sanitize.validateAllowedChars(cleanedData.name);
                if (cleanedData.type) cleanedData.type = window.App.utils.sanitize.validateAllowedChars(cleanedData.type);
                if (cleanedData.info) cleanedData.info = window.App.utils.sanitize.validateAllowedChars(cleanedData.info);
                if (cleanedData.customCategory) cleanedData.customCategory = window.App.utils.sanitize.validateAllowedChars(cleanedData.customCategory);
                if (cleanedData.customFootprint) cleanedData.customFootprint = window.App.utils.sanitize.validateAllowedChars(cleanedData.customFootprint);

                // Update form with cleaned data
                setFormData(cleanedData);
            }

            // Final sanitization of all data
            const sanitizedData = window.App.utils.sanitize.component(formData);

            // Basic validation
            if (!sanitizedData.name || !sanitizedData.category) {
                alert("Component Name and Category are required.");
                return;
            }

            onSave(sanitizedData); // Pass the sanitized form data to the parent save handler
        }
    };

    // --- Render ---
    return (
        React.createElement('div', { className: UI.modals.backdrop },
            React.createElement('div', { className: UI.modals.container },
                // Header
                React.createElement('div', { className: UI.modals.header },
                    React.createElement('h2', { className: UI.typography.title },
                        isViewOnly ? 'View Component' : (isEditMode ? 'Edit Component' : 'Add New Component')),
                    React.createElement('button', {
                        onClick: onCancel,
                        className: `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().textSecondary}`,
                        title: "Close"
                    },
                        // Close Icon SVG
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
                // Form Body (Scrollable)
                React.createElement('form', {
                    id: 'component-form',
                    onSubmit: handleSubmit,
                    className: UI.modals.body
                },
                    React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-4" },
                        // Name Input with validation and character counter
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement(window.App.components.shared.ValidatedInput, {
                                name: "name",
                                value: formData.name || '',
                                onChange: (value) => setFormData(prev => ({ ...prev, name: value })),
                                fieldType: "componentName",
                                label: "Component Name",
                                required: !isViewOnly,
                                readOnly: isViewOnly
                            })
                        ),
                        // Category Select/Input with validation
                        React.createElement('div', { className: "md:col-span-1" },
                            isViewOnly ?
                                React.createElement(window.App.components.shared.ValidatedInput, {
                                    name: "category",
                                    value: formData.category || '',
                                    label: "Category",
                                    readOnly: true
                                }) :
                                React.createElement(window.App.components.shared.SelectWithCustom, {
                                    name: "category",
                                    value: formData.category || '',
                                    onChange: (value) => setFormData(prev => ({ ...prev, category: value })),
                                    options: categories,
                                    fieldType: "category",
                                    label: "Category",
                                    required: true,
                                    customValue: formData.customCategory || '',
                                    onCustomChange: (value) => setFormData(prev => ({ ...prev, customCategory: value })),
                                    customOption: { value: '__custom__', label: 'Add new...' }
                                })
                        ),
                        // Type Input with validation and character counter
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement(window.App.components.shared.ValidatedInput, {
                                name: "type",
                                value: formData.type || '',
                                onChange: (value) => setFormData(prev => ({ ...prev, type: value })),
                                fieldType: "componentModel",
                                label: "Type / Model",
                                placeholder: "e.g., Resistor, LM7805",
                                readOnly: isViewOnly,
                                hint: "Component Type/Model . A-Z a-z 0-9 . , - _"
                            })
                        ),

                        // Quantity Input
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { htmlFor: "comp-quantity", className: UI.forms.label }, "Quantity"),
                            React.createElement('input', {
                                id: "comp-quantity",
                                name: "quantity",
                                type: "number",
                                min: "0",
                                className: UI.forms.input,
                                value: formData.quantity || 0,
                                onChange: handleNumericChange,
                                readOnly: isViewOnly
                            })
                        ),
                        // Price Input
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { htmlFor: "comp-price", className: UI.forms.label },
                                `Price (${currencySymbol || '$'})`),
                            React.createElement('input', {
                                id: "comp-price",
                                name: "price",
                                type: "number",
                                min: "0",
                                step: "0.01",
                                className: UI.forms.input,
                                value: formData.price || 0,
                                onChange: handleNumericChange,
                                placeholder: "0.00",
                                readOnly: isViewOnly
                            })
                        ),

                        // Storage Location Section - UPDATED WITH MODE SELECTOR
                        React.createElement('div', { className: `md:col-span-2 border-t pt-4 mt-2 border-${UI.getThemeColors().border}` },
                            React.createElement('h3', { className: `text-lg font-medium mb-3 text-${UI.getThemeColors().textSecondary}` },
                                "Physical Storage Location"
                            ),
                            
                            // Storage Mode Selector (only show if not view-only)
                            !isViewOnly && React.createElement('div', { className: "mb-4" },
                                React.createElement('label', { className: UI.forms.label }, "Storage Assignment Type"),
                                React.createElement('div', { className: "flex space-x-2" },
    React.createElement('button', {
        type: "button",
        onClick: () => handleStorageModeChange('location'),
        className: `px-3 py-1 text-sm rounded ${storageMode === 'location' ? 
            UI.buttons.primary : UI.buttons.secondary}`
    }, "General Location"),
    React.createElement('button', {
        type: "button",
        onClick: () => handleStorageModeChange('drawer'),
        className: `px-3 py-1 text-sm rounded ${storageMode === 'drawer' ? 
            UI.buttons.primary : UI.buttons.secondary}`
    }, "Drawer Storage")
),
                                React.createElement('p', { className: UI.forms.hint },
    "Choose how to store this component: general location or specific drawer cells."
)
                            ),

                            // Location Selector (when mode is 'location' or 'both')
                            storageMode === 'location' && React.createElement('div', { className: "mb-4" },
                                React.createElement(window.App.components.shared.LocationSelector, {
                                    locationInfo: formData.locationInfo,
                                    storageInfo: { locationId: '', drawerId: '', cells: [] }, // Empty storage for location-only
                                    locations: locations,
                                    drawers: [],
                                    cells: [],
                                    onLocationChange: (locationInfo) => setFormData(prev => ({ ...prev, locationInfo })),
                                    onStorageChange: () => {}, // No-op for location-only mode
                                    readOnly: isViewOnly,
                                    showDrawerSelector: false, // Never show drawer selector in location mode
                                    showLocationDetails: true,
                                    allowMultipleCells: false,
                                    showCellGrid: false,
                                    expandedByDefault: false,
                                    hideToggle: true,
                                    label: "Physical Location"
                                })
                            ),

                            // Drawer Selector (when mode is 'drawer' or 'both')
                            storageMode === 'drawer' && React.createElement('div', null,
                                React.createElement(window.App.components.shared.LocationSelector, {
                                    locationInfo: { locationId: '', details: '' }, // Empty location for drawer-only
                                    storageInfo: formData.storageInfo,
                                    locations: locations,
                                    drawers: drawers,
                                    cells: cells,
                                    onLocationChange: () => {}, // No-op for drawer-only mode
                                    onStorageChange: (storageInfo) => setFormData(prev => ({ ...prev, storageInfo })),
                                    readOnly: isViewOnly,
                                    showDrawerSelector: true, // Always show drawer selector in drawer mode
                                    showLocationDetails: false, // Never show location details in drawer mode
                                    allowMultipleCells: true,
                                    showCellGrid: true,
                                    expandedByDefault: true, // Always expanded for drawer selection
                                    hideToggle: true,
                                    label: "Drawer Selector"
                                })
                            ),

                            React.createElement('p', { className: UI.forms.hint },
                                "Specify where this component is physically stored. Use general location for broad placement and drawer storage for precise cell-level organization."
                            )
                        ),

                        // Footprint Select/Input with validation
                        React.createElement('div', { className: "md:col-span-1" },
                            isViewOnly ?
                                React.createElement(window.App.components.shared.ValidatedInput, {
                                    name: "footprint",
                                    value: formData.footprint || '',
                                    label: "Footprint",
                                    readOnly: true
                                }) :
                                React.createElement(window.App.components.shared.SelectWithCustom, {
                                    name: "footprint",
                                    value: formData.footprint || '',
                                    onChange: (value) => setFormData(prev => ({ ...prev, footprint: value })),
                                    options: footprints,
                                    fieldType: "footprint",
                                    label: "Footprint",
                                    customValue: formData.customFootprint || '',
                                    onCustomChange: (value) => setFormData(prev => ({ ...prev, customFootprint: value })),
                                    customOption: { value: '__custom__', label: 'Custom footprint...' }
                                })
                        ),
                        // Info Input with validation and character counter
                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement(window.App.components.shared.ValidatedInput, {
                                name: "info",
                                value: formData.info || '',
                                onChange: (value) => setFormData(prev => ({ ...prev, info: value })),
                                fieldType: "componentInfo",
                                label: "Info",
                                placeholder: "e.g., Voltage regulation",
                                readOnly: isViewOnly
                            })
                        ),
                        // Datasheets Textarea
                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement('label', { htmlFor: "comp-datasheets", className: UI.forms.label }, "Datasheet URLs"),
                            React.createElement('textarea', {
                                id: "comp-datasheets",
                                name: "datasheets",
                                className: UI.forms.textarea,
                                rows: "3",
                                value: formData.datasheets || '',
                                onChange: handleDatasheetsChange, // Use the special handler
                                // No onKeyDown handler that would block special characters
                                placeholder: "One URL per line or comma-separated...",
                                readOnly: isViewOnly
                            }),
                            !isViewOnly && React.createElement('p', { className: UI.forms.hint },
                                "Enter full URLs (http:// or https://)."
                            )
                        ),
                        // Image URL Input + Preview
                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement('label', { htmlFor: "comp-image", className: UI.forms.label }, "Image URL"),
                            React.createElement('div', { className: "flex flex-col md:flex-row gap-4" },
                                React.createElement('div', { className: "flex-grow" },
                                    React.createElement('input', {
                                        id: "comp-image",
                                        name: "image",
                                        type: "text",
                                        className: UI.forms.input,
                                        value: formData.image || '',
                                        onChange: handleImageUrlChange,
                                        placeholder: "https://example.com/image.jpg",
                                        readOnly: isViewOnly
                                    }),
                                    !isViewOnly && React.createElement('p', { className: UI.forms.hint },
                                        "Optional direct link to image."
                                    )
                                ),
                                formData.image && React.createElement('div', {
                                    className: `md:w-40 h-40 border border-${UI.getThemeColors().border} rounded flex items-center justify-center bg-${UI.getThemeColors().background}`
                                },
                                    imagePreview.loading && React.createElement('div', {
                                        className: `text-sm text-${UI.getThemeColors().textMuted}`
                                    }, "Loading..."),
                                    !imagePreview.loading && imagePreview.error && React.createElement('div', {
                                        className: UI.colors.danger.text + " text-sm"
                                    }, "Invalid image"),
                                    !imagePreview.loading && !imagePreview.error && formData.image && React.createElement('img', {
                                        src: formData.image,
                                        alt: "Preview",
                                        className: "max-w-full max-h-full object-contain",
                                        onLoad: handleImageLoad,
                                        onError: handleImageError
                                    })
                                )
                            )
                        ),
                        // Parameters Textarea
                        React.createElement('div', { className: "md:col-span-2" },
                            React.createElement('label', { htmlFor: "comp-parameters", className: UI.forms.label },
                                "Additional Parameters"),
                            React.createElement('textarea', {
                                id: "comp-parameters",
                                name: "parameters",
                                className: UI.forms.textarea,
                                rows: "5",
                                value: formData.parameters || '',
                                onChange: handleParametersChange, // New handler
                                // No onKeyDown handler that would block special characters
                                placeholder: "One per line:\nVoltage: >5V\nTolerance: +- ~5%\nAmp: <3.2A",
                                readOnly: isViewOnly
                            }),
                            !isViewOnly && React.createElement('p', { className: UI.forms.hint },
                                "Format: \"Name: Value\"."
                            )
                        ),

                        // --- Favorite, Bookmark, Star Toggles ---
                        React.createElement('div', { className: `md:col-span-2 mt-4 border-t pt-4 border-${UI.getThemeColors().border}` },
                            React.createElement('h3', { className: `text-md font-medium mb-3 text-${UI.getThemeColors().textSecondary}` },
                                "Component Marks:"),
                            React.createElement('div', { className: "flex flex-wrap gap-6" },
                                // Favorite Toggle
                                React.createElement('label', {
                                    htmlFor: "comp-favorite",
                                    className: `flex items-center space-x-2 text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                },
                                    React.createElement('input', {
                                        id: "comp-favorite",
                                        name: "favorite",
                                        type: "checkbox",
                                        checked: formData.favorite || false,
                                        onChange: handleCheckboxChange,
                                        className: UI.forms.checkbox,
                                        disabled: isViewOnly
                                    }),
                                    React.createElement('span', { className: "flex items-center" },
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
                                    )
                                ),

                                // Bookmark Toggle
                                React.createElement('label', {
                                    htmlFor: "comp-bookmark",
                                    className: `flex items-center space-x-2 text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                },
                                    React.createElement('input', {
                                        id: "comp-bookmark",
                                        name: "bookmark",
                                        type: "checkbox",
                                        checked: formData.bookmark || false,
                                        onChange: handleCheckboxChange,
                                        className: UI.forms.checkbox,
                                        disabled: isViewOnly
                                    }),
                                    React.createElement('span', { className: "flex items-center" },
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
                                    )
                                ),

                                // Star Toggle
                                React.createElement('label', {
                                    htmlFor: "comp-star",
                                    className: `flex items-center space-x-2 text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                },
                                    React.createElement('input', {
                                        id: "comp-star",
                                        name: "star",
                                        type: "checkbox",
                                        checked: formData.star || false,
                                        onChange: handleCheckboxChange,
                                        className: UI.forms.checkbox,
                                        disabled: isViewOnly
                                    }),
                                    React.createElement('span', { className: "flex items-center" },
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
                                    )
                                )
                            )
                        )
                    )
                ),

                // Footer (Action Buttons)
                React.createElement('div', { className: UI.modals.footer },
                    React.createElement('button', {
                        type: "button",
                        className: UI.buttons.secondary,
                        onClick: onCancel
                    }, isViewOnly ? "Close" : "Cancel"),

                    // Only show save button in edit mode
                    !isViewOnly && React.createElement('button', {
                        type: "submit",
                        form: 'component-form',
                        formNoValidate: true,
                        className: UI.buttons.primary
                    }, isEditMode ? 'Save Changes' : 'Add Component')
                )
            )
        )
    );
}; // End ComponentForm

console.log("ComponentForm component loaded with separated location and drawer selector modes.");