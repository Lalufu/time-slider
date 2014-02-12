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

import os
import os.path
import fcntl
import tempfile
import sys
import subprocess
import statvfs
import time
import threading
import math
import syslog
import gobject
import gio
import dbus
import shutil
import copy
from bisect import insort, bisect_left

from time_slider import util, zfs, dbussvc, autosnapsmf, timeslidersmf
import rsyncsmf


# Set to True if SMF property value of "plugin/command" is "true"
verboseprop = "plugin/verbose"
propbasename = "org.opensolaris:time-slider-plugin"

class RsyncError(Exception):
    """Generic base class for RsyncError

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)


class RsyncTargetDisconnectedError(RsyncError):
    """Exception raised when the backup device goes offline during
       the rsync transfer.

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, source, dest, message):
        msg = "Target directory error during rsync backup from " \
              "%s to target \'%s\' Rsync error details:\n%s" \
              % (source, dest, message)
        RsyncError.__init__(self, msg)


class RsyncTransferInterruptedError(RsyncError):
    """Exception raised when the rsync transfer process pid was
       interrupted or killed during the rsync transfer.

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, source, dest, message):
        msg = "Interrputed rsync transfer from %s to %s " \
              "Rsync error details:\n%s" % (source, dest, message)
        RsyncError.__init__(self, msg)


class RsyncSourceVanishedError(RsyncError):
    """Exception raised when rsync could only partially transfer
       due to the contents of the source directory being removed.
       Possibly due to a snapshot being destroyed during transfer
       because of immediate or deferred (holds released) destruction.

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, source, dest, message):
        msg = "Rsync source directory vanished during transfer of %s to %s" \
              "Rsync error details:\n%s" % (source, dest, message)
        RsyncError.__init__(self, msg)


class RsyncProcess(threading.Thread):


    def __init__(self, source, target, latest=None, verbose=False, logfile=None):

        self._sourceDir = source
        self._backupDir = target
        self._latest = latest
        self._verbose = verbose
        self._proc = None
        self._forkError = None
        self._logFile = logfile
        # Init done. Now initiaslise threading.
        threading.Thread.__init__ (self)

    def run(self):
        try:
            self._proc = subprocess.Popen(self._cmd,
                                          stderr=subprocess.PIPE,
                                          close_fds=True)
        except OSError as e:
            # _check_exit_code() will pick up this and raise an
            # exception in the original thread.
            self._forkError = "%s: %s" % (self._cmd[0], str(e))
        else:
            self._stdout,self._stderr = self._proc.communicate()
            self._exitValue = self._proc.wait()

    def _check_exit_code(self):
        if self._forkError:
            # The rsync process failed to execute, probably
            # received an OSError exception. Pass it up.
            raise RsyncError(self._forkError)

        if self._exitValue == 0:
            return
        # Non zero return code means rsync encountered an
        # error which may be transient or require sys-admin
        # intervention to fix.
        
        # This method basically just maps known rsync exit codes
        # to exception classes.
        
        # Rsync exit value codes (non-zero)
        
        # 11/12 Indicates backup drive was disconnected during
        # transfer. Recoverable once drive reconnected:
        # 11   Error in file I/O
        # 12   Error in rsync protocol data stream
        if self._exitValue == 11 or \
            self._exitValue == 12:
            raise RsyncTargetDisconnectedError(self._sourceDir,
                                               self._backupDir,
                                               self._stderr)
        # Transfer pid interrupted by SIGUSR1 or SIGINT. Recoverable:
        # 20   Received SIGUSR1 or SIGINT
        elif self._proc.returncode == 20:
            raise RsyncTransferInterruptedError(self._sourceDir,
                                                self._backupDir,
                                                self._stderr)

        # For everything else unknown or unexpected, treat it as 
        # fatal and provide the rsync stderr output.
        else:
            raise RsyncError(self._stderr)

    def start_backup(self):
        # First, check to see if the rsync destination
        # directory is accessible.
        try:
            os.stat(self._backupDir)
        except OSError:
            util.debug("Backup directory is not " \
                       "currently accessible: %s" \
                       % (self._backupDir),
                       self._verbose)
            #FIXME exit/exception needs to be raise here
            # or status needs to be set.
            return

        try:
            os.stat(self._sourceDir)
        except OSError:
            util.debug("Backup source directory is not " \
                       "currently accessible: %s" \
                       % (self._sourceDir),
                       self._verbose)
            #FIXME exit/excpetion needs to be raise here
            # or status needs to be set.
            return

        if self._latest:
            self._cmd = ["/usr/bin/rsync", "-a", "--inplace",\
                   "%s/." % (self._sourceDir), \
                   "--link-dest=%s" % (self._latest), \
                   self._backupDir]
        else:
            self._cmd = ["/usr/bin/rsync", "-a", "--inplace",\
                   "%s/." % (self._sourceDir), \
                   self._backupDir]

        if self._logFile:
            self._cmd.insert(1, "--log-file=%s" % (self._logFile))
        if self._verbose:
            self._cmd.insert(1, "-vv")

        self.start()


