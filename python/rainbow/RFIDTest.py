#!/usr/bin/python

print ("Importing libraries...")
import serial
import time
import binascii
import threading
import spidev
import sys
import select
import os
from neopixel import *

print ("Init global vars...")
#############
#global vars#
#############
#RFID
displayDebug     = False #Display reader response information
sleep_time       = 0.05 #Delay between reader commands
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
#LEDS
LED_COUNT      = 29      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_MODE       = 0
LED_ON         = False
LED_COLOR_WIPE = Color(0,0,0)
LED_COLOR_WIPE2 = Color(255,255,255)
#GAME
_curPowerup		= -1 #Current powerup (-1 for none)
_maxModeThrottle	= 1 #% of total power (0 - 1 range) determined by the race mode
_maxThrottle		= 1 #% of total power (0 - 1 range) determined by powerup

################
#POWERUP CONFIG#
################
GREEN_SHELL_DURATION	= 6
GREEN_SHELL_TIME_DOWN	= 0.2
GREEN_SHELL_TIME_UP	= 0.5
GREEN_SHELL_EFFECT	= 0.2

print ("setting up functions...")
#####################
#LED STRIP FUNCTIONS#
#####################
#scrolls a single color across all pixels
def colorWipe(strip, color, wait_ms=50):
	for i in range(strip.numPixels()):
		strip.setPixelColor(i, color)
		strip.show()
		time.sleep(wait_ms/1000.0)

#1-pixel on, 1-pixel off, scrolling across all pixels, single color
def theaterChase(strip, color, wait_ms=50, iterations=10):
	for j in range(iterations):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, color)
			strip.show()
			if LED_ON == False or LED_MODE != 2:
				return
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, 0)

#1-pixel on, 1-pixel off, scrolling across all pixels, single color
def theaterChase2(strip, color, color2, wait_ms=50, iterations=10):
	for j in range(iterations):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, color)
			strip.show()
			if LED_ON == False or LED_MODE != 7:
				return
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, color2)

#fades from black to single color in timelen seconds
def fadeInOut(strip, color, timelen, iterations):
	green =  float(color & 255)
	blue = float((color >> 8) & 255)
	red =   float((color >> 16) & 255)
	#newRed = 0
	#newBlue = 0
	#newGreen = 0
	for j in range(iterations):
		for q in range((int(timelen*20))+1):
			if (LED_ON == False) or (LED_MODE != 6):
				return
			newRed = int(round(q*(red/(timelen*20)))) & 255
			newBlue = int(round(q*(blue/(timelen*20)))) & 255
			newGreen = int(round(q*(green/(timelen*20)))) & 255

			newColor = Color(newRed, newBlue, newGreen)			
		        for i in range(strip.numPixels()):
                		strip.setPixelColor(i, newColor)
		                strip.show()
	                time.sleep(0.05)
                for q in reversed(range(int(timelen*20)+1)):
                        if (LED_ON == False) or (LED_MODE != 6):
                                return
                        newRed = int(round(q*(red/(timelen*20)))) & 255
                        newBlue = int(round(q*(blue/(timelen*20)))) & 255
                        newGreen = int(round(q*(green/(timelen*20)))) & 255

                        newColor = Color(newRed, newBlue, newGreen)
                        for i in range(strip.numPixels()):
                                strip.setPixelColor(i, newColor)
                                strip.show()
                        time.sleep(0.05)



def wheel(pos):
	if pos < 85:
		return Color(pos * 3, 255 - pos * 3, 0)
	elif pos < 170:
		pos -= 85
		return Color(255 - pos * 3, 0, pos * 3)
	else:
		pos -= 170
		return Color(0, pos * 3, 255 - pos * 3)

#rainbow fading on all pixels at once
def rainbow(strip, wait_ms=20, iterations=1):
	for j in range(256*iterations):
		for i in range(strip.numPixels()):
			strip.setPixelColor(i, wheel((i+j) & 255))
		if LED_ON == False or LED_MODE != 3:
			return
		strip.show()
		time.sleep(wait_ms/1000.0)

#rainbow uniformly scattered across all pixels
def rainbowCycle(strip, wait_ms=20, iterations=5, speed=1, size=256):
	for j in range(256*iterations):		
		for i in range(strip.numPixels()):
			strip.setPixelColor(i, wheel((int(i * size / strip.numPixels()) + (j*speed)) & 255))
		if LED_ON == False or LED_MODE != 4:
			return
		strip.show()
		time.sleep(wait_ms/1000.0)

#chase animation with rainbow colors
def theaterChaseRainbow(strip, wait_ms=50):
	for j in range(256):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, wheel((i+j) % 255))
			if LED_ON == False or LED_MODE != 5:
				return
			strip.show()
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, 0)

