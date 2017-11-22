# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

import binascii
import struct


class Packet:

    __slots__ = (
        'type',
        'size',
        'crcsum',
        'flags',
        'is_text',
        'payload', 
        'text'
    )

    def __str__(self):
        result = ['Packet: (']
        for k in self.__slots__:
            result.append('    %s: %s' % (k, getattr(self, k)))
        result.append(")")
        return "\n".join(result)

    def __init__(self):
        self.type = None
        self.size = None
        self.crcsum = None
        self.flags = None
        self.is_text = None
        self.payload = None
        self.text = None


class Protocol:

    HEADER_PROTOCOL_MARK = 0xA0
    HEADER_SIZE = 8
    TEXT_FLAG = 0x01
    TEXT_ENCODING = 'utf-8'

    @staticmethod
    def pack(type_, msg):
        textmessage, msgtype = False, type(msg)
        flags = 0
        if msgtype is str:
            flags = flags | Protocol.TEXT_FLAG
            binmsg = msg.encode('utf-8')
        elif msgtype is bytes:
            binmsg = msg
        else:
            raise TypeError

        crcsum = binascii.crc32(binmsg)
        return struct.pack('!BBHI{}s'.format(len(binmsg)),
                           Protocol.HEADER_PROTOCOL_MARK | flags,
                           type_,
                           len(binmsg),
                           crcsum,
                           binmsg)

    @staticmethod
    def unpack_header(bytes_):
        assert len(bytes_) == Protocol.HEADER_SIZE
        head, type_, size, crcsum = struct.unpack('!BBHI', bytes_)
        assert head & 0xF0 == Protocol.HEADER_PROTOCOL_MARK
        flags = head & 0x0F
        return flags, type_, size, crcsum

    @staticmethod
    def unpack_payload(size, bytes_):
        assert len(bytes_) >= size
        return struct.unpack('!{}s'.format(size), bytes_[:size])[0]


class ProtocolReader():

    class Status:

        def __init__(self, outer=None):
            self.outer = outer

        def process_buffer(self):
            raise NotImplementedError

        def status(self, status):
            self.outer.status, status.outer = status, self.outer
            status.process_buffer()

    class HeaderStatus(Status):

        def process_buffer(self):
            if len(self.outer.buffer) >= Protocol.HEADER_SIZE:
                flags, type_, size, crcsum = Protocol.unpack_header(
                    self.outer.buffer[:Protocol.HEADER_SIZE]
                )
                del self.outer.buffer[:Protocol.HEADER_SIZE]
                packet = Packet()
                packet.type = type_
                packet.size = size
                packet.flags = flags
                packet.crcsum = crcsum
                packet.is_text = packet.flags & Protocol.TEXT_FLAG
                self.status(ProtocolReader.PacketStatus(packet))

    class PacketStatus(Status):

        def __init__(self, packet):
            super().__init__()
            self.packet = packet

        def process_buffer(self):
            size = self.packet.size
            if len(self.outer.buffer) >= size:
                payload = Protocol.unpack_payload(size, self.outer.buffer)
                del self.outer.buffer[:size]
                assert binascii.crc32(payload) == self.packet.crcsum
                self.packet.payload = payload
                if self.packet.is_text:
                    self.packet.text = payload.decode(Protocol.TEXT_ENCODING)
                self.outer.callback(self.packet)
                self.packet = None
                self.status(ProtocolReader.HeaderStatus())

    def __init__(self, callback):
        self.buffer = bytearray()
        self.callback = callback
        self.status = ProtocolReader.HeaderStatus(self)

    def read(self, read):
        assert isinstance(read, bytes)
        self.buffer.extend(read)
        self.status.process_buffer()
