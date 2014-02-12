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
import re
import threading
from bisect import insort, bisect_left, bisect_right

import util

BYTESPERMB = 1048576

# Commonly used command paths
PFCMD = "/usr/bin/pfexec"
ZFSCMD = "/usr/sbin/zfs"
ZPOOLCMD = "/usr/sbin/zpool"


class Datasets(Exception):
    """
    Container class for all zfs datasets. Maintains a centralised
    list of datasets (generated on demand) and accessor methods. 
    Also allows clients to notify when a refresh might be necessary.
    """
    # Class wide instead of per-instance in order to avoid duplication
    filesystems = None
    volumes = None
    snapshots = None
    
    # Mutex locks to prevent concurrent writes to above class wide
    # dataset lists.
    _filesystemslock = threading.Lock()
    _volumeslock = threading.Lock()
    snapshotslock = threading.Lock()

    def create_auto_snapshot_set(self, label, tag = None):
        """
        Create a complete set of snapshots as if this were
        for a standard zfs-auto-snapshot operation.
        
        Keyword arguments:
        label:
            A label to apply to the snapshot name. Cannot be None.
        tag:
            A string indicating one of the standard auto-snapshot schedules
            tags to check (eg. "frequent" for will map to the tag:
            com.sun:auto-snapshot:frequent). If specified as a zfs property
            on a zfs dataset, the property corresponding to the tag will 
            override the wildcard property: "com.sun:auto-snapshot"
            Default value = None
        """
        everything = []
        included = []
        excluded = []
        single = []
        recursive = []
        finalrecursive = []

        # Get auto-snap property in two passes. First with the schedule
        # specific tag override value, then with the general property value
        cmd = [ZFSCMD, "list", "-H", "-t", "filesystem,volume",
               "-o", "name,com.sun:auto-snapshot", "-s", "name"]
        if tag:
            overrideprop = "com.sun:auto-snapshot:" + tag
            scmd = [ZFSCMD, "list", "-H", "-t", "filesystem,volume",
                    "-o", "name," + overrideprop, "-s", "name"]
            outdata,errdata = util.run_command(scmd)
            for line in outdata.rstrip().split('\n'):
                line = line.split()
                # Skip over unset values. 
                if line[1] == "-":
                    continue
                # Add to everything list. This is used later
                # for identifying parents/children of a given
                # filesystem or volume.
                everything.append(line[0])
                if line[1] == "true":
                    included.append(line[0])
                elif line[1] == "false":
                    excluded.append(line[0])
        # Now use the general property. If no value
        # was set in the first pass, we set it here.
        outdata,errdata = util.run_command(cmd)
        for line in outdata.rstrip().split('\n'):
            line = line.split()
            idx = bisect_right(everything, line[0])
            if len(everything) == 0 or \
               everything[idx-1] != line[0]:           
                # Dataset is neither included nor excluded so far
                if line[1] == "-":
                    continue
                everything.insert(idx, line[0])
                if line[1] == "true":
                    included.insert(0, line[0])
                elif line[1] == "false":
                    excluded.append(line[0])

        # Now figure out what can be recursively snapshotted and what
        # must be singly snapshotted. Single snapshot restrictions apply
        # to those datasets who have a child in the excluded list.
        # 'included' is sorted in reverse alphabetical order. 
        for datasetname in included:
            excludedchild = False
            idx = bisect_right(everything, datasetname)
            children = [name for name in everything[idx:] if \
                        name.find(datasetname) == 0]
            for child in children:
                idx = bisect_left(excluded, child)
                if idx < len(excluded) and excluded[idx] == child:
                    excludedchild = True
                    single.append(datasetname)
                    break
            if excludedchild == False:
                # We want recursive list sorted in alphabetical order
                # so insert instead of append to the list.
                recursive.insert(0, datasetname)

        for datasetname in recursive:
            parts = datasetname.rsplit('/', 1)
            parent = parts[0]
            if parent == datasetname:
                # Root filesystem of the Zpool, so
                # this can't be inherited and must be
                # set locally.
                finalrecursive.append(datasetname)
                continue
            idx = bisect_right(recursive, parent)
            if len(recursive) > 0 and \
               recursive[idx-1] == parent:
                # Parent already marked for recursive snapshot: so skip
                continue
            else:
                finalrecursive.append(datasetname)

        for name in finalrecursive:
            dataset = ReadWritableDataset(name)
            dataset.create_snapshot(label, True)
        for name in single:
            dataset = ReadWritableDataset(name)
            dataset.create_snapshot(label, False)

    def list_auto_snapshot_sets(self, tag = None):
        """
        Returns a list of zfs filesystems and volumes tagged with
        the "com.sun:auto-snapshot" property set to "true", either
        set locally or inherited. Snapshots are excluded from the
        returned result.

        Keyword Arguments:
        tag:
            A string indicating one of the standard auto-snapshot schedules
            tags to check (eg. "frequent" will map to the tag:
            com.sun:auto-snapshot:frequent). If specified as a zfs property
            on a zfs dataset, the property corresponding to the tag will 
            override the wildcard property: "com.sun:auto-snapshot"
            Default value = None
        """
        #Get auto-snap property in two passes. First with the global
        #value, then overriding with the label/schedule specific value

        included = []
        excluded = []

        cmd = [ZFSCMD, "list", "-H", "-t", "filesystem,volume",
               "-o", "name,com.sun:auto-snapshot", "-s", "name"]
        if tag:
            overrideprop = "com.sun:auto-snapshot:" + tag
            scmd = [ZFSCMD, "list", "-H", "-t", "filesystem,volume",
                    "-o", "name," + overrideprop, "-s", "name"]
            outdata,errdata = util.run_command(scmd)
            for line in outdata.rstrip().split('\n'):
                line = line.split()
                if line[1] == "true":
                    included.append(line[0])
                elif line[1] == "false":
                    excluded.append(line[0])
        outdata,errdata = util.run_command(cmd)
        for line in outdata.rstrip().split('\n'):
            line = line.split()
            # Only set values that aren't already set. Don't override
            try:
                included.index(line[0])
                continue
            except ValueError:
                try:
                    excluded.index(line[0])
                    continue
                except ValueError:
                    # Dataset is not listed in either list.
                    if line[1] == "true":
                        included.append(line[0])
        return included

    def list_filesystems(self, pattern = None):
        """
        List pattern matching filesystems sorted by name.
        
        Keyword arguments:
        pattern -- Filter according to pattern (default None)
        """
        filesystems = []
        # Need to first ensure no other thread is trying to
        # build this list at the same time.
        Datasets._filesystemslock.acquire()
        if Datasets.filesystems == None:
            Datasets.filesystems = []
            cmd = [ZFSCMD, "list", "-H", "-t", "filesystem", \
                   "-o", "name,mountpoint", "-s", "name"]
            try:
                p = subprocess.Popen(cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     close_fds=True)
                outdata,errdata = p.communicate()
                err = p.wait()
            except OSError, message:
                raise RuntimeError, "%s subprocess error:\n %s" % \
                                    (cmd, str(message))
            if err != 0:
                Datasets._filesystemslock.release()
                raise RuntimeError, '%s failed with exit code %d\n%s' % \
                                    (str(cmd), err, errdata)
            for line in outdata.rstrip().split('\n'):
                line = line.rstrip().split()
                Datasets.filesystems.append([line[0], line[1]])
        Datasets._filesystemslock.release()

        if pattern == None:
            filesystems = Datasets.filesystems[:]
        else:
            # Regular expression pattern to match "pattern" parameter.
            regexpattern = ".*%s.*" % pattern
            patternobj = re.compile(regexpattern)

            for fsname,fsmountpoint in Datasets.filesystems:
                patternmatchobj = re.match(patternobj, fsname)
                if patternmatchobj != None:
                    filesystems.append(fsname, fsmountpoint)
        return filesystems

    def list_volumes(self, pattern = None):
        """
        List pattern matching volumes sorted by name.
        
        Keyword arguments:
        pattern -- Filter according to pattern (default None)
        """
        volumes = []
        Datasets._volumeslock.acquire()
        if Datasets.volumes == None:
            Datasets.volumes = []
            cmd = [ZFSCMD, "list", "-H", "-t", "volume", \
                   "-o", "name", "-s", "name"]
            try:
                p = subprocess.Popen(cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     close_fds=True)
                outdata,errdata = p.communicate()
                err = p.wait()
            except OSError, message:
                raise RuntimeError, "%s subprocess error:\n %s" % \
                                    (cmd, str(message))
            if err != 0:
                Datasets._volumeslock.release()
                raise RuntimeError, '%s failed with exit code %d\n%s' % \
                                    (str(cmd), err, errdata)
            for line in outdata.rstrip().split('\n'):
                Datasets.volumes.append(line.rstrip())
        Datasets._volumeslock.release()

        if pattern == None:
            volumes = Datasets.volumes[:]
        else:
            # Regular expression pattern to match "pattern" parameter.
            regexpattern = ".*%s.*" % pattern
            patternobj = re.compile(regexpattern)

            for volname in Datasets.volumes:
                patternmatchobj = re.match(patternobj, volname)
                if patternmatchobj != None:
                    volumes.append(volname)
        return volumes

    def list_snapshots(self, pattern = None):
        """
        List pattern matching snapshots sorted by creation date.
        Oldest listed first
        
        Keyword arguments:
        pattern -- Filter according to pattern (default None)
        """
        snapshots = []
        Datasets.snapshotslock.acquire()
        if Datasets.snapshots == None:
            Datasets.snapshots = []
            snaps = []
            cmd = [ZFSCMD, "get", "-H", "-p", "-o", "value,name", "creation"]
            try:
                p = subprocess.Popen(cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     close_fds=True)
                outdata,errdata = p.communicate()
                err= p.wait()
            except OSError, message:
                Datasets.snapshotslock.release()
                raise RuntimeError, "%s subprocess error:\n %s" % \
                                    (cmd, str(message))
            if err != 0:
                Datasets.snapshotslock.release()
                raise RuntimeError, '%s failed with exit code %d\n%s' % \
                                    (str(cmd), err, errdata)
            for dataset in outdata.rstrip().split('\n'):
                if re.search("@", dataset):
                    insort(snaps, dataset.split())
            for snap in snaps:
                Datasets.snapshots.append([snap[1], long(snap[0])])
        if pattern == None:
            snapshots = Datasets.snapshots[:]
        else:
            # Regular expression pattern to match "pattern" parameter.
            regexpattern = ".*@.*%s" % pattern
            patternobj = re.compile(regexpattern)

            for snapname,snaptime in Datasets.snapshots:
                patternmatchobj = re.match(patternobj, snapname)
                if patternmatchobj != None:
                    snapshots.append([snapname, snaptime])
        Datasets.snapshotslock.release()
        return snapshots

    def list_cloned_snapshots(self):
        """
        Returns a list of snapshots that have cloned filesystems
        dependent on them.
        Snapshots with cloned filesystems can not be destroyed
        unless dependent cloned filesystems are first destroyed.
        """
        cmd = [ZFSCMD, "list", "-H", "-o", "origin"]
        outdata,errdata = util.run_command(cmd)
        result = []
        for line in outdata.rstrip().split('\n'):
            details = line.rstrip()
            if details != "-":
                try:
                    result.index(details)
                except ValueError:
                    result.append(details)
        return result

    def list_held_snapshots(self):
        """
        Returns a list of snapshots that have a "userrefs"
        property value of greater than 0. Resul list is
        sorted in order of creation time. Oldest listed first.
        """
        cmd = [ZFSCMD, "list", "-H",
               "-t", "snapshot",
               "-s", "creation",
               "-o", "userrefs,name"]
        outdata,errdata = util.run_command(cmd)
        result = []
        for line in outdata.rstrip().split('\n'):
            details = line.split()
            if details[0] != "0":
                result.append(details[1])
        return result

    def refresh_snapshots(self):
        """
        Should be called when snapshots have been created or deleted
        and a rescan should be performed. Rescan gets deferred until
        next invocation of zfs.Dataset.list_snapshots()
        """
        # FIXME in future.
        # This is a little sub-optimal because we should be able to modify
        # the snapshot list in place in some situations and regenerate the 
        # snapshot list without calling out to zfs(1m). But on the
        # pro side, we will pick up any new snapshots since the last
        # scan that we would be otherwise unaware of.
        Datasets.snapshotslock.acquire()
        Datasets.snapshots = None
        Datasets.snapshotslock.release()


