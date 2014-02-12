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
import smf
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

cleanupTypes = ("warning", "critical", "emergency")

SMFNAME = 'svc:/application/time-slider'
ZFSPROPGROUP = "zfs"
ZPOOLPROPGROUP = "zpool"
DAEMONPROPGROUP = "daemon"

# Commonly used command paths
PFCMD = "/usr/bin/pfexec"
SVCSCMD = "/usr/bin/svcs"
SVCADMCMD = "/usr/sbin/svcadm"
SVCCFGCMD = "/usr/sbin/svccfg"
SVCPROPCMD = "/usr/bin/svcprop"


class TimeSliderSMF(smf.SMFInstance):

    def __init__(self, instanceName = SMFNAME):
        smf.SMFInstance.__init__(self, instanceName)
        self._cleanupLevels = {}
        self._cleanupLevelsLock = threading.Lock()

    def get_keep_empties(self):
        if self.get_prop(ZFSPROPGROUP, "keep-empties") == "true":
            return True
        else:
            return False

    def is_custom_selection(self):
        value = self.get_prop(ZFSPROPGROUP, "custom-selection")
        if value == "true":
            return True
        else:
            return False

    def get_separator(self):
        result = self.get_prop(ZFSPROPGROUP, "sep")
        if len(result) != 1:
            raise ValueError("zfs/sep must be a single character length")
        return result

    def get_remedial_cleanup(self):
        value = self.get_prop(ZPOOLPROPGROUP, "remedial-cleanup")
        if value == "false":
            return False
        else:
            return True

    def get_cleanup_level(self, cleanupType):
        if cleanupType not in cleanupTypes:
            raise ValueError("\'%s\' is not a valid cleanup type" % \
                           (cleanupType))
        self._cleanupLevelsLock.acquire()
        value = self.get_prop(ZPOOLPROPGROUP, "%s-level" % (cleanupType))
        self._cleanupLevelsLock.release()
        return int(value)

    def set_cleanup_level(self, cleanupType, level):
        if cleanupType not in cleanupTypes:
            raise ValueError("\'%s\' is not a valid cleanup type" % \
                           (cleanupType))
        if level < 0:
            raise ValueError("Cleanup level value can not not be negative")
        if cleanupType == "warning" and \
            level > self.get_cleanup_level("critical"):
            raise ValueError("Warning cleanup level value can not exceed " + \
                             "critical cleanup level value")
        elif cleanupType == "critical" and \
            level > self.get_cleanup_level("emergency"):
            raise ValueError("Critical cleanup level value can not " + \
                             "exceed emergency cleanup level value")
        elif level > 100: # Emergency type value
            raise ValueError("Cleanup level value can not exceed 100")

        self._cleanupLevelsLock.acquire()
        propname = "%s-level" % (cleanupType)
        self.set_integer_prop(ZPOOLPROPGROUP, propname, level)
        self._cleanupLevels[cleanupType] = level
        self._cleanupLevelsLock.release()
        self.refresh_service()

    def set_custom_selection(self, value):
        self.set_boolean_prop(ZFSPROPGROUP, "custom-selection", value)
        self.refresh_service()

    def get_verbose(self):
        value = self.get_prop(DAEMONPROPGROUP, "verbose")
        if value == "true":
            return True
        else:
            return False

    def __eq__(self, other):
        if self.fs_name == other.fs_name and \
           self.interval == other.interval and \
           self.period == other.period:
            return True
        return False
	
    def __str__(self):
        ret = "SMF Instance:\n" +\
              "\tName:\t\t\t%s\n" % (self.instanceName) +\
              "\tState:\t\t\t%s\n" % (self.svcstate) + \
              "\tVerbose:\t\t%s\n" % str(self.get_verbose()) + \
              "\tCustom Selction:\t%s\n" % str(self.is_custom_selection()) +\
              "\tKeep Empties:\t\t%s\n" % str(self.get_keep_empties()) +\
              "\tWarning Level:\t\t%d\n" % (self.get_cleanup_level("warning")) + \
              "\tCritical Level:\t\t%d\n" % (self.get_cleanup_level("critical")) + \
              "\tEmergency Level:\t%d\n" % (self.get_cleanup_level("emergency")) + \
              "\tSeparator Char:\t\t\'%s\'" % (self.get_separator())
        return ret


if __name__ == "__main__":
  S = TimeSliderSMF('svc:/application/time-slider')
  print S

