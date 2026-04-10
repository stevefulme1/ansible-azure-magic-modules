"""Render Ansible module source files from ResourceDefinition objects."""

from pathlib import Path

import jinja2

from .parser import ResourceDefinition


# ---------------------------------------------------------------------------
# Custom Jinja2 filters
# ---------------------------------------------------------------------------

def _snake_to_camel(value: str) -> str:
    """Convert snake_case to camelCase.

    Example: ``address_prefixes`` -> ``addressPrefixes``
    """
    parts = value.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


def _snake_to_pascal(value: str) -> str:
    """Convert snake_case to PascalCase.

    Example: ``address_prefixes`` -> ``AddressPrefixes``
    """
    return "".join(w.capitalize() for w in value.split("_"))


_ANSIBLE_TYPE_MAP = {
    "str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "list": "list",
    "dict": "dict",
    "raw": "raw",
}


def _to_python(value: object) -> str:
    """Render a value as a valid Python literal.

    Unlike ``tojson``, this produces ``True``/``False``/``None`` for booleans
    and None, and wraps strings in quotes.
    """
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return repr(value)
    return repr(value)


def _ansible_type_str(value: str) -> str:
    """Map internal type names to the string used in Ansible ``DOCUMENTATION``.

    Falls back to the original value when no mapping exists.
    """
    return _ANSIBLE_TYPE_MAP.get(value, value)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class ModuleRenderer:
    """Load Jinja2 templates and render Ansible module source files."""

    def __init__(self, template_dir: str | Path) -> None:
        self.template_dir = Path(template_dir)
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["snake_to_camel"] = _snake_to_camel
        self.env.filters["snake_to_pascal"] = _snake_to_pascal
        self.env.filters["ansible_type_str"] = _ansible_type_str
        self.env.filters["to_python"] = _to_python

    def render_module(self, definition: ResourceDefinition) -> str:
        """Render the main CRUD module source."""
        template = self.env.get_template("module.py.j2")
        return template.render(resource=definition)

    def render_info_module(self, definition: ResourceDefinition) -> str:
        """Render the ``_info`` facts module source."""
        template = self.env.get_template("module_info.py.j2")
        return template.render(resource=definition)
