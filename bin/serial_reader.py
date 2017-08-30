import os
import serial
import select
import crc16
import struct
from message import *
from exceptions import *

KBSP_PREFIX = "KBSP v1:"
KBSP_PAYLOAD_MAXLEN = 112
KBSP_TRAILER = "\r\n"
KBSP_MAXLEN = KBSP_PAYLOAD_MAXLEN + len(KBSP_PREFIX) + len(KBSP_TRAILER)

class SerialReader:

  def __init__(self, device_path, speed=None):
    self.device_path = device_path
    self.incomplete_message = ""
    if not speed:
      speed = 115200
    self.speed = speed
    self.fd = None

  def __str__(self):
    return '<Kegboard path=%s speed=%s>' % (self.device_path, self.speed)

  def open(self):
    """Opens the backing device; must be called before any operations."""
    if self.fd:
      raise IOError('Already open!')
    if not os.path.isfile(self.device_path):
      self.fd = serial.Serial(self.device_path, self.speed, timeout=0.1)
      self.fd.flushInput()
    else:
      self.fd = open(self.device_path, 'rb')

  def close(self):
    """Closes the backing device."""
    self._assert_open()
    self.fd.close()
    self.fd = None
    self.incomplete_message = ""

  def close_quietly(self):
    """Similar to `close()`, but swallows any errors."""
    try:
      self.close()
    except IOError:
      pass

  def read_message_nonblock(self):
    """Immediately returns a message if available, None otherwise."""
    self._assert_open()

    while True:
      # Since we also support 'plain' fds, cannot use serial.inWaiting()
      rr, wr, er = select.select([self.fd], [], [], 0)
      if not rr:
        break

      c = self.fd.read(1)

      if self.incomplete_message is None:
        if c == '\n':
          # Reset.
          self.incomplete_message = ''
        continue

      self.incomplete_message += c

      if len(self.incomplete_message) >= KBSP_MAXLEN:
        # Packet too big; mark corrupt.
        self.incomplete_message = None

      elif not KBSP_PREFIX.startswith(self.incomplete_message[:len(KBSP_PREFIX)]):
        # Bad packet start; mark corrupt.
        self.incomplete_message = None

      elif self.incomplete_message[-2:] == KBSP_TRAILER:
        # Packet ended! Check it.
        bytes = self.incomplete_message
        self.incomplete_message = ''

        header = bytes[:12]
        payload = bytes[12:-4]
        trailer = bytes[-4:]
        crcd_bytes = bytes[:-2]
        checked_crc = crc16.crc16_ccitt(crcd_bytes)

        message_id, message_len = struct.unpack('<HH', header[8:])
        try:
          return get_message_by_id(message_id, payload)
        except UnknownMessageError, e:
          continue

      else:
        # Just continue.
        continue

    return None

  def drain_messages(self):
    """Immediately returns all available messages without blocking.

    This method is a convenience wrapper around `read_message_nonblock()`.
    """
    self._assert_open()
    ret = []
    while True:
      m = self.read_message_nonblock()
      if not m:
        break
      ret.append(m)
    return ret

  def read_message(self, timeout=None, interval=0.1):
    """Blocks until a message is available, returning it.

    If `timeout` given, the method will return None after this many seconds
    have elapsed without reading a message.
    """
    self._assert_open()
    elapsed = 0
    while True:
      m = self.read_message_nonblock()
      if m:
        return m

      elapsed += interval
      if timeout is not None and elapsed >= timeout:
        return None
      time.sleep(interval)

  def wait_for_ping(self, attempts=5):
    self.drain_messages()
    for i in xrange(attempts):
      self.ping()
      messages = [self.read_message(timeout=1)] + self.drain_messages()
      for message in messages:
        if isinstance(message, HelloMessage):
          return message

  def write_message(self, message):
    """Send a message to the device."""
    self._assert_open()
    return self.fd.write(message.ToBytes())

  def ping(self):
    return self.write_message(PingCommand())

  def set_serial_number(self, serial_number):
    command = SetSerialNumberCommand()
    command.SetValue('serial_number', serial_number)
    return self.write_message(command)

  def set_output(self, output_id, enable):
    command = SetOutputCommand()
    command.SetValue('output_id', int(output_id))
    command.SetValue('output_mode', int(enable))
    return self.write_message(command)

  def _assert_open(self):
    if not self.fd:
      raise IOError('Kegboard not open; call open() first.')
