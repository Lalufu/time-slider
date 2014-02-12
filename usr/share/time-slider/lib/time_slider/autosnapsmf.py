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

import threading
import smf
import util

factoryDefaultSchedules = ("monthly", "weekly", "daily", "hourly", "frequent")

BASESVC= "svc:/system/filesystem/zfs/auto-snapshot"
SNAPLABELPREFIX = "zfs-auto-snap"
ZFSPROPGROUP = "zfs"


# Bombarding the class with schedule queries causes the occasional
# OSError exception due to interrupted system calls.
# Serialising them helps prevent this unlikely event from occuring.
_scheddetaillock = threading.RLock()

class AutoSnap(smf.SMFInstance):

    def __init__(self, schedule):
        smf.SMFInstance.__init__(self, "%s:%s" % (BASESVC, schedule))
        self.schedule = schedule

    def get_schedule_details(self):
        svc= "%s:%s" % (BASESVC, self.schedule)
        _scheddetaillock.acquire()
        try:
            interval = self.get_prop(ZFSPROPGROUP, "interval")
            period = int(self.get_prop(ZFSPROPGROUP, "period"))
            keep =  int(self.get_prop(ZFSPROPGROUP, "keep"))

        except OSError, message:
            raise RuntimeError, "%s subprocess error:\n %s" % \
                                (cmd, str(message))
        finally:
            _scheddetaillock.release()
      
        return [self.schedule, interval, period, keep]

# FIXME - merge with enable_default_schedules()
def disable_default_schedules():
    """
    Disables the default auto-snapshot SMF instances corresponding
    to: "frequent", "hourly", "daily", "weekly" and "monthly"
    schedules
    Raises RuntimeError exception if unsuccessful
    """

    for s in factoryDefaultSchedules:
        # Acquire the scheddetail lock since their status will
        # likely be changed as a result of enabling the instances.
        _scheddetaillock.acquire()
        instanceName = "%s:%s" % (BASESVC,s)
        svc = smf.SMFInstance(instanceName)
        svc.disable_service()
        _scheddetaillock.release()

def enable_default_schedules():
    """
    Enables the default auto-snapshot SMF instances corresponding
    to: "frequent", "hourly", "daily", "weekly" and "monthly"
    schedules
    Raises RuntimeError exception if unsuccessful
    """
    for s in factoryDefaultSchedules:
        # Acquire the scheddetail lock since their status will
        # likely be changed as a result of enabling the instances.
        _scheddetaillock.acquire()
        instanceName = "%s:%s" % (BASESVC,s)
        svc = smf.SMFInstance(instanceName)
        svc.enable_service()
        _scheddetaillock.release()

def get_default_schedules():
    """
    Finds the default schedules that are enabled (online, offline or degraded)
    """
    #This is not the fastest method but it is the safest, we need
    #to ensure that default schedules are processed in the pre-defined
    #order to ensure that the overlap between them is adhered to
    #correctly. monthly->weekly->daily->hourly->frequent. They have
    #to be processed first and they HAVE to be in the correct order.
    _defaultSchedules = []
    for s in factoryDefaultSchedules:
        instanceName = "%s:%s" % (BASESVC,s)
        cmd = [smf.SVCSCMD, "-H", "-o", "state", instanceName]
        _scheddetaillock.acquire()
        try:
            outdata,errdata = util.run_command(cmd)
        finally:
            _scheddetaillock.release()
        result = outdata.rstrip()
        # Note that the schedules, being dependent on the time-slider service
        # itself will typically be in an offline state when enabled. They will
        # transition to an "online" state once time-slider itself comes
        # "online" to satisfy it's dependency
        if result == "online" or result == "offline" or result == "degraded":
            instance = AutoSnap(s)
            try:
                _defaultSchedules.append(instance.get_schedule_details())
            except RuntimeError, message:
                raise RuntimeError, "Error getting schedule details for " + \
                                    "default auto-snapshot SMF instance:" + \
                                    "\n\t" + instanceName + "\nDetails:\n" + \
                                    str(message)
    return _defaultSchedules

def get_custom_schedules():
    """
    Finds custom schedules ie. not the factory default
    'monthly', 'weekly', 'hourly', 'daily' and 'frequent' schedules
    """
    _customSchedules = []
    cmd = [smf.SVCSCMD, "-H", "-o", "state,FMRI", BASESVC]
    _scheddetaillock.acquire()
    try:
        outdata,errdata = util.run_command(cmd)
    finally:
        _scheddetaillock.release()

    for line in outdata.rstrip().split('\n'):
        line = line.rstrip().split()
        state = line[0]
        fmri = line[1]
        fmri = fmri.rsplit(":", 1)
        label = fmri[1]
        if label not in factoryDefaultSchedules:
        # Note that the schedules, being dependent on the time-slider service
        # itself will typically be in an offline state when enabled. They will
        # transition to an "online" state once time-slider itself comes
        # "online" to satisfy it's dependency
            if state == "online" or state == "offline" or state == "degraded":
                instance = AutoSnap(label)
                try:
                    _customSchedules.append(instance.get_schedule_details())
                except RuntimeError, message:
                    raise RuntimeError, "Error getting schedule details " + \
                                        "for custom auto-snapshot SMF " + \
                                        "instance:\n\t" + label + "\n" + \
                                        "Details:\n" + str(message) 
    return _customSchedules


if __name__ == "__main__":
    defaults = get_default_schedules()
    for sched in defaults:
        S = AutoSnap(sched[0])
        print S.get_schedule_details()

