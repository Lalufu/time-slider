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

import time
import getopt
import os
import gio
import sys
import threading
import subprocess
import string
import gnomevfs
import gnome.ui
#import traceback

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

KILOBYTES = 1024.0
MEGABYTES = KILOBYTES*1024
GIGABYTES = MEGABYTES*1024
TERABYTES = GIGABYTES*1024

class File:
	displayTemplates = [
		(TERABYTES, '%0.1f TB'), 
		(GIGABYTES, '%0.1f GB'),
		(MEGABYTES, '%0.1f MB'),
		(KILOBYTES, '%0.1f KB'),
		(0, '%0.1f B'),]

	def __init__(self, path):
		self.path = path
		self.file = gio.File (path)
		try:
			self.info = self.file.query_info ("*")
			self.exist = True
		except gio.Error:
			self.exist = False

	def  get_icon (self):
		#try thumnailer first
		icon_factory = gnome.ui.ThumbnailFactory(gnome.ui.THUMBNAIL_SIZE_NORMAL)
		mtime = os.path.getmtime(self.path)
		uri = gnomevfs.make_uri_from_input(self.path)
		thumb =  icon_factory.lookup (uri, mtime)
		if thumb:
		  return gtk.gdk.pixbuf_new_from_file (thumb)
	        thumb = icon_factory.generate_thumbnail (uri, self.info.get_content_type())
		if thumb:
		  icon_factory.save_thumbnail (thumb, uri, mtime)
		  return thumb
		 #fallback get the themed icon
		return gtk.icon_theme_get_default().choose_icon (self.info.get_icon().get_property ("names"), 48,  gtk.ICON_LOOKUP_USE_BUILTIN).load_icon ()

	def  get_size (self):
		amount = self.info.get_size ()
		for treshold, template in self.displayTemplates:
			if amount > treshold:
				if treshold:
					amount = amount /treshold
				return "%s (%d bytes)" % (template % amount, self.info.get_size ())
		return "%d byte" % amount

	def add_if_unique (self, versions):
		found = False
		for file in versions:
			if int (file.info.get_modification_time ()) == int (self.info.get_modification_time ()):
				found = True
		if not found:
			versions.append (self)
			return True
		return False

	def get_mime_type (self):
		return gnomevfs.get_mime_type(gnomevfs.make_uri_from_input(self.path))


( COLUMN_ICON,
  COLUMN_NAME,
  COLUMN_STRING_DATE,
  COLUMN_DATE,
  COLUMN_SIZE
) = range (5)



class FileVersionWindow:
	meld_hint_displayed = False

	def __init__(self, snap_path, file):
		self.snap_path = snap_path
		self.filename = file
		self.xml = gtk.glade.XML("%s/../../glade/time-slider-version.glade" \
			% (os.path.dirname(__file__)))
		self.window = self.xml.get_widget("toplevel")
		self.progress = self.xml.get_widget("progress")
		self.version_label = self.xml.get_widget("num_versions_label")
		# signal dictionary
		dic = {"on_toplevel_delete_event": self.exit3 ,
			"on_close_clicked": self.exit ,
			"on_compare_button_clicked": self.on_compare_button_clicked,
			"on_current_file_button_clicked": self.on_current_file_button_clicked,
			"on_treeview_row_activated": self.on_treeview_row_activated,
			"on_treeview_cursor_changed": self.on_treeview_cursor_changed}
		self.xml.signal_autoconnect(dic)
			
		self.filename_label = self.xml.get_widget("filename_label")
		self.size_label = self.xml.get_widget("size_label")
		self.date_label = self.xml.get_widget("date_label")
		self.older_versions_label = self.xml.get_widget("older_versions_label")
		self.compare_button = self.xml.get_widget("compare_button")
		self.button_init = False

		self.window.show ()

		self.file = File (file)
		self.filename_label.set_text (self.file.info.get_name ())
		self.size_label.set_text (self.file.get_size ())
		self.date_label.set_text (time.strftime ("%d/%m/%y %Hh%Ms%S", time.localtime(self.file.info.get_modification_time ())))
		self.xml.get_widget("icon_image").set_from_pixbuf (self.file.get_icon ())

		self.treeview = self.xml.get_widget("treeview")
		self.model = gtk.ListStore(gtk.gdk.Pixbuf,
					   gobject.TYPE_STRING,
					   gobject.TYPE_STRING,
					   gobject.TYPE_STRING,
					   gobject.TYPE_STRING)

		self.treeview.set_model (self.model)
		self.__add_columns (self.treeview)

		self.scanner = VersionScanner (self)
		self.scanner.start()

	def __add_columns(self, treeview):
		model = treeview.get_model()

		renderer = gtk.CellRendererPixbuf()
		column = gtk.TreeViewColumn('Icon', renderer, pixbuf=COLUMN_ICON)
		treeview.append_column(column)

		self.date_column = gtk.TreeViewColumn('Last Modified Date', gtk.CellRendererText(),
			text=COLUMN_STRING_DATE)
		self.date_column.set_sort_column_id(COLUMN_DATE)
		treeview.append_column(self.date_column)

		# column for description
		column = gtk.TreeViewColumn('Size', gtk.CellRendererText(),
			text=COLUMN_SIZE)
		column.set_sort_column_id(COLUMN_SIZE)
		treeview.append_column(column)

	def add_file (self, file):
		iter = self.model.append ()
		self.model.set (iter, 
		COLUMN_ICON, file.get_icon (),
		COLUMN_NAME, file.path,
		COLUMN_STRING_DATE, time.strftime ("%d/%m/%y %Hh%Ms%S", time.localtime(file.info.get_modification_time ())),
		COLUMN_DATE, file.info.get_modification_time (),
		COLUMN_SIZE, file.get_size ())

	def exit3 (self, blah, blih):
		self.exit (self)

	def exit (self, blah):
		self.scanner.join ()
		gtk.main_quit ()
		
	def on_current_file_button_clicked (self, widget):
		application = gnomevfs.mime_get_default_application (gnomevfs.get_mime_type(gnomevfs.make_uri_from_input(self.filename)))
		if application:
			subprocess.Popen (str.split (application[2]) + [self.filename])

	def on_treeview_row_activated (self, treeview, path, column):
		(model, iter) = treeview.get_selection ().get_selected ()
		filename = model.get (iter, 1)[0]
		application = gnomevfs.mime_get_default_application (gnomevfs.get_mime_type(gnomevfs.make_uri_from_input(filename)))
		if application:
			subprocess.Popen (str.split (application[2]) + [filename])

	def on_treeview_cursor_changed (self, treeview):
		if not self.button_init:
			self.button_init = True
			if self.file.get_mime_type ().find ("text") != -1 :
				self.compare_button.set_sensitive (True)

	def on_compare_button_clicked (self, widget):
		(model, iter) = self.treeview.get_selection ().get_selected ()
		filename = model.get (iter, 1)[0]
		if os.path.exists ("/usr/bin/meld"):
		  subprocess.Popen (["/usr/bin/meld",self.filename, filename])
		else:
		  if not self.meld_hint_displayed:
		    dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _("Hint"))
		    dialog.set_title (_("Hint"))
		    dialog.format_secondary_text(_("Installing the optional meld package will enhance the file comparison visualization"))
		    dialog.run ()
		    dialog.destroy ()
		    self.meld_hint_displayed = True
		  p1 = subprocess.Popen(["/usr/bin/diff", "-u", self.filename, filename], stdout=subprocess.PIPE)
		  p2 = subprocess.Popen(str.split ("/usr/bin/zenity --text-info --editable"), stdin=p1.stdout, stdout=subprocess.PIPE)