class BackupQueue():

    def __init__(self, fmri, dbus, mainLoop=None):
        self._bus = dbus
        self._mainLoop = mainLoop
        self._started = False
        self._pluginFMRI = fmri
        self._smfInst = rsyncsmf.RsyncSMF(self._pluginFMRI)
        self._verbose = self._smfInst.get_verbose()
        self._rsyncVerbose = self._smfInst.get_rsync_verbose()
        self._propName = "%s:%s" % (propbasename, fmri.rsplit(':', 1)[1])

        # Variables to quickly access time sorted backups and 
        # to map directory names to mtimes.
        self._backupDirs = None
        self._backups = None
        self._backupTimes = {}

        released = release_held_snapshots(self._propName)
        for snapName in released:
            util.debug("Released dangling userref on: " + snapName,
                       self._verbose)

        self._tempSchedules = None
        # List of all snapshots currently in our backup queue
        self._pendingList = list_pending_snapshots(self._propName)

        # Try to backup in sets of snapshots grouped by a common
        # snapshot label. These get taken from the head of the
        # pending list. After a working set has been completed,
        # pending list gets refreshed and a new working set is
        # extracted.
        self._currentQueueSet = []
        self._skipList = []
        self._queueLength = 0

        self._cleanupThreshold = self._smfInst.get_cleanup_threshold()
        if self._cleanupThreshold < 1 or \
           self._cleanupThreshold > 99:
            # Stupid value. #FIXME Plugin should be checked by SMF start
            # method and placed into maintenance if this happens.
            # For now, go with default
            util.log_error(syslog.LOG_ERR,
                           "Invalid value for SMF property " \
                           "<rsync/cleanup_threshold>: %d." \
                           "Using default value of 95%" \
                           % (self._cleanupThreshold))

        # Base variables for backup device. Will be initialised
        # later in _find_backup_device()
        self._smfTargetKey = self._smfInst.get_target_key()
        sys,self._nodeName,rel,ver,arch = os.uname()
        self._rsyncBaseDir = None
        self._rsyncDir = None
        self._keyFile = None

        tsSMF = timeslidersmf.TimeSliderSMF()
        self._labelSeparator = tsSMF.get_separator()
        del tsSMF
        # Finally go look for the backup device
        self._find_backup_device()

    def empty_trash_folders(self):
        trashDirs = []
        trashedBackups = []
        os.chdir(self._rsyncDir)
        for root, dirs, files in os.walk(self._rsyncDir):
            if '.time-slider' in dirs:
                dirs.remove ('.time-slider')
                trashDir = os.path.join(root,
                                        rsyncsmf.RSYNCTRASHSUFFIX)
                if os.path.exists(trashDir):
                    trashDirs.append(trashDir)
        for trashDir in trashDirs:
            os.chdir(trashDir)
            trashItems = []
            trashItems = [d for d in os.listdir(trashDir) \
                          if os.path.isdir(d) and
                          not os.path.islink(d)]
            if len(trashItems) > 0:
                util.debug("Deleting trash backups in %s" % (trashDir),
                           self._verbose)
            for trashItem in trashItems:
                util.debug("Deleting trash item: %s" % (trashItem),
                           self._verbose)
                # FIXME add some dbus notification here to let the
                # applet know what's going on.
                shutil.rmtree(trashItem)

    def _get_temp_schedules(self):
        # Get retention rule for non archival snapshots as per
        # rules defined in:
        # svc://system/filesystem/zfs/auto-snapshot:<schedule>
        archived = self._smfInst.get_archived_schedules()
        triggers = self._smfInst.get_trigger_list()
        defScheds = autosnapsmf.get_default_schedules()
        customScheds = autosnapsmf.get_custom_schedules()
        try:
            triggers.index('all')
            # Expand the wildcard value 'all' 
            triggers = [sched for sched,i,p,k in defScheds]
            customTriggers = [sched for sched,i,p,k in customScheds]
            triggers.extend(customTriggers)
        except ValueError:
            pass

        self._tempSchedules = [schedule for schedule in defScheds if \
                               schedule[0] not in archived]
        self._tempSchedules.extend([schedule for schedule in customScheds if \
                                   schedule[0] not in archived])

    def _remove_dead_backups(self):
        """
           Identifies and removes partially completed backups whose origin
           snapshot is no longer in the pending queue, indicating that the
           backup will never get completed, in which case it's just a waste
           of space
        """
        backupDirs = []
        partialDirs = []
        deadBackups = []
        os.chdir(self._rsyncDir)
        for root, dirs, files in os.walk(self._rsyncDir):
            if '.time-slider' in dirs:
                dirs.remove ('.time-slider')
                partialDir = os.path.join(root,
                                          rsyncsmf.RSYNCPARTIALSUFFIX)
                partialDirs.append(partialDir)
        for dirName in partialDirs:
            if not os.path.exists(partialDir):
                continue
            os.chdir(dirName)
            partials = [d for d in os.listdir(dirName) \
                        if os.path.isdir(d)]
            if len(partials) == 0:
                continue
            suffix = rsyncsmf.RSYNCPARTIALSUFFIX
            prefix = self._rsyncDir
            # Reconstruct the origin ZFS filesystem name
            baseName = dirName.replace(prefix, '', 1).lstrip('/')
            fsName = baseName.replace(suffix, '', 1).rstrip('/')
            for snapshotLabel in partials:
                pending = False
                # Reconstruct the origin snapshot name and see
                # if it's still pending rsync backup. If it is
                # then leave it alone since it can be used to
                # resume a partial backup later. Otherwise it's
                # never going to be backed up and needs to be
                # manually deleted.
                snapshotName = "%s@%s" % (fsName, snapshotLabel)
                for ctime,name in self._pendingList:
                    if name == snapshotName:
                        pending = True
                        continue
                if pending == False:
                    util.debug("Deleting zombied partial backup: %s" \
                               % (os.path.abspath(snapshotLabel)),
                               self._verbose)
                    shutil.rmtree(snapshotLabel)
                    # Don't forget the log file too.
                    logFile = os.path.join(os.path.pardir,
                                           os.path.pardir,
                                           rsyncsmf.RSYNCLOGSUFFIX,
                                           snapshotLabel + ".log")
                    try:
                        os.stat(logFile)
                        util.debug("Deleting zombie log file: %s" \
                                   % (os.path.abspath(logFile)),
                                   self._verbose)
                        os.unlink(logFile)
                    except OSError:
                        util.debug("Expected rsync log file not " \
                                   "found: %s"\
                                   % (os.path.abspath(logFile)),
                                   self._verbose)

    def _discover_backups(self):
        self._backupDirs = []
        self._backups = []
        self._backupTimes = {}
        # backupTimes dictionary is not primarily used
        # to store directory listings, but to map 
        # mtimes to directories for quick lookups.
        
        os.chdir (self._rsyncDir)
        for root, dirs, files in os.walk(self._rsyncDir):
            if '.time-slider' in dirs:
                dirs.remove('.time-slider')
                backupDir = os.path.join(root, rsyncsmf.RSYNCDIRSUFFIX)
                if os.path.exists(backupDir):
                    insort(self._backupDirs, os.path.abspath(backupDir))
        for dirName in self._backupDirs:
            self._backupTimes[dirName] = {}
            os.chdir(dirName)
            dirList = [d for d in os.listdir(dirName) \
                        if os.path.isdir(d) and
                        not os.path.islink(d)]
            for d in dirList:
                mtime = os.stat(d).st_mtime
                insort(self._backups, [long(mtime), os.path.abspath(d)])
                self._backupTimes[dirName][d] = mtime

    def _find_backup_device(self):
        # Determine the rsync backup dir. This is the target dir
        # defined by the SMF instance plus the "TIMESLIDER/<nodename>"
        # suffix. Try finding it at the preconfigured path first,
        # then failing that, scan removable media mounts, in case it
        # got remounted under a different path than at setup time.
        self._rsyncBaseDir = None
        path = self._smfInst.get_target_dir()
        if self._validate_rsync_target(path) == True:
            self._rsyncBaseDir = path
            util.debug("Backup target device online: %s" % (path),
                       self._verbose)
        else:
            util.debug("Backup target device not mounted at: %s" \
                       "Scanning removable devices.." \
                       % (path),
                       self._verbose)
            volMonitor = gio.volume_monitor_get()
            mounts = volMonitor.get_mounts()
            for mount in mounts:
                root = mount.get_root()
                path = root.get_path()
                if self._validate_rsync_target(path) == True:
                    util.debug("Located backup target device at: %s" \
                               % (path),
                               self._verbose)
                    self._rsyncBaseDir = path

        if self._rsyncBaseDir != None:
            self._rsyncDir = os.path.join(self._rsyncBaseDir,
                                         rsyncsmf.RSYNCDIRPREFIX,
                                         self._nodeName)
            self._keyFile = os.path.join(self._rsyncBaseDir,
                                         rsyncsmf.RSYNCDIRPREFIX,
                                         rsyncsmf.RSYNCCONFIGFILE)

        
    def _validate_rsync_target(self, path):
        """
           Tests path to see if it is the pre-configured
           rsync backup device path.
           Returns True on success, otherwise False
        """
        # FIXME - this is duplicate in the applet and should
        # be moved into a shared module
        if not os.path.exists(path):
            return False
        testDir = os.path.join(path,
                               rsyncsmf.RSYNCDIRPREFIX,
                               self._nodeName)
        testKeyFile = os.path.join(path,
                                   rsyncsmf.RSYNCDIRPREFIX,
                                   rsyncsmf.RSYNCCONFIGFILE)
        if os.path.exists(testDir) and \
            os.path.exists(testKeyFile):
            testKeyVal = None
            f = open(testKeyFile, 'r')
            for line in f.readlines():
                key, val = line.strip().split('=')
                if key.strip() == "target_key":
                    targetKey = val.strip()
                    break
            f.close()
            if targetKey == self._smfTargetKey:
                return True
        return False

    def _find_deleteable_backups(self, timestamp):
        """
           Returns a list of backup directory paths that are older than
           timestamp, and can be deleted in order to make room for newer
           backups. Certain restrictions apply such as:
           - The backup cannot be locked (indicating it's being or about
             to be deleted by another process
           - The last remaining backup in it's parent directory, which
             would mean it is the only backup of a given fileystem on the
             device. We always keep at least 1 full backup of a filesystem
             on the device if it belongs to a currently selected filesystem.
        """
        deleteables = []
        # This should have already occured in
        # backup_snapshot() mainloop method
        if self._backupDirs == None:
            self._discover_backups()

        if len(self._backupDirs) == 0:
            # We were not able to find any backups to delete. Try again later
            return []

        # Extract the subset of self._backupDirs that are older than timestamp
        idx = bisect_left(self._backups, [timestamp, ''])
        subset = self._backups[0:idx]

        # Copy the backupTimes dictionary since so we can
        # modify it safely.
        copiedTimes = copy.deepcopy(self._backupTimes)
        for mtime, dirName in subset:
            head,tail = os.path.split(dirName)
            if len(copiedTimes[head]) < 2:
                # We can only delete this single backup provided
                # it's filesystem is no longer tagged for rsync
                # replication. Othewise we need to leave at least
                # one backup on the device at all times, and also
                # to provide an incremental backup point for
                # future backups.
                snapName = backup_name_to_snapshot_name(dirName)
                snapshot = zfs.Snapshot(snapName)
                fs = zfs.Filesystem(snapshot.fsname)
                if fs.get_user_property(rsyncsmf.RSYNCFSTAG) == "true":
                    continue
                else:
                    # If we are going to actually remove this final
                    # remaining backup of this filesystem then we need
                    # to unqueue any pending snapshots of it,
                    # otherwise after deleting this one, we'll just 
                    # start backing up the older snapshots of this 
                    # filesystem afterwards, which is a waste of time
                    # and space.
                    pending = [name for time,name in \
                               list_pending_snapshots(self._propName) if \
                               name.find(snapshot.fsname + '@') == 0]
                    cmd = [zfs.PFCMD, zfs.ZFSCMD, "inherit", self._propName]
                    util.debug("Unqueuing pending backups of deselected " \
                               "filesystem: " + snapshot.fsname + '\n' + \
                               str(pending),
                               self._verbose)
                    cmd.extend(pending)
                    util.run_command(cmd)

            lockFileDir = os.path.join(head,
                                       os.path.pardir,
                                       os.path.pardir,
                                       rsyncsmf.RSYNCLOCKSUFFIX)
            lockFile = os.path.join(lockFileDir, tail)

            if not os.path.exists(lockFile):
                # No lock file so we are free to delete it.
                deleteables.append([mtime, dirName])
                # Remove it from copiedTimes so it doesn't get
                # double counted
                del copiedTimes[head][tail]
                continue
            # Lock file so probably can't delete this, but try it out
            # anyway incase it's stale/unlocked
            try:
                lockFp = open(lockFile, 'w')
                fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                util.debug("Can't delete backup %s because it " \
                           "is locked by another process." \
                           "Skipping" % (dirName),
                           self._verbose)
                continue
            # Ok, we can still delete it, but get rid of the stale lock file
            lockFp.close()
            os.unlink(lockFile)
            deleteabled.append([mtime, dirName])
            # Remove it from copiedTimes so it doesn't get
            # double counted
            del copiedTimes[head][tail]
        return deleteables

    def _recover_space(self, deleteables):

        # Important:
        # Don't actually loop throught this list fully. Break out
        # as soon as pool capacity is beneath the threshhold level
        # again.
        remainder = deleteables[:]
        for mtime,dirName in deleteables:
            if util.get_filesystem_capacity(self._rsyncDir) < \
               self._cleanupThreshold:
                # No need to delete anything further
                return remainder
            lockFile = None
            lockFp = None
            head,tail = os.path.split(dirName)
                
            # Check if it has a lock file and try to grab it.
            # If that fails we need to move onto the next backup in
            # the list.
            lockFileDir = os.path.join(head,
                                       os.path.pardir,
                                       os.path.pardir,
                                       rsyncsmf.RSYNCLOCKSUFFIX)
            lockFile = os.path.join(lockFileDir, tail)

            if not os.path.exists(lockFileDir):
                os.makedirs(lockFileDir, 0755)
            try:
                lockFp = open(lockFile, 'w')
                fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                util.debug("Can't delete backup %s because it " \
                           "is locked by another process." \
                           "Skipping" % (dirName),
                           self._verbose)
                # Remove if from the remainder list
                idx = bisect_left(remainder, [mtime, dirName])
                del remainder[idx]
                continue

            trash = os.path.join(head,
                                 os.path.pardir,
                                 os.path.pardir,
                                 rsyncsmf.RSYNCTRASHSUFFIX)
            trashDir = os.path.join(trash, tail)

            if not os.path.exists(trash):
                os.makedirs(trash, 0755)

            util.debug("Deleting rsync backup to recover space: %s"\
                % (dirName), self._verbose)
            os.rename(dirName, trashDir)
            lockFp.close()
            os.unlink(lockFile)
            shutil.rmtree(trashDir)
            # Remove the log file if it exists
            logFile = os.path.join(head,
                                   os.path.pardir,
                                   os.path.pardir,
                                   rsyncsmf.RSYNCLOGSUFFIX,
                                   tail + ".log")
            if os.path.exists(logFile):
                os.unlink(logFile)
            else:
                util.debug("Expected to find log file %s when deleting %s " \
                           "during space recovery" % (logFile, dirName),
                           self._verbose)
            # Remove dirName from the backup list
            idx = bisect_left(self._backups, [mtime, dirName])
            del self._backups[idx]
            # Remove if from the remainder list too
            idx = bisect_left(remainder, [mtime, dirName])
            del remainder[idx]
        return remainder

    def backup_snapshot(self):
        # First, check to see if the rsync destination
        # directory is accessible.

        if self._rsyncBaseDir == None:
            util.debug("Backup target device is not " \
                       "accessible right now: %s" \
                       % (self._smfInst.get_target_dir()),
                       self._verbose)
            self._bus.rsync_unsynced(len(self._pendingList))
            if self._mainLoop:
                self._mainLoop.quit()
            sys.exit(0)

        # Extra paranoia
        if self._validate_rsync_target(self._rsyncBaseDir) == False:
            util.debug("Backup target directory does not " \
                       "have a matching configuration key. " \
                       "Possibly old or wrong device: %s" \
                       % (self._keyFile),
                       self._verbose)
            self._bus.rsync_unsynced(len(self._pendingList))
            if self._mainLoop:
                self._mainLoop.quit()
            sys.exit(0)

        # Before getting started. Identify what needs to be cleaned up on 
        # the backup target.
        if self._tempSchedules == None:
            self._get_temp_schedules()
        
        # Remove incompleteable partial backups, then find out what
        # complete backups we already have on the target device
        if self._started == False:
            self._remove_dead_backups()
            self._discover_backups()

        if len(self._currentQueueSet) == 0:
            # Means we are just getting started or have just completed
            # backup of one full set of snapshots. Clear out anything
            # we may have moved to the trash during the previous 
            # backup set iterations.
            self.empty_trash_folders()
            # Refresh the pending list and build a new working set queue
            self._pendingList = list_pending_snapshots(self._propName)
            # Remove skipped items to avoid infinite looping.
            for item in self._skipList:
                try:
                    self._pendingList.remove(item)
                except ValueError:
                    pass
            if len(self._pendingList) == 0:
                # If something was actually backed up, signal
                # that it is now completed.
                if self._started == True:
                    self._bus.rsync_complete(self._rsyncBaseDir)
                self._bus.rsync_synced()
                # Nothing to do exit
                if self._mainLoop:
                    self._mainLoop.quit()
                sys.exit(0)
            else:
                # Construct a new working set queue
                # Identify the newest snapshot and then all
                # snapshots with a matching snapshot label
                self._queueLength = len(self._pendingList)
                ctime,headSnapName = self._pendingList[0]
                label = headSnapName.rsplit("@", 1)[1]
                self._currentQueueSet = \
                    [(ctime,snapName) for \
                     ctime,snapName in self._pendingList if \
                     snapName.rsplit("@", 1)[1] == label]


        if len(self._backups) > 0:
            oldestBackupTime, oldestBackup = self._backups[0]
            qTime, qItem = self._currentQueueSet[0]

            # If the backup device is nearly full, don't
            # bother trying to backup anything unless it's
            # newer than the oldest backup set already on
            # the device.
            # This avoids potential situations where if the
            # backup device has severely limited capacity and
            # older backups sets were in the queue, newer backups
            # might get deleted in order to make room for older
            # ones, creating a downward spiral.
            capacity = util.get_filesystem_capacity(self._rsyncDir)
            if capacity > self._cleanupThreshold:
                # Find backups older than qTime that could in theory
                # be deleted in order to make room for the curtent
                # pending item.
                deleteables = self._find_deleteable_backups(qTime)

                if len(deleteables) == 0 and \
                   qTime < oldestBackupTime:
                    util.debug("%s has exceeded %d%% of its capacity. " \
                                "Skipping pending backups prior to: " \
                                "%s" % (self._rsyncDir,
                                        self._cleanupThreshold,
                                        time.ctime(oldestBackupTime)),
                                self._verbose)
                    if self._started == True:
                        self._bus.rsync_complete(self._rsyncBaseDir)
                    self._bus.rsync_synced()
                    # Nothing to do exit
                    if self._mainLoop:
                        self._mainLoop.quit()
                    sys.exit(0)

        if self._started == False:
            self._started = True
            self._bus.rsync_started(self._rsyncBaseDir)

        ctime,snapName = self._currentQueueSet[0]
        snapshot = zfs.Snapshot(snapName, long(ctime))
        # Make sure the snapshot didn't get destroyed since we last
        # checked it.
        remainingList = self._currentQueueSet[1:]
        if snapshot.exists() == False:
            util.debug("Snapshot: %s no longer exists. Skipping" \
                        % (snapName), self._verbose)
            self._currentQueueSet = remainingList
            return True

        # Place a hold on the snapshot so it doesn't go anywhere
        # while rsync is trying to back it up.
        snapshot.hold(self._propName)
        self._queueLength -= 1
        fs = zfs.Filesystem(snapshot.fsname)
        sourceDir = None
        if fs.is_mounted() == True:
            # Get the mountpoint
            mountPoint = fs.get_mountpoint()
            sourceDir = "%s/.zfs/snapshot/%s" \
                        % (mountPoint, snapshot.snaplabel)
        else:
            # If the filesystem is not mounted just skip it. If it's
            # not mounted then nothing is being written to it. And
            # we can just catch up with it again later if it doesn't
            # get expired by time-sliderd
            util.debug("%s is not mounted. Skipping." \
                        % (snapshot.fsname), self._verbose)
            snapshot.release(self._propName)
            self._skipList.append(ctime, snapName)
            self._currentQueueSet = remainingList
            return True

        # targetDir is the parent folder of all backups
        # for a given filesystem
        targetDir = os.path.join(self._rsyncDir,
                                 snapshot.fsname,
                                 rsyncsmf.RSYNCDIRSUFFIX)
        # partialDir is a separate directory in which
        # snapshots are initially backed up to. Upon successful
        # completion they are moved to the backupDir.
        partialDir = os.path.join(self._rsyncDir,
                                  snapshot.fsname,
                                  rsyncsmf.RSYNCPARTIALSUFFIX,
                                  snapshot.snaplabel)
        lockFileDir = os.path.join(self._rsyncDir,
                                   snapshot.fsname,
                                   rsyncsmf.RSYNCLOCKSUFFIX)
        logDir = os.path.join(self._rsyncDir,
                              snapshot.fsname,
                              rsyncsmf.RSYNCLOGSUFFIX)
        logFile = os.path.join(logDir,
                               snapshot.snaplabel + ".log")

        
        # backupDir is the full directory path where the new
        # backup will be located ie <targetDir>/<snapshot label>
        backupDir = os.path.join(targetDir, snapshot.snaplabel)

        # Figure out the closest previous backup. Since we
        # backup newest first instead of oldest first it's
        # determined as follows:
        # If queued backup item is newer than the most recent
        # backup on the backup target, use the most recent 
        # backup as the incremental source.
        # Othewise identify the backup on the device that is
        # nearest to but newer than the queued backup.
        nearestOlder = None
        nearestNewer = None
        dirList = []

        if not os.path.exists(partialDir):
            os.makedirs(partialDir, 0755)
        if not os.path.exists(logDir):
            os.makedirs(logDir, 0755)

        if not os.path.exists(targetDir):
            os.makedirs(targetDir, 0755)
            # Add the new directory to our internal
            # mtime dictionary and sorted list.
            self._backupTimes[targetDir] = {}
            insort(self._backupDirs, targetDir)
        else:
            for name,value in self._backupTimes[targetDir].items():
                if ctime > value:
                    if nearestOlder == None or \
                       value > nearestOlder[1]:
                        nearestOlder = [name, value]
                else:
                    if nearestNewer == None or \
                       value < nearestNewer[1]:
                        nearestNewer = [name, value]

        os.chdir(targetDir)
        link = None
        linkDest = None
        lockFile = None
        lockFp = None
        if nearestNewer:
            link = nearestNewer[0]
        elif nearestOlder:
            link = nearestOlder[0]
        if link:
            linkDest = os.path.realpath(link)
            # Create a lock for linkDest. We need to ensure that
            # nautilus' restore view or the time-slider-delete
            # GUI doesn't attempt to delete it or move it to the
            # trash while it is being used by rsync for incremental
            # backup.
            lockFile = os.path.join(lockFileDir,
                                    link + ".lock")

            if not os.path.exists(lockFileDir):
                os.makedirs(lockFileDir, 0755)

            try:
                lockFp = open(lockFile, 'w')
                fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                util.debug("Can't perform incremental rsync of %s because " \
                           "unable to obtain exclusive lock on incremental " \
                           "backup reference point: %s. Exiting" \
                           % (lockFile), self._verbose)
                os.chdir("/")
                snapshot.release(self._propName)
                sys.exit(1)

        self._rsyncProc = RsyncProcess(sourceDir,
                                       partialDir,
                                       linkDest,
                                       self._rsyncVerbose,
                                       logFile)

        # Notify the applet of current status via dbus
        self._bus.rsync_current(snapshot.name, self._queueLength)

        # Set umask temporarily so that rsync backups are read-only to
        # the owner by default. Rync will override this to match the
        # permissions of each snapshot as appropriate.
        origmask = os.umask(0222)
        util.debug("Starting rsync backup of '%s' to: %s" \
                   % (sourceDir, partialDir),
                   self._verbose)
        self._rsyncProc.start_backup()

        warningDone = False
        while self._rsyncProc.is_alive():
            if len(self._backups) > 0:
                # Monitor backup target capacity while we wait for rsync.
                capacity = util.get_filesystem_capacity(self._rsyncDir)
                if capacity > self._cleanupThreshold:
                    # Find backups older than qTime that could in theory
                    # be deleted in order to make room for the curtent
                    # pending item.
                    deleteables = self._find_deleteable_backups(qTime)
                    # Only generate annoying debug message once instead of
                    # every 5 seconds.
                    if warningDone == False:
                        util.debug("Backup device capacity exceeds %d%%. " \
                                   "Found %d deleteable backups for space " \
                                   "recovery." \
                                    % (capacity, len(deleteables)),
                                    self._verbose)
                        warningDone = True
                    if len(deleteables) > 0:
                        deleteables = self._recover_space(deleteables)
            time.sleep(5)

        try:
            self._rsyncProc._check_exit_code()
        except (RsyncTransferInterruptedError,
                RsyncTargetDisconnectedError,
                RsyncSourceVanishedError) as e:
            os.chdir("/")
            snapshot.release(self._propName)
            util.log_error(syslog.LOG_ERR, str(e))
            # These are recoverable, so exit for now and try again
            # later
            sys.exit(-1)

        except RsyncError as e:
            # If the backup device went offline we need to chdir
            # out of it or running further commands might fail.
            os.chdir("/")
            util.log_error(syslog.LOG_ERR,
                           "Unexpected rsync error encountered: \n" + \
                           str(e))
            util.log_error(syslog.LOG_ERR,
                           "Rsync log file location: %s" \
                           % (os.path.abspath(logFile)))
            util.log_error(syslog.LOG_ERR,
                           "Placing plugin into maintenance mode")
            self._smfInst.mark_maintenance()
            snapshot.release(self._propName)
            sys.exit(-1)

        finally:
            if lockFp:
                lockFp.close()
                os.unlink(lockFile)

        util.debug("Rsync process exited", self._verbose)
        os.umask(origmask)

        # Move the completed backup from the partial dir to the
        # the propert backup directory 
        util.debug("Renaming completed backup from %s to %s" \
                   % (partialDir, backupDir), self._verbose)
        os.rename(partialDir, backupDir)

        # Reset the mtime and atime properties of the backup directory so that
        # they match the snapshot creation time. This is extremely important
        # because the backup mechanism relies on it to determine backup times
        # and nearest matches for incremental rsync (linkDest)
        os.utime(backupDir, (long(ctime), long(ctime)))
        # Update the dictionary and time sorted list with ctime also
        self._backupTimes[targetDir][snapshot.snaplabel] = long(ctime)
        insort(self._backups, [long(ctime), os.path.abspath(backupDir)]) 
        snapshot.set_user_property(self._propName, "completed")
        snapshot.release(self._propName)
        self._currentQueueSet = remainingList
        
        # Now is a good time to clean out the directory:
        # Check to see if the backup just completed belonged to an
        # auto-snapshot schedule and whether older backups should get
        # deleted.
        if snapshot.snaplabel.find(autosnapsmf.SNAPLABELPREFIX) == 0:
            tempSchedule = None
            label = None
            for schedule in self._tempSchedules:
                label = "%s%s%s" % (autosnapsmf.SNAPLABELPREFIX,
                                    self._labelSeparator,
                                    schedule[0])
                if snapshot.snaplabel.find(label) == 0:
                    tempSchedule = schedule
                    break
            if tempSchedule == None:
                # Backup doesn't belong to a temporary schedule so 
                # nothing left to do
                return True

            keep = tempSchedule[3] # [schedule,interval,period,keep]
            schedBackups = [d for d in os.listdir(targetDir) if 
                            d.find(label) == 0]
            

            schedBackups = [d for d in dirList if 
                            d.find(label) == 0]
            # The minimum that can be kept around is one:
            # keeping zero is stupid since it might trigger
            # a total replication rather than an incremental
            # rsync replication.
            if len(schedBackups) <= 1:
                return True
            if len(schedBackups) <= keep:
                return True

            sortedBackupList = []
            for backup in schedBackups:
                stInfo = os.stat(backup)
                # List is sorted by mtime, oldest first
                insort(sortedBackupList, [stInfo.st_mtime, backup])
            purgeList = sortedBackupList[0:-keep]

            trash = os.path.join(self._rsyncDir,
                                 snapshot.fsname,
                                 rsyncsmf.RSYNCTRASHSUFFIX)
            if not os.path.exists(trash):
                os.makedirs(trash, 0755)
            for mtime,dirName in purgeList:
                trashDir = os.path.join(trash,
                                        dirName)
                # Perform a final sanity check to make sure a backup
                # directory and not a system directory is being purged.
                # If it doesn't contain the RSYNCDIRSUFFIX string a
                # ValueError will be raised.
                try:
                    os.getcwd().index(rsyncsmf.RSYNCDIRSUFFIX)
                    lockFp = None
                    lockFile = os.path.join(lockFileDir,
                                            dirName + ".lock")

                    if not os.path.exists(lockFileDir):
                        os.makedirs(lockFileDir, 0755)

                    try:
                        lockFp = open(lockFile, 'w')
                        fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except IOError:
                        util.debug("Can't move expired  backup %s to trash " \
                                   "because it is locked by another " \
                                   "process. Skipping" % (dirName),
                                   self._verbose)

                    util.debug("Moving expired rsync backup to trash:" \
                               " %s -> %s" % (dirName, trash),
                               self._verbose)
                    os.rename(dirName, trashDir)
                    # Release and delete lock file
                    lockFp.close()
                    os.unlink(lockFile)
                    # Remove its mtime key/value from self._backupTimes
                    del self._backupTimes[targetDir][dirName]
                    # Log file needs to be deleted too.
                    logFile = os.path.join(logDir,
                                            dirName + ".log")
                    try:
                        os.stat(logFile)
                        util.debug("Deleting rsync log file: %s" \
                                    % (os.path.abspath(logFile)),
                                    self._verbose)
                        os.unlink(logFile)
                    except OSError:
                        util.debug("Expected rsync log file not " \
                                    "found: %s"\
                                    % (os.path.abspath(logFile)),
                                    self._verbose)
                                                
                except ValueError:
                    util.log_error(syslog.LOG_ALERT,
                                    "Invalid attempt to delete " \
                                    "non-backup directory: %s\n" \
                                    "Placing plugin into " \
                                    "maintenance state" % (dirName))
                    self._smfInst.mark_maintenance()
                    sys.exit(-1)
        return True

