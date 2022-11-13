
import mimetypes
from datetime import date, datetime


try:
    import pysftp
except Exception as err:
    pysftp = None

def SEND(task):
    """
    tdata.host = host
    tdata.filename = filename
    # TODO this should be more secure!
    # TODO support ssh keys?
    tdata.username = username
    tdata.password = password
    tdata.data = data

    :param      task:  The task
    :type       task:  { type_description }

    :returns:   { description_of_the_return_value }
    :rtype:     { return_type_description }
    """
    now = datetime.now()
    filename = task.data.filename.format(date=now)
    host = task.data.host
    port = task.data.get("port", 22)
    if ":" in host:
        host, port = host.split(":")
    client = FTPClient(host, port,
        username=task.data.username,
        password=task.data.password,
        default_dir=task.data.path)
    client.put(filename, task.data.data)
    client.disconnect()
    return False

class FTPClient(object):
    def __init__(self, host, port=22, username=None, password=None, default_dir=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.cnopts = pysftp.CnOpts()
        self._client = self.connect()
        if default_dir:
            self.chdir(default_dir)

    def __del__(self):
        self.disconnect()

    def connect(self):
        self.cnopts.hostkeys = None
        return pysftp.Connection(host=self.host, 
            port=self.port,
            username=self.username,
            password=self.password,
            cnopts=self.cnopts)

    def disconnect(self):
        if not self._client: return
        self._client.close()

    def chdir(self, path):
        self._client.chdir(path)

    def put(self, file_name, file_data):
        with self._client.open(file_name, 'wb') as f:
            f.write(file_data)
