import socket

from bxcommon.connections.abstract_connection import AbstractConnection
from bxcommon.connections.connection_type import ConnectionType
from bxcommon.utils import logger
from bxgateway import gateway_constants


class AbstractGatewayBlockchainConnection(AbstractConnection):
    CONNECTION_TYPE = ConnectionType.BLOCKCHAIN_NODE

    def __init__(self, sock, address, node, from_me=False):
        super(AbstractGatewayBlockchainConnection, self).__init__(sock, address, node, from_me)

        # Requires OS tuning (for Linux here; MacOS and windows require different commands):
        # echo 'net.core.wmem_max=16777216' >> /etc/sysctl.conf && sysctl -p
        # cat /proc/sys/net/core/wmem_max # to check
        previous_buffer_size = sock.socket_instance.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        try:
            sock.socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, gateway_constants.BLOCKCHAIN_SOCKET_SEND_BUFFER_SIZE)
            logger.info("Set socket send buffer size for blockchain connection to {}",
                        sock.socket_instance.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF))
        except Exception as e:
            logger.error("Could not set socket send buffer size for blockchain connection: {}", e)

        set_buffer_size = sock.socket_instance.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        if set_buffer_size != gateway_constants.BLOCKCHAIN_SOCKET_SEND_BUFFER_SIZE:
            logger.warn("Socket buffer size set was unsuccessful, and was instead set to {}. Reverting.",
                        set_buffer_size)
            sock.socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, previous_buffer_size)

        self.message_converter = None
        self.connection_protocol = None
        self.is_server = False

    def send_ping(self):
        self.enqueue_msg(self.ping_message)
        return gateway_constants.BLOCKCHAIN_PING_INTERVAL_S
