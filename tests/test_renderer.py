"""Tests for the Jinja2 module renderer."""

import py_compile
import tempfile
from pathlib import Path

import pytest

from generator.parser import parse_file
from generator.renderer import (
    ModuleRenderer,
    _snake_to_camel,
    _snake_to_pascal,
    _to_python,
    _to_python_list,
)
from tests.conftest import DEFINITIONS_DIR, TEMPLATES_DIR


# ---------------------------------------------------------------------------
# Unit: custom filters
# ---------------------------------------------------------------------------


class TestSnakeToCamel:
    def test_basic(self):
        assert _snake_to_camel("source_port_range") == "sourcePortRange"

    def test_single_word(self):
        assert _snake_to_camel("name") == "name"


class TestSnakeToPascal:
    def test_basic(self):
        assert _snake_to_pascal("source_port_range") == "SourcePortRange"


class TestToPython:
    def test_none(self):
        assert _to_python(None) == "None"

    def test_true(self):
        assert _to_python(True) == "True"

    def test_false(self):
        assert _to_python(False) == "False"

    def test_string(self):
        result = _to_python("hello")
        assert result == "'hello'"

    def test_int(self):
        assert _to_python(42) == "42"


class TestToPythonList:
    def test_short_list_single_line(self):
        result = _to_python_list(["a", "b", "c"], indent=16)
        assert result == "['a', 'b', 'c']"
        assert "\n" not in result

    def test_long_list_multi_line(self):
        long_choices = [f"VeryLongChoiceName_{i}" for i in range(20)]
        result = _to_python_list(long_choices, indent=16)
        assert "\n" in result
        assert result.startswith("[")
        assert result.strip().endswith("]")

    def test_all_items_present(self):
        items = ["Alpha", "Beta", "Gamma"]
        result = _to_python_list(items, indent=16)
        for item in items:
            assert f"'{item}'" in result


# ---------------------------------------------------------------------------
# Integration: ModuleRenderer
# ---------------------------------------------------------------------------


class TestModuleRenderer:
    @pytest.fixture()
    def renderer(self):
        return ModuleRenderer(TEMPLATES_DIR)

    @pytest.fixture()
    def simple_definition(self, tmp_definition, minimal_yaml):
        return parse_file(tmp_definition(minimal_yaml))

    def test_render_module_contains_class(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "class AzureRMTestWidget(AzureRMModuleBase):" in output

    def test_render_module_contains_documentation(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "DOCUMENTATION" in output
        assert "azure_rm_testwidget" in output
        assert "Manage test widgets" in output

    def test_render_module_contains_examples(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "EXAMPLES" in output
        assert "Create TestWidget" in output
        assert "Delete TestWidget" in output

    def test_render_module_contains_return(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "RETURN" in output

    def test_render_module_contains_state_param(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "state=dict(type='str', default='present'" in output

    def test_render_module_contains_api_version(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "'api-version': '2024-01-01'" in output

    def test_render_module_contains_provider_url(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "Microsoft.Test/widgets" in output

    def test_render_module_valid_python(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(output)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_render_info_module_contains_class(self, renderer, simple_definition):
        output = renderer.render_info_module(simple_definition)
        assert "class AzureRMTestWidgetInfo(AzureRMModuleBase):" in output

    def test_render_info_module_valid_python(self, renderer, simple_definition):
        output = renderer.render_info_module(simple_definition)
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(output)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_render_info_module_list_endpoint(self, renderer, simple_definition):
        output = renderer.render_info_module(simple_definition)
        assert "list_by_resource_group" in output

    def test_render_module_gpl_header(self, renderer, simple_definition):
        output = renderer.render_module(simple_definition)
        assert "GNU General Public License v3.0" in output

    def test_render_module_nested_api_field(self, renderer, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              name:
                type: str
                required: true
              resource_group:
                type: str
                required: true
              location:
                type: str
                required: true
                api_field: location
                location: body
              sku_name:
                type: str
                api_field: sku.name
                location: body
              tags:
                type: dict
                location: tags
        """
        defn = parse_file(tmp_definition(yaml_str))
        output = renderer.render_module(defn)
        # Should use setdefault for nested path
        assert "setdefault('sku', {})" in output
        assert py_compile.compile(
            _write_temp(output), doraise=True
        ) is not None

    def test_render_module_choices(self, renderer, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              name:
                type: str
                required: true
              resource_group:
                type: str
                required: true
              location:
                type: str
                required: true
                api_field: location
                location: body
              tier:
                type: str
                choices:
                  - Basic
                  - Standard
                  - Premium
                location: body
              tags:
                type: dict
                location: tags
        """
        defn = parse_file(tmp_definition(yaml_str))
        output = renderer.render_module(defn)
        assert "'Basic'" in output
        assert "'Standard'" in output
        assert "'Premium'" in output

    def test_render_module_suboptions(self, renderer, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              name:
                type: str
                required: true
              resource_group:
                type: str
                required: true
              location:
                type: str
                required: true
                api_field: location
                location: body
              rules:
                type: list
                elements: dict
                location: properties
                api_field: securityRules
                suboptions:
                  rule_name:
                    type: str
                    required: true
                  priority:
                    type: int
              tags:
                type: dict
                location: tags
        """
        defn = parse_file(tmp_definition(yaml_str))
        output = renderer.render_module(defn)
        assert "options=dict(" in output
        assert "rule_name=dict(" in output
        assert py_compile.compile(
            _write_temp(output), doraise=True
        ) is not None


def _write_temp(content: str) -> str:
    """Write content to a temp .py file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(content)
        return f.name
