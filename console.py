#!/usr/bin/env python3

#         Python Stream Deck Library
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

# Example script showing basic library usage - updating key images with new
# tiles generated at runtime, and responding to button state change events.

import os
import time
from time import sleep
import json

import threading
from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
import paho.mqtt.client as mqtt

import datetime
def formatStopWatch(deltaus):
    millis = int(deltaus.microseconds/1000)
    seconds=int(deltaus.seconds%60)
    minutes=int (deltaus.seconds/60)%60
    return '{0:02d}:{1:02d}.{2:03d}'.format(minutes, seconds, millis)
    
class myTimer(object):
    """A simple timer class"""
    
    def __init__(self):
        self.started= False
        self.splited = False
        print("Stopwatch initialized")
        pass
    
    def start(self):
        """Starts the timer"""
        self._start = datetime.datetime.now()
        self.started= True
        self.splited = False
        return self._start
    
    def stop(self):
        """Stops the timer.  Returns the time elapsed"""
        self._stop = datetime.datetime.now()
        self.started= False
        return (self._stop - self._start)
    
    def now(self):
        """Returns the current time with a message"""
        return datetime.datetime.now()
    
    def elapsed(self):
        """Time elapsed since start was called"""
        return (datetime.datetime.now() - self._start)
    
    def split(self):
        """Start a split timer"""
        now = datetime.datetime.now()
        if (self.splited):
            self._latLap = now - self._split_start
        else:
            self._latLap = now - self._start
        self._split_start = now
        self.splited = True
        return self._split_start
    
    def lastLap(self):
        return (self._latLap)


stopWatch = myTimer()
run = False

gateStates={}

client = mqtt.Client()

# Folder location of image assets used by this example.
ASSETS_PATH = os.path.join(os.path.dirname(__file__), "Assets")


def getSWKey (deck):
    return deck.key_count() - 4

def getTLKey (deck):
    return deck.key_count() - 5