class ZPool:
    """
    Base class for ZFS storage pool objects
    """
    def __init__(self, name):
        self.name = name
        self.health = self.__get_health()
        self.__datasets = Datasets()
        self.__filesystems = None
        self.__volumes = None
        self.__snapshots = None

    def __get_health(self):
        """
        Returns pool health status: 'ONLINE', 'DEGRADED' or 'FAULTED'
        """
        cmd = [ZPOOLCMD, "list", "-H", "-o", "health", self.name]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip()
        return result

    def get_capacity(self):
        """
        Returns the percentage of total pool storage in use.
        Calculated based on the "used" and "available" properties
        of the pool's top-level filesystem because the values account
        for reservations and quotas of children in their calculations,
        giving a more practical indication of how much capacity is used
        up on the pool.
        """
        if self.health == "FAULTED":
            raise ZPoolFaultedError("Can not determine capacity of zpool: %s" \
                                    "because it is in a FAULTED state" \
                                    % (self.name))

        cmd = [ZFSCMD, "get", "-H", "-p", "-o", "value", \
               "used,available", self.name]
        outdata,errdata = util.run_command(cmd)
        _used,_available = outdata.rstrip().split('\n')
        used = float(_used)
        available = float(_available) 
        return 100.0 * used/(used + available)

    def get_available_size(self):
        """
        How much unused space is available for use on this Zpool.
        Answer in bytes.
        """
        # zpool(1) doesn't report available space in
        # units suitable for calulations but zfs(1)
        # can so use it to find the value for the
        # filesystem matching the pool.
        # The root filesystem of the pool is simply
        # the pool name.
        poolfs = Filesystem(self.name)
        avail = poolfs.get_available_size()
        return avail

    def get_used_size(self):
        """
        How much space is in use on this Zpool.
        Answer in bytes
        """
        # Same as ZPool.get_available_size(): zpool(1)
        # doesn't generate suitable out put so use
        # zfs(1) on the toplevel filesystem
        if self.health == "FAULTED":
            raise ZPoolFaultedError("Can not determine used size of zpool: %s" \
                                    "because it is in a FAULTED state" \
                                    % (self.name))
        poolfs = Filesystem(self.name)
        used = poolfs.get_used_size()
        return used

    def list_filesystems(self):
        """
        Return a list of filesystems on this Zpool.
        List is sorted by name.
        """
        if self.__filesystems == None:
            result = []
            # Provides pre-sorted filesystem list
            for fsname,fsmountpoint in self.__datasets.list_filesystems():
                if re.match(self.name, fsname):
                    result.append([fsname, fsmountpoint])
            self.__filesystems = result
        return self.__filesystems

    def list_volumes(self):
        """
        Return a list of volumes (zvol) on this Zpool
        List is sorted by name
        """
        if self.__volumes == None:
            result = []
            regexpattern = "^%s" % self.name
            patternobj = re.compile(regexpattern)
            for volname in self.__datasets.list_volumes():
                patternmatchobj = re.match(patternobj, volname)
                if patternmatchobj != None:
                    result.append(volname)
            result.sort()
            self.__volumes = result
        return self.__volumes

    def list_auto_snapshot_sets(self, tag = None):
        """
        Returns a list of zfs filesystems and volumes tagged with
        the "com.sun:auto-snapshot" property set to "true", either
        set locally or inherited. Snapshots are excluded from the
        returned result. Results are not sorted.

        Keyword Arguments:
        tag:
            A string indicating one of the standard auto-snapshot schedules
            tags to check (eg. "frequent" will map to the tag:
            com.sun:auto-snapshot:frequent). If specified as a zfs property
            on a zfs dataset, the property corresponding to the tag will 
            override the wildcard property: "com.sun:auto-snapshot"
            Default value = None
        """
        result = []
        allsets = self.__datasets.list_auto_snapshot_sets(tag)
        if len(allsets) == 0:
            return result

        regexpattern = "^%s" % self.name
        patternobj = re.compile(regexpattern)
        for datasetname in allsets:
            patternmatchobj = re.match(patternobj, datasetname)
            if patternmatchobj != None:
                result.append(datasetname)
        return result

    def list_snapshots(self, pattern = None):
        """
        List pattern matching snapshots sorted by creation date.
        Oldest listed first
           
        Keyword arguments:
        pattern -- Filter according to pattern (default None)   
        """
        # If there isn't a list of snapshots for this dataset
        # already, create it now and store it in order to save
        # time later for potential future invocations.
        Datasets.snapshotslock.acquire()
        if Datasets.snapshots == None:
            self.__snapshots = None
        Datasets.snapshotslock.release()
        if self.__snapshots == None:
            result = []
            regexpattern = "^%s.*@"  % self.name
            patternobj = re.compile(regexpattern)
            for snapname,snaptime in self.__datasets.list_snapshots():
                patternmatchobj = re.match(patternobj, snapname)
                if patternmatchobj != None:
                    result.append([snapname, snaptime])
            # Results already sorted by creation time
            self.__snapshots = result
        if pattern == None:
            return self.__snapshots
        else:
            snapshots = []
            regexpattern = "^%s.*@.*%s" % (self.name, pattern)
            patternobj = re.compile(regexpattern)
            for snapname,snaptime in self.__snapshots:
                patternmatchobj = re.match(patternobj, snapname)
                if patternmatchobj != None:
                    snapshots.append([snapname, snaptime])
            return snapshots

    def __str__(self):
        return_string = "ZPool name: " + self.name
        return_string = return_string + "\n\tHealth: " + self.health
        try:
            return_string = return_string + \
                            "\n\tUsed: " + \
                            str(self.get_used_size()/BYTESPERMB) + "Mb"
            return_string = return_string + \
                            "\n\tAvailable: " + \
                            str(self.get_available_size()/BYTESPERMB) + "Mb"
            return_string = return_string + \
                            "\n\tCapacity: " + \
                            str(self.get_capacity()) + "%"
        except ZPoolFaultedError:
            pass
        return return_string


