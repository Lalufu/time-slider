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
import gobject
import dbus
import dbus.decorators
import dbus.glib
import dbus.mainloop
import dbus.mainloop.glib
import gio
import gtk
import pygtk
import pynotify

from time_slider import util, rbac

from os.path import abspath, dirname, join, pardir
sys.path.insert(0, join(dirname(__file__), pardir, "plugin"))
import plugin
sys.path.insert(0, join(dirname(__file__), pardir, "plugin", "rsync"))
import backup, rsyncsmf

class Note:
    _iconConnected = False

    def __init__(self, icon, menu):
        self._note = None
        self._msgDialog = None
        self._menu = menu
        self._icon = icon
        if Note._iconConnected == False:
            self._icon.connect("popup-menu", self._popup_menu)
            Note._iconConnected = True
        self._icon.set_visible(True)

    def _popup_menu(self, icon, button, time):
        if button == 3:
            # Don't popup an empty menu
            if len(self._menu.get_children()) > 0:
                self._menu.popup(None, None,
                                 gtk.status_icon_position_menu,
                                 button, time, icon)

    def _dialog_response(self, dialog, response):
        dialog.destroy()

    def _notification_closed(self, notifcation):
        self._note = None
        self._icon.set_blinking(False)

    def _show_notification(self):
        if self._icon.is_embedded() == True:
            self._note.attach_to_status_icon(self._icon)
        self._note.show()
        return False

    def _connect_to_object(self):
        pass

    def refresh(self):
        pass

    def _watch_handler(self, new_owner = None):
        if new_owner == None or len(new_owner) == 0:
            pass
        else:
            self._connect_to_object()

    def _setup_icon_for_note(self, themed=None):
        if themed:
            iconList = themed.get_names()
        else:
            iconList = ['gnome-dev-harddisk']

        iconTheme = gtk.icon_theme_get_default()
        iconInfo = iconTheme.choose_icon(iconList, 48, 0)
        pixbuf = iconInfo.load_icon()

        self._note.set_category("device")
        self._note.set_icon_from_pixbuf(pixbuf)


