"""
Setup for the (SB)AC on FUSE Project. The main computation is done in the :doc:`infuser`.

Created by Alexander Krause on 02/28/2023.
Modified by Stephan Winker from 10/01/2023 to 28/02/2024.

Libraries/Modules:

- argparse standard library
  - Access to argument parsing functionality
- datetime standard library
  - Access to current date and time
- logging standard library
  - Access to logging functionality
- sys standard library
  - Access to the exit function
- re standard library
  - Access to regular expressions
- configparser standard library
  - Access to ConfigParser to parse the .ini format
- collections standard library
  - Access to OrderedDict

"""

import argparse
import datetime
import logging
import sys
import re

from configparser import ConfigParser
from collections import OrderedDict


def create_logger(log_file: str, log_level: int) -> None:
    """
    Creates an object from the logging library, specifying several log levels
    and a format
    
    :param log_file: The file to log to
    :type log_file: str
    :param log_level: The verbosity of the logging process
    :type log_level: str
    """

    # Specify logging format
    logging_format = "%(asctime)s | %(levelname)-8s | %(name)s / %(funcName)-18s | %(message)s"
 durch die Implementierung blockiert. Der Prozess ist
    # Bring log_level in format given by logging-framework
    log_level *= 10
    if log_level > logging.CRITICAL:
        log_level = logging.CRITICAL

    # Set logger to default-level WARNING if not set
    if log_level == logging.NOTSET:
        log_level = logging.WARNING

    # Determining file name for current logfile
    current_time = datetime.datetime.now()
    log_file = log_file.rsplit(".", 1)[0] + "_" + f"{current_time.year:04d}-{current_time.month:02d}-" \
                                                  f"{current_time.day:02d}_{current_time.hour:02d}:" \
                                                  f"{current_time.minute:02d}:{current_time.second:02d}.log"

    # Create handler and formatter
    f_handler = logging.FileHandler(log_file)
    f_handler.setLevel(log_level)
    formatter = logging.Formatter(logging_format)
    f_handler.setFormatter(formatter)

    # Add handlers to custom logger
    logger = logging.getLogger("infuser")
    logger.addHandler(f_handler)
    logger.setLevel(log_level)

def parse_args():
    """
    Parses and defines the command line arguments. Provides defaults and type
    definitions.
    """

    parser = argparse.ArgumentParser(description='Programm zum Mounten eines FUSE Dateisystems unter Einbeziehung '
                                                 'einer Policy zur Zugriffskontrolle.')
    required_named = parser.add_argument_group('Pflichtargumente')
    required_named.add_argument('-d', '--dir-to-mount', type=str, required=True, metavar='dir_to_mount',
                                help='Ursprungspfad, der gemounted werden soll.')
    required_named.add_argument('-m', '--mountpoint', type=str, required=True,
                                help='Zielpfad, auf den der Ursprungspfad gemounted werden soll.')
    parser.add_argument('-p', '--policy-file', type=str, metavar='policy_file',
                        help='Pfad zu der zu verwendenden Policy-Konfiguration. Diese muss im .ini-Format '
                             'vorliegen.')
    parser.add_argument('-l', '--log-file', type=str, default='infuser.log', metavar='log_file',
                        help='Pfad zu einer Log-Datei.')
    parser.add_argument('-u', '--uri-file', type=str, metavar='uri_file',
                        help='Pfad zu einer Datei mit URI von Servern zur Autorisierungsanfrage. Diese muss im .csv-Format vorliegen.')
    parser.add_argument('-s', '--state-file', type=str, metavar='state_file',
                        help='Pfad zu einer Datei mit geloggten Zugriffsentscheidungen. Diese muss im .json-Format vorliegen.')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Log-level des Programms. Wird durch die Anzahl v definiert. 5 v ist Log-Level CRITICAL\n'
                             ' - 1 v ist Log-Level DEBUG. Bsp: -vvv ist Log-Level WARNING')
    return parser.parse_args()


def parse_policy(pf: str):
    """
    Parses the policies, whereby excessive error handling is carried out.
    attention is paid to correct values and regular expressions according to
    longest prefix matching
    
    :param pf: The file containing the policies
    :type pf: str
    """
    
    log = logging.getLogger('infuser')

    parser = ConfigParser()
    try:
        # Try to read the contents of the policy file
        parser.read(pf)
    except FileNotFoundError as e:
        # Invalid policy file-path
        log.critical(f"Could not read policy-file: {pf} - {e.strerror}")
        sys.exit(0)
    except TypeError:
        # No policy provided
        log.info(f"No policy-file provided, using empty default config")
        return {"read": {"/*": True}, "write": {"/*": True}, "execute": {"/*": True}}

    policy = dict()

    # Allowed values for Policy File
    # Values if access to filepath should be granted
    values_allow = ["allow", "true", "1"]
    # Values if access to filepath should not be granted
    values_deny = ["deny", "false", "0"]
    values_section = ["read", "write", "execute", "written-no-execute",
                      "first-object-only"]  # Values for names of the sections

    # Parse the contents of the policy
    for sec in parser.sections():
        if sec not in values_section:
            # Invalid section name found, skipping section
            log.error(
                f"Policy Section {sec} has incorrect value. Permitted are: {values_section}")
            log.error(f"Skipping this section ...")
            continue
        policy[sec] = OrderedDict()
        # Log the contents of the policy file for debug reasons
        log.debug(f"{sec} - {parser.items(sec)}")
        for item in parser.items(sec):
            is_allowed = False
            # Should access to filepath be granted according to policy
            if item[1].lower() in values_allow:
                is_allowed = True
            elif item[1].lower() not in values_deny:
                # Invalid value for filepath found, skipping filepath
                log.warning(
                    f"Policy Entry {item} has incorrect value. Permitted are: {values_allow} or {values_deny}")
                log.warning(f"Skipping this entry ...")
                continue
            # If access to filepath should not be granted according to policy, it will be False at this point
            policy[sec][item[0]] = is_allowed

        # sort the section for longest regex without wildcard
        find_wildcards_in_regex = re.compile(r"(?<!\\)[(\[{?*+|.$^]")
        policy[sec] = \
            OrderedDict(
                sorted(
                    policy[sec].items(), key=lambda tmp_key: len(
                        re.split(find_wildcards_in_regex,
                                 tmp_key[0], maxsplit=1)[0]
                    ), reverse=True
                )
        )

    # Add section to policy dict if it's not there so there are no KeyErrors later on
    for section in values_section:
        try:
            policy[section]
        except KeyError:
            policy[section] = dict()

    return policy
