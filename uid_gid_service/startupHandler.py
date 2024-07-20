#!/usr/bin/env python3

# Takes parameters
# startupHandler.py  application, parameters, [:groups]

import subprocess
import os
import sys


def run():
    if len(sys.argv) < 3:
        print("argument exception")
        return 1


    print(os.getpid())
    input()
    # exec new child process
    subprocess_parameters = ['./launcher.py']
    subprocess_parameters.extend(sys.argv[1:])
    subprocess.Popen(subprocess_parameters)
    # use as parameter sys.argv[1:]


if __name__ == '__main__':
    run()
