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
        fs = zfs.Filesystem (self.fsname)
        self.zfs_mountpoint = fs.get_mountpoint ()

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

        log = "%s/%s/%s/%s.log" % (self.rsync_dir,
                                   self.fsname,
                                   rsyncsmf.RSYNCLOGSUFFIX,
                                   self.snaplabel)
        if os.path.exists (log):
            os.unlink (log)

        lockFp.close()
        os.unlink(lockFile)

class DeleteSnapManager:

    def __init__(self, snapshots = None):
        self.xml = gtk.glade.XML("%s/../../glade/time-slider-delete.glade" \
                                  % (os.path.dirname(__file__)))
        self.backuptodelete = []
        self.shortcircuit = []
        maindialog = self.xml.get_widget("time-slider-delete")
        self.pulsedialog = self.xml.get_widget("pulsedialog")
        self.pulsedialog.set_transient_for(maindialog)
        self.datasets = zfs.Datasets()
        if snapshots:
            maindialog.hide()
            self.shortcircuit = snapshots
        else:
            glib.idle_add(self.__init_scan)

        self.progressdialog = self.xml.get_widget("deletingdialog")
        self.progressdialog.set_transient_for(maindialog)
        self.progressbar = self.xml.get_widget("deletingprogress")
        # signal dictionary
        dic = {"on_closebutton_clicked" : gtk.main_quit,
               "on_window_delete_event" : gtk.main_quit,
               "on_snapshotmanager_delete_event" : gtk.main_quit,
               "on_fsfilterentry_changed" : self.__on_filterentry_changed,
               "on_schedfilterentry_changed" : self.__on_filterentry_changed,
               "on_typefiltercombo_changed" : self.__on_filterentry_changed,
               "on_selectbutton_clicked" : self.__on_selectbutton_clicked,
               "on_deselectbutton_clicked" : self.__on_deselectbutton_clicked,
               "on_deletebutton_clicked" : self.__on_deletebutton_clicked,
               "on_confirmcancel_clicked" : self.__on_confirmcancel_clicked,
               "on_confirmdelete_clicked" : self.__on_confirmdelete_clicked,
               "on_errordialog_response" : self.__on_errordialog_response}
        self.xml.signal_autoconnect(dic)

    def initialise_view(self):
        if len(self.shortcircuit) == 0:
            # Set TreeViews
            self.liststorefs = gtk.ListStore(str, str, str, str, str, long,
                                             gobject.TYPE_PYOBJECT)
            list_filter = self.liststorefs.filter_new()
            list_sort = gtk.TreeModelSort(list_filter)
            list_sort.set_sort_column_id(1, gtk.SORT_ASCENDING)

            self.snaptreeview = self.xml.get_widget("snaplist")
            self.snaptreeview.set_model(self.liststorefs)
            self.snaptreeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

            cell0 = gtk.CellRendererText()
            cell1 = gtk.CellRendererText()
            cell2 = gtk.CellRendererText()
            cell3 = gtk.CellRendererText()
            cell4 = gtk.CellRendererText()
            cell5 = gtk.CellRendererText()

            typecol = gtk.TreeViewColumn(_("Type"),
                                            cell0, text = 0)
            typecol.set_sort_column_id(0)
            typecol.set_resizable(True)
            typecol.connect("clicked",
                self.__on_treeviewcol_clicked, 0)
            self.snaptreeview.append_column(typecol)

            mountptcol = gtk.TreeViewColumn(_("Mount Point"),
                                            cell1, text = 1)
            mountptcol.set_sort_column_id(1)
            mountptcol.set_resizable(True)
            mountptcol.connect("clicked",
                self.__on_treeviewcol_clicked, 1)
            self.snaptreeview.append_column(mountptcol)

            fsnamecol = gtk.TreeViewColumn(_("File System Name"),
                                           cell2, text = 2)
            fsnamecol.set_sort_column_id(2)
            fsnamecol.set_resizable(True)
            fsnamecol.connect("clicked",
                self.__on_treeviewcol_clicked, 2)
            self.snaptreeview.append_column(fsnamecol)

            snaplabelcol = gtk.TreeViewColumn(_("Snapshot Name"),
                                              cell3, text = 3)
            snaplabelcol.set_sort_column_id(3)
            snaplabelcol.set_resizable(True)
            snaplabelcol.connect("clicked",
                self.__on_treeviewcol_clicked, 3)
            self.snaptreeview.append_column(snaplabelcol)

            cell4.props.xalign = 1.0
            creationcol = gtk.TreeViewColumn(_("Creation Time"),
                                             cell4, text = 4)
            creationcol.set_sort_column_id(5)
            creationcol.set_resizable(True)
            creationcol.connect("clicked",
                self.__on_treeviewcol_clicked, 5)
            self.snaptreeview.append_column(creationcol)

            # Note to developers.
            # The second element is for internal matching and should not
            # be i18ned under any circumstances.
            typestore = gtk.ListStore(str, str)
            typestore.append([_("All"), "All"])
            typestore.append([_("Backups"), "Backup"])
            typestore.append([_("Snapshots"), "Snapshot"])

            self.typefiltercombo = self.xml.get_widget("typefiltercombo")
            self.typefiltercombo.set_model(typestore)
            typefiltercomboCell = gtk.CellRendererText()
            self.typefiltercombo.pack_start(typefiltercomboCell, True)
            self.typefiltercombo.add_attribute(typefiltercomboCell, 'text',0)

            # Note to developers.
            # The second element is for internal matching and should not
            # be i18ned under any circumstances.
            fsstore = gtk.ListStore(str, str)
            fslist = self.datasets.list_filesystems()
            fsstore.append([_("All"), None])
            for fsname,fsmount in fslist:
                fsstore.append([fsname, fsname])
            self.fsfilterentry = self.xml.get_widget("fsfilterentry")
            self.fsfilterentry.set_model(fsstore)
            self.fsfilterentry.set_text_column(0)
            fsfilterentryCell = gtk.CellRendererText()
            self.fsfilterentry.pack_start(fsfilterentryCell)

            schedstore = gtk.ListStore(str, str)
            # Note to developers.
            # The second element is for internal matching and should not
            # be i18ned under any circumstances.
            schedstore.append([_("All"), None])
            schedstore.append([_("Monthly"), "monthly"])
            schedstore.append([_("Weekly"), "weekly"])
            schedstore.append([_("Daily"), "daily"])
            schedstore.append([_("Hourly"), "hourly"])
            schedstore.append([_("1/4 Hourly"), "frequent"])
            self.schedfilterentry = self.xml.get_widget("schedfilterentry")
            self.schedfilterentry.set_model(schedstore)
            self.schedfilterentry.set_text_column(0)
            schedentryCell = gtk.CellRendererText()
            self.schedfilterentry.pack_start(schedentryCell)

            self.schedfilterentry.set_active(0)
            self.fsfilterentry.set_active(0)
            self.typefiltercombo.set_active(0)
        else:
            cloned = self.datasets.list_cloned_snapshots()
            num_snap = 0
            num_rsync = 0
            for snapname in self.shortcircuit:
                # Filter out snapshots that are the root
                # of cloned filesystems or volumes
                try:
                    cloned.index(snapname)
                    dialog = gtk.MessageDialog(None,
                                   0,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   _("Snapshot can not be deleted"))
                    text = _("%s has one or more dependent clones "
                             "and will not be deleted. To delete "
                             "this snapshot, first delete all "
                             "datasets and snapshots cloned from "
                             "this snapshot.") \
                             % snapname
                    dialog.format_secondary_text(text)
                    dialog.run()
                    sys.exit(1)
                except ValueError:
                    path = os.path.abspath (snapname)
                    if not os.path.exists (path):
                        snapshot = zfs.Snapshot(snapname)
                        self.backuptodelete.append(snapshot)
                        num_snap += 1
                    else:
                        self.backuptodelete.append(RsyncBackup (snapname))
                        num_rsync += 1

            confirm = self.xml.get_widget("confirmdialog")
            summary = self.xml.get_widget("summarylabel")
            total = len(self.backuptodelete)

            text = ""
            if num_rsync != 0 :
                if num_rsync == 1:
                    text = _("1 external backup will be deleted.")
                else:
                    text = _("%d external backups will be deleted.") % num_rsync

            if num_snap != 0 :
                if len(text) != 0:
                    text += "\n"
                if num_snap == 1:
                    text += _("1 snapshot will be deleted.")
                else:
                    text += _("%d snapshots will be deleted.") % num_snap

            summary.set_text(text )
            response = confirm.run()
            if response != 2:
                sys.exit(0)
            else:
                # Create the thread in an idle loop in order to
                # avoid deadlock inside gtk.
                glib.idle_add(self.__init_delete)
        return False

    def __on_treeviewcol_clicked(self, widget, searchcol):
        self.snaptreeview.set_search_column(searchcol)

    def __filter_snapshot_list(self, list, filesys = None, snap = None, btype = None):
        if filesys == None and snap == None and btype == None:
            return list
        fssublist = []
        if filesys != None:
            for snapshot in list:
                if snapshot.fsname.find(filesys) != -1:
                    fssublist.append(snapshot)
        else:
            fssublist = list

        snaplist = []
        if snap != None:
            for snapshot in fssublist:
                if  snapshot.snaplabel.find(snap) != -1:
                    snaplist.append(snapshot)
        else:
            snaplist = fssublist

        typelist = []
        if btype != None and btype != "All":
            for item in snaplist:
                if btype == "Backup":
                    if isinstance(item, RsyncBackup):
                        typelist.append (item)
                else:
                    if isinstance(item, zfs.Snapshot):
                        typelist.append (item)
        else:
            typelist = snaplist

        return typelist

    def __on_filterentry_changed(self, widget):
        # Get the filesystem filter value
        iter = self.fsfilterentry.get_active_iter()
        if iter == None:
            filesys = self.fsfilterentry.get_active_text()
        else:
            model = self.fsfilterentry.get_model()
            filesys = model.get(iter, 1)[0]
        # Get the snapshot name filter value
        iter = self.schedfilterentry.get_active_iter()
        if iter == None:
            snap = self.schedfilterentry.get_active_text()
        else:
            model = self.schedfilterentry.get_model()
            snap = model.get(iter, 1)[0]

        # Get the type filter value
        iter = self.typefiltercombo.get_active_iter()
        if iter == None:
            type = "All"
        else:
            model = self.typefiltercombo.get_model()
            type = model.get(iter, 1)[0]

        self.liststorefs.clear()
        newlist = self.__filter_snapshot_list(self.snapscanner.snapshots,
                    filesys,
                    snap, type)
        for snapshot in newlist:
            try:
                tm = time.localtime(snapshot.get_creation_time())
                t = unicode(time.strftime ("%c", tm),
                    locale.getpreferredencoding()).encode('utf-8')
            except:
                t = time.ctime(snapshot.get_creation_time())
            try:
                mount_point = self.snapscanner.mounts[snapshot.fsname]
                if (mount_point == "legacy"):
                    mount_point = _("Legacy")

                self.liststorefs.append([
                       _("Snapshot"),
                       mount_point,
                       snapshot.fsname,
                       snapshot.snaplabel,
                       t,
                       snapshot.get_creation_time(),
                       snapshot])
            except KeyError:
                continue
                # This will catch exceptions from things we ignore
                # such as dump as swap volumes and skip over them.
            # add rsync backups
        newlist = self.__filter_snapshot_list(self.snapscanner.rsynced_backups,
                                                filesys,
                                                snap, type)
        for backup in newlist:
            self.liststorefs.append([_("Backup"),
                                     backup.zfs_mountpoint,
                                     backup.fsname,
                                     backup.snaplabel,
                                     backup.creationtime_str,
                                     backup.creationtime,
                                     backup])

    def __on_selectbutton_clicked(self, widget):
        selection = self.snaptreeview.get_selection()
        selection.select_all()
        return

    def __on_deselectbutton_clicked(self, widget):
        selection = self.snaptreeview.get_selection()
        selection.unselect_all()
        return

    def __on_deletebutton_clicked(self, widget):
        self.backuptodelete = []
        selection = self.snaptreeview.get_selection()
        selection.selected_foreach(self.__add_selection)
        total = len(self.backuptodelete)
        if total <= 0:
            return

        confirm = self.xml.get_widget("confirmdialog")
        summary = self.xml.get_widget("summarylabel")

        num_snap = 0
        num_rsync = 0
        for item in self.backuptodelete:
            if isinstance (item, RsyncBackup):
                num_rsync+=1
            else:
                num_snap+=1

        str = ""
        if num_rsync != 0 :
            if num_rsync == 1:
                str = _("1 external backup will be deleted.")
            else:
                str = _("%d external backups will be deleted.") % num_rsync

        if num_snap != 0 :
            if len(str) != 0:
                str += "\n"
            if num_snap == 1:
                str += _("1 snapshot will be deleted.")
            else:
                str += _("%d snapshots will be deleted.") % num_snap

        summary.set_text(str)
        response = confirm.run()
        if response != 2:
            return
        else:
            glib.idle_add(self.__init_delete)
        return

    def __init_scan(self):
        self.snapscanner = ScanSnapshots()
        self.pulsedialog.show()
        self.snapscanner.start()
        glib.timeout_add(100, self.__monitor_scan)
        return False

    def __init_delete(self):
        self.snapdeleter = DeleteSnapshots(self.backuptodelete)
        # If there's more than a few snapshots, pop up
        # a progress bar.
        if len(self.backuptodelete) > 3:
            self.progressbar.set_fraction(0.0)
            self.progressdialog.show()
        self.snapdeleter.start()
        glib.timeout_add(300, self.__monitor_deletion)
        return False

    def __monitor_scan(self):
        if self.snapscanner.isAlive() == True:
            self.xml.get_widget("pulsebar").pulse()
            return True
        else:
            self.pulsedialog.hide()
            if self.snapscanner.errors:
                details = ""
                dialog = gtk.MessageDialog(None,
                            0,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_CLOSE,
                            _("Some snapshots could not be read"))
                dialog.connect("response",
                            self.__on_errordialog_response)
                for error in self.snapscanner.errors:
                    details = details + error
                dialog.format_secondary_text(details)
                dialog.show()
            self.__on_filterentry_changed(None)
            return False

    def __monitor_deletion(self):
        if self.snapdeleter.isAlive() == True:
            self.progressbar.set_fraction(self.snapdeleter.progress)
            return True
        else:
            self.progressdialog.hide()
            self.progressbar.set_fraction(1.0)
            self.progressdialog.hide()
            if self.snapdeleter.errors:
                details = ""
                dialog = gtk.MessageDialog(None,
                            0,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_CLOSE,
                            _("Some snapshots could not be deleted"))
                dialog.connect("response",
                            self.__on_errordialog_response)
                for error in self.snapdeleter.errors:
                    details = details + error
                dialog.format_secondary_text(details)
                dialog.show()
            # If we didn't shortcircut straight to the delete confirmation
            # dialog then the main dialog is visible so we rebuild the list
            # view.
            if len(self.shortcircuit) ==  0:
                self.__refresh_view()
            else:
                gtk.main_quit()
            return False

    def __refresh_view(self):
        self.liststorefs.clear()
        glib.idle_add(self.__init_scan)
        self.backuptodelete = []

    def __add_selection(self, treemodel, path, iter):
        snapshot = treemodel.get(iter, 6)[0]
        self.backuptodelete.append(snapshot)

    def __on_confirmcancel_clicked(self, widget):
        widget.get_toplevel().hide()
        widget.get_toplevel().response(1)

    def __on_confirmdelete_clicked(self, widget):
        widget.get_toplevel().hide()
        widget.get_toplevel().response(2)

    def __on_errordialog_response(self, widget, responseid):
        widget.hide()

