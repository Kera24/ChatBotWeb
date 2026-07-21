# Infrastructure

Infrastructure definitions for local development and controlled pilot deployment.

## Current folders

- `azure` - Bicep foundation for Azure staging and controlled-production-pilot infrastructure.

## Local development

Local development remains Docker Compose based:

```bash
docker compose up postgres redis
```

The Compose `app` profile keeps development commands for API reload and Next.js dev server.

## Azure controlled pilot

TASK-068B1 adds the Azure-first infrastructure foundation selected by ADR-0018. It does not deploy live infrastructure or change DNS.

Validate locally:

```bash
npm run infra:azure:validate
```

Run non-destructive what-if after Azure credentials and secure parameters are configured:

```bash
npm run infra:azure:whatif -- staging
```

See:

- `docs/04_Engineering/Azure_Controlled_Pilot_Infrastructure.md`
- `docs/06_Operations/Azure_Infrastructure_Deployment_Runbook.md`
- `docs/06_Operations/Azure_Widget_Domain_and_TLS_Runbook.md`
- `docs/06_Operations/Azure_Secret_Bootstrap_Runbook.md`
