"""
Item list filtering shared by the items page, its print view and the advanced search form.
"""
import json
from datetime import datetime

from sqlalchemy.orm import joinedload, selectinload

from item_stock import StockColumns, item_stock_subquery
from models import (db, Item, Category, Footprint, Rack, Tag, MagicParameter,
                    ItemParameter, ItemParameterStringValue, item_tags)

STATUS_LABELS = {'ok': 'OK', 'low': 'Low Stock', 'no': 'No Stock'}
NUMBER_OPS = ('range', 'min', 'max', 'eq')
MAX_PARAM_FILTERS = 20


def _to_float(raw):
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float('inf') else None


def _to_date(raw):
    try:
        return datetime.strptime(str(raw).strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        return None


def _int_list(args, key):
    result = []
    for raw in args.getlist(key):
        for part in str(raw).split(','):
            part = part.strip()
            if part.isdigit() and int(part) not in result:
                result.append(int(part))
    return result


def _text(args, key, limit=200):
    return (args.get(key, '') or '').strip()[:limit]


def _parse_param_filters(raw):
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(entries, list):
        return []

    result = []
    for entry in entries[:MAX_PARAM_FILTERS]:
        if not isinstance(entry, dict):
            continue
        try:
            param = db.session.get(MagicParameter, int(entry.get('id')))
        except (TypeError, ValueError):
            param = None
        if not param:
            continue

        crit = {'id': param.id, 'name': param.name, 'type': param.param_type,
                'join': 'or' if entry.get('join') == 'or' and result else 'and'}
        if param.param_type == 'number':
            units = entry.get('units') if isinstance(entry.get('units'), list) else []
            crit['units'] = [str(u)[:50] for u in units if str(u).strip()]
            op = entry.get('op') if entry.get('op') in NUMBER_OPS else 'range'
            low, high = _to_float(entry.get('min')), _to_float(entry.get('max'))
            if op == 'eq':
                high = low
            elif op == 'min':
                high = None
            elif op == 'max':
                low = None
            elif low is not None and high is not None and low > high:
                low, high = high, low
            crit.update(op=op, min=low, max=high)
        elif param.param_type == 'string':
            values = entry.get('values') if isinstance(entry.get('values'), list) else []
            crit['values'] = [str(v)[:128] for v in values if str(v).strip()]
            crit['mode'] = 'all' if entry.get('mode') == 'all' else 'any'
        elif param.param_type == 'date':
            start, end = _to_date(entry.get('from')), _to_date(entry.get('to'))
            if start and end and start > end:
                start, end = end, start
            crit.update({'from': start, 'to': end})
        else:
            continue
        result.append(crit)
    return result


def parse_item_filters(args, can_view_info=True, can_view_price=True):
    """Read list filters from a query string. Filters on fields the user may not view are dropped."""
    statuses = []
    for raw in args.getlist('status'):
        for part in str(raw).split(','):
            part = part.strip()
            if part in STATUS_LABELS and part not in statuses:
                statuses.append(part)

    filters = {
        'search': (args.get('search', '') or '').strip(),
        'category_id': args.get('category', 0, type=int) or 0,
        'statuses': statuses,
        'name': _text(args, 'name'),
        'uuid': _text(args, 'uuid', 32),
        'short_info': _text(args, 'short_info'),
        'sku': '', 'model': '',
        'cat_ids': [], 'tag_ids': [], 'tag_mode': 'any', 'fp_ids': [],
        'qty_min': _to_float(args.get('qty_min')),
        'qty_max': _to_float(args.get('qty_max')),
        'price_min': None, 'price_max': None,
        'params': _parse_param_filters(args.get('mp')),
    }
    if can_view_info:
        filters.update(
            sku=_text(args, 'sku'),
            model=_text(args, 'model'),
            cat_ids=_int_list(args, 'cat'),
            tag_ids=_int_list(args, 'tag'),
            tag_mode='all' if args.get('tag_mode') == 'all' else 'any',
            fp_ids=_int_list(args, 'fp'),
        )
    if can_view_price:
        filters.update(price_min=_to_float(args.get('price_min')),
                       price_max=_to_float(args.get('price_max')))
    return filters


def has_advanced_filters(filters):
    return any([
        filters['name'], filters['uuid'], filters['short_info'], filters['sku'], filters['model'],
        filters['cat_ids'], filters['tag_ids'], filters['fp_ids'], filters['params'],
        filters['qty_min'] is not None, filters['qty_max'] is not None,
        filters['price_min'] is not None, filters['price_max'] is not None,
    ])


def _number_interval(item_param):
    """The span of values an item's number parameter covers, as (low, high)."""
    value = _to_float(item_param.value)
    if value is None:
        return None
    if item_param.operation == 'range':
        value2 = _to_float(item_param.value2)
        if value2 is None:
            return (value, value)
        return (min(value, value2), max(value, value2))
    if item_param.operation == 'min':
        return (value, float('inf'))
    if item_param.operation == 'max':
        return (float('-inf'), value)
    return (value, value)


def _date_interval(item_param):
    value = _to_date(item_param.value)
    if value is None:
        return None
    if item_param.operation == 'duration':
        value2 = _to_date(item_param.value2) or value
        return (min(value, value2), max(value, value2))
    if item_param.operation == 'start':
        return (value, '9999-12-31')
    if item_param.operation == 'end':
        return ('0000-01-01', value)
    return (value, value)


def _param_item_ids(crit):
    """Ids of items carrying a magic parameter that satisfies one search criterion."""
    query = ItemParameter.query.filter_by(parameter_id=crit['id'])

    if crit['type'] == 'number':
        if crit['units']:
            query = query.filter(ItemParameter.unit.in_(crit['units']))
        low = crit['min'] if crit['min'] is not None else float('-inf')
        high = crit['max'] if crit['max'] is not None else float('inf')
        if crit['min'] is None and crit['max'] is None:
            return {ip.item_id for ip in query}
        ids = set()
        for ip in query:
            span = _number_interval(ip)
            if span and span[0] <= high and span[1] >= low:
                ids.add(ip.item_id)
        return ids

    if crit['type'] == 'date':
        if not crit['from'] and not crit['to']:
            return {ip.item_id for ip in query}
        low, high = crit['from'] or '0000-01-01', crit['to'] or '9999-12-31'
        ids = set()
        for ip in query:
            span = _date_interval(ip)
            if span and span[0] <= high and span[1] >= low:
                ids.add(ip.item_id)
        return ids

    wanted = set(crit['values'])
    if not wanted:
        return {ip.item_id for ip in query}
    ids = set()
    for ip in query.options(selectinload(ItemParameter.string_values)):
        have = {sv.value for sv in ip.string_values}
        if ip.string_option:
            have.add(ip.string_option)
        if (wanted <= have) if crit['mode'] == 'all' else (wanted & have):
            ids.add(ip.item_id)
    return ids


def param_groups(params):
    """Split criteria into OR-groups; a criterion joined with 'or' shares the previous one's group."""
    groups = []
    for crit in params:
        if crit['join'] == 'or' and groups:
            groups[-1].append(crit)
        else:
            groups.append([crit])
    return groups


def _between(query, column, low, high):
    if low is not None:
        query = query.filter(column >= low)
    if high is not None:
        query = query.filter(column <= high)
    return query


def _like(column, text):
    escaped = text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return column.ilike(f'%{escaped}%', escape='\\')


def find_items(filters):
    """Query for every item matching the filters, most recently updated first."""
    query = Item.query

    search = filters['search']
    if search:
        if search.lower().startswith('uuid:'):
            query = query.filter(Item.uuid == search[5:].strip())
        else:
            query = query.filter(db.or_(Item.name.ilike(f'%{search}%'),
                                        Item.short_info.ilike(f'%{search}%')))
    if filters['category_id'] > 0:
        query = query.filter(Item.category_id == filters['category_id'])

    for key, column in (('name', Item.name), ('uuid', Item.uuid), ('short_info', Item.short_info),
                        ('sku', Item.sku), ('model', Item.info)):
        if filters[key]:
            query = query.filter(_like(column, filters[key]))
    if filters['cat_ids']:
        query = query.filter(Item.category_id.in_(filters['cat_ids']))
    if filters['fp_ids']:
        query = query.filter(Item.footprint_id.in_(filters['fp_ids']))

    if filters['tag_ids']:
        tagged = db.select(item_tags.c.item_id).where(item_tags.c.tag_id.in_(filters['tag_ids']))
        if filters['tag_mode'] == 'all':
            tagged = (tagged.group_by(item_tags.c.item_id)
                      .having(db.func.count(item_tags.c.tag_id) == len(filters['tag_ids'])))
        query = query.filter(Item.id.in_(tagged))

    if filters['params']:
        matching = None
        for group in param_groups(filters['params']):
            ids = set().union(*(_param_item_ids(crit) for crit in group))
            matching = ids if matching is None else matching & ids
        # Rendered inline so a large match set cannot exceed the driver's bound-parameter limit.
        query = query.filter(Item.id.in_(
            db.bindparam('matching_ids', sorted(matching), expanding=True, literal_execute=True)))

    stock_filters = (filters['qty_min'], filters['qty_max'], filters['price_min'], filters['price_max'])
    if filters['statuses'] or any(value is not None for value in stock_filters):
        cols = StockColumns(item_stock_subquery())
        query = cols.join(query)
        query = _between(query, cols.available, filters['qty_min'], filters['qty_max'])
        query = _between(query, cols.average_price, filters['price_min'], filters['price_max'])
        if filters['statuses']:
            query = query.filter(cols.status.in_(filters['statuses']))

    return query.order_by(Item.updated_at.desc())


def paginate_items(filters, page, per_page):
    """One page of matching items with what the list templates display loaded up front."""
    query = find_items(filters).options(
        joinedload(Item.category), joinedload(Item.footprint), joinedload(Item.general_location),
        joinedload(Item.rack).joinedload(Rack.physical_location), selectinload(Item.tags), selectinload(Item.attachments),
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def _fmt(number):
    return f'{number:g}'


def _range_text(low, high):
    if low is not None and high is not None:
        return f'= {_fmt(low)}' if low == high else f'{_fmt(low)} – {_fmt(high)}'
    if low is not None:
        return f'≥ {_fmt(low)}'
    return f'≤ {_fmt(high)}'


def _describe_param(crit):
    text = crit['name']
    if crit['type'] == 'number':
        if crit['min'] is not None or crit['max'] is not None:
            text += f" {_range_text(crit['min'], crit['max'])}"
        if crit['units']:
            text += f" [{', '.join(crit['units'])}]"
    elif crit['type'] == 'date':
        if crit['from'] and crit['to']:
            text += f": {crit['from']} – {crit['to']}"
        elif crit['from']:
            text += f": from {crit['from']}"
        elif crit['to']:
            text += f": until {crit['to']}"
    elif crit['values']:
        joiner = ' + ' if crit['mode'] == 'all' else ', '
        text += f": {joiner.join(crit['values'])}"
    return text


def describe_filters(filters):
    """Human-readable summary of the advanced filters, one string per filter."""
    chips = []
    for key, label in (('name', 'Name'), ('uuid', 'UUID'), ('short_info', 'Short info'),
                       ('sku', 'SKU'), ('model', 'Type/Model')):
        if filters[key]:
            chips.append(f'{label}: {filters[key]}')

    def names(model, ids):
        rows = {r.id: r.name for r in model.query.filter(model.id.in_(ids)).all()}
        return ', '.join(rows[i] for i in ids if i in rows)

    if filters['cat_ids']:
        chips.append(f"Category: {names(Category, filters['cat_ids'])}")
    if filters['tag_ids']:
        mode = ' (all)' if filters['tag_mode'] == 'all' and len(filters['tag_ids']) > 1 else ''
        chips.append(f"Tags{mode}: {names(Tag, filters['tag_ids'])}")
    if filters['fp_ids']:
        chips.append(f"Footprint: {names(Footprint, filters['fp_ids'])}")
    if filters['qty_min'] is not None or filters['qty_max'] is not None:
        chips.append(f"Available Qty {_range_text(filters['qty_min'], filters['qty_max'])}")
    if filters['price_min'] is not None or filters['price_max'] is not None:
        chips.append(f"Price per Unit {_range_text(filters['price_min'], filters['price_max'])}")

    for group in param_groups(filters['params']):
        chips.append(' OR '.join(_describe_param(crit) for crit in group))
    return chips


def magic_parameter_catalog():
    """Magic parameters with their units and pickable string values, for the search form."""
    custom = {}
    rows = (db.session.query(ItemParameter.parameter_id, ItemParameterStringValue.value)
            .join(ItemParameterStringValue,
                  ItemParameterStringValue.item_parameter_id == ItemParameter.id)
            .distinct().all())
    for parameter_id, value in rows:
        custom.setdefault(parameter_id, set()).add(value)

    catalog = []
    params = (MagicParameter.query
              .options(selectinload(MagicParameter.units), selectinload(MagicParameter.string_options))
              .order_by(MagicParameter.name).all())
    for param in params:
        options = [opt.value for opt in param.string_options]
        extra = sorted(custom.get(param.id, set()) - set(options), key=str.lower)
        catalog.append({
            'id': param.id,
            'name': param.name,
            'type': param.param_type,
            'units': [unit.unit for unit in param.units],
            'options': options + extra,
        })
    return catalog
