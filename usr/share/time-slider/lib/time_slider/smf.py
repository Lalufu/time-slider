#!/usr/bin/python2.6
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

import subprocess
import threading
import util

#SMF EXIT CODES
SMF_EXIT_OK          = 0
SMF_EXIT_ERR_FATAL   = 95
SMF_EXIT_ERR_CONFIG  = 96
SMF_EXIT_MON_DEGRADE = 97
SMF_EXIT_MON_OFFLINE = 98
SMF_EXIT_ERR_NOSMF   = 99
SMF_EXIT_ERR_PERM    = 100
#SMF_EXIT_ERR_OTHER = non-zero


# Commonly used command paths
PFCMD = "/usr/bin/pfexec"
SVCSCMD = "/usr/bin/svcs"
SVCADMCMD = "/usr/sbin/svcadm"
SVCCFGCMD = "/usr/sbin/svccfg"
SVCPROPCMD = "/usr/bin/svcprop"


class SMFInstance(Exception):

    def __init__(self, instanceName):
        self.instanceName = instanceName
        self.svcstate = self.get_service_state()
        self.svcdeps = self.get_service_dependencies()


    def get_service_dependencies(self):
        cmd = [SVCSCMD, "-H", "-o", "fmri", "-d", self.instanceName]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip().split("\n")
        return result

    def get_verbose(self):
        cmd = [SVCPROPCMD, "-c", "-p", \
               DAEMONPROPGROUP + '/' + "verbose", \
               self.instanceName]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip()
        if result == "true":
            return True
        else:
            return False

    def find_dependency_errors(self):
        errors = []
        #FIXME - do this in one pass.
        for dep in self.svcdeps:
            cmd = [SVCSCMD, "-H", "-o", "state", dep]
            outdata,errdata = util.run_command(cmd)
            result = outdata.rstrip()
            if result != "online":
                errors.append("%s\t%s" % (result, dep))
        return errors

    def get_service_state(self):
        cmd = [SVCSCMD, "-H", "-o", "state", self.instanceName]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip()
        return result

    def get_prop(self, propgroup, propname):
        cmd = [SVCPROPCMD, "-c", "-p", \
               propgroup + '/' + propname,\
               self.instanceName]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip()

        return result

    def set_prop(self, propgroup, propname, proptype, value):
        cmd = [PFCMD, SVCCFGCMD, "-s", self.instanceName, "setprop", \
               propgroup + '/' + propname, "=", proptype + ":", \
               value]
        util.run_command(cmd)
        self.refresh_service()

    def set_string_prop(self, propgroup, propname, value):
        cmd = [PFCMD, SVCCFGCMD, "-s", self.instanceName, "setprop", \
               propgroup + '/' + propname, "=", "astring:",
               "\"%s\"" % (value)]
        util.run_command(cmd)
        self.refresh_service()

    def set_boolean_prop(self, propgroup, propname, value):
        if value == True:
            strval = "true"
        else:
            strval = "false"
        self.set_prop(propgroup, propname, "boolean", strval)

    def set_integer_prop(self, propgroup, propname, value):
        self.set_prop(propgroup, propname, "integer", str(value))

    def refresh_service(self):
        cmd = [PFCMD, SVCADMCMD, "refresh", self.instanceName]
        p = subprocess.Popen(cmd, close_fds=True)

    def disable_service (self):
        if self.svcstate == "disabled":
            return
        cmd = [PFCMD, SVCADMCMD, "disable", self.instanceName]
        p = subprocess.Popen(cmd, close_fds=True)
        self.svcstate = self.get_service_state()

    def enable_service (self):
        if (self.svcstate == "online" or self.svcstate == "degraded"):
            return
        cmd = [PFCMD, SVCADMCMD, "enable", self.instanceName]
        p = subprocess.Popen(cmd, close_fds=True)
        self.svcstate = self.get_service_state()

    def mark_maintenance (self):
        cmd = [SVCADMCMD, "mark", "maintenance", self.instanceName]
        subprocess.Popen(cmd, close_fds=True)

    def __str__(self):
        ret = "SMF Instance:\n" +\
              "\tName:\t\t\t%s\n" % (self.instanceName) +\
              "\tState:\t\t\t%s\n" % (self.svcstate)
        return ret


if __name__ == "__main__":
  S = SMFInstance('svc:/application/time-slider')
  print S