def release_held_snapshots(propName):
    """
    Releases dangling user snapshot holds that could
    have occured during abnormal termination of a
    previous invocation of this command during a 
    previous rsync transfer.
    Returns a list of snapshots that had holds mathcing
    propName released.
    """ 
    # First narrow the list down by finding snapshots
    # with userref count > 0
    heldList = []
    released = []
    cmd = [zfs.ZFSCMD, "list", "-H",
           "-t", "snapshot",
           "-o", "userrefs,name"]
    outdata,errdata = util.run_command(cmd)
    for line in outdata.rstrip().split('\n'):
        holdCount,name = line.split()
        if int(holdCount) > 0:
            heldList.append(name)
    # Now check to see if any of those holds
    # match 'propName'
    for snapName in heldList:
        snapshot = zfs.Snapshot(snapName)
        holds = snapshot.holds()
        try:
            holds.index(propName)
            snapshot.release(propName)
            released.append(snapName)
        except ValueError:
            pass
    return released


def backup_name_to_snapshot_name(path):
    """Reconstructs the original snapshot based on an
       rsync backup's full path.
       Returns a zfs snapshot name.
    """
    head,snapLabel = os.path.split(path)
    sys,nodeName,rel,ver,arch = os.uname()
    prefix = os.path.join(rsyncsmf.RSYNCDIRPREFIX,
                          nodeName + '/')
    suffix = rsyncsmf.RSYNCDIRSUFFIX

    rsyncBaseDir,tail = head.split(prefix , 1)
    fsName = tail.split(suffix, 1)[0].rstrip('/')
    snapshotName = "%s@%s" % (fsName, snapLabel)
    return snapshotName