class ReadableDataset:
    """
    Base class for Filesystem, Volume and Snapshot classes
    Provides methods for read only operations common to all.
    """
    def __init__(self, name, creation = None):
        self.name = name
        self.__creationTime = creation
        self.datasets = Datasets()

    def __str__(self):
        return_string = "ReadableDataset name: " + self.name + "\n"
        return return_string

    def get_creation_time(self):
        if self.__creationTime == None:
            cmd = [ZFSCMD, "get", "-H", "-p", "-o", "value", "creation",
                   self.name]
            outdata,errdata = util.run_command(cmd)
            self.__creationTime = long(outdata.rstrip())
        return self.__creationTime

    def exists(self):
        """
        Returns True if the dataset is still existent on the system.
        False otherwise
        """
        # Test existance of the dataset by checking the output of a 
        # simple zfs get command on the snapshot
        cmd = [ZFSCMD, "get", "-H", "-o", "name", "type", self.name]
        try:
            p = subprocess.Popen(cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 close_fds=True)
            outdata,errdata = p.communicate()
            err = p.wait()
        except OSError, message:
            raise RuntimeError, "%s subprocess error:\n %s" % \
                            (command, str(message))
        if err != 0:
            # Doesn't exist
            return False

        result = outdata.rstrip()
        if result == self.name:
            return True
        else:
            return False

    def get_used_size(self):
        cmd = [ZFSCMD, "get", "-H", "-p", "-o", "value", "used", self.name]
        outdata,errdata = util.run_command(cmd)
        return long(outdata.rstrip())

    def get_user_property(self, prop, local=False):
        if local == True:
            cmd = [ZFSCMD, "get", "-s", "local", "-H", "-o", "value", prop, self.name]
        else:
            cmd = [ZFSCMD, "get", "-H", "-o", "value", prop, self.name]
        outdata,errdata = util.run_command(cmd)
        return outdata.rstrip()

    def set_user_property(self, prop, value):
        cmd = [PFCMD, ZFSCMD, "set", "%s=%s" % (prop, value), self.name]
        outdata,errdata = util.run_command(cmd)
    
    def unset_user_property(self, prop):
        cmd = [PFCMD, ZFSCMD, "inherit", prop, self.name]
        outdata,errdata = util.run_command(cmd)

