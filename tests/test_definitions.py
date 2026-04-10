"""Validate all YAML definitions in the definitions/ directory.

This test suite ensures every shipped definition parses without errors
and that the generated Python output compiles cleanly.
"""

import py_compile
import tempfile
from pathlib import Path

import pytest

from generator.parser import parse_file
from generator.renderer import ModuleRenderer
from tests.conftest import DEFINITIONS_DIR, TEMPLATES_DIR

YAML_FILES = sorted(DEFINITIONS_DIR.glob("*.yaml"))
# Exclude _schema.yaml if present
YAML_FILES = [f for f in YAML_FILES if not f.name.startswith("_")]


@pytest.fixture(scope="module")
def renderer():
    return ModuleRenderer(TEMPLATES_DIR)


@pytest.mark.parametrize(
    "yaml_file",
    YAML_FILES,
    ids=[f.stem for f in YAML_FILES],
)
class TestDefinitions:
    def test_parses_without_error(self, yaml_file):
        defn = parse_file(yaml_file)
        assert defn.name
        assert defn.module_name
        assert defn.api_version
        assert defn.provider
        assert defn.resource_type

    def test_has_properties(self, yaml_file):
        defn = parse_file(yaml_file)
        assert len(defn.properties) > 0, (
            f"{yaml_file.name}: definition has no properties"
        )

    def test_valid_property_locations(self, yaml_file):
        defn = parse_file(yaml_file)
        for prop in defn.properties:
            assert prop.location in ("body", "properties", "tags"), (
                f"{yaml_file.name}: property '{prop.name}' has invalid location '{prop.location}'"
            )

    def test_generated_module_compiles(self, yaml_file, renderer):
        defn = parse_file(yaml_file)
        output = renderer.render_module(defn)
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(output)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_generated_info_module_compiles(self, yaml_file, renderer):
        defn = parse_file(yaml_file)
        if not defn.generate_info:
            pytest.skip("generate_info is False")
        output = renderer.render_info_module(defn)
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(output)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_no_line_exceeds_160_chars(self, yaml_file, renderer):
        """Ensure generated code passes ansible-test pep8 line length."""
        defn = parse_file(yaml_file)
        output = renderer.render_module(defn)
        for i, line in enumerate(output.splitlines(), 1):
            assert len(line) <= 160, (
                f"{yaml_file.name}: generated module line {i} is {len(line)} chars (max 160)"
            )
