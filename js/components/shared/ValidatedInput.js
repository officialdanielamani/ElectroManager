// js/components/shared/ValidatedInput.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.components.shared = window.App.components.shared || {};

/**
 * ValidatedInput - A reusable input component with built-in validation and sanitization
 * Combines sanitize-utils functions with React UI components
 */
window.App.components.shared.ValidatedInput = ({
    // Core props
    name,
    value = '',
    onChange,
    
    // Input configuration
    type = 'text',
    placeholder = '',
    maxLength,
    required = false,
    disabled = false,
    readOnly = false,
    autoFocus = false,
    
    // Validation options
    fieldType, // 'componentName', 'category', 'locationName', etc.
    customPattern,
    
    // UI options  
    className,
    label,
    hint,
    showCharCounter = true,
    showValidation = true,
    
    // Numeric input options
    min,
    max,
    step,
    
    // Event handlers
    onBlur,
    onFocus,
    onKeyDown: customKeyDown,
    
    // Advanced options
    allowAllChars = false, // For URLs, parameters, etc.
    customValidation
}) => {
    // Get references to utilities - ensure they exist
    const { UI } = window.App.utils || {};
    const { sanitize } = window.App.utils || {};
    const { useState } = React;
    
    // Ensure sanitize exists
    if (!sanitize) {
        console.error('sanitize utils not available in ValidatedInput');
        return React.createElement('div', null, 'Error: sanitize utils not loaded');
    }
    
    // Internal state for validation feedback
    const [touched, setTouched] = useState(false);
    const [focused, setFocused] = useState(false);
    
    // Get appropriate validator and limit based on fieldType
    const getFieldConfig = () => {
        if (customValidation) return customValidation;
        
        // Debug logging
        //console.log('Getting field config for:', fieldType);
        //console.log('Sanitize object:', sanitize);
        //console.log('Sanitize.LIMITS:', sanitize.LIMITS);
        
        const configs = {
            componentName: { 
                validator: sanitize.componentName?.bind(sanitize), 
                limit: sanitize.LIMITS?.COMPONENT_NAME 
            },
            componentModel: { 
                validator: sanitize.componentModel?.bind(sanitize), 
                limit: sanitize.LIMITS?.COMPONENT_MODEL 
            },
            componentInfo: { 
                validator: sanitize.componentInfo?.bind(sanitize), 
                limit: sanitize.LIMITS?.COMPONENT_INFO 
            },
            category: { 
                validator: sanitize.category?.bind(sanitize), 
                limit: sanitize.LIMITS?.CATEGORY 
            },
            footprint: { 
                validator: sanitize.footprint?.bind(sanitize), 
                limit: sanitize.LIMITS?.FOOTPRINT 
            },
            locationName: { 
                validator: sanitize.locationName?.bind(sanitize), 
                limit: sanitize.LIMITS?.LOCATION_NAME 
            },
            locationDescription: { 
                validator: sanitize.locationDescription?.bind(sanitize), 
                limit: sanitize.LIMITS?.LOCATION_DESCRIPTION 
            },
            drawerName: { 
                validator: sanitize.drawerName?.bind(sanitize), 
                limit: sanitize.LIMITS?.DRAWER_NAME 
            },
            drawerDescription: { 
                validator: sanitize.drawerDescription?.bind(sanitize), 
                limit: sanitize.LIMITS?.DRAWER_DESCRIPTION 
            },
            cellNickname: { 
                validator: sanitize.cellNickname?.bind(sanitize), 
                limit: sanitize.LIMITS?.CELL_NICKNAME 
            }
        };
        
        // Check if the fieldType exists in configs
        if (fieldType && configs[fieldType]) {
            const config = configs[fieldType];
            // Ensure both validator and limit exist
            if (config.validator && config.limit !== undefined) {
                return config;
            }
        }
        
        // Default fallback
        return { 
            validator: sanitize.value?.bind(sanitize), 
            limit: maxLength || 50 
        };
    };
    
    const fieldConfig = getFieldConfig();
    const effectiveMaxLength = maxLength || fieldConfig.limit;
    
    // Create sanitized change handler
    const handleChange = (e) => {
        if (readOnly || disabled) return;
        
        let newValue = e.target.value;
        
        // Debug logging
        /*
        console.log('Handle change:', {
            fieldType,
            value: newValue,
            fieldConfig,
            sanitize: !!sanitize,
            limits: sanitize?.LIMITS
        });
        */
        
        // Apply appropriate sanitization
        if (!allowAllChars) {
            if (type === 'number') {
                // For number inputs, allow numbers and decimal point
                newValue = newValue.replace(/[^0-9.-]/g, '');
            } else {
                // For text inputs, validate allowed characters
                if (sanitize && sanitize.validateAllowedChars) {
                    newValue = sanitize.validateAllowedChars(newValue);
                }
            }
        } else {
            // For special fields like URLs, just use basic sanitization
            if (sanitize && sanitize.value) {
                newValue = sanitize.value(newValue);
            }
        }
        
        // Apply field-specific validation if available
        if (fieldConfig.validator && !allowAllChars) {
            try {
                newValue = fieldConfig.validator(newValue);
            } catch (error) {
                console.error('Error in field validator:', error);
                console.error('Field config:', fieldConfig);
                console.error('Sanitize object:', sanitize);
                
                // Fallback to basic validation if field validator fails
                if (sanitize && sanitize.validateLength) {
                    newValue = sanitize.validateLength(newValue, effectiveMaxLength);
                }
            }
        }
        
        // Enforce length limit
        if (effectiveMaxLength && newValue.length > effectiveMaxLength) {
            newValue = newValue.substring(0, effectiveMaxLength);
        }
        
        onChange(newValue);
    };

    // Create keydown handler
    const handleKeyDown = (e) => {
        // Call custom keydown handler if provided
        if (customKeyDown) {
            customKeyDown(e);
            if (e.defaultPrevented) return;
        }

        // Apply character restriction for text inputs
        if (!allowAllChars && type === 'text') {
            if (sanitize && sanitize.createKeyDownHandler) {
                const keyDownHandler = sanitize.createKeyDownHandler();
                keyDownHandler(e);
            }
        }
    };

    // Handle focus events
    const handleFocus = (e) => {
        setFocused(true);
        if (onFocus) onFocus(e);
    };

    const handleBlur = (e) => {
        setTouched(true);
        setFocused(false);
        if (onBlur) onBlur(e);
    };

    // Validation state
    const isValid = !showValidation || (sanitize && sanitize.isValidString ? sanitize.isValidString(value) : true);
    const showError = touched && !isValid;
    const currentLength = (value || '').length;
    const isNearLimit = effectiveMaxLength && currentLength > effectiveMaxLength * 0.8;

    // Generate classes
    const inputClasses = [
        className || (UI && UI.forms ? UI.forms.input : 'w-full p-2 border border-gray-300 rounded'),
        showError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : '',
        readOnly ? 'cursor-not-allowed opacity-60' : '',
        disabled ? 'cursor-not-allowed opacity-40' : ''
    ].filter(Boolean).join(' ');

    // Fallback UI if UI constants aren't available
    const fallbackUI = {
        forms: {
            label: "block mb-1 text-sm font-medium text-gray-700",
            hint: "text-xs text-gray-500 mt-1",
            error: "text-red-500 text-xs mt-1"
        },
        getThemeColors: () => ({
            textMuted: 'gray-500'
        })
    };
    
    const uiToUse = UI || fallbackUI;

    // Render the component
    return React.createElement('div', { className: "relative" },
        // Label
        label && React.createElement('label', {
            htmlFor: name,
            className: `${uiToUse.forms.label} ${required ? "after:content-['*'] after:text-red-500 after:ml-1" : ''}`
        }, label),

        // Input container
        React.createElement('div', { className: "relative" },
            // Main input
            React.createElement('input', {
                id: name,
                name,
                type,
                value: value || '',
                onChange: handleChange,
                onKeyDown: handleKeyDown,
                onFocus: handleFocus,
                onBlur: handleBlur,
                placeholder,
                required,
                disabled,
                readOnly,
                autoFocus,
                min,
                max,
                step,
                maxLength: effectiveMaxLength,
                pattern: customPattern,
                className: inputClasses,
                'aria-invalid': showError,
                'aria-describedby': hint ? `${name}-hint` : undefined
            }),

            // Character counter
            showCharCounter && effectiveMaxLength && React.createElement('div', {
                className: `absolute bottom-1 right-2 text-xs pointer-events-none ${isNearLimit
                        ? 'text-orange-500'
                        : `text-${uiToUse.getThemeColors ? uiToUse.getThemeColors().textMuted : 'gray-500'}`
                    }`
            }, `${currentLength}/${effectiveMaxLength}`),

            // Validation indicator
            showValidation && !isValid && React.createElement('div', {
                className: 'absolute right-8 top-1/2 transform -translate-y-1/2 pointer-events-none',
                title: `${label || name} contains invalid characters that will be removed`
            },
                React.createElement('span', {
                    className: "text-red-500 text-sm font-bold"
                }, "!")
            )
        ),

        // Hint text
        hint && React.createElement('p', {
            id: `${name}-hint`,
            className: uiToUse.forms.hint
        }, hint),

        // Error message
        showError && React.createElement('p', {
            className: uiToUse.forms.error,
            role: "alert"
        }, `Please remove invalid characters from ${label || name}`)
    );
};

console.log("ValidatedInput loaded");