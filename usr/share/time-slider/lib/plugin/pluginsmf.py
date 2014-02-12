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
from os.path import abspath, dirname, join, pardir
sys.path.insert(0, join(dirname(__file__), pardir))
from time_slider import smf, autosnapsmf, util


PLUGINBASEFMRI = "svc:/application/time-slider/plugin"
PLUGINPROPGROUP = "plugin"

class PluginSMF(smf.SMFInstance):

    def __init__(self, instanceName):
        smf.SMFInstance.__init__(self, instanceName)
        self.triggerCommand = None
        self.triggers = None

    def get_trigger_command(self):
        # FIXME Use mutex locking for MT safety
        if self.triggerCommand == None:
            value = self.get_prop(PLUGINPROPGROUP, "trigger_command")
            self.triggerCommand = value.strip()
        return self.triggerCommand            

    def get_trigger_list(self):
        #FIXME Use mutex locking to make MT-safe
        if self.triggers == None:
            self.triggers = []
            value = self.get_prop(PLUGINPROPGROUP, "trigger_on")
            
            # Strip out '\' characters inserted by svcprop
            triggerList = value.strip().replace('\\', '').split(',')
            for trigger in triggerList:
                self.triggers.append(trigger.strip())
        return self.triggers

    def get_verbose(self):
        value = self.get_prop(PLUGINPROPGROUP, "verbose")
        if value == "true":
            return True
        else:
            return False

