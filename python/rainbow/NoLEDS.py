
#!/usr/bin/python

import serial
import time
import binascii
import threading
import spidev
import sys
import select
import os
import random
from neopixel import *

#############
#global vars#
#############
#RFID
displayDebug     = False #Display reader response information
sleep_time       = 0.02 #Delay between reader commands
mode             = 0 #reader connection mode: 0= DISCONNECTED / 1 = USB / 2 = SERIAL UART
_buffer          = bytearray() #read buffer (4096)
#Card types
GreenShellCards		= [] #0
RedShellCards		= [] #1
BananaCards		= [] #2
MushroomCards		= [] #3
GoldMushroomCards	= [] #4
StarCards		= [] #5
AdminCards		= [] #6
BoltCards		= [] #7
s50ccCards		= [] #8
s100ccCards		= [] #9
s150ccCards		= [] #10
ColorCycleCards		= [] #11
#LEDS
LED_COUNT      = 180      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_MODE       = 0
LED_ON         = False
LED_COLOR_WIPE = Color(0,0,0)
#GAME
_curPowerup		= -1 #Current powerup (-1 for none)
_maxModeThrottle	= 0.2 #% of total power (0 - 1 range) determined by the race mode
_maxThrottle		= 1 #% of total power (0 - 1 range) determined by powerup

################
#POWERUP CONFIG#
################
GREEN_SHELL_DURATION	= 4
GREEN_SHELL_TIME_DOWN	= 0.2
GREEN_SHELL_TIME_UP	= 1
GREEN_SHELL_EFFECT	= 0.1
RED_SHELL_DURATION    = 6
RED_SHELL_TIME_DOWN   = 0.2
RED_SHELL_TIME_UP     = 1
RED_SHELL_EFFECT      = 0
BANANA_DURATION    = 6
BANANA_TIME_DOWN   = 1
BANANA_TIME_UP     = 1
BANANA_EFFECT      = 0.15
STAR_DURATION    = 10
STAR_TIME_DOWN   = 0.5
STAR_TIME_UP     = 1
STAR_EFFECT      = 15
BOLT_DURATION    = 3
BOLT_TIME_DOWN   = 0.2
BOLT_TIME_UP     = 0.5
BOLT_EFFECT      = 0.3
MUSHROOM_DURATION    = 2
MUSHROOM_TIME_DOWN   = 0.1
MUSHROOM_TIME_UP     = 1
MUSHROOM_EFFECT      = 50

##################
#READER FUNCTIONS#
##################
def initReaderUSB(): #Sets up the reader connected on USB Port
    try:
        global ser
        global mode
        ser = serial.Serial (port = "/dev/ttyUSB0", bytesize = 8, stopbits = 1, timeout = 0.1)
        ser.baudrate = 115200
        mode = 1
    except:
        try:
            input("Press ENTER to continue")
        except:
            pass

def resetReader(): #resets the reader
    ser.write(b'\xA0\x03\x01\x70\xEC')

def readContinuous(): #inventory mode (continuous read)
    ser.write(b'\xA0\x04\x01\x89\x01\xD1')

def startReading(): #Start reading in inventory mode
	while True:
		readContinuous()
		time.sleep(sleep_time)
		msg = ser.read(4096)
		parseReaderMsg(msg)
		if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
			line = raw_input()
			break

def parseSingleReaderMsg(_buffer): #Reads the card information from the reader
        if len(_buffer) == 0:
                return

        tmpDir = _buffer[0]
        tmpData = _buffer[3:-1]

        tmpCardID = binascii.hexlify(tmpData[11:len(tmpData) - 1])  # Split the rea$
        if tmpCardID in GreenShellCards:  # TYPE 0 CARD
            cardTypesFound[0] += 1
            lastCardType = 0
        elif tmpCardID in RedShellCards:  # TYPE 1 CARD
            cardTypesFound[1] += 1
            lastCardType = 1
        elif tmpCardID in BananaCards:  # TYPE 2 CARD
            cardTypesFound[2] += 1
            lastCardType = 2
        elif tmpCardID in MushroomCards:  # TYPE 3 CARD
            cardTypesFound[3] += 1
            lastCardType = 3
        elif tmpCardID in GoldMushroomCards:  # TYPE 4 CARD
            cardTypesFound[4] += 1
            lastCardType = 4
        elif tmpCardID in StarCards:  # TYPE 5 CARD
            cardTypesFound[5] += 1
            lastCardType = 5
        elif tmpCardID in AdminCards:  # TYPE 6 CARD
            cardTypesFound[6] += 1
            lastCardType = 6
        elif tmpCardID in BoltCards:  # TYPE 7 CARD
            cardTypesFound[7] += 1
            lastCardType = 7
        elif tmpCardID in s50ccCards: #TYPE 8 CARD
            cardTypesFound[8] += 1
            lastCardType = 8
        elif tmpCardID in s100ccCards: #TYPE 9 CARD
            cardTypesFound[9] += 1
            lastCardType = 9
        elif tmpCardID in s150ccCards: #TYPE 10 CARD
            cardTypesFound[10] += 1
            lastCardType = 10
	elif tmpCardID in ColorCycleCards: #COLOR CYCLE CARD TYPE 11
            cardTypesFound[11] += 1
            lastCardType = 11


        executeCardEffectON(lastCardType)