class Snapshot(ReadableDataset):
    """
    ZFS Snapshot object class.
    Provides information and operations specfic to ZFS snapshots
    """    
    def __init__(self, name, creation = None):
        """
        Keyword arguments:
        name -- Name of the ZFS snapshot
        creation -- Creation time of the snapshot if known (Default None)
        """
        ReadableDataset.__init__(self, name, creation)
        self.fsname, self.snaplabel = self.__split_snapshot_name()
        self.poolname = self.__get_pool_name()

    def __get_pool_name(self):
        name = self.fsname.split("/", 1)
        return name[0]

    def __split_snapshot_name(self):
        name = self.name.split("@", 1)
        # Make sure this is really a snapshot and not a
        # filesystem otherwise a filesystem could get 
        # destroyed instead of a snapshot. That would be
        # really really bad.
        if name[0] == self.name:
            raise SnapshotError("\'%s\' is not a valid snapshot name" \
                                % (self.name))
        return name[0],name[1]

    def get_referenced_size(self):
        """
        How much unique storage space is used by this snapshot.
        Answer in bytes
        """
        cmd = [ZFSCMD, "get", "-H", "-p", \
               "-o", "value", "referenced", \
               self.name]
        outdata,errdata = util.run_command(cmd)
        return long(outdata.rstrip())

    def list_children(self):
        """Returns a recursive list of child snapshots of this snapshot"""
        cmd = [ZFSCMD,
               "list", "-t", "snapshot", "-H", "-r", "-o", "name",
               self.fsname]
        outdata,errdata = util.run_command(cmd)
        result = []
        for line in outdata.rstrip().split('\n'):
            if re.search("@%s" % (self.snaplabel), line) and \
                line != self.name:
                    result.append(line)
        return result

    def has_clones(self):
        """Returns True if the snapshot has any dependent clones"""
        cmd = [ZFSCMD, "list", "-H", "-o", "origin,name"]
        outdata,errdata = util.run_command(cmd)
        for line in outdata.rstrip().split('\n'):
            details = line.rstrip().split()
            if details[0] == self.name and \
                details[1] != '-':
                return True
        return False

    def destroy(self, deferred=True):
        """
        Permanently remove this snapshot from the filesystem
        Performs deferred destruction by default.
        """
        # Be sure it genuninely exists before trying to destroy it
        if self.exists() == False:
            return
        if deferred == False:
            cmd = [PFCMD, ZFSCMD, "destroy", self.name]
        else:
            cmd = [PFCMD, ZFSCMD, "destroy", "-d", self.name]

        outdata,errdata = util.run_command(cmd)
        # Clear the global snapshot cache so that a rescan will be
        # triggered on the next call to Datasets.list_snapshots()
        self.datasets.refresh_snapshots()

    def hold(self, tag):
        """
        Place a hold on the snapshot with the specified "tag" string.
        """
        # FIXME - fails if hold is already held
        # Be sure it genuninely exists before trying to place a hold
        if self.exists() == False:
            return

        cmd = [PFCMD, ZFSCMD, "hold", tag, self.name]
        outdata,errdata = util.run_command(cmd)

    def holds(self):
        """
        Returns a list of user hold tags for this snapshot
        """
        cmd = [ZFSCMD, "holds", self.name]
        results = []
        outdata,errdata = util.run_command(cmd)

        for line in outdata.rstrip().split('\n'):
            if len(line) == 0:
                continue
            # The first line heading columns are  NAME TAG TIMESTAMP
            # Filter that line out.
            line = line.split()
            if (line[0] != "NAME" and line[1] != "TAG"):
                results.append(line[1])
        return results

    def release(self, tag,):
        """
        Release the hold on the snapshot with the specified "tag" string.
        """
        # FIXME raises exception if no hold exists.
        # Be sure it genuninely exists before trying to destroy it
        if self.exists() == False:
            return

        cmd = [PFCMD, ZFSCMD, "release", tag, self.name]

        outdata,errdata = util.run_command(cmd)
        # Releasing the snapshot might cause it get automatically
        # deleted by zfs.
        # Clear the global snapshot cache so that a rescan will be
        # triggered on the next call to Datasets.list_snapshots()
        self.datasets.refresh_snapshots()


    def __str__(self):
        return_string = "Snapshot name: " + self.name
        return_string = return_string + "\n\tCreation time: " \
                        + str(self.get_creation_time())
        return_string = return_string + "\n\tUsed Size: " \
                        + str(self.get_used_size())
        return_string = return_string + "\n\tReferenced Size: " \
                        + str(self.get_referenced_size())
        return return_string


