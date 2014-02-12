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

import sys
import os
import subprocess
import re
import threading
import getopt
import syslog
import time
import datetime
import calendar
import signal

import glib
import gobject
import dbus
import dbus.service
import dbus.mainloop
import dbus.mainloop.glib

import dbussvc
import zfs
import smf
import timeslidersmf
import autosnapsmf
import plugin
from rbac import RBACprofile
import util

_MINUTE = 60
_HOUR = _MINUTE * 60
_DAY = _HOUR * 24
_WEEK = _DAY * 7


# Status codes for actual zpool capacity levels.
# These are relative to the SMF property defined
# levels for: user, warning and emergenecy levels
STATUS_OK = 0 # Below user specified threshhold. Everything was OK
STATUS_WARNING = 1 # Above specified user threshold level
STATUS_CRITICAL = 2 # Above specified critical threshhold level
STATUS_EMERGENCY = 3 # Above specified emergency threshhold level

intervals = {"weeks" : _WEEK, "days" : _DAY, "hours" : _HOUR, "minutes" : _MINUTE}


class SnapshotManager(threading.Thread):

    def __init__(self, bus):
        # Used to wake up the run() method prematurely in the event
        # of a SIGHUP/SMF refresh
        self._conditionLock = threading.Condition(threading.RLock())
        # Used when schedules are being rebuilt or examined.
        self._refreshLock = threading.Lock()
        # Indicates that cleanup is in progress when locked
        self._cleanupLock = threading.Lock()
        self._datasets = zfs.Datasets()
        # Indicates that schedules need to be rebuilt from scratch
        self._stale = True
        self._lastCleanupCheck = 0;
        self._zpools = []
        self._poolstatus = {}
        self._destroyedsnaps = []

        # This is also checked during the refresh() method but we need
        # to know it sooner for instantiation of the PluginManager
        self._smf = timeslidersmf.TimeSliderSMF()
        try:
            self.verbose = self._smf.get_verbose()
        except RuntimeError,message:
            sys.stderr.write("Error determing whether debugging is enabled\n")
            self.verbose = False

        self._dbus = dbussvc.AutoSnap(bus,
                                      '/org/opensolaris/TimeSlider/autosnap',
                                      self)

        self._plugin = plugin.PluginManager(self.verbose)
        self.exitCode = smf.SMF_EXIT_OK
        self.refresh()

        # Seems we're up and running OK. 
        # Signal our parent so we can daemonise
        os.kill(os.getppid(), signal.SIGUSR1)

        # SMF/svc.startd sends SIGHUP to force a
        # a refresh of the daemon
        signal.signal(signal.SIGHUP, self._signalled)

        # Init done. Now initiaslise threading.
        threading.Thread.__init__ (self)
        self.setDaemon(True)

    def run(self):
        # Deselect swap and dump volumes so they don't get snapshotted.
        for vol in self._datasets.list_volumes():
            name = vol.rsplit("/")
            try:
                if (name[1] == "swap" or name[1] == "dump"):
                    util.debug("Auto excluding %s volume" % vol, self.verbose)
                    volume = zfs.Volume(vol)
                    volume.set_auto_snap(False)
            except IndexError:
                pass
            
        nexttime = None
        waittime = None
        while True:
            try:
                self.refresh()
                # First check and, if necessary, perform any remedial cleanup.
                # This is best done before creating any new snapshots which may
                # otherwise get immediately gobbled up by the remedial cleanup.
                if self._needs_cleanup() == True:
                    self._perform_cleanup()
                    # Check to see if cleanup actually deleted anything before
                    # notifying the user. Avoids the popup appearing continuously
                    if len(self._destroyedsnaps) > 0:
                        self._send_notification()
                    self._send_to_syslog()

                nexttime = self._check_snapshots()
                # Overdue snapshots are already taken automatically
                # inside _check_snapshots() so nexttime should never be
                # < 0. It can be None however, which is fine since it 
                # will cause the scheduler thread to sleep indefinitely
                # or until a SIGHUP is caught.
                if nexttime:
                    util.debug("Waiting until " + str (nexttime), self.verbose)
                waittime = None
                if nexttime != None:
                    waittime = nexttime - long(time.time())
                    if (waittime <= 0):
                        # We took too long and missed a snapshot, so break out
                        # and catch up on it the next time through the loop
                        continue
                # waittime could be None if no auto-snap schedules are online
                self._conditionLock.acquire()
                if waittime:
                    util.debug("Waiting %d seconds" % (waittime), self.verbose)
                    self._conditionLock.wait(waittime)
                else: #None. Just wait a while to check for cleanups.
                    util.debug("No auto-snapshot schedules online.", \
                               self.verbose)
                    self._conditionLock.wait(_MINUTE * 15)

            except OSError, message:
                sys.stderr.write("Caught OSError exception in snapshot" +
                                 " manager thread\n")
                sys.stderr.write("Error details:\n" + \
                                 "--------BEGIN ERROR MESSAGE--------\n" + \
                                 str(message) + \
                                 "\n--------END ERROR MESSAGE--------\n")
                self.exitCode = smf.SMF_EXIT_ERR_FATAL
                # Exit this thread
                break
            except RuntimeError,message:
                sys.stderr.write("Caught RuntimeError exception in snapshot" +
                                 " manager thread\n")
                sys.stderr.write("Error details:\n" + \
                                 "--------BEGIN ERROR MESSAGE--------\n" + \
                                 str(message) + \
                                 "\n--------END ERROR MESSAGE--------\n")
                # Exit this thread
                break

    def _signalled(self, signum, frame):
        if signum == signal.SIGHUP:
            if self._refreshLock.acquire(False) == False:
                return
            self._stale = True
            self._refreshLock.release()
            self._conditionLock.acquire()
            self._conditionLock.notify()
            self._conditionLock.release()

    def refresh(self):
        """
        Checks if defined snapshot schedules are out
        of date and rebuilds and updates if necessary
        """
        self._refreshLock.acquire()
        if self._stale == True:
            self._configure_svc_props()
            self._rebuild_schedules()
            self._update_schedules()
            self._plugin.refresh()
            self._stale = False
        self._refreshLock.release()

    def _configure_svc_props(self):
        try:
            self.verbose = self._smf.get_verbose()
        except RuntimeError,message:
            sys.stderr.write("Error determing whether debugging is enabled\n")
            self.verbose = False

        try:
            cleanup = self._smf.get_remedial_cleanup()
            warn = self._smf.get_cleanup_level("warning")
            util.debug("Warning level value is:   %d%%" % warn, self.verbose)
            crit = self._smf.get_cleanup_level("critical")
            util.debug("Critical level value is:  %d%%" % crit, self.verbose)
            emer = self._smf.get_cleanup_level("emergency")
            util.debug("Emergency level value is: %d%%" % emer, self.verbose)
        except RuntimeError,message:
            sys.stderr.write("Failed to determine cleanup threshhold levels\n")
            sys.stderr.write("Details:\n" + \
                             "--------BEGIN ERROR MESSAGE--------\n" + \
                             str(message) + \
                             "\n---------END ERROR MESSAGE---------\n")
            sys.stderr.write("Using factory defaults of 80%, 90% and 95%\n")
            #Go with defaults
            #FIXME - this would be an appropriate case to mark svc as degraded
            self._remedialCleanup = True
            self._warningLevel = 80
            self._criticalLevel = 90
            self._emergencyLevel = 95
        else:
            self._remedialCleanup = cleanup
            self._warningLevel = warn
            self._criticalLevel = crit
            self._emergencyLevel = emer

        try:
            self._keepEmpties = self._smf.get_keep_empties()
        except RuntimeError,message:
            # Not fatal, just assume we delete them (default configuration)
            sys.stderr.write("Can't determine whether to keep empty snapshots\n")
            sys.stderr.write("Details:\n" + \
                             "--------BEGIN ERROR MESSAGE--------\n" + \
                             str(message) + \
                             "\n---------END ERROR MESSAGE---------\n")
            sys.stderr.write("Assuming default value: False\n")
            self._keepEmpties = False

        # Previously, snapshot labels used the ":" character was used as a 
        # separator character for datestamps. Windows filesystems such as
        # CIFS and FAT choke on this character so now we use a user definable
        # separator value, with a default value of "_"
        # We need to check for both the old and new format when looking for
        # snapshots.
        self._separator = self._smf.get_separator()
        self._prefix = "%s[:%s]" \
            % (autosnapsmf.SNAPLABELPREFIX, self._separator)

        # Rebuild pool list
        self._zpools = []
        try:
            for poolname in zfs.list_zpools():
                # Do not try to examine FAULTED pools
                zpool = zfs.ZPool(poolname)
                if zpool.health == "FAULTED":
                    util.debug("Ignoring faulted Zpool: %s\n" \
                               % (zpool.name), \
                               self.verbose)
                else:
                    self._zpools.append(zpool)
                util.debug(str(zpool), self.verbose)
        except RuntimeError,message:
            sys.stderr.write("Could not list Zpools\n")
            self.exitCode = smf.SMF_EXIT_ERR_FATAL
            # Propogate exception up to thread's run() method
            raise RuntimeError,message


    def _rebuild_schedules(self):
        """
        Builds 2 lists of default and custom auto-snapshot SMF instances
        """

        self._last = {}
        self._next = {}
        self._keep = {}

        try:
            _defaultSchedules = autosnapsmf.get_default_schedules()
            _customSchedules = autosnapsmf.get_custom_schedules()
        except RuntimeError,message:
            self.exitCode = smf.SMF_EXIT_ERR_FATAL
            raise RuntimeError, "Error reading SMF schedule instances\n" + \
                                "Details:\n" + str(message)
        else:
            # Now set it in stone.
            self._defaultSchedules = tuple(_defaultSchedules)
            self._customSchedules = tuple(_customSchedules)
            
            # Build the combined schedule tuple from default + custom schedules
            _defaultSchedules.extend(_customSchedules)
            self._allSchedules = tuple(_defaultSchedules)
            for schedule,i,p,keep in self._allSchedules:
                self._last[schedule] = 0
                self._next[schedule] = 0
                self._keep[schedule] = keep

    def _update_schedules(self):
        interval = 0
        idx = 1 # Used to index subsets for schedule overlap calculation
        last = None

        for schedule,interval,period,keep in self._allSchedules:
            # Shortcut if we've already processed this schedule and it's 
            # still up to date. Don't skip the default schedules though
            # because overlap affects their scheduling
            if [schedule,interval,period,keep] not in \
                self._defaultSchedules and \
                (self._next[schedule] > self._last[schedule]):
                util.debug("Short circuiting %s recalculation" \
                           % (schedule), \
                           self.verbose)
                continue

            # If we don't have an internal timestamp for the given schedule
            # ask zfs for the last snapshot and get it's creation timestamp.
            if self._last[schedule] == 0:
                try:
                    snaps = self._datasets.list_snapshots("%s%s" % \
                                                         (self._prefix,
                                                          schedule))
                except RuntimeError,message:
                    self.exitCode = smf.SMF_EXIT_ERR_FATAL
                    sys.stderr.write("Failed to list snapshots during schedule update\n")
                    #Propogate up to the thread's run() method
                    raise RuntimeError,message

                if len(snaps) > 0:
                    util.debug("Last %s snapshot was: %s" % \
                               (schedule, snaps[-1][0]), \
                               self.verbose)
                    self._last[schedule] = snaps[-1][1]

            last = self._last[schedule]
            if interval != "months": # months is non-constant. See below.
                util.debug("Recalculating %s schedule" % (schedule), \
                           self.verbose)
                try:
                    totalinterval = intervals[interval] * period
                except KeyError:
                    self.exitCode = smf.SMF_EXIT_ERR_CONFIG
                    sys.stderr.write(schedule + \
                                      " schedule has invalid interval: " + \
                                      "'%s\'\n" % interval)
                    #Propogate up to thread's run() method
                    raise RuntimeError
                if [schedule,interval,period,keep] in self._defaultSchedules:
                    # This is one of the default schedules so check for an
                    # overlap with one of the dominant shchedules.
                    for s,i,p,k in self._defaultSchedules[:idx]:
                        last = max(last, self._last[s])
                    idx += 1

            else: # interval == "months"
                if self._next[schedule] > last:
                    util.debug("Short circuiting " + \
                               schedule + \
                               " recalculation", \
                               self.verbose)
                    continue
                util.debug("Recalculating %s schedule" % (schedule), \
                           self.verbose)
                snap_tm = time.gmtime(self._last[schedule])
                # Increment year if period >= than 1 calender year.
                year = snap_tm.tm_year
                year += period / 12
                period = period % 12

                mon = (snap_tm.tm_mon + period) % 12
                # Result of 0 actually means december.
                if mon == 0:
                    mon = 12
                # Account for period that spans calendar year boundary.
                elif snap_tm.tm_mon + period > 12:
                    year += 1

                d,dlastmon = calendar.monthrange(snap_tm.tm_year, snap_tm.tm_mon)
                d,dnewmon = calendar.monthrange(year, mon)
                mday = snap_tm.tm_mday
                if dlastmon > dnewmon and snap_tm.tm_mday > dnewmon:
                   mday = dnewmon
                
                tm =(year, mon, mday, \
                    snap_tm.tm_hour, snap_tm.tm_min, snap_tm.tm_sec, \
                    0, 0, -1)
                newt = calendar.timegm(tm)
                new_tm = time.gmtime(newt)
                totalinterval = newt - self._last[schedule]

            self._next[schedule] = last + totalinterval

    def _next_due(self):
        schedule = None
        earliest = None
        now = long(time.time())
        
        for s,i,p,k in self._defaultSchedules:
            due = self._next[s]
            if due <= now:
                #Default Schedule - so break out at the first 
                #schedule that is overdue. The subordinate schedules
                #will re-adjust afterwards.
                earliest,schedule = due,s
                break
            elif earliest != None:
                if due < earliest:
                    earliest,schedule = due,s
            else: #FIXME better optimisation with above condition
                earliest,schedule = due,s
        for s,i,p,k in self._customSchedules:
            due = self._next[s]
            if earliest != None:
                if due < earliest:
                    earliest,schedule = due,s
            else: #FIXME better optimisation with above condition
                earliest,schedule = due,s
        return earliest,schedule

    def _check_snapshots(self):
        """
        Check the schedules and see what the required snapshot is.
        Take one immediately on the first overdue snapshot required
        """
        # Make sure a refresh() doesn't mess with the schedule while
        # we're reading through it.
        self._refreshLock.acquire()
        next,schedule = self._next_due()
        self._refreshLock.release()
        now = long(time.time())
        while next != None and next <= now:
            label = self._take_snapshots(schedule)
            self._plugin.execute_plugins(schedule, label)
            self._refreshLock.acquire()
            self._update_schedules()
            next,schedule = self._next_due();
            self._refreshLock.release()
            dt = datetime.datetime.fromtimestamp(next)
            util.debug("Next snapshot is %s due at: %s" % \
                       (schedule, dt.isoformat()), \
                       self.verbose)
        return next
                    
    def _take_snapshots(self, schedule):
        # Set the time before taking snapshot to avoid clock skew due
        # to time taken to complete snapshot.
        tm = long(time.time())
        label = "%s%s%s-%s" % \
                (autosnapsmf.SNAPLABELPREFIX, self._separator, schedule,
                 datetime.datetime.now().strftime("%Y-%m-%d-%Hh%M"))
        try:
            self._datasets.create_auto_snapshot_set(label, tag=schedule)
        except RuntimeError, message:
            # Write an error message, set the exit code and pass it up the
            # stack so the thread can terminate
            sys.stderr.write("Failed to create snapshots for schedule: %s\n" \
                             % (schedule))
            self.exitCode = smf.SMF_EXIT_MON_DEGRADE
            raise RuntimeError,message
        self._last[schedule] = tm;
        self._perform_purge(schedule)
        return label

    def _prune_snapshots(self, dataset, schedule):
        """Cleans out zero sized snapshots, kind of cautiously"""
            # Per schedule: We want to delete 0 sized
            # snapshots but we need to keep at least one around (the most
            # recent one) for each schedule so that that overlap is 
            # maintained from frequent -> hourly -> daily etc.
            # Start off with the smallest interval schedule first and
            # move up. This increases the amount of data retained where
            # several snapshots are taken together like a frequent hourly
            # and daily snapshot taken at 12:00am. If 3 snapshots are all
            # identical and reference the same identical data they will all
            # be initially reported as zero for used size. Deleting the
            # daily first then the hourly would shift make the data referenced
            # by all 3 snapshots unique to the frequent scheduled snapshot.
            # This snapshot would probably be purged within an how ever and the
            # data referenced by it would be gone for good.
            # Doing it the other way however ensures that the data should
            # remain accessible to the user for at least a week as long as
            # the pool doesn't run low on available space before that.

        try:
            snaps = dataset.list_snapshots("%s%s" % (self._prefix,schedule))
            # Clone the list because we want to remove items from it
            # while iterating through it.
            remainingsnaps = snaps[:]
        except RuntimeError,message:
            sys.stderr.write("Failed to list snapshots during snapshot cleanup\n")
            self.exitCode = smf.SMF_EXIT_ERR_FATAL
            raise RuntimeError,message

        if (self._keepEmpties == False):
            try: # remove the newest one from the list.
                snaps.pop()
            except IndexError:
                pass
            for snapname in snaps:
                try:
                    snapshot = zfs.Snapshot(snapname)
                except Exception,message:
                    sys.stderr.write(str(message))
                    # Not fatal, just skip to the next snapshot
                    continue

                try:
                    if snapshot.get_used_size() == 0:
                        util.debug("Destroying zero sized: " + snapname, \
                                   self.verbose)
                        try:
                            snapshot.destroy()
                        except RuntimeError,message:
                            sys.stderr.write("Failed to destroy snapshot: " +
                                             snapname + "\n")
                            self.exitCode = smf.SMF_EXIT_MON_DEGRADE
                            # Propogate exception so thread can exit
                            raise RuntimeError,message
                        remainingsnaps.remove(snapname)
                except RuntimeError,message:
                    sys.stderr.write("Can not determine used size of: " + \
                                     snapname + "\n")
                    self.exitCode = smf.SMF_EXIT_MON_DEGRADE
                    #Propogate the exception to the thead run() method
                    raise RuntimeError,message

        # Deleting individual snapshots instead of recursive sets
        # breaks the recursion chain and leaves child snapshots
        # dangling so we need to take care of cleaning up the 
        # snapshots.
        target = len(remainingsnaps) - self._keep[schedule]
        counter = 0
        while counter < target:
            util.debug("Destroy expired snapshot: " + \
                       remainingsnaps[counter], 
                       self.verbose)
            try:
                snapshot = zfs.Snapshot(remainingsnaps[counter])
            except Exception,message:
                    sys.stderr.write(str(message))
                    # Not fatal, just skip to the next snapshot
                    counter += 1
                    continue
            try:
                snapshot.destroy()
            except RuntimeError,message:
                sys.stderr.write("Failed to destroy snapshot: " +
                                 snapshot.name + "\n")
                self.exitCode = smf.SMF_EXIT_ERR_FATAL
                # Propogate exception so thread can exit
                raise RuntimeError,message
            else:
                counter += 1

    def _perform_purge(self, schedule):
        """Cautiously cleans out zero sized snapshots"""
        # We need to avoid accidentally pruning auto snapshots received
        # from one zpool to another. We ensure this by examining only
        # snapshots whose parent fileystems and volumes are explicitly
        # tagged to be snapshotted.
        try:
            for name in self._datasets.list_auto_snapshot_sets(schedule):
                dataset = zfs.ReadWritableDataset(name)
                self._prune_snapshots(dataset, schedule)
        except RuntimeError,message:
            sys.stderr.write("Error listing datasets during " + \
                             "removal of expired snapshots\n")
            self.exitCode = smf.SMF_EXIT_ERR_FATAL
            # Propogate up to thread's run() method
            raise RuntimeError,message

    def _needs_cleanup(self):
        if self._remedialCleanup == False:
            # Sys admin has explicitly instructed for remedial cleanups
            # not to be performed.
            return False
        now = long(time.time())
        # Don't run checks any less than 15 minutes apart.
        if self._cleanupLock.acquire(False) == False:
            #Indicates that a cleanup is already running.
            return False
        # FIXME - Make the cleanup interval equal to the minimum snapshot interval
        # if custom snapshot schedules are defined and enabled.
        elif ((now - self._lastCleanupCheck) < (_MINUTE * 15)):
            pass
        else:
            for zpool in self._zpools:
                try:
                    if zpool.get_capacity() > self._warningLevel:
                        # Before getting into a panic, determine if the pool
                        # is one we actually take snapshots on, by checking
                        # for one of the "auto-snapshot:<schedule> tags. Not
                        # super fast, but it only happens under exceptional
                        # circumstances of a zpool nearing it's capacity.

                        for sched in self._allSchedules:
                            sets = zpool.list_auto_snapshot_sets(sched[0])
                            if len(sets) > 0:
                                util.debug("%s needs a cleanup" \
                                           % zpool.name, \
                                           self.verbose)
                                self._cleanupLock.release()
                                return True
                except RuntimeError, message:
                    sys.stderr.write("Error checking zpool capacity of: " + \
                                     zpool.name + "\n")
                    self._cleanupLock.release()
                    self.exitCode = smf.SMF_EXIT_ERR_FATAL
                    # Propogate up to thread's run() mehod.
                    raise RuntimeError,message
            self._lastCleanupCheck = long(time.time())
        self._cleanupLock.release()
        return False

    def _perform_cleanup(self):
        if self._cleanupLock.acquire(False) == False:
            # Cleanup already running. Skip
            return
        self._destroyedsnaps = []
        for zpool in self._zpools:
            try:
                self._poolstatus[zpool.name] = 0
                capacity = zpool.get_capacity()
                if capacity > self._warningLevel:
                    self._run_warning_cleanup(zpool)
                    self._poolstatus[zpool.name] = 1
                    capacity = zpool.get_capacity()
                if capacity > self._criticalLevel:
                    self._run_critical_cleanup(zpool)
                    self._poolstatus[zpool.name] = 2
                    capacity = zpool.get_capacity()
                if capacity > self._emergencyLevel:
                    self._run_emergency_cleanup(zpool)
                    self._poolstatus[zpool.name] = 3
                    capacity = zpool.get_capacity()
                if capacity > self._emergencyLevel:
                    self._run_emergency_cleanup(zpool)
                    self._poolstatus[zpool.name] = 4
            # This also catches exceptions thrown from _run_<level>_cleanup()
            # and _run_cleanup() in methods called by _perform_cleanup()
            except RuntimeError,message:
                sys.stderr.write("Remedial space cleanup failed because " + \
                                 "of failure to determinecapacity of: " + \
                                 zpool.name + "\n")
                self.exitCode = smf.SMF_EXIT_ERR_FATAL
                self._cleanupLock.release()
                # Propogate up to thread's run() method.
                raise RuntimeError,message

            # Bad - there's no more snapshots left and nothing 
            # left to delete. We don't disable the service since
            # it will permit self recovery and snapshot
            # retention when space becomes available on
            # the pool (hopefully).
            util.debug("%s pool status after cleanup:" \
                       % zpool.name, \
                       self.verbose)
            util.debug(zpool, self.verbose)
        util.debug("Cleanup completed. %d snapshots were destroyed" \
                   % len(self._destroyedsnaps), \
                   self.verbose)
        # Avoid needless list iteration for non-debug mode
        if self.verbose == True and len(self._destroyedsnaps) > 0:
            for snap in self._destroyedsnaps:
                sys.stderr.write("\t%s\n" % snap)
        self._cleanupLock.release()

    def _run_warning_cleanup(self, zpool):
        util.debug("Performing warning level cleanup on %s" % \
                   zpool.name, \
                   self.verbose)
        self._run_cleanup(zpool, "daily", self._warningLevel)
        if zpool.get_capacity() > self._warningLevel:
            self._run_cleanup(zpool, "hourly", self._warningLevel)

    def _run_critical_cleanup(self, zpool):
        util.debug("Performing critical level cleanup on %s" % \
                   zpool.name, \
                   self.verbose)
        self._run_cleanup(zpool, "weekly", self._criticalLevel)
        if zpool.get_capacity() > self._criticalLevel:
            self._run_cleanup(zpool, "daily", self._criticalLevel)
        if zpool.get_capacity() > self._criticalLevel:
            self._run_cleanup(zpool, "hourly", self._criticalLevel)

    def _run_emergency_cleanup(self, zpool):
        util.debug("Performing emergency level cleanup on %s" % \
                   zpool.name, \
                   self.verbose)
        self._run_cleanup(zpool, "monthly", self._emergencyLevel)
        if zpool.get_capacity() > self._emergencyLevel:
            self._run_cleanup(zpool, "weekly", self._emergencyLevel)
        if zpool.get_capacity() > self._emergencyLevel:
            self._run_cleanup(zpool, "daily", self._emergencyLevel)
        if zpool.get_capacity() > self._emergencyLevel:
            self._run_cleanup(zpool, "hourly", self._emergencyLevel)
        if zpool.get_capacity() > self._emergencyLevel:
            self._run_cleanup(zpool, "frequent", self._emergencyLevel)
        #Finally, as a last resort, delete custom scheduled snaphots
        for schedule,i,p,k in self._customSchedules:
            if zpool.get_capacity() < self._emergencyLevel:
                break
            else:
                self._run_cleanup(zpool, schedule, self._emergencyLevel)

    def _run_cleanup(self, zpool, schedule, threshold):
        clonedsnaps = []
        snapshots = []
        try:
            clonedsnaps = self._datasets.list_cloned_snapshots()
        except RuntimeError,message:
                sys.stderr.write("Error (non-fatal) listing cloned snapshots" +
                                 " while recovering pool capacity\n")
                sys.stderr.write("Error details:\n" + \
                                 "--------BEGIN ERROR MESSAGE--------\n" + \
                                 str(message) + \
                                 "\n--------END ERROR MESSAGE--------\n")    

        # Build a list of snapshots in the given schedule, that are not
        # cloned, and sort the result in reverse chronological order.
        try:
            snapshots = [s for s,t in \
                            zpool.list_snapshots("%s%s" \
                            % (self._prefix,schedule)) \
                            if not s in clonedsnaps]
            snapshots.reverse()
        except RuntimeError,message:
            sys.stderr.write("Error listing snapshots" +
                             " while recovering pool capacity\n")
            self.exitCode = smf.SMF_EXIT_ERR_FATAL
            # Propogate the error up to the thread's run() method.
            raise RuntimeError,message
   
        while zpool.get_capacity() > threshold:
            if len(snapshots) == 0:
                syslog.syslog(syslog.LOG_NOTICE,
                              "No more %s snapshots left" \
                               % schedule)
                return

            """This is not an exact science. Deleteing a zero sized 
            snapshot can have unpredictable results. For example a
            pair of snapshots may share exclusive reference to a large
            amount of data (eg. a large core file). The usage of both
            snapshots will initially be seen to be 0 by zfs(1). Deleting
            one of the snapshots will make the data become unique to the
            single remaining snapshot that references it uniquely. The
            remaining snapshot's size will then show up as non zero. So
            deleting 0 sized snapshot is not as pointless as it might seem.
            It also means we have to loop through this, each snapshot set
            at a time and observe the before and after results. Perhaps
            better way exists...."""

            # Start with the oldest first
            snapname = snapshots.pop()
            snapshot = zfs.Snapshot(snapname)
            # It would be nicer, for performance purposes, to delete sets
            # of snapshots recursively but this might destroy more data than
            # absolutely necessary, plus the previous purging of zero sized
            # snapshots can easily break the recursion chain between
            # filesystems.
            # On the positive side there should be fewer snapshots and they
            # will mostly non-zero so we should get more effectiveness as a
            # result of deleting snapshots since they should be nearly always
            # non zero sized.
            util.debug("Destroying %s" % snapname, self.verbose)
            try:
                snapshot.destroy()
            except RuntimeError,message:
                # Would be nice to be able to mark service as degraded here
                # but it's better to try to continue on rather than to give
                # up alltogether (SMF maintenance state)
                sys.stderr.write("Warning: Cleanup failed to destroy: %s\n" % \
                                 (snapshot.name))
                sys.stderr.write("Details:\n%s\n" % (str(message)))
            else:
                self._destroyedsnaps.append(snapname)
            # Give zfs some time to recalculate.
            time.sleep(3)
        
    def _send_to_syslog(self):
        for zpool in self._zpools:
            status = self._poolstatus[zpool.name]
            if status == 4:
                syslog.syslog(syslog.LOG_EMERG,
                              "%s is over %d%% capacity. " \
                              "All automatic snapshots were destroyed" \
                               % (zpool.name, self._emergencyLevel))
            elif status == 3:
                syslog.syslog(syslog.LOG_ALERT,
                              "%s exceeded %d%% capacity. " \
                              "Automatic snapshots over 1 hour old were destroyed" \
                               % (zpool.name, self._emergencyLevel))
            elif status == 2:
                syslog.syslog(syslog.LOG_CRIT,
                              "%s exceeded %d%% capacity. " \
                              "Weekly, hourly and daily automatic snapshots were destroyed" \
                               % (zpool.name, self._criticalLevel))                             
            elif status == 1:
                syslog.syslog(syslog.LOG_WARNING,
                              "%s exceeded %d%% capacity. " \
                              "Hourly and daily automatic snapshots were destroyed" \
                               % (zpool.name, self._warningLevel))

        if len(self._destroyedsnaps) > 0:
            syslog.syslog(syslog.LOG_NOTICE,
                          "%d automatic snapshots were destroyed" \
                           % len(self._destroyedsnaps))

    def _send_notification(self):
        worstpool = None
        worststatus = 0

        for zpool in self._zpools:
            status = self._poolstatus[zpool.name]
            # >= to ensure that something should always be set.
            if status >= worststatus:
                worstpool = zpool.name
                worststatus = status

        #FIXME make the various levels indexible
        if worststatus == 4:
            self._dbus.capacity_exceeded(worstpool, 4, self._emergencyLevel)
        elif worststatus == 3:
            self._dbus.capacity_exceeded(worstpool, 3, self._emergencyLevel)
        elif worststatus == 2:
            self._dbus.capacity_exceeded(worstpool, 2, self._criticalLevel)
        elif worststatus == 1:
            self._dbus.capacity_exceeded(worstpool, 1, self._warningLevel)
        #elif: 0 everything is fine. Do nothing.


