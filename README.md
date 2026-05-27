# ccbackup_bot

ccbackup_bot is a read-only Cisco switch backup utility. It reads switch names
and IP addresses from an Excel file, connects to each switch, runs
`show running-config`, and stores the output in a dated backup folder.

This release does not modify switch configuration. It does not create VLANs,
change interfaces, push configuration, or run `write memory`.

## Telnet Warning

The current version uses Telnet. Telnet sends usernames and passwords in clear
text and should only be used on trusted management networks. SSH support using
Netmiko is the next priority.

## Device Inventory

Create an Excel file with at least these columns:

| Switch_name | Ip-address |
| --- | --- |
| core-sw-01 | 192.168.1.10 |
| access-sw-01 | 192.168.1.11 |

The loader also accepts friendlier column names like `name` and `ip`.

## Credentials

Copy `credentials.example.json` to `credentials.json` and update the values.
Real credentials must never be committed to Git or shared in release packages.
The `enable_password` value can be blank if enable mode is not required in your
environment.

```json
{
  "username": "example_operator",
  "password": "not-a-real-password",
  "enable_password": "",
  "connection_type": "telnet"
}
```

Do not commit real credentials.

## Run

```bash
python swbck.py --devices devices.xlsx --credentials credentials.json
```

Backups are saved under:

```text
backups/YYYY-MM-DD/
```

Expected backup output example:

```text
backups/YYYY-MM-DD/switch-name.txt
```

Optional PostgreSQL-backed configuration history can be enabled with:

```bash
python swbck.py --devices devices.xlsx --credentials credentials.json --db-report
```

Database setup is documented in
[docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md). The app still works normally
without PostgreSQL configured.

## GUI

Install the requirements, then start the desktop app:

```bash
pip install -r requirements.txt
python gui.py
```

The first GUI supports selecting the device inventory, credentials file, and
backup folder before running a backup job.

The GUI remembers the selected file and folder paths for the current Windows
user. It stores only paths, not passwords or credential contents. Saved paths
can be cleared from the GUI with **Reset Saved Paths**.

The GUI also includes an optional **Store backups in PostgreSQL / Generate DB
change report** checkbox. If selected, PostgreSQL connection settings must be
provided through environment variables. If database settings are missing, the
normal file backup still runs and the log explains that database storage was
skipped.

On Windows, GUI settings are stored at:

```text
%APPDATA%\ccbackup_bot\gui_settings.json
```

## Windows Packaged Version

A PyInstaller packaging prototype is available for Windows users who are not
comfortable running Python scripts manually. See
[packaging/README.md](packaging/README.md) for build instructions and release
notes. The Windows user guide is available at
[docs/USER_GUIDE_WINDOWS.md](docs/USER_GUIDE_WINDOWS.md). Credentials and
inventory files are not bundled.

For non-Python Windows users, start with the step-by-step
[Windows user guide](docs/USER_GUIDE_WINDOWS.md).

## Before Running Against Real Switches

- Confirm you are on a trusted management network.
- Confirm Telnet is permitted by your internal security policy.
- Use a test switch first.
- Confirm the Excel inventory has the correct switch names and IP addresses.
- Confirm `credentials.json` contains the correct username and password.
- Confirm real credentials are not committed to Git.
- Confirm the selected backup folder is writable.
- Review the log after the run and check that backup files were created.

## Planned Future Features

- SSH support using Netmiko.
- Better inventory validation and clearer import errors.
- Packaged Windows release for users who are not comfortable running Python.
- Backup result summaries and exportable reports.

Configuration-changing tools are not part of this read-only release.

