/**
 * Theme Metadata Loader
 * Dynamically parses CSS theme files and extracts metadata
 */

const ThemeLoader = {
  themes: {},
  
  /**
   * Parse CSS metadata from theme file
   */
  parseThemeMetadata(cssText) {
    const metadataRegex = /\/\*\s*Theme Metadata\s*([\s\S]*?)\*\//;
    const match = cssText.match(metadataRegex);
    
    if (!match) return null;
    
    const metadata = {};
    const lines = match[1].split('\n');
    
    lines.forEach(line => {
      const trimmed = line.trim();
      if (!trimmed) return;
      
      const [key, ...valueParts] = trimmed.split(':');
      const cleanKey = key.trim();
      const cleanValue = valueParts.join(':').trim();
      
      if (cleanKey && cleanValue) {
        metadata[cleanKey] = cleanValue;
      }
    });
    
    return metadata;
  },
  
  /**
   * Load and parse all available themes
   */
  async loadAllThemes(themeList) {
    const themePromises = themeList.map(themeName => 
      this.loadTheme(themeName)
    );
    
    const results = await Promise.all(themePromises);
    
    results.forEach((metadata, index) => {
      if (metadata) {
        this.themes[themeList[index]] = metadata;
      }
    });
    
    return this.themes;
  },
  
  /**
   * Load single theme by name
   */
  async loadTheme(themeName) {
    try {
      const response = await fetch(`/static/css/themes/${themeName}.css`);
      const cssText = await response.text();
      const metadata = this.parseThemeMetadata(cssText);
      
      if (metadata) {
        this.themes[themeName] = metadata;
      }
      
      return metadata;
    } catch (error) {
      console.error(`Failed to load theme: ${themeName}`, error);
      return null;
    }
  },
  
  /**
   * Get theme metadata
   */
  getTheme(themeName) {
    return this.themes[themeName] || null;
  },
  
  /**
   * Get specific color from theme
   */
  getThemeColor(themeName, colorKey) {
    const theme = this.themes[themeName];
    return theme ? theme[colorKey] || null : null;
  },
  
  /**
   * Apply theme colors to preview element
   */
  applyThemeToPreview(previewElement, themeName) {
    const theme = this.themes[themeName];
    if (!theme) return;
    
    const cssVars = {
      '--theme-color': theme['color'],
      '--theme-bg': theme['background-color'],
      '--theme-text': theme['text-color'],
      '--theme-primary': theme['primary-button'],
      '--theme-secondary': theme['secondary-button'],
      '--theme-badge': theme['badge'],
      '--theme-card-bg': theme['card-background'],
      '--theme-card-header': theme['card-header-background'],
      '--theme-header-text': theme['header-text']
    };
    
    Object.entries(cssVars).forEach(([key, value]) => {
      if (value) {
        previewElement.style.setProperty(key, value);
      }
    });
  }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ThemeLoader;
}
