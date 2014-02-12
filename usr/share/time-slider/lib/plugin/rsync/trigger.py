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

import rsyncsmf
from time_slider import util, smf, zfs

# Set to True if SMF property value of "plugin/command" is "true"
verboseprop = "plugin/verbose"
propbasename = "org.opensolaris:time-slider-plugin"


def main(argv):
    # Check that appropriate environment variables have been
    # provided by time-sliderd
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
                  "No snapshot label provided. Exiting")
        sys.exit(-1)
    if snapfmri == None:
        log_error(syslog.LOG_ERR,
                  "No auto-snapshot SMF instance FMRI provided. Exiting")
        sys.exit(-1)

    schedule = snapfmri.rsplit(':', 1)[1]
    plugininstance = pluginfmri.rsplit(':', 1)[1]

    # The user property/tag used when tagging and holding zfs datasets
    propname = "%s:%s" % (propbasename, plugininstance)

    # Identifying snapshots is a 3 stage process.
    #
    # First: identify all snapshots matching the AUTOSNAP_LABEL
    # value passed in by the time-slider daemon.
    #
	# Second: Filter out snapshots of volumes, since rsync can only
    # back up filesystems.
    #
    # Third: we need to filter the results and ensure that the
    # filesystem corresponding to each snapshot is actually
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
    autosnapsets = datasets.list_auto_snapshot_sets(schedule)
    autosnapfs = [name for [name,mount] in datasets.list_filesystems() \
                   if name in autosnapsets]
    snappeddatasets = []
    snapnames = [name for [name,ctime] in candidates \
                 if name.split('@',1)[0] in autosnapfs]

    # Mark the snapshots with a user property. Doing this instead of
    # placing a physical hold on the snapshot allows time-slider to
    # expire the snapshots naturally or destroy them if a zpool fills
    # up and triggers a remedial cleanup.
    # It also prevents the possiblity of leaving snapshots lying around
    # indefinitely on the system if the plugin SMF instance becomes 
    # disabled or having to release a pile of held snapshots.
    # We set org.opensolaris:time-slider-plugin:<instance> to "pending",
    # indicate
    snapshots = []
    for snap in snapnames:
        snapshot = zfs.Snapshot(snap)
        fs = zfs.Filesystem(snapshot.fsname)
        if fs.get_user_property(rsyncsmf.RSYNCFSTAG) == "true":
            if fs.is_mounted() == True:
                snapshot.set_user_property(propname, "pending")
                util.debug("Marking %s as pending rsync" % (snap), verbose)
            else:
                util.debug("Ignoring snapshot of unmounted fileystem: %s" \
                           % (snap), verbose)

def maintenance(svcfmri):
    log_error(syslog.LOG_ERR,
              "Placing plugin into maintenance state")
    cmd = [smf.SVCADMCMD, "mark", "maintenance", svcfmri]
    subprocess.Popen(cmd, close_fds=True)

def log_error(loglevel, message):
    syslog.syslog(loglevel, message + '\n')
    sys.stderr.write(message + '\n')

