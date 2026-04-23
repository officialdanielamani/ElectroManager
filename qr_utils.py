"""
QR/Barcode Sticker Template Utilities
"""
import json
import os
from io import BytesIO
from flask import current_app
from datetime import datetime, timezone

# Available placeholders for each template type
AVAILABLE_PLACEHOLDERS = {
    'Items': [
        '{ItemUUID}', '{ItemName}', '{SKU}', '{Price}',
        '{Quantity}', '{Category}', '{LocationName}', '{RackName}', '{Drawer}'
    ],
    'Location': [
        '{LocationUUID}', '{LocationName}', '{LocationInfo}', '{ItemCount}'
    ],
    'Racks': [
        '{RackUUID}', '{RackName}', '{Capacity}', '{ItemCount}'
    ]
}

def validate_bootstrap_icons():
    """Validate Bootstrap Icons files exist. Halt if missing."""
    from flask import Flask
    if isinstance(current_app, Flask):
        icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
        required_files = ['bootstrap-icons.css', 'bootstrap-icons.woff2']

        missing = [f for f in required_files if not os.path.exists(os.path.join(icons_dir, f))]

        if missing:
            print(f"[ERROR] Bootstrap Icons files missing in {icons_dir}:")
            for f in missing:
                print(f"  - {f}")
            print("[ERROR] Cannot start without Bootstrap Icons. Please ensure static/icons/ directory has the required files.")
            raise RuntimeError(f"Missing Bootstrap Icons files: {', '.join(missing)}")

def get_item_data(item):
    """Extract printable data from Item"""
    return {
        'ItemUUID': f"item/{item.uuid}",
        'ItemName': item.name,
        'SKU': item.sku or '',
        'Price': f"${item.get_average_price():.2f}" if item.get_average_price() else '',
        'Quantity': str(item.get_overall_quantity()),
        'Category': item.category.name if item.category else '',
        'LocationName': item.general_location.name if item.general_location else '',
        'RackName': item.rack.name if item.rack else '',
        'Drawer': f"drawer/{item.drawer}" if item.drawer else ''
    }

def get_location_data(location):
    """Extract printable data from Location"""
    from models import Item
    item_count = Item.query.filter_by(location_id=location.id).count()
    return {
        'LocationUUID': f"location/{location.uuid}",
        'LocationName': location.name,
        'LocationInfo': location.info or '',
        'ItemCount': str(item_count)
    }

def get_rack_data(rack):
    """Extract printable data from Rack"""
    from models import Item
    item_count = Item.query.filter_by(rack_id=rack.id).count()
    return {
        'RackUUID': f"rack/{rack.uuid}",
        'RackName': rack.name,
        'Capacity': str(rack.rows * rack.cols),
        'ItemCount': str(item_count)
    }

def replace_placeholders(text, data_dict):
    """Replace {Placeholder} with actual values"""
    result = text
    for key, value in data_dict.items():
        result = result.replace(f'{{{key}}}', str(value))
    return result

def _get_format(ext):
    """Get font format string from file extension"""
    formats = {
        '.woff2': 'woff2',
        '.woff': 'woff',
        '.ttf': 'truetype',
        '.otf': 'opentype'
    }
    return formats.get(ext.lower(), 'truetype')

