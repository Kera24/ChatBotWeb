# Azure Environment Parameters

These checked-in parameter files intentionally contain no passwords, connection strings, provider API keys, or production secrets.

Deployment commands must provide secure values at runtime, for example:

```bash
az deployment sub what-if \
  --location australiaeast \
  --template-file infrastructure/azure/main.bicep \
  --parameters infrastructure/azure/environments/staging.bicepparam \
  --parameters postgresAdministratorPassword="$AZURE_POSTGRES_ADMIN_PASSWORD"
```

`pilot.bicepparam` contains explicit `<approved-domain-required>` placeholders and is not deployable until the approved production domain is supplied through a reviewed parameter change or secure deployment parameter overlay.

Staging may initially use Azure-generated hostnames before custom domain validation is configured.
