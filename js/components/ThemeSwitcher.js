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
        themeNames.map(name => {
          // Get theme-specific colors
          const theme = UI.themes[name];
          const colors = theme.colors;
          
          // Define button styling based on theme
          let buttonStyle = "px-3 py-2 rounded border ";
          
          // Current theme indicator 
          buttonStyle += currentTheme === name ? 'ring-2 ring-offset-1 ring-blue-500 ' : 'border-gray-300 ';
          
          // Theme-specific styling
          if (name === 'dark') {
            buttonStyle += 'bg-gray-800 text-white';
          } else if (name === 'keqing') {
            buttonStyle += 'bg-purple-100 text-purple-800 border-purple-300';
          } else {
            buttonStyle += 'bg-white text-gray-800'; 
          }
          
          return React.createElement('button', {
            key: name,
            onClick: () => handleThemeChange(name),
            className: buttonStyle,
            title: theme.name
          }, 
          theme.name
        )})
      )
    )};
console.log("ThemeSwitcher loaded");