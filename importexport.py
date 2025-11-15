"""
Import/Export module for managing data configurations
Handles export and import of Magic Parameters, Locations, Racks, Categories, Footprints, and Tags
"""

import json
from datetime import datetime
from models import (
    db, MagicParameter, ParameterTemplate, TemplateParameter, 
    ParameterUnit, ParameterStringOption, ItemParameter,
    Location, Rack, Category, Footprint, Tag, Item
)


class DataExporter:
    """Handles exporting data to JSON"""
    
    @staticmethod
    def export_magic_parameters(include_item_values=False, include_parameters=True, include_templates=True, include_units=True, include_options=True):
        """Export Magic Parameters configuration with granular control"""
        parameters = []
        if include_parameters:
            for param in MagicParameter.query.all():
                param_data = {
                    'name': param.name,
                    'param_type': param.param_type,
                    'description': param.description,
                    'notify_enabled': param.notify_enabled,
                }
                if include_units and param.param_type == 'number':
                    param_data['units'] = [unit.unit for unit in param.units]
                else:
                    param_data['units'] = []
                    
                if include_options and param.param_type == 'string':
                    param_data['string_options'] = [opt.value for opt in param.string_options]
                else:
                    param_data['string_options'] = []
                    
                parameters.append(param_data)
        
        templates = []
        if include_templates:
            for template in ParameterTemplate.query.all():
                template_data = {
                    'name': template.name,
                    'description': template.description,
                    'parameters': [
                        {
                            'parameter_name': tp.parameter.name,
                            'operation': tp.operation,
                            'value': tp.value,
                            'value2': tp.value2,
                            'unit': tp.unit,
                            'string_option': tp.string_option
                        }
                        for tp in template.template_parameters
                    ]
                }
                templates.append(template_data)
        
        item_parameters = []
        if include_item_values and include_parameters:
            for ip in ItemParameter.query.all():
                item_param_data = {
                    'item_sku': ip.item.sku or ip.item.name,
                    'parameter_name': ip.parameter.name,
                    'operation': ip.operation,
                    'value': ip.value,
                    'value2': ip.value2,
                    'unit': ip.unit,
                    'string_option': ip.string_option,
                    'description': ip.description
                }
                item_parameters.append(item_param_data)
        
        return {
            'parameters': parameters,
            'templates': templates,
            'item_parameters': item_parameters
        }
    
    @staticmethod
    def export_locations():
        """Export Locations data"""
        locations = []
        for loc in Location.query.all():
            loc_data = {
                'name': loc.name,
                'info': loc.info,
                'description': loc.description,
                'color': loc.color
            }
            locations.append(loc_data)
        return {'locations': locations}
    
    @staticmethod
    def export_racks():
        """Export Racks data"""
        racks = []
        for rack in Rack.query.all():
            rack_data = {
                'name': rack.name,
                'description': rack.description,
                'location_name': rack.physical_location.name if rack.physical_location else None,
                'color': rack.color,
                'rows': rack.rows,
                'cols': rack.cols,
                'unavailable_drawers': rack.unavailable_drawers
            }
            racks.append(rack_data)
        return {'racks': racks}
    
    @staticmethod
    def export_categories():
        """Export Categories data"""
        categories = []
        for cat in Category.query.all():
            cat_data = {
                'name': cat.name,
                'description': cat.description
            }
            categories.append(cat_data)
        return {'categories': categories}
    
    @staticmethod
    def export_footprints():
        """Export Footprints data"""
        footprints = []
        for fp in Footprint.query.all():
            fp_data = {
                'name': fp.name,
                'description': fp.description
            }
            footprints.append(fp_data)
        return {'footprints': footprints}
    
    @staticmethod
    def export_tags():
        """Export Tags data"""
        tags = []
        for tag in Tag.query.all():
            tag_data = {
                'name': tag.name,
                'color': tag.color
            }
            tags.append(tag_data)
        return {'tags': tags}
    
    @staticmethod
    def export_selective(selections, include_item_values=False):
        """
        Export selected data types with granular control for Magic Parameters
        selections: dict with keys like 'magic_parameters', 'locations', 'racks', etc.
                   magic_parameters can be a dict with: parameters, templates, units, options
        """
        export_data = {
            'export_date': datetime.now().isoformat(),
            'include_item_values': include_item_values
        }
        
        if selections.get('magic_parameters'):
            mp_opts = selections.get('magic_parameters')
            # If it's just True, export all
            if mp_opts is True:
                export_data.update(DataExporter.export_magic_parameters(include_item_values))
            else:
                # If it's a dict, use granular options
                export_data.update(DataExporter.export_magic_parameters(
                    include_item_values=include_item_values,
                    include_parameters=mp_opts.get('parameters', True),
                    include_templates=mp_opts.get('templates', True),
                    include_units=mp_opts.get('units', True),
                    include_options=mp_opts.get('options', True)
                ))
        if selections.get('locations'):
            export_data.update(DataExporter.export_locations())
        if selections.get('racks'):
            export_data.update(DataExporter.export_racks())
        if selections.get('categories'):
            export_data.update(DataExporter.export_categories())
        if selections.get('footprints'):
            export_data.update(DataExporter.export_footprints())
        if selections.get('tags'):
            export_data.update(DataExporter.export_tags())
        
        return export_data


