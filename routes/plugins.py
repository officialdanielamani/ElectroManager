"""
Plugin management routes — admin only.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Plugin
from utils import admin_required
from plugins import get_registered_plugins
import json
import logging

logger = logging.getLogger(__name__)

plugins_bp = Blueprint('plugins', __name__)


@plugins_bp.route('/settings/plugins', endpoint='plugin_list')
@login_required
@admin_required
def plugin_list():
    registered = get_registered_plugins()
    db_plugins = {p.slug: p for p in Plugin.query.all()}

    # Sync: ensure every registered plugin has a DB row
    for slug, plugin in registered.items():
        if slug not in db_plugins:
            row = Plugin(
                slug=slug,
                name=plugin.name,
                description=plugin.description,
                version=plugin.version,
                plugin_type=plugin.plugin_type,
            )
            db.session.add(row)
            db_plugins[slug] = row
    db.session.commit()

    plugins = Plugin.query.order_by(Plugin.name).all()
    return render_template('settings_plugins.html', plugins=plugins, registered=registered)


@plugins_bp.route('/settings/plugins/<slug>/toggle', endpoint='plugin_toggle', methods=['POST'])
@login_required
@admin_required
def plugin_toggle(slug):
    plugin_row = Plugin.query.filter_by(slug=slug).first_or_404()
    registered = get_registered_plugins()
    instance = registered.get(slug)

    plugin_row.enabled = not plugin_row.enabled
    db.session.commit()

    if instance:
        try:
            if plugin_row.enabled:
                instance.on_enable(plugin_row.get_config())
            else:
                instance.on_disable()
        except Exception as exc:
            logger.error(f"Plugin {slug} on_{'enable' if plugin_row.enabled else 'disable'} error: {exc}")
            flash(f'Plugin toggled but encountered an error: {exc}', 'warning')
            return redirect(url_for('plugins.plugin_list'))

    state = 'enabled' if plugin_row.enabled else 'disabled'
    flash(f'Plugin "{plugin_row.name}" {state}.', 'success')
    return redirect(url_for('plugins.plugin_list'))


@plugins_bp.route('/settings/plugins/<slug>/config', endpoint='plugin_config', methods=['GET', 'POST'])
@login_required
@admin_required
def plugin_config(slug):
    plugin_row = Plugin.query.filter_by(slug=slug).first_or_404()
    registered = get_registered_plugins()
    instance = registered.get(slug)
    schema = instance.config_schema if instance else []

    if request.method == 'POST':
        current_cfg = plugin_row.get_config()
        for field in schema:
            key = field['key']
            if field['type'] == 'bool':
                current_cfg[key] = key in request.form
            elif field['type'] == 'password':
                val = request.form.get(key, '').strip()
                if val:  # only overwrite if a new value was submitted
                    current_cfg[key] = val
            else:
                current_cfg[key] = request.form.get(key, '').strip()

        errors = instance.validate_config(current_cfg) if instance else []
        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('settings_plugin_config.html',
                                   plugin=plugin_row, schema=schema, config=current_cfg)

        plugin_row.set_config(current_cfg)
        db.session.commit()

        if instance and plugin_row.enabled:
            try:
                instance.on_config_update(current_cfg)
            except Exception as exc:
                logger.error(f"Plugin {slug} on_config_update error: {exc}")

        flash('Plugin configuration saved.', 'success')
        return redirect(url_for('plugins.plugin_list'))

    cfg = plugin_row.get_config()
    return render_template('settings_plugin_config.html',
                           plugin=plugin_row, schema=schema, config=cfg)
