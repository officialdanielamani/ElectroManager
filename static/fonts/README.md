# Font Files for Offline Support

**Important:** All fonts MUST be in this folder for offline operation. NO CDN fallback.

## Folder Structure
```
/static/fonts/
├── README.md (this file)
├── OpenDyslexic-Regular.woff2
├── OpenDyslexic-Bold.woff2
└── (optional: .otf files for additional fallback)
```

## Required Font Files

### 1. OpenDyslexic (Dyslexia-Friendly)

**Download from:** https://github.com/antijingoist/open-dyslexic/releases

**Files needed:**
- `OpenDyslexic-Regular.woff2` (~30 KB)
- `OpenDyslexic-Bold.woff2` (~35 KB)

**Steps:**
1. Go to: https://github.com/antijingoist/open-dyslexic/releases/latest
2. Download the release (usually a zip file)
3. Extract and find the `.woff2` files
4. Copy both files to `/static/fonts/`

**File names MUST match exactly:**
```
/static/fonts/OpenDyslexic-Regular.woff2
/static/fonts/OpenDyslexic-Bold.woff2
```

### 2. System Font (Default)
- No files needed - uses system fonts automatically
- Always available offline

### 3. Courier New (Monospace)
- No files needed - uses system fonts automatically
- Always available offline

## Installation Checklist

- [ ] Created `/static/fonts/` folder (if not exists)
- [ ] Downloaded OpenDyslexic from GitHub
- [ ] Copied `OpenDyslexic-Regular.woff2` to `/static/fonts/`
- [ ] Copied `OpenDyslexic-Bold.woff2` to `/static/fonts/`
- [ ] File names match exactly (case-sensitive on Linux)
- [ ] Restart application

## Verification

To verify fonts are working:
1. Go to Settings → General
2. Select "OpenDyslexic (Dyslexia-Friendly)" from dropdown
3. Font should change immediately
4. If font doesn't change, check:
   - Files are in correct folder
   - File names match exactly
   - Restart application

## Current Status

- ✅ Local font loading configured
- ✅ NO CDN fallback (fully offline)
- ⚠️ OpenDyslexic files: **NOT INCLUDED** (add manually)
- ✅ System fonts: Ready
- ✅ Courier New: Ready

## File Sizes

- OpenDyslexic-Regular.woff2: ~30 KB
- OpenDyslexic-Bold.woff2: ~35 KB
- **Total OpenDyslexic: ~65 KB**

## Optional: Add TTF/OTF Files

For additional compatibility, you can also add:
```
/static/fonts/OpenDyslexic-Regular.ttf  (optional)
/static/fonts/OpenDyslexic-Bold.ttf     (optional)
/static/fonts/OpenDyslexic-Regular.otf  (optional)
/static/fonts/OpenDyslexic-Bold.otf     (optional)
```

These are fallbacks but WOFF2 files are primary.

