# ansible-inventory-ad

Ansible dynamic inventory script for finding computer devices in Active Directory.

*The script was designed for Active Directory but since it just uses LDAP, it should work with non-AD LDAP too. Untested!*

## Changelog

### 07/05/2017

**Inventory script**

  - Renamed project from `ansible-inventory-ldap` to `ansible-inventory-ad` as that is what it's designed for and tested against.
  - Renamed master script from `ansible-ldap.py` to `ansible_ad.py`.
  - Converted entire inventory script from standalone functions to `AnsibleInventoryLDAP` class. All functions are now methods of the class, variables are properties, etc.
  - **Functionality change:** Previously, the `--hostgroup` parameter was defined and all child computers were placed under this named host group. Now, the name of the OU defined in `basedn` is used for the top-level Ansible grup, and child OUs are now returned as their own host groups, containing the computers within the OU. This means that the inventory can now be pointed at an OU within Active Directory and the resulting inventory JSON will mirror the AD tree.
  - **Removed parameter:** `--hostgroup`. Functionality deprecated.
  - **New parameter:** `--no-children` - Specifying this stops each child OU from being linked as a child of the parent OU. This is useful when you only want to run playbooks against an OU, and not all child OUs.
  - **New parameter** `--os`. This allows you to search for a specific value within the `Operating System` field.
  - **Removed parameter:** `--only-windows`. Functionaltiy deprecated by new parameter `--os`.

**Other**

  - Wrapper script name changed from `ldap_winservers.py` to `production_servers.py`.

## Overview

The main dynamic inventory script (`ansible_ad.py`) is a command-line utility that will search an Active Directory, and return each OU as a host group containing all of the computers within as Ansible hosts. To facilitate the use of this with Ansible, a wrapper script is included called `production_servers.py`. The wrapper script can be duplicated and renamed as appropriate, to apply against different parts of AD, different directories, etc.

### Wrapper script

Because you can't pass any extra arguments to a dynamic inventory script (Ansible simply calls it with either `--list` or `--host <hostname>`), it makes the dynamic inventory scripts pretty rigid and not reusable. But by using a wrapper script, we can create multiple copies that all call the master script with different arguments - the main one being the OU to search in.

