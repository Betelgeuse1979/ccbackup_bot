# ccbackup_bot
It's a basic program that reads Cisco switch configs and stores them in a file.


 It reads the name and IP address of an Excel spreadsheet, logs into every switch and copies the config in a file named the same as the switch name in the Excel file.

This is for internal use because it uses telnet to connect to each switch, but I will make an SSH version if anybody needs it.

User credentials need to be updated in JSON file.

