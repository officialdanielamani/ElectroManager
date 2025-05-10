// js/utils/ui-constants.js

// Create a global namespace if it doesn't exist
window.App = window.App || {};
window.App.utils = window.App.utils || {};

/**
 * Central UI styling constants for the Electronics Inventory App.
 * Provides consistent styling across all components.
 */
window.App.utils.UI = {
    // Theme definitions
    themes: {
        // ─── LIGHT MODE ────────────────────────────────────────────────
        light: {
            name: 'Light',
            colors: {
                // Core theme colors
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
                accent: 'purple-500',
                accentHover: 'purple-600',

                // Page & component backgrounds
                background: 'gray-100',
                cardBackground: 'white',
                headerBackground: 'white',

                // Borders
                border: 'gray-200',
                borderLight: 'gray-100',
                borderDark: 'gray-300',

                // Text colors
                textPrimary: 'gray-900',
                textSecondary: 'gray-700',
                textMuted: 'gray-500',
                textLight: 'white'
            }
        },

        // ─── DARK MODE ─────────────────────────────────────────────────
        dark: {
            name: 'Dark',
            colors: {
                // Core theme colors
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
                accent: 'purple-400',
                accentHover: 'purple-300',

                // Page & component backgrounds
                background: 'gray-900',
                cardBackground: 'gray-800',
                headerBackground: 'gray-800',

                // Borders
                border: 'gray-700',
                borderLight: 'gray-600',
                borderDark: 'gray-600',

                // Text colors
                textPrimary: 'gray-100',
                textSecondary: 'gray-300',
                textMuted: 'gray-400',
                textLight: 'gray-100'
            }
        }

    },

    // Current theme (default to light)
    currentTheme: 'light',

    // NEW HELPER: Get a style with fallback
    getStyle: function (path, defaultValue = '') {
        // Handle direct paths like 'typography.small'
        if (typeof path === 'string') {
            const parts = path.split('.');
            let result = this;

            for (const part of parts) {
                if (result && result[part] !== undefined) {
                    result = result[part];
                } else {
                    return defaultValue;
                }
            }

            return result;
        }

        // Handle already resolved values
        return path !== undefined ? path : defaultValue;
    },

    // Function to set theme
    setTheme: function (themeName) {
        if (this.themes[themeName]) {
            this.currentTheme = themeName;

            // Get theme colors FIRST
            const themeColors = this.getThemeColors();

            // Update all the theme-based styles
            const styles = this.getThemeStyles();

            // Update all UI components
            this.buttons = styles.buttons;
            this.cards = styles.cards;
            this.typography = styles.typography;
            this.tables = styles.tables;
            this.status = styles.status;
            this.tags = styles.tags;
            this.modals = styles.modals;
            this.layout = styles.layout;
            // Add colors direct access (for components that need direct color values)
            this.colors = {
                primary: {
                    text: `text-${themeColors.primary}`,
                    bg: `bg-${themeColors.primary}`,
                    border: `border-${themeColors.primary}`,
                    hover: `hover:bg-${themeColors.primaryHover}`
                },
                secondary: {
                    text: `text-${this.getThemeColors().secondary}`,
                    bg: `bg-${this.getThemeColors().secondary}`,
                    border: `border-${this.getThemeColors().secondary}`,
                    hover: `hover:bg-${this.getThemeColors().secondaryHover}`
                },
                danger: {
                    text: `text-${this.getThemeColors().danger}`,
                    bg: `bg-${this.getThemeColors().danger}`,
                    border: `border-${this.getThemeColors().danger}`,
                    hover: `hover:bg-${this.getThemeColors().dangerHover}`
                },
                success: {
                    text: `text-${this.getThemeColors().success}`,
                    bg: `bg-${this.getThemeColors().success}`,
                    border: `border-${this.getThemeColors().success}`,
                    hover: `hover:bg-${this.getThemeColors().successHover}`
                },
                warning: {
                    text: `text-${this.getThemeColors().warning}`,
                    bg: `bg-${this.getThemeColors().warning}`,
                    border: `border-${this.getThemeColors().warning}`,
                    hover: `hover:bg-${this.getThemeColors().warningHover}`
                },
                info: {
                    text: `text-${this.getThemeColors().info}`,
                    bg: `bg-${this.getThemeColors().info}`,
                    border: `border-${this.getThemeColors().info}`,
                    hover: `hover:bg-${this.getThemeColors().infoHover}`
                },
                accent: {
                    text: `text-${this.getThemeColors().accent}`,
                    bg: `bg-${this.getThemeColors().accent}`,
                    border: `border-${this.getThemeColors().accent}`,
                    hover: `hover:bg-${this.getThemeColors().accentHover}`
                },
                background: {
                    default: `bg-${this.getThemeColors().background}`,
                    alt: `bg-${this.getThemeColors().background.replace('900', '800').replace('100', '50')}`
                }
            };
            if (typeof document !== 'undefined') {
                // Get the body element
                const bodyElement = document.body;
                if (bodyElement) {
                    bodyElement.classList.remove('bg-gray-100', 'bg-gray-900');
                    bodyElement.classList.add(`bg-${themeColors.background}`);
                    bodyElement.classList.add(`text-${themeColors.textPrimary}`);
                }

                try {
                    if (typeof localStorage !== 'undefined') {
                        localStorage.setItem('electronicsTheme', themeName);
                    }
                } catch (e) {
                    console.warn('Failed to save theme preference:', e);
                }
            }

            console.log(`Theme switched to ${this.themes[themeName].name}`);
            return true;
        }
        return false;
    },


    // Get current theme colors
    getThemeColors: function () {
        return this.themes[this.currentTheme].colors;
    },

    // Function to generate dynamic styles based on current theme
    getThemeStyles: function () {
        const colors = this.getThemeColors();

        return {
            buttons: {
                // Standard buttons
                primary: `px-4 py-2 bg-${colors.primary} text-${colors.textLight} rounded shadow hover:bg-${colors.primaryHover} transition duration-150 ease-in-out`,
                secondary: `px-4 py-2 bg-${colors.secondary} text-${colors.textPrimary} rounded shadow hover:bg-${colors.secondaryHover} transition duration-150 ease-in-out`,
                danger: `px-4 py-2 bg-${colors.danger} text-${colors.textLight} rounded shadow hover:bg-${colors.dangerHover} transition duration-150 ease-in-out`,
                success: `px-4 py-2 bg-${colors.success} text-${colors.textLight} rounded shadow hover:bg-${colors.successHover} transition duration-150 ease-in-out`,
                info: `px-4 py-2 bg-${colors.info} text-${colors.textLight} rounded shadow hover:bg-${colors.infoHover} transition duration-150 ease-in-out`,
                warning: `px-4 py-2 bg-${colors.warning} text-${colors.textLight} rounded shadow hover:bg-${colors.warningHover} transition duration-150 ease-in-out`,
                accent: `px-4 py-2 bg-${colors.accent} text-${colors.textLight} rounded shadow hover:bg-${colors.accentHover} transition duration-150 ease-in-out`,

                // Small buttons
                small: {
                    primary: `px-2 py-1 bg-${colors.primary} text-${colors.textLight} text-xs rounded shadow hover:bg-${colors.primaryHover}`,
                    secondary: `px-2 py-1 bg-${colors.secondary} text-${colors.textPrimary} text-xs rounded shadow hover:bg-${colors.secondaryHover}`,
                    danger: `px-2 py-1 bg-${colors.danger} text-${colors.textLight} text-xs rounded shadow hover:bg-${colors.dangerHover}`,
                    success: `px-2 py-1 bg-${colors.success} text-${colors.textLight} text-xs rounded shadow hover:bg-${colors.successHover}`,
                    info: `px-2 py-1 bg-${colors.info} text-${colors.textLight} text-xs rounded shadow hover:bg-${colors.infoHover}`,
                    warning: `px-2 py-1 bg-${colors.warning} text-${colors.textLight} text-xs rounded shadow hover:bg-${colors.warningHover}`
                },

                // Icon buttons
                icon: {
                    primary: `w-8 h-8 flex items-center justify-center text-${colors.primary} hover:bg-${colors.primary.replace('500', '100').replace('400', '900')} rounded-full`,
                    danger: `w-8 h-8 flex items-center justify-center text-${colors.danger} hover:bg-${colors.danger.replace('500', '100').replace('400', '900')} rounded-full`,
                    success: `w-8 h-8 flex items-center justify-center text-${colors.success} hover:bg-${colors.success.replace('500', '100').replace('400', '900')} rounded-full`
                }
            },

            // Cards styling
            cards: {
                container: `bg-${colors.cardBackground} rounded-lg shadow border border-${colors.border} hover:shadow-md transition-shadow duration-150`,
                header: `p-4 border-b border-${colors.border} text-${colors.textPrimary}`,
                body: `p-4 text-${colors.textSecondary}`,
                footer: `p-4 border-t border-${colors.border} bg-${colors.cardBackground.replace('white', 'gray-50').replace('gray-800', 'gray-700')} text-${colors.textSecondary}`
            },

            // Typography styling
            typography: {
                weight: {
                    normal: 'font-normal',
                    medium: 'font-medium',
                    semibold: 'font-semibold',
                    bold: 'font-bold'
                },
                title: `text-xl font-semibold text-${colors.textPrimary}`,
                subtitle: `text-lg font-medium text-${colors.textSecondary}`,
                sectionTitle: `font-medium text-${colors.textSecondary}`,
                body: `text-sm text-${colors.textSecondary}`,
                small: `text-xs text-${colors.textMuted}`,
                heading: {
                    h1: `text-3xl font-bold text-${colors.textPrimary}`,
                    h2: `text-2xl font-semibold text-${colors.textPrimary}`,
                    h3: `text-xl font-semibold text-${colors.textSecondary}`,
                    h4: `text-lg font-medium text-${colors.textSecondary}`,
                    h5: `text-base font-medium text-${colors.textSecondary}`,
                    h6: `text-sm font-medium text-${colors.textSecondary}`
                }
            },

            // Form styling
            forms: {
                input: `w-full p-2 border border-${colors.border} rounded shadow-sm bg-${colors.cardBackground} text-${colors.textPrimary} focus:ring-${colors.primary} focus:border-${colors.primary}`,
                select: `w-full p-2 border border-${colors.border} rounded shadow-sm bg-${colors.cardBackground} text-${colors.textPrimary} focus:ring-${colors.primary} focus:border-${colors.primary}`,
                checkbox: `h-4 w-4 text-${colors.primary} border-${colors.border} rounded focus:ring-${colors.primary}`,
                radio: `h-4 w-4 text-${colors.primary} border-${colors.border} focus:ring-${colors.primary}`,
                label: `block mb-1 text-sm font-medium text-${colors.textSecondary}`,
                textarea: `w-full p-2 border border-${colors.border} rounded shadow-sm bg-${colors.cardBackground} text-${colors.textPrimary} focus:ring-${colors.primary} focus:border-${colors.primary}`,
                error: `text-${colors.danger} text-xs mt-1`,
                hint: `text-xs text-${colors.textMuted} mt-1`
            },

            // Table styling
            tables: {
                container: `min-w-full bg-${colors.cardBackground} divide-y divide-${colors.border} rounded-lg shadow`,
                header: {
                    row: `bg-${colors.headerBackground}`,
                    cell: `py-3 px-4 text-center text-xs font-medium text-${colors.textMuted} uppercase tracking-wider`
                },
                body: {
                    // Updated row styling with proper theme background colors and selection highlighting
                    row: `hover:bg-${colors.background} border-b border-${colors.borderLight} bg-${colors.cardBackground}`,
                    rowSelected: `bg-${colors.primary.replace('500', '50').replace('400', '950')} hover:bg-${colors.primary.replace('500', '100').replace('400', '900')} border-b border-${colors.borderLight}`,
                    cell: `px-4 py-2 whitespace-nowrap text-${colors.textSecondary}`,
                    cellAction: `px-4 py-2 whitespace-nowrap text-center text-sm font-medium`
                },
            },

            // Status indicators
            status: {
                success: `bg-${colors.success.replace('500', '100').replace('400', '900')} text-${colors.success.replace('500', '800').replace('400', '300')} border border-${colors.success.replace('500', '200').replace('400', '800')} p-3 rounded`,
                error: `bg-${colors.danger.replace('500', '100').replace('400', '900')} text-${colors.danger.replace('500', '800').replace('400', '300')} border border-${colors.danger.replace('500', '200').replace('400', '800')} p-3 rounded`,
                warning: `bg-${colors.warning.replace('500', '100').replace('400', '900')} text-${colors.warning.replace('500', '800').replace('400', '300')} border border-${colors.warning.replace('500', '200').replace('400', '800')} p-3 rounded`,
                info: `bg-${colors.info.replace('500', '100').replace('400', '900')} text-${colors.info.replace('500', '800').replace('400', '300')} border border-${colors.info.replace('500', '200').replace('400', '800')} p-3 rounded`
            },

            // Tags
            tags: {
                base: 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                primary: `bg-${colors.primary.replace('500', '100').replace('400', '900')} text-${colors.primary.replace('500', '800').replace('400', '300')}`,
                gray: `bg-${colors.secondary.replace('300', '100').replace('600', '900')} text-${colors.textSecondary}`,
                red: `bg-${colors.danger.replace('500', '100').replace('400', '900')} text-white`,  // Improved contrast for "Low Stock"
                green: `bg-${colors.success.replace('500', '100').replace('400', '900')} text-${colors.success.replace('500', '800').replace('400', '300')}`,
                yellow: `bg-${colors.warning.replace('500', '100').replace('400', '900')} text-${colors.warning.replace('500', '800').replace('400', '300')}`,
                indigo: `bg-${colors.info.replace('500', '100').replace('400', '900')} text-${colors.info.replace('500', '800').replace('400', '300')}`
            },

            // Layout related
            layout: {
                section: 'mb-6',
                sectionAlt: `mb-6 bg-${colors.background} p-4 rounded-lg border border-${colors.border}`
            },

            // Modal styling
            modals: {
                backdrop: 'fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4 z-30',
                container: `bg-${colors.cardBackground} rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col`,
                header: `flex justify-between items-center p-5 border-b border-${colors.border} text-${colors.textPrimary} flex-shrink-0`,
                body: `p-6 overflow-y-auto flex-grow text-${colors.textSecondary}`,
                footer: `flex justify-end space-x-3 p-4 border-t border-${colors.border} bg-${colors.cardBackground.replace('white', 'gray-50').replace('gray-800', 'gray-700')} rounded-b-lg flex-shrink-0`
            },
        };
    },

    // Initialize default styles based on initial theme
    initialize: function () {
        // Set default theme first
        this.currentTheme = 'light';

        // Try to load from localStorage if available
        try {
            if (typeof localStorage !== 'undefined') {
                const savedTheme = localStorage.getItem('electronicsTheme');
                if (savedTheme && this.themes[savedTheme]) {
                    this.currentTheme = savedTheme;
                }
            }
        } catch (e) {
            console.warn('Error loading theme from localStorage:', e);
        }

        // Ensure theme exists
        if (!this.themes[this.currentTheme]) {
            console.warn(`Theme "${this.currentTheme}" not found, falling back to light theme`);
            this.currentTheme = 'light';
        }

        // Get theme colors BEFORE getting styles
        const themeColors = this.getThemeColors();

        // Get theme styles based on current theme
        const styles = this.getThemeStyles();

        // Initialize all UI component styles
        this.buttons = styles.buttons;
        this.cards = styles.cards;
        this.typography = styles.typography;
        this.forms = styles.forms;
        this.tables = styles.tables;
        this.status = styles.status;
        this.tags = styles.tags;
        this.modals = styles.modals;
        this.layout = styles.layout;

        // Add colors direct access
        const colors = this.getThemeColors();
        this.colors = {
            primary: {
                text: `text-${themeColors.primary}`,
                bg: `bg-${themeColors.primary}`,
                border: `border-${colors.primary}`,
                hover: `hover:bg-${colors.primaryHover}`
            },
            secondary: {
                text: `text-${colors.secondary}`,
                bg: `bg-${colors.secondary}`,
                border: `border-${colors.secondary}`,
                hover: `hover:bg-${colors.secondaryHover}`
            },
            danger: {
                text: `text-${colors.danger}`,
                bg: `bg-${colors.danger}`,
                border: `border-${colors.danger}`,
                hover: `hover:bg-${colors.dangerHover}`
            },
            success: {
                text: `text-${colors.success}`,
                bg: `bg-${colors.success}`,
                border: `border-${colors.success}`,
                hover: `hover:bg-${colors.successHover}`
            },
            warning: {
                text: `text-${colors.warning}`,
                bg: `bg-${colors.warning}`,
                border: `border-${colors.warning}`,
                hover: `hover:bg-${colors.warningHover}`
            },
            info: {
                text: `text-${colors.info}`,
                bg: `bg-${colors.info}`,
                border: `border-${colors.info}`,
                hover: `hover:bg-${colors.infoHover}`
            },
            accent: {
                text: `text-${colors.accent}`,
                bg: `bg-${colors.accent}`,
                border: `border-${colors.accent}`,
                hover: `hover:bg-${colors.accentHover}`
            },
            background: {
                default: `bg-${colors.background}`,
                alt: `bg-${colors.background.replace('900', '800').replace('100', '50')}`
            }
        };

        // Standard utility helpers that don't change with theme
        this.utils = {
            divider: 'border-t my-4',
            shadowSm: 'shadow-sm',
            shadow: 'shadow',
            shadowMd: 'shadow-md',
            rounded: 'rounded-md',
            roundedLg: 'rounded-lg',
            roundedFull: 'rounded-full',
            border: 'border',
            borderTop: 'border-t',
            borderBottom: 'border-b'
        };
        // Update body class with themeColors
        const bodyElement = document.body;
        if (bodyElement) {
            bodyElement.classList.remove('bg-gray-100', 'bg-gray-900');
            bodyElement.classList.add(`bg-${themeColors.background}`);
            bodyElement.classList.add(`text-${themeColors.textPrimary}`);
        }

        console.log(`UI initialized with ${this.currentTheme} theme`);

        console.log(`UI initialized with ${this.currentTheme} theme`);
        return this;
    },

    // Save current theme to localStorage
    saveThemePreference: function () {
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('electronicsTheme', this.currentTheme);
            return true;
        }
        return false;
    },

    // Load theme preference from localStorage
    loadThemePreference: function () {
        if (typeof localStorage !== 'undefined') {
            const savedTheme = localStorage.getItem('electronicsTheme');
            if (savedTheme && this.themes[savedTheme]) {
                this.currentTheme = savedTheme;
                return savedTheme;
            }
        }
        return null;
    },
};

// Initialize UI with default theme
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.App.utils.UI.initialize();
    });
} else {
    // If document is already loaded, initialize immediately
    window.App.utils.UI.initialize();
}

console.log("UI constants loaded with improved theme support.");