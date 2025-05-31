// js/components/AdvancedFilters.js - Updated for better dark mode support

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * React Component for Advanced Filtering Options
 * Provides multi-select filters and range sliders for component filtering
 */
window.App.components.AdvancedFilters = ({
    // Props
    components = [], // Array: All component objects
    categories = [], // Array: List of category strings
    locations = [], // Array: List of location objects
    footprints = [], // Array: List of footprint strings
    viewMode, // String: 'table' or 'card'
    searchTerm = '',//String: Current search term

    // Filter states
    selectedCategories = [], // Array: Currently selected categories
    selectedTypes = [], // Array: Currently selected types  
    selectedMarks = [], // Array: Currently selected marks (favorite, bookmark, star)
    selectedLocations = [], // Array: Currently selected locations
    selectedFootprints = [], // Array: Currently selected footprints
    quantityRange, // Object: {min, max} for quantity filter
    priceRange, // Object: {min, max} for price filter
    itemsPerPage, // Number: Items to show per page
    onChangeViewMode, // Function(mode): Called to change view mode ('table'/'card')
    selectedApFilters = [], // Array: Currently applied AP filters
    onApFiltersChange, // Function(filters): Update AP filters

    // Callbacks
    onCategoriesChange, // Function(categories): Update selected categories
    onTypesChange, // Function(types): Update selected types
    onMarksChange, // Function(marks): Update selected marks
    onLocationsChange, // Function(locations): Update selected locations
    onFootprintsChange, // Function(footprints): Update selected footprints
    onQuantityRangeChange, // Function(range): Update quantity range
    onPriceRangeChange, // Function(range): Update price range
    onItemsPerPageChange, // Function(count): Update items per page
    onClearFilters, // Function: Clear all filters
    onChangeSearchTerm = () => { },
    onAddComponent, // Function: Called when 'Add Component' button clicked

    // State
    isExpanded, // Boolean: Whether the filter panel is expanded
    onToggleExpand, // Function: Toggle expanded state
}) => {

    // Get UI constants
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;

    // Extract unique types from components
    const allTypes = [...new Set(components
        .map(comp => comp.type)
        .filter(Boolean) // Remove empty types
    )].sort();

    // Handle mark types
    const markTypes = [
        { id: 'favorite', label: 'Favorite', icon: 'heart' },
        { id: 'bookmark', label: 'Bookmark', icon: 'bookmark' },
        { id: 'star', label: 'Star', icon: 'star' }
    ];

    // Get min/max values for range filters
    const [priceStats, setPriceStats] = useState({ min: 0, max: 100 });
    const [quantityStats, setQuantityStats] = useState({ min: 0, max: 100 });

    const [apSearchText, setApSearchText] = useState('');
    const [apCaseSensitive, setApCaseSensitive] = useState(false);
    const [apIgnoreWhitespace, setApIgnoreWhitespace] = useState(true);
    const [apPartialMatch, setApPartialMatch] = useState(true);

    // Items per page options
    const pageOptions = [8, 16, 24, 100];

    // Calculate price and quantity stats on component changes
    useEffect(() => {
        // Check if components exists and has items
        if (components && components.length > 0) {
            const prices = components.map(c => Number(c.price) || 0);
            const quantities = components.map(c => Number(c.quantity) || 0);

            // Ensure calculated min is at least 0
            const calculatedPriceMin = Math.min(...prices);
            const calculatedQuantityMin = Math.min(...quantities);

            // Set stats, ensuring min is never below 0
            setPriceStats({
                min: Math.max(0, calculatedPriceMin),
                max: Math.max(Math.max(0, calculatedPriceMin), Math.max(...prices) || 0) || 100
            });

            setQuantityStats({
                min: Math.max(0, calculatedQuantityMin),
                max: Math.max(Math.max(0, calculatedQuantityMin), Math.max(...quantities) || 0) || 100
            });
        } else {
            // Default stats if no components
            setPriceStats({ min: 0, max: 100 });
            setQuantityStats({ min: 0, max: 100 });
        }
    }, [components]);

    // Handler for checkbox group changes
    const handleCheckboxGroup = (currentSelected, item, onChange) => {
        if (!currentSelected) {
            onChange([item]);
        } else {
            const newSelected = currentSelected.includes(item)
                ? currentSelected.filter(i => i !== item) // Remove item
                : [...currentSelected, item]; // Add item

            onChange(newSelected);
        }
    };

    // Handler for "select all" in a category
    const handleSelectAll = (items, currentSelected, onChange) => {
        // If all are already selected, clear the selection
        if (items.length === currentSelected?.length) {
            onChange([]);
        } else {
            // Otherwise select all
            onChange([...items]);
        }
    };

    // Render a checkbox group with select all option and scrollable area
    const renderCheckboxGroup = (title, items, selectedItems, onChange) => {
        const isItemsArray = Array.isArray(items); // Check if it's an array
        const itemCount = isItemsArray ? items.length : 0; // Get length safely
        const showScroll = itemCount > 6; // Enable scroll view if more than 6 items

        // Calculate allSelected safely
        const allSelected = isItemsArray && itemCount === selectedItems?.length;

        return React.createElement('div', { className: "mb-4" },
            React.createElement('div', { className: "flex justify-between items-center mb-2" },
                React.createElement('h4', { className: UI.typography.sectionTitle }, title),
                // Select all checkbox
                itemCount === 0
                    ? React.createElement('p', { className: `text-${UI.getThemeColors().textMuted}` }, "No items available")
                    :
                    React.createElement('label', { className: `flex items-center text-xs cursor-pointer text-${UI.getThemeColors().textSecondary}` },
                        React.createElement('input', {
                            type: "checkbox",
                            className: UI.forms.checkbox + " mr-1",
                            checked: allSelected,
                            onChange: () => handleSelectAll(items, selectedItems, onChange)
                        }),
                        "Select all"
                    )
            ),
            // Checkbox list in scrollable container
            React.createElement('div', {
                className: `${showScroll ? 'max-h-48' : 'max-h-36'} overflow-y-auto px-1 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
            },
                items.length === 0
                    ? React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textMuted} p-2 italic` }, "No items available")
                    : React.createElement('div', { className: "py-1" },
                        // Showing items in a single column for better readability when there are many items
                        showScroll
                            ? items.map(item =>
                                React.createElement('div', { key: item, className: "mb-1" },
                                    React.createElement('label', {
                                        className: `flex items-center text-sm px-2 py-1 hover:bg-${UI.getThemeColors().background} rounded cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                    },
                                        React.createElement('input', {
                                            type: "checkbox",
                                            className: UI.forms.checkbox + " mr-2",
                                            checked: selectedItems?.includes(item) || false,
                                            onChange: () => handleCheckboxGroup(selectedItems, item, onChange)
                                        }),
                                        typeof item === 'string' ? item : item.label
                                    )
                                )
                            )
                            // For 6 or fewer items, keep the 2-column grid
                            : React.createElement('div', { className: "grid grid-cols-2 gap-1" },
                                items.map(item =>
                                    React.createElement('label', {
                                        key: item,
                                        className: `flex items-center text-sm px-1 py-0.5 hover:bg-${UI.getThemeColors().background} rounded cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                    },
                                        React.createElement('input', {
                                            type: "checkbox",
                                            className: UI.forms.checkbox + " mr-1",
                                            checked: selectedItems?.includes(item) || false,
                                            onChange: () => handleCheckboxGroup(selectedItems, item, onChange)
                                        }),
                                        typeof item === 'string' ? item : item.label
                                    )
                                )
                            )
                    )
            ),
            // Show count of items if there are many
            showScroll && React.createElement('div', {
                className: `text-xs text-${UI.getThemeColors().textMuted} mt-1 text-right`
            }, `${itemCount} items available`)
        );
    };

    // For use with many filter options - Add this function to your component
    const FilterCheckboxGroup = ({ title, items, selectedItems, onChange }) => {
        const [searchTerm, setSearchTerm] = useState('');
        const isItemsArray = Array.isArray(items);
        const itemCount = isItemsArray ? items.length : 0;
        const showSearch = itemCount > 4; // Show search if more than 4 items

        // Calculate if all visible items are selected
        const filteredItems = showSearch && searchTerm
            ? items.filter(item =>
                typeof item === 'string'
                    ? item.toLowerCase().includes(searchTerm.toLowerCase())
                    : (item.label || '').toLowerCase().includes(searchTerm.toLowerCase())
            )
            : items;

        const allSelected = filteredItems.length > 0 &&
            filteredItems.every(item => selectedItems?.includes(item));

        // Handle select all for filtered items
        const handleSelectAllFiltered = () => {
            if (allSelected) {
                // Remove all filtered items from selection
                onChange(selectedItems.filter(item => !filteredItems.includes(item)));
            } else {
                // Add all filtered items to selection, preserving existing selections
                const newSelected = [...(selectedItems || [])];
                filteredItems.forEach(item => {
                    if (!newSelected.includes(item)) {
                        newSelected.push(item);
                    }
                });
                onChange(newSelected);
            }
        };

        return React.createElement('div', { className: "mb-4" },
            // Title and controls
            React.createElement('div', { className: "flex justify-between items-center mb-2" },
                React.createElement('h4', { className: UI.typography.sectionTitle }, title),
                itemCount === 0
                    ? React.createElement('p', { className: `text-${UI.getThemeColors().textMuted}` }, "No items")
                    : React.createElement('label', {
                        className: `flex items-center text-xs cursor-pointer text-${UI.getThemeColors().textSecondary}`
                    },
                        React.createElement('input', {
                            type: "checkbox",
                            className: UI.forms.checkbox + " mr-1",
                            checked: allSelected && filteredItems.length > 0,
                            onChange: handleSelectAllFiltered,
                            disabled: filteredItems.length === 0
                        }),
                        searchTerm ? "Select filtered" : "Select all"
                    )
            ),

            // Search box (conditionally rendered)
            showSearch && React.createElement('div', { className: "mb-2" },
                React.createElement('input', {
                    type: "text",
                    value: searchTerm,
                    onChange: (e) => setSearchTerm(e.target.value),
                    placeholder: "Search...",
                    className: `w-full text-sm px-2 py-1 border border-${UI.getThemeColors().border} rounded`
                })
            ),

            // Checkbox list
            React.createElement('div', {
                className: `max-h-24 overflow-y-auto px-1 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground}`
            },
                filteredItems.length === 0
                    ? React.createElement('p', { className: `text-sm text-${UI.getThemeColors().textMuted} p-2 italic` },
                        searchTerm ? "No matches found" : "No items available"
                    )
                    : React.createElement('div', { className: "py-1" },
                        filteredItems.map(item => {
                            const label = typeof item === 'string' ? item : item.label;
                            return React.createElement('div', { key: item, className: "mb-1" },
                                React.createElement('label', {
                                    className: `flex items-center text-sm px-2 py-1 hover:bg-${UI.getThemeColors().background} rounded cursor-pointer text-${UI.getThemeColors().textSecondary}`
                                },
                                    React.createElement('input', {
                                        type: "checkbox",
                                        className: UI.forms.checkbox + " mr-2",
                                        checked: selectedItems?.includes(item) || false,
                                        onChange: () => {
                                            if (!selectedItems) {
                                                onChange([item]);
                                            } else {
                                                const newSelected = selectedItems.includes(item)
                                                    ? selectedItems.filter(i => i !== item)
                                                    : [...selectedItems, item];
                                                onChange(newSelected);
                                            }
                                        }
                                    }),
                                    // If search term exists, highlight the matching part
                                    searchTerm
                                        ? highlightMatch(label, searchTerm)
                                        : label
                                )
                            );
                        })
                    )
            ),

            // Item count
            showSearch && React.createElement('div', {
                className: `text-xs text-${UI.getThemeColors().textMuted} mt-1 flex justify-between`
            },
                React.createElement('span', null,
                    searchTerm
                        ? `${filteredItems.length} of ${itemCount} items shown`
                        : `${itemCount} items available`
                ),
                selectedItems?.length > 0 && React.createElement('span', null,
                    `${selectedItems.length} selected`
                )
            )
        );
    };

    // Helper function to highlight matched text
    const highlightMatch = (text, query) => {
        if (!query || !text) return text;

        // Escape special regex characters to prevent errors
        const escapeRegExp = (string) => {
            return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        };

        try {
            const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'gi'));
            return React.createElement('span', null,
                parts.map((part, index) => {
                    const isMatch = part.toLowerCase() === query.toLowerCase();
                    return isMatch
                        ? React.createElement('span', {
                            key: index,
                            className: `bg-${UI.getThemeColors().primary.replace('500', '100').replace('400', '900')} text-${UI.getThemeColors().primary.replace('500', '800').replace('400', '300')}`
                        }, part)
                        : part;
                })
            );
        } catch (e) {
            // Fallback if regex fails
            return text;
        }
    };

    const [exactMatchModes, setExactMatchModes] = useState({
        quantity: false,
        price: false
    });


    const renderRangeSlider = (title, range, stats, onChange) => {
        // Get current values with fallbacks
        const currentMin = range?.min ?? stats.min;
        const currentMax = range?.max ?? stats.max;

        // Determine which filter this is
        const filterKey = title.toLowerCase().includes('price') ? 'price' : 'quantity';
        const exactMatchMode = exactMatchModes[filterKey];

        // Handle min value change
        const handleMinChange = (value) => {
            const newMin = Number(value);
            if (exactMatchMode) {
                // In exact match mode, set both min and max to the same value
                onChange({ min: newMin, max: newMin });
            } else {
                // In range mode, only update min
                onChange({ min: newMin, max: currentMax });
            }
        };

        // Handle max value change (only active in range mode)
        const handleMaxChange = (value) => {
            const newMax = Number(value);
            onChange({ min: currentMin, max: newMax });
        };

        // Toggle between exact match and range modes
        const toggleExactMatch = (e) => {
            const isExact = e.target.checked;

            // Update the state for this specific filter
            setExactMatchModes(prev => ({
                ...prev,
                [filterKey]: isExact
            }));

            if (isExact) {
                // Switch to exact match - use min value for both
                onChange({ min: currentMin, max: currentMin });
            } else {
                // Switch to range mode - restore max to default or current
                onChange({ min: currentMin, max: stats.max });
            }
        };

        return React.createElement('div', { className: "mb-4" },
            React.createElement('h4', { className: UI.typography.sectionTitle + " mb-1" }, title),

            // Filter mode indicator
            React.createElement('div', { className: "flex justify-between items-center mb-2" },
                React.createElement('span', { className: `text-xs font-medium text-${UI.getThemeColors().primary}` },
                    exactMatchMode ? "Finding exact value" : "Finding in range"
                ),
                // Exact match toggle
                React.createElement('label', { className: `flex items-center text-xs cursor-pointer text-${UI.getThemeColors().textSecondary}` },
                    React.createElement('input', {
                        type: "checkbox",
                        className: UI.forms.checkbox + " mr-1",
                        checked: exactMatchMode,
                        onChange: toggleExactMatch
                    }),
                    "Exact value only"
                )
            ),

            // Inputs container
            React.createElement('div', { className: "grid grid-cols-2 gap-2" },
                // Min Input
                React.createElement('div', null,
                    React.createElement('label', { className: `text-xs block mb-0.5 text-${UI.getThemeColors().textSecondary}` },
                        exactMatchMode ? "Value" : "Minimum"
                    ),
                    React.createElement('input', {
                        type: "number",
                        min: 0,
                        step: title.toLowerCase().includes('price') ? "0.01" : "1",
                        value: currentMin,
                        onChange: (e) => handleMinChange(e.target.value),
                        className: UI.forms.input
                    })
                ),

                // Max Input (hidden or disabled in exact match mode)
                React.createElement('div', {
                    style: { visibility: exactMatchMode ? 'hidden' : 'visible' }
                },
                    React.createElement('label', { className: `text-xs block mb-0.5 text-${UI.getThemeColors().textSecondary}` }, "Maximum"),
                    React.createElement('input', {
                        type: "number",
                        min: 0,
                        step: title.toLowerCase().includes('price') ? "0.01" : "1",
                        value: currentMax,
                        onChange: (e) => handleMaxChange(e.target.value),
                        className: UI.forms.input
                    })
                )
            )
        );
    };


    const parseApSearchText = (text) => {
        if (!text.trim()) return [];

        const filters = [];
        const lines = text.split(/[;\n]/).filter(line => line.trim());

        for (const line of lines) {
            const colonIndex = line.indexOf(':');
            if (colonIndex > 0) {
                const key = line.substring(0, colonIndex).trim();
                const value = line.substring(colonIndex + 1).trim();

                if (key) { // Only require key, value can be empty
                    filters.push({
                        key,
                        value: value || '', // Empty string if no value provided
                        isKeyOnlyFilter: value === '' // Flag to indicate this is a "key exists" filter
                    });
                }
            }
        }

        return filters;
    };

    const handleApSearchAdd = () => {
        const newFilters = parseApSearchText(apSearchText);
        if (newFilters.length > 0) {
            const updatedFilters = [...selectedApFilters];

            newFilters.forEach(newFilter => {
                // Check if this key-value combination already exists
                const exists = updatedFilters.some(existing =>
                    existing.key === newFilter.key &&
                    existing.value === newFilter.value &&
                    existing.isKeyOnlyFilter === newFilter.isKeyOnlyFilter
                );

                if (!exists) {
                    updatedFilters.push({
                        ...newFilter,
                        caseSensitive: apCaseSensitive,
                        ignoreWhitespace: apIgnoreWhitespace,
                        partialMatch: apPartialMatch,
                        id: Date.now() + Math.random() // Simple unique ID
                    });
                }
            });

            onApFiltersChange(updatedFilters);
            setApSearchText(''); // Clear the input after adding
        }
    };

    const handleApFilterRemove = (filterId) => {
        const updatedFilters = selectedApFilters.filter(filter => filter.id !== filterId);
        onApFiltersChange(updatedFilters);
    };

    // Special render method for marks (with icons)
    const renderMarksCheckboxes = () => {
        return React.createElement('div', { className: "mb-4" },
            React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Filter by Marks"),
            React.createElement('div', { className: "grid grid-cols-3 gap-2" },
                markTypes.map(mark => {
                    const iconComponents = {
                        heart: React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 text-red-500 mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        }, React.createElement('path', {
                            fillRule: "evenodd",
                            d: "M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z",
                            clipRule: "evenodd"
                        })),
                        bookmark: React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 text-blue-500 mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        }, React.createElement('path', {
                            d: "M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
                        })),
                        star: React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 text-yellow-500 mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        }, React.createElement('path', {
                            d: "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                        }))
                    };

                    return React.createElement('label', {
                        key: mark.id,
                        className: `flex items-center bg-${UI.getThemeColors().cardBackground} px-2 py-1 border border-${UI.getThemeColors().border} rounded hover:bg-${UI.getThemeColors().background} cursor-pointer text-${UI.getThemeColors().textSecondary}`
                    },
                        React.createElement('input', {
                            type: "checkbox",
                            className: UI.forms.checkbox + " mr-1",
                            checked: selectedMarks?.includes(mark.id) || false,
                            onChange: () => handleCheckboxGroup(selectedMarks, mark.id, onMarksChange)
                        }),
                        iconComponents[mark.icon],
                        mark.label
                    );
                })
            )
        );
    };

    // Render page size selector
    const renderPageSizeSelector = () => {
        return React.createElement('div', { className: "mb-4" },
            React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Items per Page"),
            React.createElement('div', { className: "flex space-x-2" },
                pageOptions.map(option =>
                    React.createElement('button', {
                        key: option,
                        onClick: () => onItemsPerPageChange(option),
                        className: `px-3 py-1.5 text-sm border border-${UI.getThemeColors().border} rounded 
                            ${itemsPerPage === option ?
                                `bg-${UI.getThemeColors().primary} text-white` :
                                `bg-${UI.getThemeColors().cardBackground} text-${UI.getThemeColors().textSecondary} hover:bg-${UI.getThemeColors().background}`}`
                    }, option === 'all' ? 'All' : option)
                )
            )
        );
    };

    // Count active filters
    const getActiveFilterCount = () => {
        let count = 0;
        if (selectedCategories?.length) count++;
        if (selectedTypes?.length) count++;
        if (selectedMarks?.length) count++;
        if (selectedLocations?.length) count++;
        if (selectedFootprints?.length) count++;
        if (selectedApFilters?.length) count++; // Add this line

        // Count range filters only if they're not at min/max
        if (quantityRange && (
            quantityRange.min > quantityStats.min ||
            quantityRange.max < quantityStats.max
        )) count++;

        if (priceRange && (
            priceRange.min > priceStats.min ||
            priceRange.max < priceStats.max
        )) count++;

        return count;
    };

    const renderApParameterSearch = () => {
        return React.createElement('div', { className: "mb-4" },
            React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Additional Parameters Search"),

            // Search input area
            React.createElement('div', {
                className: `p-3 border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().cardBackground} mb-3`
            },
                // Input textarea
                React.createElement('textarea', {
                    value: apSearchText,
                    onChange: (e) => setApSearchText(e.target.value),
                    placeholder: "Enter search criteria:\nVCC:\nhFE: 60-180\nMaxVr: 50V\nIf: {regex pattern}",
                    className: UI.forms.textarea + " mb-2 h-20 text-sm",
                    rows: 3
                }),

                // Options row
                React.createElement('div', { className: "flex items-center justify-between mb-2" },
                    React.createElement('div', { className: "flex items-center space-x-4" },
                        // Partial match checkbox
                        React.createElement('label', {
                            className: `flex items-center text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                        },
                            React.createElement('input', {
                                type: "checkbox",
                                className: UI.forms.checkbox + " mr-1",
                                checked: apPartialMatch,
                                onChange: (e) => setApPartialMatch(e.target.checked)
                            }),
                            "Partial Match"
                        ),

                        // Case sensitive checkbox
                        React.createElement('label', {
                            className: `flex items-center text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                        },
                            React.createElement('input', {
                                type: "checkbox",
                                className: UI.forms.checkbox + " mr-1",
                                checked: apCaseSensitive,
                                onChange: (e) => setApCaseSensitive(e.target.checked)
                            }),
                            "Case Sensitive"
                        ),

                        // Ignore whitespace checkbox
                        React.createElement('label', {
                            className: `flex items-center text-sm cursor-pointer text-${UI.getThemeColors().textSecondary}`
                        },
                            React.createElement('input', {
                                type: "checkbox",
                                className: UI.forms.checkbox + " mr-1",
                                checked: apIgnoreWhitespace,
                                onChange: (e) => setApIgnoreWhitespace(e.target.checked)
                            }),
                            "Ignore Whitespace"
                        )
                    ),

                    // Add button
                    React.createElement('button', {
                        onClick: handleApSearchAdd,
                        disabled: !apSearchText.trim(),
                        className: UI.buttons.small.primary + " min-w-16"
                    }, "Add")
                ),

                // Help text
                React.createElement('div', {
                    className: `text-xs text-${UI.getThemeColors().textMuted}`
                },
                    "Format: Key: Value (one per line). Use 'Key:' (without value) to find components that have that parameter. Supports ranges (60-180), regex patterns in {braces}, and partial matching. Separate multiple with semicolons or new lines."
                )
            ),

            // Active filters display
            selectedApFilters.length > 0 && React.createElement('div', {
                className: `border border-${UI.getThemeColors().border} rounded bg-${UI.getThemeColors().background} p-2`
            },
                React.createElement('div', {
                    className: `text-sm font-medium text-${UI.getThemeColors().textSecondary} mb-2`
                }, "Active AP Filters:"),

                React.createElement('div', { className: "flex flex-wrap gap-1" },
                    selectedApFilters.map(filter =>
                        React.createElement('div', {
                            key: filter.id,
                            className: `inline-flex items-center ${UI.tags.base} ${UI.tags.indigo} text-xs`
                        },
                            React.createElement('span', { className: "mr-1" },
                                filter.isKeyOnlyFilter ?
                                    `${filter.key}: [exists]` :
                                    `${filter.key}: ${filter.value}`
                            ),

                            // Options indicators
                            (filter.caseSensitive || !filter.ignoreWhitespace || !filter.partialMatch) &&
                            React.createElement('span', {
                                className: `text-xs opacity-75 mr-1`,
                                title: `${filter.caseSensitive ? 'Case Sensitive' : ''}${filter.caseSensitive && (!filter.ignoreWhitespace || !filter.partialMatch) ? ', ' : ''}${!filter.ignoreWhitespace ? 'Whitespace Sensitive' : ''}${!filter.ignoreWhitespace && !filter.partialMatch ? ', ' : ''}${!filter.partialMatch ? 'Exact Match' : ''}`
                            },
                                `(${[
                                    filter.caseSensitive ? 'CS' : '',
                                    !filter.ignoreWhitespace ? 'WS' : '',
                                    !filter.partialMatch ? 'EM' : ''
                                ].filter(Boolean).join(',')})`
                            ),

                            // Remove button
                            React.createElement('button', {
                                onClick: () => handleApFilterRemove(filter.id),
                                className: `ml-1 text-current hover:text-red-300 transition-colors`,
                                title: "Remove filter"
                            }, "×")
                        )
                    )
                )
            )
        );
    };

    const activeFilterCount = getActiveFilterCount();

    // --- Main Render ---
    return React.createElement('div', { className: UI.cards.container + " mb-6" },

        React.createElement('div', {
            className: `p-4 border-b border-${UI.getThemeColors().border} grid grid-cols-5 gap-4 items-end`,
        },
            // Add Component Button (column 1)
            React.createElement('div', null,
                React.createElement('button', {
                    onClick: () => {
                        if (typeof onAddComponent === 'function') {
                            onAddComponent();
                        }
                    },
                    className: UI.buttons.success + " w-full",
                    disabled: typeof onAddComponent !== 'function'
                }, "+ Add Component")
            ),

            // Search Input (column 2-3, spans 2 columns)
            React.createElement('div', { className: "col-span-2" },
                React.createElement('label', {
                    htmlFor: "search-input",
                    className: UI.typography.body
                }, "Search Components"),
                React.createElement('div', { className: "flex" },
                    React.createElement('input', {
                        id: "search-input",
                        type: "text",
                        placeholder: "Search by name, type, category, info...",
                        className: UI.forms.input + " flex-grow",
                        value: searchTerm || '',
                        onChange: (e) => {
                            if (typeof onChangeSearchTerm === 'function') {
                                onChangeSearchTerm(e.target.value);
                            }
                        }
                    }),
                    // Clear button (only shown when search has text)
                    searchTerm && React.createElement('button', {
                        className: `ml-2 px-2 text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().textPrimary}`,
                        onClick: () => {
                            if (typeof onChangeSearchTerm === 'function') {
                                onChangeSearchTerm('');
                            }
                        },
                        title: "Clear search"
                    }, "✕")
                )
            ),

            // View Mode Toggle (column 4)
            React.createElement('div', null,
                React.createElement('label', { className: UI.typography.body }, "View Mode"),
                React.createElement('div', { className: `flex rounded shadow-sm border border-${UI.getThemeColors().border}` },
                    React.createElement('button', {
                        title: "Table View",
                        className: `flex-1 p-2 text-sm rounded-l ${viewMode === 'table' ?
                            `bg-${UI.getThemeColors().primary} text-white` :
                            `bg-${UI.getThemeColors().cardBackground} text-${UI.getThemeColors().textSecondary} hover:bg-${UI.getThemeColors().background}`}`,
                        onClick: () => onChangeViewMode('table')
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 inline",
                            fill: "none",
                            viewBox: "0 0 24 24",
                            stroke: "currentColor"
                        },
                            React.createElement('path', {
                                strokeLinecap: "round",
                                strokeLinejoin: "round",
                                strokeWidth: 2,
                                d: "M3 10h18M3 14h18M4 6h16M4 18h16"
                            })
                        )
                    ),
                    React.createElement('button', {
                        title: "Card View",
                        className: `flex-1 p-2 text-sm rounded-r ${viewMode === 'card' ?
                            `bg-${UI.getThemeColors().primary} text-white` :
                            `bg-${UI.getThemeColors().cardBackground} text-${UI.getThemeColors().textSecondary} hover:bg-${UI.getThemeColors().background}`}`,
                        onClick: () => onChangeViewMode('card')
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 inline",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                d: "M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"
                            })
                        )
                    )
                )
            ),

            // Items per Page (column 5)
            React.createElement('div', null,
                React.createElement('label', { className: UI.typography.body }, "Items per Page"),
                React.createElement('div', { className: "flex flex-wrap gap-1" },
                    pageOptions.map(option =>
                        React.createElement('button', {
                            key: option,
                            onClick: () => onItemsPerPageChange(option),
                            className: `px-2 py-1 text-xs border border-${UI.getThemeColors().border} rounded 
                        ${itemsPerPage === option ?
                                    `bg-${UI.getThemeColors().primary} text-white` :
                                    `bg-${UI.getThemeColors().cardBackground} text-${UI.getThemeColors().textSecondary} hover:bg-${UI.getThemeColors().background}`}`
                        }, option === 'all' ? 'All' : option)
                    )
                )
            )
        ),

        React.createElement('div', {
            className: `flex justify-between items-center p-4 border-b border-${UI.getThemeColors().border} cursor-pointer`,
            onClick: onToggleExpand
        },
            React.createElement('div', { className: "flex items-center" },
                React.createElement('h3', { className: UI.typography.heading.h3 }, "Advanced Filters"),
                activeFilterCount > 0 && React.createElement('span', {
                    className: `ml-2 ${UI.buttons.small.info} `
                }, `${activeFilterCount} active`)
            ),
            // Expand/collapse icon
            React.createElement('svg', {
                xmlns: "http://www.w3.org/2000/svg",
                className: `h-5 w-5 ${UI.colors.secondary} transform transition-transform ${isExpanded ? 'rotate-180' : ''}`,
                fill: "none",
                viewBox: "0 0 24 24",
                stroke: "currentColor"
            },
                React.createElement('path', {
                    strokeLinecap: "round",
                    strokeLinejoin: "round",
                    strokeWidth: 2,
                    d: "M19 9l-7 7-7-7"
                })
            )
        ),

        isExpanded && React.createElement('div', { className: UI.cards.body },
            // Filter controls grid - more compact layout
            React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" },
                // Category filter 
                React.createElement('div', null,
                    categories && categories.length > 4
                        ? React.createElement(FilterCheckboxGroup, {
                            title: "Filter by Category",
                            items: categories,
                            selectedItems: selectedCategories,
                            onChange: onCategoriesChange
                        })
                        : renderCheckboxGroup("Filter by Category", categories, selectedCategories, onCategoriesChange)
                ),

                // Type filter 
                React.createElement('div', null,
                    allTypes && allTypes.length > 4
                        ? React.createElement(FilterCheckboxGroup, {
                            title: "Filter by Type",
                            items: allTypes,
                            selectedItems: selectedTypes,
                            onChange: onTypesChange
                        })
                        : renderCheckboxGroup("Filter by Type", allTypes, selectedTypes, onTypesChange)
                ),

                // Location filter
                React.createElement('div', null,
                    locations && locations.length > 4
                        ? React.createElement(FilterCheckboxGroup, {
                            title: "Filter by Location",
                            items: locations.map(loc => loc.name),
                            selectedItems: selectedLocations,
                            onChange: onLocationsChange
                        })
                        : renderCheckboxGroup("Filter by Location",
                            locations.map(loc => loc.name),
                            selectedLocations,
                            onLocationsChange
                        )
                ),

                // Footprint filter
                React.createElement('div', null,
                    footprints && footprints.length > 4
                        ? React.createElement(FilterCheckboxGroup, {
                            title: "Filter by Footprint",
                            items: footprints,
                            selectedItems: selectedFootprints,
                            onChange: onFootprintsChange
                        })
                        : renderCheckboxGroup("Filter by Footprint", footprints, selectedFootprints, onFootprintsChange)
                )
            ),

            // Second row for remaining filters
            React.createElement('div', { className: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4" },
                // Marks filter (compact version)
                React.createElement('div', null,
                    React.createElement('h4', { className: UI.typography.sectionTitle + " mb-2" }, "Filter by Marks"),
                    React.createElement('div', { className: "flex flex-wrap gap-1" },
                        markTypes.map(mark => {
                            const iconComponents = {
                                heart: "❤",
                                bookmark: "🔖",
                                star: "⭐"
                            };

                            return React.createElement('label', {
                                key: mark.id,
                                className: `flex items-center bg-${UI.getThemeColors().cardBackground} px-2 py-1 border border-${UI.getThemeColors().border} rounded hover:bg-${UI.getThemeColors().background} cursor-pointer text-xs text-${UI.getThemeColors().textSecondary}`
                            },
                                React.createElement('input', {
                                    type: "checkbox",
                                    className: UI.forms.checkbox + " mr-1",
                                    checked: selectedMarks?.includes(mark.id) || false,
                                    onChange: () => handleCheckboxGroup(selectedMarks, mark.id, onMarksChange)
                                }),
                                iconComponents[mark.icon],
                                React.createElement('span', { className: "ml-1" }, mark.label)
                            );
                        })
                    )
                ),

                // Quantity range filter (compact)
                React.createElement('div', null,
                    renderRangeSlider("Filter by Quantity", quantityRange, quantityStats, onQuantityRangeChange)
                ),

                // Price range filter (compact)
                React.createElement('div', null,
                    renderRangeSlider("Filter by Price", priceRange, priceStats, onPriceRangeChange)
                ),

                // Clear filters button
                React.createElement('div', { className: "flex items-end" },
                    React.createElement('button', {
                        onClick: onClearFilters,
                        className: UI.buttons.secondary + " w-full",
                        disabled: activeFilterCount === 0
                    }, "Clear All Filters")
                )
            ),

            // Third row for AP search (full width)
            React.createElement('div', { className: "mt-4" },
                renderApParameterSearch()
            )
        )

    );
};

console.log("AdvancedFilters loaded");