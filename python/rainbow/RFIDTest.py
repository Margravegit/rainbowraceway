#!/usr/bin/python

print ("Importing libraries...")
import serial
import time
import binascii
import threading
import sys, select, os
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
type1Cards      = [] #R
type2Cards      = [] #G
type3Cards      = [] #B
#LEDS
LED_COUNT      = 24      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_MODE       = 0
LED_ON         = False
LED_COLOR_WIPE = Color(0,0,0)

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
				break
			time.sleep(wait_ms/1000.0)
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, 0)

#fades from black to single color in timelen seconds
def fadeInOut(strip, color, timelen, iterations):
	green =  float(color & 255)
	blue = float((color >> 8) & 255)
	red =   float((color >> 16) & 255)
	newRed = 0
	newBlue = 0
	newGreen = 0
	for j in range(iterations):
		for q in range((timelen*20)+1):
			if (LED_ON == False) or (LED_MODE != 6):
				break
			newRed = int(round(q*(red/(timelen*20)))) & 255
			newBlue = int(round(q*(blue/(timelen*20)))) & 255
			newGreen = int(round(q*(green/(timelen*20)))) & 255

			newColor = Color(newRed, newBlue, newGreen)			
		        for i in range(strip.numPixels()):
                		strip.setPixelColor(i, newColor)
		                strip.show()
	                time.sleep(0.05)
                for q in reversed(range((timelen*20)+1)):
                        if (LED_ON == False) or (LED_MODE != 6):
                                break
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
			break
		strip.show()
		time.sleep(wait_ms/1000.0)

#rainbow uniformly scattered across all pixels
def rainbowCycle(strip, wait_ms=20, iterations=5):
	for j in range(256*iterations):
		for i in range(strip.numPixels()):
			strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
		if LED_ON == False or LED_MODE != 4:
			break
		strip.show()
		time.sleep(wait_ms/1000.0)

#chase animation with rainbow colors
def theaterChaseRainbow(strip, wait_ms=50):
	for j in range(256):
		for q in range(3):
			for i in range(0, strip.numPixels(), 3):
				strip.setPixelColor(i+q, wheel((i+j) % 255))
			if LED_ON == False or LED_MODE != 5:
				break
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
	                rainbowCycle(strip)
		if LED_MODE == 5:
	                theaterChaseRainbow(strip)
		if LED_MODE == 6:
			fadeInOut(strip,LED_COLOR_WIPE,1,1)

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
  
def parseReaderMsg(buf):
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
			else:
				tmpCardID = binascii.hexlify(tmpData[11:len(tmpData)-1]) #Split the reader response and check card type
				if displayDebug:
					print "Msg = " + binascii.hexlify(tmpMsg) #All the message
					print "Len = " + str(tmpLen) #Len of the message data
					print "Dir = " + str(tmpDir) #Address of the reader
					print "Data = " + binascii.hexlify(tmpData) #message data
				print "CardID = " + tmpCardID
				if tmpCardID in type1Cards: #TYPE 1 CARD LOGIC - TODO
					print "Card type 1"
					LED_COLOR_WIPE = Color(0,0,150)
					LED_MODE = 1
					time.sleep(2)
				elif tmpCardID in type2Cards: #TYPE 2 CARD LOGIC - TODO
					print "Card type 2"
                                        LED_COLOR_WIPE = Color(150,0,150)
                                        LED_MODE = 1
					time.sleep(2)
				elif tmpCardID in type3Cards: #TYPE 3 CARDS LOGIC - TODO
					print "Card type 3"
                                        LED_COLOR_WIPE = Color(150,150,0)
                                        LED_MODE = 1
					time.sleep(2)
				else:
					print "Unknown card"
			_buffer = _buffer[tmpLen:]
			LED_MODE = 4
			i = -1
		i += 1


def clearScreen():
	print ("\n" * 100)

def showFunctions():
	global LED_COLOR_WIPE
	global LED_MODE

	print "Reader functions:"
	print "1: Connect to reader via USB"
	print "2: Reset Reader"
	print "3: Start Reading"
	print "9: Debug display: " +  str(displayDebug)
	print "0: Exit"
	print ("\n" * 2)

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

def readValidCardList():
	f = open("cardList.txt")
	next = f.readline()
	while next != "":
		_card = next.split(':')
		if _card[1] == '1\n':
			type1Cards.append(_card[0])
		if _card[1] == '2\n':
			type2Cards.append(_card[0])
		if _card[1] == '3\n':
			type3Cards.append(_card[0])

		next = f.readline()
	print "type 1 cards: " +  str(type1Cards)
	print "type 2 cards: " +  str(type2Cards)
	print "type 3 cards: " +  str(type3Cards)


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

