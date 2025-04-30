// ThemeSwitcher.js
window.App.components.ThemeSwitcher = ({ currentTheme, onThemeChange }) => {
    const { UI } = window.App.utils;
    
    // Get available themes
    const themeNames = Object.keys(UI.themes);
    
    // Handle theme change
    const handleThemeChange = (themeName) => {
      // Call the parent component's handler
      if (onThemeChange && UI.themes[themeName]) {
        onThemeChange(themeName);
      }
    };
    
    return React.createElement('div', { className: "mb-4" },
      React.createElement('div', { className: "flex flex-wrap gap-2" },
        themeNames.map(name => 
          React.createElement('button', {
            key: name,
            onClick: () => handleThemeChange(name),
            className: `px-3 py-2 rounded border ${currentTheme === name ? 'ring-2 ring-offset-1 ring-blue-500' : 'border-gray-300'} ${UI.themes[name].name === 'Dark' ? 'bg-gray-800 text-white' : ''}`,
            title: UI.themes[name].name
          }, 
          UI.themes[name].name
        ))
      )
    );
  };