class DataImporter:
    """Handles importing data from JSON"""
    
    def __init__(self):
        self.results = {
            'imported': 0,
            'skipped': 0,
            'errors': [],
            'details': {}
        }
    
    def import_magic_parameters(self, data, include_item_values=False, import_params=True, import_templates=True, import_units=True, import_options=True):
        """Import Magic Parameters with granular control"""
        imported = 0
        skipped = 0
        errors = []
        param_map = {}
        
        # Step 1: Import parameters
        if import_params:
            for pd in data.get('parameters', []):
                try:
                    name = pd.get('name', '').strip()
                    if not name:
                        continue
                    
                    existing = MagicParameter.query.filter_by(name=name).first()
                    if existing:
                        skipped += 1
                        param_map[name] = existing.id
                    else:
                        p = MagicParameter(
                            name=name,
                            param_type=pd.get('param_type', 'string'),
                            description=pd.get('description', ''),
                            notify_enabled=pd.get('notify_enabled', False)
                        )
                        db.session.add(p)
                        db.session.flush()
                        param_map[name] = p.id
                        imported += 1
                        
                        if import_units and pd.get('param_type') == 'number':
                            for u in pd.get('units', []):
                                if u:
                                    db.session.add(ParameterUnit(parameter_id=p.id, unit=str(u)))
                        
                        if import_options and pd.get('param_type') == 'string':
                            for o in pd.get('string_options', []):
                                if o:
                                    db.session.add(ParameterStringOption(parameter_id=p.id, value=str(o)))
                except Exception as e:
                    errors.append(f"Parameter '{pd.get('name', '?')}': {str(e)[:50]}")
            
            db.session.commit()
        else:
            # Still build param_map from existing parameters
            for pd in data.get('parameters', []):
                name = pd.get('name', '').strip()
                if name:
                    existing = MagicParameter.query.filter_by(name=name).first()
                    if existing:
                        param_map[name] = existing.id
        
        # Step 2: Import templates
        if import_templates:
            for td in data.get('templates', []):
                try:
                    name = td.get('name', '').strip()
                    if not name:
                        continue
                    
                    if not ParameterTemplate.query.filter_by(name=name).first():
                        t = ParameterTemplate(
                            name=name,
                            description=td.get('description', '')
                        )
                        db.session.add(t)
                        db.session.flush()
                        
                        for tpd in td.get('parameters', []):
                            param_id = param_map.get(tpd.get('parameter_name'))
                            if param_id:
                                db.session.add(TemplateParameter(
                                    template_id=t.id,
                                    parameter_id=param_id,
                                    operation=str(tpd.get('operation') or ''),
                                    value=str(tpd.get('value') or ''),
                                    value2=str(tpd.get('value2') or ''),
                                    unit=str(tpd.get('unit') or ''),
                                    string_option=str(tpd.get('string_option') or '')
                                ))
                        imported += 1
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append(f"Template '{td.get('name', '?')}': {str(e)[:50]}")
            
            db.session.commit()
        
        # Step 3: Import item parameters if requested
        item_params_imported = 0
        item_params_skipped = 0
        if include_item_values and import_params:
            for ipd in data.get('item_parameters', []):
                try:
                    item_sku = ipd.get('item_sku', '').strip()
                    param_name = ipd.get('parameter_name', '').strip()
                    
                    if not item_sku or not param_name:
                        continue
                    
                    item = Item.query.filter_by(sku=item_sku).first() or Item.query.filter_by(name=item_sku).first()
                    param_id = param_map.get(param_name)
                    
                    if item and param_id:
                        existing = ItemParameter.query.filter_by(
                            item_id=item.id,
                            parameter_id=param_id
                        ).first()
                        
                        if existing:
                            item_params_skipped += 1
                        else:
                            db.session.add(ItemParameter(
                                item_id=item.id,
                                parameter_id=param_id,
                                operation=str(ipd.get('operation') or ''),
                                value=str(ipd.get('value') or ''),
                                value2=str(ipd.get('value2') or ''),
                                unit=str(ipd.get('unit') or ''),
                                string_option=str(ipd.get('string_option') or ''),
                                description=str(ipd.get('description') or '')
                            ))
                            item_params_imported += 1
                except Exception as e:
                    errors.append(f"Item parameter for '{ipd.get('item_sku', '?')}': {str(e)[:50]}")
            
            db.session.commit()
        
        self.results['details']['magic_parameters'] = {
            'imported': imported,
            'skipped': skipped,
            'item_parameters': {
                'imported': item_params_imported,
                'skipped': item_params_skipped
            }
        }
        self.results['imported'] += imported + item_params_imported
        self.results['skipped'] += skipped + item_params_skipped
        self.results['errors'].extend(errors)
    
    def import_locations(self, data):
        """Import Locations"""
        imported = 0
        skipped = 0
        errors = []
        
        for ld in data.get('locations', []):
            try:
                name = ld.get('name', '').strip()
                if not name:
                    continue
                
                # Allow duplicate names - UUID ensures uniqueness
                loc = Location(
                    name=name,
                    info=ld.get('info', ''),
                    description=ld.get('description', ''),
                    color=ld.get('color', '#6c757d')
                )
                db.session.add(loc)
                imported += 1
            except Exception as e:
                errors.append(f"Location '{ld.get('name', '?')}': {str(e)[:50]}")
        
        db.session.commit()
        
        self.results['details']['locations'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)
    
    def import_racks(self, data):
        """Import Racks"""
        imported = 0
        skipped = 0
        errors = []
        
        for rd in data.get('racks', []):
            try:
                name = rd.get('name', '').strip()
                if not name:
                    continue
                
                # Allow duplicate names - UUID ensures uniqueness
                location_id = None
                location_name = rd.get('location_name', '').strip()
                if location_name:
                    # Get first matching location by name (since names can now be duplicated)
                    loc = Location.query.filter_by(name=location_name).first()
                    if loc:
                        location_id = loc.id
                
                rack = Rack(
                    name=name,
                    description=rd.get('description', ''),
                    location_id=location_id,
                    color=rd.get('color', '#6c757d'),
                    rows=rd.get('rows', 5),
                    cols=rd.get('cols', 5),
                    unavailable_drawers=rd.get('unavailable_drawers', '')
                )
                db.session.add(rack)
                imported += 1
            except Exception as e:
                errors.append(f"Rack '{rd.get('name', '?')}': {str(e)[:50]}")
        
        db.session.commit()
        
        self.results['details']['racks'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)
    
    def import_categories(self, data):
        """Import Categories"""
        imported = 0
        skipped = 0
        errors = []
        
        for cd in data.get('categories', []):
            try:
                name = cd.get('name', '').strip()
                if not name:
                    continue
                
                existing = Category.query.filter_by(name=name).first()
                if existing:
                    skipped += 1
                else:
                    cat = Category(
                        name=name,
                        description=cd.get('description', '')
                    )
                    db.session.add(cat)
                    imported += 1
            except Exception as e:
                errors.append(f"Category '{cd.get('name', '?')}': {str(e)[:50]}")
        
        db.session.commit()
        
        self.results['details']['categories'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)
    
    def import_footprints(self, data):
        """Import Footprints"""
        imported = 0
        skipped = 0
        errors = []
        
        for fd in data.get('footprints', []):
            try:
                name = fd.get('name', '').strip()
                if not name:
                    continue
                
                existing = Footprint.query.filter_by(name=name).first()
                if existing:
                    skipped += 1
                else:
                    fp = Footprint(
                        name=name,
                        description=fd.get('description', '')
                    )
                    db.session.add(fp)
                    imported += 1
            except Exception as e:
                errors.append(f"Footprint '{fd.get('name', '?')}': {str(e)[:50]}")
        
        db.session.commit()
        
        self.results['details']['footprints'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)
    
    def import_tags(self, data):
        """Import Tags"""
        imported = 0
        skipped = 0
        errors = []
        
        for td in data.get('tags', []):
            try:
                name = td.get('name', '').strip()
                if not name:
                    continue
                
                existing = Tag.query.filter_by(name=name).first()
                if existing:
                    skipped += 1
                else:
                    tag = Tag(
                        name=name,
                        color=td.get('color', '#6c757d')
                    )
                    db.session.add(tag)
                    imported += 1
            except Exception as e:
                errors.append(f"Tag '{td.get('name', '?')}': {str(e)[:50]}")
        
        db.session.commit()
        
        self.results['details']['tags'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)
    
    def import_selective(self, data, selections):
        """
        Import selected data types with granular control for Magic Parameters
        selections: dict with keys like 'magic_parameters', 'locations', 'racks', etc.
                   magic_parameters can be a dict with: parameters, templates, units, options
        """
        self.results['details'] = {}
        
        if selections.get('magic_parameters'):
            mp_opts = selections.get('magic_parameters')
            include_item_values = data.get('include_item_values', False)
            
            # If it's just True, import all
            if mp_opts is True:
                self.import_magic_parameters(data, include_item_values)
            else:
                # If it's a dict, use granular options
                self.import_magic_parameters(
                    data,
                    include_item_values=include_item_values,
                    import_params=mp_opts.get('parameters', True),
                    import_templates=mp_opts.get('templates', True),
                    import_units=mp_opts.get('units', True),
                    import_options=mp_opts.get('options', True)
                )
        
        if selections.get('locations'):
            self.import_locations(data)
        if selections.get('racks'):
            self.import_racks(data)
        if selections.get('categories'):
            self.import_categories(data)
        if selections.get('footprints'):
            self.import_footprints(data)
        if selections.get('tags'):
            self.import_tags(data)
        
        return self.results