def monitor_threads(snapthread):
    if snapthread.is_alive():
        return True
    else:
        sys.stderr.write("Snapshot monitor thread exited.\n")
        if snapthread.exitCode == smf.SMF_EXIT_MON_DEGRADE:
            # FIXME - it would be nicer to mark the service as degraded than
            # go into maintenance state for some situations such as a
            # particular snapshot schedule failing.
            # But for now SMF does not implement this feature. But if/when it
            # does it's better to use svcadm to put the # service into the
            # correct state since the daemon shouldn't exit whentransitioning
            # to a degraded state.
            #sys.stderr.write("Placing service into maintenance state\n")
            #subprocess.call(["/usr/sbin/svcadm", "mark", "maintenance",
            #                 os.getenv("SMF_FMRI")])
            # SMF will take care of kill the daemon
            sys.exit(smf.SMF_EXIT_ERR_FATAL)
            return False
        elif snapthread.exitCode == smf.SMF_EXIT_ERR_FATAL:
            #sys.stderr.write("Placing service into maintenance state\n")
            #subprocess.call(["/usr/sbin/svcadm", "mark", "maintenance",
            #                 os.getenv("SMF_FMRI")])
            # SMF will take care of killing the daemon
            sys.exit(smf.SMF_EXIT_ERR_FATAL)
            return False
        else:
            sys.stderr.write("Snapshot monitor thread exited abnormally\n")
            sys.stderr.write("Exit code: %d\n" % (snapthread.exitCode))
            #subprocess.call(["/usr/sbin/svcadm", "mark", "maintenance",
            #                 os.getenv("SMF_FMRI")])
            sys.exit(smf.SMF_EXIT_ERR_FATAL)
            return False


