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

import threading
import sys
import os
import time
import getopt
import locale
import shutil
import fcntl
from bisect import insort

try:
    import pygtk
    pygtk.require("2.4")
except:
    pass
try:
    import gtk
    import gtk.glade
    gtk.gdk.threads_init()
except:
    sys.exit(1)
try:
    import glib
    import gobject
except:
    sys.exit(1)

from os.path import abspath, dirname, join, pardir
sys.path.insert(0, join(dirname(__file__), pardir, "plugin"))
import plugin
sys.path.insert(0, join(dirname(__file__), pardir, "plugin", "rsync"))
import rsyncsmf


# here we define the path constants so that other modules can use it.
# this allows us to get access to the shared files without having to
# know the actual location, we just use the location of the current
# file and use paths relative to that.
SHARED_FILES = os.path.abspath(os.path.join(os.path.dirname(__file__),
                               os.path.pardir,
                               os.path.pardir))
LOCALE_PATH = os.path.join('/usr', 'share', 'locale')
RESOURCE_PATH = os.path.join(SHARED_FILES, 'res')

# the name of the gettext domain. because we have our translation files
# not in a global folder this doesn't really matter, setting it to the
# application name is a good idea tough.
GETTEXT_DOMAIN = 'time-slider'

# set up the glade gettext system and locales
gtk.glade.bindtextdomain(GETTEXT_DOMAIN, LOCALE_PATH)
gtk.glade.textdomain(GETTEXT_DOMAIN)

import zfs
from rbac import RBACprofile

class RsyncBackup:

    def __init__(self, mountpoint, rsync_dir = None,  fsname= None, snaplabel= None, creationtime= None):

	if rsync_dir == None:
	  self.__init_from_mp (mountpoint)
	else:
	  self.rsync_dir = rsync_dir
          self.mountpoint = mountpoint
          self.fsname = fsname
          self.snaplabel = snaplabel
  
          self.creationtime = creationtime
          try:
              tm = time.localtime(self.creationtime)
              self.creationtime_str = unicode(time.strftime ("%c", tm),
                         locale.getpreferredencoding()).encode('utf-8')
          except:
              self.creationtime_str = time.ctime(self.creationtime)
    
    def __init_from_mp (self, mountpoint):
	self.rsyncsmf = rsyncsmf.RsyncSMF("%s:rsync" %(plugin.PLUGINBASEFMRI))
        rsyncBaseDir = self.rsyncsmf.get_target_dir()
        sys,nodeName,rel,ver,arch = os.uname()
        self.rsync_dir = os.path.join(rsyncBaseDir,
                                     rsyncsmf.RSYNCDIRPREFIX,
                                     nodeName)
	self.mountpoint = mountpoint
	
	s1 = mountpoint.split ("%s/" % self.rsync_dir, 1)
	s2 = s1[1].split ("/%s" % rsyncsmf.RSYNCDIRSUFFIX, 1)
	s3 = s2[1].split ('/',2)
        self.fsname = s2[0]
        self.snaplabel =  s3[1]
	self.creationtime = os.stat(mountpoint).st_mtime

    def __str__(self):
	ret = "self.rsync_dir = %s\n \
	       self.mountpoint = %s\n \
	       self.fsname = %s\n \
	       self.snaplabel = %s\n" % (self.rsync_dir, 
					 self.mountpoint, self.fsname,
					 self.snaplabel)
	return ret					 


    def exists(self):
        return os.path.exists(self.mountpoint)

    def destroy(self):
	lockFileDir = os.path.join(self.rsync_dir,
	      		     self.fsname,
	      		     rsyncsmf.RSYNCLOCKSUFFIX)

	if not os.path.exists(lockFileDir):
	  os.makedirs(lockFileDir, 0755)
	
	lockFile = os.path.join(lockFileDir, self.snaplabel + ".lock")
	try:
	  lockFp = open(lockFile, 'w')
	  fcntl.flock(lockFp, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except IOError:
	  raise RuntimeError, \
	  "couldn't delete %s, already used by another process" % self.mountpoint
	  return 

	trashDir = os.path.join(self.rsync_dir,
	      		  self.fsname,
	      		  rsyncsmf.RSYNCTRASHSUFFIX)
	if not os.path.exists(trashDir):
	  os.makedirs(trashDir, 0755)

	backupTrashDir = os.path.join (self.rsync_dir,
	      			 self.fsname,
	      			 rsyncsmf.RSYNCTRASHSUFFIX,
	      			 self.snaplabel)

	# move then delete
	os.rename (self.mountpoint, backupTrashDir)
	shutil.rmtree (backupTrashDir)

	log = "%s/%s/%s/%s/%s.log" % (self.rsync_dir,
	      			   self.fsname,
	      			   rsyncsmf.RSYNCDIRSUFFIX,
	      			   ".partial",
	      			   self.snaplabel)
	if os.path.exists (log):
            os.unlink (log)

	lockFp.close()
	os.unlink(lockFile)


backupDirs = []
for root, dirs, files in os.walk(rsyncsmf.RsyncSMF("%s:rsync" %(plugin.PLUGINBASEFMRI)).get_target_dir ()):
            if '.time-slider' in dirs:
                dirs.remove('.time-slider')
                backupDir = os.path.join(root, rsyncsmf.RSYNCDIRSUFFIX)
                if os.path.exists(backupDir):
                    insort(backupDirs, os.path.abspath(backupDir))


print backupDirs


