// js/utils/storage.js - Ultra-compact format with minimal code

window.App = window.App || {};
window.App.utils = window.App.utils || {};

window.App.utils.storage = {
    useIndexedDB: null,
    
    init() {
        if (this.useIndexedDB !== null) return Promise.resolve(this.useIndexedDB);
        
        const idb = window.App.utils.idb;
        if (!idb?.init) {
            this.useIndexedDB = false;
            return Promise.resolve(false);
        }
        
        return idb.init()
            .then(initialized => {
                this.useIndexedDB = initialized;
                return initialized;
            })
            .catch(() => {
                this.useIndexedDB = false;
                return false;
            });
    },
    
    // Generic load/save for all store types
    async _load(storeName, defaultValue = []) {
        await this.init();
        if (!this.useIndexedDB) return defaultValue;
        
        try {
            console.log(`Loading ${storeName}...`);
            
            if (storeName === 'lowStockConfig') {
                const config = await window.App.utils.idb.loadLowStockConfig();
                console.log(`Loaded ${storeName}:`, config);
                return config;
            }
            
            const methodName = `load${storeName.charAt(0).toUpperCase()}${storeName.slice(1)}`;
            const data = await window.App.utils.idb[methodName]();
            
            console.log(`Raw ${storeName} data:`, data);
            
            // Expand components from compact format
            if (storeName === 'components') {
                const expanded = data.map(comp => this._expandComponent(comp));
                console.log(`Expanded ${storeName}:`, expanded);
                return expanded;
            }
            
            console.log(`Loaded ${storeName}:`, data);
            return data;
        } catch (err) {
            console.error(`Error loading ${storeName}:`, err);
            return defaultValue;
        }
    },
    
    async _save(storeName, data) {
        await this.init();
        if (!this.useIndexedDB) return false;
        
        try {
            console.log(`Saving ${storeName}...`, data);
            
            let processedData = data;
            
            // Compact components before saving
            if (storeName === 'components') {
                processedData = data.map(comp => this._compactComponent(comp));
                console.log(`Compacted ${storeName}:`, processedData);
            }
            
            // Sanitize data
            if (Array.isArray(processedData)) {
                const sanitizeMethod = window.App.utils.sanitize[storeName.slice(0, -1)] || window.App.utils.sanitize.object;
                processedData = processedData.map(item => sanitizeMethod.call(window.App.utils.sanitize, item));
                console.log(`Sanitized ${storeName}:`, processedData);
            }
            
            const methodName = `save${storeName.charAt(0).toUpperCase()}${storeName.slice(1)}`;
            const result = await window.App.utils.idb[methodName](processedData);
            console.log(`Saved ${storeName} result:`, result);
            return result;
        } catch (err) {
            console.error(`Error saving ${storeName}:`, err);
            return false;
        }
    },
    
    // Component compaction using single-letter keys for maximum compression
    _compactComponent(c) {
        if (!c) return c;
        
        console.log('Compacting component:', c.name);
        
        // Core fields (always included): i=id, n=name, c=category, t=type, q=quantity, p=price
        const compact = { 
            i: c.id || '', 
            n: c.name || '', 
            c: c.category || '', 
            t: c.type || '', 
            q: c.quantity || 0, 
            p: c.price || 0 
        };
        
        // Handle footprint - use customFootprint if it exists and footprint is __custom__
        let footprintValue = c.footprint;
        if (c.footprint === '__custom__' && c.customFootprint) {
            footprintValue = c.customFootprint;
        }
        if (footprintValue && footprintValue !== '__custom__' && footprintValue.trim()) {
            compact.f = footprintValue;
        }
        
        // Handle category - use customCategory if it exists and category is __custom__
        let categoryValue = c.category;
        if (c.category === '__custom__' && c.customCategory) {
            categoryValue = c.customCategory;
            compact.c = categoryValue; // Update the category field
        }
        
        // Optional fields: d=description/info, s=datasheets, m=image
        if (c.info && c.info.trim()) compact.d = c.info;
        if (c.datasheets && c.datasheets.trim()) compact.s = c.datasheets;
        if (c.image && c.image.trim()) compact.m = c.image;
        
        // Flags (only if true): v=favorite, b=bookmark, r=star
        if (c.favorite === true) compact.v = 1;
        if (c.bookmark === true) compact.b = 1;
        if (c.star === true) compact.r = 1;
        
        // Storage: l=location, w=drawer, e=cells, x=details
        if (c.storageInfo?.drawerId) {
            compact.l = { w: c.storageInfo.drawerId };
            if (c.storageInfo.cells?.length) compact.l.e = c.storageInfo.cells;
        } else if (c.locationInfo?.locationId) {
            compact.l = { i: c.locationInfo.locationId };
            if (c.locationInfo.details && c.locationInfo.details.trim()) compact.l.x = c.locationInfo.details;
        }
        
        // Parameters (custom fields) - exclude more fields now
        const params = {};
        const excludeFields = ['id', 'name', 'category', 'type', 'quantity', 'price', 'footprint', 'info', 
                              'datasheets', 'image', 'favorite', 'bookmark', 'star', 'locationInfo', 'storageInfo',
                              'customCategory', 'customFootprint']; // Exclude custom fields since they're handled above
        
        for (const [key, value] of Object.entries(c)) {
            if (!excludeFields.includes(key) && value !== undefined && value !== null && value !== '') {
                params[key] = value;
            }
        }
        
        if (Object.keys(params).length) compact.a = params; // a=additional/parameters
        
        console.log('Compacted to:', compact);
        return compact;
    },
    
    // Expand from compact format
    _expandComponent(c) {
        if (!c) return c;
        console.log('Expanding component:', c);
        
        // If already in expanded format, return as-is
        if (c.locationInfo || c.storageInfo) {
            console.log('Already expanded:', c);
            return c;
        }
        
        const expanded = {
            id: c.i || c.id || '',
            name: c.n || c.name || '',
            category: c.c || c.category || '',
            type: c.t || c.type || '',
            quantity: c.q ?? c.quantity ?? 0,
            price: c.p ?? c.price ?? 0,
            footprint: c.f || c.footprint || '',
            info: c.d || c.info || '',
            datasheets: c.s || c.datasheets || '',
            image: c.m || c.image || '',
            favorite: !!(c.v || c.favorite),
            bookmark: !!(c.b || c.bookmark),
            star: !!(c.r || c.star),
            locationInfo: { locationId: '', details: '' },
            storageInfo: { locationId: '', drawerId: '', cells: [] }
        };
        
        // Restore storage
        if (c.l) {
            if (c.l.w) { // Drawer storage
                expanded.storageInfo = {
                    locationId: '',
                    drawerId: c.l.w,
                    cells: c.l.e || []
                };
            } else if (c.l.i) { // Location storage
                expanded.locationInfo = {
                    locationId: c.l.i,
                    details: c.l.x || ''
                };
            }
        }
        
        // Restore parameters
        if (c.a && typeof c.a === 'object') {
            Object.assign(expanded, c.a);
        }
        
        console.log('Expanded to:', expanded);
        return expanded;
    },
    
    // Public API methods
    loadComponents() { return this._load('components'); },
    saveComponents(data) { return this._save('components', data); },
    loadLocations() { return this._load('locations'); },
    saveLocations(data) { return this._save('locations', data); },
    loadDrawers() { return this._load('drawers'); },
    saveDrawers(data) { return this._save('drawers', data); },
    loadCells() { return this._load('cells'); },
    saveCells(data) { return this._save('cells', data); },
    loadCategories() { return this._load('categories'); },
    saveCategories(data) { return this._save('categories', data); },
    loadFootprints() { return this._load('footprints'); },
    saveFootprints(data) { return this._save('footprints', data); },
    loadLowStockConfig() { return this._load('lowStockConfig', {}); },
    saveLowStockConfig(data) { return this._save('lowStockConfig', data); },
    
    // Config (localStorage only)
    loadConfig() {
        const defaults = { viewMode: 'table', currencySymbol: 'RM', showTotalValue: true, itemsPerPage: 'all', theme: 'light' };
        try {
            return {
                viewMode: localStorage.getItem('electronicsViewMode') || defaults.viewMode,
                currencySymbol: localStorage.getItem('electronicsCurrencySymbol') || defaults.currencySymbol,
                showTotalValue: localStorage.getItem('electronicsShowTotalValue') === 'true',
                itemsPerPage: JSON.parse(localStorage.getItem('electronicsItemsPerPage') || JSON.stringify(defaults.itemsPerPage)),
                theme: localStorage.getItem('electronicsTheme') || defaults.theme
            };
        } catch {
            return defaults;
        }
    },
    
    saveConfig(config) {
        try {
            if (config.viewMode) localStorage.setItem('electronicsViewMode', config.viewMode);
            if (config.currencySymbol) localStorage.setItem('electronicsCurrencySymbol', config.currencySymbol);
            if (typeof config.showTotalValue === 'boolean') localStorage.setItem('electronicsShowTotalValue', String(config.showTotalValue));
            if (config.theme) localStorage.setItem('electronicsTheme', config.theme);
            if (config.itemsPerPage !== undefined) localStorage.setItem('electronicsItemsPerPage', JSON.stringify(config.itemsPerPage));
            return true;
        } catch {
            return false;
        }
    },
    
    // Backup/Restore
    async createBackup() {
        await this.init();
        if (!this.useIndexedDB) throw new Error("IndexedDB not available");
        
        const stores = ['components', 'locations', 'drawers', 'cells', 'categories', 'footprints', 'lowStockConfig'];
        const data = {};
        
        for (const store of stores) {
            try {
                if (store === 'lowStockConfig') {
                    const config = await this.loadLowStockConfig();
                    data[store] = Object.entries(config).map(([category, threshold]) => ({ 
                        id: `ls-${category.replace(/[^a-zA-Z0-9]/g, '_')}`, category, threshold 
                    }));
                } else if (store === 'categories' || store === 'footprints') {
                    const items = await this._load(store);
                    data[store] = items.map((name, i) => ({ id: `${store[0]}${i}`, name }));
                } else if (store === 'components') {
                    // Get components in compact format directly from IndexedDB
                    data[store] = await window.App.utils.idb.loadComponents();
                } else {
                    data[store] = await this._load(store);
                }
            } catch (err) {
                console.error(`Error backing up ${store}:`, err);
                data[store] = [];
            }
        }
        
        return {
            meta: { v: "0.1.7beta", d: new Date().toISOString(), ultra: true },
            data
        };
    },
    
    async restoreBackup(backup) {
        await this.init();
        if (!this.useIndexedDB) throw new Error("IndexedDB not available");
        if (!backup?.meta || !backup?.data) throw new Error("Invalid backup format");
        
        const results = [];
        
        for (const [store, storeData] of Object.entries(backup.data)) {
            try {
                if (store === 'lowStockConfig') {
                    const config = {};
                    storeData.forEach(item => { if (item.category) config[item.category] = item.threshold; });
                    await this.saveLowStockConfig(config);
                } else if (store === 'categories' || store === 'footprints') {
                    const items = storeData.map(item => item.name);
                    await this._save(store, items);
                } else {
                    await this._save(store, storeData);
                }
                results.push({ store, success: true });
            } catch (err) {
                console.error(`Error restoring ${store}:`, err);
                results.push({ store, success: false, error: err.message });
            }
        }
        
        const successCount = results.filter(r => r.success).length;
        return {
            success: successCount > 0,
            message: `${successCount}/${results.length} stores restored`,
            details: results
        };
    },
    
    async clearStorage() {
        const promises = [];
        
        if (this.useIndexedDB) {
            promises.push(window.App.utils.idb.clearAll());
        }
        
        try {
            ['electronicsComponents', 'electronicsViewMode', 'electronicsCurrencySymbol', 
             'electronicsShowTotalValue', 'electronicsLocations', 'electronicsDrawers', 
             'electronicsCells', 'electronicsItemsPerPage'].forEach(key => localStorage.removeItem(key));
        } catch (err) {
            console.error("Error clearing localStorage:", err);
            return false;
        }
        
        try {
            await Promise.all(promises);
            return true;
        } catch (err) {
            console.error("Error clearing storage:", err);
            return false;
        }
    }
};

console.log("Ultra-compact storage.js loaded");