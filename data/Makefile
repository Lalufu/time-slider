
top_builddir = ..
top_srcdir = ..
mkinstalldirs = /usr/bin/mkdir -p
INSTALL = /usr/sbin/install
INSTALL_DATA = ${INSTALL} -u root -g bin -m 644 -f
RM = /usr/bin/rm -f
RMDIR = /usr/bin/rmdir
INTLTOOL_MERGE = /usr/bin/intltool-merge
desktop_in_files = time-slider.desktop.in
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

all: $(desktop_DATA)

install:
	$(mkinstalldirs) $(DESTDIR)/usr/share/applications
	$(INSTALL_DATA) $(DESTDIR)/usr/share/applications time-slider.desktop

uninstall:
	$(RM) $(DESTDIR)/usr/share/applications/time-slider.desktop

%.desktop:   %.desktop.in   $(INTLTOOL_MERGE) $(wildcard $(top_srcdir)/po/*.po) ; LC_ALL=C $(INTLTOOL_MERGE) -d -u -c $(top_builddir)/po/.intltool-merge-cache $(top_srcdir)/po $< $@

