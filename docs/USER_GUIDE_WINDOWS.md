# Windows User Guide - ccbackup-bot Read-Only Release

This guide is for Globecast users who need to run Cisco switch backups from the Windows GUI. You do not need to install Python or type Python commands when using the packaged Windows release.

## What The App Does

ccbackup-bot reads a switch inventory from an Excel file, connects to each listed Cisco switch, runs `show running-config`, and saves the returned running configuration as a text backup file.

This release is read-only. It is intended for collecting backups, not changing switch configuration.

## What The App Does Not Do

This release does not make configuration changes.

It does not:

- add, remove, or change VLANs
- change interfaces
- push configuration commands
- run `write memory`
- save changes to startup configuration
- change routing, management, or access settings
- change Telnet, SSH, or other switch service settings

If a task requires changing switch configuration, use the approved network operations process. Do not use this read-only backup tool for that work.

## Launch ccbackup-bot.exe

Open the packaged Windows release folder:

```text
dist\ccbackup-bot\
```

Double-click:

```text
ccbackup-bot.exe
```

The app opens a small Windows GUI called `Cisco Backup Utility`.

## Prepare The Excel Inventory File

Create an Excel file with one row per switch. The file can be `.xlsx` or `.xls`.

Required columns:

| Switch_name | Ip-address |
| --- | --- |
| core-sw-01 | 192.168.10.10 |
| access-sw-01 | 192.168.10.11 |
| studio-sw-02 | 192.168.10.12 |

The app also accepts these alternative column names:

- Switch name: `Switch_name`, `switch_name`, `name`, `Name`
- IP address: `Ip-address`, `ip_address`, `ip`, `IP`, `IP Address`

Use clear switch names. The switch name is used when naming the backup file.

Avoid blank switch names or blank IP addresses. Blank rows are ignored.

## Prepare credentials.json

Find the sample credentials file:

```text
credentials.example.json
```

Make a copy of it and rename the copy to:

```text
credentials.json
```

Edit `credentials.json` with the switch login details:

```json
{
  "username": "example_operator",
  "password": "not-a-real-password",
  "enable_password": "",
  "connection_type": "telnet"
}
```

Field notes:

- `username`: the switch username, if your switches ask for one
- `password`: the switch login password
- `enable_password`: the enable password; leave blank only if enable mode is not required
- `connection_type`: use `telnet` for this read-only release

Do not store or email real passwords carelessly. Keep `credentials.json` private. Do not commit it to Git, include it in release packages, or send it through email or chat unless Globecast policy explicitly allows that method.

## Choose Files In The GUI

In the app, use the `Browse` buttons to select:

- `Device inventory`: your Excel inventory file
- `Credentials`: your private `credentials.json` file
- `Backup folder`: the folder where backup files should be saved

The app remembers these paths for the current Windows user. It stores only the selected file and folder paths. It does not store passwords or the contents of `credentials.json`.

Saved GUI paths are stored here:

```text
%APPDATA%\ccbackup_bot\gui_settings.json
```

## Reset Saved Paths

Click `Reset Saved Paths` if the app is pointing to old files or an old backup folder.

This only clears the remembered paths in the GUI. It does not delete:

- the Excel inventory file
- `credentials.json`
- any backup output files

After resetting, use the `Browse` buttons to choose the files and folder again.

## Optional Database Change Report

The GUI includes a checkbox:

```text
Store backups in PostgreSQL / Generate DB change report
```

Leave this unchecked unless PostgreSQL has been configured for your site. Normal
file backups work without PostgreSQL.

If enabled, successful backups are stored in PostgreSQL and a report is written
under the selected backup output folder:

```text
reports/config_changes_YYYYMMDD_HHMMSS.txt
```

The report shows whether each switch changed compared with its previous
successful database backup. Database setup is documented in
`docs/DATABASE_SETUP.md`.

## Read-Only Serial Console Identification

The GUI includes a **Serial Console - READ-ONLY Identification** section for
identifying a switch connected by console cable.

Use it to:

- refresh available COM ports
- select the console COM port
- keep the default `9600` baudrate unless instructed otherwise
- identify the switch prompt, hostname, model, serial number, and IOS version
- save a serial session log
- run a read-only restore readiness check
- save a pre-restore safety backup bundle if existing configuration is detected