def parseReaderMsg(buf): #Reads the card information from the reader
	#total number of cards scanned of each type on the last round
	#if we read more than one type of card at the same time, we'll ignore everything
	cardTypesFound = [0,0,0,0,0,0,0,0,0,0,0,0]
	lastCardType		= -1
	global _buffer
	if len(buf) == 0:
		return
	_buffer += buf #append the new byte array to global parse buffer
	i = 0
	while (len(_buffer) > 0):
		bt = _buffer[i]
			
		if bt == 160: #Msg init - \xA0
			tmpLen = _buffer[i+1] + 2 
			tmpMsg = _buffer[:tmpLen]
			tmpDir = _buffer[i+2]
			tmpData = tmpMsg[3:tmpLen-1]

			if tmpLen == 12: #last part of msg: total number of tags identified in the last round
				totalCards = int(binascii.hexlify(tmpData[len(tmpData)-4:]))
				if totalCards > 0:
					#If the number of cards scanned of the last type doesn't match the total number of cards, we have too many types of cards
					if cardTypesFound[lastCardType] != totalCards:
						executeCardEffectON(lastCardType)
					else:
						executeCardEffectON(lastCardType)
			else:
				tmpCardID = binascii.hexlify(tmpData[11:len(tmpData)-1]) #Split the reader response and check card type
				if tmpCardID in GreenShellCards: #TYPE 0 CARD
					cardTypesFound[0] += 1
					lastCardType = 0
				elif tmpCardID in RedShellCards: #TYPE 1 CARD
					cardTypesFound[1] += 1
					lastCardType = 1
				elif tmpCardID in BananaCards: #TYPE 2 CARD
					cardTypesFound[2] += 1
					lastCardType = 2
				elif tmpCardID in MushroomCards: #TYPE 3 CARD
					cardTypesFound[3] += 1
					lastCardType = 3
				elif tmpCardID in GoldMushroomCards: #TYPE 4 CARD
					cardTypesFound[4] += 1
					lastCardType = 4
				elif tmpCardID in StarCards: #TYPE 5 CARD
					cardTypesFound[5] += 1
					lastCardType = 5
				elif tmpCardID in AdminCards: #TYPE 6 CARD
					cardTypesFound[6] += 1
					lastCardType = 6
				elif tmpCardID in BoltCards: #TYPE 7 CARD
					cardTypesFound[7] += 1
					lastCardType = 7
                                elif tmpCardID in s50ccCards: #TYPE 8 CARD
                                        cardTypesFound[8] += 1
                                        lastCardType = 8
                                elif tmpCardID in s100ccCards: #TYPE 9 CARD
                                        cardTypesFound[9] += 1
                                        lastCardType = 9
                                elif tmpCardID in s150ccCards: #TYPE 10 CARD
                                        cardTypesFound[10] += 1
                                        lastCardType = 10
                                elif tmpCardID in ColorCycleCards: #COLOR CYCLE CARD TYPE 11
                                        cardTypesFound[11] += 1
                                        lastCardType = 11
			_buffer = _buffer[tmpLen:]
			i = -1
		i += 1


def clearScreen(): #Prints a bunch of newlines to clear the terminal screen
        pass
def showFunctions(): #Shows the terminal interface
	option = input("Choose an option: ")
	return option

