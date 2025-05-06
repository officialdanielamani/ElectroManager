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
        },

        // ─── KEQING (PURPLE & GOLD) ────────────────────────────────────
        keqing: {
            name: 'Keqing',
            colors: {
                // Core theme colors
                primary: 'purple-500',
                primaryHover: 'purple-600',
                secondary: 'yellow-400',
                secondaryHover: 'yellow-500',
                danger: 'red-400',
                dangerHover: 'red-500',
                success: 'green-400',
                successHover: 'green-500',
                warning: 'yellow-400',
                warningHover: 'yellow-500',
                info: 'indigo-400',
                infoHover: 'indigo-500',
                accent: 'yellow-400',
                accentHover: 'yellow-500',
                
                // Page & component backgrounds
                background: 'purple-900',
                cardBackground: 'purple-800',
                headerBackground: 'purple-800',
                
                // Borders
                border: 'purple-700',
                borderLight: 'purple-600',
                borderDark: 'purple-700',
                
                // Text colors
                textPrimary: 'yellow-300',
                textSecondary: 'yellow-200',
                textMuted: 'purple-300',
                textLight: 'yellow-300'
            }
        }
    },

    // Current theme (default to light)
    currentTheme: 'light',

    // Function to set theme
    setTheme: function(themeName) {
        if (this.themes[themeName]) {
            this.currentTheme = themeName;
            
            // Update all the theme-based styles
            this.buttons = this.getThemeStyles().buttons;
            this.cards = this.getThemeStyles().cards;
            this.typography = this.getThemeStyles().typography;
            this.forms = this.getThemeStyles().forms;
            this.tables = this.getThemeStyles().tables;
            this.status = this.getThemeStyles().status;
            this.tags = this.getThemeStyles().tags;
            
            console.log(`Theme switched to ${this.themes[themeName].name}`);
            return true;
        }
        return false;
    },

    // Get current theme colors
    getThemeColors: function() {
        return this.themes[this.currentTheme].colors;
    },

    // Function to generate dynamic styles based on current theme
    getThemeStyles: function() {
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
                    primary: `w-8 h-8 flex items-center justify-center text-${colors.primary} hover:bg-${colors.primary.replace('500', '100')} rounded-full`,
                    danger: `w-8 h-8 flex items-center justify-center text-${colors.danger} hover:bg-${colors.danger.replace('500', '100')} rounded-full`,
                    success: `w-8 h-8 flex items-center justify-center text-${colors.success} hover:bg-${colors.success.replace('500', '100')} rounded-full`
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
                    cell: `py-3 px-4 text-left text-xs font-medium text-${colors.textMuted} uppercase tracking-wider`
                },
                body: {
                    row: `hover:bg-${colors.background} border-b border-${colors.borderLight}`,
                    cell: `px-4 py-2 whitespace-nowrap text-${colors.textSecondary}`,
                    cellAction: `px-4 py-2 whitespace-nowrap text-center text-sm font-medium`
                }
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
                red: `bg-${colors.danger.replace('500', '100').replace('400', '900')} text-${colors.danger.replace('500', '800').replace('400', '300')}`,
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
    initialize: function() {
        const styles = this.getThemeStyles();
        
        // Assign initial styles
        this.buttons = styles.buttons;
        this.cards = styles.cards;
        this.typography = styles.typography;
        this.forms = styles.forms;
        this.tables = styles.tables;
        this.status = styles.status;
        this.tags = styles.tags;
        this.modals = styles.modals;
        this.layout = styles.layout;
        
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
    }
};

// Initialize UI with default theme
window.App.utils.UI.initialize();

console.log("UI constants loaded with theme support.");