class ReadWritableDataset(ReadableDataset):
    """
    Base class for ZFS filesystems and volumes.
    Provides methods for operations and properties
    common to both filesystems and volumes.
    """
    def __init__(self, name, creation = None):
        ReadableDataset.__init__(self, name, creation)
        self.__snapshots = None

    def __str__(self):
        return_string = "ReadWritableDataset name: " + self.name + "\n"
        return return_string

    def get_auto_snap(self, schedule = None):
        if schedule:
            cmd = [ZFSCMD, "get", "-H", "-o", "value", \
               "com.sun:auto-snapshot", self.name]
        cmd = [ZFSCMD, "get", "-H", "-o", "value", \
               "com.sun:auto-snapshot", self.name]
        outdata,errdata = util.run_command(cmd)
        if outdata.rstrip() == "true":
            return True
        else:
            return False

    def get_available_size(self):
        cmd = [ZFSCMD, "get", "-H", "-p", "-o", "value", "available", \
               self.name]
        outdata,errdata = util.run_command(cmd)
        return long(outdata.rstrip())

    def create_snapshot(self, snaplabel, recursive = False):
        """
        Create a snapshot for the ReadWritable dataset using the supplied
        snapshot label.

        Keyword Arguments:
        snaplabel:
            A string to use as the snapshot label.
            The bit that comes after the "@" part of the snapshot
            name.
        recursive:
            Recursively snapshot childfren of this dataset.
            Default = False
        """
        cmd = [PFCMD, ZFSCMD, "snapshot"]
        if recursive == True:
            cmd.append("-r")
        cmd.append("%s@%s" % (self.name, snaplabel))
        outdata,errdata = util.run_command(cmd, False)
	if errdata:
	  print errdata
        self.datasets.refresh_snapshots()

    def list_children(self):
        
        # Note, if more dataset types ever come around they will
        # need to be added to the filsystem,volume args below.
        # Not for the forseeable future though.
        cmd = [ZFSCMD, "list", "-H", "-r", "-t", "filesystem,volume",
               "-o", "name", self.name]
        outdata,errdata = util.run_command(cmd)
        result = []
        for line in outdata.rstrip().split('\n'):
            if line.rstrip() != self.name:
                result.append(line.rstrip())
        return result


    def list_snapshots(self, pattern = None):
        """
        List pattern matching snapshots sorted by creation date.
        Oldest listed first
           
        Keyword arguments:
        pattern -- Filter according to pattern (default None)   
        """
        # If there isn't a list of snapshots for this dataset
        # already, create it now and store it in order to save
        # time later for potential future invocations.
        Datasets.snapshotslock.acquire()
        if Datasets.snapshots == None:
            self.__snapshots = None
        Datasets.snapshotslock.release()
        if self.__snapshots == None:
            result = []
            regexpattern = "^%s@" % self.name
            patternobj = re.compile(regexpattern)
            for snapname,snaptime in self.datasets.list_snapshots():
                patternmatchobj = re.match(patternobj, snapname)
                if patternmatchobj != None:
                    result.append([snapname, snaptime])
            # Results already sorted by creation time
            self.__snapshots = result
        if pattern == None:
            return self.__snapshots
        else:
            snapshots = []
            regexpattern = "^%s@.*%s" % (self.name, pattern)
            patternobj = re.compile(regexpattern)
            for snapname,snaptime in self.__snapshots:
                patternmatchobj = re.match(patternobj, snapname)
                if patternmatchobj != None:
                    snapshots.append(snapname)
            return snapshots

    def set_auto_snap(self, include, inherit = False):
        if inherit == True:
            self.unset_user_property("com.sun:auto-snapshot")
        else:
            if include == True:
                value = "true"
            else:
                value = "false"
            self.set_user_property("com.sun:auto-snapshot", value)

        return


