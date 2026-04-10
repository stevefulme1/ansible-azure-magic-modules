"""Tests for the YAML definition parser."""

import pytest

from generator.parser import (
    DefinitionError,
    PropertyDef,
    ResourceDefinition,
    _snake_to_pascal,
    _validate_definition,
    parse_file,
)


# ---------------------------------------------------------------------------
# Unit: _snake_to_pascal
# ---------------------------------------------------------------------------


class TestSnakeToPascal:
    def test_single_word(self):
        assert _snake_to_pascal("name") == "Name"

    def test_multi_word(self):
        assert _snake_to_pascal("disk_size_gb") == "DiskSizeGb"

    def test_already_single(self):
        assert _snake_to_pascal("id") == "Id"


# ---------------------------------------------------------------------------
# Unit: PropertyDef
# ---------------------------------------------------------------------------


class TestPropertyDef:
    def test_auto_api_field(self):
        p = PropertyDef(name="disk_size_gb", type="int")
        assert p.api_field == "DiskSizeGb"

    def test_explicit_api_field(self):
        p = PropertyDef(name="disk_size_gb", type="int", api_field="diskSizeGB")
        assert p.api_field == "diskSizeGB"

    def test_defaults(self):
        p = PropertyDef(name="x", type="str")
        assert p.required is False
        assert p.location == "body"
        assert p.updatable is True
        assert p.choices is None
        assert p.elements is None
        assert p.suboptions is None


# ---------------------------------------------------------------------------
# Unit: _validate_definition
# ---------------------------------------------------------------------------


class TestValidateDefinition:
    def test_valid_minimal(self):
        data = {
            "name": "Foo",
            "module_name": "azure_rm_foo",
            "api_version": "2024-01-01",
            "provider": "Microsoft.Test",
            "resource_type": "foos",
        }
        assert _validate_definition(data) == []

    def test_missing_required_fields(self):
        errors = _validate_definition({"name": "Foo"})
        assert len(errors) == 1
        assert "missing required top-level fields" in errors[0]

    def test_invalid_property_type(self):
        data = {
            "name": "Foo",
            "module_name": "azure_rm_foo",
            "api_version": "2024-01-01",
            "provider": "Microsoft.Test",
            "resource_type": "foos",
            "properties": {"bad_prop": {"type": "banana"}},
        }
        errors = _validate_definition(data)
        assert any("invalid type 'banana'" in e for e in errors)

    def test_invalid_location(self):
        data = {
            "name": "Foo",
            "module_name": "azure_rm_foo",
            "api_version": "2024-01-01",
            "provider": "Microsoft.Test",
            "resource_type": "foos",
            "properties": {"x": {"type": "str", "location": "sku"}},
        }
        errors = _validate_definition(data)
        assert any("invalid location 'sku'" in e for e in errors)

    def test_invalid_elements_type(self):
        data = {
            "name": "Foo",
            "module_name": "azure_rm_foo",
            "api_version": "2024-01-01",
            "provider": "Microsoft.Test",
            "resource_type": "foos",
            "properties": {"x": {"type": "list", "elements": "banana"}},
        }
        errors = _validate_definition(data)
        assert any("invalid elements type" in e for e in errors)


# ---------------------------------------------------------------------------
# Integration: parse_file
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_minimal_definition(self, tmp_definition, minimal_yaml):
        path = tmp_definition(minimal_yaml)
        defn = parse_file(path)

        assert isinstance(defn, ResourceDefinition)
        assert defn.name == "TestWidget"
        assert defn.module_name == "azure_rm_testwidget"
        assert defn.api_version == "2024-01-01"
        assert defn.provider == "Microsoft.Test"
        assert defn.resource_type == "widgets"
        assert defn.generate_info is True

    def test_properties_parsed(self, tmp_definition, minimal_yaml):
        path = tmp_definition(minimal_yaml)
        defn = parse_file(path)

        names = [p.name for p in defn.properties]
        assert "name" in names
        assert "resource_group" in names
        assert "location" in names
        assert "tags" in names

    def test_property_attributes(self, tmp_definition, minimal_yaml):
        path = tmp_definition(minimal_yaml)
        defn = parse_file(path)

        loc_prop = next(p for p in defn.properties if p.name == "location")
        assert loc_prop.api_field == "location"
        assert loc_prop.location == "body"
        assert loc_prop.required is True

    def test_invalid_yaml_raises(self, tmp_definition):
        path = tmp_definition("not: valid: yaml: [")
        with pytest.raises(Exception):
            parse_file(path)

    def test_missing_fields_raises(self, tmp_definition):
        path = tmp_definition("name: Foo\n")
        with pytest.raises(DefinitionError, match="missing required top-level fields"):
            parse_file(path)

    def test_non_mapping_raises(self, tmp_definition):
        path = tmp_definition("- list\n- item\n")
        with pytest.raises(DefinitionError, match="expected a YAML mapping"):
            parse_file(path)

    def test_choices_parsed(self, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              tier:
                type: str
                choices:
                  - Basic
                  - Standard
                  - Premium
        """
        defn = parse_file(tmp_definition(yaml_str))
        tier = next(p for p in defn.properties if p.name == "tier")
        assert tier.choices == ["Basic", "Standard", "Premium"]

    def test_suboptions_parsed(self, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              rules:
                type: list
                elements: dict
                suboptions:
                  rule_name:
                    type: str
                    required: true
                  priority:
                    type: int
        """
        defn = parse_file(tmp_definition(yaml_str))
        rules = next(p for p in defn.properties if p.name == "rules")
        assert rules.elements == "dict"
        assert "rule_name" in rules.suboptions
        assert rules.suboptions["rule_name"]["required"] is True

    def test_dot_notation_api_field(self, tmp_definition):
        yaml_str = """\
            name: Foo
            module_name: azure_rm_foo
            api_version: "2024-01-01"
            provider: Microsoft.Test
            resource_type: foos
            properties:
              sku_name:
                type: str
                api_field: sku.name
                location: body
        """
        defn = parse_file(tmp_definition(yaml_str))
        sku = next(p for p in defn.properties if p.name == "sku_name")
        assert sku.api_field == "sku.name"

    def test_real_definition_resource_group(self):
        """Parse the real resource_group.yaml from definitions/."""
        from tests.conftest import DEFINITIONS_DIR

        path = DEFINITIONS_DIR / "resource_group.yaml"
        if not path.exists():
            pytest.skip("resource_group.yaml not found")
        defn = parse_file(path)
        assert defn.name == "ResourceGroup"
        assert defn.module_name == "azure_rm_resourcegroup"

    def test_real_definition_storage_account(self):
        """Parse the real storage_account.yaml from definitions/."""
        from tests.conftest import DEFINITIONS_DIR

        path = DEFINITIONS_DIR / "storage_account.yaml"
        if not path.exists():
            pytest.skip("storage_account.yaml not found")
        defn = parse_file(path)
        assert defn.name == "StorageAccount"
        sku = next(p for p in defn.properties if p.name == "account_type")
        assert sku.api_field == "sku.name"
        assert "Standard_LRS" in sku.choices
