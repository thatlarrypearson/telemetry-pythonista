# Pythonista Client
import datetime
import time
import json
import requests
from requests.auth import HTTPBasicAuth
import location, motion, dialogs


DEFAULT_CONFIG = {
    'use_config_file':               False,
    'save_config_file':              True,
    'config_file_name':              'pythonista_client_config.json',
    'base_url':                      'http://localhost:8000',
    'username':                      'test1',
    'password':                      'telemetry',
    'interval':                      '0',
    'max_retries':                   '3',
    'retry_delay':                   '3',
    'reset_retry_counter_duration':  '3600',
}


def get_config_or_defaults():
    config = None
    try:
        with open(DEFAULT_CONFIG['config_file_name'], 'r') as fd:
            config = json.load(fd)
        return config
    except:
        pass

    return dict(DEFAULT_CONFIG)


def save_config(config):
    with open(config['config_file_name'], 'w') as fd:
        json.dump(config, fd)
    
    if DEFAULT_CONFIG['config_file_name'] != config['config_file_name']:
        print("\n\nWARNING: only default config file (%s) gets loaded on startup.\n\n" % (
            DEFAULT_CONFIG['config_file_name'],
        ))


def connection_dialog(config):
    config = dialogs.form_dialog(
            title='Python Automotive Telemetry Lab',
            sections=[
                [
                    # Config Section
                    'Configuration Information',
                    [
                        {
                            'type':        'switch',
                            'key':         'use_config_file',
                            'title':       'Use Config File',
                            'value':       config['use_config_file'],
                        },
                        {
                            'type':        'switch',
                            'key':         'save_config_file',
                            'title':       'Save Config File',
                            'value':       config['save_config_file'],
                        },
                        {
                            'type':        'text',
                            'key':         'config_file_name',
                            'title':       'Config File Name',
                            'value':       config['config_file_name'],
                        },
                    ],
                ],
                [   # First Section
                    'Server Connection Info',
                    [
                        {
                            'type':         'url',
                            'key':          'base_url',
                            'title':        'Base URL',
                            'value':        config['base_url'],
                        },
                        {
                            'type':        'text',
                            'key':         'username',
                            'title':       'username',
                            'value':       config['username'],
                        },
                        {
                            'type':        'text',
                            'key':         'password',
                            'title':       'password',
                            'value':       config['password'],
                        },
                    ],
                ],
                [
                    # Second Section
                    'Data Collection',
                    [
                        {
                            'type':         'number',
                            'key':          'interval',
                            'title':        'Cycle Interval In Milliseconds',
                            'value':        config['interval'],
                        },
                    ],
                    'Zero value means no loop delay.\n\n',
                ],
                [
                    # Third Section
                    'Data Transmission Failure Handling',
                    [
                        {
                            'type':          'number',
                            'key':           'max_retries',
                            'title':         'Maximum Number of Retries',
                            'value':         config['max_retries'],
                        },
                        {
                            'type':          'number',
                            'key':           'retry_delay',
                            'title':         'Retry Delay in Seconds',
                            'value':         config['retry_delay'],
                        },
                        {
                            'type':           'number',
                            'key':            'reset_retry_counter_duration',
                            'title':          'Reset Retry in Seconds',
                            'value':          config['reset_retry_counter_duration'],
                        },
                    ],
                ],
            ]
        )
    
    if config is None:
        return None

    if config['base_url'][-1:] != '/':
        config['base_url'] = config['base_url'] + '/'

    return config


class BasicAuthRequest():
    auth = None
    retry_count = 0
    last_successful_try = datetime.datetime.now()

    def __init__(self, config):
        self.base_url = config['base_url']
        self.username = config['username']
        self.password = config['password']
        self.interval = int(config['interval'])
        self.max_retries = int(config['max_retries'])
        self.retry_delay = int(config['retry_delay'])
        self.reset_retry_counter_duration = int(config['reset_retry_counter_duration'])

        self.auth = HTTPBasicAuth(self.username, self.password)

    def post(self, path, data):
        try:
            r = requests.post(self.base_url + path, auth=self.auth, data=data)
        except Exception as e:
            print("\n\nrequests.post() exception: %s" % (str(e), ))
            self.transmit_failure()
        else:
            if r.status_code != 201:
                print("\n\nrequests.post() status_code = %d" % (r.status_code, ))
                self.transmit_failure()
            self.last_successful_try = datetime.datetime.now()

    def transmit_failure(self):
        right_now = datetime.datetime.now()
        if (right_now - self.last_successful_try).total_seconds() > self.reset_retry_counter_duration:
            self.retry_count = 0
        else:
            self.retry_count = self.retry_count + 1
            if self.retry_count > self.max_retries:
                raise Exception('retry counter exceeded')
            

if not location.is_authorized():
    dialogs.alert('Authorize Location Services For Pythonista Application Before Continuing')
    raise Exception('Location Services Not Enabled')

config = get_config_or_defaults()

if config['use_config_file']:
    print("Starting from config file (%s)\n" % (config['config_file_name'], ))
else:
    config = connection_dialog(config)

if not config:
    print("\n\nNo configuration - exiting.\n\n")
    exit(1)

print("Configuration: %s\n" % (str(config), ))

if config['save_config_file']:
    save_config(config)
    print("Config file (%s) saved.\n" % (config['config_file_name'], ))

r = BasicAuthRequest(config)

location.start_updates()
motion.start_updates()

try:

    while True:
        x, y, z = motion.get_gravity()
        gravity_data = {'x': x, 'y': y, 'z': z}

        x, y, z = motion.get_user_acceleration()
        acceleration_data = {'x': x, 'y': y, 'z': z}

        roll, pitch, yaw = motion.get_attitude()
        attitude_data = {'roll': roll, 'pitch': pitch, 'yaw': yaw}

        x, y, z, accuracy = motion.get_magnetic_field()
        magnetic_data = {'x': x, 'y': y, 'z': z, 'accuracy': accuracy}

        location_data = location.get_location()

        r.post('ios_sensor_pack/gravity/', gravity_data)
        r.post('ios_sensor_pack/user_acceleration/', acceleration_data)
        r.post('ios_sensor_pack/attitude/', attitude_data)
        r.post('ios_sensor_pack/magnetic_field/', magnetic_data)
        r.post('ios_sensor_pack/location/', location_data)

        if r.retry_delay != 0:
            time.sleep(float(r.retry_delay)/1000.0)


except Exception as e:
    location.stop_updates()
    motion.stop_updates()
    print("\n\nException: %s" % (str(e), ))
    dialogs.alert('Too many failures to continue...\n\nBye!')
    exit(1)

exit(0)