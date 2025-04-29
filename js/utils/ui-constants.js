// js/utils/ui-constants.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Central UI styling constants for the Electronics Inventory App.
 * Provides consistent styling across all components.
 */
window.App.utils.UI = {
    // Themes system
    themes: {
        light: {
            name: 'Light',
            colors: {
                primary: 'blue-500',
                primaryHover: 'blue-600',
                secondary: 'gray-300',
                secondaryHover: 'gray-400',
                danger: 'red-500',
                dangerHover: 'red-600',
                success: 'green-500',
                successHover: 'green-600',
                warning: 'yellow-500',
                warningHover: 'yellow-600',
                info: 'indigo-500',
                infoHover: 'indigo-600',
                background: 'gray-100',
                cardBackground: 'white',
                border: 'gray-200',
                textPrimary: 'gray-800',
                textSecondary: 'gray-600',
                textMuted: 'gray-400'
            }
        },
        
        dark: {
            name: 'Dark',
            colors: {
                primary: 'blue-400',
                primaryHover: 'blue-300',
                secondary: 'gray-600',
                secondaryHover: 'gray-500',
                danger: 'red-400',
                dangerHover: 'red-300',
                success: 'green-400',
                successHover: 'green-300',
                warning: 'yellow-400',
                warningHover: 'yellow-300',
                info: 'indigo-400',
                infoHover: 'indigo-300',
                background: 'gray-900',
                cardBackground: 'gray-800',
                border: 'gray-700',
                textPrimary: 'white',
                textSecondary: 'gray-300',
                textMuted: 'gray-500'
            }
        },
        
        keqing: {
            name: 'Purple-Gold',
            colors: {
                primary: 'purple-600',
                primaryHover: 'purple-700',
                secondary: 'yellow-500',
                secondaryHover: 'yellow-600',
                danger: 'red-500',
                dangerHover: 'red-600',
                success: 'purple-400',
                successHover: 'purple-500',
                warning: 'yellow-400',
                warningHover: 'yellow-500',
                info: 'indigo-400',
                infoHover: 'indigo-500',
                background: 'purple-50',
                cardBackground: 'white',
                border: 'purple-200',
                textPrimary: 'purple-900',
                textSecondary: 'purple-700',
                textMuted: 'purple-300'
            },
            gradients: {
                primary: 'bg-gradient-to-r from-purple-500 to-purple-700',
                accent: 'bg-gradient-to-r from-yellow-400 to-yellow-600'
            },
            specialButtons: {
                electro: 'px-4 py-2 bg-gradient-to-r from-purple-500 to-indigo-500 text-white rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200'
            }
        }
    },

    // Current theme (default to light)
    currentTheme: 'light',

    // Function to set theme
    setTheme: function(themeName) {
        if (this.themes[themeName]) {
            this.currentTheme = themeName;
            console.log(`Theme switched to ${this.themes[themeName].name}`);
            return true;
        }
        return false;
    },

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
        hint: 'text-xs text-gray-500 mt-1',
        group: 'mb-4',
        inputGroup: 'flex rounded-md shadow-sm',
        inputIcon: 'absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400',
        inputWithIcon: 'pl-10',
        inputSmall: 'p-1.5 text-sm',
        inputLarge: 'p-3 text-base',
        labelInline: 'inline-flex items-center mb-0 mr-4'
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
    },

    // Toast/Notification Styles
    toast: {
        container: "fixed bottom-4 right-4 z-50 max-w-md",
        success: "bg-green-100 border-green-500 text-green-800 p-4 rounded shadow-md border-l-4",
        error: "bg-red-100 border-red-500 text-red-800 p-4 rounded shadow-md border-l-4",
        warning: "bg-yellow-100 border-yellow-500 text-yellow-800 p-4 rounded shadow-md border-l-4",
        info: "bg-blue-100 border-blue-500 text-blue-800 p-4 rounded shadow-md border-l-4"
    },

    // Badges (small indicator elements)
    badges: {
        base: "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        small: "inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium",
        primary: "bg-blue-100 text-blue-800",
        green: "bg-green-100 text-green-800",
        red: "bg-red-100 text-red-800",
        yellow: "bg-yellow-100 text-yellow-800",
        gray: "bg-gray-100 text-gray-800",
        purple: "bg-purple-100 text-purple-800",
        count: "inline-flex items-center justify-center h-5 w-5 rounded-full text-xs font-medium"
    },

    // Drawer/Panel/Menu Styles
    drawers: {
        container: "fixed inset-0 overflow-hidden z-40",
        overlay: "absolute inset-0 bg-gray-500 bg-opacity-75 transition-opacity",
        panel: "fixed inset-y-0 right-0 max-w-full flex",
        content: "relative w-screen max-w-md h-full bg-white shadow-xl flex flex-col",
        header: "px-4 py-3 border-b border-gray-200 bg-gray-50",
        body: "flex-1 overflow-y-auto p-4",
        footer: "px-4 py-3 border-t border-gray-200 bg-gray-50"
    },

    // Animation and Transitions
    transitions: {
        default: "transition-all duration-200 ease-in-out",
        slow: "transition-all duration-300 ease-in-out",
        fast: "transition-all duration-100 ease-in-out",
        none: ""
    },

    // Loader/Spinner
    loaders: {
        container: "flex justify-center items-center",
        spinner: "animate-spin h-5 w-5 text-blue-500",
        spinnerLarge: "animate-spin h-8 w-8 text-blue-500",
        spinnerSmall: "animate-spin h-4 w-4 text-blue-500",
        overlay: "fixed inset-0 bg-black bg-opacity-30 flex justify-center items-center z-50"
    },

    // Pagination
    pagination: {
        container: "flex justify-center mt-4",
        list: "inline-flex shadow-sm rounded-md",
        item: "px-3 py-1 border-r border-gray-200 bg-white hover:bg-gray-50",
        itemActive: "px-3 py-1 border-r border-gray-200 bg-blue-500 text-white",
        itemFirst: "px-3 py-1 border-r border-gray-200 bg-white hover:bg-gray-50 rounded-l-md",
        itemLast: "px-3 py-1 bg-white hover:bg-gray-50 rounded-r-md",
    },

    // Function to generate dynamic styles based on current theme
    getThemeStyles: function() {
        const theme = this.themes[this.currentTheme];
        
        return {
            buttons: {
                primary: `px-4 py-2 bg-${theme.colors.primary} text-${theme.colors.cardBackground} rounded shadow hover:bg-${theme.colors.primaryHover} transition duration-150 ease-in-out`,
                secondary: `px-4 py-2 bg-${theme.colors.secondary} text-${theme.colors.textPrimary} rounded hover:bg-${theme.colors.secondaryHover} transition duration-150 ease-in-out`,
                danger: `px-4 py-2 bg-${theme.colors.danger} text-white rounded shadow hover:bg-${theme.colors.dangerHover} transition duration-150 ease-in-out`,
                success: `px-4 py-2 bg-${theme.colors.success} text-white rounded shadow hover:bg-${theme.colors.successHover} transition duration-150 ease-in-out`,
                
                // Small variants
                small: {
                    primary: `px-2 py-1 bg-${theme.colors.primary} text-white text-xs rounded shadow hover:bg-${theme.colors.primaryHover}`,
                    secondary: `px-2 py-1 bg-${theme.colors.secondary} text-${theme.colors.textPrimary} text-xs rounded shadow hover:bg-${theme.colors.secondaryHover}`,
                    danger: `px-2 py-1 bg-${theme.colors.danger} text-white text-xs rounded shadow hover:bg-${theme.colors.dangerHover}`,
                    success: `px-2 py-1 bg-${theme.colors.success} text-white text-xs rounded shadow hover:bg-${theme.colors.successHover}`
                },

                // Icon buttons
                icon: {
                    base: 'p-2 rounded-full transition duration-150',
                    primary: `p-2 text-${theme.colors.primary} hover:bg-${theme.colors.primary.replace('500', '100')} rounded-full`,
                    danger: `p-2 text-${theme.colors.danger} hover:bg-${theme.colors.danger.replace('500', '100')} rounded-full`,
                    success: `p-2 text-${theme.colors.success} hover:bg-${theme.colors.success.replace('500', '100')} rounded-full`
                }
            },
            
            // Cards, typography, forms, etc. follow the same pattern
            cards: {
                container: `bg-${theme.colors.cardBackground} rounded-lg shadow border border-${theme.colors.border} hover:shadow-md transition-shadow duration-150`,
                header: `p-4 border-b border-${theme.colors.border}`,
                body: `p-4`,
                footer: `p-4 border-t border-${theme.colors.border} bg-${theme.colors.background}`
            },
            
            typography: {
                title: `text-xl font-semibold text-${theme.colors.textPrimary}`,
                subtitle: `text-lg font-medium text-${theme.colors.textSecondary}`,
                body: `text-sm text-${theme.colors.textSecondary}`,
                small: `text-xs text-${theme.colors.textMuted}`,
                heading: {
                    h1: `text-3xl font-bold text-${theme.colors.textPrimary}`,
                    h2: `text-2xl font-semibold text-${theme.colors.textPrimary}`,
                    h3: `text-xl font-semibold text-${theme.colors.textSecondary}`,
                    h4: `text-lg font-medium text-${theme.colors.textSecondary}`,
                    h5: `text-base font-medium text-${theme.colors.textSecondary}`,
                    h6: `text-sm font-medium text-${theme.colors.textSecondary}`
                }
            },
            
            // Additional themed components...
            status: {
                success: `bg-${theme.colors.success.replace('500', '100')} text-${theme.colors.success.replace('500', '800')} border border-${theme.colors.success.replace('500', '200')} p-3 rounded`,
                error: `bg-${theme.colors.danger.replace('500', '100')} text-${theme.colors.danger.replace('500', '800')} border border-${theme.colors.danger.replace('500', '200')} p-3 rounded`,
                warning: `bg-${theme.colors.warning.replace('500', '100')} text-${theme.colors.warning.replace('500', '800')} border border-${theme.colors.warning.replace('500', '200')} p-3 rounded`,
                info: `bg-${theme.colors.info.replace('500', '100')} text-${theme.colors.info.replace('500', '800')} border border-${theme.colors.info.replace('500', '200')} p-3 rounded`
            },
            
            tags: {
                base: 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                primary: `bg-${theme.colors.primary.replace('500', '100')} text-${theme.colors.primary.replace('500', '800')}`,
                gray: `bg-${theme.colors.secondary.replace('300', '100')} text-${theme.colors.textSecondary}`,
                red: `bg-${theme.colors.danger.replace('500', '100')} text-${theme.colors.danger.replace('500', '800')}`,
                green: `bg-${theme.colors.success.replace('500', '100')} text-${theme.colors.success.replace('500', '800')}`,
                yellow: `bg-${theme.colors.warning.replace('500', '100')} text-${theme.colors.warning.replace('500', '800')}`,
                indigo: `bg-${theme.colors.info.replace('500', '100')} text-${theme.colors.info.replace('500', '800')}`
            }
        };
    }
};

console.log("UI constants loaded.");