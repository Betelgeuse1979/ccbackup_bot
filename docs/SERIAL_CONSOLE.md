# Read-Only Serial Console Identification

This feature is for identifying a Cisco replacement switch through a serial
console cable before any future restore workflow exists.

This release is read-only. It does not restore configuration, enter
configuration mode, run `write memory`, run copy commands, reload the switch, or
answer the initial setup dialog.

## Supported Use Case

Use serial identification when a switch is connected to a Windows PC with a
USB-to-serial adapter or console cable and you need to confirm basic device
identity.

The app attempts to collect:

- console prompt
- hostname
- model
- serial number
- IOS version
- raw serial session log

## Restore Readiness Check

The read-only restore readiness check classifies the connected switch as:

- `LIKELY_FACTORY_DEFAULT`
- `HAS_EXISTING_CONFIG`
- `UNKNOWN_NEEDS_MANUAL_REVIEW`

It uses show commands only. It does not enter configuration mode, save
configuration, copy files, erase files, reload the device, or answer setup
dialog prompts.

If the console lands at a user exec prompt ending in `>`, the app may enter
enable mode using the provided credentials so that read-only `show` commands
such as `show running-config` and `show startup-config` are available. It still
does not enter configuration mode or save any changes.

Evidence of existing configuration includes:

- non-default hostname
- VLANs other than default
- interface descriptions
- configured IP interfaces
- static routes
- routing protocols
- AAA configuration
- local usernames
- enable secret
- startup-config content
- non-trivial running-config size

If existing configuration is detected, the app automatically saves a
pre-restore safety backup bundle before any future restore workflow could be
used.

Bundle structure:

```text
backup-output-folder/
  pre_restore_backups/
    YYYYMMDD_HHMMSS_HOSTNAME/
      running-config.txt
      startup-config.txt
      show-version.txt
      show-inventory.txt
      vlan-brief.txt
      ip-interface-brief.txt
      readiness-report.txt
      serial-session.log
```

The readiness report states that the switch appears already configured, that a
backup was captured, and that no restore actions were performed.

## Default Cisco Console Settings

The default settings are:

- 9600 baud
- 8 data bits
- no parity
- 1 stop bit
- no flow control

These are the standard Cisco console settings for many switches.

## Find The COM Port In Windows

1. Plug in the USB-to-serial adapter or console cable.
2. Open **Device Manager**.
3. Expand **Ports (COM & LPT)**.
4. Look for the adapter name, for example `USB Serial Port (COM3)`.
5. Use that COM port in the app.

## CLI Usage

List available serial ports:

```powershell
python swbck.py --list-serial-ports
```

Identify a switch on `COM3`:

```powershell
python swbck.py --serial-identify COM3
```

Run a read-only restore readiness check:

```powershell
python swbck.py --serial-readiness COM3
```

Use a different baudrate:

```powershell
python swbck.py --serial-identify COM3 --serial-baudrate 115200
```

The CLI writes a serial session log under:

```text
backups/logs/
```

## GUI Usage

In the Windows GUI, use the **Serial Console - READ-ONLY Identification**
section:

1. Click **Refresh COM Ports**.
2. Select the COM port.
3. Leave baudrate at `9600` unless instructed otherwise.
4. Click **Identify Switch Over Serial**.
5. Review the result summary in the log window.

To check whether a replacement switch already has configuration, click
**Run Restore Readiness Check**. If existing configuration is found, review the
evidence and the pre-restore safety backup bundle path shown in the log.

The serial session log is saved under:

```text
selected-backup-folder/logs/
```

## Initial Setup Dialog

If the switch asks:

```text
Would you like to enter the initial configuration dialog?
```

the app does not answer yes or no. It stops and reports that the initial setup
prompt was detected.

## Troubleshooting

**Wrong COM port**

Refresh COM ports and confirm the port in Windows Device Manager.

**Wrong baudrate**

If the output is unreadable or blank, try the expected site baudrate. Start with
`9600`.

**No output until Enter is pressed**

This is normal on many console sessions. The app sends Enter before trying to
detect the prompt.

**USB serial driver issue**

If no COM port appears, install the correct driver for the USB-to-serial adapter
and reconnect the cable.

## Future Restore Warning

Restore mode is not implemented in this release. Do not use this feature as a
restore tool. It is only for safe device identification and logging.
