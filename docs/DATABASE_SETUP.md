# Optional PostgreSQL Configuration History

PostgreSQL storage is optional. The backup utility still writes normal text
backup files when no database is configured.

When enabled, successful backups are stored in PostgreSQL and a change report is
written to:

```text
backup-output-folder/reports/config_changes_YYYYMMDD_HHMMSS.txt
```

## Enable Database Storage

Set this environment variable to enable database storage from the command line:

```powershell
$env:CCBACKUP_ENABLE_DB = "1"
```

Or run the CLI with:

```powershell
python swbck.py --devices devices.xlsx --credentials credentials.json --db-report
```

In the Windows GUI, tick:

```text
Store backups in PostgreSQL / Generate DB change report
```

## Connection Settings

Use one database URL:

```powershell
$env:CCBACKUP_DATABASE_URL = "postgresql://user:password@server:5432/database"
```

Or use separate PostgreSQL fields:

```powershell
$env:CCBACKUP_PGHOST = "postgres-server"
$env:CCBACKUP_PGPORT = "5432"
$env:CCBACKUP_PGDATABASE = "ccbackup"
$env:CCBACKUP_PGUSER = "ccbackup_user"
$env:CCBACKUP_PGPASSWORD = "change-this-password"
```

Do not hardcode database credentials in the application.

## What Gets Stored

The database stores:

- device hostname and management IP
- backup timestamp
- full running configuration text
- SHA256 hash of the normalized configuration
- backup file path
- full unified diff between the previous and latest successful backup
- a short change summary

The app creates the required tables automatically if the database user has
permission.

## Security Warning

Running configuration files can contain sensitive network information and may
include secrets depending on switch configuration. Treat the PostgreSQL database
as sensitive infrastructure:

- restrict database access
- use strong database credentials
- protect backups of the database
- do not expose the database to untrusted networks
- follow Globecast security requirements for storing network configuration data

## Read-Only Boundary

This feature does not change switch configuration. It only stores successful
read-only backup results and generates change reports.