class Filesystem(ReadWritableDataset):
    """ZFS Filesystem class"""
    def __init__(self, name, mountpoint = None):
        ReadWritableDataset.__init__(self, name)
        self.__mountpoint = mountpoint

    def __str__(self):
        return_string = "Filesystem name: " + self.name + \
                        "\n\tMountpoint: " + self.get_mountpoint() + \
                        "\n\tMounted: " + str(self.is_mounted()) + \
                        "\n\tAuto snap: " + str(self.get_auto_snap())
        return return_string

    def get_mountpoint(self):
        if (self.__mountpoint == None):
            cmd = [ZFSCMD, "get", "-H", "-o", "value", "mountpoint", \
                   self.name]
            outdata,errdata = util.run_command(cmd)
            result = outdata.rstrip()
            self.__mountpoint = result
        return self.__mountpoint

    def is_mounted(self):
        cmd = [ZFSCMD, "get", "-H", "-o", "value", "mounted", \
               self.name]
        outdata,errdata = util.run_command(cmd)
        result = outdata.rstrip()
        if result == "yes":
            return True
        else:
            return False

    def list_children(self):
        cmd = [ZFSCMD, "list", "-H", "-r", "-t", "filesystem", "-o", "name",
               self.name]
        outdata,errdata = util.run_command(cmd)
        result = []
        for line in outdata.rstrip().split('\n'):
            if line.rstrip() != self.name:
                result.append(line.rstrip())
        return result