def readValidCardList(): #Parses the list of registered cards from the file cardList.txt
	f = open("/home/pi/rainbowraceway/python/rainbow/cardList.txt")
	next = f.readline()
	while next != "":
		_card = next.split(':')
		if _card[1] == '0\n':
			GreenShellCards.append(_card[0])
		if _card[1] == '1\n':
			RedShellCards.append(_card[0])
		if _card[1] == '2\n':
			BananaCards.append(_card[0])
		if _card[1] == '3\n':
			MushroomCards.append(_card[0])
		if _card[1] == '4\n':
			GoldMushroomCards.append(_card[0])
		if _card[1] == '5\n':
			StarCards.append(_card[0])
		if _card[1] == '6\n':
			AdminCards.append(_card[0])
		if _card[1] == '7\n':
			BoltCards.append(_card[0])
		if _card[1] == '8\n':
			s50ccCards.append(_card[0])
		if _card[1] == '9\n':
			s100ccCards.append(_card[0])
		if _card[1] == '10\n':
			s150ccCards.append(_card[0])
                if _card[1] == '11\n':
                        ColorCycleCards.append(_card[0])

		next = f.readline()

###############
#SPI FUNCTIONS#
###############
def SPI_init(): #Initializes the SPI pins
	spi.open(0, 0)
	spi.max_speed_hz = 10000

# Split an integer input into a two byte array to send via SPI
def SPI_write_pot(input):
	msb = input >> 8
	lsb = input & 0xFF
	resp = spi.xfer([msb,lsb])

# Sets the maximum throttle between 0 and 1 (0-100%)	
def setThrottle(throttle):
	global _maxThrottle
	_maxThrottle = throttle
	val = throttle
	SPI_write_pot(int(val*255))
	
#Interpolates the pot resistor value between two values in specified amount of time
def potFromTo(initvalue, endvalue, duration):
	global _maxModeThrottle
	numsteps = duration / 0.05
	tinit = initvalue*_maxModeThrottle
	tend = endvalue*_maxModeThrottle
	increment = (tend-tinit)/numsteps
	curvalue = tinit
	steps = 1
	while steps<numsteps:
		curvalue = curvalue + increment
		steps = steps + 1
		setThrottle(curvalue)
		time.sleep(0.05)
	curvalue = tend
	setThrottle(curvalue)

##################
##GAME FUNCTIONS##
##################
def executeCardEffectON(cardType):
    global _curPowerup
    global _maxModeThrottle
    global _maxThrottle

    #-1: No powerup
    #0: GREEN SHELL
    global GREEN_SHELL_DURATION
    global GREEN_SHELL_TIME_DOWN
    global GREEN_SHELL_TIME_UP
    global GREEN_SHELL_EFFECT
    #1: RED SHELL
    global RED_SHELL_DURATION
    global RED_SHELL_TIME_DOWN
    global RED_SHELL_TIME_UP
    global RED_SHELL_EFFECT
    #2: BANANA
    global BANANA_DURATION
    global BANANA_TIME_DOWN
    global BANANA_TIME_UP
    global BANANA_EFFECT
    #5: STAR
    global STAR_DURATION
    global STAR_TIME_DOWN
    global STAR_TIME_UP
    global STAR_EFFECT
    #7: LIGHTNING BOLT
    global BOLT_DURATION
    global BOLT_TIME_DOWN
    global BOLT_TIME_UP
    global BOLT_EFFECT
    #3: MUSHROOM
    global MUSHROOM_DURATION
    global MUSHROOM_TIME_DOWN
    global MUSHROOM_TIME_UP
    global MUSHROOM_EFFECT
    if _curPowerup == cardType:
        return

    #MAIN POWERUP LOGIC GOES HERE
    if cardType == 0:
        if _curPowerup in [-1,3,4]:
            #Won't count while affected by other effects, except mushrooms (overwrites mushroom effects)
            _curPowerup = cardType
            #Stop other timer threads if there are any in effect - TO DO
            tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(GREEN_SHELL_DURATION,)) #Set timer thread
            tmr.start() #Start timer thread
            potFromTo(1, GREEN_SHELL_EFFECT, GREEN_SHELL_TIME_DOWN) #set pot resistance
    elif cardType == 1:
        if _curPowerup in [-1,3,4]:
            _curPowerup = cardType
            tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(RED_SHELL_DURATION,))
            tmr.start()
            potFromTo(1, RED_SHELL_EFFECT, RED_SHELL_TIME_DOWN) #set pot resistance
    elif cardType == 2:
        if _curPowerup in [-1, 3, 4]:
            _curPowerup = cardType
            tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(BANANA_DURATION,))
            tmr.start()
            potFromTo(1, BANANA_EFFECT, BANANA_TIME_DOWN)  # set pot resistance
    elif cardType == 3:
        if _curPowerup in [-1, 3, 4]:
            _curPowerup = cardType
            tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(MUSHROOM_DURATION,))
            tmr.start()
            potFromTo(1, MUSHROOM_EFFECT, MUSHROOM_TIME_DOWN)  # set pot resistance
    elif cardType == 4:
        _curPowerup = cardType
        tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(10,))
        tmr.start()
    elif cardType == 5:
        _curPowerup = cardType
        tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(STAR_DURATION,))
        tmr.start()
        potFromTo(1, STAR_EFFECT, STAR_TIME_DOWN)
    elif cardType == 6:
        pass
    elif cardType == 7:
        if _curPowerup in [-1, 3, 4]:
            _curPowerup = cardType
            #Stop other timer threads if there are any in effect - TO DO
            tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(BOLT_DURATION,)) #Set timer thread
            tmr.start() #Start timer thread
            potFromTo(1, BOLT_EFFECT, BOLT_TIME_DOWN) #set pot resistance
    elif cardType == 8: #50cc speed
        _maxModeThrottle = 0.04
        setThrottle(_maxModeThrottle)
    elif cardType == 9: #100cc speed
        _maxModeThrottle = 0.3
        setThrottle(_maxModeThrottle)
    elif cardType == 10: #150cc speed
        _maxModeThrottle = 0.8
        setThrottle(_maxModeThrottle)

