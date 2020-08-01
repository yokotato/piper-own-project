#ライブラリをインポート
import numpy as np
import pandas as pd
import influxdb
import subprocess
import time
from datetime import datetime, timezone, timedelta
import picamera
import pymsteams
import RPi.GPIO as GPIO
from linenotipy import Line
from azure.iot.device import IoTHubDeviceClient, Message
CONNECTION_STRING = "HostName=<Your Azure IOT name>.azure-devices.net;DeviceId=raspberrypi;SharedAccessKey=<Your Own Shared Access Key>"
#MSG_TXT = "{\"temperature\": %.2f}"
MSG_TXT = "{\"temperature\":"

pins = {'pin_R':11, 'pin_G':12, 'pin_B':13}  # pins is a dict
BtnPin = 15    # pin15 --- button

GPIO.setmode(GPIO.BOARD)       # Numbers GPIOs by physical location
GPIO.setup(BtnPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)    # Set BtnPin's mode is input, and pull up to high level(3.3V)
for i in pins:
    GPIO.setup(pins[i], GPIO.OUT)   # Set pins' mode is output
    GPIO.output(pins[i], True) # Set pins to high(+3.3V) to off led
    
p_R = GPIO.PWM(pins['pin_R'], 2000)  # set Frequece to 2KHz
p_G = GPIO.PWM(pins['pin_G'], 2000)
p_B = GPIO.PWM(pins['pin_B'], 2000)

LEDcolor = 0xFFFFFF  #LED off
p_R.start(100)      # Initial duty Cycle = 0(leds off)
p_G.start(100)
p_B.start(100)

DIO = 22
CLK = 18
STB = 16

LSBFIRST = 0
MSBFIRST = 1

tmp = 0



def SendTapTime(tapdata):
    #today = datetime.datetime.fromtimestamp(time.time())
    #dataframe = pd.DataFrame({'TapTime': today.strftime('%Y/%m/%d %H:%M:%S'), 'Tap' : 1})
    dataframe = pd.DataFrame([{
    #dataframe = [{
        #"measurement" : "tap",
        #'tags' :{
        #    'col1':'col1',
        #    'col2':'col2',
        #    'col3':'col3',
        #    'col3':'col4',
        #},
        #"fields" :{
            "temperature" : tapdata,
            #"value" : "dummy",
        #},
        #'time': today.strftime('%Y/%m/%d %H:%M:%S'),
        "time" : datetime.now(timezone.utc),
    }])
    dataframe.set_index('time', inplace=True)
    print(dataframe)
    dbclient.write_points(dataframe, measurement ='tap', database="dbyok" , time_precision='s', protocol='json')
    return dbclient.query("select temperature from tap")


def _shiftOut(dataPin, clockPin, bitOrder, val):
    for i in range(8):
        if bitOrder == LSBFIRST:
            GPIO.output(dataPin, val & (1 << i))
        else:
            GPIO.output(dataPin, val & (1 << (7 -i)))
        GPIO.output(clockPin, True)
        time.sleep(0.000001)            
        GPIO.output(clockPin, False)
        time.sleep(0.000001)     

def sendCommand(cmd):
    GPIO.output(STB, False)
    _shiftOut(DIO, CLK, LSBFIRST, cmd)
    GPIO.output(STB, True)

def TM1638_init():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(DIO, GPIO.OUT)
    GPIO.setup(CLK, GPIO.OUT)
    GPIO.setup(STB, GPIO.OUT)
    sendCommand(0x8f)