# Generates a custom tile with run-time generated text and custom image via the
# PIL module.
def render_key_image(deck, icon_filename, font_filename, label_text):
    # Create new key image of the correct dimensions, black background.
    image = PILHelper.create_image(deck)

    # Resize the source image asset to best-fit the dimensions of a single key,
    # and paste it onto our blank frame centered as closely as possible.
    icon = Image.open(icon_filename).convert("RGBA")
    icon.thumbnail((image.width, image.height - 20), Image.LANCZOS)
    icon_pos = ((image.width - icon.width) // 2, 0)
    image.paste(icon, icon_pos, icon)

    # Load a custom TrueType font and use it to overlay the key index, draw key
    # label onto the image.
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_filename, 14)
    label_w, label_h = draw.textsize(label_text, font=font)
    label_pos = ((image.width - label_w) // 2, image.height - 20)
    draw.text(label_pos, text=label_text, font=font, fill="white")

    return PILHelper.to_native_format(deck, image)

# Returns styling information for a key based on its position and state.
def get_key_style(deck, key, state):
    # Last button in the example application is the exit button.
    exit_key_index = deck.key_count() - 1

    if key == exit_key_index:
        name = "exit"
        icon = "{}.png".format("Exit")
        font = "Roboto-Regular.ttf"
        label = "Bye" if state else "Exit"
    elif (key == exit_key_index-1):
        name = "stop"
        icon = "{}.png".format("Stop")
        font = "Roboto-Regular.ttf"
        label = "Stoped" if state else "Stop"
    elif (key == exit_key_index-2):
        name = "start"
        icon = "{}.png".format("Start")
        font = "Roboto-Regular.ttf"
        label = "Started" if state else "Start"
    elif (key == exit_key_index-3):
        name = "stopwatch"
        icon = "{}.png".format("Blank")
        font = "Roboto-Regular.ttf"
        label = "00:00.000" if state else "00:00.000"
    elif (key == exit_key_index-4):
        name = "laptime"
        icon = "{}.png".format("Blank")
        font = "Roboto-Regular.ttf"
        label = "00:00.000" if state else "00:00.000"
    else:
        name = "G{}".format(key+1)
        icon = "{}.png".format("Plugged" if ("G{}".format(key+1) in gateStates and gateStates["G{}".format(key+1)]!='disconnected') else "Unplugged")
        font = "Roboto-Regular.ttf"
        label = "Pressed!" if state else "Gate {}".format(key+1)

    return {
        "name": name,
        "icon": os.path.join(ASSETS_PATH, icon),
        "font": os.path.join(ASSETS_PATH, font),
        "label": label
    }


# Creates a new key image based on the key index, style and current key state
# and updates the image on the StreamDeck.
def update_key_image(deck, key, state):
    # Determine what icon and label to use on the generated key.
    key_style = get_key_style(deck, key, state)

    # Generate the custom key with the requested image and label.
    image = render_key_image(deck, key_style["icon"], key_style["font"], key_style["label"])

    # Update requested key with the generated image.
    deck.set_key_image(key, image)

def update_key_stopwatch_image(deck, key, state, msg):
    # Determine what icon and label to use on the generated key.
    key_style = get_key_style(deck, key, state)

    # Generate the custom key with the requested image and label.
    image = render_key_image(deck, key_style["icon"], key_style["font"], msg)

    # Update requested key with the generated image.
    deck.set_key_image(key, image)

# Prints key state change information, updates rhe key image and performs any
# associated actions when a key is pressed.
def key_change_callback(deck, key, state):
    global run
    key_style = get_key_style(deck, key, state)
    # Print new key state
    print("Deck {} Key {} = {}".format(deck.id(), key, state), flush=True)

    # Update the key image based on the new key state.
    update_key_image(deck, key, state)

    # Check if the key is changing to the pressed state.
    if state:
        if key_style["name"] == "start":
            if stopWatch.started:
                stopWatch.split()
            else:
                stopWatch.start()
                client.publish("/cmd", json.dumps({'cmd': 'step'}))
                msg = '------'
                update_key_stopwatch_image(deck, getTLKey(deck), False, msg)

        elif key_style["name"] == "stop":
            client.publish("/cmd", json.dumps({'cmd': 'init'}))
            if stopWatch.started:
                msg = formatStopWatch(stopWatch.stop())
                update_key_stopwatch_image(deck, getSWKey(deck), state, msg)
        # When an exit button is pressed, close the application.
        elif key_style["name"] == "exit":
            # Reset deck, clearing all button images.
            deck.reset()
            # Close deck handle, terminating internal worker threads.
            deck.close()
            run=False
    return

mainDeck = {}

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("/status")


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))
    if (msg.topic == '/status'):
        states = json.loads(msg.payload)
        for idx in range(len(states)):
            gateStates[states[idx]['id']]=states[idx]['state']
            update_key_image(mainDeck, idx, False)

if __name__ == "__main__":
    streamdecks = DeviceManager().enumerate()

    print("Found {} Stream Deck(s).\n".format(len(streamdecks)))

    for index, deck in enumerate(streamdecks):
        mainDeck=deck
        deck.open()
        deck.reset()

        print("Opened '{}' device (serial number: '{}')".format(deck.deck_type(), deck.get_serial_number()))

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect("localhost", 1883, 2)

        # Set initial screen brightness to 30%.
        deck.set_brightness(30)

        # Set initial key images.
        for key in range(deck.key_count()):
            update_key_image(deck, key, False)

        # Register callback function for when a key state changes.
        deck.set_key_callback(key_change_callback)

        run = True
        while run:
            client.loop()
            if (stopWatch.started==True):
                msg = formatStopWatch(stopWatch.elapsed())
                update_key_stopwatch_image(deck, getSWKey(deck), False, msg)
            if (stopWatch.splited==True):
                msg = formatStopWatch(stopWatch.lastLap())
                update_key_stopwatch_image(deck, getTLKey(deck), False, msg)
            sleep(0.05)

