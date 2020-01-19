# Pythonista Client
import datetime
import time
import requests
from requests.auth import HTTPBasicAuth
import location, motion, dialogs


def gps_to_utc(gps_timestamp):
    # https://stackoverflow.com/questions/33415475/how-to-get-current-date-and-time-from-gps-unsegment-time-in-python
    # utc = 1980-01-06UTC + (gps - (leap_count(2017) - leap_count(1980)))
    # leap_count table: http://hpiers.obspm.fr/eop-pc/index.php?index=TAI-UTC_tab&lang=en
    return datetime.datetime(1980, 1, 6) + datetime.timedelta(seconds=gps_timestamp - (37 - 19))


def connection_dialog():
    config = dialogs.form_dialog(
            title='Python Automotive Telemetry Lab',
            sections=[
                [   # First Section
                    'Server Connection Info',
                    [
                        {
                            'type':         'url',
                            'key':          'base_url',
                            'title':        'Base URL',
                            'value':        'http://192.168.2.10:8000/',
                        },
                        {
                            'type':        'text',
                            'key':         'username',
                            'title':       'username',
                        },
                        {
                            'type':        'text',
                            'key':         'password',
                            'title':       'password',
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
                            'value':        '0',
                        },
                    ],
                    'Zero value means no loop delay.',
                ],
                [
                    # Third Section
                    'Data Transmission Failure Handling',
                    [
                        {
                            'type':          'number',
                            'key':           'max_retries',
                            'title':         'Maximum Number of Retries',
                            'value':         '10',
                        },
                        {
                            'type':          'number',
                            'key':           'retry_delay',
                            'title':         'Retry Delay in Seconds',
                            'value':         '60',
                        },
                        {
                            'type':           'number',
                            'key':            'reset_retry_counter_duration',
                            'title':          'Reset Retry Counter Duration in Seconds',
                            'value':          '3600',
                        },
                    ],
                ],
            ]
        )
    
    if config is None:
        return None

    if config['base_url'][-1:] != '/':
        config['base_url'] = base_url + '/'

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
            r = requests.post(base_url + path, auth=self.auth, data=data)
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

base_url = None
username = None

while base_url is None or username is None:
    config = connection_dialog()
    if config:
        base_url = config['base_url']
        username = config['username']

print(config)

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
        location_data['sat_timestamp'] = gps_to_utc(location_data['timestamp'])

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
    dialogs.alert('Too many failures to continue...')
    exit(1)

exit(0)