def startLEDStrip(strip):
	global LED_ON 
	global LED_MODE
	LED_ON = True
	while LED_ON == True:
		if LED_MODE == 0:
			colorWipe(strip, Color(0,0,0))
                if LED_MODE == 1:
	                colorWipe(strip, LED_COLOR_WIPE)  # Wipe
		if LED_MODE == 2:
	                theaterChase(strip, LED_COLOR_WIPE)  # Theater chase
		if LED_MODE == 3:
	                rainbow(strip)
		if LED_MODE == 4:
	                rainbowCycle(strip,20,5,5,1025)
		if LED_MODE == 5:
	                theaterChaseRainbow(strip)
		if LED_MODE == 6:
			fadeInOut(strip,LED_COLOR_WIPE,2,1)
		if LED_MODE == 7:
			theaterChase2(strip, LED_COLOR_WIPE, LED_COLOR_WIPE2)

def stopLEDStrip():
	global LED_ON
	LED_ON = False
	colorWipe(strip, Color(0,0,0))

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
		print "Cannot connect to reader. Make sure the pins are configured for USB and the reader is connected"
		try:
			input("Press ENTER to continue")
		except:
			pass

def resetReader(): #resets the reader
	ser.write(b'\xA0\x03\x01\x70\xEC')

def readContinuous(): #inventory mode (continuous read)
	ser.write(b'\xA0\x04\x01\x89\x01\xD1')

def startReading(): #Start reading in inventory mode
	global LED_MODE
	clearScreen()
	print("Reading tags... Press ENTER to stop")
	LED_MODE = 4
	while True:
		readContinuous()
		time.sleep(sleep_time)
		msg = ser.read(4096)
		parseReaderMsg(msg)
		if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
			line = raw_input()
			break
  
def parseReaderMsg(buf): #Reads the card information from the reader
	#total number of cards scanned of each type on the last round
	#if we read more than one type of card at the same time, we'll ignore everything
	cardTypesFound = [0,0,0,0,0,0,0]
	lastCardType		= -1
	global _buffer
	global LED_MODE
	global LED_COLOR_WIPE
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
					print("Total number of tags scanned in the last round: " + str(totalCards))
					if displayDebug:
						print("Card type list: " + str(cardTypesFound))
						print("Last card type found: " + str(lastCardType))
					#If the number of cards scanned of the last type doesn't match the total number of cards, we have too many types of cards
					if cardTypesFound[lastCardType] != totalCards:
						print("Too many types in one read")
						executeCardEffectON(lastCardType)
					else:
						print("Type check OK. Card type = ") + str(lastCardType)
						executeCardEffectON(lastCardType)
			else:
				tmpCardID = binascii.hexlify(tmpData[11:len(tmpData)-1]) #Split the reader response and check card type
				if displayDebug:
					print "Msg = " + binascii.hexlify(tmpMsg) #All the message
					print "Len = " + str(tmpLen) #Len of the message data
					print "Dir = " + str(tmpDir) #Address of the reader
					print "Data = " + binascii.hexlify(tmpData) #message data
				print "CardID = " + tmpCardID
				if tmpCardID in GreenShellCards: #TYPE 0 CARD
					print "Card type 0: GREEN SHELL"
					cardTypesFound[0] += 1
					lastCardType = 0
				elif tmpCardID in RedShellCards: #TYPE 1 CARD
					print "Card type 1: RED SHELL"
					cardTypesFound[1] += 1
					lastCardType = 1
				elif tmpCardID in BananaCards: #TYPE 2 CARD
					print "Card type 2: BANANA"
					cardTypesFound[2] += 1
					lastCardType = 2
				elif tmpCardID in MushroomCards: #TYPE 3 CARD
					print "Card type 3: MUSHROOM"
					cardTypesFound[3] += 1
					lastCardType = 3
				elif tmpCardID in GoldMushroomCards: #TYPE 4 CARD
					print "Card type 4: GOLD MUSHROOM"
					cardTypesFound[4] += 1
					lastCardType = 4
				elif tmpCardID in StarCards: #TYPE 4 CARD
					print "Card type 5: STAR"
					cardTypesFound[5] += 1
					lastCardType = 5
				elif tmpCardID in AdminCards: #TYPE 5 CARD
					print "Card type 6: ADMIN"
					cardTypesFound[6] += 1
					lastCardType = 6
				else:
					print "Unknown card type. Make sure to register new cards before using them"
			_buffer = _buffer[tmpLen:]
			i = -1
		i += 1


def clearScreen(): #Prints a bunch of newlines to clear the terminal screen
	print ("\n" * 100)

def showFunctions(): #Shows the terminal interface
	global LED_COLOR_WIPE
	global LED_MODE

	print "Reader functions:"
	print "1: Connect to reader via USB"
	print "2: Reset Reader"
	print "3: Start Reading"
	print "9: Debug display: " +  str(displayDebug)
	print "0: Exit"
	print ("\n" * 2)

	#Change LED color to show reader connection status
	LED_MODE = 6
	if mode == 0:
		print "Reader status: Disconnected"
		LED_COLOR_WIPE = Color(150,0,0)
	elif mode == 1:
		print "Reader status: Connected on TTYUSB0"
		LED_COLOR_WIPE = Color(0,150,0)
	elif mode == 2:
		print "Reader status: Connected on TTYS0"
		LED_COLOR_WIPE = Color(0,150,0)
	
	print ("\n" *2)
	option = input("Choose an option: ")
	return option

