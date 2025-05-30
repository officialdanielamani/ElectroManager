// js/components/ViewTableInventory.js

window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * ViewTableInventory - Renders components in table view format
 */
window.App.components.ViewTableInventory = ({
    // Data props
    components = [],
    locations = [],
    drawers = [],
    cells = [],
    selectedComponents = [],
    lowStockConfig = {},
    currencySymbol = 'RM',
    
    // Event handlers
    onToggleSelect,
    onToggleSelectAll,
    onUpdateQuantity,
    onToggleFavorite,
    onEditComponent,
    onDeleteComponent
}) => {
    const { UI, helpers } = window.App.utils;

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
            React.createElement('td', { className: `px-3 py-2 text-center` },
                React.createElement('input', {
                    type: "checkbox",
                    className: UI.forms.checkbox,
                    checked: isSelected,
                    onChange: () => onToggleSelect(component.id),
                    title: "Select component"
                })
            ),

            // Component Name/Category/Datasheet
            React.createElement('td', { className: UI.tables.body.cell },
                React.createElement('div', {
                    className: `${UI.typography.heading.h5} text-${UI.getThemeColors().textPrimary}`
                }, component.name),
                React.createElement('div', {
                    className: `${UI.typography.small} text-${UI.getThemeColors().textMuted}`
                }, component.category),
                React.createElement('div', { className: "mt-1" },
                    datasheetLinks.map((url, index) =>
                        React.createElement('a', {
                            key: index,
                            href: url,
                            target: "_blank",
                            rel: "noopener noreferrer",
                            className: `${UI.typography.small} text-${UI.getThemeColors().info} hover:text-${UI.getThemeColors().infoHover} hover:underline mr-2`
                        }, `Datasheet ${datasheetLinks.length > 1 ? index + 1 : ''}`)
                    )
                )
            ),

            // Type
            React.createElement('td', {
                className: `${UI.tables.body.cell} text-${UI.getThemeColors().textSecondary}`
            }, component.type || '-'),

            // Bookmark/Favorite/Star column
            React.createElement('td', { className: "px-2 py-2 whitespace-nowrap" },
                React.createElement('div', { className: "flex items-center space-x-1" },
                    // Favorite Icon/Button
                    React.createElement('button', {
                        onClick: () => onToggleFavorite(component.id, 'favorite'),
                        className: `p-1 rounded-full transition-colors ${component.favorite ?
                            `text-${UI.getThemeColors().danger} hover:text-${UI.getThemeColors().dangerHover}` :
                            `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().danger}`}`,
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
                        className: `p-1 rounded-full transition-colors ${component.bookmark ?
                            `text-${UI.getThemeColors().info} hover:text-${UI.getThemeColors().infoHover}` :
                            `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().info}`}`,
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
                        className: `p-1 rounded-full transition-colors ${component.star ?
                            `text-${UI.getThemeColors().warning} hover:text-${UI.getThemeColors().warningHover}` :
                            `text-${UI.getThemeColors().textMuted} hover:text-${UI.getThemeColors().warning}`}`,
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
            React.createElement('td', {
                className: `${UI.tables.body.cell} text-${UI.getThemeColors().textSecondary}`
            }, component.footprint || '-'),

            // Storage Location
            React.createElement('td', {
                className: `${UI.tables.body.cell} text-${UI.getThemeColors().textSecondary} max-w-xs truncate`,
                title: window.App.utils.formHelpers.formatStorageDisplay(component.storage, locations, drawers, cells)
            },
                window.App.utils.formHelpers.formatStorageDisplay(component.storage, locations, drawers, cells)
            ),

            // Quantity
            React.createElement('td', { className: "px-4 py-2 whitespace-nowrap text-center" },
                React.createElement('div', { className: "flex items-center justify-center space-x-1" },
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, -1),
                        className: UI.buttons.icon.danger,
                        title: "Decrease Quantity"
                    }, "-"),
                    React.createElement('span', {
                        className: `${UI.tables.body.cell} ${lowStock ? `text-${UI.getThemeColors().danger} ${UI.typography.weight.semibold}` : `text-${UI.getThemeColors().textPrimary}`}`
                    }, component.quantity || 0),
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, 1),
                        className: UI.buttons.icon.success,
                        title: "Increase Quantity"
                    }, "+")
                ),
                lowStock && React.createElement('div', {
                    className: `${UI.tags.base} ${UI.tags.red} mt-1`,
                }, "Low Stock")
            ),

            // Price
            React.createElement('td', {
                className: `${UI.tables.body.cell} text-right text-${UI.getThemeColors().success} ${UI.typography.weight.medium}`
            }, formattedPrice),

            // Info
            React.createElement('td', {
                className: `${UI.tables.body.cell} text-${UI.getThemeColors().textSecondary} max-w-xs truncate`,
                title: component.info
            }, component.info || '-'),

            // Actions
            React.createElement('td', { className: UI.tables.body.cellAction },
                React.createElement('button', {
                    onClick: () => onEditComponent(component),
                    className: `text-${UI.getThemeColors().info} hover:text-${UI.getThemeColors().infoHover} mr-3 transition-colors`,
                    title: "Edit Component"
                }, "Edit"),
                React.createElement('button', {
                    onClick: () => onDeleteComponent(component.id),
                    className: `text-${UI.getThemeColors().danger} hover:text-${UI.getThemeColors().dangerHover} transition-colors`,
                    title: "Delete Component"
                }, "Delete")
            )
        );
    };

    return React.createElement('div', { className: UI.tables.container + " overflow-x-auto w-full mb-6" },
        React.createElement('div', { className: "min-w-full" },
            React.createElement('table', { className: "w-full divide-y divide-gray-200" },
                // Table Header
                React.createElement('thead', { className: UI.tables.header.row },
                    React.createElement('tr', null,
                        // Select All Header Checkbox
                        React.createElement('th', { className: `w-10 px-3 py-3 text-center text-${UI.getThemeColors().tableHeaderText}` },
                            React.createElement('input', {
                                type: "checkbox",
                                className: UI.forms.checkbox,
                                checked: selectedComponents.length === components.length && components.length > 0,
                                onChange: onToggleSelectAll,
                                disabled: components.length === 0,
                                title: selectedComponents.length === components.length ? "Deselect All" : "Select All"
                            })
                        ),

                        // Column Headers
                        React.createElement('th', { className: UI.tables.header.cell }, "Component"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Type"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Marks"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Footprint"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Storage"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Quantity"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Price"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Info"),
                        React.createElement('th', { className: UI.tables.header.cell }, "Actions")
                    )
                ),

                // Table Body
                React.createElement('tbody', { className: `divide-y divide-${UI.getThemeColors().border}` },
                    components.length > 0 ? components.map(renderTableRow) : null,
                    
                    // Empty state message
                    components.length === 0 && React.createElement('tr', { className: UI.tables.body.row },
                        React.createElement('td', { 
                            colSpan: "10", 
                            className: `px-4 py-8 text-center text-${UI.getThemeColors().textMuted} italic` 
                        }, "No components found.")
                    )
                )
            )
        )
    );
};

console.log("ViewTableInventory component loaded.");