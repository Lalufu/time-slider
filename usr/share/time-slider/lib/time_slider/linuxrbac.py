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

import os
import pwd

import util

class RBACprofile:

    def __init__(self, name = None):
        # Filtering through the pwd module is beneficial because
        # it will raise a KeyError exception for an invalid
        # name argument 
        if name == None:
            euid = os.geteuid()
            pwnam = pwd.getpwuid(euid)
            self.uid = euid
            self.name = pwnam[0]
        else:
            pwnam = pwd.getpwnam(name)
            self.name = pwnam[0]
            self.uid = pwnam[2]

        self.profiles = []
        self.auths = []

    def has_profile(self, profile):
        # root is all powerful
        if self.uid == 0:
            return True
        else:
            return False

    def has_auth(self, auth):
        # root is all powerful
        if self.uid == 0:
            return True
        else:
            return False

if __name__ == "__main__":
  rbac = RBACprofile()
  print rbac.name
  print rbac.uid
  print rbac.profiles
  print rbac.auths