def readValidCardList(): #Parses the list of registered cards from the file cardList.txt
	f = open("/home/pi/rpi_ws281x/python/rainbow/cardList.txt")
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


		next = f.readline()
	print 'Green Shell cards: ' +  str(GreenShellCards)
	print 'Red Shell cards: ' +  str(RedShellCards)
	print 'Banana cards: ' +  str(BananaCards)
        print 'Mushroom cards: ' +  str(MushroomCards)
        print 'Gold mushroom cards: ' +  str(GoldMushroomCards)
	print 'Star cards: ' + str(StarCards)
        print 'Admin cards: ' +  str(AdminCards)

###############
#SPI FUNCTIONS#
###############
def SPI_init(): #Initializes the SPI pins
	spi = spidev.SpiDev()
	spi.open(0, 0)
	spi.max_speed_hz = 10000

# Split an integer input into a two byte array to send via SPI
def SPI_write_pot(input):
	msb = input >> 8
	lsb = input & 0xFF
	resp = spi.xfer([msb,lsb])
	#print str([msb,lsb]) + ' - ' + str(resp)

##################
##GAME FUNCTIONS##
##################
def executeCardEffectON(cardType):
	global LED_MODE
	global LED_COLOR_WIPE
	global LED_COLOR_WIPE2
	global _curPowerup

	#-1: No powerup
	#0: GREEN SHELL
	global GREEN_SHELL_DURATION
	global GREEN_SHELL_TIME_DOWN
	global GREEN_SHELL_TIME_UP
	global GREEN_SHELL_EFFECT
	#1: RED SHELL


	if _curPowerup == cardType:
		return

	#MAIN POWERUP LOGIC GOES HERE
	if cardType == 0:
		if _curPowerup in [-1,3,4]:
			print("GREEN SHELL ON")
			#Won't count while affected by other effects, except mushrooms (overwrites mushroom effects)
			_curPowerup = cardType
			#Lowers the throttle power - TO DO
			LED_COLOR_WIPE = Color(0,255,0)
			LED_COLOR_WIPE2 = Color(100,100,100)
			LED_MODE = 7 #Set the light effects
			#Stop other timer threads if there are any in effect - TO DO
			tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(GREEN_SHELL_DURATION,)) #Set timer thread
			tmr.start() #Start timer thread
	elif cardType == 1:
		print("RED SHELL ON")
		_curPowerup = cardType
		tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(6,))
		tmr.start()
	elif cardType == 2:
		print("BANANA ON")
		_curPowerup = cardType
		tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(3,))
		tmr.start()
	elif cardType == 3:
		print("MUSHROOM ON")
		_curPowerup = cardType
		tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(3,))
		tmr.start()
	elif cardType == 4:
		print("GOLD MUSHROOM ON")
		_curPowerup = cardType
		tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(10,))
		tmr.start()
	elif cardType == 5:
		print("STAR ON")
		_curPowerup = cardType
		tmr = threading.Thread(name='TIMER', target=powerupTimer, args=(10,))
		tmr.start()
	elif cardType == 6:
		print("ADMIN MODE ON")

def executeCardEffectOFF(cardType):
	global LED_MODE
#GreenShellCards         = 0
#RedShellCards           = 1
#BananaCards             = 2
#MushroomCards           = 3
#GoldMushroomCards       = 4
#StarCards               = 5
#AdminCards              = 6

        #MAIN POWERUP DEACTIVATION LOGIC GOES HERE
	if cardType == 0:
		print("GREEN SHELL OFF")
		LED_MODE = 4
	elif cardType == 1:
		print("RED SHELL OFF")
		LED_MODE = 4
	elif cardType == 2:
		print("BANANA OFF")
		LED_MODE = 4
	elif cardType == 3:
		print("MUSHROOM OFF")
		LED_MODE = 4
	elif cardType == 4:
		print("GOLD MUSHROOM OFF")
		LED_MODE = 4
	elif cardType == 5:
		print("STAR OFF")
		LED_MODE = 4

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
	# Intialize the library (must be called once before other functions).
	strip.begin()

	LED_COLOR_WIPE = Color(150,0,0)
	t = threading.Thread(name='LEDS', target=startLEDStrip, args=(strip,))
	t.start()

	#init SPI interface
	spi = spidev.SpiDev() #create SPI object
	spi.open(0,0) #open spi port 0, device 0

	if "-autorun" in sys.argv:
		#while True:
		initReaderUSB()
		resetReader()
		startReading()

while True:
	clearScreen()
	usrOption = showFunctions()
	if (usrOption > 1) and (mode == 0) and (usrOption in validOptions):
		print "ERROR: Connect to reader before this"
		try:
			input("Press ENTER to continue")
		except:
			pass
	elif usrOption == 1:
		initReaderUSB()
		LED_MODE = 0
		time.sleep(1)		
	elif usrOption == 2:
		resetReader()
	elif usrOption == 3:
		startReading()
	elif usrOption == 0:
		stopLEDStrip()
		break
	elif usrOption == 9:
		displayDebug = not displayDebug
	elif not (usrOption in validOptions):
		print "Incorrect option. Please try again"
		try:
			input("Press ENTER to continue")
		except:
			pass

