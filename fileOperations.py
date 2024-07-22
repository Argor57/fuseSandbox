import os
import time
import logging
import errno
from fuse import FuseOSError, Operations, LoggingMixIn

class FileOperations(Operations):
    def __init__(self, mountpoint):
        self.files = {}
        self.data = {}
        self.mountpoint = mountpoint
        now = time.time()
        self.files['/'] = dict(st_mode=(0o755 | 0o040000), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=2)

    def log(self, message):
        log = logging.getLogger(__name__)
        log.info(message)

    def getattr(self, path, fh=None):
        self.log(f'getattr: {path}')
        if path not in self.files:
            self.log(f'File not found: {path}')
            raise FuseOSError(errno.ENOENT)
        return self.files[path]

    def readdir(self, path, fh):
        self.log(f'readdir: {path}')
        return ['.', '..'] + [name[1:] for name in self.files if name != '/']

    def mkdir(self, path, mode):
        self.log(f'mkdir: {path}, mode: {oct(mode)}')
        now = time.time()
        self.files[path] = dict(st_mode=(mode | 0o040000), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=2)
        self.files['/']['st_nlink'] += 1

    def rmdir(self, path):
        self.log(f'rmdir: {path}')
        self.files.pop(path)
        self.files['/']['st_nlink'] -= 1

    def create(self, path, mode, fi=None):
        self.log(f'create: {path}, mode: {oct(mode)}')
        now = time.time()
        self.files[path] = dict(st_mode=(mode | 0o100000), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=1, st_size=0)
        self.data[path] = b''
        return 0

    def open(self, path, flags):
        self.log(f'open: {path}, flags: {flags}')
        if path not in self.files:
            raise FuseOSError(errno.ENOENT)
        return 0

    def read(self, path, size, offset, fh):
        self.log(f'read: {path}, size: {size}, offset: {offset}')
        if path not in self.data:
            raise FuseOSError(errno.ENOENT)
        return self.data[path][offset:offset + size]

    def write(self, path, buf, offset, fh):
        self.log(f'write: {path}, size: {len(buf)}, offset: {offset}')
        if path not in self.data:
            raise FuseOSError(errno.ENOENT)
        self.data[path] = self.data[path][:offset] + buf + self.data[path][offset + len(buf):]
        self.files[path]['st_size'] = len(self.data[path])
        return len(buf)

    def unlink(self, path):
        self.log(f'unlink: {path}')
        self.files.pop(path)
        self.data.pop(path)

    def truncate(self, path, length, fh=None):
        self.log(f'truncate: {path}, length: {length}')
        if path not in self.data:
            raise FuseOSError(errno.ENOENT)
        self.data[path] = self.data[path][:length]
        self.files[path]['st_size'] = length

    def chmod(self, path, mode):
        self.log(f'chmod: {path}, mode: {oct(mode)}')
        if path not in self.files:
            raise FuseOSError(errno.ENOENT)
        self.files[path]['st_mode'] &= 0o770000
        self.files[path]['st_mode'] |= mode

    def chown(self, path, uid, gid):
        self.log(f'chown: {path}, uid: {uid}, gid: {gid}')
        if path not in self.files:
            raise FuseOSError(errno.ENOENT)
        self.files[path]['st_uid'] = uid
        self.files[path]['st_gid'] = gid

    def utimens(self, path, times=None):
        self.log(f'utimens: {path}, times: {times}')
        now = time.time()
        atime, mtime = times if times else (now, now)
        self.files[path]['st_atime'] = atime
        self.files[path]['st_mtime'] = mtime

    def rename(self, old, new):
        self.log(f'rename: {old} to {new}')
        self.files[new] = self.files.pop(old)
        if old in self.data:
            self.data[new] = self.data.pop(old)

    def link(self, target, source):
        self.log(f'link: {target} to {source}')
        self.files[target] = self.files[source]
        self.files[target]['st_nlink'] += 1

    def symlink(self, target, source):
        self.log(f'symlink: {target} to {source}')
        now = time.time()
        self.files[target] = dict(st_mode=(0o777 | 0o120000), st_ctime=now, st_mtime=now, st_atime=now, st_nlink=1)
        self.data[target] = source.encode()

    def readlink(self, path):
        self.log(f'readlink: {path}')
        if path not in self.data:
            raise FuseOSError(errno.ENOENT)
        return self.data[path].decode()

    def mknod(self, path, mode, dev):
        self.log(f'mknod: {path}, mode: {oct(mode)}, dev: {dev}')
        self.files[path] = dict(st_mode=(mode | 0o100000), st_ctime=time.time(), st_mtime=time.time(), st_atime=time.time(), st_nlink=1, st_size=0)

    def statfs(self, path):
        self.log(f'statfs: {path}')
        return dict(f_bsize=4096, f_blocks=1024*1024, f_bfree=1024*512, f_bavail=1024*512,
                    f_files=1024, f_ffree=1024)

    def flush(self, path, fh):
        self.log(f'flush: {path}, fh: {fh}')
        return os.fsync(fh)

    def release(self, path, fh):
        self.log(f'release: {path}, fh: {fh}')
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        self.log(f'fsync: {path}, fdatasync: {fdatasync}, fh: {fh}')
        if fdatasync:
            return os.fdatasync(fh)
        else:
            return os.fsync(fh)

    def access(self, path, mode):
        self.log(f'access: {path}, mode: {mode}')
        if path not in self.files:
            raise FuseOSError(errno.ENOENT)
        # Always return 0 to grant access
        return 0

    def fgetattr(self, path, fh=None):
        self.log(f'fgetattr: {path}')
        return self.getattr(path, fh)

    def ftruncate(self, path, length, fh=None):
        self.log(f'ftruncate: {path}, length: {length}')
        return self.truncate(path, length, fh)

    def lock(self, path, cmd, fh, lock):
        self.log(f'lock: {path}, cmd: {cmd}, fh: {fh}, lock: {lock}')
        # This is a no-op (no operation), as we are not implementing actual locking
        return 0

    def ioctl(self, path, cmd, arg, fh, flags, data):
        self.log(f'ioctl: {path}, cmd: {cmd}, arg: {arg}, fh: {fh}, flags: {flags}, data: {data}')
        raise FuseOSError(errno.ENOTTY)

