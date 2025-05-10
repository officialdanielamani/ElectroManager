// js/components/InventoryView.js

window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.utils = window.App.utils || {};

window.App.components.InventoryView = ({
    // --- Data ----------------------------------------------------------------
    components = [], // Array: All component objects
    categories = [], // Array: List of category strings
    locations = [], // Array: Location objects (rack / shelf / zone)
    drawers = [], // Array: Drawer metadata (visual containers)
    cells = [], // Array: Individual cell definitions within drawers
    footprints = [], // Array: List of footprint strings (e.g., SOIC‑8, 0603)

    // --- UI state ------------------------------------------------------------
    viewMode,                 // String: 'table' | 'card' – current view toggle
    selectedCategory,         // String: Category filter selected in UI
    lowStockConfig,           // Object: { [category]: threshold } for alerts
    currencySymbol,           // String: e.g., '$', 'RM' – prefix in totals
    showTotalValue,           // Boolean: true shows total inventory value card
    itemsPerPage,             // Number | 'all' – pagination page size
    selectedComponents = [],  // Array<string> of component IDs currently selected

    // Callbacks 
    onItemsPerPageChange, // (newSize)        → void
    onAddComponent,       // ()               → void
    onEditComponent,      // (component)      → void
    onDeleteComponent,    // (id)             → void
    onUpdateQuantity,     // (id, delta)      → void
    onToggleSelect,       // (id)             → void
    onToggleSelectAll,    // (selectAll)      → void
    onBulkEdit,           // (ids)            → void
    onBulkDelete,         // (ids)            → void
    onChangeViewMode,     // ('table'|'card') → void
    onToggleFavorite,     // (id)             → void
}) => {
    const { UI, helpers } = window.App.utils;
    const { useState, useEffect } = React;

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

    /* -------------------------- Summary statistics ------------------------- */
    const totalComponents = components.length;
    const totalItems = components.reduce((s, c) => s + (Number(c.quantity) || 0), 0);
    const totalValue = helpers.calculateTotalInventoryValue(components);

    const lowStockCount = components.filter(c => helpers.isLowStock(c, lowStockConfig)).length;
    const outOfStockCount = components.filter(c => (Number(c.quantity) || 0) === 0).length;

    const locationCount = locations.length;
    const drawerCount = drawers.length;
    const cellCount = cells.length;
    const footprintCount = footprints.length;

    const categoryCounts = helpers.calculateCategoryCounts(components);

    const renderSummaryCard = (label, value, colorClass = UI.colors.primary.text) => {
        const cardClass = `${UI.cards.container} text-center p-4`;
        const labelClass = `${UI.typography.small} font-medium mb-1`;
        const valueClass = `${UI.typography.heading.h2} ${colorClass}`;

        return React.createElement('div', { className: cardClass },
            React.createElement('div', { className: labelClass }, label),
            React.createElement('div', { className: valueClass }, value)
        );
    };

    // Clear advanced filters if simple category/search filters change
    useEffect(() => {
        // If category dropdown changes and we have selected categories in advanced filter,
        // align them by setting the advanced filter to match the dropdown
        if (selectedCategory !== 'all' && selectedCategories.length > 0) {
            setSelectedCategories([selectedCategory]);
        }
    }, [selectedCategory, selectedCategories]);

    // Reset pagination when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [selectedCategories, selectedTypes, selectedMarks, selectedLocations,
        selectedFootprints, quantityRange, priceRange, searchTerm, selectedCategory]);

    // Clear all advanced filters
    const handleClearAdvancedFilters = useCallback(() => {
        setSelectedCategories([]);
        setSelectedTypes([]);
        setSelectedMarks([]);
        setSelectedLocations([]);
        setSelectedFootprints([]);
        setQuantityRange(null);
        setPriceRange(null);
        setCurrentPage(1);
    }, []);

    // --- Filtering Logic ---
    // Filter components based on search term, selected category, and advanced filters
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
        // Category filter
        const matchesAdvancedCategory = selectedCategories.length === 0 ||
            selectedCategories.includes(component.category);

        // Type filter
        const matchesType = selectedTypes.length === 0 ||
            (component.type && selectedTypes.includes(component.type));

        // Marks filter (favorite, bookmark, star)
        const matchesMarks = selectedMarks.length === 0 ||
            selectedMarks.some(mark => component[mark]);

        // Location filter
        const matchesLocation = selectedLocations.length === 0 ||
            (component.locationInfo && component.locationInfo.locationId &&
                locations.some(loc =>
                    selectedLocations.includes(loc.name) &&
                    loc.id === component.locationInfo.locationId
                ));

        // Footprint filter
        const matchesFootprint = selectedFootprints.length === 0 ||
            (component.footprint && selectedFootprints.includes(component.footprint));

        // Quantity range filter - FIXED LOGIC
        const componentQuantity = component.quantity || 0;
        const matchesQuantity = !quantityRange || (
            // If min and max are defined and equal, filter for exact match
            (quantityRange.min !== null && quantityRange.max !== null && quantityRange.min === quantityRange.max)
                ? (componentQuantity === quantityRange.min)
                // Otherwise, use proper range filtering with both min and max boundaries
                : (
                    (quantityRange.min === null || componentQuantity >= quantityRange.min) &&
                    (quantityRange.max === null || componentQuantity <= quantityRange.max)
                )
        );

        // Price range filter - FIXED LOGIC
        const componentPrice = component.price || 0;
        const matchesPrice = !priceRange || (
            // If min and max are defined and equal, filter for exact match
            (priceRange.min !== null && priceRange.max !== null && priceRange.min === priceRange.max)
                ? (componentPrice === priceRange.min)
                // Otherwise, use proper range filtering with both min and max boundaries
                : (
                    (priceRange.min === null || componentPrice >= priceRange.min) &&
                    (priceRange.max === null || componentPrice <= priceRange.max)
                )
        );

        // Combine all filters
        return matchesCategory && matchesSearch &&
            matchesAdvancedCategory && matchesType &&
            matchesMarks && matchesLocation &&
            matchesFootprint && matchesQuantity && matchesPrice;
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
        // Extract the search value safely
        let newSearchTerm = '';

        if (e && e.target && e.target.value !== undefined) {
            // Normal event object from input element
            newSearchTerm = e.target.value;
        } else if (typeof e === 'string') {
            // Direct string value
            newSearchTerm = e;
        }

        // Update the search term state
        setSearchTerm(newSearchTerm);

        // Reset to page 1 when search changes (if using pagination)
        setCurrentPage(1);
    };

    const handleViewChange = (mode) => {
        // Just pass the mode directly - this is expected to be a string value
        if (mode === 'table' || mode === 'card') {
            onChangeViewMode(mode);
        } else {
            console.warn("handleViewChange called with invalid mode", mode);
            onChangeViewMode('table'); // Default to table view
        }
    };

    // --- Render Functions for Table and Card Views ---

    // Renders a single row in the table view
    const renderTableRow = (component) => {
        const isSelected = selectedComponents.includes(component.id);
        const lowStock = helpers.isLowStock(component, lowStockConfig);
        const formattedPrice = helpers.formatCurrency(component.price, currencySymbol);
        const datasheetLinks = helpers.formatDatasheets(component.datasheets);

        return React.createElement('tr', {
            key: component.id,
            className: `${isSelected ? UI.tables.body.rowSelected : UI.tables.body.row} ${lowStock ? `bg-${UI.getThemeColors().danger.replace('500', '50').replace('400', '950')} hover:bg-${UI.getThemeColors().danger.replace('500', '100').replace('400', '900')}` : ''}`
        },
            // Checkbox
            React.createElement('td', { className: "px-3 py-2 text-center" },
                React.createElement('input', {
                    type: "checkbox",
                    className: UI.forms.checkbox,
                    checked: isSelected,
                    onChange: () => onToggleSelect(component.id)
                })
            ),
            // Component Name/Category/Datasheet
            React.createElement('td', { className: UI.tables.body.cell },
                React.createElement('div', { className: UI.typography.heading.h5 }, component.name),
                React.createElement('div', { className: UI.typography.small }, component.category),
                React.createElement('div', { className: "mt-1" },
                    datasheetLinks.map((url, index) =>
                        React.createElement('a', {
                            key: index,
                            href: url,
                            target: "_blank",
                            rel: "noopener noreferrer",
                            className: "text-xs text-blue-500 hover:text-blue-700 hover:underline mr-2"
                        }, `Datasheet ${datasheetLinks.length > 1 ? index + 1 : ''}`)
                    )
                )
            ),
            // Type
            React.createElement('td', { className: UI.tables.body.cell }, component.type),

            // Bookmark/Favorite/Star column
            React.createElement('td', { className: "px-2 py-2 whitespace-nowrap" },
                React.createElement('div', { className: "flex items-center space-x-1" },
                    // Favorite Icon/Button
                    React.createElement('button', {
                        onClick: () => onToggleFavorite(component.id, 'favorite'),
                        className: `p-1 rounded-full ${component.favorite ? "text-red-500 hover:text-red-600" : 'text-gray-300 hover:text-red-500'}`,
                        title: component.favorite ? "Remove from favorites" : "Add to favorites"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-5 w-5",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                fillRule: "evenodd",
                                d: "M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z",
                                clipRule: "evenodd"
                            })
                        )
                    ),

                    // Bookmark Icon/Button
                    React.createElement('button', {
                        onClick: () => onToggleFavorite(component.id, 'bookmark'),
                        className: `p-1 rounded-full ${component.bookmark ? "text-blue-500 hover:text-blue-600" : 'text-gray-300 hover:text-blue-500'}`,
                        title: component.bookmark ? "Remove bookmark" : "Add bookmark"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-5 w-5",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                d: "M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
                            })
                        )
                    ),

                    // Star Icon/Button
                    React.createElement('button', {
                        onClick: () => onToggleFavorite(component.id, 'star'),
                        className: `p-1 rounded-full ${component.star ? "text-yellow-500 hover:text-yellow-600" : 'text-gray-300 hover:text-yellow-500'}`,
                        title: component.star ? "Remove star" : "Add star"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-5 w-5",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                d: "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                            })
                        )
                    )
                )
            ),
            // Footprint
            React.createElement('td', { className: UI.tables.body.cell }, component.footprint || '-'),
            // Quantity
            React.createElement('td', { className: "px-4 py-2 whitespace-nowrap text-center" },
                React.createElement('div', { className: "flex items-center justify-center space-x-1" },
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, -1),
                        className: UI.buttons.icon.danger,
                        title: "Decrease Quantity"
                    }, "-"),
                    React.createElement('span', { className: UI.tables.body.cell }, component.quantity || 0),
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, 1),
                        className: UI.buttons.icon.success,
                        title: "Increase Quantity"
                    }, "+")
                ),
                lowStock && React.createElement('div', {
                    className: UI.tags.red,
                }, "Low Stock")
            ),
            // Price
            React.createElement('td', { className: UI.tables.body.cell + " text-right" }, formattedPrice),
            // Info
            React.createElement('td', { className: "px-4 py-2 max-w-xs text-sm text-gray-700 truncate", title: component.info }, component.info),
            // Actions
            React.createElement('td', { className: UI.tables.body.cellAction },
                React.createElement('button', {
                    onClick: () => onEditComponent(component),
                    className: "text-indigo-600 hover:text-indigo-900 mr-3",
                    title: "Edit Component"
                }, "Edit"),
                React.createElement('button', {
                    onClick: () => onDeleteComponent(component.id),
                    className: "text-red-600 hover:text-red-900",
                    title: "Delete Component"
                }, "Delete")
            )
        );
    };

    // Pagination component
    const renderPagination = () => {
        if (itemsPerPage === 'all' || totalPages <= 1) {
            return null; // Don't render pagination if showing all or only one page
        }

        return React.createElement('div', { className: "flex flex-col items-center mb-4" },
            // Pagination controls
            React.createElement('div', { className: "flex justify-center" },
                React.createElement('div', { className: "bg-white shadow-sm rounded border inline-flex" },
                    // Previous button
                    React.createElement('button', {
                        onClick: () => handlePageChange(currentPage - 1),
                        disabled: currentPage === 1,
                        className: `px-3 py-1 border-r ${currentPage === 1 ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-gray-50'}`
                    }, "<"),

                    // Page numbers - limit visible pages for readability
                    (() => {
                        const pages = [];
                        const maxVisiblePages = 5; // Show max 5 page numbers at once
                        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
                        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

                        // Adjust if we're near the end
                        if (endPage - startPage + 1 < maxVisiblePages) {
                            startPage = Math.max(1, endPage - maxVisiblePages + 1);
                        }

                        // Add first page if not in range
                        if (startPage > 1) {
                            pages.push(React.createElement('button', {
                                key: 1,
                                onClick: () => handlePageChange(1),
                                className: `px-3 py-1 border-r ${1 === currentPage ? 'bg-blue-500 text-white' : 'hover:bg-gray-50'}`
                            }, "1"));

                            if (startPage > 2) {
                                pages.push(React.createElement('span', {
                                    key: 'start-ellipsis',
                                    className: "px-2 py-1 border-r text-gray-500"
                                }, "..."));
                            }
                        }

                        // Add visible page numbers
                        for (let i = startPage; i <= endPage; i++) {
                            pages.push(React.createElement('button', {
                                key: i,
                                onClick: () => handlePageChange(i),
                                className: `px-3 py-1 border-r ${i === currentPage ? 'bg-blue-500 text-white' : 'hover:bg-gray-50'}`
                            }, i.toString()));
                        }

                        // Add last page if not in range
                        if (endPage < totalPages) {
                            if (endPage < totalPages - 1) {
                                pages.push(React.createElement('span', {
                                    key: 'end-ellipsis',
                                    className: "px-2 py-1 border-r text-gray-500"
                                }, "..."));
                            }

                            pages.push(React.createElement('button', {
                                key: totalPages,
                                onClick: () => handlePageChange(totalPages),
                                className: `px-3 py-1 border-r ${totalPages === currentPage ? 'bg-blue-500 text-white' : 'hover:bg-gray-50'}`
                            }, totalPages.toString()));
                        }

                        return pages;
                    })(),

                    // Next button
                    React.createElement('button', {
                        onClick: () => handlePageChange(currentPage + 1),
                        disabled: currentPage === totalPages,
                        className: `px-3 py-1 ${currentPage === totalPages ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-gray-50'}`
                    }, ">")
                )
            ),

            // Pagination status text
            filteredComponents.length > 0 && React.createElement('div', { className: "text-center text-sm text-gray-600 mt-2" },
                `Showing ${(currentPage - 1) * itemsPerPage + 1}-${Math.min(currentPage * itemsPerPage, filteredComponents.length)} of ${filteredComponents.length} items`
            )
        );
    };

    // Renders a single card in the card view
    const renderCard = (component) => {
        const isSelected = selectedComponents.includes(component.id);
        const lowStock = helpers.isLowStock(component, lowStockConfig);
        const formattedPrice = helpers.formatCurrency(component.price, currencySymbol);
        const datasheetLinks = helpers.formatDatasheets(component.datasheets);

        return React.createElement('div', {
            key: component.id,
            className: `${UI.cards.container} ${isSelected ? 'ring-2 ring-offset-1 ring-blue-500' : ''} ${lowStock ? 'border-l-4 border-red-400' : ''}`
        },
            // Select Checkbox
            React.createElement('div', { className: "absolute top-2 left-2 z-10" },
                React.createElement('input', {
                    type: "checkbox",
                    checked: isSelected,
                    onChange: () => onToggleSelect(component.id),
                    className: UI.forms.checkbox + " bg-white bg-opacity-75",
                    title: "Select component"
                })
            ),
            // Image Area
            React.createElement('div', { className: "relative h-40 bg-gray-100 rounded-t-lg flex items-center justify-center overflow-hidden" },
                React.createElement('img', {
                    src: component.image || '',
                    alt: component.name || 'Component Image',
                    className: "w-full h-full object-contain p-2",
                    // Fallback placeholder if image fails to load
                    //onError: (e) => { e.target.onerror = null; e.target.src = `https://placehold.co/200x150/e2e8f0/94a3b8?text=No+Image`; }
                }),
                lowStock && React.createElement('span', {
                    className: UI.tags.red + " absolute bottom-1 right-1"
                }, "LOW")
            ),
            // Card Content
            React.createElement('div', { className: UI.cards.body },
                // Name & Type
                React.createElement('div', { className: "flex justify-between items-start mb-2" },
                    React.createElement('h3', {
                        className: UI.typography.heading.h4 + " truncate mr-2",
                        title: component.name
                    }, component.name),
                    component.type && React.createElement('span', {
                        className: UI.tags.gray
                    }, component.type)
                ),
                // Footprint
                React.createElement('div', { className: "text-sm text-gray-600 mb-1 flex justify-between" },
                    React.createElement('span', { className: "font-medium" }, "Footprint:"),
                    component.footprint ?
                        React.createElement('span', {
                            className: UI.tags.gray
                        }, component.footprint)
                        : React.createElement('span', { className: "text-gray-400" }, "-")
                ),
                // Category
                React.createElement('div', {
                    className: UI.typography.small + " mb-1"
                }, component.category),
                // Price
                React.createElement('div', { className: "text-md font-semibold text-green-700 mb-3" }, formattedPrice),
                // Quantity Controls
                React.createElement('div', { className: "flex items-center justify-center space-x-2 mb-3 border-t border-b py-2 border-gray-100" },
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, -1),
                        className: UI.buttons.icon.danger,
                        title: "Decrease Quantity"
                    },
                        React.createElement('svg', { xmlns: "http://www.w3.org/2000/svg", className: "h-5 w-5", viewBox: "0 0 20 20", fill: "currentColor" },
                            React.createElement('path', { fillRule: "evenodd", d: "M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z", clipRule: "evenodd" }))),

                    React.createElement('span', { className: `text-lg font-semibold ${lowStock ? 'text-red-600' : 'text-gray-900'}` }, component.quantity || 0),

                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, 1),
                        className: UI.buttons.icon.success,
                        title: "Increase Quantity"
                    },
                        React.createElement('svg', { xmlns: "http://www.w3.org/2000/svg", className: "h-5 w-5", viewBox: "0 0 20 20", fill: "currentColor" },
                            React.createElement('path', { fillRule: "evenodd", d: "M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z", clipRule: "evenodd" })))
                ),
                // Info
                component.info && React.createElement('p', {
                    className: UI.typography.small + " mb-2 truncate",
                    title: component.info
                },
                    React.createElement('span', { className: "font-medium" }, "Uses: "), component.info),
                // Datasheets
                React.createElement('div', { className: "mb-3" },
                    datasheetLinks.map((url, index) =>
                        React.createElement('a', {
                            key: index,
                            href: url,
                            target: "_blank",
                            rel: "noopener noreferrer",
                            className: "text-sm text-blue-500 hover:text-blue-700 hover:underline mr-2 inline-block"
                        }, `Datasheet ${datasheetLinks.length > 1 ? index + 1 : ''}`)
                    )
                ),
                // Action Buttons
                React.createElement('div', { className: "flex justify-end space-x-2 border-t border-gray-100 pt-3" },
                    React.createElement('button', {
                        onClick: () => onEditComponent(component),
                        className: UI.buttons.small.info,
                        title: "Edit Component"
                    }, "Edit"),
                    React.createElement('button', {
                        onClick: () => onDeleteComponent(component.id),
                        className: UI.buttons.small.danger,
                        title: "Delete Component"
                    }, "Delete")
                )
            )
        );
    };

    // --- Main Render ---
    return (
        React.createElement('div', null,

            // --- Inventory Summary Stats ---
            React.createElement('div', { className: UI.layout.sectionAlt },
                React.createElement('h2', { className: `${UI.typography.subtitle} mb-3` }, 'Inventory Summary'),

                React.createElement('div', {
                    className: 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4'
                },
                    renderSummaryCard('Components', totalComponents, UI.colors.primary.text),
                    renderSummaryCard('Total Items', totalItems, UI.colors.success.text),
                    showTotalValue && renderSummaryCard('Total Value', helpers.formatCurrency(totalValue, currencySymbol), UI.colors.accent.text),
                    renderSummaryCard('Categories', categories.length, UI.colors.info.text),
                    renderSummaryCard('Low Stock', lowStockCount, lowStockCount ? UI.colors.danger.text : UI.colors.secondary.text),
                    renderSummaryCard('Out of Stock', outOfStockCount, outOfStockCount ? UI.colors.danger.text : UI.colors.secondary.text),
                    renderSummaryCard('Locations', locationCount, UI.colors.info.text),
                    renderSummaryCard('Drawers', drawerCount, UI.colors.info.text),
                    renderSummaryCard('Cells', cellCount, UI.colors.info.text),
                    renderSummaryCard('Footprints', footprintCount, UI.colors.info.text)
                ),

                totalComponents > 0 && React.createElement('div', {
                    className: `${UI.utils.borderTop} pt-3 mt-3 border-${UI.getThemeColors().border}`
                },
                    React.createElement('h3', { className: `${UI.typography.subtitle} mb-2` }, 'Item Counts by Category'),
                    React.createElement('div', { className: 'flex flex-wrap gap-3' },
                        categoryCounts.length ? categoryCounts.map(([cat, cnt]) => React.createElement('div', {
                            key: cat,
                            className: `${UI.cards.container} px-3 py-1`
                        },
                            React.createElement('span', { className: `${UI.typography.small} mr-1` }, `${cat}:`),
                            React.createElement('span', { className: `${UI.typography.small} font-semibold ${UI.colors.primary.text}` }, cnt)
                        )) : React.createElement('p', { className: `${UI.typography.small} italic` }, 'No items with categories found.')
                    )
                )



            ),

            // --- Advanced Filters Card ---
            React.createElement(window.App.components.AdvancedFilters, {
                // Props
                components: components,
                categories: categories,
                locations: locations,
                footprints: footprints,
                viewMode: viewMode,
                searchTerm: searchTerm,

                // Filter states
                selectedCategories: selectedCategories,
                selectedTypes: selectedTypes,
                selectedMarks: selectedMarks,
                selectedLocations: selectedLocations,
                selectedFootprints: selectedFootprints,
                quantityRange: quantityRange,
                priceRange: priceRange,
                itemsPerPage: itemsPerPage, // Pass the prop

                // Callbacks
                onAddComponent: onAddComponent,
                onCategoriesChange: setSelectedCategories,
                onTypesChange: setSelectedTypes,
                onMarksChange: setSelectedMarks,
                onLocationsChange: setSelectedLocations,
                onFootprintsChange: setSelectedFootprints,
                onQuantityRangeChange: setQuantityRange,
                onPriceRangeChange: setPriceRange,
                onItemsPerPageChange: onItemsPerPageChange, // Pass the callback
                onClearFilters: handleClearAdvancedFilters,
                onChangeViewMode: handleViewChange,
                onChangeSearchTerm: handleSearchChange,

                // UI state
                isExpanded: advancedFiltersExpanded,
                onToggleExpand: () => setAdvancedFiltersExpanded(!advancedFiltersExpanded)
            }),

            // --- Bulk Action Bar (Conditional) ---
            selectedComponents.length > 0 && React.createElement('div', { className: UI.status.info + " mb-4 flex flex-wrap justify-between items-center gap-2" },
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
                    React.createElement('label', { htmlFor: "select-all-filtered-bulk", className: UI.forms.label }, ` ${selectedComponents.length} component(s) selected `)
                ),
                // Bulk Action Buttons
                React.createElement('div', { className: "flex gap-2" },
                    React.createElement('button', {
                        onClick: onBulkEdit,
                        className: UI.buttons.small.primary
                    }, "Edit Selected"),
                    React.createElement('button', {
                        onClick: onBulkDelete,
                        className: UI.buttons.small.danger
                    }, "Delete Selected")
                )
            ), // End Bulk Action Bar
            renderPagination(),

            // --- Components List (Table or Cards) ---
            viewMode === 'table' ? (
                // Table View
                React.createElement('div', { className: UI.tables.container + " overflow-x-auto w-full mb-6" },
                    React.createElement('div', { className: "min-w-full" }, // Ensure minimum width fits content
                        React.createElement('table', { className: "w-full divide-y divide-gray-200" },
                            React.createElement('thead', { className: UI.tables.header.row },
                                React.createElement('tr', null,
                                    // Select All Header Checkbox
                                    React.createElement('th', { className: "w-10 px-3 py-3 text-center" },
                                        React.createElement('input', {
                                            type: "checkbox",
                                            className: UI.forms.checkbox,
                                            checked: selectedComponents.length === filteredComponents.length && filteredComponents.length > 0,
                                            onChange: onToggleSelectAll,
                                            disabled: filteredComponents.length === 0,
                                            title: selectedComponents.length === filteredComponents.length ? "Deselect All Visible" : "Select All Visible"
                                        })
                                    ),

                                    // Other Headers
                                    React.createElement('th', { className: UI.tables.header.cell }, "Component"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Type"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Marks"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Footprint"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Quantity"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Price"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Info"),
                                    React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                                )
                            ),
                            React.createElement('tbody', { className: "bg-white divide-y divide-gray-200" },
                                filteredComponents.length > 0 ? paginatedComponents.map(renderTableRow) : null,
                                // Empty/No Match Messages
                                filteredComponents.length === 0 && totalComponents > 0 && React.createElement('tr', null,
                                    React.createElement('td', { colSpan: "9", className: "px-4 py-8 text-center text-gray-500 italic" },
                                        "No components match filters."
                                    )
                                ),
                                totalComponents === 0 && React.createElement('tr', null,
                                    React.createElement('td', { colSpan: "9", className: "px-4 py-8 text-center text-gray-500" },
                                        "Inventory empty. Add components."
                                    )
                                )
                            )
                        )
                    )
                )
            ) : (
                // Card View
                React.createElement('div', null,
                    React.createElement('div', { className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 mb-6" },
                        filteredComponents.length > 0 ? filteredComponents.map(renderCard) : null,
                        // Empty/No Match Messages
                        filteredComponents.length === 0 && totalComponents > 0 &&
                        React.createElement('div', { className: "col-span-full p-8 text-center text-gray-500 bg-white rounded shadow italic" },
                            "No components match filters."
                        ),
                        totalComponents === 0 &&
                        React.createElement('div', { className: "col-span-full p-8 text-center text-gray-500 bg-white rounded shadow" },
                            "Inventory empty. Add components."
                        )
                    )
                )
            ), // End Conditional View Rendering
            renderPagination(),
        )

        // End Main Inventory View Div
    );
};

console.log("InventoryView component loaded with clean direct UI references."); // For debugging