import subprocess as sp
import random
import tempfile


def append_p_and_g(prop_reads, command_list):
    text_file = open("random.txt", "w")
    for i in range(125000000):
        x = random.random()
        if x < prop_reads:
            text_file.write('g ' + str(random.randrange(0, 10000)))
        else:
            text_file.write('p ' + str(random.randrange(0, 10000)) + ' ' + str(random.randrange(0, 10000)))
    text_file.close()
    return text_file


def insert_10gb():
    text_file = open("sample.txt", "w")
    for i in range(1250000000):
        text_file.write('p ' + str(random.randrange(0, 10000)) + ' ' + str(random.randrange(0, 10000)) + '\n')
    text_file.close()
    return text_file


with tempfile.NamedTemporaryFile() as input:
    insert_10gb()
    text_file = open("sample.txt", "r+")
    p = sp.Popen([f'build/main < {text_file.read()}'], stdout=sp.PIPE, stdin=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = p.communicate()
    print('stdout:')
    print(stdout.decode())
    print('stderr:')
    print(stderr.decode())
    print('exitcode:')
    print(p.returncode)


