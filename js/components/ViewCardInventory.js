// js/components/ViewCardInventory.js

window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * ViewCardInventory - Renders components in card view format
 */
window.App.components.ViewCardInventory = ({
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
    onUpdateQuantity,
    onEditComponent,
    onDeleteComponent
}) => {
    const { UI, helpers } = window.App.utils;

    // Renders a single card in the card view
    const renderCard = (component) => {
        const isSelected = selectedComponents.includes(component.id);
        const lowStock = helpers.isLowStock(component, lowStockConfig);
        const formattedPrice = helpers.formatCurrency(component.price, currencySymbol);
        const datasheetLinks = helpers.formatDatasheets(component.datasheets);

        return React.createElement('div', {
            key: component.id,
            className: `${UI.cards.container} relative ${isSelected ? `ring-2 ring-offset-1 ring-${UI.getThemeColors().primary}` : ''} ${lowStock ? `border-l-4 border-${UI.getThemeColors().danger}` : ''}`
        },
            // Select Checkbox (positioned absolutely in top-left)
            React.createElement('div', { className: "absolute top-2 left-2 z-20" },
                React.createElement('input', {
                    type: "checkbox",
                    checked: isSelected,
                    onChange: () => onToggleSelect(component.id),
                    className: UI.forms.checkbox + ` bg-white bg-opacity-90 shadow-sm border-2 border-gray-300`,
                    title: "Select component"
                })
            ),

            // Image Area
            React.createElement('div', {
                className: `relative h-40 bg-${UI.getThemeColors().background} rounded-t-lg flex items-center justify-center overflow-hidden`
            },
                React.createElement('img', {
                    src: component.image || '',
                    alt: component.name || 'Component Image',
                    className: "w-full h-full object-contain p-2",
                    style: { marginLeft: '24px' } // Give space for checkbox
                }),
                lowStock && React.createElement('span', {
                    className: `${UI.tags.base} ${UI.tags.red} absolute bottom-1 right-1`
                }, "LOW")
            ),

            // Card Content
            React.createElement('div', { className: UI.cards.body },
                // Name & Type
                React.createElement('div', { className: "flex justify-between items-start mb-2" },
                    React.createElement('h3', {
                        className: `${UI.typography.heading.h4} truncate mr-2 text-${UI.getThemeColors().textPrimary}`,
                        title: component.name
                    }, component.name),
                    component.type && React.createElement('span', {
                        className: `${UI.tags.base} ${UI.tags.gray}`
                    }, component.type)
                ),

                // Footprint
                React.createElement('div', {
                    className: `${UI.typography.small} text-${UI.getThemeColors().textSecondary} mb-1 flex justify-between`
                },
                    React.createElement('span', {
                        className: UI.typography.weight.medium
                    }, "Footprint:"),
                    component.footprint ?
                        React.createElement('span', {
                            className: `${UI.tags.base} ${UI.tags.gray}`
                        }, component.footprint)
                        : React.createElement('span', {
                            className: `text-${UI.getThemeColors().textMuted}`
                        }, "-")
                ),

                // Category
                React.createElement('div', {
                    className: `${UI.typography.small} text-${UI.getThemeColors().textSecondary} mb-1`
                }, component.category),

                // Price
                React.createElement('div', {
                    className: `text-md ${UI.typography.weight.semibold} text-${UI.getThemeColors().success} mb-3`
                }, formattedPrice),

                // Quantity Controls
                React.createElement('div', {
                    className: `flex items-center justify-center space-x-2 mb-3 border-t border-b py-2 border-${UI.getThemeColors().borderLight}`
                },
                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, -1),
                        className: UI.buttons.icon.danger,
                        title: "Decrease Quantity"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-5 w-5",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                fillRule: "evenodd",
                                d: "M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z",
                                clipRule: "evenodd"
                            })
                        )
                    ),

                    React.createElement('span', {
                        className: `text-lg ${UI.typography.weight.semibold} ${lowStock ? `text-${UI.getThemeColors().danger}` : `text-${UI.getThemeColors().textPrimary}`}`
                    }, component.quantity || 0),

                    React.createElement('button', {
                        onClick: () => onUpdateQuantity(component.id, 1),
                        className: UI.buttons.icon.success,
                        title: "Increase Quantity"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-5 w-5",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                fillRule: "evenodd",
                                d: "M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z",
                                clipRule: "evenodd"
                            })
                        )
                    )
                ),

                // Info
                component.info && React.createElement('p', {
                    className: `${UI.typography.small} text-${UI.getThemeColors().textSecondary} mb-2 truncate`,
                    title: component.info
                },
                    React.createElement('span', {
                        className: UI.typography.weight.medium
                    }, "Uses: "),
                    component.info
                ),

                // Datasheets
                React.createElement('div', { className: "mb-3" },
                    datasheetLinks.map((url, index) =>
                        React.createElement('a', {
                            key: index,
                            href: url,
                            target: "_blank",
                            rel: "noopener noreferrer",
                            className: `${UI.typography.small} text-${UI.getThemeColors().info} hover:text-${UI.getThemeColors().infoHover} hover:underline mr-2 inline-block`
                        }, `Datasheet ${datasheetLinks.length > 1 ? index + 1 : ''}`)
                    )
                ),

                // Storage Location Display
                React.createElement('div', {
                    className: `mb-3 p-2 bg-${UI.getThemeColors().background} rounded border border-${UI.getThemeColors().borderLight}`
                },
                    React.createElement('div', {
                        className: `${UI.typography.small} text-${UI.getThemeColors().textMuted} mb-1`
                    }, "Storage:"),
                    React.createElement('div', {
                        className: `${UI.typography.small} text-${UI.getThemeColors().textSecondary}`
                    },
                        window.App.utils.formHelpers.formatStorageDisplay(
                            component.storage,
                            locations,
                            drawers,
                            cells
                        )
                    )
                ),

                // Component Marks (Favorite, Bookmark, Star)
                (component.favorite || component.bookmark || component.star) &&
                React.createElement('div', {
                    className: `flex space-x-1 mb-3`
                },
                    component.favorite && React.createElement('span', {
                        className: `${UI.tags.base} ${UI.tags.red}`,
                        title: "Favorite"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 inline mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                fillRule: "evenodd",
                                d: "M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z",
                                clipRule: "evenodd"
                            })
                        ),
                        "Fav"
                    ),

                    component.bookmark && React.createElement('span', {
                        className: `${UI.tags.base} ${UI.tags.indigo}`,
                        title: "Bookmark"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 inline mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                d: "M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"
                            })
                        ),
                        "Book"
                    ),

                    component.star && React.createElement('span', {
                        className: `${UI.tags.base} ${UI.tags.yellow}`,
                        title: "Star"
                    },
                        React.createElement('svg', {
                            xmlns: "http://www.w3.org/2000/svg",
                            className: "h-4 w-4 inline mr-1",
                            viewBox: "0 0 20 20",
                            fill: "currentColor"
                        },
                            React.createElement('path', {
                                d: "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
                            })
                        ),
                        "Star"
                    )
                ),

                // Action Buttons
                React.createElement('div', {
                    className: `flex justify-end space-x-2 border-t border-${UI.getThemeColors().borderLight} pt-3`
                },
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

    return React.createElement('div', null,
        React.createElement('div', { className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 mb-6" },
            components.length > 0 ? components.map(renderCard) : null,
            
            // Empty state message
            components.length === 0 &&
            React.createElement('div', { 
                className: "col-span-full p-8 text-center text-gray-500 bg-white rounded shadow" 
            }, "No components found.")
        )
    );
};

console.log("ViewCardInventory component loaded.");