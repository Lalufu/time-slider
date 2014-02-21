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

import time_slider.timeslidersmf as base
import smf
import threading

class TimeSliderSMF(base.TimeSliderSMF):

    def __init__(self, instanceName = base.SMFNAME):
        base.TimeSliderSMF.__init__(self, instanceName)

#
# This is beyond ugly.
#
# The problem this is trying to solve is to change the inheritance chain. Origially
# it looks like this:
#
# <class 'time_slider.linux.timeslidersmf.TimeSliderSMF'>
# <class 'time_slider.timeslidersmf.TimeSliderSMF'>
# <class 'time_slider.smf.SMFInstance'>
# <type 'exceptions.Exception'>
# <type 'exceptions.BaseException'>
# <type 'object'>
#
# We'd like it to look like this:
#
# <class 'time_slider.linux.timeslidersmf.TimeSliderSMF'>
# <class 'time_slider.timeslidersmf.TimeSliderSMF'>
# <class 'time_slider.linux.smf.SMFInstance'>
# <class 'time_slider.smf.SMFInstance'>
# <type 'exceptions.Exception'>
# <type 'exceptions.BaseException'>
# <type 'object'>
#
# so we can inject some linux specific things into SMF without having to copy all
# the code.
#
# This has to be done here as the __init__ of TimeSliderSMF will otherwise fail.
#

base.TimeSliderSMF.__bases__ = (smf.SMFInstance,)

if __name__ == "__main__":
  S = TimeSliderSMF('svc:/application/time-slider')
  print S
