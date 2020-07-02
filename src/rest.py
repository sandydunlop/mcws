#!/usr/bin/python3

import subprocess
from flask import request, Response
from flask import Flask
from functools import wraps
import json
import os


CONF_FILE="/etc/mcws.conf"

env_conf_file = os.environ.get('CONF_FILE')
if env_conf_file != None:
    CONF_FILE = env_conf_file

app = Flask(__name__)


############ Support functions ############

def read_conf():
    # Some defaults...

    # The port this web service runs on
    service_port='4446'

    # The minecraft server host and port it talks to
    mc_host='127.0.0.1'
    mc_port='23888'

    token = None
    test_token = None
    rconpass = None
    rcon_path = '/usr/bin/mcrcon'
    daemon_log_script=None
    try:
        f = open(CONF_FILE, 'r')
        for line in f.read().split('\n'):
            if line.find('=')>0:
                (n,v) = line.split('=')
                if n == 'token':
                    token = v
                elif n == 'test_token':
                    test_token = v
                elif n == 'rconpass':
                    rconpass = v
                elif n == 'mc_host':
                    mc_host = v
                elif n == 'mc_port':
                    mc_port = v
                elif n == 'service_port':
                    service_port = v
                elif n == 'daemon_log_script':
                    daemon_log_script = v
                elif n =='rcon_path':
                    rcon_path = v
    except:
        pass
    return (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script)


def not_authorized():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script) = read_conf()
        given_token = request.headers.get('Authorization')
        if given_token != token and given_token != test_token:
            return not_authorized()
        return f(*args, **kwargs)
    return decorated


def server_command(cmd):
    (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script) = read_conf()
    bytes_string = subprocess.check_output([rcon_path,'-H', mc_host, '-P', mc_port ,'-p', rconpass, cmd])
    output = str(bytes_string, 'utf-8', 'ignore')
    return output[:-5]


########## Production webservice endpoints ###########

@app.route('/weather/<x>', methods=['GET'])
def weather(x):
    output = server_command('/weather %s 600' % x)
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/time/<x>', methods=['GET'])
def set_time(x):
    r = '{"response":"denied"}'
    if x == 'day':
        output = server_command('/time set day')
        r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/online', methods=['GET'])
def online_players():
    (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script) = read_conf()
    array_as_string = ''
    bytes_string = subprocess.check_output([rcon_path,'-H', mc_host, '-P', mc_port ,'-p', rconpass, '/list'])

    output = str(bytes_string, 'utf-8', 'ignore')

    list_start_pos = output.find('online:')
    if list_start_pos > -1 and len(output) > 14:
        csv = output[list_start_pos+8:-5]
        items = csv.split(',')
        array_as_string = ','.join(['"' + x.strip() + '"' for x in items])
        print (array_as_string)

    r = '{"online-players":[%s]}' % array_as_string
    return Response(r, mimetype='text/json')


@app.route('/say/<x>', methods=['GET'])
@requires_auth
def say(x):
    output = server_command('/say %s' % x)
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/locate-player/<x>', methods=['GET'])
def locate_player(x):
    output = server_command('/tp %s ~ ~ ~' % x)
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/whitelist/add/<id>', methods=['GET'])
@requires_auth
def whitelist_add(id):
    output = server_command('/whitelist add %s' % id)
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/whitelist/remove/<id>', methods=['GET'])
@requires_auth
def whitelist_remove(id):
    output = server_command('/whitelist remove %s' % id)
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


# This calls a script that returns only the Minecraft server entries 
# from /var/log/daemon.log and isn't going to remain like this. I'm not
# sure how to get Minecraft running as a systemd service to log to its
# own file, so I either have to work that out, or find a better way of
# doing this.
@app.route('/daemongrep', methods=['GET'])
@requires_auth
def daemon_grep():
    (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script) = read_conf()
    output = 'fail'
    bytes_string = bytearray()
    try:
        bytes_string = subprocess.check_output([daemon_log_script], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        a = 'FAILURE: code=%s, msg=' % exc.returncode
        output = a + str(exc.output, 'utf-8', 'ignore')
    else:
        all_lines = str(bytes_string, 'utf-8', 'ignore')
        output = all_lines.splitlines()
    j = json.dumps(output)
    r = '{"response":%s}' % j
    return Response(r, mimetype='text/json')


########## Test webservice endpoints ###########

@app.route('/test', methods=['GET'])
def test_method():
    r = '{"response":"success""}'
    return Response(r, mimetype='text/json')


@app.route('/auth-test', methods=['GET'])
@requires_auth
def auth_test():
    r = '{"response":"success""}'
    return Response(r, mimetype='text/json')


@app.route('/test/new-bartender', methods=['GET'])
def new_bartender():
    output = server_command('/summon villager -236 64 -193')
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


@app.route('/config/reload', methods=['GET'])
@requires_auth
def config_reload():
    output = server_command('/reload')
    r = '{"response":"%s"}' % output
    return Response(r, mimetype='text/json')


###########################################

if __name__ == "__main__":
    (rcon_path,service_port,mc_host,mc_port,token,test_token,rconpass,daemon_log_script) = read_conf()
    port = int(service_port)
    app.run(host='0.0.0.0',port=service_port)