def list_pending_snapshots(propName):
    """
    Lists all snaphots which have 'propName" set locally.
    Resulting list is returned sorted in descending order
    of creation time (ie.newest first).
    Each element in the returned list is tuple of the form:
    [creationtime, snapshotname]
    """
    results = []
    snaplist = []
    sortsnaplist = []
    # The process for backing up snapshots is:
    # Identify all filesystem snapshots that have the (propName)
    # property set to "pending" on them. Back them up starting
    # with the oldest first.
    #
    # Unfortunately, there's no single zfs command that can
    # output a locally set user property and a creation timestamp
    # in one go. So this is done in two passes. The first pass
    # identifies snapshots that are tagged as "pending". The 
    # second pass uses the filtered results from the first pass
    # as arguments to zfs(1) to get creation times.
    cmd = [zfs.ZFSCMD, "get", "-H",
            "-s", "local",
            "-o", "name,value",
            propName]
    outdata,errdata = util.run_command(cmd)
    for line in outdata.rstrip().split('\n'):
        if len(line) > 1:
            line = line.split()
            results.append(line)

    for name,value in results:
        if value != "pending":
            # Already backed up. Skip it."
            continue
        if name.find('@') == -1:
            # Not a snapshot, and should not be set on a filesystem/volume
            # Ignore it.
            util.log_error(syslog.LOG_WARNING,
                           "Dataset: %s shouldn't have local property: %s" \
                           % (name, propName))
            continue
        snaplist.append(name)

    # Nothing pending so just return the empty list
    if len(snaplist) == 0:
        return snaplist

    cmd = [zfs.ZFSCMD, "get", "-p", "-H",
            "-o", "value,name",
            "creation"]
    cmd.extend(snaplist)

    outdata,errdata = util.run_command(cmd)
    for line in outdata.rstrip().split('\n'):
        ctimeStr,name = line.split()
        insort(sortsnaplist, tuple((long(ctimeStr), name)))
    sortsnaplist.reverse()
    return sortsnaplist


