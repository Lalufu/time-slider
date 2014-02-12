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
import pluginsmf

from time_slider import smf, autosnapsmf, util

PLUGINBASEFMRI = "svc:/application/time-slider/plugin"


class Plugin(Exception):

    def __init__(self, instanceName, debug=False):
        self.verbose = debug
        util.debug("Instantiating plugin for:\t%s" % (instanceName), self.verbose)
        self.smfInst = pluginsmf.PluginSMF(instanceName)
        self._proc = None

        # Note that the associated plugin service's start method checks
        # that the command is defined and executable. But SMF doesn't 
        # bother to do this for offline services until all dependencies
        # (ie. time-slider) are brought online.
        # So we also check the permissions here.
        command = self.smfInst.get_trigger_command()
        try:
            statinfo = os.stat(command)
            other_x = (statinfo.st_mode & 01)
            if other_x == 0:
              raise RuntimeError, 'Plugin: %s:\nConfigured trigger command is not ' \
                                  'executable:\n%s' \
                                  % (self.smfInst.instanceName, command)  
        except OSError:
            raise RuntimeError, 'Plugin: %s:\nCan not access the configured ' \
                                'plugin/trigger_command:\n%s' \
                                % (self.smfInst.instanceName, command)      


    def execute(self, schedule, label):

        triggers = self.smfInst.get_trigger_list()
        try:
            triggers.index("all")
        except ValueError:
            try:
                triggers.index(schedule)
            except ValueError:
                return

        # Skip if already running
        if self.is_running() == True:
            util.debug("Plugin: %s is already running. Skipping execution" \
                       % (self.smfInst.instanceName), \
                       self.verbose)
            return
        # Skip if plugin FMRI has been disabled or placed into maintenance
        cmd = [smf.SVCSCMD, "-H", "-o", "state", self.smfInst.instanceName]
        outdata,errdata = util.run_command(cmd)
        state = outdata.strip()
        if state == "disabled" or state == "maintenance":
            util.debug("Plugin: %s is in %s state. Skipping execution" \
                       % (self.smfInst.instanceName, state), \
                       self.verbose)
            return

        cmd = self.smfInst.get_trigger_command()
        util.debug("Executing plugin command: %s" % str(cmd), self.verbose)
        svcFmri = "%s:%s" % (autosnapsmf.BASESVC, schedule)

        os.putenv("AUTOSNAP_FMRI", svcFmri)
        os.putenv("AUTOSNAP_LABEL", label)
        try:
            os.putenv("PLUGIN_FMRI", self.smfInst.instanceName) 
            self._proc = subprocess.Popen(cmd,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          close_fds=True)
        except OSError, message:
            raise RuntimeError, "%s subprocess error:\n %s" % \
                                (cmd, str(message))
            self._proc = None

    def is_running(self):
        if self._proc == None:
            util.debug("Plugin child process is not started", self.verbose)
            return False
        else:
            self._proc.poll()
            if self._proc.returncode == None:
                util.debug("Plugin child process is still running",
                           self.verbose)
                return True
            else:
                util.debug("Plugin child process has ended", self.verbose)
                return False


class PluginManager():

    def __init__(self, debug=False):
        self.plugins = []
        self.verbose = debug

    def execute_plugins(self, schedule, label):
        util.debug("Executing plugins for \"%s\" with label: \"%s\"" \
                   % (schedule, label), \
                   self.verbose)
        for plugin in self.plugins:
            plugin.execute(schedule, label)


    def refresh(self):
        self.plugins = []
        cmd = [smf.SVCSCMD, "-H", "-o", "state,FMRI", PLUGINBASEFMRI]

        p = subprocess.Popen(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             close_fds=True)
        outdata,errdata = p.communicate()
        err = p.wait()
        if err != 0:
            self._refreshLock.release()
            raise RuntimeError, '%s failed with exit code %d\n%s' % \
                                (str(cmd), err, errdata)
        for line in outdata.rstrip().split('\n'):
            line = line.rstrip().split()
            state = line[0]
            fmri = line[1]

            # Note that the plugins, being dependent on the time-slider service
            # themselves will typically be in an offline state when enabled. They will
            # transition to an "online" state once time-slider itself comes
            # "online" to satisfy it's dependency
            if state == "online" or state == "offline" or state == "degraded":
                util.debug("Found enabled plugin:\t%s" % (fmri), self.verbose)
                try:
                    plugin = Plugin(fmri, self.verbose)
                    self.plugins.append(plugin)
                except RuntimeError, message:
                    sys.stderr.write("Ignoring misconfigured plugin: %s\n" \
                                     % (fmri))
                    sys.stderr.write("Reason:\n%s\n" % (message))
            else:
                util.debug("Found disabled plugin:\t%s" + fmri, self.verbose)

