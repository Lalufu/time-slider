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


import dbus
import dbus.service
import dbus.mainloop
import dbus.mainloop.glib


class AutoSnap(dbus.service.Object):
    """
    D-Bus object for Time Slider's auto snapshot features.
    """
    def __init__(self, bus, path, snapshotmanager):
        self.snapshotmanager = snapshotmanager
        self._bus = bus
        dbus.service.Object.__init__(self,
                                     bus,
                                     path)

    # Remedial cleanup signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.autosnap",
                         signature='suu')
    def capacity_exceeded(self, pool, severity, threshhold):
        pass

class RsyncBackup(dbus.service.Object):
    """
    D-Bus object for Time Slider's rsync backup feature.
    """
    def __init__(self, bus, path):
        self._bus = bus
        dbus.service.Object.__init__(self, 
                                     bus,  
                                     path)

    # Rsync operation rsync_started signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.plugin.rsync",
                         signature='s')
    def rsync_started(self, target):
        pass

    # Rsync operation rsync_current signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.plugin.rsync",
                         signature='su')
    def rsync_current(self, snapshot, remaining):
        pass

    # Rsync operation rsync_complete signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.plugin.rsync",
                         signature='s')
    def rsync_complete(self, target):
        pass

    # Rsync operation rsync_synced signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.plugin.rsync",
                         signature='')
    def rsync_synced(self):
        pass

    # Rsync operation rsync_unsynced signal
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.plugin.rsync",
                         signature='u')
    def rsync_unsynced(self, queueSize):
        pass


class Config(dbus.service.Object):
    """
    D-Bus object representing Time Slider service configuration changes.
    """
    def __init__(self, bus, path):
        self._bus = bus
        dbus.service.Object.__init__(self, 
                                        bus,  
                                        path)
    # Service configuration change signal. Nothing fancy for now. 
    # Listeners need to figure out what changed for themselves.
    @dbus.service.signal(dbus_interface="org.opensolaris.TimeSlider.config",
                         signature='')
    def config_changed(self):
        pass