def child_sig_handler(signum, frame):
    if signum == signal.SIGUSR1:
        sys.exit(smf.SMF_EXIT_OK)
    elif signum == signal.SIGCHLD:
        sys.exit(smf.SMF_EXIT_ERR_FATAL)
    elif signum == signal.SIGALRM:
        sys.exit(smf.SMF_EXIT_ERR_FATAL)

# Default daemon parameters.
# File mode creation mask of the daemon.
UMASK = 0
# Default working directory for the daemon.
WORKDIR = "/"
# Default maximum for the number of available file descriptors.
MAXFD = 1024

def create_daemon():
    """
    Detach a process from the controlling terminal and run it in the
    background as a daemon.
    """
    #Catch signals that we might receive from child
    signal.signal(signal.SIGCHLD, child_sig_handler)
    signal.signal(signal.SIGUSR1, child_sig_handler)
    signal.signal(signal.SIGALRM, child_sig_handler)
    try:
        pid = os.fork()
    except OSError, e:
        raise Exception, "%s [%d]" % (e.strerror, e.errno)

    if (pid == 0):
        #Reset signals that we set to trap in parent
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        os.setsid()
        os.chdir(WORKDIR)
        os.umask(UMASK)
    else:
        #Wait for the child to give the OK or otherwise.
        signal.pause()


