#!/usr/bin/python2.6
import os

backupDirs = []

for root, dirs, files in os.walk("/ts-test/TIMESLIDER/nanmbp"):
    if '.time-slider' in dirs:
#        dirs.remove('.time-slider')
        backupDirs.append(os.path.join(root, ".time-slider/rsync"))
	print "root %s" % root
	s1 = root.split ("/ts-test/TIMESLIDER/nanmbp/", 1)
	print s1

for dirName in backupDirs:
    print "dirName %s " % dirName
    s1 = dirName.split ("/ts-test/TIMESLIDER/nanmbp/",1)
    s2 = s1[1].split ("/.time-slider/rsync",1)
    print s2[0]
    os.chdir(dirName)
    dirList = ["toto %s" % d for d in os.listdir(dirName) \
                if os.path.isdir(d) and
                not os.path.islink(d)] 
    print dirList
