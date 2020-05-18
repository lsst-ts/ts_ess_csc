#*****************************************************************************
# RPi4 PoE Serial Hat classes
#
# File: serialhat.py
# Programmer: Garry Knight
# Date: 2020/05/05
#
#*****************************************************************************

from gpiozero import LED, Button
import serial
import time

SCRIPT_NAME = 'serialhat.py :'

# Hardware Definitions ......
# Define GPIO pin numbers for LTM module power control
U4_ON_PIN_NUM = 17
U5_ON_PIN_NUM = 23
U6_ON_PIN_NUM = 11
# Define GPIO pin numbers for LTM module DIN/DOUT pins
# Not implemented here, but provided for future use
U4_DOUT_PIN_NUM = 18
U4_TXRX_PIN_NUM = 3
U5_DIN_PIN_NUM = 24
U6_DIN_PIN_NUM = 7
#Define Fan locked rotor pin number
FAN_LOCKED_ROTOR_PIN_NUM = 2
fan_locked_rotor_pin = Button(FAN_LOCKED_ROTOR_PIN_NUM)

# Define RPi UART's
UART0 = '/dev/ttyS0'		# Use with Module1 (U4)
UART2 = '/dev/ttyAMA2'		# Use with Module2 (U5), channel 1
UART3 = '/dev/ttyAMA3'		# Use with Module2 (U5), channel 2
UART1 = '/dev/ttyAMA1'		# Use with Module3 (U6), channel 1
UART4 = '/dev/ttyAMA4'		# Use with Module3 (U6), channel 2

# Setup RPi control pins
power_pin_U4 = LED(U4_ON_PIN_NUM)
power_pin_U5 = LED(U5_ON_PIN_NUM)
power_pin_U6 = LED(U6_ON_PIN_NUM)
power_pin_U4.off()
power_pin_U5.off()
power_pin_U6.off()

txrx_pin_U4 = LED(U4_TXRX_PIN_NUM)
txrx_pin_U4.off()

# Class for RS-422 channel using module 1 (U4) ....
class serialhatrs422:
    
    def __init__(self, uart):
        self.serial_port = serial.Serial()
        self.port_name = uart
        power_pin_U4.off()
        print (SCRIPT_NAME, "Module 1 - Power OFF")
        txrx_pin_U4.off()
        print (SCRIPT_NAME, "Module 1 - Set to receive")
        try:
            self.serial_port = serial.Serial(uart)
            print (SCRIPT_NAME, "Module 1 =", uart)
        except:
            print (SCRIPT_NAME, "Module 1", uart, "Not connected")

    def powerOff(self):
        power_pin_U4.off()
        print (SCRIPT_NAME, "Module 1 Power = OFF")

    def powerOn(self):
        power_pin_U4.on()
        print (SCRIPT_NAME, "Module 1 Power = ON")

    def setTransmit(self):
        txrx_pin_U4.on()
        print (SCRIPT_NAME, "Module1 is ready for tranmsit")

    def setReceive(self):
        txrx_pin_U4.off()
        print (SCRIPT_NAME, "Module1 is ready for receive")

    def readLine(self):
        line = ""
        self.receive()
        line = self.serial_port.readline()
        return line

    def writeLine(self, txline, terminator = '\r\n'):
        line = txline + terminator
        self.setTransmit()
        self.serial_port.write(line.encode('utf-8'))
        print (SCRIPT_NAME, "Module 1 wrote ...", line)
        while (self.serial_port.out_waiting > 0):
            time.sleep(0.01)
        self.setReceive()

    def open(self, baud = 9600, timeout = 1.0, rtscts = 0):
        self.serial_port.baudrate = baud
        self.serial_port.timeout = timeout
        self.serial_port.rtscts = rtscts
        self.serial_port.write_timeout = 1.0
        try:
            self.serial_port.open()
            print (SCRIPT_NAME, self.port_name, "is open")
        except:
            print (SCRIPT_NAME, self.port_name, "Failed to open")


    def close(self):
        self.serial_port.close()
        print (SCRIPT_NAME, self.port_name, "closed")


# Class for RS-232 channels using module 2 or 3 (U5,6) ....
class serialhatrs232:

    def __init__(self, uart):
        self.serial_port = serial.Serial()
        self.port_name = uart
        try:
            self.serial_port = serial.Serial(uart)
            print (SCRIPT_NAME, "RS-232 Module =", uart)
        except:
            print (SCRIPT_NAME, "RS-232 Module =", uart, "Not connected")

    def powerOff(self):
        if self.port_name == UART2:
            power_pin_U5.off()
        if self.port_name == UART3:
            power_pin_U5.off()
        if self.port_name == UART1:
            power_pin_U6.off()
        if self.port_name == UART4:
            power_pin_U6.off()
        print (SCRIPT_NAME, self.port_name, "Power = OFF")

    def powerOn(self):
        if self.port_name == UART2:
            power_pin_U5.on()
        if self.port_name == UART3:
            power_pin_U5.on()
        if self.port_name == UART1:
            power_pin_U6.on()
        if self.port_name == UART4:
            power_pin_U6.on()
        print (SCRIPT_NAME, self.port_name, "Power = ON")

    def readLine(self):
        line = ""
        line = self.serial_port.readline()
        return line

    def writeLine(self, txline, terminator = '\r\n'):
        line = txline + terminator
        self.serial_port.write(line.encode('utf-8'))
        while (self.serial_port.out_waiting > 0):
            time.sleep(0.01)

    def open(self, baud = 9600, timeout = 1.0, rtscts = False):
        self.serial_port.baudrate = baud
        self.serial_port.timeout = timeout
        self.serial_port.rtscts = rtscts
        self.serial_port.write_timeout = 1.0
        try:
            self.serial_port.open()
        except:
            print (SCRIPT_NAME, self.port_name, "Failed to open")

    def close(self):
        self.serial_port.close()
        print (SCRIPT_NAME, self.port_name, "closed")


#---------------------------------------
# Fan Locked Rotor State Read
#---------------------------------------
def FanLockedRotorInput():
    if fan_locked_rotor_pin.is_active == True:
        print (SCRIPT_NAME, "Fan locked pin is HI")
    else:
        print (SCRIPT_NAME, "Fan locked pin is LO")
    return fan_locked_rotor_pin.is_active

#---------------------------------------

