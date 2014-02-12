import compileall
import os

destdir = os.getenv("DESTDIR", ".")
dir = destdir + "/usr"
compileall.compile_dir(destdir, force=1)

