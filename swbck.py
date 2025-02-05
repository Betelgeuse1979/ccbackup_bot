import pandas as pd
import telnetlib
from telnetlib import Telnet
import os
import subprocess
import json
from datetime import datetime


with open("credentials.json", "r") as cred_file:
    credentials = json.load(cred_file)

username = credentials["username"]
password = credentials["password"]


# df = pd.read_excel("PATH TO YOUR EXCEL FILE", header=0)
job_set = df.to_dict()

switch_name = job_set['Switch_name']
ip_address = job_set['Ip-address']


for k, v in switch_name.items():
    ip_address[v] = ip_address.pop(k)


date_today = datetime.now().strftime("%Y-%m-%d")
os.makedirs(date_today, exist_ok=True)


for s, i in ip_address.items():
    response = subprocess.call(["ping", "-c", "2", i])
    
    if response == 0:
        try:
            with Telnet(i, 23, timeout=10) as tn:
                tn.read_until(b"Password: ")
                tn.write(password.encode('ascii') + b"\n")
                tn.write(b"enable\n")
                tn.write(password.encode('ascii') + b"\n")
                tn.write(b"term len 0\n")
                tn.write(b"sh run\n")
                
                
                runconfig = tn.read_until(b"banner motd ^C", timeout=10)
                tn.write(b"term len 25\n")
                tn.write(b"exit\n")

                
                filename = os.path.join(date_today, f"{s}.txt")
                with open(filename, 'w') as backup_file:
                    backup_file.write(runconfig.decode('ascii'))

                print(f"Configuration for {s} saved successfully.")

        except Exception as e:
            print(f"Error connecting to {s} ({i}): {e}")
    else:
        print(f"{s} is not available on {i}")

print("All done!")

