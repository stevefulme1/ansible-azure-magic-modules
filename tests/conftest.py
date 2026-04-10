"""Shared fixtures for Azure Magic Modules tests."""

import textwrap
from pathlib import Path

import pytest

DEFINITIONS_DIR = Path(__file__).resolve().parent.parent / "definitions"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "generator" / "templates"


@pytest.fixture()
def tmp_definition(tmp_path):
    """Return a helper that writes a YAML string to a temp file and returns its path."""

    def _write(content: str, filename: str = "test_resource.yaml") -> Path:
        p = tmp_path / filename
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    return _write


@pytest.fixture()
def minimal_yaml():
    """Minimal valid YAML definition."""
    return """\
        name: TestWidget
        module_name: azure_rm_testwidget
        description: "Manage test widgets"
        api_version: "2024-01-01"
        provider: Microsoft.Test
        resource_type: widgets
        properties:
          name:
            type: str
            required: true
            description: "Widget name."
          resource_group:
            type: str
            required: true
            description: "Resource group name."
          location:
            type: str
            required: true
            description: "Azure region."
            api_field: location
            location: body
          tags:
            type: dict
            description: "Resource tags."
            location: tags
    """