In the wrapper script, there are some variables you can change, but the whole thing can be altered as required (And it doesn't have to be a python script, it can just as easily be a bash script).

### Master script

The main python script accepts a number of options for searching & refining the results before outputting them in ansible-friendly json.

```
usage: ansible-ldap.py [-h] [--user USER] [--password PASSWORD]
                       [--ldapuri LDAPURI] [--recursive] [--no-children]
                       [--fqdn] [--os OS] [--group-prefix GROUP_PREFIX]
                       [--list | --host HOST]
                       basedn

Populate ansible inventory from LDAP.

positional arguments:
  basedn                DN of the OU to search in.

optional arguments:
  -h, --help            show this help message and exit
  --user USER, -u USER  DN of user to authenticate as.
  --password PASSWORD, -p PASSWORD
                        Password of user to authenticate as.
  --ldapuri LDAPURI     URI of the LDAP server (ldap://dc01.mydomain.local).
  --recursive, -r       Recursively search into sub-OUs
  --no-children, -c     Don link child OUs as children in the inventory (Stops
                        inheritance).
  --fqdn                Output the hosts FQDN, not just host name
  --os OS, -os OS       Only return hosts matching the OS specified (Uses ldap
                        formatting, so '*windows*').
  --group-prefix GROUP_PREFIX
                        Prefix all group names.
  --list                List all nodes from specified OU.
  --host HOST           Not implemented.

```

You can call the script directly for testing, for example:

```bash
/etc/ansible/dynamic_inventory/ansible_ad.py --username 'CN=AnsibleRunner,OU=Service Accounts,DC=mydomain,DC=local' --password 'mysupersecretamazingpasswordhere' --ldapuri 'ldap://dc01.mydomain.local' --fqdn 'OU=Production Servers,DC=MyDomain,DC=local'
```

### Fallback args

Instead of forcing each wrapper to include a `username`, `password`, `ldapuri` and `hostgroup` argument (Used for authenticating with LDAP), you can ommit them and supply them in the `fallback_args` dictionary that is in the master script. This way, if you have 5 different wrappers for different OUs that all share the same credentials, just specify it once in the master, and if you have any others that want to override the `fallback_args`, specify them in the wrapper.

```python
fallback_args  = dict(
    ldapuri = os.getenv('LDAP_URI','ldap://dc01.mydomain.local'),
    user = os.getenv('LDAP_USER','CN=AnsibleRunner,OU=Service Accounts, DC=MyDomain,DC=local'),
    password = os.getenv('LDAP_PASS','mysupersecretamazingpasswordhere'),
    hostgroup = os.getenv('LDAP_HOSTGROUP','ldap_hosts')
)
```

The example included first tries to use environmental variables and if they don't exist, uses an explicitly defined default.

**Please note:** Storing username & passwords in your inventory files is a security consideration. Please look at using vault or environmental variables as a safer solution.

## Usage with Ansible

  - Store the master script (eg. `/etc/ansible/dynamic_inventory/ansible_ad.py`) and make sure it's executable (`chmod +x`).
  - Store the wrapper script(s) (eg. `/etc/ansible/inventory/ldap/production_servers.py`)
  - Add your `username`, `password`, etc. wherever you feel comfortable. Run a test by calling the wrapper directly and ensure you get the json output you're expecting.
  - Run a test with ansible: `ansible ldap_file_servers -i /etc/ansible/inventory/ldap/production_servers.py -m win_ping`.

**ProTip**: You can statically apply host/group vars against the returned hosts/groups, as long as you know their names. For example, I can add a `host_vars/filesrv01.mydomain.local` file containing host vars and as long as that host is returned, the static vars will be applied.

## Inventory breakdown

**AD layout:**

```bash
.
└── Production Servers
    ├── Domain Controllers
    │   ├── dc01
    │   └── dc02
    ├── File Servers
    │   ├── filesrv01
    │   ├── filesrv02
    │   ├── filesrv03
    │   └── filesrv04
    └── Web Servers
        ├── iis01
        ├── iis02
        ├── nginx01
        └── nginx02
```


**Wrapper script:**

```python
#!/usr/bin/env python

import sys
import os

# Path to the master script
scriptpath = "/etc/ansible/dynamic_inventories/ansible_ad.py"
# The DN of the OU in which to search
basedn = "OU=Production Servers,OU=Member servers,DC=mydomain,DC=local"

# Any custom args to pass to master script
# (Run the master script with -h for a list)
custom_args = "--fqdn --os '*win*' --group-prefix 'ldap_' --recursive"

if __name__ == '__main__':
    ansible_args = ''.join(sys.argv[1:]) # Any arguments that ansible has called the script with (Eg. --list)

    # Build the command string for python to run
    cmd = "%s %s %s '%s'" % (scriptpath, custom_args, ansible_args, basedn)
    os.system(cmd)
```

Now, using the above script will return the follwing inventory (`_meta` section excluded):

```json
{
  "ldap_production_servers": {
    "hosts": [], 
    "children": [
      "ldap_domain_controllers",
      "ldap_file_servers",
      "ldap_web_servers"
    ], 
    "vars": {}
  }, 
  "ldap_domain_controllers": {
    "hosts": [
      "dc01.mydomain.local", 
      "dc02.mydomain.local" 
    ], 
    "children": [], 
    "vars": {}
  },
  "ldap_file_servers": {
    "hosts": [
      "filesrv01.mydomain.local", 
      "filesrv02.mydomain.local", 
      "filesrv03.mydomain.local", 
      "filesrv04.mydomain.local"
    ], 
    "children": [], 
    "vars": {}
  },
  "ldap_web_servers": {
    "hosts": [
      "iis01.mydomain.local", 
      "iis02.mydomain.local" 
    ], 
    "children": [], 
    "vars": {}
  }
}
```

This is equal to the following in Ansible's traditional 'ini' format:

```
[ldap_production_servers:children]
ldap_domain_controllers
ldap_file_servers
ldap_web_servers

[ldap_domain_controllers]
dc01.mydomain.local
dc02.mydomain.local

[ldap_file_servers]
filesrv01.mydomain.local
filesrv02.mydomain.local
filesrv03.mydomain.local
filesrv04.mydomain.local

[ldap_web_servers]
iis01.mydomain.local
iis01.mydomain.local
```

So, what do we have?

  - All groups are prefixed with `ldap_` as per the `--group-prefix` argument.
  - All OU names are converted to lower cased and spaces are replaced with underscores `_`.
  - The top level group is `ldap_production_servers` and all child OUs are linked in the `children` list. Without the `--recursive` flag, only hosts directly within `Production Servers` would be returned (None in this case).
  - The `nginx01` and `nginx02` hosts are missing as in AD, their `Operating System` field does not contain `win`.
  - All hosts are returned with their fqdn `xyz.mydomain.local` instead of just hostname. Remove the `--fqdn` flag for hostnames.

This means that if we now run plays against `ldap_production_servers`, it will include **ALL** hosts listed above as they are all listed as children. Specify `--no-children` to stop the child OUs being linked as children within the inventory.