class ScanSnapshots(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.errors = []
        self.datasets = zfs.Datasets()
        self.snapshots = []
        self.rsynced_fs = []
        self.rsynced_backups = []

    def run(self):
        self.mounts = self.__get_fs_mountpoints()
        self.rsyncsmf = rsyncsmf.RsyncSMF("%s:rsync" %(plugin.PLUGINBASEFMRI))
        self.__get_rsync_backups ()
        self.rescan()

    def __get_rsync_backups (self):
        # get rsync backup dir
        self.rsyncsmf = rsyncsmf.RsyncSMF("%s:rsync" %(plugin.PLUGINBASEFMRI))
        rsyncBaseDir = self.rsyncsmf.get_target_dir()
        sys,nodeName,rel,ver,arch = os.uname()
        self.rsyncDir = os.path.join(rsyncBaseDir,
                                     rsyncsmf.RSYNCDIRPREFIX,
                                     nodeName)
        if not os.path.exists(self.rsyncDir):
            return

        rootBackupDirs = []

        for root, dirs, files in os.walk(self.rsyncDir):
            if '.time-slider' in dirs:
                dirs.remove('.time-slider')
                backupDir = os.path.join(root, rsyncsmf.RSYNCDIRSUFFIX)
                if os.path.exists(backupDir):
                    insort(rootBackupDirs, os.path.abspath(backupDir))

        for dirName in rootBackupDirs:
            os.chdir(dirName)
            for d in os.listdir(dirName):
                if os.path.isdir(d) and not os.path.islink(d):
                    s1 = dirName.split ("%s/" % self.rsyncDir, 1)
                    s2 = s1[1].split ("/%s" % rsyncsmf.RSYNCDIRSUFFIX, 1)
                    fs = s2[0]

                    rb = RsyncBackup ("%s/%s" %(dirName, d),
                                      self.rsyncDir,
                                      fs,
                                      d,
                                      os.stat(d).st_mtime)
                    self.rsynced_backups.append (rb)

    def __get_fs_mountpoints(self):
        """Returns a dictionary mapping:
           {filesystem : mountpoint}"""
        result = {}
        for filesys,mountpoint in self.datasets.list_filesystems():
            result[filesys] = mountpoint
        return result

    def rescan(self):
        cloned = self.datasets.list_cloned_snapshots()
        self.snapshots = []
        snaplist = self.datasets.list_snapshots()
        for snapname,snaptime in snaplist:
            # Filter out snapshots that are the root
            # of cloned filesystems or volumes
            try:
                cloned.index(snapname)
            except ValueError:
                snapshot = zfs.Snapshot(snapname, snaptime)
                self.snapshots.append(snapshot)

class DeleteSnapshots(threading.Thread):

    def __init__(self, snapshots):
        threading.Thread.__init__(self)
        self.backuptodelete = snapshots
        self.started = False
        self.completed = False
        self.progress = 0.0
        self.errors = []

    def run(self):
        deleted = 0
        self.started = True
        total = len(self.backuptodelete)
        for backup in self.backuptodelete:
            # The backup could have expired and been automatically
            # destroyed since the user selected it. Check that it
            # still exists before attempting to delete it. If it
            # doesn't exist just silently ignore it.
            if backup.exists():
                try:
                    backup.destroy ()
                except RuntimeError, inst:
                    self.errors.append(str(inst))
            deleted += 1
            self.progress = deleted / (total * 1.0)
        self.completed = True

def main(argv):
    try:
        opts,args = getopt.getopt(sys.argv[1:], "", [])
    except getopt.GetoptError:
        sys.exit(2)
    rbacp = RBACprofile()
    if os.geteuid() == 0:
        if len(args) > 0:
            manager = DeleteSnapManager(args)
        else:
            manager = DeleteSnapManager()
        gtk.gdk.threads_enter()
        glib.idle_add(manager.initialise_view)
        gtk.main()
        gtk.gdk.threads_leave()
    elif os.path.exists(argv) and os.path.exists("/usr/bin/gksu"):
        # Run via gksu, which will prompt for the root password
        newargs = ["gksu", argv]
        for arg in args:
            newargs.append(arg)
        os.execv("/usr/bin/gksu", newargs);
        # Shouldn't reach this point
        sys.exit(1)
    else:
        dialog = gtk.MessageDialog(None,
                                   0,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   _("Insufficient Priviliges"))
        dialog.format_secondary_text(_("Snapshot deletion requires "
                                       "administrative privileges to run. "
                                       "You have not been assigned the necessary"
                                       "administrative priviliges."
                                       "\n\nConsult your system administrator "))
        dialog.run()
        print argv + "is not a valid executable path"
        sys.exit(1)
