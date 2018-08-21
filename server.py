from gevent.pool import Pool
from gevent.server import StreamServer

from collections import namedtuple

import protocolHandler as pH
import logging

logger = logging.getLogger(__name__)

class CommandError(Exception): pass
class Disconnect(Exception): pass

Error = namedtuple('Error', ('message',))

class Server(object):
    def __init__(self, host='127.0.0.1', port= 31337, max_clients=64):
        self._pool = Pool(max_clients)
        self._server = StreamServer((host, port), self.connection_handler, spawn = self._pool)
        self._protocol = pH.ProtocolHandler()
        self._kv = {}
        self._commands = self.get_commands()

    def connection_handler(self, conn, address):
        logger.info('Connection received: %s:%s' % address)
        socket_file = conn.makefile('rwb')

        while True:
            try:
                data = self._protocol.handle_request(socket_file)
            except Disconnect:
                logger.info('Client went away: %s:%s' % address)
                break

            try:
                resp = self.get_response(data)
            except CommandError as exc:
                logger.exception('Command error')
                resp = Error(exc.args[0])
            
            self._protocol.write_response(socket_file, resp)

    def get_commands(self):
        return {
            b'GET' : self.get,
            b'SET' : self.set,
            b'DELETE' : self.delete,
            b'FLUSH' : self.flush,
            b'MGET' : self.mget,
            b'MSET' : self.mset,
        }

    def get_response(self, data):
        if not isinstance(data, list):
            try:
                data = data.split()
            except:
                raise CommandError('Request must be list or simple string.')

        if not data:
            raise CommandError('Missing command.')

        command = data[0].upper()

        if command not in self._commands:
            raise CommandError('Unrecognized command: %s' % command)
        else:
            logger.debug('Received %s', command)

        return self._commands[command](*data[1:])

    def get(self, key):
        return self._kv.get(key)
    
    def set(self, key, value):
        self._kv[key] = value

    def delete(self, key):
        if key in self._kv:
            del self._kv[key]
            return 1
        return 0

    def flush(self):
        kvlen = len(self._kv)
        self._kv.clear()
        return kvlen

    def mget(self, *keys):
        return [self._kv.get(key) for key in keys]

    def mset(self, *items):
        data = zip(items[::2], items[1::2])
        for key, value in data:
            self._kv[key] = value
        return len(list(data))

    def run(self):
        self._server.serve_forever()


if __name__ == '__main__':
    from gevent import monkey; monkey.patch_all()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    Server().run()