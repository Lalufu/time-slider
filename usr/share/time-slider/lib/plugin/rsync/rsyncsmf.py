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
#from string import letters, digits
from plugin import pluginsmf

RSYNCPROPGROUP = "rsync"
RSYNCDIRPREFIX = "TIMESLIDER"
RSYNCDIRSUFFIX = ".time-slider/rsync"
RSYNCPARTIALSUFFIX = ".time-slider/.rsync-partial"
RSYNCTRASHSUFFIX = ".time-slider/.trash"
RSYNCLOCKSUFFIX = ".time-slider/.rsync-lock"
RSYNCLOGSUFFIX = ".time-slider/.rsync-log"
RSYNCCONFIGFILE = ".rsync-config"
RSYNCFSTAG = "org.opensolaris:time-slider-rsync"

class RsyncSMF(pluginsmf.PluginSMF):

    def __init__(self, instanceName):
        pluginsmf.PluginSMF.__init__(self, instanceName)
        self._archivedSchedules = None

    def get_cleanup_threshold(self):
        result = self.get_prop(RSYNCPROPGROUP, "cleanup_threshold").strip()
        return int(result)

    def get_target_dir(self):
        result = self.get_prop(RSYNCPROPGROUP, "target_dir").strip()
        # Strip out '\' characters inserted by svcprop
        return result.strip().replace('\\', '')

    def get_target_key(self):
        return self.get_prop(RSYNCPROPGROUP, "target_key").strip()

    def set_target_dir(self, path):
        self.set_string_prop(RSYNCPROPGROUP, "target_dir", path)

    def set_target_key(self, key):
        self.set_string_prop(RSYNCPROPGROUP, "target_key", key)

    def get_archived_schedules(self):
        #FIXME Use mutex locking to make MT-safe
        if self._archivedSchedules == None:
            self._archivedSchedules = []
            value = self.get_prop(RSYNCPROPGROUP, "archived_schedules")
            
            # Strip out '\' characters inserted by svcprop
            archiveList = value.strip().replace('\\', '').split(',')
            for schedule in archiveList:
                self._archivedSchedules.append(schedule.strip())
        return self._archivedSchedules

    def get_rsync_verbose(self):
        value = self.get_prop(RSYNCPROPGROUP, "verbose")
        if value == "true":
            return True
        else:
            return False

    def __str__(self):
        ret = "SMF Instance:\n" +\
              "\tName:\t\t\t%s\n" % (self.instance_name) +\
              "\tState:\t\t\t%s\n" % (self.svcstate) + \
              "\tTriggers:\t\t%s\n" % str(self.get_triggers()) + \
              "\tTarget Dir:\t%s\n" % self.get_target_dir() + \
              "\tVerbose:\t\t\'%s\'" % str((self.get_verbose()))
        return ret

