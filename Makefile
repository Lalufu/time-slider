ifeq ($(wildcard .git),)
	include VERSION
else
	VERSION=$(shell git describe)
endif
MAINVER=$(shell echo $(VERSION) | cut -f1 -d'-')
RELEASE=$(shell echo $(VERSION) | cut -f2- -d'-' | sed -e 's/-/./g')

mkinstalldirs = /usr/bin/mkdir -p
INSTALL = /usr/bin/install
INSTALL_DATA = ${INSTALL} -m 644 -t
INSTALL_PROGRAM = ${INSTALL} -m 755 -t
INSTALL_SCRIPT = ${INSTALL} -t
RM = /usr/bin/rm -f
RMRF = /usr/bin/rm -Rf
RMDIR = /usr/bin/rmdir
RPM = /usr/bin/rpm
RPMBUILD = /usr/bin/rpmbuild
# Use python 2.6 if PYTHON environent is not set
ifeq ($(strip $(PYTHON)),)
PYTHON = /usr/bin/python2
endif

SUBDIRS = po data rpm

DISTFILES = Authors \
			VERSION \
			ChangeLog \
			README.md \
			OPENSOLARIS.LICENSE \
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
	$(RM) rpm/time-slider.spec

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
	$(mkinstalldirs) $(DESTDIR)/usr/lib/systemd/system
	$(INSTALL_DATA) $(DESTDIR)/usr/lib/systemd/system etc/systemd/system/*.service
	$(mkinstalldirs) $(DESTDIR)/usr/bin
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/bin usr/bin/time-slider-setup
	$(mkinstalldirs) $(DESTDIR)/usr/lib/time-slider/plugins/rsync
	$(mkinstalldirs) $(DESTDIR)/usr/lib/time-slider/plugins/zfssend
	$(mkinstalldirs) $(DESTDIR)/usr/libexec
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/libexec usr/lib/time-sliderd
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/libexec usr/lib/time-slider-delete
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/libexec usr/lib/time-slider-notify
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/libexec usr/lib/time-slider-snapshot
	$(INSTALL_PROGRAM) $(DESTDIR)/usr/libexec usr/lib/time-slider-version
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
	$(mkinstalldirs) $(DESTDIR)/usr/share/time-slider/lib/time_slider/linux
	for file in usr/share/time-slider/lib/time_slider/linux/*.py; do \
		if test -f $$file ; then \
		  $(INSTALL_DATA) $(DESTDIR)/usr/share/time-slider/lib/time_slider/linux $$file; \
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
	
uninstall:
	for subdir in $(SUBDIRS); do \
	  cd $$subdir; \
	  make DESTDIR=$(DESTDIR) GETTEXT_PACKAGE=time-slider uninstall; \
	  cd ..;\
	done
	$(RM) $(DESTDIR)/etc/dbus-1/system.d/time-slider.conf
	$(RM) $(DESTDIR)/etc/xdg/autostart/time-slider-notify.desktop
	$(RM) $(DESTDIR)/usr/lib/systemd/system/time-sliderd.service
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


rpm-local:
	@(if test ! -x "${RPMBUILD}"; then \
		echo -e "\n" \
	"*** Required util ${RPMBUILD} missing.  Please install the\n" \
	"*** package for your distribution which provides ${RPMBUILD},\n" \
	"*** re-run configure, and try again.\n"; \
		exit 1; \
	fi; \
	mkdir -p $(rpmbuild)/TMP && \
	mkdir -p $(rpmbuild)/BUILD && \
	mkdir -p $(rpmbuild)/RPMS && \
	mkdir -p $(rpmbuild)/SRPMS && \
	mkdir -p $(rpmbuild)/SPECS && \
	cp rpm/$(rpmspec) $(rpmbuild)/SPECS && \
	mkdir -p $(rpmbuild)/SOURCES && \
	cp time-slider-$(VERSION).tar.bz2 $(rpmbuild)/SOURCES)

srpm: dist
	@(dist=`$(RPM) --eval %{?dist}`; \
	rpmpkg=time-slider-$(MAINVER)-0.$(RELEASE)$$dist*src.rpm; \
	rpmspec=time-slider.spec; \
	rpmbuild=`mktemp -t -d time-slider-build-$$USER-XXXXXXXX`; \
	$(MAKE) \
		rpmbuild="$$rpmbuild" \
		rpmspec="$$rpmspec" \
		rpm-local || exit 1; \
	$(RPMBUILD) \
		--define "_tmppath $$rpmbuild/TMP" \
		--define "_topdir $$rpmbuild" \
		$(def) -bs $$rpmbuild/SPECS/$$rpmspec || exit 1; \
	cp $$rpmbuild/SRPMS/$$rpmpkg . || exit 1; \
	rm -R $$rpmbuild)

rpm: srpm
	@(dist=`$(RPM) --eval %{?dist}`; \
	rpmpkg=time-slider-$(MAINVER)-0.$(RELEASE)$$dist*src.rpm; \
	rpmspec=time-slider.spec; \
	rpmbuild=`mktemp -t -d time-slider-build-$$USER-XXXXXXXX`; \
	$(MAKE) \
		rpmbuild="$$rpmbuild" \
		rpmspec="$$rpmspec" \
		rpm-local || exit 1; \
	${RPMBUILD} \
		--define "_tmppath $$rpmbuild/TMP" \
		--define "_topdir $$rpmbuild" \
		$(def) --rebuild $$rpmpkg || exit 1; \
	cp $$rpmbuild/RPMS/*/* . || exit 1; \
	rm -R $$rpmbuild)
