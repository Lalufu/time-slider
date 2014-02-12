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
import subprocess
import threading
import util
import smf
from autosnapsmf import enable_default_schedules, disable_default_schedules

from os.path import abspath, dirname, join, pardir
sys.path.insert(0, join(dirname(__file__), pardir, "plugin"))
import plugin
sys.path.insert(0, join(dirname(__file__), pardir, "plugin", "rsync"))
import rsyncsmf

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

import glib
import gobject
import gio
import dbus
import dbus.service
import dbus.mainloop
import dbus.mainloop.glib
import dbussvc


# This is the rough guess ratio used for rsync backup device size
# vs. the total size of the pools it's expected to backup.
RSYNCTARGETRATIO = 2

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
from timeslidersmf import TimeSliderSMF
from rbac import RBACprofile


class FilesystemIntention:

    def __init__(self, name, selected, inherited):
        self.name = name
        self.selected = selected
        self.inherited = inherited

    def __str__(self):
        return_string = "Filesystem name: " + self.name + \
                "\n\tSelected: " + str(self.selected) + \
                "\n\tInherited: " + str(self.inherited)
        return return_string

    def __eq__(self, other):
        if self.name != other.name:
            return False
        if self.inherited and other.inherited:
            return True
        elif not self.inherited and other.inherited:
            return False
        if (self.selected == other.selected) and \
           (self.inherited == other.inherited):
            return True
        else:
            return False

