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

        self.profiles = self.get_profiles()
        self.auths = self.get_auths()

    def get_profiles(self):
        cmd = ["/usr/bin/profiles", self.name]
        profiles = []
        outdata,errdata = util.run_command(cmd)
        for line in outdata.split('\n'):
            if line.isspace():
                continue
            else:
                try:
                    line.index(self.name + " :")
                except ValueError:
                    profiles.append(line.strip())
        # Remove "All" because it's (seemingly) meaningless
        try:
            profiles.remove("All")
        except ValueError:
            return profiles
        return profiles

    def get_auths(self):
        cmd = ["/usr/bin/auths", self.name]
        auths = []
        outdata,errdata  = util.run_command(cmd)
        auths = outdata.rstrip().split(",")
        return auths

    def has_profile(self, profile):
        # root is all powerful
        if self.uid == 0:
            return True
        try:
            self.profiles.index(profile)
        except ValueError:
            return False
        return True

    def has_auth(self, auth):
        """ Checks the user's authorisations to see if "auth" is
            assigned to the user. Recursively searches higher up
            for glob matching eg. solaris.network.hosts.read ->
            solaris.network.hosts.* -> solaris.network.* ->
            solaris.*, until a valid authorisation is found.
            Returns True if user has the "auth" authorisation,
            False otherwise"""
        try:
            self.auths.index(auth)
            return True
        except ValueError:
            subpattern = auth.rsplit(".", 1)
            # If there are still more "."s in the string
            if subpattern[0] != auth:
                # Try using the glob pattern if auth is not
                # already a glob pattern eg. solaris.device.*
                if subpattern[1] != "*":
                    try:
                        self.auths.index("%s.*" % subpattern[0])
                        return True
                    except ValueError:
                        pass
                # Strip another "." off the auth and carry on searching 
                subsearch = subpattern[0].rsplit(".", 1)
                if subsearch[0] != subpattern[0]:
                    return self.has_auth("%s.*" % subsearch[0])
            return False

if __name__ == "__main__":
  rbac = RBACprofile()
  print rbac.name
  print rbac.uid
  print rbac.profiles
  print rbac.auths

