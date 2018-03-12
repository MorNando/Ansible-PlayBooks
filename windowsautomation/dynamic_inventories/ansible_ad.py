#!/usr/bin/env python
from ansible_vault import Vault

vault = Vault('TestingPass2018')
print vault.load(open('/etc/ansible/windowsautomation/vars_and_pswds').read())

import os
import sys
import argparse

try:
    import ldap
except ImportError:
    print 'Could not import \'ldap\' module.'
    print 'Please ensure \'python-ldap\' module is installed.'
    sys.exit(1)

try:
    import json
except ImportError:
    import simplejson as json

# Configure fallback_args so you don't have to pass any commandline arguments in, or alternatively
# rely on environmental variables (Takes precedence over explicitly defined options), eg:
#   user = os.getenv('LDAP_PASS','mypassword123!')
fallback_args  = dict(
    ldapuri = os.getenv('LDAP_URI','ldap://{{domain_name}}'),
    user = os.getenv('{{LDAP_USER','{{svc_winaccountoupath}}}}'),
    password = os.getenv('LDAP_PASS','{{svc_password}}'),
)

class AnsibleInventoryLDAP(object):

    def __init__(self):
        # Create skeleton dict for inventory
        #    '_meta': {
        #        'hostvars': {
        #            'hostA': [ 'hostvarA': 'foo', 'hostvarB': 'bar' ],
        #            'hostB': [ 'hostvarA': 'foo', 'hostvarB': 'bar' ]
        #        }
        #    }
        self.ansible_inventory = { '_meta': { 'hostvars': { } } }

        # Parse arguments passed at cli
        self.parse_arguments()
  
        # Auth against ldap
        self.ldap_auth()
        
        # Get search results with provided options
        if self.args.os != False:
            ldapfilter = "(&(sAMAccountType=805306369)(operatingSystem=%s))" % (self.args.os)
        else:
            ldapfilter = "(sAMAccountType=805306369)"
 
        self.ldap_search(ldapfilter)

        self.build_hierarchy()
        print json.dumps(self.ansible_inventory, indent=2, encoding='iso-8859-9')


    def ldap_auth(self):
        """Authenticate to LDAP."""
        try:
            ldapobj = ldap.initialize(self.args.ldapuri)
            ldapobj.set_option(
                    ldap.OPT_REFERRALS,
                    ldap.OPT_OFF)
            ldapobj.bind_s(self.args.user,self.args.password)
            self.ldapobj = ldapobj
        except Exception as ex:
            print 'Could not successfully authenticate to LDAP.'
            print ex.__class__.__name__
            sys.exit(1)
    

    def ldap_search(self, ldapfilter):
        """Search LDAP in given OU."""
        # Determine the scope value
        if self.args.recursive:
            scope = ldap.SCOPE_SUBTREE
        else:
            scope = ldap.SCOPE_ONELEVEL
    
        # Search ldap for results
        try:
            self.searchresult = self.ldapobj.search_s(self.args.basedn, scope, ldapfilter)
        except ldap.REFERRAL as ex:
            print >> sys.stderr, "Error: LDAP referral received. Is the basedn correct?"
            sys.exit(1)
        except ldap.INVALID_CREDENTIALS:
            print >> sys.stderr, "Error: Invalid credentials"
            sys.exit(1)
        except Exception as ex:
            print ex.__class__.__name__
        finally:
            self.ldapobj.unbind_s()


    def add_inventory_entry(self, host=None, group_name=None, child_group=None, hostvars=None):
        # Example output:
        # {
        #    'groupnameA': {
        #        'hosts': [ 'hostA', 'hostB', 'hostC' ],
        #        'vars': { 'groupvarA': 'foo', 'groupvarB': 'bar' },
        #        'children': [ 'childgroupA', 'childgroupB' ]
        #     },
        #    '_meta': {
        #        'hostvars': {
        #            'hostA': [ 'hostvarA': 'foo', 'hostvarB': 'bar' ],
        #            'hostB': [ 'hostvarA': 'foo', 'hostvarB': 'bar' ]
        #        }
        #    }
        # }
       
        # Force the group name to lowercase
        group_name = group_name.lower()

        # Append the --group-prefix value if one is specified
        if self.args.group_prefix != False:
            group_name = self.args.group_prefix + group_name

        # If the group doesn't exist, then create it 
        if group_name not in self.ansible_inventory.keys():
            self.ansible_inventory[group_name] = { 'hosts': [], 'vars': { }, 'children': [] }

        # Add the 'children' value if --no-children wasn't specified
        if child_group != None and not self.args.no_children:
            child_group = child_group.lower()
            if self.args.group_prefix != False:
                child_group = self.args.group_prefix + child_group

            if child_group not in self.ansible_inventory[group_name]['children']:
                self.ansible_inventory[group_name]['children'].append(child_group)

        # Add the host if a host was passed
        if host != None:
            # The host should never get added twice anyway, but we'll add this as a safeguard
            if host not in self.ansible_inventory[group_name]['hosts']:
                self.ansible_inventory[group_name]['hosts'].append(host)

            # And add the hostvars for the host to the _meta dict
            if hostvars != None:
                self.ansible_inventory['_meta']['hostvars'][host] = hostvars


    def build_hierarchy(self):
        """We want to build the hierarchy of OUs and child OUs by traversing the ldap tree via.
           the host's distinguished name and linking each sub-OU as a 'child'."""

        # We are not interested in every last OU back to the domain name, instead we want to go
        # back to the 'basedn' that we searched in originally. 
        #
        # So, if the basedn that we searched in is:
        #   OU=Member servers, OU=North-East Branch, DC=Contoso, DC=Local
        # and the DN of our host is:
        #   CN=INT-IIS01, OU=Internal, OU=Webservers, OU=Member servers, OU=North-east Branch, DC=Contoso, DC=Local
        # then we only want up until the ROOT OU of the basedn ('OU=Member servers').
        #   CN=INT-IIS01, OU=Internal, OU=Webservers, OU=Member servers
        searchresult = self.searchresult

        basedn = self.args.basedn
        basedn_list = basedn.replace(' ','_').replace('CN=','').replace('OU=','').replace('DC=','').split(',')

        for dn,attrs in searchresult:
            # Collect information about the host
            hostvars = {}
            hostvars['name'] = attrs['dNSHostName'][0]
            hostvars['cn'] = attrs['cn'][0]
            hostvars['dn'] = attrs['distinguishedName'][0]
            try:
                hostvars['osname'] = attrs['operatingSystem'][0]
            except:
                pass
            try:
                hostvars['osversion'] = attrs['operatingSystemVersion'][0]
            except:
                pass
            # Do we want fqdn or just the basic hostname
            if self.args.fqdn == True:
                hostvars['inventory_name'] = hostvars['name']
            else:
                hostvars['inventory_name'] = hostvars['cn']

            #
            # TODO: Cut out the loop and statically add on the root OU of basedn to see if it improves
            #       inventory parsing speed in Ansible?
            #

            # Now, build the hierarchy of groups building up to the host (Parent OUs)
            dn_list = dn.replace(' ','_').replace('CN=','').replace('OU=','').replace('DC=','').split(',')
            # Remove the hostname from the list as we add this at the end, separately.
            del dn_list[0]

            # Delete each extra entry in the list until we hit the root OU of our basedn
            for count in range(0, (len(basedn_list)-1)):
                del dn_list[-1]

            # Flip reverse it
            dn_list.reverse()
            # Now we should have:
            # [ 'Member servers', 'Webservers', 'Internal' ]

            # Loop through each entry in the list and make the next item in the list a child of
            # the current item. If its the last item in the list, the next item should be the host instead.
            counter_range = range(0,(len(dn_list)))
            for group_counter in counter_range:
                if group_counter == counter_range[-1]:
                    self.add_inventory_entry(group_name=dn_list[group_counter], host=hostvars['inventory_name'], hostvars=hostvars)
                else:
                    self.add_inventory_entry(group_name=dn_list[group_counter], child_group=dn_list[group_counter+1])


    def parse_arguments(self):
        parser = argparse.ArgumentParser(description='Populate ansible inventory from LDAP.')
    
        parser.add_argument('basedn', help='DN of the OU to search in.') # Required
        parser.add_argument('--user', '-u', help='DN of user to authenticate as.', default=fallback_args['user'])
        parser.add_argument('--password','-p', help='Password of user to authenticate as.', default=fallback_args['password'])
        parser.add_argument('--ldapuri', help='URI of the LDAP server (ldap://dc01.mydomain.local).', default=fallback_args['ldapuri'])
        parser.add_argument('--recursive','-r', help='Recursively search into sub-OUs', default=False, action='store_true')
        parser.add_argument('--no-children','-c', help='Don\t link child OUs as children in the inventory (Stops inheritance).', default=False, action='store_true')
        parser.add_argument('--fqdn', help='Output the hosts FQDN, not just host name', default=False, action='store_true')
        parser.add_argument('--os','-os', help='Only return hosts matching the OS specified (Uses ldap formatting, so \'*windows*\').', default=False)
        parser.add_argument('--group-prefix', help='Prefix all group names.', default=False)

        args_hostlist = parser.add_mutually_exclusive_group()
        args_hostlist.add_argument('--list', help='List all nodes from specified OU.', action='store_true')
        args_hostlist.add_argument('--host', help='Not implemented.')
    
        self.args = parser.parse_args()
  
if __name__ == '__main__':
    # Instantiate the inventory object
    AnsibleInventoryLDAP()
