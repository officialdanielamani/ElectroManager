// js/components/shared/SelectWithCustom.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.components.shared = window.App.components.shared || {};

/**
 * SelectWithCustom - A reusable select component with "Add custom" option
 * Commonly used for categories, footprints, and other dropdown lists
 */
window.App.components.shared.SelectWithCustom = ({
    // Core props
    name,
    value = '',
    onChange,
    
    // Select options
    options = [], // Array of strings or objects with {value, label}
    placeholder = '-- Select option --',
    customOption = { value: '__custom__', label: 'Add new...' },
    
    // Custom input configuration
    customInputProps = {},
    customValue = '',
    onCustomChange,
    
    // Validation
    fieldType, // For automatic validation (e.g., 'category', 'footprint')
    required = false,
    
    // UI configuration
    label,
    hint,
    disabled = false,
    className,
    
    // Styling options
    showCharCounter = true,
    showValidation = true,
    
    // Event handlers
    onBlur,
    onFocus
}) => {
    const { UI } = window.App.utils;
    const { sanitize } = window.App.utils;
    const { useState } = React;
    
    // Track if custom option is selected
    const isCustomSelected = value === customOption.value;
    
    // Get field configuration for validation
    const getFieldConfig = () => {
        const configs = {
            category: { 
                validator: sanitize.category, 
                limit: sanitize.LIMITS.CATEGORY,
                hint: 'Category name (A-Z a-z 0-9 . , - _ space) - Max 32 chars'
            },
            footprint: { 
                validator: sanitize.footprint, 
                limit: sanitize.LIMITS.FOOTPRINT,
                hint: 'Footprint name (A-Z a-z 0-9 . , - _ space) - Max 32 chars'
            },
            type: { 
                validator: sanitize.componentModel, 
                limit: sanitize.LIMITS.COMPONENT_MODEL,
                hint: 'Type/Model (A-Z a-z 0-9 . , - _ space) - Max 128 chars'
            }
        };
        
        return configs[fieldType] || { 
            validator: sanitize.value, 
            limit: 50,
            hint: 'Enter custom value'
        };
    };
    
    const fieldConfig = getFieldConfig();
    
    // Normalize options to consistent format
    const normalizedOptions = options.map(option => 
        typeof option === 'string' 
            ? { value: option, label: option }
            : option
    );
    
    // Handle select change
    const handleSelectChange = (e) => {
        const newValue = e.target.value;
        
        // Reset custom input when switching away from custom
        if (value === customOption.value && newValue !== customOption.value && onCustomChange) {
            onCustomChange('');
        }
        
        onChange(newValue);
    };
    
    // Handle custom input change
    const handleCustomInputChange = (sanitizedValue) => {
        if (onCustomChange) {
            onCustomChange(sanitizedValue);
        }
    };
    
    // Generate select classes
    const selectClasses = [
        className || UI.forms.select,
        disabled ? 'cursor-not-allowed opacity-40' : ''
    ].filter(Boolean).join(' ');
    
    return React.createElement('div', { className: "relative" },
        // Label
        label && React.createElement('label', {
            htmlFor: name,
            className: `${UI.forms.label} ${required ? "after:content-['*'] after:text-red-500 after:ml-1" : ''}`
        }, label),
        
        // Select dropdown
        React.createElement('select', {
            id: name,
            name,
            value,
            onChange: handleSelectChange,
            onFocus,
            onBlur,
            required,
            disabled,
            className: selectClasses,
            'aria-describedby': hint ? `${name}-hint` : undefined
        },
            // Placeholder option
            React.createElement('option', { value: '' }, placeholder),
            
            // Regular options
            normalizedOptions.map(option => 
                React.createElement('option', {
                    key: option.value,
                    value: option.value
                }, option.label)
            ),
            
            // Custom option (if provided)
            customOption && React.createElement('option', {
                value: customOption.value
            }, customOption.label)
        ),
        
        // Custom input (shown when custom option is selected)
        isCustomSelected && React.createElement('div', { className: "mt-2" },
            React.createElement(window.App.components.shared.ValidatedInput, {
                name: `${name}_custom`,
                value: customValue,
                onChange: handleCustomInputChange,
                fieldType,
                placeholder: customInputProps.placeholder || `Enter custom ${fieldType || 'value'}...`,
                required: isCustomSelected && required,
                showCharCounter,
                showValidation,
                autoFocus: true,
                hint: customInputProps.hint || fieldConfig.hint,
                ...customInputProps
            })
        ),
        
        // Main hint (for the select itself)
        hint && !isCustomSelected && React.createElement('p', {
            id: `${name}-hint`,
            className: UI.forms.hint
        }, hint)
    );
};

console.log("SelectWithCustom component loaded with integration to ValidatedInput.");