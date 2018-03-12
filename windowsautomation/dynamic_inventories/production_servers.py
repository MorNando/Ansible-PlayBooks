#!/usr/bin/env python

import sys
import os

# Path to the master script
scriptpath = "/etc/ansible/dynamic_inventories/ansible_ad.py"
# The DN of the OU in which to search
basedn = "{{baseoupath}}"

# Any custom args to pass to master script
# (Run the master script with -h for a list)
custom_args = "--fqdn --os '*win*' --group-prefix 'ldap_' --recursive" 

if __name__ == '__main__':
    ansible_args = ''.join(sys.argv[1:]) # Any arguments that ansible has called the script with (Eg. --list)

    # Build the command string for python to run
    cmd = "%s %s %s '%s'" % (scriptpath, custom_args, ansible_args, basedn)
    os.system(cmd)
