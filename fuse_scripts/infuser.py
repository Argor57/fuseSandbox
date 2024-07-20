"""

Implementation of a FUSE-based file system using fusepy for
(state-based) access control. The file system overwrites the operations
in the :doc:`fileoperations`. The Setup is done in the :doc:`infuser_setup`.

Created by Alexander Krause on 02/28/2023.
Modified by Stephan Winker from 10/01/2023 to 28/02/2024.
Libraries/Modules:

- fusepy (https://github.com/fusepy/fusepy)
- Python interface to the FUSE kernel module
- magic (https://github.com/ahupp/python-magic)
- Access to mime types
- datetime standard library
- Access to current date and time
- logging standard library
- Access to logging functionality
- errno standard library
- Access to error messages
- re standard library
- Access to regular expressions
- sys standard library
- Access to the exit function
- os standard library
- Access to the path.isdir function
- json standard library
- Access to json parsing functions
- tomllib standard library
- Access to toml parsing functions
- socket standard library
- Access to networking functions

.. note:: If open is denied/broken, access gets called

.. todo:: [#0] Finalize the documentation for the project (fileoperations)
.. todo:: [#1] Merge check_policy and check_state (some redundant code)
.. todo:: [#2] Test, fix and unify path matching algorithms
.. todo:: [#3] Fix log level order (informativ-debug-errors -> debug-informativ-error) 
               and use of verbose flags (-vvvvv should result in more logs than -v)
.. todo:: [#4] Implement internal state and selections as DB ?
.. todo:: [#5] Optimize usage of algorithms and data structure 
.. todo:: [#6] Add security measures to uwu  
.. todo:: [#7] Add verification of the result of the central mechanism 
.. todo:: [#8] Add or improves log messages 

"""


import errno
import datetime
import logging
import re
import sys
import os
import json
import tomllib
import socket

import magic
from fuse import FUSE
from fuse import FuseOSError

import infuser_setup
from fileoperations import FileOperations

# All the policies relying on the internal state
sbac_policies = ["written-no-execute", "first-object-only"]
    
current_flag = None
    
flag_list = {
    'fuse.O_RDONLY': 32768,
    'fuse.O_WRONLY': 32869,
    'fuse.O_RDWR': 32770,
    'fuse.O_EXEC': 32800,
    'fuse.O_APPEND': 33793
}

def set_current_flag(flag: str):
    global current_flag
    current_flag = flag

def is_execution_intended(self, mode: str) -> bool:
     """
     Check whether the O_EXEC flag is set on the open syscall. This flag 
     get enables to indicate the intention to execute an object.

     :param mode: The syscall to be executed
     :type mode: str
     :return: A boolean that indicates, whether an execution is intended
     :rtype: bool
     """
     return (mode == "open" and current_flag == flag_list['fuse.O_EXEC'])

        
def current_time(fmt="%Y-%m-%d %H:%M:%S") -> str:
    """
    Return the current time of the system's time zone
    
    :return: A time in the format "year-month-day hour:minute:second" 
              or another specified format
    :rtype: str 
    """

    local_timezone = datetime.datetime.utcnow().astimezone().tzinfo
    return datetime.datetime.now(local_timezone).strftime(fmt)


def parse_toml(file: str) -> list:
    """
    Return the lines of a de-duplicated toml as a list.

    :param file: The path of the toml file to be read.
    :type file: str
    :return: A list of unique lines from a toml.
    :rtype: list
    """

    toml_entries = []
    logger = logging.getLogger("infuser")

    try:
        with open(file, 'r') as file:
            data = file.read()
        toml_entries = tomllib.loads(data)
    except FileNotFoundError:
        logger.error(f"ERROR - Could not load TOML data from file - File {file} does not exist.")
    except tomllib.TOMLDecodeError:
        logger.error(f"ERROR - Could not load TOML data from file - {file} has no valid TOML data.")
    except Exception as e:
        logger.error(f"ERROR - An unexpected error occurred while loading data from file - {e}")
    finally:
        return toml_entries

