# Azure Infrastructure Foundation

This directory contains the TASK-068B1 Azure infrastructure-as-code foundation for staging and controlled-production-pilot environments.

No checked-in file contains production credentials. Do not add passwords, connection strings, provider keys, or customer data to this directory.

## Structure

- `main.bicep` - subscription-scope entry point that creates one environment resource group and composes modules.
- `modules/` - reusable Azure resource modules.
- `environments/staging.bicepparam` - safe staging parameters.
- `environments/pilot.bicepparam` - pilot parameter template with approved-domain placeholders.
- `environments/README.md` - secure parameter guidance.

## IaC Choice

Bicep is used for TASK-068B1 because ADR-0018 selects Azure and the repository did not already use Terraform or Pulumi. Bicep keeps the first pilot foundation native to Azure and supports ARM what-if without introducing a state backend.

## Validation

Run:

```bash
npm run infra:azure:validate
```

This performs repository-local static checks and runs `az bicep build` when Azure CLI/Bicep is available.

Run non-destructive what-if after Azure login and secure parameter setup:

```bash
npm run infra:azure:whatif -- staging
```

The what-if helper exits without deploying if required credentials are missing.

## Deployment Boundary

TASK-068B1 prepares infrastructure code only. It does not deploy Azure resources, mutate DNS, or create live production secrets.