def render_template_to_svg(template, data):
    """
    Convert template layout + data to SVG
    MM to pixels: 1mm = 3.78px (at 96 DPI)
    """
    import os
    import base64
    
    MM_TO_PX = 3.78
    width_px = template.width_mm * MM_TO_PX
    height_px = template.height_mm * MM_TO_PX
    
    print(f"[SVG] Rendering template: {template.name} ({template.width_mm}×{template.height_mm}mm)")
    print(f"[SVG] Template ID: {template.id}")
    print(f"[SVG] Layout elements: {len(template.get_layout())}")
    print(f"[SVG] Data keys: {list(data.keys())}")
    
    # Collect fonts used in this template (for text elements only)
    # Icon fonts are no longer needed as icons are rendered as SVG paths
    text_fonts_used = set()
    layout = template.get_layout()
    for element in layout:
        if element.get('type') == 'text':
            font = element.get('font_family', 'Arial')
            if font:
                text_fonts_used.add(font)
    
    # Build font-face rules for SVG with embedded fonts for project fonts
    font_styles = ''
    fonts_dir = os.path.join(current_app.root_path, 'static', 'fonts')
    system_fonts = {'system', 'Arial', 'Times New Roman', 'Courier New', 'Georgia', 'Verdana', 'Comic Sans MS', 'Trebuchet MS'}
    
    # Embed text fonts
    for font_name in text_fonts_used:
        if font_name not in system_fonts:  # Only embed project fonts
            # Try to find the font file
            for ext in ['.woff2', '.woff', '.ttf', '.otf']:
                # Try exact name first, then with -Regular suffix
                font_path = os.path.join(fonts_dir, font_name + ext)
                if not os.path.exists(font_path):
                    font_path = os.path.join(fonts_dir, font_name + '-Regular' + ext)
                
                if os.path.exists(font_path):
                    try:
                        with open(font_path, 'rb') as f:
                            font_data = base64.b64encode(f.read()).decode('utf-8')
                        format_type = _get_format(ext)
                        font_styles += f'''<style>
        @font-face {{
            font-family: '{font_name}';
            src: url('data:font/{format_type};base64,{font_data}') format('{format_type}');
            font-display: swap;
        }}
    </style>
'''
                        print(f"[SVG] Embedded text font: {font_name}")
                        break
                    except Exception as e:
                        print(f"[SVG] Failed to embed text font {font_name}: {e}")
    
    svg = f'<svg width="{width_px}" height="{height_px}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}">\n'
    svg += font_styles
    svg += f'  <rect width="{width_px}" height="{height_px}" fill="white" stroke="black" stroke-width="0.5"/>\n'
    
    layout = template.get_layout()
    
    for idx, element in enumerate(layout):
        x_px = element['x_mm'] * MM_TO_PX
        y_px = element['y_mm'] * MM_TO_PX
        w_px = element.get('width_mm', 10) * MM_TO_PX
        h_px = element.get('height_mm', 10) * MM_TO_PX
        
        if element['type'] == 'text':
            # Get content, handle missing field
            content = element.get('content', '')
            content = replace_placeholders(content, data)
            print(f"[SVG] Element {idx}: TEXT = '{content}' (template: '{element.get('content', '')}')")
            # Escape XML special characters
            content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            
            # Use font_size_mm if available, otherwise fallback to old font_size in pixels
            font_size_mm = element.get('font_size_mm', 4)
            if font_size_mm:
                font_size = font_size_mm * MM_TO_PX  # Convert mm to pixels
            else:
                font_size = element.get('font_size', 12)  # Fallback to old px value
            
            color = element.get('color', '#000000')
            text_align = element.get('text_align', 'left')
            # Get font family with fallback to Arial if not found or empty
            font_family = element.get('font_family') or 'Arial'
            if not font_family or font_family == 'default':
                font_family = 'Arial'
            
            # For fonts with spaces, ensure they're quoted in CSS/SVG
            if ' ' in font_family:
                font_family_quoted = f"'{font_family}'"
            else:
                font_family_quoted = font_family
            
            print(f"[SVG] Element {idx}: Font = '{font_family}' (quoted: '{font_family_quoted}')")
            
            anchor = 'start'
            x_text = x_px
            if text_align == 'center':
                anchor = 'middle'
                x_text = x_px + w_px / 2
            elif text_align == 'right':
                anchor = 'end'
                x_text = x_px + w_px
            
            # Use inline style for font-family to prevent CSS override from base.html
            svg += f'  <text x="{x_text}" y="{y_px}" font-size="{font_size}" '
            svg += f'fill="{color}" text-anchor="{anchor}" '
            svg += f'dominant-baseline="hanging" word-wrap="break-word" '
            svg += f'style="font-family: {font_family_quoted};">'
            svg += f'{content}</text>\n'
        
        elif element['type'] == 'qr':
            source_field = element['source_field']
            qr_data = replace_placeholders(source_field, data)
            print(f"[SVG] Element {idx}: QR = '{qr_data}' (template: '{source_field}')")
            
            # Generate QR code SVG
            try:
                qr_svg = generate_qr_svg(qr_data, int(w_px), int(h_px))
                svg += f'  <g transform="translate({x_px}, {y_px})">{qr_svg}</g>\n'
            except Exception as e:
                print(f"[SVG] QR generation error: {e}")
                # Fallback: just show a placeholder
                svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" '
                svg += f'fill="lightgray" stroke="red" stroke-width="1"/>\n'
                svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" '
                svg += f'text-anchor="middle">QR Error</text>\n'
        
        elif element['type'] == 'barcode':
            source_field = element['source_field']
            barcode_data = replace_placeholders(source_field, data)
            print(f"[SVG] Element {idx}: BARCODE = '{barcode_data}' (template: '{source_field}')")
            barcode_format = element.get('format', 'CODE128')
            show_label = element.get('show_label', False)
            
            # Generate barcode SVG
            try:
                barcode_svg = generate_barcode_svg(barcode_data, barcode_format, int(w_px), int(h_px), show_label=show_label)
                svg += f'  <g transform="translate({x_px}, {y_px})">{barcode_svg}</g>\n'
            except Exception as e:
                print(f"[SVG] Barcode generation error: {e}")
                # Fallback: just show a placeholder
                svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" '
                svg += f'fill="lightgray" stroke="red" stroke-width="1"/>\n'
                svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" '
                svg += f'text-anchor="middle">Barcode Error</text>\n'
        
        elif element['type'] == 'icon':
            icon_name = element.get('icon_name', '')
            icon_color = element.get('icon_color', '#000000')

            # Scale icon to fit container (80% of container size)
            icon_size_px = min(w_px, h_px) * 0.8

            if icon_name:
                print(f"[SVG] Element {idx}: ICON = '{icon_name}' (container: {w_px}×{h_px}px, scaled size: {icon_size_px}px, color: {icon_color})")
                try:
                    icon_svg = generate_icon_svg(icon_name, int(icon_size_px), icon_color, int(w_px), int(h_px))
                    svg += f'  <g transform="translate({x_px}, {y_px})">{icon_svg}</g>\n'
                except Exception as e:
                    print(f"[SVG] Icon generation error: {e}")
                    svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" '
                    svg += f'fill="lightgray" stroke="red" stroke-width="1"/>\n'
                    svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" '
                    svg += f'text-anchor="middle">Icon Error</text>\n'
            else:
                print(f"[SVG] Element {idx}: ICON - No icon name specified")
    
    svg += '</svg>\n'
    print(f"[SVG] Complete! SVG size: {len(svg)} bytes")
    return svg

