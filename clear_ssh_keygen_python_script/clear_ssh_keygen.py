import os
import argparse
import subprocess
import logging


def clear_ssh(args):
    verb = 'Would' if args.dry_run else 'Will'
    logger.info('%s run ssh-keygen -f "/home/.ssh/known_hosts" -R %s', verb, args.host)
    if not args.dry_run:
        try:
            subprocess.check_call(['ssh-keygen', '-f', '/home/.ssh/known_hosts', '-R', args.host])
        except subprocess.CalledProcessError:
            logger.exception('ssh-keygen did not work as expected, please check /home/.ssh/known_hosts')
        logger.info('%s was removed from /home/.ssh/known_hosts successfully', args.host)


def main():
    p = argparse.ArgumentParser(description='SSM run script for purging ssh keys')
    p.add_argument('-n', '--dry-run', action='store_true', help='Dry run mode')
    p.add_argument('--host', type=str, default='', help='host endpoint')
    args = p.parse_args()
    if os.path.exists('/home/.ssh/known_hosts'):
        clear_ssh(args)
    else:
        logger.info('ssh-keygen was skipped because file /home/.ssh/known_hosts does not exist on host')


if _name_ == '_main_':

    main()