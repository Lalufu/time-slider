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

from . import timesliderconfig
import time_slider.smf as base

class SMFInstance(base.SMFInstance):

    def __init__(self, instanceName):
        base.SMFInstance.__init__(self, instanceName)

    def get_service_state(self):
        config = timesliderconfig.Config()
        return config.get(self.instanceName[5:], 'state')

    def get_service_dependencies(self):
        return []

    def get_prop(self, propgroup, propname):
        return timesliderconfig.Config().get(self.instanceName[5:], \
                propgroup + '/' + propname)

if __name__ == "__main__":
  S = SMFInstance('svc:/application/time-slider')
  print(S)

