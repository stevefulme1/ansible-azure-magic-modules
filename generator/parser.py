"""Parse YAML resource definitions into structured dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Example: ``address_prefixes`` -> ``AddressPrefixes``
    """
    return "".join(word.capitalize() for word in name.split("_"))


@dataclass
class PropertyDef:
    """A single module parameter definition."""

    name: str
    type: str
    required: bool = False
    description: str = ""
    default: Any = None
    choices: list | None = None
    api_field: str = ""
    location: str = "body"
    updatable: bool = True
    elements: str | None = None
    suboptions: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.api_field:
            self.api_field = _snake_to_pascal(self.name)


@dataclass
class ResourceDefinition:
    """Fully parsed resource definition ready for rendering."""

    name: str
    module_name: str
    description: str
    api_version: str
    provider: str
    resource_type: str
    generate_info: bool = True
    author: str = "Ansible Team"
    doc_url: str = ""
    properties: list[PropertyDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_REQUIRED_TOP_LEVEL = {"name", "module_name", "api_version", "provider", "resource_type"}
_VALID_TYPES = {"str", "int", "float", "bool", "list", "dict", "raw"}
_VALID_LOCATIONS = {"body", "properties", "tags"}


class DefinitionError(Exception):
    """Raised when a YAML definition is invalid."""


def _normalize_properties(raw: Any) -> list[dict[str, Any]]:
    """Accept properties as either a list of dicts or a dict keyed by name.

    Dict format (name is the key)::

        properties:
          disk_size_gb:
            type: int
            ...

    List format (name inside each item)::

        properties:
          - name: disk_size_gb
            type: int
            ...

    Returns a list of dicts, each guaranteed to have a ``name`` key.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        result: list[dict[str, Any]] = []
        for prop_name, prop_body in raw.items():
            entry = dict(prop_body) if isinstance(prop_body, dict) else {}
            entry.setdefault("name", prop_name)
            result.append(entry)
        return result
    return []


def _validate_property(prop: dict[str, Any], path: str) -> list[str]:
    """Return a list of error messages for a single property dict."""
    errors: list[str] = []

    if "name" not in prop:
        errors.append(f"{path}: missing required field 'name'")
        return errors  # can't continue without name

    prop_path = f"{path}.{prop['name']}"

    ptype = prop.get("type", "str")
    if ptype not in _VALID_TYPES:
        errors.append(f"{prop_path}: invalid type '{ptype}' (allowed: {_VALID_TYPES})")

    location = prop.get("location", "body")
    if location not in _VALID_LOCATIONS:
        errors.append(f"{prop_path}: invalid location '{location}' (allowed: {_VALID_LOCATIONS})")

    if ptype == "list" and prop.get("elements") and prop["elements"] not in _VALID_TYPES:
        errors.append(f"{prop_path}: invalid elements type '{prop['elements']}'")

    # Recursively validate suboptions
    if prop.get("suboptions"):
        for sub in _normalize_properties(prop["suboptions"]):
            errors.extend(_validate_property(sub, f"{prop_path}.suboptions"))

    return errors


def _validate_definition(data: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation errors."""
    errors: list[str] = []

    missing = _REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"missing required top-level fields: {', '.join(sorted(missing))}")

    for prop in _normalize_properties(data.get("properties")):
        errors.extend(_validate_property(prop, "properties"))

    return errors


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_property(raw: dict[str, Any]) -> PropertyDef:
    """Build a PropertyDef from a raw YAML dict."""
    suboptions = None
    if raw.get("suboptions"):
        suboptions = {}
        for sub in _normalize_properties(raw["suboptions"]):
            parsed = _parse_property(sub)
            suboptions[parsed.name] = {
                "name": parsed.name,
                "type": parsed.type,
                "required": parsed.required,
                "description": parsed.description,
                "default": parsed.default,
                "choices": parsed.choices,
                "api_field": parsed.api_field,
                "elements": parsed.elements,
                "suboptions": parsed.suboptions,
            }

    return PropertyDef(
        name=raw["name"],
        type=raw.get("type", "str"),
        required=raw.get("required", False),
        description=raw.get("description", ""),
        default=raw.get("default"),
        choices=raw.get("choices"),
        api_field=raw.get("api_field", ""),
        location=raw.get("location", "body"),
        updatable=raw.get("updatable", True),
        elements=raw.get("elements"),
        suboptions=suboptions,
    )


def parse_file(path: str | Path) -> ResourceDefinition:
    """Parse a YAML definition file and return a ``ResourceDefinition``.

    Raises ``DefinitionError`` if the file is invalid.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise DefinitionError(f"{path}: expected a YAML mapping at top level")

    errors = _validate_definition(data)
    if errors:
        raise DefinitionError(f"{path}: validation errors:\n  " + "\n  ".join(errors))

    properties = [_parse_property(p) for p in _normalize_properties(data.get("properties"))]

    return ResourceDefinition(
        name=data["name"],
        module_name=data["module_name"],
        description=data.get("description", ""),
        api_version=data["api_version"],
        provider=data["provider"],
        resource_type=data["resource_type"],
        generate_info=data.get("generate_info", True),
        author=data.get("author", "Ansible Team"),
        doc_url=data.get("doc_url", ""),
        properties=properties,
    )
