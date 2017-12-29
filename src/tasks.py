import os, sys
import pexpect
import time


"""
config {"env":{"run_dir":"."}, "subsystem_config":{"tasks_dir": "/home/sandro/work/athome-tasks/src", "poll_interval":"60"}}
start
"""


def main():
    child = pexpect.spawn('python -m athome.lib.taskrunner')
    child.sendline('{"req_id":null, "message":"start", "payload":{"env":{"run_dir":"."}, "subsystem_config":{"tasks_dir": "/home/sandro/work/athome-tasks/src", "poll_interval":"60"}}}')
    child.expect('.*started\n')
    child.sendline('{"req_id":"asd", "message":"list_tasks", "payload":null}')
    i = child.expect('.*asd\n')
    if i == 0:
        print('success')


if  __name__ == '__main__':
    main()