class SetupManager:

    def __init__(self, execpath):
        self._execPath = execpath
        self._datasets = zfs.Datasets()
        self._xml = gtk.glade.XML("%s/../../glade/time-slider-setup.glade" \
                                  % (os.path.dirname(__file__)))

        # Tell dbus to use the gobject mainloop for async ops
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        dbus.mainloop.glib.threads_init()

        # Register a bus name with the system dbus daemon
        systemBus = dbus.SystemBus()
        busName = dbus.service.BusName("org.opensolaris.TimeSlider.config",
                                       systemBus)
        self._dbus = dbussvc.Config(systemBus,
                                    '/org/opensolaris/TimeSlider/config')
        # Used later to trigger a D-Bus notification of select configuration 
        # changes made
        self._configNotify = False

        # These variables record the initial UI state which are used
        # later to compare against the UI state when the OK or Cancel
        # button is clicked and apply the minimum set of necessary 
        # configuration changes. Prevents minor changes taking ages
        # to be applied by the GUI.
        self._initialEnabledState = None
        self._initialRsyncState = None
        self._initialRsyncTargetDir = None
        self._initialCleanupLevel = None
        self._initialCustomSelection = False
        self._initialSnapStateDic = {}
        self._initialRsyncStateDic = {}
        self._initialFsIntentDic = {}
        self._initialRsyncIntentDic = {}

        # Currently selected rsync backup device via the GUI.
        self._newRsyncTargetDir = None
        # Used to store GUI filesystem selection state and the
        # set of intended properties to apply to zfs filesystems.
        self._snapStateDic = {}
        self._rsyncStateDic = {}
        self._fsIntentDic = {}
        self._rsyncIntentDic = {}
        # Dictionary that maps device ID numbers to zfs filesystem objects
        self._fsDevices = {}

        topLevel = self._xml.get_widget("toplevel")
        self._pulseDialog = self._xml.get_widget("pulsedialog")
        self._pulseDialog.set_transient_for(topLevel)
        
        # gio.VolumeMonitor reference
        self._vm = gio.volume_monitor_get()
        self._vm.connect("mount-added", self._mount_added)
        self._vm.connect("mount-removed" , self._mount_removed)

        self._fsListStore = gtk.ListStore(bool,
                                         bool,
                                         str,
                                         str,
                                         gobject.TYPE_PYOBJECT)
        filesystems = self._datasets.list_filesystems()
        for fsname,fsmountpoint in filesystems:
            if (fsmountpoint == "legacy"):
                mountpoint = _("Legacy")
            else:
                mountpoint = fsmountpoint
            fs = zfs.Filesystem(fsname, fsmountpoint)
            # Note that we don't deal with legacy mountpoints.
            if fsmountpoint != "legacy" and fs.is_mounted():
                self._fsDevices[os.stat(fsmountpoint).st_dev] = fs
            snap = fs.get_auto_snap()
            rsyncstr = fs.get_user_property(rsyncsmf.RSYNCFSTAG)
            if rsyncstr == "true":
                rsync = True
            else:
                rsync = False
            # Rsync is only performed on snapshotted filesystems.
            # So treat as False if rsync is set to true independently
            self._fsListStore.append([snap, snap & rsync,
                                     mountpoint, fs.name, fs])
            self._initialSnapStateDic[fs.name] = snap
            self._initialRsyncStateDic[fs.name] = snap & rsync
        del filesystems

        for fsname in self._initialSnapStateDic:
                self._refine_filesys_actions(fsname,
                                              self._initialSnapStateDic,
                                              self._initialFsIntentDic)
                self._refine_filesys_actions(fsname,
                                              self._initialRsyncStateDic,
                                              self._initialRsyncIntentDic)
   
        self._fsTreeView = self._xml.get_widget("fstreeview")
        self._fsTreeView.set_sensitive(False)
        self._fsTreeView.set_size_request(10, 200)

        self._fsTreeView.set_model(self._fsListStore)

        cell0 = gtk.CellRendererToggle()
        cell1 = gtk.CellRendererToggle()
        cell2 = gtk.CellRendererText()
        cell3 = gtk.CellRendererText()
 
        radioColumn = gtk.TreeViewColumn(_("Select"),
                                             cell0, active=0)
        self._fsTreeView.insert_column(radioColumn, 0)

        self._rsyncRadioColumn = gtk.TreeViewColumn(_("Replicate"),
                                                    cell1, active=1)
        nameColumn = gtk.TreeViewColumn(_("Mount Point"),
                                        cell2, text=2)
        self._fsTreeView.insert_column(nameColumn, 2)
        mountPointColumn = gtk.TreeViewColumn(_("File System Name"),
                                              cell3, text=3)
        self._fsTreeView.insert_column(mountPointColumn, 3)
        cell0.connect('toggled', self._row_toggled)
        cell1.connect('toggled', self._rsync_cell_toggled)
        advancedBox = self._xml.get_widget("advancedbox")
        advancedBox.connect('unmap', self._advancedbox_unmap)  

        self._rsyncSMF = rsyncsmf.RsyncSMF("%s:rsync" \
                                          %(plugin.PLUGINBASEFMRI))
        state = self._rsyncSMF.get_service_state()
        self._initialRsyncTargetDir = self._rsyncSMF.get_target_dir()
        # Check for the default, unset value of "" from SMF.
        if self._initialRsyncTargetDir == '""':
            self._initialRsyncTargetDir = ''
        self._newRsyncTargetDir = self._initialRsyncTargetDir
        self._smfTargetKey = self._rsyncSMF.get_target_key()
        self._newRsyncTargetSelected = False
        sys,self._nodeName,rel,ver,arch = os.uname()

        # Model columns:
        # 0 Themed icon list (python list)
        # 1 device root
        # 2 volume name
        # 3 Is gio.Mount device
        # 4 Is separator (for comboBox separator rendering)
        self._rsyncStore = gtk.ListStore(gobject.TYPE_PYOBJECT,
                                         gobject.TYPE_STRING,
                                         gobject.TYPE_STRING,
                                         gobject.TYPE_BOOLEAN,
                                         gobject.TYPE_BOOLEAN)
        self._rsyncCombo = self._xml.get_widget("rsyncdevcombo")
        mounts = self._vm.get_mounts()
        for mount in mounts:
            self._mount_added(self._vm, mount)
        if len(mounts) > 0:
            # Add a separator
            self._rsyncStore.append((None, None, None, None, True))
        del mounts

        if len(self._newRsyncTargetDir) == 0:
            self._rsyncStore.append((['folder'],
                                    _("(None)"),
                                    '',
                                    False,
                                    False))
            # Add a separator
            self._rsyncStore.append((None, None, None, None, True))
        self._rsyncStore.append((None, _("Other..."), "Other", False, False))
        self._iconCell = gtk.CellRendererPixbuf()
        self._nameCell = gtk.CellRendererText()
        self._rsyncCombo.clear()
        self._rsyncCombo.pack_start(self._iconCell, False)
        self._rsyncCombo.set_cell_data_func(self._iconCell,
                                            self._icon_cell_render)
        self._rsyncCombo.pack_end(self._nameCell)
        self._rsyncCombo.set_attributes(self._nameCell, text=1)
        self._rsyncCombo.set_row_separator_func(self._row_separator)
        self._rsyncCombo.set_model(self._rsyncStore)
        self._rsyncCombo.connect("changed", self._rsync_combo_changed)
        # Force selection of currently configured device
        self._rsync_dev_selected(self._newRsyncTargetDir)

        # signal dictionary	
        dic = {"on_ok_clicked" : self._on_ok_clicked,
               "on_cancel_clicked" : gtk.main_quit,
               "on_snapshotmanager_delete_event" : gtk.main_quit,
               "on_enablebutton_toggled" : self._on_enablebutton_toggled,
               "on_rsyncbutton_toggled" : self._on_rsyncbutton_toggled,
               "on_defaultfsradio_toggled" : self._on_defaultfsradio_toggled,
               "on_selectfsradio_toggled" : self._on_selectfsradio_toggled,
               "on_deletesnapshots_clicked" : self._on_deletesnapshots_clicked}
        self._xml.signal_autoconnect(dic)

        if state != "disabled":
            self._rsyncEnabled = True
            self._xml.get_widget("rsyncbutton").set_active(True)
            self._initialRsyncState = True
        else:
            self._rsyncEnabled = False
            self._rsyncCombo.set_sensitive(False)
            self._initialRsyncState = False

        # Initialise SMF service instance state.
        try:
            self._sliderSMF = TimeSliderSMF()
        except RuntimeError,message:
            self._xml.get_widget("toplevel").set_sensitive(False)
            dialog = gtk.MessageDialog(self._xml.get_widget("toplevel"),
                                       0,
                                       gtk.MESSAGE_ERROR,
                                       gtk.BUTTONS_CLOSE,
                                       _("Snapshot manager service error"))
            dialog.format_secondary_text(_("The snapshot manager service does "
                                         "not appear to be installed on this "
                                         "system."
                                         "\n\nSee the svcs(1) man page for more "
                                         "information."
                                         "\n\nDetails:\n%s")%(message))
            dialog.set_icon_name("time-slider-setup")
            dialog.run()
            sys.exit(1)

        if self._sliderSMF.svcstate == "disabled":
            self._xml.get_widget("enablebutton").set_active(False)
            self._initialEnabledState = False
        elif self._sliderSMF.svcstate == "offline":
            self._xml.get_widget("toplevel").set_sensitive(False)
            errors = ''.join("%s\n" % (error) for error in \
                self._sliderSMF.find_dependency_errors())
            dialog = gtk.MessageDialog(self._xml.get_widget("toplevel"),
                                        0,
                                        gtk.MESSAGE_ERROR,
                                        gtk.BUTTONS_CLOSE,
                                        _("Snapshot manager service dependency error"))
            dialog.format_secondary_text(_("The snapshot manager service has "
                                            "been placed offline due to a dependency "
                                            "problem. The following dependency problems "
                                            "were found:\n\n%s\n\nRun \"svcs -xv\" from "
                                            "a command prompt for more information about "
                                            "these dependency problems.") % errors)
            dialog.set_icon_name("time-slider-setup")
            dialog.run()
            sys.exit(1)
        elif self._sliderSMF.svcstate == "maintenance":
            self._xml.get_widget("toplevel").set_sensitive(False)
            dialog = gtk.MessageDialog(self._xml.get_widget("toplevel"),
                                        0,
                                        gtk.MESSAGE_ERROR,
                                        gtk.BUTTONS_CLOSE,
                                        _("Snapshot manager service error"))
            dialog.format_secondary_text(_("The snapshot manager service has "
                                            "encountered a problem and has been "
                                            "disabled until the problem is fixed."
                                            "\n\nSee the svcs(1) man page for more "
                                            "information."))
            dialog.set_icon_name("time-slider-setup")
            dialog.run()
            sys.exit(1)
        else:
            # FIXME: Check transitional states 
            self._xml.get_widget("enablebutton").set_active(True)
            self._initialEnabledState = True


        # Emit a toggled signal so that the initial GUI state is consistent
        self._xml.get_widget("enablebutton").emit("toggled")
        # Check the snapshotting policy (UserData (default), or Custom)
        self._initialCustomSelection = self._sliderSMF.is_custom_selection()
        if self._initialCustomSelection == True:
            self._xml.get_widget("selectfsradio").set_active(True)
            # Show the advanced controls so the user can see the
            # customised configuration.
            if self._sliderSMF.svcstate != "disabled":
                self._xml.get_widget("expander").set_expanded(True)
        else: # "false" or any other non "true" value
            self._xml.get_widget("defaultfsradio").set_active(True)

        # Set the cleanup threshhold value
        spinButton = self._xml.get_widget("capspinbutton")
        critLevel = self._sliderSMF.get_cleanup_level("critical")
        warnLevel = self._sliderSMF.get_cleanup_level("warning")

        # Force the warning level to something practical
        # on the lower end, and make it no greater than the
        # critical level specified in the SVC instance.
        spinButton.set_range(70, critLevel)
        self._initialCleanupLevel = warnLevel
        if warnLevel > 70:
            spinButton.set_value(warnLevel)
        else:
            spinButton.set_value(70)

    def _icon_cell_render(self, celllayout, cell, model, iter):
        iconList = self._rsyncStore.get_value(iter, 0)
        if iconList != None:
            gicon = gio.ThemedIcon(iconList)
            cell.set_property("gicon", gicon)
        else:
            root = self._rsyncStore.get_value(iter, 2)
            if root == "Other":
                cell.set_property("gicon", None)

    def _row_separator(self, model, iter):
        return model.get_value(iter, 4)

    def _mount_added(self, volume_monitor, mount):
        icon = mount.get_icon()
        iconList = icon.get_names()
        if iconList == None:
            iconList = ['drive-harddisk', 'drive']
        root = mount.get_root()
        path = root.get_path()
        mountName = mount.get_name()
        volume = mount.get_volume()
        if volume == None:
            volName = mount.get_name()
            if volName == None:
                volName = os.path.split(path)[1]
        else:
            volName = volume.get_name()

        # Check to see if there is at least one gio.Mount device already
        # in the ListStore. If not, then we also need to add a separator
        # row.
        iter = self._rsyncStore.get_iter_first()
        if iter and self._rsyncStore.get_value(iter, 3) == False:
            self._rsyncStore.insert(0, (None, None, None, None, True))
        
        self._rsyncStore.insert(0, (iconList, volName, path, True, False))
        # If this happens to be the already configured backup device
        # and the user hasn't tried to change device yet, auto select
        # it.
        if self._initialRsyncTargetDir == self._newRsyncTargetDir:
            if self._validate_rsync_target(path) == True:
                self._rsyncCombo.set_active(0)

    def _mount_removed(self, volume_monitor, mount):
        root = mount.get_root()
        path = root.get_path()
        iter = self._rsyncStore.get_iter_first()
        mountIter = None
        numMounts = 0
        # Search gio.Mount devices
        while iter != None and \
            self._rsyncStore.get_value(iter, 3) == True:
            numMounts += 1
            compPath = self._rsyncStore.get_value(iter, 2)
            if compPath == path:
                mountIter = iter
                break
            else:
                iter = self._rsyncStore.iter_next(iter)
        if mountIter != None:
            if numMounts == 1:
                # Need to remove the separator also since
                # there will be no more gio.Mount devices
                # shown in the combo box
                sepIter = self._rsyncStore.iter_next(mountIter)
                if self._rsyncStore.get_value(sepIter, 4) == True:
                    self._rsyncStore.remove(sepIter)                  
            self._rsyncStore.remove(mountIter)
            iter = self._rsyncStore.get_iter_first()
            # Insert a custom folder if none exists already
            if self._rsyncStore.get_value(iter, 2) == "Other":
                path = self._initialRsyncTargetDir
                length = len(path)
                if length > 1:
                    name = os.path.split(path)[1]
                elif length == 1:
                    name = path
                else: # Indicates path is unset: ''
                    name = _("(None)")
                iter = self._rsyncStore.insert_before(iter,
                                                      (None,
                                                       None,
                                                       None,
                                                       None,
                                                       True))
                iter = self._rsyncStore.insert_before(iter,
                                                      (['folder'],
                                                       name,
                                                       path,
                                                       False,
                                                       False))
            self._rsyncCombo.set_active_iter(iter)

    def _monitor_setup(self, pulseBar):
        if self._enabler.isAlive() == True:
            pulseBar.pulse()
            return True
        else:
            gtk.main_quit()   

    def _row_toggled(self, renderer, path):
        model = self._fsTreeView.get_model()
        iter = model.get_iter(path)
        state = renderer.get_active()
        if state == False:
            self._fsListStore.set_value(iter, 0, True)
        else:
            self._fsListStore.set_value(iter, 0, False)
            self._fsListStore.set_value(iter, 1, False)

    def _rsync_cell_toggled(self, renderer, path):
        model = self._fsTreeView.get_model()
        iter = model.get_iter(path)
        state = renderer.get_active()
        rowstate = self._fsListStore.get_value(iter, 0)
        if rowstate == True:
            if state == False:
                self._fsListStore.set_value(iter, 1, True)
            else:
                self._fsListStore.set_value(iter, 1, False)

    def _rsync_config_error(self, msg):
        topLevel = self._xml.get_widget("toplevel")
        dialog = gtk.MessageDialog(topLevel,
                                    0,
                                    gtk.MESSAGE_ERROR,
                                    gtk.BUTTONS_CLOSE,
                                    _("Unsuitable Backup Location"))
        dialog.format_secondary_text(msg)
        dialog.set_icon_name("time-slider-setup")
        dialog.run()
        dialog.hide()
        return

    def _rsync_dev_selected(self, path):
        iter = self._rsyncStore.get_iter_first()
        while iter != None:
            # Break out when we hit a non gio.Mount device
            if self._rsyncStore.get_value(iter, 3) == False:
                break
            compPath = self._rsyncStore.get_value(iter, 2)
            if compPath == path:
                self._rsyncCombo.set_active_iter(iter)
                self._newRsyncTargetDir = path
                return
            else:
                iter = self._rsyncStore.iter_next(iter)

        # Not one of the shortcut RMM devices, so it's
        # some other path on the filesystem.
        # iter may be pointing at a separator. Increment
        # to next row iter if so.
        if self._rsyncStore.get_value(iter, 4) == True:
            iter = self._rsyncStore.iter_next(iter)

        if iter != None:
            if len(path) > 1:
                name = os.path.split(path)[1]
            elif len(path) == 1:
                name = path
            else: # Indicates path is unset: ''
                name = _("(None)")
            # Could be either the custom folder selection
            # row or the  "Other" row if the custom row
            # was not created. If "Other" then create the
            # custom row and separator now at this position
            if self._rsyncStore.get_value(iter, 2) == "Other":
                iter = self._rsyncStore.insert_before(iter,
                                                      (None,
                                                       None,
                                                       None,
                                                       None,
                                                       True))
                iter = self._rsyncStore.insert_before(iter,
                                                      (['folder'],
                                                       name,
                                                       path,
                                                       False,
                                                       False))
            else:
                self._rsyncStore.set(iter,
                                     1, name,
                                     2, path)
            self._rsyncCombo.set_active_iter(iter)
            self._newRsyncTargetDir = path

    def _rsync_combo_changed(self, combobox):
        newIter = combobox.get_active_iter()
        if newIter != None:
            root = self._rsyncStore.get_value(newIter, 2)
            if root != "Other":
                self._newRsyncTargetDir = root
            else:
                msg = _("Select A Back Up Device")
                fileDialog = \
                    gtk.FileChooserDialog(
                        msg,
                        self._xml.get_widget("toplevel"),
                        gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                        (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                        gtk.STOCK_OK,gtk.RESPONSE_OK),
                        None)
                self._rsyncCombo.set_sensitive(False)
                response = fileDialog.run()
                fileDialog.hide()
                if response == gtk.RESPONSE_OK:
                    gFile = fileDialog.get_file()
                    self._rsync_dev_selected(gFile.get_path())
                else:
                    self._rsync_dev_selected(self._newRsyncTargetDir)
                self._rsyncCombo.set_sensitive(True)

    def _rsync_size_warning(self, zpools, zpoolSize,
                             rsyncTarget, targetSize):
        # Using decimal "GB" instead of binary "GiB"
        KB = 1000
        MB = 1000 * KB
        GB = 1000 * MB
        TB = 1000 * GB

        suggestedSize = RSYNCTARGETRATIO * zpoolSize
        if suggestedSize > TB:
            sizeStr = "%.1f TB" % round(suggestedSize / float(TB), 1)
        elif suggestedSize > GB:
            sizeStr = "%.1f GB" % round(suggestedSize / float(GB), 1)
        else:
            sizeStr = "%.1f MB" % round(suggestedSize / float(MB), 1)

        if targetSize > TB:
            targetStr = "%.1f TB" % round(targetSize / float(TB), 1)
        elif targetSize > GB:
            targetStr = "%.1f GB" % round(targetSize / float(GB), 1)
        else:
            targetStr = "%.1f MB" % round(targetSize / float(MB), 1)


        msg = _("Time Slider suggests a device with a capacity of at "
                "least <b>%s</b>.\n"
                "The device: \'<b>%s</b>\'\nonly has <b>%s</b>\n"
                "Do you want to use it anyway?") \
                % (sizeStr, rsyncTarget, targetStr)

        topLevel = self._xml.get_widget("toplevel")
        dialog = gtk.MessageDialog(topLevel,
                                   0,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_YES_NO,
                                   _("Time Slider"))
        dialog.set_default_response(gtk.RESPONSE_NO)
        dialog.set_transient_for(topLevel)
        dialog.set_markup(msg)
        dialog.set_icon_name("time-slider-setup")

        response = dialog.run()
        dialog.hide()
        if response == gtk.RESPONSE_YES:
            return True
        else:
            return False

    def _check_rsync_config(self):
        """
           Checks rsync configuration including, filesystem selection,
           target directory validation and capacity checks.
           Returns True if everything is OK, otherwise False.
           Pops up blocking error dialogs to notify users of error
           conditions before returning.
        """
        def _get_mount_point(path):
            if os.path.ismount(path):
                return path
            else:
                return _get_mount_point(abspath(join(path, pardir)))

        if self._rsyncEnabled != True:
            return True

        if len(self._newRsyncTargetDir) == 0:
            msg = _("No backup device was selected.\n"
                    "Please select an empty device.")
            self._rsync_config_error(msg)
            return False
        # There's little that can be done if the device is from a
        # previous configuration and currently offline. So just 
        # treat it as being OK based on the assumption that it was
        # previously deemed to be OK.
        if self._initialRsyncTargetDir == self._newRsyncTargetDir and \
           not os.path.exists(self._newRsyncTargetDir):
            return True
        # Perform the required validation checks on the
        # target directory.
        newTargetDir = self._newRsyncTargetDir

        # We require the whole device. So find the enclosing
        # mount point and inspect from there.
        targetMountPoint = abspath(_get_mount_point(newTargetDir))

        # Check that it's writable.
        f = None
        testFile = os.path.join(targetMountPoint, ".ts-test")
        try:
            f = open(testFile, 'w')
        except (OSError, IOError):
            msg = _("\'%s\'\n"
                    "is not writable. The backup device must "
                    "be writable by the system administrator." 
                    "\n\nPlease use a different device.") \
                    % (targetMountPoint)
            self._rsync_config_error(msg)
            return False
        f.close()

        # Try to create a symlink. Rsync requires this to
        # do incremental backups and to ensure it's posix like
        # enough to correctly set file ownerships and perms.
        os.chdir(targetMountPoint)
        try:
            os.link(testFile, ".ts-test-link")
        except OSError:
            msg = _("\'%s\'\n"
                    "contains an incompatible file system. " 
                    "The selected device must have a Unix "
                    "style file system that supports file "
                    "linking, such as UFS"
                    "\n\nPlease use a different device.") \
                    % (targetMountPoint)
            self._rsync_config_error(msg)
            return False
        finally:
            os.unlink(testFile)
        os.unlink(".ts-test-link")

        # Check that selected directory is either empty
        # or already preconfigured as a backup target
        sys,nodeName,rel,ver,arch = os.uname()
        basePath = os.path.join(targetMountPoint,
                                rsyncsmf.RSYNCDIRPREFIX)
        nodePath = os.path.join(basePath,
                                nodeName)
        configPath = os.path.join(basePath,
                                    rsyncsmf.RSYNCCONFIGFILE)
        self._newRsyncTargetSelected = True
        targetDirKey = None

        contents = os.listdir(targetMountPoint)
        os.chdir(targetMountPoint)

        # The only other exception to an empty directory is
        # "lost+found".
        for item in contents:
            if (item != rsyncsmf.RSYNCDIRPREFIX and \
                item != "lost+found") or \
               not os.path.isdir(item) or \
               os.path.islink(item):
                msg = _("\'%s\'\n is not an empty device.\n\n"
                        "Please select an empty device.") \
                        % (newTargetDir)
                self._rsync_config_error(msg)
                return False

        # Validate existing directory structure
        if os.path.exists(basePath):
            # We only accept a pre-existing directory if
            # 1. It has a config key that matches that stored by
            #    the rsync plugin's SMF configuration
            # 2. It has a single subfolder that matches the nodename
            #    of this system,

            # Check for previous config key
            if os.path.exists(configPath):
                f = open(configPath, 'r')
                for line in f.readlines():
                    key, val = line.strip().split('=')
                    if key.strip() == "target_key":
                        targetDirKey = val.strip()
                        break

            # Examine anything else in the directory
            self._targetSelectionError = None
            dirList = [d for d in os.listdir(basePath) if
                        d != '.rsync-config']
            os.chdir(basePath)
            if len(dirList) > 0:
                msg = _("\'%s\'\n is not an empty device.\n\n"
                        "Please select an empty device.") \
                        % (newTargetDir)
                # No config key or > 1 directory:
                # User specified a non empty directory.
                if targetDirKey == None or len(dirList) > 1:
                    self._rsync_config_error(msg)
                    return False
                # Make sure the single item is not a file or symlink.
                elif os.path.islink(dirList[0]) or \
                        os.path.isfile(dirList[0]):
                    self._rsync_config_error(msg)
                    return False
                else:
                    # Has 1 other item and a config key. Other
                    # item must be a directory and must match the
                    # system nodename and SMF's key value respectively
                    # respectively
                    if dirList[0] != nodeName and \
                        targetDirKey != self._smfTargetKey:
                        msg = _("\'%s\'\n"
                                "is a Time Slider external backup device "
                                "that is already in use by another system. "
                                "Backup devices may not be shared between "
                                "systems." 
                                "\n\nPlease use a different device.") \
                                % (newTargetDir)
                        self._rsync_config_error(msg)                                
                        return False
                    else:
                        if dirList[0] == nodeName and \
                           targetDirKey != self._smfTargetKey:
                            # Looks like a device that we previously used,
                            # but discontinued using in favour of some other
                            # device.
                            msg = _("\'<b>%s</b>\' appears to be a a device "
                                    "previously configured for use by this "
                                    "system.\n\nDo you want resume use of "
                                    "this device for backups?") \
                                    % (newTargetDir)

                            topLevel = self._xml.get_widget("toplevel")
                            dialog = gtk.MessageDialog(topLevel,
                                                       0,
                                                       gtk.MESSAGE_QUESTION,
                                                       gtk.BUTTONS_YES_NO,
                                                       _("Time Slider"))
                            dialog.set_default_response(gtk.RESPONSE_NO)
                            dialog.set_transient_for(topLevel)
                            dialog.set_markup(msg)
                            dialog.set_icon_name("time-slider-setup")

                            response = dialog.run()
                            dialog.hide()
                            if response == gtk.RESPONSE_NO:
                                return False
                        else:
                            # Appears to be our own pre-configured directory.
                            self._newRsyncTargetSelected = False

        # Compare device ID against selected ZFS filesystems
        # and their enclosing Zpools. The aim is to avoid
        # a vicous circle caused by backing up snapshots onto
        # the same pool the snapshots originate from
        targetDev = os.stat(newTargetDir).st_dev
        try:
            fs = self._fsDevices[targetDev]
            
            # See if the filesystem itself is selected
            # and/or any other fileystem on the pool is 
            # selected.
            fsEnabled = self._snapStateDic[fs.name]
            if fsEnabled == True:
                # Definitely can't use this since it's a
                # snapshotted filesystem.
                msg = _("\'%s\'\n"
                        "belongs to the ZFS filesystem \'%s\' "
                        "which is already selected for "
                        "regular ZFS snaphots." 
                        "\n\nPlease select a drive "
                        "not already in use by "
                        "Time Slider") \
                        % (newTargetDir, fs.name)
                self._rsync_config_error(msg)
                return False
            else:
                # See if there is anything else on the pool being
                # snapshotted
                poolName = fs.name.split("/", 1)[0]
                for name,mount in self._datasets.list_filesystems():
                    if name.find(poolName) == 0:
                        try:
                            otherEnabled = self._snapStateDic[name]
                            radioBtn = self._xml.get_widget("defaultfsradio")
                            snapAll = radioBtn.get_active()
                            if snapAll or otherEnabled:
                                msg = _("\'%s\'\n"
                                        "belongs to the ZFS pool \'%s\' "
                                        "which is already being used "
                                        "to store ZFS snaphots." 
                                        "\n\nPlease select a drive "
                                        "not already in use by "
                                        "Time Slider") \
                                        % (newTargetDir, poolName)
                                self._rsync_config_error(msg)
                                return False
                        except KeyError:
                            pass               
        except KeyError:
            # No match found - good.
            pass


        # Figure out if there's a reasonable amount of free space to
        # store backups. This is a vague guess at best.
        allPools = zfs.list_zpools()
        snapPools = []
        # FIXME -  this is for custom selection. There is a short
        # circuit case for default (All) configuration. Don't forget
        # to implement this short circuit.
        for poolName in allPools:
            try:
                snapPools.index(poolName)
            except ValueError:
                pool = zfs.ZPool(poolName)
                # FIXME - we should include volumes here but they
                # can only be set from the command line, not via
                # the GUI, so not crucial.
                for fsName,mount in pool.list_filesystems():
                    # Don't try to catch exception. The filesystems
                    # are already populated in self._snapStateDic
                    enabled = self._snapStateDic[fsName]
                    if enabled == True:
                        snapPools.append(poolName)
                        break

        sumPoolSize = 0
        for poolName in snapPools:
            pool = zfs.ZPool(poolName)
            # Rough calcualation, but precise enough for
            # estimation purposes
            sumPoolSize += pool.get_used_size()
            sumPoolSize += pool.get_available_size()


        # Compare with available space on rsync target dir
        targetAvail = util.get_available_size(targetMountPoint)
        targetUsed = util.get_used_size(targetMountPoint)
        targetSum = targetAvail + targetUsed

        # Recommended Minimum:
        # At least double the combined size of all pools with
        # fileystems selected for backup. Variables include,
        # frequency of data changes, how much efficiency rsync
        # sacrifices compared to ZFS' block level diff tracking,
        # whether compression and/or deduplication are enabled 
        # on the source pool/fileystem.
        # We don't try to make calculations based on individual
        # filesystem selection as there are too many unpredictable
        # variables to make an estimation of any practical use.
        # Let the user figure that out for themselves.

        # The most consistent measurement is to use the sum of
        # available and used size on the target fileystem. We
        # assume based on previous checks that the target device
        # is only being used for rsync backups and therefore the
        # used value consists of existing backups and is. Available
        # space can be reduced for various reasons including the used
        # value increasing or for nfs mounted zfs fileystems, other
        # zfs filesystems on the containing pool using up more space.
        

        targetPoolRatio = targetSum/float(sumPoolSize)
        if (targetPoolRatio < RSYNCTARGETRATIO):
            response = self._rsync_size_warning(snapPools,
                                                 sumPoolSize,
                                                 targetMountPoint,
                                                 targetSum)
            if response == False:
                return False

        self._newRsyncTargetDir = targetMountPoint
        return True

    def _on_ok_clicked(self, widget):
        # Make sure the dictionaries are empty.
        self._fsIntentDic = {}
        self._snapStateDic = {}
        self._rsyncStateDic = {}
        enabled = self._xml.get_widget("enablebutton").get_active()
        self._rsyncEnabled = self._xml.get_widget("rsyncbutton").get_active()
        if enabled == False:
            if self._rsyncEnabled == False and \
               self._initialRsyncState == True:
                self._rsyncSMF.disable_service()
            if self._initialEnabledState == True:
                self._sliderSMF.disable_service()
            # Ignore other changes to the snapshot/rsync configuration
            # of filesystems. Just broadcast the change and exit.
            self._configNotify = True
            self.broadcast_changes()
            gtk.main_quit()
        else:
            model = self._fsTreeView.get_model()
            snapalldata = self._xml.get_widget("defaultfsradio").get_active()
                
            if snapalldata == True:
                model.foreach(self._set_fs_selection_state, True)
                if self._rsyncEnabled == True:
                    model.foreach(self._set_rsync_selection_state, True)
            else:
                model.foreach(self._get_fs_selection_state)
                model.foreach(self._get_rsync_selection_state)
            for fsname in self._snapStateDic:
                self._refine_filesys_actions(fsname,
                                              self._snapStateDic,
                                              self._fsIntentDic)
                if self._rsyncEnabled == True:
                    self._refine_filesys_actions(fsname,
                                                  self._rsyncStateDic,
                                                  self._rsyncIntentDic)
            if self._rsyncEnabled and \
               not self._check_rsync_config():
                    return

            self._pulseDialog.show()
            self._enabler = EnableService(self)
            self._enabler.start()
            glib.timeout_add(100,
                             self._monitor_setup,
                             self._xml.get_widget("pulsebar"))

    def _on_enablebutton_toggled(self, widget):
        expander = self._xml.get_widget("expander")
        enabled = widget.get_active()
        self._xml.get_widget("filesysframe").set_sensitive(enabled)
        expander.set_sensitive(enabled)
        if (enabled == False):
            expander.set_expanded(False)

    def _on_rsyncbutton_toggled(self, widget):
        self._rsyncEnabled = widget.get_active()
        if self._rsyncEnabled == True:
            self._fsTreeView.insert_column(self._rsyncRadioColumn, 1)
            self._rsyncCombo.set_sensitive(True)
        else:
            self._fsTreeView.remove_column(self._rsyncRadioColumn)
            self._rsyncCombo.set_sensitive(False)

    def _on_defaultfsradio_toggled(self, widget):
        if widget.get_active() == True:
            self._xml.get_widget("fstreeview").set_sensitive(False)

    def _on_selectfsradio_toggled(self, widget):
       if widget.get_active() == True:
            self._xml.get_widget("fstreeview").set_sensitive(True)

    def _advancedbox_unmap(self, widget):
        # Auto shrink the window by subtracting the frame's height
        # requistion from the window's height requisition
        myrequest = widget.size_request()
        toplevel = self._xml.get_widget("toplevel")
        toprequest = toplevel.size_request()
        toplevel.resize(toprequest[0], toprequest[1] - myrequest[1])

    def _get_fs_selection_state(self, model, path, iter):
        fsname = self._fsListStore.get_value(iter, 3)    
        enabled = self._fsListStore.get_value(iter, 0)
        self._snapStateDic[fsname] = enabled

    def _get_rsync_selection_state(self, model, path, iter):
        fsname = self._fsListStore.get_value(iter, 3)
        enabled = self._fsListStore.get_value(iter, 1)
        self._rsyncStateDic[fsname] = enabled

    def _set_fs_selection_state(self, model, path, iter, selected):
        fsname = self._fsListStore.get_value(iter, 3)
        self._snapStateDic[fsname] = selected

    def _set_rsync_selection_state(self, model, path, iter, selected):
        fsname = self._fsListStore.get_value(iter, 3)
        self._rsyncStateDic[fsname] = selected

    def _refine_filesys_actions(self, fsname, inputdic, actions):
        selected = inputdic[fsname]
        try:
            fstag = actions[fsname]
            # Found so we can skip over.
        except KeyError:
            # Need to check parent value to see if
            # we should set explicitly or just inherit.
            path = fsname.rsplit("/", 1)
            parentName = path[0]
            if parentName == fsname:
                # Means this filesystem is the root of the pool
                # so we need to set it explicitly.
                actions[fsname] = \
                    FilesystemIntention(fsname, selected, False)
            else:
                parentIntent = None
                inherit = False
                # Check if parent is already set and if so whether to
                # inherit or override with a locally set property value.
                try:
                    # Parent has already been registered
                    parentIntent = actions[parentName]
                except:
                    # Parent not yet set, so do that recursively to figure
                    # out if we need to inherit or set a local property on
                    # this child filesystem.
                    self._refine_filesys_actions(parentName,
                                                  inputdic,
                                                  actions)
                    parentIntent = actions[parentName]
                if parentIntent.selected == selected:
                    inherit = True
                actions[fsname] = \
                    FilesystemIntention(fsname, selected, inherit)

    def _validate_rsync_target(self, path):
        """
            Tests path to see if it is the pre-configured
            rsync backup device path.
            Returns True on success, otherwise False
        """
        # FIXME - this is duplicate in applet.py and rsync-backup.py
        # It should be moved into a shared module
        if not os.path.exists(path):
            return False
        testDir = os.path.join(path,
                                rsyncsmf.RSYNCDIRPREFIX,
                                self._nodeName)
        testKeyFile = os.path.join(path,
                                    rsyncsmf.RSYNCDIRPREFIX,
                                    rsyncsmf.RSYNCCONFIGFILE)
        if os.path.exists(testDir) and \
            os.path.exists(testKeyFile):
            testKeyVal = None
            f = open(testKeyFile, 'r')
            for line in f.readlines():
                key, val = line.strip().split('=')
                if key.strip() == "target_key":
                    targetKey = val.strip()
                    break
            f.close()
            if targetKey == self._smfTargetKey:
                return True
        return False


    def commit_filesystem_selection(self):
        """
        Commits the intended filesystem selection actions based on the
        user's UI configuration to disk. Compares with initial startup
        configuration and applies the minimum set of necessary changes.
        """
        for fsname,fsmountpoint in self._datasets.list_filesystems():
            fs = zfs.Filesystem(fsname, fsmountpoint)
            try:
                initialIntent = self._initialFsIntentDic[fsname]
                intent = self._fsIntentDic[fsname]
                if intent == initialIntent:
                    continue
                fs.set_auto_snap(intent.selected, intent.inherited)

            except KeyError:
                pass

    def commit_rsync_selection(self):
        """
        Commits the intended filesystem selection actions based on the
        user's UI configuration to disk. Compares with initial startup
        configuration and applies the minimum set of necessary changes.
        """
        for fsname,fsmountpoint in self._datasets.list_filesystems():
            fs = zfs.Filesystem(fsname, fsmountpoint)
            try:
                initialIntent = self._initialRsyncIntentDic[fsname]
                intent = self._rsyncIntentDic[fsname]
                if intent == initialIntent:
                    continue
                if intent.inherited == True and \
                    initialIntent.inherited == False:
                    fs.unset_user_property(rsyncsmf.RSYNCFSTAG)
                else:
                    if intent.selected == True:
                        value = "true"
                    else:
                        value = "false"
                    fs.set_user_property(rsyncsmf.RSYNCFSTAG,
                                         value)
            except KeyError:
                pass

    def setup_rsync_config(self):
        if self._rsyncEnabled == True:
            if self._newRsyncTargetSelected == True:
                sys,nodeName,rel,ver,arch = os.uname()
                basePath = os.path.join(self._newRsyncTargetDir,
                                        rsyncsmf.RSYNCDIRPREFIX,)
                nodePath = os.path.join(basePath,
                                        nodeName)
                configPath = os.path.join(basePath,
                                          rsyncsmf.RSYNCCONFIGFILE)
                newKey = generate_random_key()
                try:
                    origmask = os.umask(0222)
                    if not os.path.exists(nodePath):
                        os.makedirs(nodePath, 0755)
                    f = open(configPath, 'w')
                    f.write("target_key=%s\n" % (newKey))
                    f.close()
                    os.umask(origmask)
                except OSError as e:
                    self._pulseDialog.hide()
                    sys.stderr.write("Error configuring external " \
                                     "backup device:\n" \
                                     "%s\n\nReason:\n %s") \
                                     % (self._newRsyncTargetDir, str(e))
                    sys.exit(-1)
                self._rsyncSMF.set_target_dir(self._newRsyncTargetDir)
                self._rsyncSMF.set_target_key(newKey)
                # Applet monitors rsyncTargetDir so make sure to notify it.
                self._configNotify = True
        return

    def setup_services(self):
        # Take care of the rsync plugin service first since time-slider
        # will query it.
        # Changes to rsync or time-slider SMF service State should be
        # broadcast to let notification applet refresh.
        if self._rsyncEnabled == True and \
            self._initialRsyncState == False:
            self._rsyncSMF.enable_service()
            self._configNotify = True
        elif self._rsyncEnabled == False and \
            self._initialRsyncState == True:
            self._rsyncSMF.disable_service()
            self._configNotify = True
        customSelection = self._xml.get_widget("selectfsradio").get_active()
        if customSelection != self._initialCustomSelection:
            self._sliderSMF.set_custom_selection(customSelection)
        if self._initialEnabledState == False:
            enable_default_schedules()
            self._sliderSMF.enable_service()
            self._configNotify = True

    def set_cleanup_level(self):
        """
        Wrapper function to set the warning level cleanup threshold
        value as a percentage of pool capacity.
        """
        level = self._xml.get_widget("capspinbutton").get_value_as_int()
        if level != self._initialCleanupLevel:
            self._sliderSMF.set_cleanup_level("warning", level)

    def broadcast_changes(self):
        """
        Blunt instrument to notify D-Bus listeners such as notification
        applet to rescan service configuration
        """
        if self._configNotify == False:
            return
        self._dbus.config_changed()

    def _on_deletesnapshots_clicked(self, widget):
        cmdpath = os.path.join(os.path.dirname(self._execPath), \
                               "../lib/time-slider-delete")
        p = subprocess.Popen(cmdpath, close_fds=True)


