"""
Plugin base class and registry.
"""
import importlib
import logging
import os

logger = logging.getLogger(__name__)

_registry: dict[str, 'PluginBase'] = {}


class PluginBase:
    """
    Base class for all ElectroManager plugins.

    Subclass this, set the class attributes, and call register_plugin(MyPlugin())
    at the bottom of your plugin's __init__.py.

    Plugin types:
      - 'auth'    : authentication providers (OAuth, SSO, LDAP, …)
      - 'webhook' : outbound webhook / notification integrations
      - 'import'  : data importers
      - 'general' : everything else
    """
    slug: str = ''
    name: str = ''
    description: str = ''
    version: str = '1.0.0'
    plugin_type: str = 'general'
    # Config schema: list of dicts describing editable settings shown in the admin UI.
    # Each dict: {'key': str, 'label': str, 'type': 'text'|'password'|'bool'|'select',
    #             'options': [...] (for select), 'required': bool, 'default': any}
    config_schema: list = []

    def on_enable(self, config: dict) -> None:
        """Called when the plugin is enabled (after config is saved)."""

    def on_disable(self) -> None:
        """Called when the plugin is disabled."""

    def on_config_update(self, config: dict) -> None:
        """Called when the plugin's configuration is updated."""

    def register_blueprints(self, app) -> None:
        """Register any Flask blueprints this plugin provides."""

    def validate_config(self, config: dict) -> list[str]:
        """Return a list of error strings, or [] if valid."""
        return []


def register_plugin(plugin: PluginBase) -> None:
    if not plugin.slug:
        raise ValueError(f"Plugin {plugin.__class__.__name__} has no slug")
    _registry[plugin.slug] = plugin
    logger.info(f"Plugin registered: {plugin.slug} ({plugin.name})")


def get_registered_plugins() -> dict[str, PluginBase]:
    return dict(_registry)


def load_all_plugins(app=None) -> None:
    """
    Discover and import all plugin packages inside the plugins/ directory.
    A valid plugin package is a subdirectory containing __init__.py.
    """
    plugins_dir = os.path.dirname(__file__)
    for entry in sorted(os.listdir(plugins_dir)):
        entry_path = os.path.join(plugins_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        init_file = os.path.join(entry_path, '__init__.py')
        if not os.path.isfile(init_file):
            continue
        module_name = f'plugins.{entry}'
        try:
            mod = importlib.import_module(module_name)
            if app and hasattr(mod, 'register_blueprints'):
                mod.register_blueprints(app)
        except Exception as exc:
            logger.error(f"Failed to load plugin '{entry}': {exc}")