This feature does not restore configuration, enter configuration mode, run
`write memory`, run copy commands, reload the switch, or answer the initial
setup dialog.

If the switch opens at a prompt ending in `>`, the app may use the provided
credentials to enter enable mode so it can run read-only `show` commands. It
still does not enter configuration mode or save changes.

More details are available in `docs/SERIAL_CONSOLE.md`.

If the readiness state is `HAS_EXISTING_CONFIG`, it means the switch appears to
already have meaningful configuration such as a non-default hostname, local
users, AAA, VLANs, IP interfaces, routes, or startup-config content. The app
will save a safety backup bundle under:

```text
backup-folder\
  pre_restore_backups\
    YYYYMMDD_HHMMSS_HOSTNAME\
```

No restore actions are performed in this release.

## Run A Backup

1. Confirm the `Device inventory` path is correct.
2. Confirm the `Credentials` path is correct.
3. Confirm the `Backup folder` path is correct and writable.
4. Click `Back Up Switches`.
5. Watch the log window for progress, success messages, and failures.

The button is disabled while the backup job is running. When the job finishes, the log shows a summary like:

```text
All done. Successful: 3, Failed: 0
```

If any device fails, the app displays a message telling you to check the log.

## Confirm Backups Were Created

Open the selected backup folder. The app creates a dated subfolder for each run date.

Expected output folder structure:

```text
backups\
  2026-05-21\
    core-sw-01.txt
    access-sw-01.txt
    studio-sw-02.txt
```

Each `.txt` file should contain the running configuration output from one switch.

The exact dated folder name uses the Windows PC date on the day the backup is run.

If database reporting is enabled, also check:

```text
backups\
  reports\
    config_changes_YYYYMMDD_HHMMSS.txt
```

## Common Errors

### Inventory File Missing

Meaning:

The selected Excel inventory file does not exist, was moved, or the saved path is stale.

What to do:

Use `Browse` beside `Device inventory` and select the correct `.xlsx` or `.xls` file.

### Credentials File Missing

Meaning:

The selected `credentials.json` file does not exist, was moved, or the saved path is stale.

What to do:

Use `Browse` beside `Credentials` and select the correct private `credentials.json` file.

### Output Folder Unavailable

Meaning:

The selected backup folder cannot be opened or created. This is usually a Windows permissions issue, a disconnected network drive, or an unavailable removable drive.

What to do:

Choose a local folder or a reachable shared folder where your Windows user has write permission.

### Switch Unreachable

Meaning:

The app could not reach the switch IP address before attempting the backup.

What to do:

Check the IP address in the inventory, network connection, VPN or office network access, routing, firewall rules, and whether the switch is powered on.

### Login Failed

Meaning:

The switch rejected the login, the username/password is wrong, Telnet is not allowed, or the switch prompt/login process differs from what this release expects.

What to do:

Confirm the credentials manually through the normal approved network access method. Confirm Telnet access is permitted from the Windows PC running the app.

### Enable Password Failed

Meaning:

The enable password may be wrong, the account may not have permission to enter enable mode, or the switch may not require enable mode in the way this release expects.

What to do:

Check `enable_password` in `credentials.json`. If enable mode is not required in your environment, it can be blank.

### No Running-Config Output Received

Meaning:

The switch did not return usable `show running-config` output. The account may not have permission, the session may have closed early, or the switch prompt/output may be different from expected.

What to do:

Try the same login manually and run `show running-config` using the approved operations process. Confirm the account can view the running configuration.

### PostgreSQL Storage Skipped

Meaning:

The app could not find database settings, could not connect to PostgreSQL, or
the database driver was unavailable. The normal file backup can still succeed
without database storage.

What to do:

Leave the database checkbox unticked if your site is not using PostgreSQL
history yet. If your site is using it, check the environment variables described
in `docs/DATABASE_SETUP.md`.

## Telnet Security Warning

This release uses Telnet. Telnet sends usernames and passwords in clear text.

Use this app only on trusted management networks approved by Globecast security and network operations. Do not run it across untrusted networks.

## Read-Only Reminder

This version only runs show commands for backup collection. It does not add SSH support, change VLANs, change interfaces, save configuration, or modify switch settings.

## Basic Escalation Note

If many devices fail at once, check network reachability, credentials, and Telnet access before blaming the app. A widespread failure is usually caused by a network, access, credentials, or management-service issue rather than the backup utility itself.
