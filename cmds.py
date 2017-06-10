import subprocess, time
import os, errno
from contextlib import contextmanager


@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def run(args, shell = False):
    try:
        p = subprocess.check_output(args, stderr=subprocess.STDOUT, shell=shell).decode("utf-8")
#         print p # prints the output if any for a zero return
        return (0, p)
    except OSError as e: # bad command
#         print e
        # TODO: log this error
        return
    except subprocess.CalledProcessError as e: # non zero return
#         print e.returncode # the non zero return code
#         print e.cmd # the cmd that caused it
#         print e.output # the error output (if any)  
        return (e.returncode, e.output)
    
def generate_key_fingerprint(key_path):
    args = ['ssh-keygen', '-lf', key_path]
    ret = run(args)
    try:
        (returncode, output) = ret
    except ValueError:
        # bad command
        return
         
    if returncode == 0:   
        return output.strip().split(' ')[1].strip()
    else:
        return False

def block_directory_creation():
    args = ['/bin/bash', '-c', 'i=50000; while setfacl -m "d:u:${i}:-" .; do i=$((i + 1)); done']
    ret = run(args)


def give_dir_permissions(dir_path, owner, group):
    args = ['chown', '{0}:{1}'.format(owner, group), dir_path]
    ret = run(args)

    args = ['chmod', '0770', dir_path]
    ret = run(args)

    