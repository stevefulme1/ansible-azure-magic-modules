"""Parse YAML resource definitions into structured dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .utils import snake_to_pascal


def _snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Example: ``address_prefixes`` -> ``AddressPrefixes``

    .. deprecated::
        Use :func:`generator.utils.snake_to_pascal` instead.
    """
    return snake_to_pascal(name)


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
    no_log: bool = False
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
    parent_params: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_REQUIRED_TOP_LEVEL = {"name", "module_name", "api_version", "provider", "resource_type"}
_VALID_TYPES = {"str", "int", "float", "bool", "list", "dict", "raw"}
_VALID_LOCATIONS = {"body", "properties", "tags"}
_KNOWN_PROP_KEYS = {
    "name", "type", "required", "description", "default", "choices",
    "api_field", "location", "updatable", "elements", "element_type",
    "element", "suboptions", "no_log",
}


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

    # Normalize element_type / element -> elements (Q2)
    if "element_type" in prop and "elements" not in prop:
        prop["elements"] = prop["element_type"]
    if "element" in prop and "elements" not in prop:
        elem = prop["element"]
        if isinstance(elem, dict):
            prop["elements"] = elem.get("type", "str")
        else:
            prop["elements"] = elem

    # Check for unknown keys (Q9)
    unknown = set(prop.keys()) - _KNOWN_PROP_KEYS
    if unknown:
        errors.append(f"{prop_path}: unknown keys: {', '.join(sorted(unknown))}")

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
    # Normalize element_type / element -> elements (Q2)
    if "element_type" in raw and "elements" not in raw:
        raw["elements"] = raw["element_type"]
    if "element" in raw and "elements" not in raw:
        elem = raw["element"]
        if isinstance(elem, dict):
            raw["elements"] = elem.get("type", "str")
        else:
            raw["elements"] = elem

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
                "no_log": parsed.no_log,
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
        no_log=raw.get("no_log", False),
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

    # Auto-detect parent params for child resources (F1)
    parent_params: list[str] = []
    resource_type = data["resource_type"]
    if "/" in resource_type:
        # Identify properties that serve as parent URL path segments.
        # These are required properties (not name/resource_group/location/tags)
        # whose names end with ``_name`` — a conventional indicator that they
        # reference a parent resource.
        reserved = {"name", "resource_group", "location", "tags"}
        for prop in properties:
            if prop.name not in reserved and prop.name.endswith("_name"):
                parent_params.append(prop.name)

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
        parent_params=parent_params,
    )