def numberDisplay_dec(num):
    digits = [0x3f,0x06,0x5b,0x4f,0x66,0x6d,0x7d,0x07,0x7f,0x6f]
    integer = 0
    decimal = 0

    pro = int(num * 100)

    integer = int(pro / 100)
    decimal = int(pro % 100)

    sendCommand(0x40)
    GPIO.output(STB, False)
    _shiftOut(DIO, CLK, LSBFIRST, 0xc0)
    _shiftOut(DIO, CLK, LSBFIRST, digits[int(integer/10)])
    _shiftOut(DIO, CLK, LSBFIRST, 0x00)
    _shiftOut(DIO, CLK, LSBFIRST, digits[int(integer%10)] | 0x80)
    _shiftOut(DIO, CLK, LSBFIRST, 0x00)
    _shiftOut(DIO, CLK, LSBFIRST, digits[int(decimal/10)])
    _shiftOut(DIO, CLK, LSBFIRST, 0x00)
    _shiftOut(DIO, CLK, LSBFIRST, digits[int(decimal%10)])
    _shiftOut(DIO, CLK, LSBFIRST, 0x00)
    GPIO.output(STB, True)

def mapcol(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def setColor(col):   # For example : col = 0x112233
    R_val = (col & 0xFF0000) >> 16
    G_val = (col & 0x00FF00) >> 8
    B_val = (col & 0x0000FF) >> 0
    
    R_val = mapcol(R_val, 0, 255, 0, 100)
    G_val = mapcol(G_val, 0, 255, 0, 100)
    B_val = mapcol(B_val, 0, 255, 0, 100)
    
    p_R.ChangeDutyCycle(R_val)     # Change duty cycle
    p_G.ChangeDutyCycle(G_val)
    p_B.ChangeDutyCycle(B_val)



def send_confirmation_callback(message, result, user_context):
    print ( "IoT Hub responded to message with status: %s" % (result) )

def getTemperature():
    response = subprocess.check_output('/usr/local/bin/tempered', universal_newlines=True)
    temperature = response.split(" ")[3]
    return temperature

def CapPicture():
    width = 400
    height = 400
    photofilename = "./uploads/photo-yok.jpg"
    cam = picamera.PiCamera()
    cam.resolution = (width, height)
    cam.hflip = True
    cam.vflip = True
    cam.start_preview()
    time.sleep(2)
    cam.capture(photofilename)
    cam.stop_preview()
    cam.close()
    return photofilename

def SendLine(photofilename, temp):
    line = Line(token='<Your Own Line Token>')
    print(line.post(message="暑いよ〜" + str(temp) + " degree Celsius!!", imageFile=photofilename))
    return photofilename

def SendTeams(photofilename,temp):
    webhook_url = 'https://outlook.office.com/webhook/<Your MS-TEAMS Webhook ID>'
    myTeamsMessage = pymsteams.connectorcard(webhook_url)
    myTeamsMessage.text("It's too hot! "+temp+" degree Celsius!!")
    #myTeamsMessage.addImage("./uploads/photo-yok.jpg", ititle="This is hot place")
    myTeamsMessage.send()


try:
    TM1638_init()
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
    dbclient = influxdb.DataFrameClient(host=u'<Your influxDB address>', port=8086, username=u'admin', password=u'admin', database='dbyok')
    while True:
        inputValue = getTemperature()
        numberDisplay_dec(float(inputValue))
        if int(inputValue.replace('.','')) > 2900:
            print('Over 30 degree')
            LEDcolor=0  # LED on
            setColor(LEDcolor)
            photofile = CapPicture()
            print(SendLine(photofile,inputValue))
            print(SendTeams(photofile,inputValue))
        #msg_txt_formatted = MSG_TXT % (inputValue)
        #msg_txt_formatted = MSG_TXT + '"' + str(inputValue) + '"' + '}'
        msg_txt_formatted = MSG_TXT + str(inputValue) + '}'
        print(inputValue, msg_txt_formatted)
        message = Message(msg_txt_formatted)
        client.send_message(message)
        j=0
        while j<60:
            if GPIO.input(BtnPin) == GPIO.LOW and LEDcolor == 0: # Check whether the button is pressed.
                print ('Somebody hit the button, and led light turned off')
                LEDcolor = 0xFFFFFF   #LED off
                setColor(LEDcolor)
                #print(SendTapTime(inputValue))
            time.sleep(1)
            j+=1

except KeyboardInterrupt:
    p_R.stop()
    p_G.stop()
    p_B.stop()
    for i in pins:
        GPIO.output(pins[i], True)  # Turn off all leds
    GPIO.cleanup()
    pass
