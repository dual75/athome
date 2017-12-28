import os, sys
import pexpect
import time


"""
config {"env":{"run_dir":"."}, "subsystem_config":{"tasks_dir": "/home/sandro/work/athome-tasks/src", "poll_interval":"60"}}
start
"""


def main():
    child = pexpect.spawn('python -m athome.lib.taskrunner')
    child.expect('ready\n')
    child.sendline('start  {"env":{"run_dir":"."}, "subsystem_config":{"tasks_dir": "/home/sandro/work/athome-tasks/src", "poll_interval":"60"}}')
    child.expect('started\n')
    child.sendline('list_tasks')
    i = child.expect('list_tasks\n')
    if i == 0:
        print('success')


if  __name__ == '__main__':
    main()

