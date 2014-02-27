time-slider for Linux
=====================

This is a port (if one can call it that) of the Opensolaris/Illimos
time-slider package to Linux. The porting effort so far was concentrated
mainly on removing Solaris-isms and fixing minor annoyances. More work
might be done in the future


Installation
============

The Makefile provides an install target that can be used to install
the package. For RPM based distributions a .spec file is included in
the rpm/ subdirectory.

"rpm" and "srpm" Makefile targets exist that will attempt to build
a noarch RPM and/or a SRPM based on that spec file. This might fail
if the user running the command has messed with their RPM environment
(by using ~/.rpmmacros, for example). Moving that file out of the way
temporarily should fix the issues.

The .spec file has been tested on Fedora 20 (as the whole package has),
running ZFS on Linux version 0.6.2 and later.


Running
=======

Python 2 is needed to run this package. Python 3 is not supported.

A systemd time-sliderd.service file is included in the installation.
It is not enabled by default.

No SysV init file is provided, but should not be too complicated to
create.

The main binary is /usr/libexec/time-sliderd. By default this will daemonize
itself, but a --foreground parameter has been added that will keep the
program attached to the starting terminal.


Configuration
=============

Like under Solaris the main way of specifying datasets to be snapshotted
is using the "com.sun:auto-snapshot" property. This will enable the
default "frequent", "hourly", "daily", "weekly" and "monthly" snapshots.
The respective "com.sun:auto-snapshot:<frequency>" properties are
understood as well.


SMF
===

Further configuration of the time-sliderd service and the snapshots could
be done unter Solaris by using SMF properties of the respective services.

As Linux does not share this concept a config file located at
/etc/time-slider/time-sliderd.conf can be used to set configuration options.

To see a config file dump of the default options run "/usr/libexec/time-sliderd
--configdump" which will print the config to stdout.

No restart is necessary after changes to the config file, the new values
will be picked up immediately.


Known issues
============

Plugins are currently not working and are completely disabled. Also no
integration with Gnome or other Desktop Environments exists.