class IFS(FileOperations):
    """
    File system based on the FUSE Kernel Module
    
    The Infuser file system implements a series of functions that are
    used to access files. used to access files. Various conditions are
    that must be fulfilled for access. The Infuser file system has the
    subclass State, which provides an internal state and associated
    functions. When an infuser file system is created, a logger is called
    and the specified guidelines, as well as an internal state
    instantiated. The Infuser file system inherits from the
    FileOperations class of the module fuse.py module.
        
    :param dir_to_mount: The directory to mount in the IFS
    :type dir_to_mount: str
    :param policy_dict: The policies to apply to the directory
    :type policy_dict: str
    :param uri_file: The path to the configuration file with the URI
    :type uri_file: str
    :param state_file: The path to a json file containing a recorded internal state
    :type state_file: str
    """
     
    def __init__(self, dir_to_mount: str, policy_dict: dict, uri_file: str, state_file: str):
    
        self.log = logging.getLogger("infuser")
        self.dir_to_mount = dir_to_mount
        self.policy = policy_dict
        self.uri_file = uri_file
        self.uri_entries = parse_toml(self.uri_file) if uri_file else None
        self.state = self.State(self.dir_to_mount, state_file)
        super().__init__(dir_to_mount)
    
    class State:
        """
        Internal state of the infuser file system
        
        The internal state of the infuser file system contains a history of
        accesses to objects. These are used to make state-based access
        control decisions. In addition, the class provides a series of
        functions that are used to process the state. are used to process the
        state. The state-based policies are also part of the class.
        When an object of the State class is created, a logger is called
        and a list of dictionaries is created. This list contains past
        accesses in the format {Path, Access, Time, Success}. Another 
        list of previously selected objects ({Prefix, Path}) is used for 'foo'.
            
        :param dir_to_mount: The directory in which the operation is to be 
                              performed (required for recording the file type of the mapped files)
        :type dir_to_mount: str
        :param state_file: The path to a json file containing a recorded internal state
        :type state_file: str
        """
        
    
        def __init__(self, dir_to_mount: str, state_file: str):
            
            self.log = logging.getLogger("infuser")
            self.selections = {} 
            self.entries = self.handle_state(state_file)
            self.state_log = logging.getLogger("StateHandlerLogger")
            self.dir_to_mount = dir_to_mount
    
        def handle_state(self, state_file: str):
            """
            Parses a JSON file containing a recorded internal state and creates a logger.
            
            :param state_file: The file to log to and read from
            :str: state_file: str
            """
           
            # Select logger in case of error 
            logger = logging.getLogger("infuser")
            
            # If no file has to be read, create a temporary file only
            import_wanted = True 
            if not state_file:
               state_file = '/tmp/' + current_time("%Y-%m-%d_%H:%M:%S") + '-infuser.json'
               import_wanted = False
  
            # Create logger for internal state data
            state_logger = logging.getLogger('StateHandlerLogger')
            state_logger.setLevel(logging.INFO)
            handler = logging.FileHandler(state_file)
            formatter = logging.Formatter('')
            handler.setFormatter(formatter)
            state_logger.addHandler(handler)

            # Load data from the specified file 
            try:
                with open(state_file, 'r') as file:
                    if file.read(1):
                        file.seek(0)
                        data = [json.loads(line) for line in file]
                        return data
                    else:
                        logger.error(f"Could not load internal state from file - File {state_file} is empty.")
                        return []
            except FileNotFoundError:
                logger.error(f"Could not load internal state from file - File {state_file} does not exist.")
                return []
            except json.JSONDecodeError:
                logger.error(f"Could not load internal state from file - {state_file} has no valid JSON data")
                return []
            except Exception as e:
                logger.error(f"ERROR - Could not load internal state from file - {e}")                                                                                                                
                return []
    
        def dump(self):
            """
            Dump the internal state as JSON 
            """
    
            internal_state = json.dumps(self.entries, indent=4)
            self.log.debug(f"{internal_state}")
    
        def append(self, path: str, prefix: str, access: str, success: bool) -> bool:
            """
            Add an entry to the internal state
            
            :param path: The path of the accessed object
            :type path: str
            :param path: The longest prefix of the accessed object
            :type prefix: str
            :param access: The type of access that has been decided
            :type access: str
            :param success: Whether the access was successful or not
            :type success: bool
            :return: Whether the action was successful or not
            :rtype: bool
            """

            if isinstance(path, str) and isinstance(prefix, str) and isinstance(access, str) and isinstance(success, bool):
                entry = {"Path": path, "Prefix": prefix, "Access": access,
                         "Time": current_time(), "Success": success}
                self.entries.append(entry)
                try:
                    self.state_log.info(json.dumps(entry))
                except Exception as e:
                    self.log.debug(f"ERROR - {e}")
                    pass
                self.log.debug(f"Added entry {entry} to accessed objects")
                return True
            else:
                return False
    
        def query(self, key: str, value: str) -> dict:
            """
            Return all entries from a dictionary that contain a specific value
    
            :param key: The type of entry to search for
            :type key: str
            :param value: The value to search for
            :type value: str
            :return: A list of dictionaries with a corresponding value
            :rtype: dict
            .. todo:: [#5] Sorting the entire list with each access is not performant
            """
    
            list_of_entries = []
            sorted_entries = sorted(
                self.entries, key=lambda item: item['Time'], reverse=True)
            for entry in sorted_entries:
                if entry.get(key) == value and entry.get("Success"):
                    list_of_entries.append(entry)
            return list_of_entries
    
        def is_mimetype(self, path: str, mime_major: str, mime_minor="<None>") -> bool:
            """
            Check, whether a file has a specific mime type
            
            :param path: The file to check
            :type path: str            
            :param mime_major: The first part of the mime type to check. 
                                This has to be an exact string.
            :param mime_minor: The second part of the mime type to check. 
                                This can be a substring or an exact string. 
                                By default, it is set to the string <None> 
                                that is recognizable as a gap filler.
            :type mime_minor: str            
            
            :return: A boolean that is true if the first type of mime type matches, 
                     or the second type of the mime types contains a given string.
            :rtype: bool            
            """
            
    
            real_path = os.path.join(self.dir_to_mount, path[1:])
    
            if os.path.isdir(real_path):
                self.log.debug(
                    f"Object {real_path} is a directory. Ignoring mime type.")
                return False
            elif os.path.isfile(real_path):
                mime_type = magic.from_file(real_path, mime=True)
                file_major, file_minor = mime_type.split('/')
                self.log.debug(
                    f"Mime type of {path} is {mime_type}. Testing for {mime_major} or {mime_minor}")
                return (mime_major == file_major or mime_minor in file_minor)
    
            else:
                self.log.debug(
                    f"Object {real_path} is no directory or file. Ignoring mime type.")
                return False
    
        def written_no_execute(self, path_entries: dict, permission: str, path: str) -> bool:
            """
            
            If an object has already been opened for writing, do not allow the object to be executed
            
            :param path_entries: The entries created on the basis of the
                                  accesses to an object.
            :type path_entries: str
            :param permission: The currently requested permission to the
                                object
            :type permission: str
            :param path: The path of the object to be accessed
            :type path: str
            :return: A boolean that may allow or deny permission
            :rtype: bool
            """
            for entry in path_entries:
                if (
                        entry["Access"] == "write" and entry["Success"] and
                        is_execution_intended(permission)
                ):
                    self.log.info(
                        f"ACCESS ({permission}) DENIED --- Path: {path} --- Accessed at {entry['Time']} with {entry['Access']} access")
                    return False
            return True
    
        def first_object_only(self, path: str, mode: str) -> bool:
            """
           
            If an object below a prefix has already been accessed, 
            access to other objects shall be restricted. 
            
            :param path: The path of the object to be accessed
            :type path: str
            :param mode: The system call to be made 
            :type mode: str
            :return: A boolean that may allow or deny permission
            :rtype: bool
            """
           
            # Check whether 'path' is in 'selections'
            if any(path in entry['Path'] for entry in self.entries):
                self.log.debug(f"Path {path} has already been selected - Permission for {path} is granted")
                return True
            # Check whether any folder above is in 'selections'
            prefix = os.path.dirname(path)
            if any(prefix in entry['Prefix'] for entry in self.entries):
                self.log.debug(f"Prefix {prefix} has already been selected - Permission for {path} is denied")
                return False 
            if path != prefix:
                self.log.debug(f"No Path has been selected under prefix {prefix}")
                self.append(path, prefix, mode, True)  
                
                return True 

        def check_state(self, policies: list, permission: str, path: str) -> bool:
            """
            Check whether the internal state is relevant to an access control decision
            
            :param policies: The policies and entries of the policy file
            :type policies: list
            :param permission: The requested permission over an object
            :type permission: str
            :param path: The path of the object to be accessed
            :type path: str
            :return: A boolean that may allow or deny permission
            :rtype: bool
            .. todo:: [#2] Redundant code regarding path matching
            """
    
            # Check for a recent entry
            if not self.entries:
                self.log.debug(f"No entry recorded yet.")
                return True
            elif not (path_entries := self.query("Path", path)):
                self.log.debug(f"No successful access for {path}")
            else:
                self.log.debug(f"Last successful access: {path_entries[0]}")
    
            accessable = True
    
            for policy in sbac_policies:
                # Check whether any entry can be found
                if not policies[policy]:
                    self.log.debug(f"Policy '{policy}' has no defined objects")
                    continue
                # Check whether a matching entry can be found
                try:
                    prefix = next((muster for muster in sorted(policies[policy].keys(), 
                                   key=len, reverse=True) if re.match(muster, path)), None)
                except re.error as e:
                    self.log.debug(f"ERROR - Could not match path to entrie via regex - {e}")
                if policies[policy].get(prefix) if prefix else False:
                    self.log.debug(f"Policy {policy} allows path {path}")
                    continue
                else:
                    self.log.debug(f"Testing policy {policy} for {path}")
                # Check the policies for which an entry exists
                match policy:
                    case "written-no-execute":
                        if (accessable := self.written_no_execute(
                            path_entries, permission, path)) == False:
                            return False
                    case "first-object-only":
                        if (accessable := self.first_object_only(
                            path, permission)) == False:
                            return False
                    case _:
                        self.log.debug(
                            f"Failed to match {policy} for {path} to rule in the internal state")
                        return True
    
            self.log.debug(
                f"Internal state allows access to {path}: {accessable}")
            return accessable
    
    def check_policy(self, section: dict, path: str, mode: str) -> bool:
        """
        Check whether a policy prevents access to an object depending on previous accesses
        
        :param section: The policies (sections) and entries of the (ini) policy file
        :type section: dict 
        :param path: The path of the object
        :type path: str 
        :param mode: The system call to be made
        :type mode: str 
        :return: A boolean that grants or denies permission
        :rtype: bool 
        .. todo:: [#2] Redundant code regarding path matching
        .. todo:: [#2] Path matching matches file.sh to file even if file.sh is an entry
        """
   
        longest_prefix = None
    
        # Try to match every policy entry for the access mode to the path.
        # Break loop, when match is found
        for key in section.keys():
            try:
                regex = re.compile(key)
            except re.error:
                self.log.warning(
                    f"Regular expression '{key}' could not be compiled. Skipping this policy entry ...")
                continue
            if not re.match(regex, path) is None:
                # At this point a match is found and because the dict is already ordered, this is the most specific match
                longest_prefix = key
                break

        parent_folder = os.path.dirname(path)
    
        # If no entry was found, access is granted by IFS and the permission is up to the OS-permissions
        if longest_prefix is None:
            self.log.info(
                f"No Policy-Entry ({mode}) prefix found for {path} - defaulting to OS-filesystem permissions")
            # TODO [#7] The system does not check whether the OS agrees. Only the IFS issues a authorisation
            if super().access(path, mode):
                self.state.append(path, parent_folder, mode, True)
            else:
                self.state.append(path, parent_folder, mode, False)
            return True
          
        try:
            # If an entry is found, check whether it issues a authorisation
            if section[longest_prefix]:
                # Check whether the syscalls indicates the intention to execute the object
                if not (section[longest_prefix] is False and is_execution_intended(mode) is True):
                    # Check whether the permission requires a certain internal state
                    if self.state.check_state(self.policy, mode, path) is True:
                        # Check whether the permission requires a certain external state
                        if not self.uri_entries or (self.uri_entries and self.usage_with_uri(path, mode) is True):
                            self.log.debug(f"ACCESS ({mode}) GRANTED --- Path: {path} --- Policy-Entry: '{longest_prefix}: "
                                           f"{section[longest_prefix]}'")
                            self.state.append(path, parent_folder, mode, True)
                            return True
        except TypeError as e:
            self.log.info(f"ERROR - Can not check internal or external state - {e}")
    
        # If an entry was found and file access should not be granted by policy raise FuseOSError according to FUSE API
        self.log.info(f"ACCESS ({mode}) DENIED --- Path: {path} --- Policy-Entry: '{longest_prefix}: "
                      f"{section[longest_prefix]}'")
        self.state.append(path, parent_folder, mode, False)
        raise FuseOSError(errno.EPERM)
    
    def call_to_uri(self, path: str, mode: str, ip: str, port: str) -> bool:
        """
        
        Establish a connection to an (external) PDP via a URI to obtain authorization
        
        :param path: The path of the object to be accessed
        :type path: str
        :param mode: The syscall that has to be authorised 
        :type mode: str
        :param ip: The IP of the URI of the PDP
        :type ip: str
        :param port: The Port of the URI of the PDP
        :type port: str
        
        :return: A bool that grants or denies permission. None is returned if
                 an Error happens an no decision has been made.
        :rtype: bool 
        
        .. todo:: [#6] Add mTLS to call_to_uri()
        
        .. todo:: [#6] Add remote integrity check to call_to_uri()
        
        """
    
        self.log.info(f"Requesting validation for mode {mode} on {path} from {ip}:{port}")
    
        # Connect to the URI and send the path to the object to be accessed
        try:
            BUFFER = len(path) + len(mode) + 8
            client_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(3.0)
            client_socket.connect((ip, port))
            self.log.debug(f"Sending {path},{mode} to {ip}:{port}")
            client_socket.send(path.encode() + ",".encode() + mode.encode())
            received_data = client_socket.recv(BUFFER).decode()
            if len(received_data) > BUFFER:
                self.log.debug(
                    f"ERROR - Received data does not fit into the buffer")
                return None 
            self.log.debug(f"Received {received_data} from {ip}:{port}")
            client_socket.close()
        except socket.error as e:
            self.log.error(f"ERROR - Socket error occurred: {e}")
            return None
        except socket.timeout as e:
            self.log.error(f"ERROR - Socket has timed out: {e}")
            return None
        except Exception as e:
            self.log.error(f"ERROR - An unexpected error occurred: {e}")
            return None
    
        # Column the returned string and check if the path was transferred
        # correctly and translate the issued permission into a bool
        rpath, rmode, allowed = received_data.split(',')
        if rpath == path and rmode == mode:
            return (True if allowed == 'True' else False)
        else:
            return False
    
    def usage_with_uri(self, path: str, mode: str) -> bool:
        """
        Check whether an external validator on a predefined URI gives permission
        
        :param path: The path of the object
        :type path: str
        :param mode: The system call to be requested 
        :type mode: str
        :return: A bool that grants or denies permission
        :rtype: bool
        .. todo:: [#2] Merge redundant regex matching
        .. todo:: [#8] Add log message to indicate that no policy is matching the syscall to be executed
        """
   
        patterns = []
        path_entries = {}
        accessable = True
        checked_servers = []

        # Search for exact matches and matching regular expressions and
        # gather dictionaries with key that matches as regular expression
        for entry_pattern, entry_data in self.uri_entries.items():
            try:
                if path == entry_pattern or re.match(entry_pattern, path):
                    patterns.append(entry_pattern) 
            except re.error:
                continue
        for pattern in patterns:
            path_entries.update(self.uri_entries[pattern])
        if not path_entries:
            self.log.debug(f"Ignoring external authorisation, as toml has no entries (referring to mode: {mode})")
            return True

        try:
            # Match 'flat' entries with only a path
            if 'IP' in path_entries and 'PORT' in path_entries:
                self.log.debug(f"Validating external state for {path}")
                accessable = self.call_to_uri(path=path, mode=mode, 
                                  ip=path_entries['IP'], port=path_entries['PORT'])
                self.log.info(f"Path: {path} is allowed: {str(accessable)}")
                return accessable
            # Match entries with a path and access mode
            for fmode, mode_data in path_entries.items():
                if fmode != mode:
                    continue
                if 'IP' in mode_data and 'PORT' in mode_data:
                    self.log.debug(f"Validating external state for {path} and {mode}")
                    accessable = self.call_to_uri(path=path, mode=mode, 
                                      ip=mode_data['IP'], port=mode_data['PORT'])
                    self.log.info(f"Mode {mode} on path: {path} is allowed: {str(accessable)}")
                    return accessable
                else:
                    # Match 'redundant' entries with a path, access mode and server_id
                    for server_id, server_data in mode_data.items():
                        if server_id not in checked_servers:
                            self.log.debug(f"Validating external state for {path} and {mode} on uri {server_id}")
                            accessable = self.call_to_uri(path=path, mode=mode, 
                                              ip=server_data['IP'], port=server_data['PORT'])
                            self.log.info(f"Mode {mode} on path: {path} is allowed (as per server {server_id}): {str(accessable)}")
                            if not accessable:
                                checked_servers.append(server_id)
                            if accessable is False:
                                return False
        except KeyError as e:
            self.log.debug(f"ERROR - Missing expected key in data: {e}")
            accessable = False
        except ValueError as e:
            self.log.debug(f"ERROR - Invalid value in data: {e}")
            accessable = False
        except TypeError as e:
            self.log.debug(f"ERROR - Type mismatch in data: {e}")
            accessable = False
        except Exception as e:  
            self.log.debug(f"ERROR - Unexpected error: {e}")
            accessable = False

        self.log.debug(f"External state allow access to {path}: {accessable}")
        return accessable

    # Section READ #

    def read(self, path, length, offset, fh):
        """
        Gets called when reading the contents of a file
        
        :param path: The path of the accessed object
        :param length: The number of bytes to read
        :param offset: The offset in the file from where to start reading.
        :param fh: The file handle returned by the 'open' method.
        
        :return: The data read from the file by the parent class.
        """
        
        if self.check_policy(self.policy["read"], path, "read"):
            # self.log.debug(f"SYSCALL (read) --- Path: {path}")
            return super().read(path, length, offset, fh)

    def open(self, path, flags):
        """
        Gets called by opening or touching a file
        
        :param path: The path of the accessed object
        :param flags: Flags specifying the mode in which the file is opened.
        :return: File handle representing the opened file.
        """
        set_current_flag(flags)
        if flags == flag_list['fuse.O_EXEC']:
            if self.check_policy(self.policy["execute"], path, "open"):
                self.log.debug(f"SYSCALL (open) --- Flags: {flags} --- Path: {path}")
                return super().open(path, flags)
        elif self.check_policy(self.policy["read"], path, "open"):
            self.log.debug(f"SYSCALL (open) --- Flags: {flags} --- Path: {path}")
            return super().open(path, flags)

    def readdir(self, path, fh):
        """
        Reads the contents of a directory
        
        :param path: The path of the accessed object
        :param fh: The file handle returned by the 'open' method.
        :return: The data read from the file by the parent class.
        """
        
        if self.check_policy(self.policy["read"], path, "readdir"):
            # self.log.debug(f"SYSCALL (readdir) --- Path: {path}")
            return super().readdir(path, fh)

    # Section WRITE #

    def write(self, path, buf, offset, fh):
        """
        Write to a file. Gets called most Operations that write to a file,
        e.g. append, truncate or sth. similar
        
        :param path: The path of the accessed object
        :param buf: The data to be written to the file.
        :param offset: The offset in the file where writing should begin.
        :param fh: The file handle returned by the 'open' method.
        :return: The number of bytes written to the file.
        """
        
        if self.check_policy(self.policy["write"], path, "write"):
            # self.log.debug(f"SYSCALL (write) --- Path: {path}")
            return super().write(path, buf, offset, fh)

    def unlink(self, path):
        """
        Used for removing a file, so is to be categorized under write
        
        :param path: The path of the accessed object
        
        :return: Return value indicating the success of the operation.
        """

        if self.check_policy(self.policy["write"], path, "unlink"):
            # self.log.debug(f"SYSCALL (unlink) --- Path: {path}")
            return super().unlink(path)

    def mkdir(self, path, mode):
        """
        Creates new directory, so is to be categorized under write
        
        :param path: The path of the accessed object
        :param mode: The system call to be made
        
        :return: Return value indicating the success of the operation.
        """
        
        if self.check_policy(self.policy["write"], path, "mkdir"):
            # self.log.debug(f"SYSCALL (mkdir) --- Path: {path}")
            return super().mkdir(path, mode)

    def rmdir(self, path):
        """
        Deletes directory, so is to be categorized under write
        
        :param path: The path of the accessed object
        :return: Return value indicating the success of the operation.
        """
        
        if self.check_policy(self.policy["write"], path, "rmdir"):
            # self.log.debug(f"SYSCALL (rmdir) --- Path: {path}")
            return super().rmdir(path)

    def rename(self, old, new):
        """
        Changes the name of a file or directory, so is to be categorized
        under write
        
        :param old: The path of the old file or directory.
        :param new: The path of the new file or directory.
        :return: Return value indicating the success of the operation.
        """
        
        # Rename needs to read the old file and write the new one, so both
        # modes need to be checked
        if self.check_policy(self.policy["write"], new, "rename") and self.check_policy(self.policy["write"], old, "rename"):
            # self.log.debug(f"SYSCALL (rename) --- Path: {path}")
            return super().rename(old, new)

    # Section EXECUTE #

    def access(self, path, mode):
        """
        Gets called by different methods that contain file or directory access. 
        The method is not overwritten so that access to an object may be checked and
        explicit logging is possible.
        
        :param path: The path of the accessed object
        :param mode: The system call to be made
        :return: Return value indicating the success of the operation.
        """
        #accessable = True 
        ## self.log.debug(f"SYSCALL (access) --- Path: {path}")

        #match mode:
        #    case 0:  # Check, if file exists. Could be seen as read access
        #        accessable = self.check_policy(self.policy["read"], path, "f")
        #    case 1:  # Corresponds to UNIX permission x
        #        accessable = self.check_policy(self.policy["execute"], path, "x")
        #    case 2:  # Corresponds to UNIX permission w
        #        accessable = self.check_policy(self.policy["write"], path, "w")
        #    case 4:  # Corresponds to UNIX permission r
        #        accessable = self.check_policy(self.policy["read"], path, "r")
        #
        ## If the policy accepts the access, check with OS-permissions
        #if accessable:
        #    super().access(path, mode)
        super().access(path, mode)

