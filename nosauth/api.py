"""Api file."""
import binascii
import datetime
import hashlib
import random
import uuid

import requests

try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to PY<37 `importlib_resources`.
    import importlib_resources as pkg_resources


class NtLauncher:
    """Nt launcher class."""

    BROWSER_USERAGENT = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                        'Chrome/72.0.3626.121 Safari/537.36'
    DEFAULT_CHROME_VERSION = 'C2.2.19.1700'
    DEFAULT_GF_VERSION = '2.2.19'
    
    def __init__(self, locale, gf_lang, installation_id=None, chrome_version=None, gf_version=None, cert=None):
        """Init func."""
        self.username = ''
        self.password = ''
        self.locale = locale
        self.gf_lang = gf_lang
        self.installation_id = installation_id
        self.chrome_version = chrome_version
        self.gf_version = gf_version
        self.cert = cert
        self.token = None
        
        if not self.chrome_version:
            self.chrome_version = NtLauncher.DEFAULT_CHROME_VERSION
            
        if not self.gf_version:
            self.gf_version = NtLauncher.DEFAULT_GF_VERSION
            
        if not self.cert:
            data = pkg_resources.read_binary(__package__, 'all_certs.pem')
            start = data.find(b'-----BEGIN CERTIFICATE-----')
            end = data.find(b'-----END CERTIFICATE-----', start)

            self.cert = data[start:end+1+len(b'-----END CERTIFICATE-----')]

    def auth(self, username, password):  # noqa: D102
        self.username = username
        self.password = password
        
        if not self.installation_id:
            m = hashlib.md5((username + password).encode()).digest()
            self.installation_id = str(uuid.UUID(bytes_le=m)) # it generates just unique uuid for username+password, so others who use this library won't have the same installation_id
            
        if not self.send_start_time():
            return False

        URL = 'https://spark.gameforge.com/api/v1/auth/sessions'
        HEADERS = {
            'User-Agent': NtLauncher.BROWSER_USERAGENT,
            'TNT-Installation-Id': self.installation_id,
            'Origin': 'spark://www.gameforge.com',
        }

        CONTENT = {
            'email': self.username,
            'locale': self.locale,
            'password': self.password,
        }
        
        r = requests.post(URL, headers=HEADERS, json=CONTENT)
        if r.status_code != 201:
            return False
        
        response = r.json()
        self.token = response['token']
        return True
        
    def send_start_time(self):  # noqa: D102
        HEADERS = {
            'Host': 'events.gameforge.com',
            'User-Agent': f'GameforgeClient/{self.gf_version}',
            'Content-Type': 'application/json',
            'Connection': 'Keep-Alive',
        }

        PAYLOAD = """{
    "client_installation_id": "%INSTALLATION_ID%",
    "client_locale": "pol_pol",
    "client_session_id": "%SESSION_ID%",
    "client_version_info": {
        "branch": "master",
        "commit_id": "27942713",
        "version": "%CHROME_VERSION%"
    },
    "id": 0,
    "localtime": "%LOCAL_TIME%",
    "start_count": 1,
    "start_time": %START_TIME%,
    "type": "start_time"
}
        """
        
        payload = PAYLOAD.replace('%INSTALLATION_ID%', self.installation_id)
        payload = payload.replace('%SESSION_ID%', str(uuid.uuid4()))
        payload = payload.replace('%CHROME_VERSION%', self.chrome_version[1:])
        
        def rreplace(s, old, new, occurrence):
            li = s.rsplit(old, occurrence)
            return new.join(li)

        eu = datetime.timezone(datetime.timedelta(hours=1))  # EU timezone
        date = datetime.datetime.now(eu)
        date = date.replace(microsecond=0)
        
        payload = payload.replace('%LOCAL_TIME%', rreplace(date.isoformat(), ":", "", 1))
        payload = payload.replace('%START_TIME%', str(random.randint(1500, 10000)))
        
        with pkg_resources.path(__package__, 'all_certs.pem') as path:
            cert_path = str(path)
        
        r = requests.post(
            'https://events.gameforge.com',
            headers=HEADERS, data=payload,
            cert=cert_path, verify=cert_path)
        
        if r.status_code != 200:
            return False
            
        return True
        
    def get_accounts(self):  # noqa: D102
        if not self.token:
            return False
        
        URL = 'https://spark.gameforge.com/api/v1/user/accounts'

        HEADERS = {
            'User-Agent': NtLauncher.BROWSER_USERAGENT,
            'TNT-Installation-Id': self.installation_id,
            'Origin': 'spark://www.gameforge.com',
            'Authorization': f'Bearer {self.token}',
            'Connection': 'Keep-Alive',
        }

        r = requests.get(URL, headers=HEADERS)

        if r.status_code != 200:
            return False
            
        accounts = []
        response = r.json()
        
        for key in response.keys():
            accounts.append((key, response[key]['displayName']))

        return accounts

    def _convert_token(self, guid):  # noqa: D102
        return binascii.hexlify(guid.encode()).decode()
        
    def get_first_number(self, uuid):  # noqa: D102
        for char in uuid:
            if char.isdigit():
                return char
        return None
        
    def generate_second_type_user_agent_magic(self):  # noqa: D102
        firstLetter = self.get_first_number(self.installation_id)
        
        if not firstLetter or not int(firstLetter) % 2:
            hash_of_cert = hashlib.sha256(self.cert).hexdigest()
            hash_of_version = hashlib.sha1(self.chrome_version.encode('ascii')).hexdigest()
            hash_of_installation_id = hashlib.sha256(self.installation_id.encode('ascii')).hexdigest()
            hash_of_sum = hashlib.sha256(
                (hash_of_cert + hash_of_version + hash_of_installation_id).encode('ascii')).hexdigest()
            return hash_of_sum[:8]
            
        else:
            hash_of_cert = hashlib.sha1(self.cert).hexdigest()
            hash_of_version = hashlib.sha256(self.chrome_version.encode('ascii')).hexdigest()
            hash_of_installation_id = hashlib.sha1(self.installation_id.encode('ascii')).hexdigest()
            hash_of_sum = hashlib.sha256(
                (hash_of_cert + hash_of_version + hash_of_installation_id).encode('ascii')).hexdigest()
            return hash_of_sum[-8:]
        
    def generate_third_type_user_agent_magic(self, account_id):  # noqa: D102
        first_letter = self.get_first_number(self.installation_id)
        first_two_letters_of_account_id = account_id[:2]
        
        if not first_letter or not int(first_letter) % 2:
            hash_of_cert = hashlib.sha256(self.cert).hexdigest()
            hash_of_version = hashlib.sha1(self.chrome_version.encode('ascii')).hexdigest()
            hash_of_installation_id = hashlib.sha256(self.installation_id.encode('ascii')).hexdigest()
            hash_of_account_id = hashlib.sha1(account_id.encode('ascii')).hexdigest()
            hash_of_sum = hashlib.sha256(
                (hash_of_cert + hash_of_version + hash_of_installation_id + hash_of_account_id).encode('ascii'),
            ).hexdigest()
            return first_two_letters_of_account_id + hash_of_sum[:8]
        hash_of_cert = hashlib.sha1(self.cert).hexdigest()
        hash_of_version = hashlib.sha256(self.chrome_version.encode('ascii')).hexdigest()
        hash_of_installation_id = hashlib.sha1(self.installation_id.encode('ascii')).hexdigest()
        hash_of_account_id = hashlib.sha256(account_id.encode('ascii')).hexdigest()
        hash_of_sum = hashlib.sha256(
            (hash_of_cert + hash_of_version + hash_of_installation_id + hash_of_account_id).encode('ascii'),
        ).hexdigest()
        return first_two_letters_of_account_id + hash_of_sum[-8:]

    def get_token(self, account, raw=False):  # noqa: D102
        if not self.token:
            return False
        
        URL = 'https://spark.gameforge.com/api/v1/auth/thin/codes'

        ua_magic = self.generate_third_type_user_agent_magic(account)
        HEADERS = {
            'User-Agent': f'Chrome/{self.chrome_version} ({ua_magic}) GameforgeClient/{self.gf_version}',
            'TNT-Installation-Id': self.installation_id,
            'Origin': 'spark://www.gameforge.com',
            'Authorization': f'Bearer {self.token}',
            'Connection': 'Keep-Alive',
        }

        CONTENT = {
            'platformGameAccountId': account,
            'gsid': f'{uuid.uuid4()}-{random.randint(1000, 9999)}',
        }

        r = requests.post(URL, headers=HEADERS, json=CONTENT)

        if r.status_code != 201:
            return False

        if raw:
            return r.json()['code']
        
        return self._convert_token(r.json()['code'])
