"""
Implementation of sycalls for a FUSE based file system using fuse.py.
The operations are overwritten and used in the :doc:`infuser`.

Created by Alexander Krause on 02/28/2023.
Modified by Stephan Winker from 10/01/2023 to 28/02/2024.

Libraries/Modules:

- fusepy (https://github.com/fusepy/fusepy)
  - Python interface to the FUSE kernel module
- logging standard library
  - Access to logging functionality
- errno standard library
  - Access to error messages

.. note:: Seems to be inspired by the work of stavros https://www.stavros.io/posts/python-fuse-filesystem/

.. todo:: [#0] Finalize documentation for this file.
.. todo:: [#9] Finalize libfuse logic (e.g. mkdir does not work as access raises FileNotFoundError) 
"""


import errno
import os
import logging

from fuse import FuseOSError
from fuse import Operations

class FileOperations(Operations):
    def __init__(self, dir_to_mount):
        self.dir_to_mount = dir_to_mount
        self.log = logging.getLogger('infuser')

    ##################
    # Sanitize input #
    ##################

    # Keep operations in mounted folder and prevent accessing unwanted files
    def _get_real_path(self, path):
        # self.log.debug(f"get-PATH - {self.dir_to_mount} - {path}")
        if path.startswith("/"):
            path = path[1:]
        fullpath = os.path.join(self.dir_to_mount, path)
        return fullpath

    ########################
    # Filesystem functions #
    ########################

    # Check if user or process has access to given file or dir with access mode "mode"
    def access(self, path, mode):
        converted_mode = "f"
        match mode:
            case 1:  # Execute a file or open a directory
                converted_mode = "x"
            case 2:  # Write to a file or directory
                converted_mode = "w"
            case 4:  # Read the contents of a file or directory
                converted_mode = "r"
        full_path = self._get_real_path(path)
        if not os.access(full_path, mode):
            self.log.info(f"ACCESS ({converted_mode}) DENIED --- Path: {path} --- Denied by Operating System")
            raise FuseOSError(errno.EACCES)
        self.log.debug(f"ACCESS ({converted_mode}) GRANTED --- Path: {path} --- Granted by Operating System")
        return os.access(full_path, mode)

    # Change Permissions of file and folder permissions
    def chmod(self, path, mode):
        full_path = self._get_real_path(path)
        return os.chmod(full_path, mode)

    # Change ownership of a file or directory
    def chown(self, path, uid, gid):
        full_path = self._get_real_path(path)
        return os.chown(full_path, uid, gid)

    # Get dir and forresponds to UNIX permission r
    def getattr(self, path, fh=None):
        full_path = self._get_real_path(path)
        try:
            st = os.lstat(full_path)
        except FileNotFoundError:
            self.log.error(f"FILE NOT FOUND: {path}")
            raise FuseOSError(errno.EEXIST)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                                                        'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size',
                                                        'st_uid'))

    # Get all the directory contents (files and subdirs) as list
    def readdir(self, path, fh):
        full_path = self._get_real_path(path)
        self.log.debug(f"readdir - {fh} - {path}")
        directory_contents = ['.', '..']
        if os.path.isdir(full_path):
            directory_contents.extend(os.listdir(full_path))
        for r in directory_contents:
            yield r

    # Reads the contents of a symlink
    def readlink(self, path):
        pathname = os.readlink(self._get_real_path(path))
        if pathname.startswith(b"/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.dir_to_mount)
        else:
            return pathname

    # Equivalent to mknod command
    def mknod(self, path, mode, dev):
        return os.mknod(self._get_real_path(path), mode, dev)

    # Equivalent to rmdir command
    def rmdir(self, path):
        full_path = self._get_real_path(path)
        self.log.debug(f"rmdir - {path}")
        return os.rmdir(full_path)

    # Equivalent to mkdir command
    def mkdir(self, path, mode):
        full_path = self._get_real_path(path)
        self.log.debug(f"mkdir - {mode} - {path}")
        return os.mkdir(full_path, mode)

    # Returns information about a mounted filesystem
    def statfs(self, path):
        full_path = self._get_real_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail',
                                                         'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax'))

    # Equivalent to unlink command
    def unlink(self, path):
        return os.unlink(self._get_real_path(path))

    # Equivalent to symlink command
    def symlink(self, name, target):
        return os.symlink(name, self._get_real_path(target))

    # Equivalent to "mv <old> <new>" command
    def rename(self, old, new):
        old_full_path = self._get_real_path(old)
        new_full_path = self._get_real_path(new)
        self.log.debug(f"rename - {old} - {new}")
        return os.rename(old_full_path, new_full_path)

    # Equivalent to link command
    def link(self, target, name):
        return os.link(self._get_real_path(target), self._get_real_path(name))

    # Changes the timestamp of a file or dir
    def utimens(self, path, times=None):
        return os.utime(self._get_real_path(path), times)

    ###############
    # File access #
    ###############

    # Opens a file
    def open(self, path, flags):
        full_path = self._get_real_path(path)
        self.log.debug(f"open - {flags} - {path}")
        return os.open(full_path, flags)

    # Creates a file
    def create(self, path, mode, fi=None):
        full_path = self._get_real_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    # Reads the content of a file
    def read(self, path, length, offset, fh):
        # CAUTION: Conversion to full_path not useful here because read is being called with a filehandler
        os.lseek(fh, offset, os.SEEK_SET)
        self.log.debug(f"read - {path}")
        return os.read(fh, length)

    # Writes to a file
    def write(self, path, buf, offset, fh):
        # CAUTION: Conversion to full_path not useful here because write is being called with a filehandler
        os.lseek(fh, offset, os.SEEK_SET)
        self.log.debug(f"write - {path}")
        return os.write(fh, buf)

    # Sets the file to "length". Cuts content > length or adds '\0' bytes if the file was shorter than "length"
    def truncate(self, path, length, fh=None):
        full_path = self._get_real_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    # Forces a write-operation for all buffered data
    def flush(self, path, fh):
        return os.fsync(fh)

    # Release file lock and close file
    def release(self, path, fh):
        return os.close(fh)

    # Forces a write-operation for all buffered data
    def fsync(self, path, fdatasync, fh):
        return self.flush(path, fh)
