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
        '{ItemUUID}', '{ItemName}', '{ItemType}', '{ItemSKU}', '{ItemInfo}',
        '{ItemCat}', '{ItemFoot}', '{ItemTPrice}', '{ItemMOvrQty}', '{ItemMinQty}',
        '{ItemMLocName}', '{ItemMLocUUID}', '{ItemMRackName}', '{ItemMRackUUID}', '{ItemMDrawLoc}'
    ],
    'Location': [
        '{LocUUID}', '{LocName}', '{LocInfo}', '{LocICount}'
    ],
    'Racks': [
        '{RackUUID}', '{RackName}', '{RackInfo}', '{RackLoc}',
        '{RackCap}', '{RackICount}', '{RackSize}'
    ],
    'Drawer': [
        '{RackUUID}', '{RackName}', '{RackInfo}', '{RackLoc}',
        '{RackCap}', '{RackICount}', '{RackSize}',
        '{DrawInfo}', '{DrawLoc}', '{DrawSize}', '{DrawICount}',
        '{DrawStatus}', '{DrawGroup}'
    ]
}

def validate_bootstrap_icons():
    """Validate Bootstrap Icons files exist. Logs a warning if missing but does not halt startup."""
    import logging
    logger = logging.getLogger(__name__)
    from flask import Flask
    if isinstance(current_app, Flask):
        icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
        required_files = [
            'bootstrap-icons.css',
            os.path.join('fonts', 'bootstrap-icons.woff2'),
        ]

        missing = [f for f in required_files if not os.path.exists(os.path.join(icons_dir, f))]

        if missing:
            logger.warning(
                "Bootstrap Icons files missing in %s: %s — icons may not display correctly.",
                icons_dir, ', '.join(missing)
            )

def get_item_data(item):
    """Extract printable data from Item"""
    # Determine main location: rack's physical location takes priority over general location
    if item.rack_id and item.rack and item.rack.physical_location:
        main_loc_name = item.rack.physical_location.name
        main_loc_uuid = item.rack.physical_location.uuid
    elif item.location_id and item.general_location:
        main_loc_name = item.general_location.name
        main_loc_uuid = item.general_location.uuid
    else:
        main_loc_name = ''
        main_loc_uuid = ''

    rack_name = item.rack.name if item.rack else ''
    rack_uuid = item.rack.uuid if item.rack else ''
    draw_loc  = item.drawer if (item.rack_id and item.drawer) else ''

    total_price = item.get_overall_total_price()

    return {
        'ItemUUID':     item.uuid,
        'ItemName':     item.name,
        'ItemType':     item.info or '',
        'ItemSKU':      item.sku or '',
        'ItemInfo':     item.short_info or '',
        'ItemCat':      item.category.name if item.category else '',
        'ItemFoot':     item.footprint.name if item.footprint else '',
        'ItemTPrice':   f"{total_price:.2f}" if total_price else '',
        'ItemMOvrQty':  str(item.get_overall_quantity()),
        'ItemMinQty':   str(item.min_quantity or 0),
        'ItemMLocName': main_loc_name,
        'ItemMLocUUID': main_loc_uuid,
        'ItemMRackName': rack_name,
        'ItemMRackUUID': rack_uuid,
        'ItemMDrawLoc':  draw_loc,
    }

def get_location_data(location):
    """Extract printable data from Location"""
    from models import Item
    item_count = Item.query.filter_by(location_id=location.id).count()
    return {
        'LocUUID':   location.uuid,
        'LocName':   location.name,
        'LocInfo':   location.info or '',
        'LocICount': str(item_count),
    }

def get_rack_data(rack):
    """Extract printable data from Rack"""
    from models import Item
    item_count = Item.query.filter_by(rack_id=rack.id).count()
    loc_name = rack.physical_location.name if rack.physical_location else ''
    rack_size = f"{rack.rows}X{rack.cols:02d}"
    return {
        'RackUUID':   rack.uuid,
        'RackName':   rack.name,
        'RackInfo':   rack.short_info or '',
        'RackLoc':    loc_name,
        'RackCap':    str(rack.rows * rack.cols),
        'RackICount': str(item_count),
        'RackSize':   rack_size,
    }

