"""
Import/Export module for managing data configurations
Handles export and import of settings: Locations, Racks, Item Categories/Footprints/Tags,
Magic Parameters (Number/String/Date/Templates), Project Categories/Tags/Statuses,
and Contacts (Persons, Organizations, Groups).
"""

import json
from datetime import datetime
from models import (
    db, MagicParameter, ParameterTemplate, TemplateParameter,
    ParameterUnit, ParameterStringOption, ItemParameter,
    Location, Rack, Category, Footprint, Tag, Item,
    ProjectCategory, ProjectTag, ProjectStatus,
    ContactOrganization, ContactPerson, ContactGroup, ContactGroupMember,
)


class DataExporter:
    """Handles exporting data to JSON"""

    @staticmethod
    def export_magic_parameters(include_item_values=False, types=None, include_templates=True):
        """
        Export Magic Parameters.
        types: set of param_type strings to include e.g. {'number','string','date'}. None = all.
        include_templates: whether to include ParameterTemplates.
        """
        parameters = []
        query = MagicParameter.query
        if types is not None:
            query = query.filter(MagicParameter.param_type.in_(list(types)))
        for param in query.all():
            param_data = {
                'name': param.name,
                'param_type': param.param_type,
                'description': param.description,
                'notify_enabled': param.notify_enabled,
                'units': [],
                'string_options': [],
            }
            if param.param_type == 'number':
                param_data['units'] = [u.unit for u in param.units]
            elif param.param_type == 'string':
                param_data['string_options'] = [o.value for o in param.string_options]
            parameters.append(param_data)

        templates = []
        if include_templates:
            for tmpl in ParameterTemplate.query.all():
                templates.append({
                    'name': tmpl.name,
                    'description': tmpl.description,
                    'parameters': [
                        {
                            'parameter_name': tp.parameter.name,
                            'operation': tp.operation,
                            'value': tp.value,
                            'value2': tp.value2,
                            'unit': tp.unit,
                            'string_option': tp.string_option,
                        }
                        for tp in tmpl.template_parameters
                    ],
                })

        item_parameters = []
        if include_item_values:
            for ip in ItemParameter.query.all():
                if types is None or ip.parameter.param_type in types:
                    item_parameters.append({
                        'item_sku': ip.item.sku or ip.item.name,
                        'parameter_name': ip.parameter.name,
                        'operation': ip.operation,
                        'value': ip.value,
                        'value2': ip.value2,
                        'unit': ip.unit,
                        'string_option': ip.string_option,
                        'description': ip.description,
                    })

        return {'parameters': parameters, 'templates': templates, 'item_parameters': item_parameters}

    @staticmethod
    def export_locations():
        return {'locations': [
            {'name': l.name, 'info': l.info, 'description': l.description, 'color': l.color}
            for l in Location.query.all()
        ]}

    @staticmethod
    def export_racks():
        return {'racks': [
            {
                'name': r.name,
                'description': r.description,
                'location_name': r.physical_location.name if r.physical_location else None,
                'color': r.color,
                'rows': r.rows,
                'cols': r.cols,
                'unavailable_drawers': r.unavailable_drawers or '[]',
                'merged_cells': r.merged_cells or '[]',
            }
            for r in Rack.query.all()
        ]}

    @staticmethod
    def export_categories():
        return {'categories': [
            {'name': c.name, 'description': c.description}
            for c in Category.query.all()
        ]}

    @staticmethod
    def export_footprints():
        return {'footprints': [
            {'name': f.name, 'description': f.description}
            for f in Footprint.query.all()
        ]}

    @staticmethod
    def export_tags():
        return {'tags': [
            {'name': t.name, 'color': t.color}
            for t in Tag.query.all()
        ]}

    @staticmethod
    def export_project_categories():
        return {'project_categories': [
            {'name': c.name, 'description': c.description or '', 'color': c.color}
            for c in ProjectCategory.query.all()
        ]}

    @staticmethod
    def export_project_tags():
        return {'project_tags': [
            {'name': t.name, 'description': t.description or '', 'color': t.color}
            for t in ProjectTag.query.all()
        ]}

    @staticmethod
    def export_project_statuses():
        return {'project_statuses': [
            {'name': s.name, 'description': s.description or '', 'color': s.color}
            for s in ProjectStatus.query.all()
        ]}

    @staticmethod
    def export_contact_persons():
        rows = []
        for p in ContactPerson.query.all():
            org_name = p.organization.name if p.organization else None
            rows.append({'name': p.name, 'email': p.email or '', 'tel': p.tel or '', 'organization_name': org_name})
        return {'contact_persons': rows}

    @staticmethod
    def export_contact_organizations():
        return {'contact_organizations': [
            {'name': o.name, 'email': o.email or '', 'tel': o.tel or '', 'url': o.url or '',
             'address': o.address or '', 'zip_code': o.zip_code or '', 'info': o.info or ''}
            for o in ContactOrganization.query.all()
        ]}

    @staticmethod
    def export_contact_groups():
        groups = []
        for g in ContactGroup.query.all():
            members = []
            for m in g.members:
                if m.person_id and m.person:
                    members.append({'type': 'person', 'name': m.person.name})
                elif m.organization_id and m.org:
                    members.append({'type': 'organization', 'name': m.org.name})
            groups.append({'name': g.name, 'description': g.description or '', 'members': members})
        return {'contact_groups': groups}

    @staticmethod
    def export_selective(selections, include_item_values=False):
        """
        Export selected data types.
        selections keys: magic_parameters (dict or True), locations, racks, categories,
          footprints, tags, project_categories, project_tags, project_statuses,
          contact_persons, contact_organizations, contact_groups.
        magic_parameters dict keys: number, string, date, template (booleans).
        """
        export_data = {
            'export_date': datetime.now().isoformat(),
            'include_item_values': include_item_values,
        }

        mp_opts = selections.get('magic_parameters')
        if mp_opts:
            if mp_opts is True:
                export_data.update(DataExporter.export_magic_parameters(include_item_values))
            else:
                types = set()
                if mp_opts.get('number'): types.add('number')
                if mp_opts.get('string'): types.add('string')
                if mp_opts.get('date'): types.add('date')
                include_templates = bool(mp_opts.get('template', False))
                export_data.update(DataExporter.export_magic_parameters(
                    include_item_values,
                    types=types if types else None,
                    include_templates=include_templates,
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
        if selections.get('project_categories'):
            export_data.update(DataExporter.export_project_categories())
        if selections.get('project_tags'):
            export_data.update(DataExporter.export_project_tags())
        if selections.get('project_statuses'):
            export_data.update(DataExporter.export_project_statuses())
        if selections.get('contact_persons'):
            export_data.update(DataExporter.export_contact_persons())
        if selections.get('contact_organizations'):
            export_data.update(DataExporter.export_contact_organizations())
        if selections.get('contact_groups'):
            export_data.update(DataExporter.export_contact_groups())

        return export_data


class DataImporter:
    """Handles importing data from JSON"""

    def __init__(self):
        self.results = {'imported': 0, 'skipped': 0, 'errors': [], 'details': {}}

    def import_magic_parameters(self, data, include_item_values=False, types=None, import_templates=True,
                                 import_params=True, import_units=True, import_options=True):
        """
        Import Magic Parameters.
        types: set of param_type strings to include. None = all.
        import_params, import_units, import_options kept for backward compat.
        import_templates: whether to import templates.
        """
        imported = 0
        skipped = 0
        errors = []
        param_map = {}

        if import_params:
            for pd in data.get('parameters', []):
                try:
                    ptype = pd.get('param_type', 'string')
                    if types is not None and ptype not in types:
                        continue
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
                            param_type=ptype,
                            description=pd.get('description', ''),
                            notify_enabled=pd.get('notify_enabled', False),
                        )
                        db.session.add(p)
                        db.session.flush()
                        param_map[name] = p.id
                        imported += 1
                        if import_units and ptype == 'number':
                            for u in pd.get('units', []):
                                if u:
                                    db.session.add(ParameterUnit(parameter_id=p.id, unit=str(u)))
                        if import_options and ptype == 'string':
                            for o in pd.get('string_options', []):
                                if o:
                                    db.session.add(ParameterStringOption(parameter_id=p.id, value=str(o)))
                except Exception as e:
                    errors.append(f"Parameter '{pd.get('name', '?')}': {str(e)[:50]}")
            db.session.commit()
        else:
            for pd in data.get('parameters', []):
                name = pd.get('name', '').strip()
                if name:
                    existing = MagicParameter.query.filter_by(name=name).first()
                    if existing:
                        param_map[name] = existing.id

        if import_templates:
            for td in data.get('templates', []):
                try:
                    name = td.get('name', '').strip()
                    if not name:
                        continue
                    if not ParameterTemplate.query.filter_by(name=name).first():
                        t = ParameterTemplate(name=name, description=td.get('description', ''))
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
                                    string_option=str(tpd.get('string_option') or ''),
                                ))
                        imported += 1
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append(f"Template '{td.get('name', '?')}': {str(e)[:50]}")
            db.session.commit()

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
                        if ItemParameter.query.filter_by(item_id=item.id, parameter_id=param_id).first():
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
                                description=str(ipd.get('description') or ''),
                            ))
                            item_params_imported += 1
                except Exception as e:
                    errors.append(f"Item param '{ipd.get('item_sku', '?')}': {str(e)[:50]}")
            db.session.commit()

        self.results['details']['magic_parameters'] = {
            'imported': imported, 'skipped': skipped,
            'item_parameters': {'imported': item_params_imported, 'skipped': item_params_skipped},
        }
        self.results['imported'] += imported + item_params_imported
        self.results['skipped'] += skipped + item_params_skipped
        self.results['errors'].extend(errors)

    def import_locations(self, data):
        imported = 0
        skipped = 0
        errors = []
        for ld in data.get('locations', []):
            try:
                name = ld.get('name', '').strip()
                if not name:
                    continue
                loc = Location(name=name, info=ld.get('info', ''), description=ld.get('description', ''), color=ld.get('color', '#6c757d'))
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
        imported = 0
        skipped = 0
        errors = []
        for rd in data.get('racks', []):
            try:
                name = rd.get('name', '').strip()
                if not name:
                    continue
                location_id = None
                loc_name = rd.get('location_name', '').strip()
                if loc_name:
                    loc = Location.query.filter_by(name=loc_name).first()
                    if loc:
                        location_id = loc.id
                rack = Rack(
                    name=name,
                    description=rd.get('description', ''),
                    location_id=location_id,
                    color=rd.get('color', '#6c757d'),
                    rows=rd.get('rows', 5),
                    cols=rd.get('cols', 5),
                    unavailable_drawers=rd.get('unavailable_drawers', '[]'),
                    merged_cells=rd.get('merged_cells', '[]'),
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
        imported = 0
        skipped = 0
        errors = []
        for cd in data.get('categories', []):
            try:
                name = cd.get('name', '').strip()
                if not name:
                    continue
                if Category.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(Category(name=name, description=cd.get('description', '')))
                    imported += 1
            except Exception as e:
                errors.append(f"Category '{cd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['categories'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_footprints(self, data):
        imported = 0
        skipped = 0
        errors = []
        for fd in data.get('footprints', []):
            try:
                name = fd.get('name', '').strip()
                if not name:
                    continue
                if Footprint.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(Footprint(name=name, description=fd.get('description', '')))
                    imported += 1
            except Exception as e:
                errors.append(f"Footprint '{fd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['footprints'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_tags(self, data):
        imported = 0
        skipped = 0
        errors = []
        for td in data.get('tags', []):
            try:
                name = td.get('name', '').strip()
                if not name:
                    continue
                if Tag.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(Tag(name=name, color=td.get('color', '#6c757d')))
                    imported += 1
            except Exception as e:
                errors.append(f"Tag '{td.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['tags'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_project_categories(self, data):
        imported = 0
        skipped = 0
        errors = []
        for cd in data.get('project_categories', []):
            try:
                name = cd.get('name', '').strip()
                if not name:
                    continue
                if ProjectCategory.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(ProjectCategory(name=name, description=cd.get('description', ''), color=cd.get('color', '#6c757d')))
                    imported += 1
            except Exception as e:
                errors.append(f"Project category '{cd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['project_categories'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_project_tags(self, data):
        imported = 0
        skipped = 0
        errors = []
        for td in data.get('project_tags', []):
            try:
                name = td.get('name', '').strip()
                if not name:
                    continue
                if ProjectTag.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(ProjectTag(name=name, description=td.get('description', ''), color=td.get('color', '#6c757d')))
                    imported += 1
            except Exception as e:
                errors.append(f"Project tag '{td.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['project_tags'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_project_statuses(self, data):
        imported = 0
        skipped = 0
        errors = []
        for sd in data.get('project_statuses', []):
            try:
                name = sd.get('name', '').strip()
                if not name:
                    continue
                if ProjectStatus.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(ProjectStatus(name=name, description=sd.get('description', ''), color=sd.get('color', '#6c757d')))
                    imported += 1
            except Exception as e:
                errors.append(f"Project status '{sd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['project_statuses'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_contact_organizations(self, data):
        imported = 0
        skipped = 0
        errors = []
        for od in data.get('contact_organizations', []):
            try:
                name = od.get('name', '').strip()
                if not name:
                    continue
                if ContactOrganization.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(ContactOrganization(
                        name=name, email=od.get('email', ''), tel=od.get('tel', ''),
                        url=od.get('url', ''), address=od.get('address', '') or None,
                        zip_code=od.get('zip_code', '') or None, info=od.get('info', ''),
                    ))
                    imported += 1
            except Exception as e:
                errors.append(f"Organization '{od.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['contact_organizations'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_contact_persons(self, data):
        imported = 0
        skipped = 0
        errors = []
        for pd in data.get('contact_persons', []):
            try:
                name = pd.get('name', '').strip()
                if not name:
                    continue
                organization_id = None
                org_name = (pd.get('organization_name') or '').strip()
                if org_name:
                    org = ContactOrganization.query.filter_by(name=org_name).first()
                    if org:
                        organization_id = org.id
                if ContactPerson.query.filter_by(name=name).first():
                    skipped += 1
                else:
                    db.session.add(ContactPerson(
                        name=name, email=pd.get('email', ''), tel=pd.get('tel', ''),
                        organization_id=organization_id,
                    ))
                    imported += 1
            except Exception as e:
                errors.append(f"Person '{pd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['contact_persons'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_contact_groups(self, data):
        imported = 0
        skipped = 0
        errors = []
        for gd in data.get('contact_groups', []):
            try:
                name = gd.get('name', '').strip()
                if not name:
                    continue
                if ContactGroup.query.filter_by(name=name).first():
                    skipped += 1
                    continue
                g = ContactGroup(name=name, description=gd.get('description', ''))
                db.session.add(g)
                db.session.flush()
                for md in gd.get('members', []):
                    mtype = md.get('type', '')
                    mname = md.get('name', '').strip()
                    if mtype == 'person' and mname:
                        p = ContactPerson.query.filter_by(name=mname).first()
                        if p:
                            db.session.add(ContactGroupMember(group_id=g.id, person_id=p.id))
                    elif mtype == 'organization' and mname:
                        o = ContactOrganization.query.filter_by(name=mname).first()
                        if o:
                            db.session.add(ContactGroupMember(group_id=g.id, organization_id=o.id))
                imported += 1
            except Exception as e:
                errors.append(f"Group '{gd.get('name', '?')}': {str(e)[:50]}")
        db.session.commit()
        self.results['details']['contact_groups'] = {'imported': imported, 'skipped': skipped}
        self.results['imported'] += imported
        self.results['skipped'] += skipped
        self.results['errors'].extend(errors)

    def import_selective(self, data, selections):
        """
        Import selected data types.
        selections keys: magic_parameters (dict or True/False), locations, racks, categories,
          footprints, tags, project_categories, project_tags, project_statuses,
          contact_persons, contact_organizations, contact_groups.
        magic_parameters dict keys: number, string, date, template (booleans).
        """
        self.results['details'] = {}
        include_item_values = data.get('include_item_values', False)

        mp_opts = selections.get('magic_parameters')
        if mp_opts:
            if mp_opts is True:
                self.import_magic_parameters(data, include_item_values)
            else:
                types = set()
                if mp_opts.get('number'): types.add('number')
                if mp_opts.get('string'): types.add('string')
                if mp_opts.get('date'): types.add('date')
                # backward compat: old dict uses 'parameters'/'templates'/'units'/'options' keys
                import_params = mp_opts.get('parameters', True)
                import_units = mp_opts.get('units', True)
                import_options = mp_opts.get('options', True)
                import_templates = mp_opts.get('templates', mp_opts.get('template', False))
                self.import_magic_parameters(
                    data, include_item_values,
                    types=types if types else None,
                    import_templates=import_templates,
                    import_params=import_params,
                    import_units=import_units,
                    import_options=import_options,
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
        if selections.get('project_categories'):
            self.import_project_categories(data)
        if selections.get('project_tags'):
            self.import_project_tags(data)
        if selections.get('project_statuses'):
            self.import_project_statuses(data)
        if selections.get('contact_organizations'):
            self.import_contact_organizations(data)
        if selections.get('contact_persons'):
            self.import_contact_persons(data)
        if selections.get('contact_groups'):
            self.import_contact_groups(data)

        return self.results
