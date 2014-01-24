__author__ = 'Shyue Ping Ong'
__copyright__ = 'Copyright 2013, The Materials Project'
__version__ = '0.1'
__maintainer__ = 'Shyue Ping Ong'
__email__ = 'ongsp@ucsd.edu'
__date__ = '1/24/14'


import os
from bz2 import BZ2File
from gzip import GzipFile
import tempfile
import shutil

from monty.shutil import copy_r


def zopen(filename, *args, **kwargs):
    """
    This function wraps around the bz2, gzip and standard python's open
    function to deal intelligently with bzipped, gzipped or standard text
    files.

    Args:
        filename (str): filename
        \*args: Standard args for python open(..). E.g., 'r' for read, 'w' for
            write.
        \*\*kwargs: Standard kwargs for python open(..).

    Returns:
        File-like object. Supports with context.
    """
    file_ext = filename.split(".")[-1].upper()
    if file_ext == "BZ2":
        return BZ2File(filename, *args, **kwargs)
    elif file_ext in ("GZ", "Z"):
        return GzipFile(filename, *args, **kwargs)
    else:
        return open(filename, *args, **kwargs)


def reverse_readline(m_file, blk_size=4096, max_mem=4000000):
    """
    Generator method to read a file line-by-line, but backwards. This allows
    one to efficiently get data at the end of a file.

    Based on code by Peter Astrand <astrand@cendio.se>, using modifications by
    Raymond Hettinger and Kevin German.
    http://code.activestate.com/recipes/439045-read-a-text-file-backwards
    -yet-another-implementat/

    Reads file forwards and reverses in memory for files smaller than the
    max_mem parameter, or for gzip files where reverse seeks are not supported.

    Files larger than max_mem are dynamically read backwards.

    Args:
        m_file (File): File stream to read (backwards)
        blk_size (int): The buffer size. Defaults to 4096.
        max_mem (int): The maximum amount of memory to involve in this
            operation. This is used to determine when to reverse a file
            in-memory versus seeking portions of a file. For bz2 files,
            this sets the maximum block size.

    Returns:
        Generator that returns lines from the file. Similar behavior to the
        file.readline() method, except the lines are returned from the back
        of the file.
    """

    file_size = os.path.getsize(m_file.name)

    # If the file size is within our desired RAM use, just reverse it in memory
    # GZip files must use this method because there is no way to negative seek
    if file_size < max_mem or isinstance(m_file, GzipFile):
        for line in reversed(m_file.readlines()):
            yield line.rstrip()
    else:
        if isinstance(m_file, BZ2File):
            # for bz2 files, seeks are expensive. It is therefore in our best
            # interest to maximize the blk_size within limits of desired RAM
            # use.
            blk_size = min(max_mem, file_size)

        buf = ""
        m_file.seek(0, 2)
        lastchar = m_file.read(1)
        trailing_newline = (lastchar == "\n")

        while 1:
            newline_pos = buf.rfind("\n")
            pos = m_file.tell()
            if newline_pos != -1:
                # Found a newline
                line = buf[newline_pos + 1:]
                buf = buf[:newline_pos]
                if pos or newline_pos or trailing_newline:
                    line += "\n"
                yield line
            elif pos:
                # Need to fill buffer
                toread = min(blk_size, pos)
                m_file.seek(pos - toread, 0)
                buf = m_file.read(toread) + buf
                m_file.seek(pos - toread, 0)
                if pos == toread:
                    buf = "\n" + buf
            else:
                # Start-of-file
                return


def gzip_dir(path):
    """
    Gzips all files in a directory.

    Args:
        path (str): Path to directory.
    """
    for f in os.listdir(path):
        if not f.lower().endswith("gz"):
            with open(f, 'rb') as f_in, \
                    GzipFile('{}.gz'.format(f), 'wb') as f_out:
                f_out.writelines(f_in)
            os.remove(f)


class ScratchDir(object):
    """
    Creates a with context manager that automatically handles creation of
    temporary directories in the scratch space and cleanup when done.
    """
    SCR_LINK = "scratch_link"

    def __init__(self, rootpath, create_symbolic_link=False):
        """
        Initializes scratch directory given a **root** path. There is no need
        to try to create unique directory names. The code will generate a
        temporary sub directory in the rootpath. The way to use this is using a
        with context manager. Example::

            with ScratchDir("/scratch"):
                do_something()

        Args:
            rootpath (str): The path in which to create temp subdirectories.
            create_symbolic_link (bool): Whether to create a symbolic link in
                the current working directory.
        """
        self.rootpath = rootpath
        self.cwd = os.getcwd()
        self.create_symbolic_link = create_symbolic_link

    def __enter__(self):
        tempdir = self.cwd
        if self.rootpath is not None and os.path.abspath(self.rootpath) != \
                self.cwd:
            tempdir = tempfile.mkdtemp(dir=self.rootpath)
            self.tempdir = os.path.abspath(tempdir)
            copy_r(".", tempdir)
            if self.create_symbolic_link:
                os.symlink(tempdir, ScratchDir.SCR_LINK)
            os.chdir(tempdir)
        return tempdir

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.rootpath is not None and os.path.abspath(self.rootpath) != \
                self.cwd:
            copy_r(".", self.cwd)
            shutil.rmtree(self.tempdir)
            os.chdir(self.cwd)
            if self.create_symbolic_link:
                os.remove(ScratchDir.SCR_LINK)