import os
import json
import importlib.util
from typing import List, Optional, Dict, Any

PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "user_plugins")


class PluginManager:
    def __init__(self, plugin_dir: str = PLUGIN_DIR):
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Any] = {}
        os.makedirs(plugin_dir, exist_ok=True)
        self._load_plugins()

    def _load_plugins(self):
        for fname in os.listdir(self.plugin_dir):
            if fname.endswith(".py") and not fname.startswith("_"):
                path = os.path.join(self.plugin_dir, fname)
                name = fname[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(name, path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register"):
                        self.plugins[name] = mod.register()
                except Exception:
                    pass

    def get_translator(self, name: str):
        return self.plugins.get(name, {}).get("translate")

    def list_plugins(self) -> List[str]:
        return list(self.plugins.keys())

    def get_plugin_info(self, name: str) -> dict:
        p = self.plugins.get(name, {})
        return {
            "name": p.get("name", name),
            "description": p.get("description", ""),
            "type": p.get("type", "unknown"),
        }

    def translate(self, text: str, source: str = "en", target: str = "zh-CN") -> Optional[str]:
        for name, plugin in self.plugins.items():
            fn = plugin.get("translate")
            if fn:
                try:
                    result = fn(text, source, target)
                    if result:
                        return result
                except Exception:
                    continue
        return None

