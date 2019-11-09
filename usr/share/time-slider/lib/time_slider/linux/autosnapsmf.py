#!/usr/bin/python2
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

import time_slider.autosnapsmf as base
from . import smf
from .timesliderconfig import Config

SNAPLABELPREFIX = base.SNAPLABELPREFIX

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
    for s in base.factoryDefaultSchedules:
        instanceName = "%s:%s" % (base.BASESVC,s)
        config = Config()
        result = config.get(instanceName[5:], "state")
        #
        # Note that the schedules, being dependent on the time-slider service
        # itself will typically be in an offline state when enabled. They will
        # transition to an "online" state once time-slider itself comes
        # "online" to satisfy it's dependency
        if result == "online" or result == "offline" or result == "degraded":
            instance = AutoSnap(s)
            try:
                _defaultSchedules.append(instance.get_schedule_details())
            except RuntimeError as message:
                raise RuntimeError("Error getting schedule details for " + \
                                    "default auto-snapshot SMF instance:" + \
                                    "\n\t" + instanceName + "\nDetails:\n" + \
                                    str(message))
    return _defaultSchedules


def get_custom_schedules():
    """
    Finds custom schedules ie. not the factory default
    'monthly', 'weekly', 'hourly', 'daily' and 'frequent' schedules
    """
    _customSchedules = []
    config = Config()
    for section in config.sections():
        if section.startswith(base.BASESVC[5:]):
            frmi = section.rsplit(":", 1)
            label = frmi[1]
            state = config.get(section, "state")

            if label not in base.factoryDefaultSchedules:
            # Note that the schedules, being dependent on the time-slider service
            # itself will typically be in an offline state when enabled. They will
            # transition to an "online" state once time-slider itself comes
            # "online" to satisfy it's dependency
                if state == "online" or state == "offline" or state == "degraded":
                    instance = AutoSnap(label)
                    try:
                        _customSchedules.append(instance.get_schedule_details())
                    except RuntimeError as message:
                        raise RuntimeError("Error getting schedule details " + \
                                            "for custom auto-snapshot SMF " + \
                                            "instance:\n\t" + label + "\n" + \
                                            "Details:\n" + str(message))
    return _customSchedules

class AutoSnap(base.AutoSnap):

    def __init__(self, schedule):
        base.AutoSnap.__init__(self, schedule)

#
# This is beyond ugly.
#
# The problem this is trying to solve is to change the inheritance chain. Origially
# it looks like this:
#
# <class 'time_slider.linux.autosnapsmf.AutoSnap'>
# <class 'time_slider.autosnapsmf.AutoSnap'>
# <class 'time_slider.smf.SMFInstance'>
# <type 'exceptions.Exception'>
# <type 'exceptions.BaseException'>
# <type 'object'>
#
# We'd like it to look like this:
#
# <class 'time_slider.linux.autosnapsmf.AutoSnap'>
# <class 'time_slider.autosnapsmf.AutoSnap'>
# <class 'time_slider.linux.smf.SMFInstance'>
# <class 'time_slider.smf.SMFInstance'>
# <type 'exceptions.Exception'>
# <type 'exceptions.BaseException'>
# <type 'object'>
#
# so we can inject some linux specific things into SMF without having to copy all
# the code.
#
# This has to be done here as the __init__ of AutoSnap will otherwise fail.
#

base.AutoSnap.__bases__ = (smf.SMFInstance,)

if __name__ == "__main__":
    defaults = get_default_schedules()
    for sched in defaults:
        S = AutoSnap(sched[0])
        print(S.get_schedule_details())