def main(mountpoint, dir_to_mount, policy_dict, uri_file, state_file):
    """
    
    Main function, so project can be imported and used in other projects
    
    :param dir_to_mount: The directory to be mounted, which is to be
                          regulated via FUSE
    :param policy_dict: The dictionary containing the guidelines
    :param uri_file: The path to the configuration file with the URI
    :param state_file: The path to a json file containing a recorded internal state
    """
    

    infuser_file_system = IFS(dir_to_mount, policy_dict, uri_file, state_file)
    try:
        FUSE(infuser_file_system, mountpoint)
    except RuntimeError:
        # Catch the problem where mountpoint is still mounted and cannot be mounted again
        log = logging.getLogger("infuser")
        log.critical(f"Error while trying to mount FileSystem")
        log.critical(f"Check if {dir_to_mount} is maybe still mounted to {mountpoint} and if so, "
                     f"unmount it with the following command:")
        log.critical(f"sudo fusermount -u {mountpoint}")
        sys.exit(0)


if __name__ == '__main__':
    """
    The starting point of the programme in which the arguments, the logger
    and the policies are instantiated
    """

    args = infuser_setup.parse_args()
    infuser_setup.create_logger(args.log_file, args.verbose)
    policy = infuser_setup.parse_policy(args.policy_file)
    main(args.mountpoint, args.dir_to_mount, policy, args.uri_file, args.state_file)