def executeCardEffectOFF(cardType):
    global _maxModeThrottle
    global _maxThrottle

    # -1: No powerup
    # 0: GREEN SHELL
    global GREEN_SHELL_DURATION
    global GREEN_SHELL_TIME_DOWN
    global GREEN_SHELL_TIME_UP
    global GREEN_SHELL_EFFECT
    # 1: RED SHELL
    global RED_SHELL_DURATION
    global RED_SHELL_TIME_DOWN
    global RED_SHELL_TIME_UP
    global RED_SHELL_EFFECT
    # 2: BANANA
    global BANANA_DURATION
    global BANANA_TIME_DOWN
    global BANANA_TIME_UP
    global BANANA_EFFECT
    # 5: STAR
    global STAR_DURATION
    global STAR_TIME_DOWN
    global STAR_TIME_UP
    global STAR_EFFECT
    # 7: LIGHTNING BOLT
    global BOLT_DURATION
    global BOLT_TIME_DOWN
    global BOLT_TIME_UP
    global BOLT_EFFECT
    #3: MUSHROOM
    global MUSHROOM_DURATION
    global MUSHROOM_TIME_DOWN
    global MUSHROOM_TIME_UP
    global MUSHROOM_EFFECT

    #MAIN POWERUP DEACTIVATION LOGIC GOES HERE
    if cardType == 0:
        potFromTo(_maxThrottle,1,GREEN_SHELL_TIME_UP)
    elif cardType == 1:
        potFromTo(_maxThrottle,1,RED_SHELL_TIME_UP)
    elif cardType == 2:
        potFromTo(_maxThrottle,1, BANANA_TIME_UP)
    elif cardType == 3:
        potFromTo(_maxThrottle,1, MUSHROOM_TIME_UP)
    elif cardType == 5:
	potFromTo(_maxThrottle,1,STAR_TIME_UP)
    elif cardType == 7:
        potFromTo(_maxThrottle,1, BOLT_TIME_UP)

def powerupTimer(sec):
    global _curPowerup
    time.sleep(sec)
    executeCardEffectOFF(_curPowerup)
    _curPowerup = -1


######
#MAIN#
######
validOptions = [0, 1, 2, 3, 9]
readValidCardList()

if __name__ == '__main__':
	# Create NeoPixel object with appropriate configuration.
	strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)

	#init SPI interface
	spi = spidev.SpiDev()
	SPI_init()

	setThrottle(_maxModeThrottle)


#	serial = serial.Serial(port='COM5', bytesize=8, stopbits=1, timeout=0.05)
 #       serial.baudrate = 115200

     
#            threading.Timer(2,parseSingleReaderMsg).start()
#            Y.startRealtimeMode() 
	if not "-noautorun" in sys.argv:
		#while True:
		initReaderUSB()
		resetReader()
		startReading()

# while True:
#	clearScreen()
#	usrOption = showFunctions()
#	if (usrOption > 1) and (mode == 0) and (usrOption in validOptions):
#		try:
#			input("Press ENTER to continue")
#		except:
#			pass
#	elif usrOption == 1:
#		initReaderUSB()
#		LED_MODE = 0
#		time.sleep(1)		
#	elif usrOption == 2:
#		resetReader()
#	elif usrOption == 3:
#		startReading()
#	elif usrOption == 0:
#		stopLEDStrip()
#		break
#	elif usrOption == 9:
#		displayDebug = not displayDebug
#	elif not (usrOption in validOptions):
#		try:
#			input("Press ENTER to continue")
#		except:
#			pass
