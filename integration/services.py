import importlib
import sys
from pathlib import Path

from django.conf import settings


def get_plugin_paths() -> list[Path]:
    """Return configured plugin directories in precedence order."""
    configured_paths = settings.PLUGINS_PATH
    if isinstance(configured_paths, (str, Path)):
        configured_paths = [configured_paths]
    return [Path(path) for path in configured_paths]


def load_plugin_module(module_name: str):
    """Load a plugin module from the configured plugin directories."""
    for plugin_path in reversed(get_plugin_paths()):
        path_string = str(plugin_path)
        if path_string not in sys.path:
            sys.path.insert(0, path_string)

    try:
        importlib.invalidate_caches()
        if module_name in sys.modules:
            return importlib.reload(sys.modules[module_name])
        return importlib.import_module(module_name)
    except Exception:
        return None


def discover_plugin_modules() -> list[str]:
    """Discover Python plugin module names, respecting path precedence."""
    modules = []
    seen_modules = set()

    for plugin_path in get_plugin_paths():
        plugin_path.mkdir(parents=True, exist_ok=True)
        for plugin_file in sorted(plugin_path.glob("*.py")):
            module_name = plugin_file.stem
            if module_name.startswith("_") or module_name in seen_modules:
                continue
            seen_modules.add(module_name)
            modules.append(module_name)

    return modules
