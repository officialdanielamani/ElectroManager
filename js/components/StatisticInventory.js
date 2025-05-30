// js/components/StatisticInventory.js

window.App = window.App || {};
window.App.components = window.App.components || {};

/**
 * StatisticInventory - Displays inventory summary statistics and category counts
 */
window.App.components.StatisticInventory = ({
    // Data props
    components = [],
    categories = [],
    locations = [],
    drawers = [],
    cells = [],
    footprints = [],
    lowStockConfig = {},
    
    // Configuration
    currencySymbol = 'RM',
    showTotalValue = false
}) => {
    const { UI, helpers } = window.App.utils;

    // Calculate statistics
    const totalComponents = components.length;
    const totalItems = components.reduce((s, c) => s + (Number(c.quantity) || 0), 0);
    const totalValue = helpers.calculateTotalInventoryValue(components);
    const lowStockCount = components.filter(c => helpers.isLowStock(c, lowStockConfig)).length;
    const outOfStockCount = components.filter(c => (Number(c.quantity) || 0) === 0).length;
    const categoryCounts = helpers.calculateCategoryCounts(components);

    // Render individual summary card
    const renderSummaryCard = (label, value, colorClass = UI.colors.primary.text) => {
        const cardClass = `${UI.cards.container} text-center p-4`;
        const labelClass = `${UI.typography.small} font-medium mb-1`;
        const valueClass = `${UI.typography.heading.h2} ${colorClass}`;

        return React.createElement('div', { className: cardClass },
            React.createElement('div', { className: labelClass }, label),
            React.createElement('div', { className: valueClass }, value)
        );
    };

    return React.createElement('div', { className: UI.layout.sectionAlt },
        // Section title
        React.createElement('h2', { 
            className: `${UI.typography.subtitle} mb-3` 
        }, 'Inventory Summary'),

        // Summary cards grid
        React.createElement('div', {
            className: 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4'
        },
            renderSummaryCard('Components', totalComponents, UI.colors.primary.text),
            renderSummaryCard('Total Items', totalItems, UI.colors.success.text),
            showTotalValue && renderSummaryCard('Total Value', helpers.formatCurrency(totalValue, currencySymbol), UI.colors.accent.text),
            renderSummaryCard('Categories', categories.length, UI.colors.info.text),
            renderSummaryCard('Low Stock', lowStockCount, lowStockCount ? UI.colors.danger.text : UI.colors.secondary.text),
            renderSummaryCard('Out of Stock', outOfStockCount, outOfStockCount ? UI.colors.danger.text : UI.colors.secondary.text),
            renderSummaryCard('Locations', locations.length, UI.colors.info.text),
            renderSummaryCard('Drawers', drawers.length, UI.colors.info.text),
            renderSummaryCard('Cells', cells.length, UI.colors.info.text),
            renderSummaryCard('Footprints', footprints.length, UI.colors.info.text)
        ),

        // Category breakdown (if components exist)
        totalComponents > 0 && React.createElement('div', {
            className: `${UI.utils.borderTop} pt-3 mt-3 border-${UI.getThemeColors().border}`
        },
            React.createElement('h3', { 
                className: `${UI.typography.subtitle} mb-2` 
            }, 'Item Counts by Category'),
            
            React.createElement('div', { className: 'flex flex-wrap gap-3' },
                categoryCounts.length ? categoryCounts.map(([cat, cnt]) => 
                    React.createElement('div', {
                        key: cat,
                        className: `${UI.cards.container} px-3 py-1`
                    },
                        React.createElement('span', { 
                            className: `${UI.typography.small} mr-1` 
                        }, `${cat}:`),
                        React.createElement('span', { 
                            className: `${UI.typography.small} font-semibold ${UI.colors.primary.text}` 
                        }, cnt)
                    )
                ) : React.createElement('p', { 
                    className: `${UI.typography.small} italic` 
                }, 'No items with categories found.')
            )
        )
    );
};

console.log("StatisticInventory component loaded.");