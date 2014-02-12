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
import sys
import subprocess
import syslog
from bisect import insort

import time_slider.util
import time_slider.smf
import time_slider.zfs

# Set to True if SMF property value of "plugin/command" is "true"
verboseprop = "plugin/verbose"
propbasename = "org.opensolaris:time-slider-plugin"
print _("Do I work?")

def main(argv):

    # Check appropriate environment variables habe been supplied
    # by time-slider
    #
    # The label used for the snapshot set just taken, ie. the
    # component proceeding the "@" in the snapshot name
    snaplabel = os.getenv("AUTOSNAP_LABEL")
    # The SMF fmri of the auto-snapshot instance corresponding to
    # the snapshot set just taken.
    snapfmri = os.getenv("AUTOSNAP_FMRI")
    # The SMF fmri of the time-slider plugin instance associated with
    # this command.
    pluginfmri = os.getenv("PLUGIN_FMRI")

    if pluginfmri == None:
        sys.stderr.write("No time-slider plugin SMF instance FMRI defined. " \
                         "This plugin does not support command line "
                         "execution. Exiting\n")
        sys.exit(-1)
    syslog.openlog(pluginfmri, 0, syslog.LOG_DAEMON)

    cmd = [smf.SVCPROPCMD, "-p", verboseprop, pluginfmri]
    outdata,errdata = util.run_command(cmd)
    if outdata.rstrip() == "true":
        verbose = True
    else:
        verbose = False

    if snaplabel == None:
        log_error(syslog.LOG_ERR,
                  "No snapshot label defined. Exiting")
        sys.exit(-1)
    if snapfmri == None:
        log_error(syslog.LOG_ERR,
                  "No auto-snapshot SMF instance FMRI defined. Exiting")
        sys.exit(-1)

    schedule = snapfmri.rsplit(':', 1)[1]
    plugininstance = pluginfmri.rsplit(':', 1)[1]

    # The user property/tag used when tagging and holding zfs datasets
    propname = "%s:%s" % (propbasename, plugininstance)

    # Identifying snapshots is a two stage process.
    #
    # First: identify all snapshots matching the AUTOSNAP_LABEL
    # value passed in by the time-slider daemon.
    #
    # Second: we need to filter the results and ensure that the
    # filesystem/voluem corresponding to each snapshot is actually
    # tagged with the property (com.sun:auto-snapshot<:schedule>)
    #
    # This is necessary to avoid confusion whereby a snapshot might
    # have been sent|received from one zpool to another on the same
    # system. The received snapshot will show up in the first pass
    # results but is not actually part of the auto-snapshot set
    # created by time-slider. It also avoids incorrectly placing
    # zfs holds on the imported snapshots.

    datasets = zfs.Datasets()
    candidates = datasets.list_snapshots(snaplabel)
    originsets = datasets.list_auto_snapshot_sets(schedule)
    snappeddatasets = []
    snapnames = [name for [name,ctime] in candidates \
                 if name.split('@',1)[0] in originsets]


    # Place a hold on the the newly created snapshots so
    # they can be backed up without fear of being destroyed
    # before the backup gets a chance to complete.
    for snap in snapnames:
        snapshot = zfs.Snapshot(snap)
        holds = snapshot.holds()
        try:
            holds.index(propname)
        except ValueError:
            util.debug("Placing hold on %s" % (snap), verbose)
            snapshot.hold(propname)
        datasetname = snapshot.fsname
        # Insert datasetnames in alphabetically sorted order because
        # zfs receive falls over if it receives a child before the
        # parent if the "-F" option is not used.
        insort(snappeddatasets, datasetname)

    # Find out the receive command property value
    cmd = [smf.SVCPROPCMD, "-c", "-p", "receive/command", pluginfmri]
    outdata,errdata = util.run_command(cmd)
    # Strip out '\' characters inserted by svcprop
    recvcmd = outdata.strip().replace('\\', '').split()

    # Check to see if the receive command is accessible and executable
    try:
        statinfo = os.stat(recvcmd[0])
        other_x = (statinfo.st_mode & 01)
        if other_x == 0:
            log_error(syslog.LOG_ERR,
                      "Plugin: %s: Configured receive/command is not " \
                      "executable: %s" \
                      % (pluginfmri, outdata))
            maintenance(pluginfmri)
            sys.exit(-1)
    except OSError:
        log_error(syslog.LOG_ERR,
                  "Plugin: %s: Can not access the configured " \
                  "receive/command: %s" \
                  % (pluginfmri, outdata)) 
        maintenance(pluginfmri)   
        sys.exit(-1)

    for dataset in snappeddatasets:
        sendcmd = None
        prevsnapname = None
        ds = zfs.ReadableDataset(dataset)
        prevlabel = ds.get_user_property(propname)

        snapname = "%s@%s" % (ds.name, snaplabel)
        if (prevlabel == None or len(prevlabel) == 0):
            # No previous backup - send a full replication stream
            sendcmd = [zfs.ZFSCMD, "send", snapname]
            util.debug("No previous backup registered for %s" % ds.name, verbose)
        else:
            # A record of a previous backup exists.
            # Check that it exists to enable send of an incremental stream.
            prevsnapname = "%s@%s" % (ds.name, prevlabel)
            util.debug("Previously sent snapshot: %s" % prevsnapname, verbose)
            prevsnap = zfs.Snapshot(prevsnapname)
            if prevsnap.exists():
                sendcmd = [zfs.ZFSCMD, "send", "-i", prevsnapname, snapname]
            else:
                # This should not happen under normal operation since we
                # place a hold on the snapshot until it gets sent. So
                # getting here suggests that something else released the
                # hold on the snapshot, allowing it to get destroyed
                # prematurely.
                log_error(syslog.LOG_ERR,
                          "Previously sent snapshot no longer exists: %s" \
                          % prevsnapname)
                maintenance(pluginfmri)
                sys.exit(-1)
        
        
        # Invoke the send and receive commands via pfexec(1) since
        # we are not using the role's shell to take care of that
        # for us.
        sendcmd.insert(0, smf.PFCMD)
        recvcmd.insert(0, smf.PFCMD)

        try:
            sendP = subprocess.Popen(sendcmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     close_fds=True)
            recvP = subprocess.Popen(recvcmd,
                                     stdin=sendP.stdout,
                                     stderr=subprocess.PIPE,
                                     close_fds=True)

            recvout,recverr = recvP.communicate()
            recverrno = recvP.wait()
            sendout,senderr = sendP.communicate()
            senderrno = sendP.wait()

            if senderrno != 0:
                raise RuntimeError, "Send command: %s failed with exit code" \
                                    "%d. Error message: \n%s" \
                                    % (str(sendcmd), senderrno, senderr)
            if recverrno != 0:
                raise RuntimeError, "Receive command %s failed with exit " \
                                    "code %d. Error message: \n%s" \
                                    % (str(recvcmd), recverrno, recverr)

            if prevsnapname != None:
                util.debug("Releasing hold on %s" % (prevsnapname), verbose)
                snapshot = zfs.Snapshot(prevsnapname)
                util.debug("Releasing hold on previous snapshot: %s" \
                      % (prevsnapname),
                      verbose)
                snapshot.release(propname)
        except Exception, message:
            log_error(syslog.LOG_ERR,
                      "Error during snapshot send/receive operation: %s" \
                      % (message))

            maintenance(pluginfmri)
            sys.exit(-1)            

        # Finally, after success, make a record of the latest backup
        # and release the old snapshot.
        ds.set_user_property(propname, snaplabel)
        util.debug("Sending of \"%s\"snapshot streams completed" \
              % (snaplabel),
              verbose)

def maintenance(svcfmri):
    log_error(syslog.LOG_ERR,
              "Placing plugin into maintenance state")
    cmd = [smf.SVCADMCMD, "mark", "maintenance", svcfmri]
    subprocess.Popen(cmd, close_fds=True)

def log_error(loglevel, message):
    syslog.syslog(loglevel, message + '\n')
    sys.stderr.write(message + '\n')