class EnableService(threading.Thread):

    def __init__(self, setupManager):
        threading.Thread.__init__(self)
        self._setupManager = setupManager

    def run(self):
        try:
            # Set the service state last so that the ZFS filesystems
            # are correctly tagged before the snapshot scripts check them
            self._setupManager.commit_filesystem_selection()
            self._setupManager.commit_rsync_selection()
            self._setupManager.set_cleanup_level()
            self._setupManager.setup_rsync_config()
            self._setupManager.setup_services()
            self._setupManager.broadcast_changes()
        except RuntimeError, message:
            sys.stderr.write(str(message))

def generate_random_key(length=32):
    """
    Returns a 'length' byte character composed of random letters and
    unsigned single digit integers. Used to create a random
    signature key to identify pre-configured backup directories
    for the rsync plugin
    """
    from string import letters, digits
    from random import choice
    return ''.join([choice(letters + digits) \
              for i in range(length)])

def main(argv):
    rbacp = RBACprofile()
    # The setup GUI needs to be run as root in order to ensure
    # that the rsync backup target directory is accessible by
    # root and to perform validation checks on it.
    # This GUI can be launched with an euid of root in one of
    # the following 3 ways;
    # 0. Run by the superuser (root)
    # 1. Run via gksu to allow a non priviliged user to authenticate
    #    as the superuser (root)

    if os.geteuid() == 0:
        manager = SetupManager(argv)
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()
    elif os.path.exists(argv) and os.path.exists("/usr/bin/gksu"):
        # Run via gksu, which will prompt for the root password
        os.unsetenv("DBUS_SESSION_BUS_ADDRESS")
        os.execl("/usr/bin/gksu", "gksu", argv)
        # Shouldn't reach this point
        sys.exit(1)
    else:
        dialog = gtk.MessageDialog(None,
                                   0,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   _("Insufficient Priviliges"))
        dialog.format_secondary_text(_("The snapshot manager service requires "
                                       "administrative privileges to run. "
                                       "You have not been assigned the necessary"
                                       "administrative priviliges."
                                       "\n\nConsult your system administrator "))
        dialog.set_icon_name("time-slider-setup")
        dialog.run()
        sys.exit(1)

