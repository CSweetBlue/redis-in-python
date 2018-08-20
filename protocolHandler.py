from io import BytesIO

from collections import namedtuple

class Disconnect(Exception): pass
class CommandError(Exception): pass

Error = namedtuple('Error', ('message',))

class ProtocolHandler(object):
    def __init__(self):
        self.handlers = {
            '+': self.handle_simple_string,
            '-': self.handle_error,
            ':': self.handle_integer,
            '$': self.handle_string,
            '*': self.handle_array,
            '%': self.handle_dict,
        }

    def handle_request(self, socket_file):
        first_byte = socket_file.read(1)

        if not first_byte:
            raise Disconnect()

        try:
            return self.handlers[first_byte](socket_file)
        except KeyError:
            raise CommandError('Bad Request.')
    
    def handle_simple_string(self, socket_file):
        return socket_file.readline().rstrip('\r\n')

    def handle_error(self, socket_file):
        return Error(socket_file.readline().rstrip('\r\n'))
    
    def handle_integer(self, socket_file):
        return int(socket_file.readline().rstrip('\r\n'))

    def handle_string(self, socket_file):
        length = int(socket_file.readline().rstrip('\r\n'))

        if length == -1:
            return None
        
        length +=2

        return socket_file.read(length)[:-2]
    
    def handle_array(self, socket_file):
        num_elements = int(socket_file.readline().rstrip('\r\n'))
        return [self.handle_request(socket_file) for _ in range(num_elements)]

    def handle_dict(self, socket_file):
        num_items = int(socket_file.readline().rstrip('\r\n'))
        elements = [self.handle_request(socket_file) for _ in range(num_items * 2)]

        return dict(zip(elements[::2], elements[1::2]))

    def write_response(self, socket_file, data):
        buf = BytesIO()
        self._write(buf, data)
        buf.seek(0)
        socket_file.write(buf.getvalue())
        socket_file.flush()

    def _write(self, buf, data):
        print(type(data))
        
        if isinstance(data, str):
            data = data.encode('utf-8')

        if isinstance(data, bytes):
            buf.write('$%s\r\n%s\r\n' % (len(data), data))
        elif isinstance(data, int):
            buf.write(':%s\r\n' % data)
        elif isinstance(data, Error):
            buf.wirte('-%s\r\n' % Error.message)
        elif isinstance(data, (list, tuple)):
            buf.write('*%s\r\n' % len(data))
            for item in data:
                self._write(buf, item)
        elif isinstance(data, dict):
            buf.write('%%%s\r\n' % len(data))
            for key in data:
                self._write(buf, key)
                self._write(buf, data[key])
        elif data is None:
            buf.write('$-1\r\n')
        else:
            raise CommandError('Unrecognized type: %s' % type(data))