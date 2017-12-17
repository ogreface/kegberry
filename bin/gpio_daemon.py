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

def postDrink(tap, clicks, volumeInL):
  url = "http://localhost/api/taps/" + str(tap)  
  payload = {'ticks': clicks, 'volume_ml': volumeInL * 1000, 'api_key': '8e9d45559c883413183a9e9d0d884027'}
  #print payload
  r = requests.post(url, data=payload)
 # print r.text
  try:
    r.raise_for_status()
  except requests.exceptions.HTTPError as e:
    print e

if __name__ == '__main__':
  killer = GracefulKiller()
  setupGPIO()

  # set up the flow meters
  fm = FlowMeter('metric', 14)
  fm2 = FlowMeter('metric', 14)

  print "Waiting for event on 23/24"

  # main loop
  while True:
    if killer.kill_now:
        break 
    currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
   
    if (fm.thisPour > 0.001 and currentTime - fm.lastClick > 3000): # 10 seconds of inactivity causes a tweet
      tweet = "Someone just poured " + fm.getFormattedThisPour() + "  on tap 1. " 
      print tweet
      postDrink(1, fm.clickDelta, fm.thisPour)
      fm.thisPour = 0.0

   
    if (fm2.thisPour > 0.001 and currentTime - fm2.lastClick > 3000): # 10 seconds of inactivity causes a tweet
      tweet = "Someone just poured " + fm.getFormattedThisPour() + "  on tap 2. " 
      print tweet
      postDrink(2, fm2.clickDelta, fm2.thisPour)
      fm2.thisPour = 0.0
      
    # reset flow meter after each pour (2 secs of inactivity)
   # if (fm.thisPour <= 0.05 and currentTime - fm.lastClick > 2000):
    #  fm.thisPour = 0.0
      
   # if (fm2.thisPour <= 0.05 and currentTime - fm2.lastClick > 2000):
    #  fm2.thisPour = 0.0

fm.clear()
fm2.clear()
GPIO.cleanup()
sys.exit()



