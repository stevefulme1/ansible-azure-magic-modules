# Azure Magic Modules

Generate fully-functional [Ansible](https://www.ansible.com/) modules for Azure from declarative YAML resource definitions — inspired by Google's [Magic Modules](https://github.com/GoogleCloudPlatform/magic-modules) for GCP/Terraform.

Instead of hand-writing hundreds of lines of boilerplate per Azure resource, you describe the resource once in YAML and the generator produces:

- A **CRUD module** (`azure_rm_<resource>.py`) with `present`/`absent` state management, idempotency checks, tag support, and check mode.
- An **info module** (`azure_rm_<resource>_info.py`) for listing and fetching resource facts.

Both inherit from `AzureRMModuleBase` in [azure.azcollection](https://github.com/ansible-collections/azure) and use the Azure REST API directly via `mgmt_client.query()`.

## Quick start

```bash
# Install dependencies
pip install jinja2 pyyaml

# Validate all definitions
python3 -m generator.cli -d definitions/ --validate

# Generate modules
python3 -m generator.cli -d definitions/ -o output/

# Generate a single resource
python3 -m generator.cli -d definitions/ -o output/ -r azure_rm_storageaccount

# Preview without writing files
python3 -m generator.cli -d definitions/ --dry-run
```

## Project structure

```
azure-magic-modules/
├── generator/
│   ├── cli.py              # CLI entry point (argparse)
│   ├── parser.py           # YAML → ResourceDefinition dataclass
│   ├── renderer.py         # Jinja2 rendering with custom filters
│   └── templates/
│       ├── module.py.j2        # CRUD module template
│       └── module_info.py.j2   # Info/facts module template
├── definitions/
│   ├── _schema.yaml            # Schema reference (not processed)
│   ├── resource_group.yaml
│   ├── virtual_network.yaml
│   ├── storage_account.yaml
│   ├── network_security_group.yaml
│   └── managed_disk.yaml
├── output/                 # Generated modules land here
├── pyproject.toml
└── LICENSE
```

## Writing a resource definition

Each YAML file in `definitions/` describes one Azure resource. Drop a new file there and re-run the generator.

### Minimal example

```yaml
name: ResourceGroup
module_name: azure_rm_resourcegroup
description: "Manage Azure resource groups"
api_version: "2024-03-01"
provider: Microsoft.Resources
resource_type: resourceGroups

properties:
  name:
    type: str
    required: true
    description: "Name of the resource group."
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
```

### Full example with nested API fields

```yaml
name: StorageAccount
module_name: azure_rm_storageaccount
description: "Manage Azure storage accounts"
api_version: "2023-05-01"
provider: Microsoft.Storage
resource_type: storageAccounts
doc_url: "https://learn.microsoft.com/en-us/rest/api/storagerp/storage-accounts"

properties:
  name:
    type: str
    required: true
    description: "Storage account name."
    updatable: false

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

  account_type:
    type: str
    required: true
    description: "SKU replication strategy."
    choices: [Standard_LRS, Standard_GRS, Premium_LRS, Standard_ZRS]
    api_field: sku.name        # nested path → body['sku']['name']
    location: body

  https_only:
    type: bool
    default: true
    description: "Require HTTPS."
    api_field: supportsHttpsTrafficOnly
    location: properties       # → body['properties']['supportsHttpsTrafficOnly']

  tags:
    type: dict
    description: "Resource tags."
    location: tags
```

### Property reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | str | `str` | Ansible type: `str`, `int`, `float`, `bool`, `list`, `dict` |
| `required` | bool | `false` | Whether the parameter is required |
| `description` | str | `""` | Shown in module DOCUMENTATION |
| `default` | any | — | Default value |
| `choices` | list | — | Allowed values |
| `api_field` | str | auto | Azure API field name (auto-converted from snake_case to PascalCase if omitted) |
| `location` | str | `body` | Where in the API body: `body` (top-level), `properties` (nested under `.properties`), `tags` |
| `updatable` | bool | `true` | Whether the field can be changed after creation |
| `elements` | str | — | Element type for `type: list` (e.g., `str`, `dict`) |
| `suboptions` | dict | — | Nested option spec for `list`/`dict` with `elements: dict` |

### Nested API field paths

Use dot notation in `api_field` to target nested JSON structures:

```yaml
# Produces: body['sku']['name'] = value
api_field: sku.name
location: body

# Produces: body['properties']['creationData']['createOption'] = value
api_field: creationData.createOption
location: properties
```

## CLI reference

```
usage: azure-magic-modules [-h] [-d DIR] [-o DIR] [-t DIR] [-r NAME]
                           [--info | --no-info] [--dry-run] [--validate]

options:
  -d, --definitions DIR   Path to definitions directory (default: definitions/)
  -o, --output DIR        Output directory (default: output/)
  -t, --templates DIR     Jinja2 templates directory (default: generator/templates/)
  -r, --resource NAME     Generate only this resource (matched by module_name)
  --info / --no-info      Override generate_info from the definition
  --dry-run               Print to stdout instead of writing files
  --validate              Parse definitions and report errors, no generation
```

## Generated module anatomy

Each generated CRUD module includes:

- **`DOCUMENTATION`** — Full Ansible docs with options, types, defaults, choices, and suboptions
- **`EXAMPLES`** — Create and delete playbook examples
- **`RETURN`** — Return value documentation
- **`AzureRM<Resource>` class** inheriting `AzureRMModuleBase` with:
  - `exec_module()` — state routing (present/absent)
  - `build_body()` — parameter-to-API-body mapping with nested path support
  - `check_update()` — idempotency comparison for each updatable property
  - `get_resource()` / `create_or_update()` / `delete_resource()` — REST operations
  - `format_response()` — API response to Ansible return dict
  - Tag support via `update_tags()` and check mode via `supports_check_mode`

## Included definitions

| Definition | Module | Resource |
|------------|--------|----------|
| `resource_group.yaml` | `azure_rm_resourcegroup` | `Microsoft.Resources/resourceGroups` |
| `virtual_network.yaml` | `azure_rm_virtualnetwork` | `Microsoft.Network/virtualNetworks` |
| `storage_account.yaml` | `azure_rm_storageaccount` | `Microsoft.Storage/storageAccounts` |
| `network_security_group.yaml` | `azure_rm_securitygroup` | `Microsoft.Network/networkSecurityGroups` |
| `managed_disk.yaml` | `azure_rm_manageddisk` | `Microsoft.Compute/disks` |

## Requirements

- Python >= 3.12
- `jinja2 >= 3.1`
- `pyyaml >= 6.0`

Generated modules target [azure.azcollection](https://github.com/ansible-collections/azure) and require `ansible-core >= 2.14`.

## License

Apache License 2.0
