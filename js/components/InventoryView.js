// js/components/InventoryView.js - Simplified version

window.App = window.App || {};
window.App.components = window.App.components || {};

window.App.components.InventoryView = ({
    // --- Data ----------------------------------------------------------------
    components = [],
    categories = [],
    locations = [],
    drawers = [],
    cells = [],
    footprints = [],

    // --- UI state ------------------------------------------------------------
    viewMode,
    selectedCategory,
    lowStockConfig,
    currencySymbol,
    showTotalValue,
    itemsPerPage,
    selectedComponents = [],

    // Callbacks 
    onItemsPerPageChange,
    onAddComponent,
    onEditComponent,
    onDeleteComponent,
    onUpdateQuantity,
    onToggleSelect,
    onToggleSelectAll,
    onBulkEdit,
    onBulkDelete,
    onChangeViewMode,
    onToggleFavorite,
}) => {
    const { UI } = window.App.utils;
    const { useState, useEffect, useCallback } = React;

    /* ----------------------------- Local state ----------------------------- */
    const [advancedFiltersExpanded, setAdvancedFiltersExpanded] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [currentPage, setCurrentPage] = useState(1);
    const [selectedCategories, setSelectedCategories] = useState([]);
    const [selectedTypes, setSelectedTypes] = useState([]);
    const [selectedMarks, setSelectedMarks] = useState([]);
    const [selectedLocations, setSelectedLocations] = useState([]);
    const [selectedFootprints, setSelectedFootprints] = useState([]);
    const [quantityRange, setQuantityRange] = useState(null);
    const [priceRange, setPriceRange] = useState(null);
    const [selectedApFilters, setSelectedApFilters] = useState([]);

    // Clear advanced filters callback
    const handleClearAdvancedFilters = useCallback(() => {
        setSelectedCategories([]);
        setSelectedTypes([]);
        setSelectedMarks([]);
        setSelectedLocations([]);
        setSelectedFootprints([]);
        setSelectedApFilters([]);
        setQuantityRange(null);
        setPriceRange(null);
        setCurrentPage(1);
    }, []);

    useEffect(() => {
        setCurrentPage(1);
    }, [selectedCategories, selectedTypes, selectedMarks, selectedLocations,
        selectedFootprints, selectedApFilters, quantityRange, priceRange, searchTerm, selectedCategory]); // Add selectedApFilters

    // --- Filtering Logic ---
    const matchesApFilters = (component, apFilters) => {
        if (!apFilters || apFilters.length === 0) return true;
        if (!component.ap || !Array.isArray(component.ap) || component.ap.length === 0) return false;

        // Get all key-value pairs from component's ap array
        const componentParams = {};
        component.ap.forEach(paramObj => {
            if (paramObj && typeof paramObj === 'object') {
                Object.entries(paramObj).forEach(([key, value]) => {
                    componentParams[key] = value;
                });
            }
        });

        // Check if all AP filters match
        return apFilters.every(filter => {
            const { key, value, caseSensitive = false, ignoreWhitespace = true, partialMatch = true, isKeyOnlyFilter = false } = filter;

            // Find matching key in component params (case sensitivity controlled by checkbox)
            let matchingKey, componentValue;

            if (caseSensitive) {
                // Case-sensitive key matching: exact match required
                componentValue = componentParams[key];
                matchingKey = key;
            } else {
                // Case-insensitive key matching: find key regardless of case
                const searchKey = key.toLowerCase();
                matchingKey = Object.keys(componentParams).find(k => k.toLowerCase() === searchKey);
                componentValue = matchingKey ? componentParams[matchingKey] : undefined;
            }

            if (componentValue === undefined) return false;

            // If this is a key-only filter (like "VCC:"), just check if the key exists
            if (isKeyOnlyFilter) {
                return true; // Key exists since we already checked componentValue !== undefined
            }

            let searchValue = value;
            let targetValue = String(componentValue);

            // Apply whitespace handling
            if (ignoreWhitespace) {
                searchValue = searchValue.replace(/\s+/g, '');
                targetValue = targetValue.replace(/\s+/g, '');
            }

            // Apply case sensitivity
            if (!caseSensitive) {
                searchValue = searchValue.toLowerCase();
                targetValue = targetValue.toLowerCase();
            }

            // Check if value is a regex pattern (wrapped in {})
            if (searchValue.startsWith('{') && searchValue.endsWith('}')) {
                try {
                    const regexPattern = searchValue.slice(1, -1); // Remove { and }
                    const flags = caseSensitive ? 'g' : 'gi';
                    const regex = new RegExp(regexPattern, flags);
                    return regex.test(targetValue);
                } catch (e) {
                    console.warn('Invalid regex pattern:', searchValue, e);
                    return false;
                }
            }

            // Handle range search (e.g., "60-180" or "1.5-3.3")
            const rangeMatch = searchValue.match(/^(\d*\.?\d+)-(\d*\.?\d+)$/);
            if (rangeMatch) {
                const [, minStr, maxStr] = rangeMatch;
                const minVal = parseFloat(minStr);
                const maxVal = parseFloat(maxStr);

                if (!isNaN(minVal) && !isNaN(maxVal)) {
                    // Extract numeric value from target (handle ranges and single values)
                    const targetNumericMatches = targetValue.match(/(\d+\.?\d*)/g);
                    if (targetNumericMatches) {
                        // Check if target is a range (has dash between numbers)
                        const targetRangeMatch = targetValue.match(/(\d+\.?\d*)\s*-\s*(\d+\.?\d*)/);
                        if (targetRangeMatch) {
                            // Target is a range like "3-20v"
                            const targetMin = parseFloat(targetRangeMatch[1]);
                            const targetMax = parseFloat(targetRangeMatch[2]);

                            if (partialMatch) {
                                // Check if ranges overlap
                                return !(maxVal < targetMin || minVal > targetMax);
                            } else {
                                // Exact match: search range must completely contain target range
                                return minVal <= targetMin && maxVal >= targetMax;
                            }
                        } else {
                            // Target is a single number like "30v"
                            const targetNum = parseFloat(targetNumericMatches[0]);
                            if (partialMatch) {
                                // Check if target number falls within search range
                                return targetNum >= minVal && targetNum <= maxVal;
                            } else {
                                // For exact match with ranges, probably no match unless it's exactly the range
                                return false;
                            }
                        }
                    }
                }
            }

            // Handle single numeric search value (like "3")
            const numericSearchMatch = searchValue.match(/^(\d+\.?\d*)$/);
            if (numericSearchMatch) {
                const searchNum = parseFloat(numericSearchMatch[1]);
                if (!isNaN(searchNum)) {
                    // Extract all numbers from target value
                    const targetNumericMatches = targetValue.match(/(\d+\.?\d*)/g);
                    if (targetNumericMatches) {
                        // Check if target is a range
                        const targetRangeMatch = targetValue.match(/(\d+\.?\d*)\s*-\s*(\d+\.?\d*)/);
                        if (targetRangeMatch) {
                            // Target is a range like "3-20v"
                            const targetMin = parseFloat(targetRangeMatch[1]);
                            const targetMax = parseFloat(targetRangeMatch[2]);

                            if (partialMatch) {
                                // Check if search number falls within target range OR matches either endpoint
                                return (searchNum >= targetMin && searchNum <= targetMax) ||
                                    searchNum === targetMin || searchNum === targetMax;
                            } else {
                                // Exact match: search number must exactly match target (unlikely for ranges)
                                return searchNum === targetMin && targetMin === targetMax;
                            }
                        } else {
                            // Target is a single number like "30v"
                            const targetNum = parseFloat(targetNumericMatches[0]);
                            if (partialMatch) {
                                // For partial match, check if numbers are equal or search is contained in target string
                                return searchNum === targetNum || targetValue.includes(searchValue);
                            } else {
                                // Exact match
                                return searchNum === targetNum;
                            }
                        }
                    }
                }
            }

            // Default string matching
            if (partialMatch) {
                // Partial match: target contains search or search contains target
                return targetValue.includes(searchValue) || searchValue.includes(targetValue);
            } else {
                // Exact match
                return targetValue === searchValue;
            }
        });
    };
    const filteredComponents = components.filter(component => {
        // Basic filters (search and category dropdown)
        const matchesCategory = selectedCategory === 'all' || component.category === selectedCategory;
        const lowerSearchTerm = searchTerm.toLowerCase();
        const matchesSearch = !searchTerm ||
            (component.name && component.name.toLowerCase().includes(lowerSearchTerm)) ||
            (component.type && component.type.toLowerCase().includes(lowerSearchTerm)) ||
            (component.category && component.category.toLowerCase().includes(lowerSearchTerm)) ||
            (component.info && component.info.toLowerCase().includes(lowerSearchTerm));

        // Advanced filters
        const matchesAdvancedCategory = selectedCategories.length === 0 ||
            selectedCategories.includes(component.category);

        const matchesType = selectedTypes.length === 0 ||
            (component.type && selectedTypes.includes(component.type));

        const matchesMarks = selectedMarks.length === 0 ||
            selectedMarks.some(mark => component[mark]);

        const matchesLocation = selectedLocations.length === 0 ||
            (component.storage && component.storage.locationId &&
                locations.some(loc =>
                    selectedLocations.includes(loc.name) &&
                    loc.id === component.storage.locationId
                ));

        const matchesFootprint = selectedFootprints.length === 0 ||
            (component.footprint && selectedFootprints.includes(component.footprint));

        // Quantity range filter
        const componentQuantity = component.quantity || 0;
        const matchesQuantity = !quantityRange || (
            (quantityRange.min !== null && quantityRange.max !== null && quantityRange.min === quantityRange.max)
                ? (componentQuantity === quantityRange.min)
                : (
                    (quantityRange.min === null || componentQuantity >= quantityRange.min) &&
                    (quantityRange.max === null || componentQuantity <= quantityRange.max)
                )
        );

        // Price range filter
        const componentPrice = component.price || 0;
        const matchesPrice = !priceRange || (
            (priceRange.min !== null && priceRange.max !== null && priceRange.min === priceRange.max)
                ? (componentPrice === priceRange.min)
                : (
                    (priceRange.min === null || componentPrice >= priceRange.min) &&
                    (priceRange.max === null || componentPrice <= priceRange.max)
                )
        );

        // Additional Parameters filter (ADD THIS)
        const matchesAp = matchesApFilters(component, selectedApFilters);

        return matchesCategory && matchesSearch &&
            matchesAdvancedCategory && matchesType &&
            matchesMarks && matchesLocation &&
            matchesFootprint && matchesQuantity && matchesPrice &&
            matchesAp; // Add this to the return condition
    });

    // --- Pagination Logic ---
    const paginatedComponents = itemsPerPage === 'all'
        ? filteredComponents
        : filteredComponents.slice(
            (currentPage - 1) * itemsPerPage,
            currentPage * itemsPerPage
        );

    const totalPages = itemsPerPage === 'all'
        ? 1
        : Math.ceil(filteredComponents.length / itemsPerPage);

    // Handle page change
    const handlePageChange = (page) => {
        setCurrentPage(Math.min(Math.max(1, page), totalPages));
    };

    // --- Event Handlers ---
    const handleSearchChange = (e) => {
        let newSearchTerm = '';
        if (e && e.target && e.target.value !== undefined) {
            newSearchTerm = e.target.value;
        } else if (typeof e === 'string') {
            newSearchTerm = e;
        }
        setSearchTerm(newSearchTerm);
        setCurrentPage(1);
    };

    const handleViewChange = (mode) => {
        if (mode === 'table' || mode === 'card') {
            onChangeViewMode(mode);
        } else {
            console.warn("handleViewChange called with invalid mode", mode);
            onChangeViewMode('table');
        }
    };

    // Pagination component (using shared Pagination component)
    const renderPagination = () => {
        if (itemsPerPage === 'all' || totalPages <= 1) {
            return null;
        }

        return React.createElement(window.App.components.shared.Pagination, {
            currentPage,
            totalPages,
            totalItems: filteredComponents.length,
            itemsPerPage,
            onPageChange: handlePageChange,
            maxVisiblePages: 3, // Controls how many page numbers to show (default: 5)
            showInfo: true,
            showJumpToPage: false, // Enable jump-to-page for easier navigation with many pages
            className: "mb-4"
        });
    };

    // --- Main Render ---
    return React.createElement('div', null,

        // --- Inventory Summary Stats ---
        React.createElement(window.App.components.StatisticInventory, {
            components,
            categories,
            locations,
            drawers,
            cells,
            footprints,
            lowStockConfig,
            currencySymbol,
            showTotalValue
        }),

        // --- Advanced Filters Card ---
        React.createElement(window.App.components.AdvancedFilters, {
            components,
            categories,
            locations,
            footprints,
            viewMode,
            searchTerm,
            selectedCategories,
            selectedTypes,
            selectedMarks,
            selectedLocations,
            selectedFootprints,
            quantityRange,
            priceRange,
            itemsPerPage,
            onAddComponent,
            onCategoriesChange: setSelectedCategories,
            onTypesChange: setSelectedTypes,
            onMarksChange: setSelectedMarks,
            onLocationsChange: setSelectedLocations,
            onFootprintsChange: setSelectedFootprints,
            onQuantityRangeChange: setQuantityRange,
            onPriceRangeChange: setPriceRange,
            selectedApFilters: selectedApFilters,
            onApFiltersChange: setSelectedApFilters,
            onItemsPerPageChange,
            onClearFilters: handleClearAdvancedFilters,
            onChangeViewMode: handleViewChange,
            onChangeSearchTerm: handleSearchChange,
            isExpanded: advancedFiltersExpanded,
            onToggleExpand: () => setAdvancedFiltersExpanded(!advancedFiltersExpanded)
        }),

        // Pagination (top)
        renderPagination(),

        // --- Selection Controls Bar (Always shown when components exist) ---
        filteredComponents.length > 0 && React.createElement('div', {
            className: `mb-4 p-3 bg-${UI.getThemeColors().background} rounded-lg border border-${UI.getThemeColors().border} flex flex-wrap justify-between items-center gap-2`
        },
            // Select All Checkbox & Count
            React.createElement('div', { className: "flex items-center" },
                React.createElement('input', {
                    type: "checkbox",
                    id: "select-all-filtered-bulk",
                    className: UI.forms.checkbox + " mr-2",
                    checked: selectedComponents.length === filteredComponents.length && filteredComponents.length > 0,
                    onChange: onToggleSelectAll,
                    title: selectedComponents.length === filteredComponents.length ? "Deselect All Visible" : "Select All Visible",
                    disabled: filteredComponents.length === 0
                }),
                React.createElement('label', {
                    htmlFor: "select-all-filtered-bulk",
                    className: UI.forms.label + " cursor-pointer"
                }, selectedComponents.length > 0
                    ? `${selectedComponents.length} component(s) selected`
                    : `Select all ${filteredComponents.length} component(s)`
                )
            ),
            // Bulk Action Buttons (only shown when components are selected)
            selectedComponents.length > 0 && React.createElement('div', { className: "flex gap-2" },
                React.createElement('button', {
                    onClick: onBulkEdit,
                    className: UI.buttons.small.primary
                }, "Edit Selected"),
                React.createElement('button', {
                    onClick: onBulkDelete,
                    className: UI.buttons.small.danger
                }, "Delete Selected")
            )
        ),

        // --- Components List (Table or Cards) ---
        viewMode === 'table' ?
            React.createElement(window.App.components.ViewTableInventory, {
                components: paginatedComponents,
                locations,
                drawers,
                cells,
                selectedComponents,
                lowStockConfig,
                currencySymbol,
                onToggleSelect,
                onToggleSelectAll,
                onUpdateQuantity,
                onToggleFavorite,
                onEditComponent,
                onDeleteComponent
            }) :
            React.createElement(window.App.components.ViewCardInventory, {
                components: paginatedComponents,
                locations,
                drawers,
                cells,
                selectedComponents,
                lowStockConfig,
                currencySymbol,
                onToggleSelect,
                onUpdateQuantity,
                onEditComponent,
                onDeleteComponent
            }),

        // Pagination (bottom)
        renderPagination()
    );
};

console.log("Simplified InventoryView component loaded.");