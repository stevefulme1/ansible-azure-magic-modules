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
├── definitions/            # 124 YAML resource definitions
├── output/                 # 248 generated modules (124 CRUD + 124 info)
├── noxfile.py              # CI sessions (generate, lint, sanity, validate)
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

## Supported resources (124 definitions → 248 modules)

### AI & Machine Learning

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_aiservices` | `Microsoft.CognitiveServices/accounts` |
| `azure_rm_botservice` | `Microsoft.BotService/botServices` |
| `azure_rm_cognitiveservicesaccount` | `Microsoft.CognitiveServices/accounts` |
| `azure_rm_mlcompute` | `Microsoft.MachineLearningServices/workspaces/computes` |
| `azure_rm_mlonlineendpoint` | `Microsoft.MachineLearningServices/workspaces/onlineEndpoints` |
| `azure_rm_mlworkspace` | `Microsoft.MachineLearningServices/workspaces` |
| `azure_rm_openai_deployment` | `Microsoft.CognitiveServices/accounts/deployments` |
| `azure_rm_searchservice` | `Microsoft.Search/searchServices` |

### Compute

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_availabilityset` | `Microsoft.Compute/availabilitySets` |
| `azure_rm_diskencryptionset` | `Microsoft.Compute/diskEncryptionSets` |
| `azure_rm_image` | `Microsoft.Compute/images` |
| `azure_rm_manageddisk` | `Microsoft.Compute/disks` |
| `azure_rm_proximityplacementgroup` | `Microsoft.Compute/proximityPlacementGroups` |
| `azure_rm_sharedimage` | `Microsoft.Compute/galleries/images` |
| `azure_rm_sharedimagegallery` | `Microsoft.Compute/galleries` |
| `azure_rm_snapshot` | `Microsoft.Compute/snapshots` |
| `azure_rm_sshpublickey` | `Microsoft.Compute/sshPublicKeys` |
| `azure_rm_virtualmachine` | `Microsoft.Compute/virtualMachines` |
| `azure_rm_virtualmachinescaleset` | `Microsoft.Compute/virtualMachineScaleSets` |

### Containers & Kubernetes

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_akscluster` | `Microsoft.ContainerService/managedClusters` |
| `azure_rm_aksnodepool` | `Microsoft.ContainerService/managedClusters/agentPools` |
| `azure_rm_containerapp` | `Microsoft.App/containerApps` |
| `azure_rm_containerappenvironment` | `Microsoft.App/managedEnvironments` |
| `azure_rm_containerinstance` | `Microsoft.ContainerInstance/containerGroups` |
| `azure_rm_containerregistry` | `Microsoft.ContainerRegistry/registries` |

### Databases

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_cosmosdbaccount` | `Microsoft.DocumentDB/databaseAccounts` |
| `azure_rm_cosmosdbsqldatabase` | `Microsoft.DocumentDB/databaseAccounts/sqlDatabases` |
| `azure_rm_mariadbserver` | `Microsoft.DBforMariaDB/servers` |
| `azure_rm_mysqlflexibleserver` | `Microsoft.DBforMySQL/flexibleServers` |
| `azure_rm_postgresqlflexibleserver` | `Microsoft.DBforPostgreSQL/flexibleServers` |
| `azure_rm_rediscache` | `Microsoft.Cache/redis` |
| `azure_rm_sqldatabase` | `Microsoft.Sql/servers/databases` |
| `azure_rm_sqlfirewallrule` | `Microsoft.Sql/servers/firewallRules` |
| `azure_rm_sqlmanagedinstance` | `Microsoft.Sql/managedInstances` |
| `azure_rm_sqlserver` | `Microsoft.Sql/servers` |