def generate_qr_svg(data, width, height, error_correction='M'):
    """Generate QR code SVG using qrcode library"""
    print(f"[QR] Generating QR for data: '{data}' (size: {width}×{height}, EC: {error_correction})")
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
        
        # Map error correction levels
        ec_map = {
            'L': qrcode.constants.ERROR_CORRECT_L,
            'M': qrcode.constants.ERROR_CORRECT_M,
            'Q': qrcode.constants.ERROR_CORRECT_Q,
            'H': qrcode.constants.ERROR_CORRECT_H
        }
        ec_level = ec_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=ec_level,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(image_factory=SvgPathImage)
        
        svg_output = BytesIO()
        img.save(svg_output)
        svg_str = svg_output.getvalue().decode('utf-8')
        
        # Extract just the SVG content and fix dimensions
        import re
        svg_match = re.search(r'<svg[^>]*>.*?</svg>', svg_str, re.DOTALL)
        if svg_match:
            result = svg_match.group(0)
            
            # Remove mm units and set to pixel dimensions
            result = re.sub(r'width="[^"]*mm"', f'width="{width}"', result)
            result = re.sub(r'height="[^"]*mm"', f'height="{height}"', result)
            # Also update viewBox if it has mm units
            result = re.sub(r'viewBox="0 0 \d+mm \d+mm"', f'viewBox="0 0 {width} {height}"', result)
            
            print(f"[QR] Success! Generated {len(result)} bytes with dimensions {width}×{height}")
            return result
        print(f"[QR] Warning: Could not extract SVG from output, returning full output")
        return svg_str
    except Exception as e:
        print(f"[QR] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        # Return placeholder SVG
        placeholder = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><rect width="{width}" height="{height}" fill="lightgray" stroke="red" stroke-width="2"/><text x="{width/2}" y="{height/2}" font-size="12" text-anchor="middle" dominant-baseline="middle">QR Error</text></svg>'
        print(f"[QR] Returning placeholder")
        return placeholder

def generate_barcode_svg(data, format_type, width, height, show_label=False):
    """Generate barcode SVG - using PIL-based approach for better control"""
    print(f"[BARCODE] Generating {format_type} barcode for data: '{data}' (size: {width}×{height}, show_label={show_label})")
    try:
        import barcode
        from barcode.writer import ImageWriter
        from io import BytesIO
        from PIL import Image
        import base64
        
        # Validate format
        valid_formats = ['CODE128', 'CODE39', 'EAN13', 'EAN8', 'UPCA', 'UPCE']
        if format_type not in valid_formats:
            print(f"[BARCODE] Format '{format_type}' not valid, using CODE128")
            format_type = 'CODE128'
        
        # For placeholder strings (like {ItemUUID}), use CODE128 which accepts any characters
        if data.startswith('{') and data.endswith('}'):
            print(f"[BARCODE] Detected placeholder format, using CODE128 for flexibility")
            format_type = 'CODE128'
        # For formats that require digits only (EAN, UPC), check if data is numeric
        elif format_type in ['EAN13', 'EAN8', 'UPCA', 'UPCE']:
            if not data.isdigit():
                print(f"[BARCODE] Data '{data}' contains non-digits, format {format_type} requires digits, using CODE128")
                format_type = 'CODE128'
        
        try:
            # Generate barcode as PNG image
            BarCodeClass = barcode.get_barcode_class(format_type.lower())
            
            # Create barcode instance
            barcode_instance = BarCodeClass(data, writer=ImageWriter())
            
            img_output = BytesIO()
            # If show_label is False, disable text label in barcode image
            # If show_label is True, use PIL's default (with text)
            if not show_label:
                barcode_instance.write(img_output, options={'font_size': 0})
                print(f"[BARCODE] Generated image without text label")
            else:
                barcode_instance.write(img_output)
                print(f"[BARCODE] Generated image with text label (from PIL)")
            
            img_output.seek(0)
            
            # Open image and get dimensions
            img = Image.open(img_output)
            img_width, img_height = img.size
            print(f"[BARCODE] Generated image dimensions: {img_width}×{img_height}")
            
            # Convert image to base64 SVG embedding
            img_output.seek(0)
            img_base64 = base64.b64encode(img_output.read()).decode('utf-8')
            
            # Create SVG with embedded image
            svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
    <image x="0" y="0" width="{width}" height="{height}" href="data:image/png;base64,{img_base64}" preserveAspectRatio="none"/>
</svg>'''
            
            print(f"[BARCODE] Success! Generated SVG with embedded PNG, {len(svg)} bytes")
            return svg
            
        except Exception as e:
            print(f"[BARCODE] {format_type} failed ({type(e).__name__}), falling back to CODE128")
            format_type = 'CODE128'
            BarCodeClass = barcode.get_barcode_class(format_type.lower())
            
            barcode_instance = BarCodeClass(data, writer=ImageWriter())
            
            img_output = BytesIO()
            # Same logic for fallback
            if not show_label:
                barcode_instance.write(img_output, options={'font_size': 0})
                print(f"[BARCODE] Fallback generated image without text label")
            else:
                barcode_instance.write(img_output)
                print(f"[BARCODE] Fallback generated image with text label (from PIL)")
            
            img_output.seek(0)
            
            img = Image.open(img_output)
            img_width, img_height = img.size
            print(f"[BARCODE] Fallback image dimensions: {img_width}×{img_height}")
            
            img_output.seek(0)
            img_base64 = base64.b64encode(img_output.read()).decode('utf-8')
            
            svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
    <image x="0" y="0" width="{width}" height="{height}" href="data:image/png;base64,{img_base64}" preserveAspectRatio="none"/>
</svg>'''
            
            print(f"[BARCODE] Success! Generated fallback SVG with embedded PNG, {len(svg)} bytes")
            return svg
            
    except Exception as e:
        print(f"[BARCODE] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        # Return placeholder SVG
        placeholder = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><rect width="{width}" height="{height}" fill="lightgray" stroke="red" stroke-width="2"/><text x="{width/2}" y="{height/2}" font-size="12" text-anchor="middle" dominant-baseline="middle">Barcode Error</text></svg>'
        print(f"[BARCODE] Returning placeholder")
        return placeholder

def generate_icon_svg(icon_name, icon_size, icon_color, container_width, container_height):
    """Generate icon as actual SVG <path> extracted from the Bootstrap Icons font.

    Extracting the glyph outline as an SVG path works everywhere: browser
    preview, PDF, SVG download, PNG export.
    """
    print(f"[ICON] Generating icon: {icon_name} (size: {icon_size}px, color: {icon_color})")

    try:
        center_x = container_width / 2
        center_y = container_height / 2

        path_data, glyph_bounds, units_per_em = get_icon_path(icon_name)
        
        if not path_data:
            print(f"[ICON] Warning: Could not extract path for {icon_name}")
            svg = f'<circle cx="{center_x}" cy="{center_y}" r="{min(container_width, container_height) * 0.3}" fill="{icon_color}" opacity="0.5"/>'
            return svg
        
        # Scale the glyph path to fit the icon_size within the container
        if glyph_bounds:
            gx_min, gy_min, gx_max, gy_max = glyph_bounds
        else:
            gx_min, gy_min, gx_max, gy_max = 0, 0, units_per_em, units_per_em
        
        glyph_width = gx_max - gx_min
        glyph_height = gy_max - gy_min
        
        if glyph_width == 0 or glyph_height == 0:
            print(f"[ICON] Warning: Zero-size glyph for {icon_name}")
            svg = f'<circle cx="{center_x}" cy="{center_y}" r="{min(container_width, container_height) * 0.3}" fill="{icon_color}" opacity="0.5"/>'
            return svg
        
        # Calculate scale to fit icon_size
        scale = icon_size / max(glyph_width, glyph_height)
        
        # Calculate translation to center the icon in the container
        # Font Y-axis goes up, SVG Y-axis goes down, so we flip Y via negative scale
        scaled_width = glyph_width * scale
        scaled_height = glyph_height * scale
        
        tx = center_x - (gx_min * scale) - (scaled_width / 2)
        ty = center_y + (gy_max * scale) - (scaled_height / 2)
        
        svg = f'<path d="{path_data}" fill="{icon_color}" transform="translate({tx:.2f}, {ty:.2f}) scale({scale:.6f}, {-scale:.6f})"/>'
        
        print(f"[ICON] Success! Generated icon SVG path, {len(svg)} bytes")
        return svg
        
    except Exception as e:
        print(f"[ICON] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        placeholder = f'<rect width="{container_width}" height="{container_height}" fill="lightgray" stroke="red" stroke-width="2"/><text x="{container_width/2}" y="{container_height/2}" font-size="12" text-anchor="middle" dominant-baseline="middle">Icon Error</text>'
        return placeholder


# Cache for loaded font data to avoid re-reading font files repeatedly
_font_cache = {}

_BS_ICON_PACKAGE = 'bootstrap-icons'


def get_icon_path(icon_name):
    """Extract SVG path data for a Bootstrap Icons glyph using fontTools.

    Returns: (path_data, bounds, units_per_em) or (None, None, None)
    """
    import os

    try:
        from fontTools.ttLib import TTFont
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.boundsPen import BoundsPen
    except ImportError:
        print("[ICON] fontTools not available, cannot extract icon paths")
        return None, None, None

    try:
        icon_unicode_char = get_icon_unicode(icon_name)
        if not icon_unicode_char:
            return None, None, None

        codepoint = ord(icon_unicode_char)

        if _BS_ICON_PACKAGE not in _font_cache:
            icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
            font_path = None
            for ext in ['.woff2', '.woff', '.ttf', '.otf']:
                candidate = os.path.join(icons_dir, _BS_ICON_PACKAGE + ext)
                if os.path.exists(candidate):
                    font_path = candidate
                    break

            if not font_path:
                print("[ICON] No Bootstrap Icons font file found in static/icons/")
                return None, None, None

            _font_cache[_BS_ICON_PACKAGE] = TTFont(font_path)
            print(f"[ICON] Loaded and cached font: {font_path}")

        font = _font_cache[_BS_ICON_PACKAGE]
        cmap = font.getBestCmap()
        units_per_em = font['head'].unitsPerEm
        
        if codepoint not in cmap:
            print(f"[ICON] Codepoint U+{codepoint:04X} not in font cmap")
            return None, None, None
        
        glyph_name = cmap[codepoint]
        glyph_set = font.getGlyphSet()
        glyph = glyph_set[glyph_name]
        
        # Extract SVG path
        pen = SVGPathPen(glyph_set)
        glyph.draw(pen)
        path_data = pen.getCommands()
        
        # Get bounds
        bpen = BoundsPen(glyph_set)
        glyph.draw(bpen)
        bounds = bpen.bounds
        
        if not path_data:
            print(f"[ICON] Empty path for glyph '{glyph_name}'")
            return None, None, None
        
        print(f"[ICON] Extracted path for '{icon_name}' (glyph: {glyph_name}, U+{codepoint:04X}, bounds: {bounds})")
        return path_data, bounds, units_per_em
        
    except Exception as e:
        print(f"[ICON] Error extracting path: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def get_icon_unicode(icon_name):
    """Extract unicode character for a Bootstrap Icon from bootstrap-icons.css."""
    import os
    import re

    try:
        css_path = os.path.join(current_app.root_path, 'static', 'icons', 'bootstrap-icons.css')

        if not os.path.exists(css_path):
            print(f"[ICON] CSS file not found: {css_path}")
            return None

        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        pattern = rf'\.bi-{re.escape(icon_name)}::before\s*{{\s*content:\s*"(\\[0-9a-fA-F]+)";'
        match = re.search(pattern, css_content)
        if match:
            unicode_value = int(match.group(1)[1:], 16)
            print(f"[ICON] Found unicode for {icon_name}: U+{unicode_value:04X}")
            return chr(unicode_value)

        print(f"[ICON] Could not find icon '{icon_name}' in bootstrap-icons.css")
        return None
        
    except Exception as e:
        print(f"[ICON] Error getting unicode: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_single_sticker_pdf(template, data, identifier):
    """Generate a PDF with a single sticker"""
    print(f"[PDF] Generating PDF for template: {template.name}, item: {identifier}")
    
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        print("[PDF] WeasyPrint not available, returning SVG fallback")
        svg_data = render_template_to_svg(template, data)
        return BytesIO(svg_data.encode())
    
    MM_TO_IN = 1 / 25.4
    width_in = template.width_mm * MM_TO_IN
    height_in = template.height_mm * MM_TO_IN
    
    # Render sticker to SVG
    svg_data = render_template_to_svg(template, data)
    print(f"[PDF] SVG rendered, size: {len(svg_data)} bytes")
    
    # Convert SVG to base64 and embed as image in HTML
    # This avoids font embedding issues in PDF rendering
    import base64
    svg_base64 = base64.b64encode(svg_data.encode()).decode('utf-8')
    
    # Create simple HTML that embeds SVG as image
    html_content = f'''<html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: {width_in}in {height_in}in;
                margin: 0;
                padding: 0;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; }}
            .sticker {{
                width: {width_in}in;
                height: {height_in}in;
                display: flex;
                align-items: center;
                justify-content: center;
                background: white;
            }}
            img {{ max-width: 100%; max-height: 100%; width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div class="sticker">
            <img src="data:image/svg+xml;base64,{svg_base64}" alt="sticker"/>
        </div>
    </body>
</html>'''
    
    print(f"[PDF] HTML created with embedded SVG image")
    
    doc = HTML(string=html_content)
    pdf_output = BytesIO()
    doc.write_pdf(pdf_output)
    pdf_output.seek(0)
    print(f"[PDF] PDF generated successfully")
    return pdf_output

def generate_batch_stickers_pdf(template, records, data_getter):
    """
    Generate PDF with multiple stickers
    """
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        raise ImportError("WeasyPrint not installed")
    
    import base64
    
    MM_TO_IN = 1 / 25.4
    width_in = template.width_mm * MM_TO_IN
    height_in = template.height_mm * MM_TO_IN
    
    # Create HTML with multiple stickers - embed SVGs as images
    html_content = f'''<html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: {width_in}in {height_in}in;
                margin: 0;
                padding: 0;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ margin: 0; padding: 0; }}
            .sticker {{
                width: {width_in}in;
                height: {height_in}in;
                display: flex;
                align-items: center;
                justify-content: center;
                page-break-after: always;
                background: white;
            }}
            img {{ max-width: 100%; max-height: 100%; width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
    '''
    
    for record in records:
        data = data_getter(record)
        svg = render_template_to_svg(template, data)
        # Embed SVG as base64 image
        svg_base64 = base64.b64encode(svg.encode()).decode('utf-8')
        html_content += f'<div class="sticker"><img src="data:image/svg+xml;base64,{svg_base64}" alt="sticker"/></div>'
    
    html_content += '</body></html>'
    
    doc = HTML(string=html_content)
    pdf_output = BytesIO()
    doc.write_pdf(pdf_output)
    pdf_output.seek(0)
    return pdf_output
