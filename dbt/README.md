# dbt and Snowflake migration scaffold

This directory expresses the production-oriented model boundary for the local reference
implementation. It is not represented as a deployed production system.

## Intended workflow

1. Load the generated CSVs into a Snowflake `RAW` schema.
2. Copy `profiles.yml.example` to a secure local profiles directory.
3. Set the `DBT_SNOWFLAKE_*` environment variables without committing credentials.
4. Run `dbt debug`, `dbt build` and `dbt docs generate`.
5. Inspect lineage, source freshness and singular safety tests before activation.

## Production hardening still required

- Replace password authentication with the production-approved authentication method.
- Configure least-privilege roles and warehouse resource monitors.
- Add source freshness using real ingestion timestamps.
- Convert high-volume event and listing models to incremental materializations.
- Add CI with a zero-copy clone or isolated development schema.
- Route test failures to the company's incident and campaign-release process.
