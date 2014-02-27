top_builddir = ..
top_srcdir = ..
SED = /usr/bin/sed
INTLTOOL_MERGE = /usr/bin/intltool-merge
spec_in_files = time-slider.spec.in
spec_DATA = $(spec_in_files:.spec.in=.spec)

ifeq ($(wildcard $(top_srcdir)/.git),)
	include $(top_srcdir)/VERSION
else
	VERSION=$(shell git describe)
endif
MAINVER=$(shell echo $(VERSION) | cut -f1 -d'-')
RELEASE=$(shell echo $(VERSION) | cut -f2- -d'-' | sed -e 's/-/./g')

all: $(spec_DATA)

$(spec_DATA):
	$(SED) -e 's,\@VERSION\@,$(MAINVER),g' \
		-e 's,\@RELEASE\@,$(RELEASE),g' \
		-e 's,\@GITVER\@,$(VERSION),g' \
		'$@.in' > '$@'