def get_drawer_data(rack, drawer_id):
    """Extract printable data for a specific drawer in a rack."""
    from models import Item
    import re

    rack_data = get_rack_data(rack)

    # Drawer short info
    draw_info = rack.get_drawer_short_info(drawer_id)

    # Drawer item count — items stored in this exact drawer
    draw_item_count = Item.query.filter_by(rack_id=rack.id, drawer=drawer_id).count()

    # Drawer status
    if rack.is_drawer_unavailable(drawer_id):
        draw_status = 'Unavailable'
    elif draw_item_count > 0:
        draw_status = 'Available'
    else:
        draw_status = 'Empty'

    # Drawer size — 01X01 for single cell; rowspan×colspan for merged rectangular cells
    skip_cells, cell_spans, group_cells = rack.compute_merge_layout()
    master_id = rack.get_master_cell(drawer_id)
    span = cell_spans.get(master_id)
    if span:
        draw_size = f"{span['rowspan']:02d}X{span['colspan']:02d}"
    else:
        draw_size = '01X01'

    # Group drawer master (for non-rectangular groups)
    grp = group_cells.get(drawer_id)
    draw_group = grp['master'] if grp else ''

    return {
        **rack_data,
        'DrawInfo':   draw_info,
        'DrawLoc':    drawer_id,
        'DrawSize':   draw_size,
        'DrawICount': str(draw_item_count),
        'DrawStatus': draw_status,
        'DrawGroup':  draw_group,
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
    
    # Collect fonts used in this template
    text_fonts_used = set()
    has_icons = False
    layout = template.get_layout()
    for element in layout:
        if element.get('visible') is False:
            continue
        if element.get('type') == 'text':
            font = element.get('font_family', 'Arial')
            if font:
                text_fonts_used.add(font)
        elif element.get('type') == 'icon' and element.get('icon_name'):
            has_icons = True

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

    # Embed Bootstrap Icons font once at SVG level (must be top-level, not inside <g>)
    if has_icons:
        icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
        fonts_subdir = os.path.join(icons_dir, 'fonts')
        bi_font_path = None
        bi_font_ext = None
        for ext in ['.woff', '.woff2', '.ttf', '.otf']:
            for search_dir in [fonts_subdir, icons_dir]:
                candidate = os.path.join(search_dir, 'bootstrap-icons' + ext)
                if os.path.exists(candidate):
                    bi_font_path = candidate
                    bi_font_ext = ext
                    break
            if bi_font_path:
                break
        if bi_font_path:
            fmt_map = {'.woff': 'woff', '.woff2': 'woff2', '.ttf': 'truetype', '.otf': 'opentype'}
            bi_fmt = fmt_map.get(bi_font_ext, 'woff')
            if bi_font_path not in _icon_font_b64_cache:
                with open(bi_font_path, 'rb') as f:
                    _icon_font_b64_cache[bi_font_path] = base64.b64encode(f.read()).decode('utf-8')
            bi_b64 = _icon_font_b64_cache[bi_font_path]
            font_styles += (
                f'<style>@font-face{{font-family:"bootstrap-icons";'
                f'src:url("data:font/{bi_fmt};base64,{bi_b64}") format("{bi_fmt}");}}</style>\n'
            )
            print(f"[SVG] Embedded Bootstrap Icons font ({bi_fmt}) at SVG level")
        else:
            print("[SVG] Bootstrap Icons font not found — icons may render as boxes")

    svg = f'<svg width="{width_px}" height="{height_px}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}">\n'
    svg += font_styles
    svg += f'  <rect width="{width_px}" height="{height_px}" fill="white" stroke="black" stroke-width="0.5"/>\n'
    
    layout = template.get_layout()
    
    for idx, element in enumerate(layout):
        if element.get('visible') is False:
            continue

        x_px = element['x_mm'] * MM_TO_PX
        y_px = element['y_mm'] * MM_TO_PX
        w_px = element.get('width_mm', 10) * MM_TO_PX
        h_px = element.get('height_mm', 10) * MM_TO_PX
        rot_deg = element.get('rotation_deg', 0) or 0
        cx_px = x_px + w_px / 2
        cy_px = y_px + h_px / 2

        # Open rotation wrapper if needed
        if rot_deg:
            svg += f'  <g transform="rotate({rot_deg}, {cx_px}, {cy_px})">\n'

        if element['type'] == 'text':
            # Get content, handle missing field
            content = element.get('content', '')
            content = replace_placeholders(content, data)
            print(f"[SVG] Element {idx}: TEXT = '{content}' (template: '{element.get('content', '')}')")

            font_size_mm = element.get('font_size_mm', 4)
            font_size = (font_size_mm * MM_TO_PX) if font_size_mm else element.get('font_size', 12)
            line_height = font_size * 1.2

            color = element.get('color', '#000000')
            text_align = element.get('text_align', 'left')
            font_family = element.get('font_family') or 'Arial'
            if not font_family or font_family == 'default':
                font_family = 'Arial'
            font_family_quoted = f"'{font_family}'" if ' ' in font_family else font_family
            font_weight = element.get('font_weight', 'normal') or 'normal'
            font_style = element.get('font_style', 'normal') or 'normal'

            anchor = 'start'
            x_text = x_px
            if text_align == 'center':
                anchor = 'middle'
                x_text = x_px + w_px / 2
            elif text_align == 'right':
                anchor = 'end'
                x_text = x_px + w_px

            print(f"[SVG] Element {idx}: Font = '{font_family}', weight={font_weight}, style={font_style}")

            # Split on newlines; render each line as a <tspan>
            lines = content.split('\n') if '\n' in content else [content]
            # Escape XML in each line
            escaped = [
                l.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                for l in lines
            ]

            svg += (
                f'  <text x="{x_text}" y="{y_px}" font-size="{font_size}" '
                f'fill="{color}" text-anchor="{anchor}" dominant-baseline="hanging" '
                f'font-weight="{font_weight}" font-style="{font_style}" '
                f'style="font-family: {font_family_quoted};">\n'
            )
            for i, line in enumerate(escaped):
                dy = 0 if i == 0 else line_height
                svg += f'    <tspan x="{x_text}" dy="{dy}">{line}</tspan>\n'
            svg += '  </text>\n'

        elif element['type'] == 'qr':
            source_field = element['source_field']
            qr_data = replace_placeholders(source_field, data)
            print(f"[SVG] Element {idx}: QR = '{qr_data}' (template: '{source_field}')")
            try:
                qr_svg = generate_qr_svg(qr_data, int(w_px), int(h_px))
                svg += f'  <g transform="translate({x_px}, {y_px})">{qr_svg}</g>\n'
            except Exception as e:
                print(f"[SVG] QR generation error: {e}")
                svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" fill="lightgray" stroke="red" stroke-width="1"/>\n'
                svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" text-anchor="middle">QR Error</text>\n'

        elif element['type'] == 'barcode':
            source_field = element['source_field']
            barcode_data = replace_placeholders(source_field, data)
            print(f"[SVG] Element {idx}: BARCODE = '{barcode_data}' (template: '{source_field}')")
            barcode_format = element.get('format', 'CODE128')
            show_label = element.get('show_label', False)
            try:
                barcode_svg = generate_barcode_svg(barcode_data, barcode_format, int(w_px), int(h_px), show_label=show_label)
                svg += f'  <g transform="translate({x_px}, {y_px})">{barcode_svg}</g>\n'
            except Exception as e:
                print(f"[SVG] Barcode generation error: {e}")
                svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" fill="lightgray" stroke="red" stroke-width="1"/>\n'
                svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" text-anchor="middle">Barcode Error</text>\n'

        elif element['type'] == 'icon':
            icon_name = element.get('icon_name', '')
            icon_color = element.get('icon_color', '#000000')
            icon_size_px = min(w_px, h_px) * 0.8
            if icon_name:
                print(f"[SVG] Element {idx}: ICON = '{icon_name}' (container: {w_px}×{h_px}px, scaled size: {icon_size_px}px, color: {icon_color})")
                try:
                    icon_svg = generate_icon_svg(icon_name, int(icon_size_px), icon_color, int(w_px), int(h_px), include_defs=False)
                    svg += f'  <g transform="translate({x_px}, {y_px})">{icon_svg}</g>\n'
                except Exception as e:
                    print(f"[SVG] Icon generation error: {e}")
                    svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" fill="lightgray" stroke="red" stroke-width="1"/>\n'
                    svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" text-anchor="middle">Icon Error</text>\n'
            else:
                print(f"[SVG] Element {idx}: ICON - No icon name specified")

        elif element['type'] == 'picture':
            picture_url = element.get('picture_url') or ''
            print(f"[SVG] Element {idx}: PICTURE url='{picture_url}'")
            img_b64 = None
            mime = 'image/png'
            if picture_url:
                try:
                    # picture_url is like /uploads/share/<category>/<filename>
                    parts = picture_url.strip('/').split('/')
                    # expected: ['uploads', 'share', category, filename]
                    if len(parts) >= 4 and parts[0] == 'uploads' and parts[1] == 'share':
                        category = parts[2]
                        filename = '/'.join(parts[3:])
                        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'share', category, filename)
                        ext = os.path.splitext(filename)[1].lower()
                        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                                    '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml'}
                        mime = mime_map.get(ext, 'image/png')
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                img_b64 = base64.b64encode(f.read()).decode('utf-8')
                            print(f"[SVG] PICTURE loaded {len(img_b64)} b64 chars from {file_path}")
                        else:
                            print(f"[SVG] PICTURE file not found: {file_path}")
                except Exception as e:
                    print(f"[SVG] PICTURE load error: {e}")
            if img_b64:
                svg += f'  <image x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" href="data:{mime};base64,{img_b64}" preserveAspectRatio="xMidYMid meet"/>\n'
            else:
                svg += f'  <rect x="{x_px}" y="{y_px}" width="{w_px}" height="{h_px}" fill="#f0e8ff" stroke="#6610f2" stroke-width="1" stroke-dasharray="3,2"/>\n'
                svg += f'  <text x="{x_px + w_px/2}" y="{y_px + h_px/2}" font-size="8" text-anchor="middle" dominant-baseline="middle" fill="#6610f2">Picture</text>\n'

        # Close rotation wrapper
        if rot_deg:
            svg += '  </g>\n'
    
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

