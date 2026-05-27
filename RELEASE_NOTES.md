# Release Notes - Read-Only Backup Version

## What This Tool Does

ccbackup_bot is a read-only Cisco switch backup utility. It reads an Excel
inventory, connects to listed switches, runs `show running-config`, and saves
each backup as a text file in a dated output folder.

Expected output example:

```text
backups/YYYY-MM-DD/switch-name.txt
```

## What This Tool Does Not Do

This release does not modify switch configuration. It does not create VLANs,
change interfaces, push configuration, save configuration, or run `write memory`.

## Requirements

- Python 3.10 or newer recommended.
- Dependencies from `requirements.txt`.
- An Excel inventory with switch names and IP addresses.
- A local `credentials.json` file based on `credentials.example.json`.
- Network reachability to the target switches.

## Known Limitations

- Telnet only in this release.
- Telnet sends credentials in clear text.
- SSH/Netmiko support is not included yet.
- The tool is designed for Cisco-style prompts and running-config output.
- Backups depend on the account having permission to run `show running-config`.

## Basic Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Run from the command line:

```bash
python swbck.py --devices devices.xlsx --credentials credentials.json
```

Run the desktop GUI:

```bash
python gui.py
```

## Safety Notes

- Use only on trusted management networks.
- Do not commit real credentials.
- Keep `credentials.json` local and private.
- Test against one known switch before running against a larger inventory.
- Review backup logs and confirm files were created.

## Recommended Next Steps

- Add SSH support using Netmiko.
- Package the GUI as a Windows application for Globecast users.
- Improve user-friendly validation for inventory files.
- Add backup summaries and simple reporting.
