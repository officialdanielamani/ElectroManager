"""
Plugin system for ElectroManager.

Place plugin packages as subdirectories here (e.g. plugins/my_plugin/__init__.py).
Each plugin must subclass PluginBase and register itself via register_plugin().
"""
from .base import PluginBase, register_plugin, get_registered_plugins, load_all_plugins

__all__ = ['PluginBase', 'register_plugin', 'get_registered_plugins', 'load_all_plugins']