def generate_icon_svg(icon_name, icon_size, icon_color, container_width, container_height, include_defs=True):
    """Generate an icon SVG fragment using the Bootstrap Icons font.

    When include_defs=False the @font-face <defs> block is omitted — use this
    when the caller already embeds the font at the top-level SVG so the font
    declaration is not buried inside a <g> element (which breaks most renderers).
    """
    import os
    import base64

    print(f"[ICON] Generating icon: {icon_name} (size: {icon_size}px, color: {icon_color})")

    try:
        center_x = container_width / 2
        center_y = container_height / 2

        icon_unicode_char = get_icon_unicode(icon_name)
        if not icon_unicode_char:
            print(f"[ICON] Warning: Could not find unicode for {icon_name}")
            svg = f'<circle cx="{center_x}" cy="{center_y}" r="{min(container_width, container_height) * 0.3}" fill="{icon_color}" opacity="0.5"/>'
            return svg

        # Locate the Bootstrap Icons font file (prefer woff, then woff2)
        icons_dir = os.path.join(current_app.root_path, 'static', 'icons')
        fonts_subdir = os.path.join(icons_dir, 'fonts')
        font_path = None
        font_ext = None
        for ext in ['.woff', '.woff2', '.ttf', '.otf']:
            for search_dir in [fonts_subdir, icons_dir]:
                candidate = os.path.join(search_dir, 'bootstrap-icons' + ext)
                if os.path.exists(candidate):
                    font_path = candidate
                    font_ext = ext
                    break
            if font_path:
                break

        if not font_path:
            print("[ICON] Bootstrap Icons font not found, falling back to circle")
            svg = f'<circle cx="{center_x}" cy="{center_y}" r="{min(container_width, container_height) * 0.3}" fill="{icon_color}" opacity="0.5"/>'
            return svg

        # Embed font as base64 so SVG is self-contained in all output formats
        fmt_map = {'.woff': 'woff', '.woff2': 'woff2', '.ttf': 'truetype', '.otf': 'opentype'}
        font_format = fmt_map.get(font_ext, 'woff')
        if font_path not in _icon_font_b64_cache:
            with open(font_path, 'rb') as f:
                _icon_font_b64_cache[font_path] = base64.b64encode(f.read()).decode('utf-8')
        font_b64 = _icon_font_b64_cache[font_path]

        codepoint = ord(icon_unicode_char)
        unicode_escape = f'&#x{codepoint:04X};'

        text_el = (
            f'<text x="{center_x}" y="{center_y}" '
            f'font-family="bootstrap-icons" font-size="{icon_size}" '
            f'fill="{icon_color}" text-anchor="middle" dominant-baseline="central">'
            f'{unicode_escape}</text>'
        )

        if include_defs:
            font_face = (
                f'<defs><style>'
                f'@font-face{{font-family:"bootstrap-icons";'
                f'src:url("data:font/{font_format};base64,{font_b64}") format("{font_format}");}}'
                f'</style></defs>'
            )
            svg = font_face + text_el
        else:
            svg = text_el
        print(f"[ICON] Success! Generated icon SVG (include_defs={include_defs}), {len(svg)} bytes")
        return svg

    except Exception as e:
        print(f"[ICON] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        placeholder = (
            f'<rect width="{container_width}" height="{container_height}" fill="lightgray" stroke="red" stroke-width="2"/>'
            f'<text x="{container_width/2}" y="{container_height/2}" font-size="12" text-anchor="middle" dominant-baseline="middle">Icon Error</text>'
        )
        return placeholder

_icon_font_b64_cache = {}  # font_path -> (b64_string, format_string)


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
