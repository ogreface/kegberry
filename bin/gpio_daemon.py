#!/usr/bin/python

'''
This is adapted from the adafruit kegbot sample code here: https://github.com/adafruit/Kegomatic
Also brings in a signal handler from SO, and uses the KegBot python message library. The polling code is pulled from KegBot/KegBoard
'''

import os
import time
import math
import logging
import RPi.GPIO as GPIO
import signal
import sys
from flowmeter import *
from serial_reader import SerialReader
from message import *
import requests

TAP1_DATA_PIN=23
TAP2_DATA_PIN=24
SERIAL_DEVICE="/tmp/ttysKEG2"

class GracefulKiller:
  kill_now = False
  def __init__(self):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

  def exit_gracefully(self,signum, frame):
    self.kill_now = True

def tapRunning(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if fm.enabled == True:
    fm.update(currentTime)

def tap2Running(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if fm2.enabled == True:
    fm2.update(currentTime)


def setupGPIO():
  #boardRevision = GPIO.RPI_REVISION
  GPIO.setmode(GPIO.BCM) # use real GPIO numbering
  GPIO.setup(TAP1_DATA_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
  GPIO.setup(TAP2_DATA_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
  GPIO.add_event_detect(TAP1_DATA_PIN, GPIO.RISING, callback=tapRunning, bouncetime=20) 
  GPIO.add_event_detect(TAP2_DATA_PIN, GPIO.RISING, callback=tap2Running, bouncetime=20)

def buildHello(serial):
  hello = HelloMessage()
  hello.SetValue('firmware_version',1)
  hello.SetValue('protocol_version',1)
  hello.SetValue('serial_number', serial)
  hello.SetValue('uptime_millis', 20)
  hello.SetValue('uptime_days', 20)
  return hello

def buildMeterStatus(name, ticks):
  status = MeterStatusMessage()
  status.SetValue('meter_name', name)
  status.SetValue('meter_reading', ticks) 
  return status

if __name__ == '__main__':
  killer = GracefulKiller()
  setupGPIO()

  # set up the flow meters
  fm = FlowMeter('metric', ["beer"])
  fm2 = FlowMeter('metric', ["root beer"])

  serial=SerialReader(SERIAL_DEVICE)
  print "Opening " + SERIAL_DEVICE
  serial.open()

  print "Waiting for event on 23/24"

  # main loop
  while True:
    if killer.kill_now:
        break 
    currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
   
    #Process any messages from the kegcore. Then generate and send any messages to kegcore.

    messages = serial.drain_messages()
    for message in messages:
        if isinstance(message, PingCommand):
            print "Got a ping message from kegcore"
            flow = buildHello("flow0")
            flow1 = buildHello("flow1")
            serial.write_message(flow)
#            serial.write_message(flow1)
        elif isinstance(message, SetOutputCommand):
            print "Received a set output command"
        elif isinstance(message, SetSerialNumberCommand):
            print "Received a set serial number command"
    


    if (fm.thisPour > 0.01 and currentTime - fm.lastClick > 250): # 10 seconds of inactivity causes a tweet
      tweet = "Someone just poured " + fm.getFormattedThisPour() + "  for " + str(fm.clickDelta) + " of " + fm.getBeverage() + " from the Adafruit kegomatic!" 
      lastTweet = int(time.time() * FlowMeter.MS_IN_A_SECOND)
      print tweet
      status = buildMeterStatus("left", fm.clickDelta)
      serial.write_message(status)

      url = "http://localhost/api/taps/1"  
      payload = {'ticks': fm.clickDelta, 'volume_ml': fm.thisPour * 1000, 'api_key': '8e9d45559c883413183a9e9d0d884027'}
      print payload
      r = requests.post(url, data=payload)
      print r.text
      fm.thisPour = 0.0

   
    if (fm2.thisPour > 0.01 and currentTime - fm2.lastClick > 250): # 10 seconds of inactivity causes a tweet
      tweet = "Someone just poured " + fm2.getFormattedThisPour() + " of " + fm2.getBeverage() + " from the Adafruit kegomatic!"
      lastTweet = int(time.time() * FlowMeter.MS_IN_A_SECOND)
      fm2.thisPour = 0.0
      print tweet
      
    # reset flow meter after each pour (2 secs of inactivity)
    if (fm.thisPour <= 0.23 and currentTime - fm.lastClick > 2000):
      fm.thisPour = 0.0
      
    if (fm2.thisPour <= 0.23 and currentTime - fm2.lastClick > 2000):
      fm2.thisPour = 0.0

fm.clear()
fm2.clear()
GPIO.cleanup()
sys.exit()



