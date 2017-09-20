#! /usr/bin/python
# _*_ coding: utf-8 _*_

#
# Copyright (c) 2017 Dell Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = """
---
module: dellemc_idrac_syslog
short_description: Configure remote system logging
version_added: "2.3"
description:
    - Configure remote system logging settings to remotely write RAC log and
      System Event Log (SEL) to an external server
options:
    idrac_ip:
        required: False
        description: iDRAC IPv4 Address
        default: None
    idrac_user:
        required: False
        description: iDRAC user name
        default: None
    idrac_pwd:
        required: False
        description: iDRAC user password
        default: None
    idrac_port:
        required: False
        description: iDRAC port
        default: None
    Servers:
        required: False
        description: List of IP Addresses of the Remote Syslog Servers
        default: None
    SyslogPort:
        required: False
        description: Port number of remote server
        default: '514'
    state:
        description:
        - if C(present), will enable the remote syslog option and add the
          remote servers
        - if C(absent), will disable the remote syslog option

requirements: ['omsdk']
author: "anupam.aloke@dell.com"
"""

EXAMPLES = """
---
- name: Configure Remote Syslog
    dellemc_idrac_syslog:
       idrac_ip:       "192.168.1.1"
       idrac_user:     "root"
       idrac_pwd:      "calvin"
       share_name:     "\\\\192.168.10.10\\share"
       share_user:     "user1"
       share_pwd:      "password"
       share_mnt:      "/mnt/share"
       syslog_servers: ["192.168.20.1", ""192.168.20.2", ""192.168.20.3"]
       Syslog_port:    "514"
       state:          "present"
"""

RETURNS = """
---
"""

from ansible.module_utils.dellemc_idrac import *
from ansible.module_utils.basic import AnsibleModule

def _setup_idrac_nw_share (idrac, module):
    """
    Setup local mount point for network file share

    idrac -- iDRAC handle
    module -- Ansible module
    """

    myshare = FileOnShare(module.params['share_name'],
                          module.params['share_mnt'],
                          isFolder=True)

    myshare.addcreds(UserCredentials(module.params['share_user'],
                                    module.params['share_pwd']))

    return idrac.config_mgr.set_liason_share(myshare)

def _syslog_exists (idrac, module):
    """
    Check whether syslog settings already exists on iDRAC

    Keyword arguments:
    idrac  -- iDRAC handle
    module -- Ansible module
    """

    old_syslog_config = idrac.config_mgr.SyslogConfig

    if old_syslog_config['SyslogEnable'] != 'Enabled':
        return False

    elif old_syslog_config['SyslogPort'] != module.params['syslog_port']:
        return False

    elif 'syslog_servers' in module.params:
        if set(old_syslog_config['Servers']) != set(module.params['syslog_servers']):
            return False

    return True

def setup_idrac_syslog (idrac, module):
    """
    Setup iDRAC remote syslog settings

    idrac  -- iDRAC handle
    module -- Ansible module
    """

    msg = {}
    msg['changed'] = False
    msg['failed'] = False
    msg['msg'] = {}
    err = False
    MAX_SYSLOG_SRV = 3

    try:
        # Check first whether local mount point for network share is setup
        if idrac.config_mgr.liason_share is None:
            if not  _setup_idrac_nw_share (idrac, module):
                msg['msg'] = "Failed to setup local mount point for network share"
                msg['failed'] = True
                return msg

        # Check if Syslog configuration settings already exists
        exists = _syslog_exists(idrac, module)

        if module.params["state"] == "present":
            if module.check_mode or exists:
                msg['changed'] = not exists
            else:
                syslog_servers = []

                if 'syslog_servers' in module.params:
                    syslog_servers = module.params['syslog_servers']
                
                syslog_servers.extend(["","",""])
                
                msg['msg'] = idrac.config_mgr.enable_syslog (
                                            module.params["syslog_port"],
                                            0,
                                            syslog_servers[0],
                                            syslog_servers[1],
                                            syslog_servers[2])
        else:
            if module.check_mode or not exists:
                msg['changed'] = exists
            else:
                msg['msg'] = idrac.config_mgr.disable_syslog()

        if "Status" in msg['msg']:
            if msg['msg']["Status"] == "Success":
                msg['changed'] = True
            else:
                msg['failed'] = True

    except Exception as e:
        err = True
        msg['msg'] = "Error: %s" % str(e)
        msg['failed'] = True

    return msg, err

# Main
def main():

    module = AnsibleModule (
            argument_spec = dict (

                # iDRAC handle
                idrac = dict (required = False, type = 'dict'),

                # iDRAC Credentials
                idrac_ip   = dict (required = False, default = None, type = 'str'),
                idrac_user = dict (required = False, default = None, type = 'str'),
                idrac_pwd  = dict (required = False, default = None,
                                    type = 'str', no_log = True),
                idrac_port = dict (required = False, default = None, type = 'int'),

                # Network File Share
                share_name = dict (required = True, type = 'str'),
                share_user = dict (required = True, type = 'str'),
                share_pwd  = dict (required = True, type = 'str', no_log = True),
                share_mnt  = dict (required = True, type = 'str'),

                # Remote Syslog parameters
                syslog_servers = dict (required = False, default = None, type = 'list'),
                syslog_port = dict (required = False, default = '514', type = 'str'),
                state = dict (required = False,
                              choices = ['present', 'absent'],
                              default = 'present')
                ),
            supports_check_mode = True)

    # Connect to iDRAC
    idrac_conn = iDRACConnection (module)
    idrac = idrac_conn.connect()

    (msg, err) = setup_idrac_syslog (idrac, module)

    # Disconnect from iDRAC
    idrac_conn.disconnect()

    if err:
        module.fail_json(**msg)
    module.exit_json(**msg)


if __name__ == '__main__':
    main()