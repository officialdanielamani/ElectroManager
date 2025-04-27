// js/utils/ui-constants.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Central UI styling constants for the Electronics Inventory App.
 * Provides consistent styling across all components.
 */
window.App.utils.UI = {
    // Color palette (Tailwind colors as reference)
    colors: {
        primary: {
            light: 'bg-blue-400',
            default: 'bg-blue-500',
            dark: 'bg-blue-600',
            text: 'text-blue-500',
            border: 'border-blue-500',
            hover: 'hover:bg-blue-600',
            focusRing: 'focus:ring-blue-500',
            focusBorder: 'focus:border-blue-500'
        },
        secondary: {
            light: 'bg-gray-200',
            default: 'bg-gray-300',
            dark: 'bg-gray-400',
            text: 'text-gray-700',
            border: 'border-gray-300',
            hover: 'hover:bg-gray-400',
            focusRing: 'focus:ring-gray-400',
            focusBorder: 'focus:border-gray-400'
        },
        success: {
            light: 'bg-green-400',
            default: 'bg-green-500',
            dark: 'bg-green-600',
            text: 'text-green-500',
            border: 'border-green-500',
            hover: 'hover:bg-green-600'
        },
        danger: {
            light: 'bg-red-400',
            default: 'bg-red-500',
            dark: 'bg-red-600',
            text: 'text-red-500',
            border: 'border-red-500',
            hover: 'hover:bg-red-600'
        },
        warning: {
            light: 'bg-yellow-400',
            default: 'bg-yellow-500',
            dark: 'bg-yellow-600',
            text: 'text-yellow-500',
            border: 'border-yellow-500',
            hover: 'hover:bg-yellow-600'
        },
        info: {
            light: 'bg-indigo-400',
            default: 'bg-indigo-500',
            dark: 'bg-indigo-600',
            text: 'text-indigo-500',
            border: 'border-indigo-500',
            hover: 'hover:bg-indigo-600'
        },
        accent: {
            light: 'bg-purple-400',
            default: 'bg-purple-500',
            dark: 'bg-purple-600',
            text: 'text-purple-500',
            border: 'border-purple-500',
            hover: 'hover:bg-purple-600'
        },
        background: {
            page: 'bg-gray-100',
            card: 'bg-white',
            alt: 'bg-gray-50'
        }
    },

    // Font sizes
    typography: {
        text: {
            xs: 'text-xs',
            sm: 'text-sm',
            base: 'text-base',
            lg: 'text-lg',
            xl: 'text-xl',
            '2xl': 'text-2xl',
            '3xl': 'text-3xl',
        },
        weight: {
            normal: 'font-normal',
            medium: 'font-medium',
            semibold: 'font-semibold',
            bold: 'font-bold'
        },
        title: 'text-xl font-semibold text-gray-800',
        subtitle: 'text-lg font-medium text-gray-700',
        sectionTitle: 'font-medium text-gray-700',
        body: 'text-sm text-gray-600',
        small: 'text-xs text-gray-500',
        heading: {
            h1: 'text-3xl font-bold text-gray-800',
            h2: 'text-2xl font-semibold text-gray-800',
            h3: 'text-xl font-semibold text-gray-700',
            h4: 'text-lg font-medium text-gray-700',
            h5: 'text-base font-medium text-gray-700',
            h6: 'text-sm font-medium text-gray-700'
        }
    },

    // Spacing and layout
    spacing: {
        xs: 'p-1',
        sm: 'p-2',
        md: 'p-4',
        lg: 'p-6',
        xl: 'p-8'
    },

    // Button styles
    buttons: {
        // Standard sizes
        base: 'rounded shadow transition duration-150 ease-in-out',
        primary: 'px-4 py-2 bg-blue-500 text-white rounded shadow hover:bg-blue-600 transition duration-150 ease-in-out',
        secondary: 'px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition duration-150 ease-in-out',
        danger: 'px-4 py-2 bg-red-500 text-white rounded shadow hover:bg-red-600 transition duration-150 ease-in-out',
        success: 'px-4 py-2 bg-green-500 text-white rounded shadow hover:bg-green-600 transition duration-150 ease-in-out',
        info: 'px-4 py-2 bg-indigo-500 text-white rounded shadow hover:bg-indigo-600 transition duration-150 ease-in-out',
        warning: 'px-4 py-2 bg-yellow-500 text-white rounded shadow hover:bg-yellow-600 transition duration-150 ease-in-out',
        accent: 'px-4 py-2 bg-purple-500 text-white rounded shadow hover:bg-purple-600 transition duration-150 ease-in-out',
        // Small sizes
        small: {
            primary: 'px-2 py-1 bg-blue-500 text-white text-xs rounded shadow hover:bg-blue-600',
            secondary: 'px-2 py-1 bg-gray-300 text-gray-700 text-xs rounded shadow hover:bg-gray-400',
            danger: 'px-2 py-1 bg-red-500 text-white text-xs rounded shadow hover:bg-red-600',
            success: 'px-2 py-1 bg-green-500 text-white text-xs rounded shadow hover:bg-green-600',
            info: 'px-2 py-1 bg-indigo-500 text-white text-xs rounded shadow hover:bg-indigo-600',
            warning: 'px-2 py-1 bg-yellow-500 text-white text-xs rounded shadow hover:bg-yellow-600',
            accent: 'px-2 py-1 bg-purple-500 text-white text-xs rounded shadow hover:bg-purple-600',
        },
        // Icon buttons
        icon: {
            base: 'p-2 rounded-full transition duration-150',
            primary: 'p-2 text-blue-500 hover:bg-blue-100 rounded-full',
            danger: 'p-2 text-red-500 hover:bg-red-100 rounded-full',
            success: 'p-2 text-green-500 hover:bg-green-100 rounded-full'
        }
    },

    // Form styles
    forms: {
        input: 'w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500',
        select: 'w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500',
        checkbox: 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
        radio: 'h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500',
        label: 'block mb-1 text-sm font-medium text-gray-700',
        textarea: 'w-full p-2 border border-gray-300 rounded shadow-sm focus:ring-blue-500 focus:border-blue-500',
        error: 'text-red-500 text-xs mt-1',
        hint: 'text-xs text-gray-500 mt-1'
    },

    // Table styles
    tables: {
        container: 'min-w-full bg-white divide-y divide-gray-200 rounded-lg shadow',
        header: {
            row: 'bg-gray-50',
            cell: 'py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider'
        },
        body: {
            row: 'hover:bg-gray-50',
            cell: 'px-4 py-2 whitespace-nowrap',
            cellAction: 'px-4 py-2 whitespace-nowrap text-center text-sm font-medium'
        }
    },

    // Card styles
    cards: {
        container: 'bg-white rounded-lg shadow border border-gray-200 hover:shadow-md transition-shadow duration-150',
        header: 'p-4 border-b border-gray-200',
        body: 'p-4',
        footer: 'p-4 border-t border-gray-200 bg-gray-50'
    },

    // Modal styles
    modals: {
        backdrop: 'fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4 z-30',
        container: 'bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col',
        header: 'flex justify-between items-center p-5 border-b border-gray-200 flex-shrink-0',
        body: 'p-6 overflow-y-auto flex-grow',
        footer: 'flex justify-end space-x-3 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg flex-shrink-0'
    },

    // Status indicators & tags
    status: {
        success: 'bg-green-100 text-green-800 border border-green-200 p-3 rounded',
        error: 'bg-red-100 text-red-800 border border-red-200 p-3 rounded',
        warning: 'bg-yellow-100 text-yellow-800 border border-yellow-200 p-3 rounded',
        info: 'bg-blue-100 text-blue-800 border border-blue-200 p-3 rounded'
    },
    tags: {
        base: 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        primary: 'bg-blue-100 text-blue-800',
        gray: 'bg-gray-100 text-gray-800',
        red: 'bg-red-100 text-red-800',
        green: 'bg-green-100 text-green-800',
        yellow: 'bg-yellow-100 text-yellow-800',
        indigo: 'bg-indigo-100 text-indigo-800'
    },

    // Grid and layout helpers
    grid: {
        container: 'grid gap-4',
        cols1: 'grid-cols-1',
        cols2: 'md:grid-cols-2',
        cols3: 'md:grid-cols-3',
        cols4: 'md:grid-cols-4'
    },
    layout: {
        section: 'mb-6',
        sectionAlt: 'mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200'
    },

    // Utility classes
    utils: {
        divider: 'border-t border-gray-200 my-4',
        shadowSm: 'shadow-sm',
        shadow: 'shadow',
        shadowMd: 'shadow-md',
        roundedSm: 'rounded',
        rounded: 'rounded-md',
        roundedLg: 'rounded-lg',
        roundedFull: 'rounded-full',
        border: 'border border-gray-200',
        borderTop: 'border-t border-gray-200',
        borderBottom: 'border-b border-gray-200'
    }
};

console.log("UI constants loaded.");