// ThemeSwitcher.js
window.App.components.ThemeSwitcher = () => {
    const { UI } = window.App.utils;
    const { useState, useEffect } = React;
    
    // Get available themes
    const themeNames = Object.keys(UI.themes);
    
    // Local state for current theme
    const [currentTheme, setCurrentTheme] = useState(UI.currentTheme);
    
    // Handle theme change
    const handleThemeChange = (themeName) => {
      if (UI.setTheme(themeName)) {
        setCurrentTheme(themeName);
        // Trigger app re-render or update (would depend on your app structure)
        if (window.App.onThemeChange) {
          window.App.onThemeChange(themeName);
        }
      }
    };
    
    return React.createElement('div', { className: "mb-4" },
      React.createElement('h4', { className: "font-medium mb-2" }, "Select Theme"),
      React.createElement('div', { className: "flex space-x-2" },
        themeNames.map(name => 
          React.createElement('button', {
            key: name,
            onClick: () => handleThemeChange(name),
            className: `px-3 py-1 rounded border ${currentTheme === name ? 'border-2 border-blue-500' : 'border-gray-300'}`,
            title: UI.themes[name].name
          }, 
          UI.themes[name].name
        ))
      )
    );
  };