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
    const [showStorageSelector, setShowStorageSelector] = useState(false);
    const [selectedCells, setSelectedCells] = useState([]);
    const [selectedDrawerId, setSelectedDrawerId] = useState('');
    
    // Image preview state - simplified to just track loading and error states
    const [imagePreview, setImagePreview] = useState({
        loading: false,
        error: false
    });

    // Create keydown handler to prevent disallowed characters
    const handleKeyDown = window.App.utils.sanitize.createKeyDownHandler();

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
        
        // Set form data
        setFormData({
            ...componentData,
            locationInfo,
            storageInfo,
            favorite: componentData.favorite || false,
            bookmark: componentData.bookmark || false,
            star: componentData.star || false
        });
        
        // Set selected cells and drawer ID for UI state
        setSelectedCells(storageInfo.cells || []);
        setSelectedDrawerId(storageInfo.drawerId || '');
        
    }, [componentData]);

    // Handle changes in form inputs with character validation
    const handleChange = (e) => {
        if (isViewOnly) return; // Don't process changes in view-only mode
        
        const { name, value, type, checked } = e.target;
        // For checkbox inputs, use the 'checked' property as the value
        let newValue = type === 'checkbox' ? checked : value;
        
        // Filter for allowed characters if it's a string
        if (typeof newValue === 'string') {
            newValue = window.App.utils.sanitize.validateAllowedChars(newValue);
        }
        
        setFormData(prevData => ({
            ...prevData,
            [name]: newValue
        }));
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

    // Handle category selection, including the "Add new..." option
    const handleCategoryChange = (e) => {
        if (isViewOnly) return;
        
        // Sanitize and validate the value
        const value = window.App.utils.sanitize.validateAllowedChars(e.target.value);
        
        setFormData(prevData => ({
            ...prevData,
            category: value,
            // Reset custom category input if a standard category is selected
            customCategory: value === '__custom__' ? prevData.customCategory : ''
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

    // Handle footprint selection, including the "Custom footprint..." option
    const handleFootprintChange = (e) => {
        if (isViewOnly) return;
        
        // Sanitize and validate the value
        const value = window.App.utils.sanitize.validateAllowedChars(e.target.value);
        
        setFormData(prevData => ({
            ...prevData,
            footprint: value,
            // Reset custom footprint input if a standard footprint is selected
            customFootprint: value === '__custom__' ? prevData.customFootprint : ''
        }));
    };

    // Handle location changes with validation
    const handleLocationChange = (e) => {
        if (isViewOnly) return;
        
        const { name, value } = e.target;
        const sanitizedValue = window.App.utils.sanitize.validateAllowedChars(value);
        
        setFormData(prevData => ({
            ...prevData,
            locationInfo: {
                ...prevData.locationInfo,
                [name]: sanitizedValue
            }
        }));
    };

    // Handle storage location changes (drawer assignment) with validation
    const handleStorageLocationChange = (e) => {
        if (isViewOnly) return;
        
        const { name, value } = e.target;
        const sanitizedValue = window.App.utils.sanitize.validateAllowedChars(value);

        // Clear drawer and cells if location changes
        if (name === 'locationId' && sanitizedValue !== formData.storageInfo?.locationId) {
            setSelectedDrawerId('');
            setSelectedCells([]);

            setFormData(prevData => ({
                ...prevData,
                storageInfo: {
                    locationId: sanitizedValue,
                    drawerId: '',
                    cells: []
                }
            }));
        } else {
            setFormData(prevData => ({
                ...prevData,
                storageInfo: {
                    ...prevData.storageInfo,
                    [name]: sanitizedValue
                }
            }));
        }
    };

    // Handle drawer selection with validation
    const handleDrawerChange = (e) => {
        if (isViewOnly) return;
        
        const drawerId = window.App.utils.sanitize.validateAllowedChars(e.target.value);
        setSelectedDrawerId(drawerId);

        // Clear selected cells when drawer changes
        setSelectedCells([]);

        setFormData(prevData => ({
            ...prevData,
            storageInfo: {
                ...prevData.storageInfo,
                drawerId: drawerId,
                cells: []
            }
        }));
    };

    // Handle cell selection/deselection
    const handleCellToggle = (cellId) => {
        if (isViewOnly) return;
        
        // Sanitize the cell ID
        const sanitizedCellId = window.App.utils.sanitize.validateAllowedChars(cellId);
        
        // Find the cell from filtered cells
        const cell = filteredCells.find(c => c.id === sanitizedCellId);

        // Safely check if cell is unavailable before proceeding
        if (!cell || cell.available === false) {
            return; // Don't toggle unavailable cells
        }

        let updatedCells;

        if (selectedCells.includes(sanitizedCellId)) {
            // Remove cell if already selected
            updatedCells = selectedCells.filter(id => id !== sanitizedCellId);
        } else {
            // Add cell if not already selected
            updatedCells = [...selectedCells, sanitizedCellId];
        }

        setSelectedCells(updatedCells);

        setFormData(prevData => ({
            ...prevData,
            storageInfo: {
                ...prevData.storageInfo,
                cells: updatedCells
            }
        }));
    };

    // Get filtered drawers using helper
    const filteredDrawers = formHelpers.getFilteredDrawers(
        formData.storageInfo?.locationId, 
        drawers
    );

    // Get filtered cells using helper
    const filteredCells = formHelpers.getFilteredCells(
        selectedDrawerId,
        cells
    );

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

    // Helper function to create a validation indicator
    const createValidationIndicator = (value, fieldName) => {
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
                        React.createElement('div', { className: "md:col-span-1 relative" },
                            React.createElement('label', { htmlFor: "comp-name", className: UI.forms.label }, 
                                "Name ", !isViewOnly && React.createElement('span', { className: UI.colors.danger.text }, "*")),
                            React.createElement('input', {
                                id: "comp-name",
                                name: "name",
                                type: "text",
                                className: UI.forms.input,
                                value: formData.name || '',
                                onChange: handleChange,
                                onKeyDown: handleKeyDown,
                                maxLength: window.App.utils.sanitize.LIMITS.COMPONENT_NAME,
                                pattern: "[A-Za-z0-9,.\-_ ]*",
                                required: !isViewOnly,
                                readOnly: isViewOnly
                            }),
                            React.createElement('p', { className: UI.forms.hint },
                                "Component Name . A-Z a-z 0-9 . , - _"
                            ),
                            !isViewOnly && createCharCounter(formData.name, window.App.utils.sanitize.LIMITS.COMPONENT_NAME),
                            !isViewOnly && createValidationIndicator(formData.name, "Name"),
                        ),
                        // Category Select/Input with validation
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { htmlFor: "comp-category", className: UI.forms.label }, 
                                "Category ", !isViewOnly && React.createElement('span', { className: UI.colors.danger.text }, "*")),
                            isViewOnly ?
                                React.createElement('input', {
                                    id: "comp-category",
                                    type: "text",
                                    className: UI.forms.input,
                                    value: formData.category || '',
                                    readOnly: true
                                }) :
                                React.createElement(React.Fragment, null,
                                    React.createElement('select', {
                                        id: "comp-category",
                                        name: "category",
                                        className: UI.forms.select,
                                        value: formData.category || '',
                                        onChange: handleCategoryChange,
                                        required: !isViewOnly,
                                        disabled: isViewOnly
                                    },
                                        React.createElement('option', { value: "" }, "-- Select category --"),
                                        (categories || []).sort().map(cat => React.createElement('option', { key: cat, value: cat }, cat)),
                                        React.createElement('option', { value: "__custom__" }, "Add new...")
                                    ),
                                    formData.category === '__custom__' && React.createElement('div', { className: "relative mt-2" },
                                        React.createElement('input', {
                                            name: "customCategory",
                                            type: "text",
                                            placeholder: "New category name",
                                            className: UI.forms.input,
                                            value: formData.customCategory || '',
                                            onChange: handleChange,
                                            onKeyDown: handleKeyDown,
                                            maxLength: window.App.utils.sanitize.LIMITS.CATEGORY,
                                            pattern: "[A-Za-z0-9,.\-_ ]*",
                                            required: formData.category === '__custom__'
                                        }),
                                        createCharCounter(formData.customCategory, window.App.utils.sanitize.LIMITS.CATEGORY),
                                        createValidationIndicator(formData.customCategory, "Category")
                                    ),
                                    React.createElement('p', { className: UI.forms.hint },
                                        "Component Category"
                                    ),
                                )
                        ),
                        // Type Input with validation and character counter
                        React.createElement('div', { className: "md:col-span-1 relative" },
                            React.createElement('label', { htmlFor: "comp-type", className: UI.forms.label }, "Type / Model"),
                            React.createElement('input', {
                                id: "comp-type",
                                name: "type",
                                type: "text",
                                className: UI.forms.input,
                                value: formData.type || '',
                                onChange: handleChange,
                                onKeyDown: handleKeyDown,
                                maxLength: window.App.utils.sanitize.LIMITS.COMPONENT_MODEL,
                                pattern: "[A-Za-z0-9,.\-_ ]*",
                                placeholder: "e.g., Resistor, LM7805",
                                readOnly: isViewOnly
                            }),
                            !isViewOnly && createCharCounter(formData.type, window.App.utils.sanitize.LIMITS.COMPONENT_MODEL),
                            !isViewOnly && createValidationIndicator(formData.type, "Type"),
                            React.createElement('p', { className: UI.forms.hint },
                                "Component Type/Model . A-Z a-z 0-9 . , - _"
                            ),
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

                        // Storage Location Section
                        React.createElement('div', { className: `md:col-span-2 border-t pt-4 mt-2 border-${UI.getThemeColors().border}` },
                            React.createElement('div', { className: "flex justify-between items-center" },
                                React.createElement('h3', { className: `text-md font-medium mb-3 text-${UI.getThemeColors().textSecondary}` }, 
                                    "Storage Location"),
                                !isViewOnly && React.createElement('button', {
                                    type: "button",
                                    className: `text-${UI.getThemeColors().primary} text-sm`,
                                    onClick: () => setShowStorageSelector(!showStorageSelector)
                                }, showStorageSelector ? "Hide Drawer Selector" : "Show Drawer Selector")
                            ),

                            // Basic Location Information
                            React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-3" },
                                // Location Dropdown
                                React.createElement('div', null,
                                    React.createElement('label', { htmlFor: "comp-location", className: UI.forms.label }, "Location"),
                                    isViewOnly ?
                                        React.createElement('div', { 
                                            className: `p-2 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
                                        }, formHelpers.getLocationName(formData.locationInfo?.locationId, locations) || "Not assigned") :
                                        React.createElement('select', {
                                            id: "comp-location",
                                            name: "locationId",
                                            className: UI.forms.select,
                                            value: formData.locationInfo?.locationId || '',
                                            onChange: handleLocationChange,
                                            disabled: isViewOnly
                                        },
                                            React.createElement('option', { value: "" }, "-- No location assigned --"),
                                            locations.map(loc => React.createElement('option', { key: loc.id, value: loc.id }, loc.name))
                                        )
                                ),
                                // Location Details with validation
                                React.createElement('div', { className: "relative" },
                                    React.createElement('label', { htmlFor: "comp-location-details", className: UI.forms.label }, 
                                        "Location Details (Optional)"),
                                    React.createElement('input', {
                                        id: "comp-location-details",
                                        name: "details",
                                        type: "text",
                                        className: UI.forms.input,
                                        value: formData.locationInfo?.details || '',
                                        onChange: handleLocationChange,
                                        onKeyDown: handleKeyDown,
                                        maxLength: window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION,
                                        pattern: "[A-Za-z0-9,.\-_ ]*",
                                        placeholder: "e.g., Shelf 3, Box A",
                                        readOnly: isViewOnly
                                    }),
                                    !isViewOnly && createCharCounter(formData.locationInfo?.details, window.App.utils.sanitize.LIMITS.LOCATION_DESCRIPTION),
                                    !isViewOnly && createValidationIndicator(formData.locationInfo?.details, "Location Details")
                                )
                            ),

                            // Drawer Storage Section (expandable)
                            (showStorageSelector || isViewOnly) && 
                                // Using the form-helpers to render the drawer selector
                                formHelpers.renderDrawerSelector({
                                    UI,
                                    storageInfo: formData.storageInfo || {},
                                    locations,
                                    filteredDrawers,
                                    selectedDrawerId,
                                    filteredCells,
                                    selectedCells,
                                    handleStorageLocationChange,
                                    handleDrawerChange,
                                    handleCellToggle,
                                    readOnly: isViewOnly
                                }),

                            React.createElement('p', { className: UI.forms.hint },
                                "Specify where this component is physically stored."
                            )
                        ),

                        // Footprint Select/Input with validation
                        React.createElement('div', { className: "md:col-span-1" },
                            React.createElement('label', { htmlFor: "comp-footprint", className: UI.forms.label }, "Footprint"),
                            isViewOnly ?
                                React.createElement('input', {
                                    id: "comp-footprint",
                                    type: "text",
                                    className: UI.forms.input,
                                    value: formData.footprint || '',
                                    readOnly: true
                                }) :
                                React.createElement(React.Fragment, null,
                                    React.createElement('select', {
                                        id: "comp-footprint",
                                        name: "footprint",
                                        className: UI.forms.select,
                                        value: formData.footprint || '',
                                        onChange: handleFootprintChange,
                                        disabled: isViewOnly
                                    },
                                        React.createElement('option', { value: "" }, "-- Select footprint --"),
                                        React.createElement('option', { value: "__custom__" }, "Custom footprint..."),
                                        (footprints || []).sort().map(fp => React.createElement('option', { key: fp, value: fp }, fp))
                                    ),
                                    formData.footprint === '__custom__' && React.createElement('div', { className: "relative mt-2" },
                                        React.createElement('input', {
                                            name: "customFootprint",
                                            type: "text",
                                            placeholder: "Enter custom footprint",
                                            className: UI.forms.input,
                                            value: formData.customFootprint || '',
                                            onChange: handleChange,
                                            onKeyDown: handleKeyDown,
                                            maxLength: window.App.utils.sanitize.LIMITS.FOOTPRINT,
                                            pattern: "[A-Za-z0-9,.\-_ ]*",
                                            required: formData.footprint === '__custom__'
                                        }),
                                        createCharCounter(formData.customFootprint, window.App.utils.sanitize.LIMITS.FOOTPRINT),
                                        createValidationIndicator(formData.customFootprint, "Footprint")
                                    )
                                )
                        ),
                        // Info Input with validation and character counter
                        React.createElement('div', { className: "md:col-span-2 relative" },
                            React.createElement('label', { htmlFor: "comp-info", className: UI.forms.label }, "Info"),
                            React.createElement('input', {
                                id: "comp-info",
                                name: "info",
                                type: "text",
                                className: UI.forms.input,
                                value: formData.info || '',
                                onChange: handleChange,
                                onKeyDown: handleKeyDown,
                                maxLength: window.App.utils.sanitize.LIMITS.COMPONENT_INFO,
                                pattern: "[A-Za-z0-9,.\-_ ]*",
                                placeholder: "e.g., Voltage regulation",
                                readOnly: isViewOnly
                            }),
                            !isViewOnly && createCharCounter(formData.info, window.App.utils.sanitize.LIMITS.COMPONENT_INFO),
                            !isViewOnly && createValidationIndicator(formData.info, "Info")
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
                                onChange: handleChange,
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
                                onChange: handleChange,
                                placeholder: "One per line:\nVoltage: 5V\nTolerance: 5%",
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
                                        onChange: handleChange,
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
                                        onChange: handleChange,
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
                                        onChange: handleChange,
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

console.log("ComponentForm component loaded with improved validation and character limits.");