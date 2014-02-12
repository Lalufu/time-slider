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

import sys
import os
import datetime
import getopt
import string

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

class SnapshotNowDialog:

    def __init__(self, dir_path, zfs_fs):
        self.dir_path = dir_path
        self.zfs_fs = zfs_fs
        self.xml = gtk.glade.XML("%s/../../glade/time-slider-snapshot.glade" \
                                  % (os.path.dirname(__file__)))
        self.dialog = self.xml.get_widget("dialog")
        self.dir_label = self.xml.get_widget("dir_label")
        self.snap_name_entry = self.xml.get_widget("snapshot_name_entry")
	# signal dictionary	
        dic = {"on_closebutton_clicked" : gtk.main_quit,
               "on_window_delete_event" : gtk.main_quit,
               "on_cancel_clicked" : gtk.main_quit,
               "on_ok_clicked" : self.__on_ok_clicked}
        self.xml.signal_autoconnect(dic)

	self.snap_name_entry.connect("activate", self.__on_entry_activate, 0)

	self.dir_label.set_text(self.dir_path)
	self.snap_name_entry.set_text("my-snapshot-%s" % datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M:%S"))

	self.dialog.show ()

    def validate_name (self, name, showErrorDialog=False):
	#check name validity
	# from http://src.opensolaris.org/source/xref/onnv/onnv-gate/usr/src/common/zfs/zfs_namecheck.c#dataset_namecheck
	# http://src.opensolaris.org/source/xref/onnv/onnv-gate/usr/src/common/zfs/zfs_namecheck.c#valid_char

	invalid = False
	_validchars = string.ascii_letters + string.digits + \
		      "-_.:"
	_allchars = string.maketrans("", "")
	_invalidchars = _allchars.translate(_allchars, _validchars)
  
	valid_name = ""

	for c in name:
	  if c not in _invalidchars:
	    valid_name = valid_name + c
	  else:
	    invalid = True

	if invalid and showErrorDialog:
	  dialog = gtk.MessageDialog(None,
				     0,
				     gtk.MESSAGE_ERROR,
				     gtk.BUTTONS_CLOSE,
				     _("Invalid characters in snapshot name"))
	  dialog.set_title (_("Error"))
	  dialog.format_secondary_text(_("Allowed characters for snapshot names are :\n"
					 "[a-z][A-Z][0-9][-_.:\n"
					 "All invalid characters will be removed\n"))
	  dialog.run ()					 
	  dialog.destroy ()
	return valid_name
	

    def __on_entry_activate (self, widget, none):
	self.snap_name_entry.set_text (self.validate_name (self.snap_name_entry.get_text(), True))
	return
	

    def __on_ok_clicked (self, widget):
      name = self.snap_name_entry.get_text()
      valid_name = self.validate_name (name, True)
      if name == valid_name:
	cmd = "pfexec /usr/sbin/zfs snapshot %s@%s" % (self.zfs_fs, self.validate_name (self.snap_name_entry.get_text()))
	fin,fout,ferr = os.popen3(cmd)
        # Check for any error output generated and
        # return it to caller if so.
        error = ferr.read()
	self.dialog.hide ()
        if len(error) > 0:
	  dialog = gtk.MessageDialog(None,
				     0,
				     gtk.MESSAGE_ERROR,
				     gtk.BUTTONS_CLOSE,
				     _("Error occured while creating the snapshot"))
	  dialog.set_title (_("Error"))
	  dialog.format_secondary_text(error)
	  dialog.run ()
        else:
	  dialog = gtk.MessageDialog(None,
				     0,
				     gtk.MESSAGE_INFO,
				     gtk.BUTTONS_CLOSE,
				     _("Snapshot created successfully"))
	  dialog.set_title (_("Success"))
	  dialog.format_secondary_text(_("A snapshot of zfs filesystem %(zfs_fs)s\n"
				       "named %(valid_name)s\n"
				       "has been created.\n") %
				       { "zfs_fs" : self.zfs_fs, "valid_name" : valid_name})
	  dialog.run ()

	sys.exit(1)
      else:
	self.snap_name_entry.set_text (valid_name)

def main(argv):
    try:
        opts,args = getopt.getopt(sys.argv[1:], "", [])
    except getopt.GetoptError:
        sys.exit(2)
    #FIXME
    #check for 2 args here we assume the arguments are correct
    if len(args) != 2:
        dialog = gtk.MessageDialog(None,
                                   0,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   _("Invalid arguments count."))
	dialog.set_title (_("Error"))
        dialog.format_secondary_text(_("Snapshot Now requires"
                                       " 2 arguments :\n- The path of the "
				       "directory to be snapshotted.\n"
                                       "- The zfs filesystem corresponding "
				       "to this directory."))
        dialog.run()
	sys.exit (2)
	
    rbacp = RBACprofile()
    # The user security attributes checked are the following:
    # 1. The "Primary Administrator" role
    # 4. The "ZFS Files System Management" profile.
    #
    # Valid combinations of the above are:
    # - 1 or 4
    # Note that an effective UID=0 will match any profile search so
    # no need to check it explicitly.
    if rbacp.has_profile("ZFS File System Management"):
	manager = SnapshotNowDialog(args[0],args[1])
        gtk.main()
    elif os.path.exists(argv) and os.path.exists("/usr/bin/gksu"):
        # Run via gksu, which will prompt for the root password
        newargs = ["gksu", argv]
        for arg in args:
            newargs.append(arg)
        os.execv("/usr/bin/gksu", newargs)
        # Shouldn't reach this point
        sys.exit(1)
    else:
        dialog = gtk.MessageDialog(None,
                                   0,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   _("Insufficient Priviliges"))
	dialog.set_title (_("Error"))
        dialog.format_secondary_text(_("Snapshot Now requires "
                                       "administrative privileges to run. "
                                       "You have not been assigned the necessary"
                                       "administrative priviliges."
                                       "\n\nConsult your system administrator "))
        dialog.run()
        print argv + "is not a valid executable path"
        sys.exit(1)

