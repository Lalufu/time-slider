include VERSION

mkinstalldirs = /usr/bin/mkdir -p
INSTALL = /usr/sbin/install
INSTALL_DATA = ${INSTALL} -u root -g bin -m 644 -f
INSTALL_PROGRAM = ${INSTALL} -u root -g bin -f
INSTALL_SCRIPT = ${INSTALL} -f
RM = /usr/bin/rm -f
RMRF = /usr/bin/rm -Rf
RMDIR = /usr/bin/rmdir
# Use python 2.6 if PYTHON environent is not set
ifeq ($(strip $(PYTHON)),)
PYTHON = /usr/bin/python2.6
endif

SUBDIRS = po data

DISTFILES = Authors \
			VERSION \
			ChangeLog \
			Makefile \
			py-compile.py \
			$(SUBDIRS) \
			lib \
			usr \
			var \
			etc

clean:
	$(RM) usr/share/time-slider/lib/time_slider/*.pyc
	$(RM) usr/share/time-slider/lib/plugin/*.pyc
	$(RM) usr/share/time-slider/lib/plugin/rsync/*.pyc
	$(RM) usr/share/time-slider/lib/plugin/zfssend/*.pyc

all:
	for subdir in $(SUBDIRS); do \
	  cd $$subdir; make; cd ..;\
	done
	echo $(VERSION)

dist: clean all
	$(RMRF) time-slider-$(VERSION)
	mkdir time-slider-$(VERSION)
	cp -pR $(DISTFILES) time-slider-$(VERSION)
	/usr/bin/tar cf - time-slider-$(VERSION) | bzip2 > time-slider-$(VERSION).tar.bz2
	$(RMRF) time-slider-$(VERSION)

install:
	for subdir in $(SUBDIRS); do \
	  cd $$subdir; \
	  make DESTDIR=$(DESTDIR) GETTEXT_PACKAGE=time-slider install; \
	  cd ..;\
	done
	$(mkinstalldirs) $(DESTDIR)/etc/dbus-1/system.d
	$(INSTALL_DATA) $(DESTDIR)/etc/dbus-1/system.d etc/dbus-1/system.d/time-slider.conf
	$(mkinstalldirs) $(DESTDIR)/etc/xdg/autostart
	$(INSTALL_DATA) $(DESTDIR)/etc/xdg/autostart etc/xdg/autostart/*.desktop
	$(mkinstalldirs) $(DESTDIR)/lib/svc/method
	$(INSTALL_SCRIPT) $(DESTDIR)/lib/svc/method lib/svc/method/time-slider
	$(INSTALL_SCRIPT) $(DESTDIR)/lib/svc/method lib/svc/method/time-slider-plugin
	$(INSTALL_SCRIPT) $(DESTDIR)/lib/svc/method lib/svc/method/time-slider-rsync
	$(mkinstalldirs) $(DESTDIR)/usr/bin
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/bin usr/bin/time-slider-setup
	$(mkinstalldirs) $(DESTDIR)/usr/lib/time-slider/plugins/rsync
	$(mkinstalldirs) $(DESTDIR)/usr/lib/time-slider/plugins/zfssend
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib usr/lib/time-sliderd
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib usr/lib/time-slider-delete
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib usr/lib/time-slider-notify
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib usr/lib/time-slider-snapshot
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib usr/lib/time-slider-version
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib/time-slider/plugins/zfssend usr/lib/time-slider/plugins/zfssend/zfssend
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib/time-slider/plugins/rsync usr/lib/time-slider/plugins/rsync/rsync-trigger
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/lib/time-slider/plugins/rsync usr/lib/time-slider/plugins/rsync/rsync-backup
	$(mkinstalldirs) $(DESTDIR)/usr/share/applications
	$(INSTALL_DATA) $(DESTDIR)/usr/share/applications usr/share/applications/time-slider.desktop
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/16x16/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/16x16/apps usr/share/icons/hicolor/16x16/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/24x24/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/24x24/apps usr/share/icons/hicolor/24x24/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/32x32/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/32x32/apps usr/share/icons/hicolor/32x32/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/36x36/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/36x36/apps usr/share/icons/hicolor/36x36/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/48x48/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/48x48/apps usr/share/icons/hicolor/48x48/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/72x72/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/72x72/apps usr/share/icons/hicolor/72x72/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/icons/hicolor/96x96/apps
	$(INSTALL_DATA) $(DESTDIR)/usr/share/icons/hicolor/96x96/apps usr/share/icons/hicolor/96x96/apps/time-slider-setup.png
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/glade
	$(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/glade usr/share/time-slider/glade/time-slider-delete.glade
	$(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/glade usr/share/time-slider/glade/time-slider-setup.glade
	$(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/glade usr/share/time-slider/glade/time-slider-snapshot.glade
	$(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/glade usr/share/time-slider/glade/time-slider-version.glade
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/lib/time_slider
	for file in usr/share/time-slider/lib/time_slider/*.py; do \
		if test -f $$file ; then \
		  $(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/lib/time_slider $$file; \
		fi; \
	done
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/lib/plugin
	for file in usr/share/time-slider/lib/plugin/*.py; do \
		if test -f $$file ; then \
		  $(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/lib/plugin $$file; \
		fi; \
	done
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/lib/plugin/rsync
	for file in usr/share/time-slider/lib/plugin/rsync/*.py; do \
		if test -f $$file ; then \
		  $(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/lib/plugin/rsync $$file; \
		fi; \
	done
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/lib/plugin/zfssend
	for file in usr/share/time-slider/lib/plugin/zfssend/*.py; do \
		if test -f $$file ; then \
		  $(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/lib/plugin/zfssend $$file; \
		fi; \
	done
	$(mkinstalldirs) $(DESTDIR)/var/svc/manifest/application
	$(INSTALL_DATA) $(DESTDIR)/var/svc/manifest/application var/svc/manifest/application/time-slider.xml
	$(INSTALL_DATA) $(DESTDIR)/var/svc/manifest/application var/svc/manifest/application/time-slider-plugin.xml
	$(mkinstalldirs) $(DESTDIR)/var/svc/manifest/system/filesystem
	$(INSTALL_DATA) $(DESTDIR)/var/svc/manifest/system/filesystem var/svc/manifest/system/filesystem/auto-snapshot.xml
	$(PYTHON) py-compile.py
	
uninstall:
	for subdir in $(SUBDIRS); do \
	  cd $$subdir; \
	  make DESTDIR=$(DESTDIR) GETTEXT_PACKAGE=time-slider uninstall; \
	  cd ..;\
	done
	$(RM) $(DESTDIR)/etc/dbus-1/system.d/time-slider.conf
	$(RM) $(DESTDIR)/etc/xdg/autostart/time-slider-notify.desktop
	$(RM) $(DESTDIR)/lib/svc/method/time-slider
	$(RM) $(DESTDIR)/lib/svc/method/time-slider-plugin
	$(RM) $(DESTDIR)/lib/svc/method/time-slider-rsync
	$(RM) $(DESTDIR)/usr/bin/time-slider-setup
	$(RM) $(DESTDIR)/usr/lib/time-sliderd
	$(RM) $(DESTDIR)/usr/lib/time-slider-delete
	$(RM) $(DESTDIR)/usr/lib/time-slider-notify
	$(RM) $(DESTDIR)/usr/lib/time-slider-snapshot
	$(RM) $(DESTDIR)/usr/lib/time-slider-version
	$(RM) $(DESTDIR)/usr/lib/time-slider-zfssend
	$(RM) $(DESTDIR)/usr/lib/time-slider-rsync
	$(RMRF) $(DESTDIR)/usr/lib/time-slider/plugins/rsync
	$(RMRF) $(DESTDIR)/usr/lib/time-slider/plugins/zfssend
	$(RM) $(DESTDIR)/usr/share/applications/time-slider.desktop
	$(RM) $(DESTDIR)/usr/share/icons/hicolor/*/apps/time-slider-setup.png
	$(RMRF) $(DESTDIR)/usr/share/time-slider
	$(RM) $(DESTDIR)/var/svc/manifest/application/time-slider.xml
	$(RM) $(DESTDIR)/var/svc/manifest/application/time-slider-plugin.xml
	$(RM) $(DESTDIR)/var/svc/manifest/system/filesystem/auto-snapshot.xml
