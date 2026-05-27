# Windows Packaging

This folder contains a prototype PyInstaller build for the read-only Cisco
backup GUI.

The packaged app remains read-only. It only runs show commands and saves backup
files. It does not create VLANs, change interfaces, push configuration, save
configuration, or run `write memory`.

## Prerequisites

- Windows.
- Python installed and available through the `py` launcher.
- PowerShell.
- Network access if dependencies need to be downloaded.

## Build

Run from the repository root:

```powershell
.\packaging\build_windows_gui.ps1
```

The script will:

- create or reuse `.venv`
- install `requirements.txt`
- install `requirements-dev.txt`
- run compile checks
- build a one-folder GUI app with PyInstaller

## Output

The packaged app is created under:

```text
dist/ccbackup-bot/
```

The executable is expected at:

```text
dist/ccbackup-bot/ccbackup-bot.exe
```

## Files Users Must Provide

Users must manually provide:

- a device inventory Excel file
- a private `credentials.json` file
- a writable backup output folder

Real credentials are not bundled into the packaged app and should never be
committed to Git or included in release archives.

For step-by-step user instructions, see
[docs/USER_GUIDE_WINDOWS.md](../docs/USER_GUIDE_WINDOWS.md).

Include the [Windows user guide](../docs/USER_GUIDE_WINDOWS.md) with any
read-only Windows release shared with Globecast operators.

## Saved GUI Paths

The GUI remembers the selected inventory file, credentials file, and backup
folder for the current Windows user. It stores only file and folder paths.
Passwords and credential contents are not stored in the GUI settings file.

On Windows, settings are stored at:

```text
%APPDATA%\ccbackup_bot\gui_settings.json
```

Users can clear these saved paths from the app with **Reset Saved Paths**.

## Notes

The current release uses Telnet, which sends credentials in clear text. Use only
on trusted management networks. SSH/Netmiko support is the next priority.

Optional PostgreSQL-backed configuration history is documented in
[docs/DATABASE_SETUP.md](../docs/DATABASE_SETUP.md). PostgreSQL settings are
provided by environment variables and are not bundled into the packaged app.

Read-only serial console identification is documented in
[docs/SERIAL_CONSOLE.md](../docs/SERIAL_CONSOLE.md).
That guide also covers the read-only restore readiness check and pre-restore
safety backup bundle.