class VersionScanner(threading.Thread):

	def __init__(self, window):
		self.w = window
		self._stopevent = threading.Event()
		threading.Thread.__init__(self)

	def run(self):
		l = self.w.snap_path.split (".zfs")
		path_before_snap = l[0]
		l = self.w.filename.split (path_before_snap)
		path_after_snap = l[1]
		snap_path = "%s.zfs/snapshot/" % path_before_snap;
		dirs = os.listdir(snap_path)

		num_dirs = len(dirs)
		current_dir = 1

		gobject.idle_add (self.w.progress.set_pulse_step,  (1.0 / num_dirs))
		gobject.idle_add (self.w.progress.set_text,  ("Scanning for older versions (%d/%d)" % (current_dir, num_dirs)))

		versions = [File (self.w.filename)]

		for dir in dirs:
			if not self._stopevent.isSet ():
				file = File ("%s%s/%s" % (snap_path, dir, path_after_snap))
				if file.exist :
					if file.add_if_unique(versions):
						gobject.idle_add (self.w.add_file, file)
				fraction = self.w.progress.get_fraction ()
				fraction += self.w.progress.get_pulse_step ()
				if fraction > 1:
					fraction = 1

				gobject.idle_add (self.w.progress.set_fraction, fraction)
				current_dir += 1
				gobject.idle_add (self.w.progress.set_text, "Scanning for older versions (%d/%d)" % (current_dir, num_dirs))
			else:
				return None

		gobject.idle_add(self.w.progress.hide)
		gobject.idle_add(self.w.older_versions_label.set_markup , "<b>Older Versions</b> (%d) " % (len(versions) - 1))
		# sort by date
		gobject.idle_add(self.w.date_column.emit, "clicked")
		gobject.idle_add(self.w.date_column.emit, "clicked")
	
	def join(self, timeout=None):
		self._stopevent.set ()
		threading.Thread.join(self, timeout)

def main(argv):
	try:
		opts, args = getopt.getopt(sys.argv[1:], "", [])
	except getopt.GetoptError:
		sys.exit(2)
	if len(args) != 2:
		dialog = gtk.MessageDialog(None,
			0,
			gtk.MESSAGE_ERROR,
			gtk.BUTTONS_CLOSE,
			_("Invalid arguments count."))
		dialog.set_title ("Error")
		dialog.format_secondary_text(_("Version explorer requires"
			" 2 arguments :\n- The path of the "
			"root snapshot directory.\n"
			"- The filename to explore."))
		dialog.run()
		sys.exit (2)

	window = FileVersionWindow(args[0], args[1])
	gtk.gdk.threads_enter()
	gtk.main()
	gtk.gdk.threads_leave()