class RsyncNote(Note):

    def __init__(self, icon, menu):
        Note.__init__(self, icon, menu)
        dbus.bus.NameOwnerWatch(bus,
                                "org.opensolaris.TimeSlider.plugin.rsync",
                                self._watch_handler)

        self.smfInst = rsyncsmf.RsyncSMF("%s:rsync" \
                                         % (plugin.PLUGINBASEFMRI))
        self._lock = threading.Lock()
        self._masterKey = None
        sys,self._nodeName,rel,ver,arch = os.uname()
        # References to gio.File and handler_id of a registered
        # monitor callback on gio.File
        self._fm = None
        self._fmID = None
        # References to gio.VolumeMonitor and handler_ids of
        # registered mount-added and mount-removed callbacks.
        self._vm = None
        self._vmAdd = None
        self._vmRem = None
        # Every time the rsync backup script runs it will
        # register with d-bus and trigger self._watch_handler().
        # Use this variable to keep track of it's running status.
        self._scriptRunning = False
        self._targetDirAvail = False
        self._syncNowItem = gtk.MenuItem(_("Update Backups Now"))
        self._syncNowItem.set_sensitive(False)
        self._syncNowItem.connect("activate",
                                  self._sync_now)
        self._menu.append(self._syncNowItem)

        self.refresh()

    def _validate_rsync_target(self, path):
        """
           Tests path to see if it is the pre-configured
           rsync backup device path.
           Returns True on success, otherwise False
        """
        if not os.path.exists(path):
            return False
        testDir = join(path,
                       rsyncsmf.RSYNCDIRPREFIX,
                       self._nodeName)
        testKeyFile = join(path,
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
            if targetKey == self._masterKey:
                return True
        return False

    def _setup_monitor(self):
        # Disconnect any previously registered signal
        # handlers
        if self._fm:
            self._fm.disconnect(self._fmID)
            self._fm = None

        useVolMonitor = False        

        # We always compare against masterKey to validate
        # an rsync backup device.
        self._masterKey = self.smfInst.get_target_key()
        self._baseTargetDir = None
        online = False

        self._masterTargetDir = self.smfInst.get_target_dir()

        if self._validate_rsync_target(self._masterTargetDir) == True:
            self._baseTargetDir = self._masterTargetDir
            online = True

        if self._vm == None:
            self._vm = gio.volume_monitor_get()

        # If located, see if it's also managed by the volume monitor.
        # Or just try to find it otherwise.
        mounts = self._vm.get_mounts()
        for mount in mounts:
            root = mount.get_root()
            path = root.get_path()
            if self._baseTargetDir != None and \
                path == self._baseTargetDir:
                # Means the directory we found is gio monitored,
                # so just monitor it using gio.VolumeMonitor.
                useVolMonitor = True
                break
            elif self._validate_rsync_target(path) == True:
                # Found it but not where we expected it to be so override
                # the target path defined by SMF for now.
                useVolMonitor = True
                self._baseTargetDir = path
                online = True
                break

        if self._baseTargetDir == None:
            # Means we didn't find it, and we don't know where to expect
            # it either - via a hotpluggable device or other nfs/zfs etc.
            # We need to hedge our bets and monitor for both.
            self._setup_file_monitor(self._masterTargetDir)
            self._setup_volume_monitor()
        else:
            # Found it
            if useVolMonitor == True:
                # Looks like a removable device. Use gio.VolumeMonitor
                # as the preferred monitoring mechanism.
                self._setup_volume_monitor()
            else:
                # Found it on a static mount point like a zfs or nfs
                # mount point.
                # Can't use gio.VolumeMonitor so use a gio.File monitor
                # instead.
                self._setup_file_monitor(self._masterTargetDir)

        # Finally, update the UI menu state
        self._lock.acquire()
        self._targetDirAvail = online
        self._update_menu_state()
        self._lock.release()
            
            
    def _setup_file_monitor(self, expectedPath):
        # Use gio.File monitor as a fallback in 
        # case gio.VolumeMonitor can't track the device.
        # This is the case for static/manual mount points
        # such as NFS, ZFS and other non-hotpluggables.
        gFile = gio.File(path=expectedPath)
        self._fm = gFile.monitor_file(gio.FILE_MONITOR_WATCH_MOUNTS)
        self._fmID = self._fm.connect("changed",
                                      self._file_monitor_changed)

    def _setup_volume_monitor(self):
        # Check the handler_ids first to see if they have 
        # already been connected. Avoids multiple callbacks
        # for a single event
        if self._vmAdd == None:
            self._vmAdd = self._vm.connect("mount-added",
                                           self._mount_added)
        if self._vmRem == None:
            self._vmRem = self._vm.connect("mount-removed",
                                           self._mount_removed)
            
    def _mount_added(self, monitor, mount):
        root = mount.get_root()
        path = root.get_path()
        if self._validate_rsync_target(path) == True:
            # Since gio.VolumeMonitor found the rsync target, don't
            # bother relying on gio.File to find it any more. Disconnect
            # it's registered callbacks.
            if self._fm:
                self._fm.disconnect(self._fmID)
                self._fm = None
            self._lock.acquire()
            self._baseTargetDir = path
            self._targetDirAvail = True
            self._update_menu_state()
            self._lock.release()

    def _mount_removed(self, monitor, mount):
        root = mount.get_root()
        path = root.get_path()
        if path == self._baseTargetDir:
            self._lock.acquire()
            self._targetDirAvail = False
            self._update_menu_state()
            self._lock.release()

    def _file_monitor_changed(self, filemonitor, file, other_file, event_type):
        if file.get_path() == self._masterTargetDir:
            self._lock.acquire()
            if self._validate_rsync_target(self._masterTargetDir) == True:
                self._targetDirAvail = True
            else:
                self._targetDirAvail = False
            self._update_menu_state()
            self._lock.release()            

    def _update_menu_state(self):
        if self._syncNowItem:
            if self._targetDirAvail == True and \
                self._scriptRunning == False:
                self._syncNowItem.set_sensitive(True)
            else:
                self._syncNowItem.set_sensitive(False)

    def _watch_handler(self, new_owner = None):
        self._lock.acquire()
        if new_owner == None or len(new_owner) == 0:
            # Script not running or exited
            self._scriptRunning = False
        else:
            self._scriptRunning = True
            self._connect_to_object()
        self._update_menu_state()
        self._lock.release()

    def _rsync_started_handler(self, target, sender=None, interface=None, path=None):
        urgency = pynotify.URGENCY_NORMAL
        if (self._note != None):
            self._note.close()
        # Try to pretty things up a bit by displaying volume name
        # and hinted icon instead of the raw device path,
        # and standard harddisk icon if possible.
        icon = None
        volume = util.path_to_volume(target)
        if volume == None:
            volName = target
        else:
            volName = volume.get_name()
            icon = volume.get_icon()
                      
        self._note = pynotify.Notification(_("Backup Started"),
                                           _("Backing up snapshots to:\n<b>%s</b>\n" \
                                           "Do not disconnect the backup device.") \
                                            % (volName))
        self._note.connect("closed", \
                           self._notification_closed)
        self._note.set_urgency(urgency)
        self._setup_icon_for_note(icon)
        gobject.idle_add(self._show_notification)

    def _rsync_current_handler(self, snapshot, remaining, sender=None, interface=None, path=None):
        self._icon.set_tooltip_markup(_("Backing up: <b>\'%s\'\n%d</b> snapshots remaining.\n" \
                                      "Do not disconnect the backup device.") \
                                      % (snapshot, remaining))

    def _rsync_complete_handler(self, target, sender=None, interface=None, path=None):
        urgency = pynotify.URGENCY_NORMAL
        if (self._note != None):
            self._note.close()
        # Try to pretty things up a bit by displaying volume name
        # and hinted icon instead of the raw device path,
        # and standard harddisk icon if possible.
        icon = None
        volume = util.path_to_volume(target)
        if volume == None:
            volName = target
        else:
            volName = volume.get_name()
            icon = volume.get_icon()

        self._note = pynotify.Notification(_("Backup Complete"),
                                           _("Your snapshots have been backed up to:\n<b>%s</b>") \
                                           % (volName))
        self._note.connect("closed", \
                           self._notification_closed)
        self._note.set_urgency(urgency)
        self._setup_icon_for_note(icon)
        self._icon.set_has_tooltip(False)
        self.queueSize = 0
        gobject.idle_add(self._show_notification)

    def _rsync_synced_handler(self, sender=None, interface=None, path=None):
        self._icon.set_tooltip_markup(_("Your backups are up to date."))
        self.queueSize = 0

    def _rsync_unsynced_handler(self, queueSize, sender=None, interface=None, path=None):
        self._icon.set_tooltip_markup(_("%d snapshots are queued for backup.") \
                                      % (queueSize))
        self.queueSize = queueSize

    def _connect_to_object(self):
        try:
            remote_object = bus.get_object("org.opensolaris.TimeSlider.plugin.rsync",
                                           "/org/opensolaris/TimeSlider/plugin/rsync")
        except dbus.DBusException:
            sys.stderr.write("Failed to connect to remote D-Bus object: " + \
                             "/org/opensolaris/TimeSlider/plugin/rsync")
            return

        # Create an Interface wrapper for the remote object
        iface = dbus.Interface(remote_object, "org.opensolaris.TimeSlider.plugin.rsync")

        iface.connect_to_signal("rsync_started", self._rsync_started_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')
        iface.connect_to_signal("rsync_current", self._rsync_current_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')
        iface.connect_to_signal("rsync_complete", self._rsync_complete_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')
        iface.connect_to_signal("rsync_synced", self._rsync_synced_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')
        iface.connect_to_signal("rsync_unsynced", self._rsync_unsynced_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')

    def refresh(self):
        # Hide/Unhide rsync menu item based on whether the plugin is online
        if self._syncNowItem and \
           self.smfInst.get_service_state() == "online":
            #self._setup_file_monitor()
            self._setup_monitor()
            # Kick start things by initially obtaining the
            # backlog size and triggering a callback.
            # Signal handlers will keep tooltip status up
            # to date afterwards when the backup cron job
            # executes.
            propName = "%s:rsync" % (backup.propbasename)
            queue = backup.list_pending_snapshots(propName)
            self.queueSize = len(queue)
            if self.queueSize == 0:
                self._rsync_synced_handler()
            else:
                self._rsync_unsynced_handler(self.queueSize)
            self._syncNowItem.show()
        else:
            self._syncNowItem.hide()

    def _sync_now(self, menuItem):
        """Runs the rsync-backup script manually
           Assumes that user is root since it is only
           called from the menu item which is invisible to
           not authorised users
        """
        cmdPath = os.path.join(os.path.dirname(sys.argv[0]), \
                               "time-slider/plugins/rsync/rsync-backup")
        if os.geteuid() == 0:
	  cmd = [cmdPath, \
		 "%s:rsync" % (plugin.PLUGINBASEFMRI)]
	else:
	  cmd = ['/usr/bin/gksu' ,cmdPath, \
		 "%s:rsync" % (plugin.PLUGINBASEFMRI)]

	subprocess.Popen(cmd, close_fds=True, cwd="/")


class CleanupNote(Note):

    def __init__(self, icon, menu):
        Note.__init__(self, icon, menu)
        self._cleanupHead = None
        self._cleanupBody = None
        dbus.bus.NameOwnerWatch(bus,
                                "org.opensolaris.TimeSlider",
                                self._watch_handler)

    def _show_cleanup_details(self, *args):
        # We could keep a dialog around but this a rare
        # enough event that's it not worth the effort.
        dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                   buttons=gtk.BUTTONS_CLOSE)
        dialog.set_title(_("Time Slider: Low Space Warning"))
        dialog.set_markup("<b>%s</b>" % (self._cleanupHead))
        dialog.format_secondary_markup(self._cleanupBody)
        dialog.show()
        dialog.present()
        dialog.connect("response", self._dialog_response)

    def _cleanup_handler(self, pool, severity, threshhold, sender=None, interface=None, path=None):
        if severity == 4:
            expiry = pynotify.EXPIRES_NEVER
            urgency = pynotify.URGENCY_CRITICAL
            self._cleanupHead = _("Emergency: \'%s\' is full!") % pool
            notifyBody = _("The file system: \'%s\', is over %s%% full.") \
                            % (pool, threshhold)
            self._cleanupBody = _("The file system: \'%s\', is over %s%% full.\n"
                     "As an emergency measure, Time Slider has "
                     "destroyed all of its backups.\nTo fix this problem, "
                     "delete any unnecessary files on \'%s\', or add "
                     "disk space (see ZFS documentation).") \
                      % (pool, threshhold, pool)
        elif severity == 3:
            expiry = pynotify.EXPIRES_NEVER
            urgency = pynotify.URGENCY_CRITICAL
            self._cleanupHead = _("Emergency: \'%s\' is almost full!") % pool
            notifyBody = _("The file system: \'%s\', exceeded %s%% "
                           "of its total capacity") \
                            % (pool, threshhold)
            self._cleanupBody = _("The file system: \'%s\', exceeded %s%% "
                     "of its total capacity. As an emerency measure, "
                     "Time Slider has has destroyed most or all of its "
                     "backups to prevent the disk becoming full. "
                     "To prevent this from happening again, delete "
                     "any unnecessary files on \'%s\', or add disk "
                     "space (see ZFS documentation).") \
                      % (pool, threshhold, pool)
        elif severity == 2:
            expiry = pynotify.EXPIRES_NEVER
            urgency = pynotify.URGENCY_CRITICAL
            self._cleanupHead = _("Urgent: \'%s\' is almost full!") % pool
            notifyBody = _("The file system: \'%s\', exceeded %s%% "
                           "of its total capacity") \
                            % (pool, threshhold)
            self._cleanupBody = _("The file system: \'%s\', exceeded %s%% "
                     "of its total capacity. As a remedial measure, "
                     "Time Slider has destroyed some backups, and will "
                     "destroy more, eventually all, as capacity continues "
                     "to diminish.\nTo prevent this from happening again, "
                     "delete any unnecessary files on \'%s\', or add disk "
                     "space (see ZFS documentation).") \
                     % (pool, threshhold, pool)
        elif severity == 1:
            expiry = 20000 # 20 seconds
            urgency = pynotify.URGENCY_NORMAL
            self._cleanupHead = _("Warning: \'%s\' is getting full") % pool
            notifyBody = _("The file system: \'%s\', exceeded %s%% "
                           "of its total capacity") \
                            % (pool, threshhold)
            self._cleanupBody = _("\'%s\' exceeded %s%% of its total "
                     "capacity. To fix this, Time Slider has destroyed "
                     "some recent backups, and will destroy more as "
                     "capacity continues to diminish.\nTo prevent "
                     "this from happening again, delete any "
                     "unnecessary files on \'%s\', or add disk space "
                     "(see ZFS documentation).\n") \
                     % (pool, threshhold, pool)
        else:
            return # No other values currently supported

        if (self._note != None):
            self._note.close()
        self._note = pynotify.Notification(self._cleanupHead,
                                           notifyBody)
        self._note.add_action("clicked",
                              _("Details..."),
                              self._show_cleanup_details)
        self._note.connect("closed",
                           self._notification_closed)
        self._note.set_urgency(urgency)
        self._note.set_timeout(expiry)
        self._setup_icon_for_note()
        self._icon.set_blinking(True)
        gobject.idle_add(self._show_notification)

    def _connect_to_object(self):
        try:
            remote_object = bus.get_object("org.opensolaris.TimeSlider",
                                           "/org/opensolaris/TimeSlider/autosnap")
        except dbus.DBusException:
            sys.stderr.write("Failed to connect to remote D-Bus object: " + \
                             "/org/opensolaris/TimeSlider/autosnap")

        #Create an Interface wrapper for the remote object
        iface = dbus.Interface(remote_object, "org.opensolaris.TimeSlider.autosnap")

        iface.connect_to_signal("capacity_exceeded", self._cleanup_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')



class SetupNote(Note):

    def __init__(self, icon, menu, manager):
        Note.__init__(self, icon, menu)
        # We are passed a reference to out parent so we can
        # provide it notification which it can then circulate
        # to other notification objects such as Rsync and
        # Cleanup
        self._manager = manager
        self._icon = icon
        self._menu = menu
        self._configSvcItem = gtk.MenuItem(_("Configure Time Slider..."))
        self._configSvcItem.connect("activate",
                                    self._run_config_app)
        self._configSvcItem.set_sensitive(True)
        self._menu.append(self._configSvcItem)
        self._configSvcItem.show()
        dbus.bus.NameOwnerWatch(bus,
                                "org.opensolaris.TimeSlider.config",
                                self._watch_handler)

    def _connect_to_object(self):
        try:
            remote_object = bus.get_object("org.opensolaris.TimeSlider.config",
                                           "/org/opensolaris/TimeSlider/config")
        except dbus.DBusException:
            sys.stderr.write("Failed to connect to remote D-Bus object: " + \
                             "/org/opensolaris/TimeSlider/config")

        #Create an Interface wrapper for the remote object
        iface = dbus.Interface(remote_object, "org.opensolaris.TimeSlider.config")

        iface.connect_to_signal("config_changed", self._config_handler, sender_keyword='sender',
                                interface_keyword='interface', path_keyword='path')

    def _config_handler(self, sender=None, interface=None, path=None):
        # Notify the manager.
        # This will eventually propogate through to an invocation
        # of our own refresh() method.
        self._manager.refresh()

    def _run_config_app(self, menuItem):
        cmdPath = os.path.join(os.path.dirname(sys.argv[0]),
                           os.path.pardir,
                           "bin",
                           "time-slider-setup")
        cmd = os.path.abspath(cmdPath)
        # The setup GUI deals with it's own security and 
        # authorisation, so no need to pfexec it. Any
        # changes made to configuration will come back to
        # us by way of D-Bus notification.
        subprocess.Popen(cmd, close_fds=True)

class NoteManager():
    def __init__(self):
        # Notification objects need to share a common
        # status icon and popup menu so these are created
        # outside the object and passed to the constructor
        self._menu = gtk.Menu()
        self._icon = gtk.StatusIcon()
        self._icon.set_from_icon_name("time-slider-setup")
        self._setupNote = SetupNote(self._icon,
                                    self._menu,
                                    self)
        self._cleanupNote = CleanupNote(self._icon,
                                        self._menu)
        self._rsyncNote = RsyncNote(self._icon,
                                    self._menu)

    def refresh(self):
        self._rsyncNote.refresh()

bus = dbus.SystemBus()

def main(argv):
    mainloop = gobject.MainLoop()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default = True)
    gobject.threads_init()
    pynotify.init(_("Time Slider"))

    noteManager = NoteManager()

    try:
        mainloop.run()
    except:
        print "Exiting"

if __name__ == '__main__':
    main()