def main(argv):
    # This command needs to be executed by the super user (root) to
    # ensure that rsync has permissions to access all local filesystem
    # snapshots and to replicate permissions and ownership on the target
    # device
    if os.geteuid() != 0:
        head,tail = os.path.split(sys.argv[0])
        sys.stderr.write(tail + " can only be executed by root")
        sys.exit(-1)

    # This process needs to be run as a system wide single instance
    # only at any given time. So create a lockfile in /tmp and try
    # to obtain an exclusive lock on it. If we can't then another 
    # instance is running and already has a lock on it so just exit.
    lockFileDir = os.path.normpath(tempfile.gettempdir() + '/' + \
    							".time-slider")
    if not os.path.exists(lockFileDir):
            os.makedirs(lockFileDir, 0755)
    lockFile = os.path.join(lockFileDir, 'rsync-backup.lock')

    lockFp = open(lockFile, 'w')
    try:
        fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        sys.exit(2)

    # The SMF fmri of the time-slider plugin instance associated with
    # this command needs to be supplied as the argument immeditately
    # proceeding the command. ie. argv[1]
    try:
        pluginFMRI = sys.argv[1]
    except IndexError:
        # No FMRI provided. Probably a user trying to invoke the command
        # from the command line.
        sys.stderr.write("No time-slider plugin SMF instance FMRI defined. " \
                         "This plugin does not support command line " \
                         "execution. Exiting\n")
        sys.exit(-1)

    # Open up a syslog session
    syslog.openlog(sys.argv[0], 0, syslog.LOG_DAEMON)

    gobject.threads_init()
    # Tell dbus to use the gobject mainloop for async ops
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    dbus.mainloop.glib.threads_init()
    # Register a bus name with the system dbus daemon
    sysbus = dbus.SystemBus()
    busName = dbus.service.BusName("org.opensolaris.TimeSlider.plugin.rsync", sysbus)
    dbusObj = dbussvc.RsyncBackup(sysbus, \
        "/org/opensolaris/TimeSlider/plugin/rsync")

    mainLoop = gobject.MainLoop()
    backupQueue = BackupQueue(pluginFMRI, dbusObj, mainLoop)
    gobject.idle_add(backupQueue.backup_snapshot)
    mainLoop.run()
    sys.exit(0)