class Volume(ReadWritableDataset):
    """
    ZFS Volume Class
    This is basically just a stub and does nothing
    unique from ReadWritableDataset parent class.
    """
    def __init__(self, name):
        ReadWritableDataset.__init__(self, name)

    def __str__(self):
        return_string = "Volume name: " + self.name + "\n"
        return return_string


class ZFSError(Exception):
    """Generic base class for ZPoolFaultedError and SnapshotError

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)


class ZPoolFaultedError(ZFSError):
    """Exception raised for queries made against ZPools that
       are in a FAULTED state

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, msg):
        ZFSError.__init__(self, msg)


class SnapshotError(ZFSError):
    """Exception raised for invalid snapshot names provided to
       Snapshot() constructor.

    Attributes:
        msg -- explanation of the error
    """
    def __init__(self, msg):
        ZFSError.__init__(self, msg)


def list_zpools():
    """Returns a list of all zpools on the system"""
    result = []
    cmd = [ZPOOLCMD, "list", "-H", "-o", "name"]
    outdata,errdata = util.run_command(cmd)
    for line in outdata.rstrip().split('\n'):
        result.append(line.rstrip())
    return result


if __name__ == "__main__":
    for zpool in list_zpools():
        pool = ZPool(zpool)
        print pool
        for filesys,mountpoint in pool.list_filesystems():
            fs = Filesystem(filesys, mountpoint)
            print fs
            print "\tSnapshots:"
            for snapshot, snaptime in fs.list_snapshots():
                snap = Snapshot(snapshot, snaptime)
                print "\t\t" + snap.name

        for volname in pool.list_volumes():
            vol = Volume(volname)
            print vol
            print "\tSnapshots:"
            for snapshot, snaptime in vol.list_snapshots():
                snap = Snapshot(snapshot, snaptime)
                print "\t\t" + snap.name