### Data & Analytics

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_databricksworkspace` | `Microsoft.Databricks/workspaces` |
| `azure_rm_datafactory` | `Microsoft.DataFactory/factories` |
| `azure_rm_datalakestore` | `Microsoft.DataLakeStore/accounts` |
| `azure_rm_hdinsightcluster` | `Microsoft.HDInsight/clusters` |
| `azure_rm_kustocluster` | `Microsoft.Kusto/clusters` |
| `azure_rm_purviewaccount` | `Microsoft.Purview/accounts` |
| `azure_rm_streamanalyticsjob` | `Microsoft.StreamAnalytics/streamingjobs` |
| `azure_rm_synapsesparkpool` | `Microsoft.Synapse/workspaces/bigDataPools` |
| `azure_rm_synapsesqlpool` | `Microsoft.Synapse/workspaces/sqlPools` |
| `azure_rm_synapseworkspace` | `Microsoft.Synapse/workspaces` |

### IoT

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_digitaltwins` | `Microsoft.DigitalTwins/digitalTwinsInstances` |
| `azure_rm_iotcentral` | `Microsoft.IoTCentral/iotApps` |
| `azure_rm_iothub` | `Microsoft.Devices/IotHubs` |
| `azure_rm_iothubdps` | `Microsoft.Devices/provisioningServices` |
| `azure_rm_mapsaccount` | `Microsoft.Maps/accounts` |

### Messaging & Events

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_eventgriddomain` | `Microsoft.EventGrid/domains` |
| `azure_rm_eventgridsystemtopic` | `Microsoft.EventGrid/systemTopics` |
| `azure_rm_eventgridtopic` | `Microsoft.EventGrid/topics` |
| `azure_rm_eventhub` | `Microsoft.EventHub/namespaces/eventhubs` |
| `azure_rm_eventhubnamespace` | `Microsoft.EventHub/namespaces` |
| `azure_rm_notificationhubnamespace` | `Microsoft.NotificationHubs/namespaces` |
| `azure_rm_servicebusnamespace` | `Microsoft.ServiceBus/namespaces` |
| `azure_rm_servicebusqueue` | `Microsoft.ServiceBus/namespaces/queues` |
| `azure_rm_servicebustopic` | `Microsoft.ServiceBus/namespaces/topics` |
| `azure_rm_signalrservice` | `Microsoft.SignalRService/signalR` |

### Networking

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_applicationgateway` | `Microsoft.Network/applicationGateways` |
| `azure_rm_azurefirewall` | `Microsoft.Network/azureFirewalls` |
| `azure_rm_bastionhost` | `Microsoft.Network/bastionHosts` |
| `azure_rm_ddosprotectionplan` | `Microsoft.Network/ddosProtectionPlans` |
| `azure_rm_dnszone` | `Microsoft.Network/dnsZones` |
| `azure_rm_expressroutecircuit` | `Microsoft.Network/expressRouteCircuits` |
| `azure_rm_firewallpolicy` | `Microsoft.Network/firewallPolicies` |
| `azure_rm_frontdoorprofile` | `Microsoft.Cdn/profiles` |
| `azure_rm_ipgroup` | `Microsoft.Network/ipGroups` |
| `azure_rm_loadbalancer` | `Microsoft.Network/loadBalancers` |
| `azure_rm_natgateway` | `Microsoft.Network/natGateways` |
| `azure_rm_networkinterface` | `Microsoft.Network/networkInterfaces` |
| `azure_rm_networkwatcher` | `Microsoft.Network/networkWatchers` |
| `azure_rm_privatednszone` | `Microsoft.Network/privateDnsZones` |
| `azure_rm_privateendpoint` | `Microsoft.Network/privateEndpoints` |
| `azure_rm_publicipaddress` | `Microsoft.Network/publicIPAddresses` |
| `azure_rm_routetable` | `Microsoft.Network/routeTables` |
| `azure_rm_securitygroup` | `Microsoft.Network/networkSecurityGroups` |
| `azure_rm_subnet` | `Microsoft.Network/virtualNetworks/subnets` |
| `azure_rm_trafficmanagerprofile` | `Microsoft.Network/trafficmanagerprofiles` |
| `azure_rm_virtualnetwork` | `Microsoft.Network/virtualNetworks` |
| `azure_rm_virtualnetworkgateway` | `Microsoft.Network/virtualNetworkGateways` |
| `azure_rm_vpngateway` | `Microsoft.Network/vpnGateways` |