def main(argv):

    # Check SMF invocation environment
    if os.getenv("SMF_FMRI") == None or os.getenv("SMF_METHOD") != "start":
        sys.stderr.write("Command line invocation of %s unsupported.\n" \
                         % (sys.argv[0]))
        sys.stderr.write("This command is intended for smf(5) invocation only.\n")
        sys.exit(smf.SMF_EXIT_ERR_NOSMF)

    # Daemonise the service.
    create_daemon()

    # The user security attributes checked are the following:
    # Note that UID == 0 will match any profile search so
    # no need to check it explicitly.
    syslog.openlog("time-sliderd", 0, syslog.LOG_DAEMON)
    rbacp = RBACprofile()
    if rbacp.has_profile("ZFS File System Management"):

        gobject.threads_init()

        # Tell dbus to use the gobject mainloop for async ops
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        dbus.mainloop.glib.threads_init()
        # Register a bus name with the system dbus daemon
        systemBus = dbus.SystemBus()
        name = dbus.service.BusName("org.opensolaris.TimeSlider", systemBus)

        # Create and start the snapshot manger. Takes care of
        # auto snapshotting service and auto cleanup.
        snapshot = SnapshotManager(systemBus)
        snapshot.start()
        gobject.timeout_add(2000, monitor_threads, snapshot)

        mainloop = gobject.MainLoop()
        try:
            mainloop.run()
        except KeyboardInterrupt:
            mainloop.quit()
            sys.exit(smf.SMF_EXIT_OK)
    else:
        syslog.syslog(syslog.LOG_ERR,
               "%s has insufficient privileges to run time-sliderd!" \
               % rbacp.name)
        syslog.closelog()    
        sys.exit(smf.SMF_EXIT_ERR_PERM)
    syslog.closelog()
    sys.exit(smf.SMF_EXIT_OK)

