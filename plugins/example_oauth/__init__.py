"""
Example OAuth / SSO plugin skeleton.

This is a non-functional example showing how to build an auth plugin.
To make it real, implement the blueprint routes and OAuth flow.
"""
from plugins.base import PluginBase, register_plugin


class ExampleOAuthPlugin(PluginBase):
    slug = 'example_oauth'
    name = 'Example OAuth / SSO'
    description = 'Example skeleton for adding an OAuth/SSO login provider. Not functional — copy and adapt.'
    version = '0.1.0'
    plugin_type = 'auth'

    config_schema = [
        {
            'key': 'client_id',
            'label': 'OAuth Client ID',
            'type': 'text',
            'required': True,
            'default': '',
        },
        {
            'key': 'client_secret',
            'label': 'OAuth Client Secret',
            'type': 'password',
            'required': True,
            'default': '',
        },
        {
            'key': 'authorization_url',
            'label': 'Authorization URL',
            'type': 'text',
            'required': True,
            'default': 'https://provider.example.com/oauth/authorize',
        },
        {
            'key': 'token_url',
            'label': 'Token URL',
            'type': 'text',
            'required': True,
            'default': 'https://provider.example.com/oauth/token',
        },
        {
            'key': 'auto_create_users',
            'label': 'Auto-create users on first login',
            'type': 'bool',
            'required': False,
            'default': False,
        },
    ]

    def on_enable(self, config: dict) -> None:
        pass  # TODO: initialise OAuth session, register callback route

    def on_disable(self) -> None:
        pass  # TODO: deregister route / clean up

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        for field in self.config_schema:
            if field.get('required') and not config.get(field['key']):
                errors.append(f"'{field['label']}' is required.")
        return errors

    def register_blueprints(self, app) -> None:
        pass  # TODO: app.register_blueprint(oauth_bp)


register_plugin(ExampleOAuthPlugin())