### Security & Identity

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_defenderplan` | `Microsoft.Security/pricings` |
| `azure_rm_keyvault` | `Microsoft.KeyVault/vaults` |
| `azure_rm_keyvaultkey` | `Microsoft.KeyVault/vaults/keys` |
| `azure_rm_keyvaultsecret` | `Microsoft.KeyVault/vaults/secrets` |
| `azure_rm_managementlock` | `Microsoft.Authorization/locks` |
| `azure_rm_policyassignment` | `Microsoft.Authorization/policyAssignments` |
| `azure_rm_policydefinition` | `Microsoft.Authorization/policyDefinitions` |
| `azure_rm_roleassignment` | `Microsoft.Authorization/roleAssignments` |
| `azure_rm_roledefinition` | `Microsoft.Authorization/roleDefinitions` |
| `azure_rm_securitycentercontact` | `Microsoft.Security/securityContacts` |
| `azure_rm_userassignedidentity` | `Microsoft.ManagedIdentity/userAssignedIdentities` |

### Monitoring & Diagnostics

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_applicationinsights` | `Microsoft.Insights/components` |
| `azure_rm_diagnosticsetting` | `Microsoft.Insights/diagnosticSettings` |
| `azure_rm_loganalyticsworkspace` | `Microsoft.OperationalInsights/workspaces` |
| `azure_rm_monitoractiongroup` | `Microsoft.Insights/actionGroups` |
| `azure_rm_monitormetricalert` | `Microsoft.Insights/metricAlerts` |

### Storage

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_storageaccount` | `Microsoft.Storage/storageAccounts` |
| `azure_rm_storagecontainer` | `Microsoft.Storage/storageAccounts/blobServices/containers` |
| `azure_rm_storagefileshare` | `Microsoft.Storage/storageAccounts/fileServices/shares` |
| `azure_rm_storagequeue` | `Microsoft.Storage/storageAccounts/queueServices/queues` |
| `azure_rm_storagetable` | `Microsoft.Storage/storageAccounts/tableServices/tables` |

### Web & Serverless

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_apimanagement` | `Microsoft.ApiManagement/service` |
| `azure_rm_appserviceplan` | `Microsoft.Web/serverfarms` |
| `azure_rm_cdnendpoint` | `Microsoft.Cdn/profiles/endpoints` |
| `azure_rm_cdnprofile` | `Microsoft.Cdn/profiles` |
| `azure_rm_functionapp` | `Microsoft.Web/sites` |
| `azure_rm_logicapp` | `Microsoft.Logic/workflows` |
| `azure_rm_staticwebapp` | `Microsoft.Web/staticSites` |
| `azure_rm_webapp` | `Microsoft.Web/sites` |

### Management & Governance

| Module | Azure Resource Provider |
|--------|------------------------|
| `azure_rm_appconfiguration` | `Microsoft.AppConfiguration/configurationStores` |
| `azure_rm_automationaccount` | `Microsoft.Automation/automationAccounts` |
| `azure_rm_automationrunbook` | `Microsoft.Automation/automationAccounts/runbooks` |
| `azure_rm_backuppolicyvm` | `Microsoft.RecoveryServices/vaults/backupPolicies` |
| `azure_rm_batchaccount` | `Microsoft.Batch/batchAccounts` |
| `azure_rm_communicationservice` | `Microsoft.Communication/communicationServices` |
| `azure_rm_deployment` | `Microsoft.Resources/deployments` |
| `azure_rm_devtestlab` | `Microsoft.DevTestLab/labs` |
| `azure_rm_maintenanceconfiguration` | `Microsoft.Maintenance/maintenanceConfigurations` |
| `azure_rm_managedapplication` | `Microsoft.Solutions/applications` |
| `azure_rm_recoveryservicesvault` | `Microsoft.RecoveryServices/vaults` |
| `azure_rm_resourcegroup` | `Microsoft.Resources/resourceGroups` |
| `azure_rm_templatespec` | `Microsoft.Resources/templateSpecs` |

> Each module listed above generates both a CRUD module (`azure_rm_<name>.py`) and an info module (`azure_rm_<name>_info.py`).

## Requirements

- Python >= 3.12
- `jinja2 >= 3.1`
- `pyyaml >= 6.0`

Generated modules target [azure.azcollection](https://github.com/ansible-collections/azure) and require `ansible-core >= 2.14`.

## License

GNU General Public License v3.0
