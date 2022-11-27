# -*- coding: ISO-8859-1 -*-
from __future__ import print_function
import os
import sys
import binascii
import re
import logging
from time import sleep
from threading import Thread

#####################################################

#  Set here, what you want to use
#  PLEASE ONLY USE 'true' or 'false'

#  MFSW (multi function steering wheel) will autodetect if it's installed

activate_rnse_tv_input = 'true'                     # If you don't have a multimedia interface, you can send the activation message for rns-e tv input with raspberry pi. Note: You'll need fbas or rgbs video pinned into 32 pin rns-e plug.
read_and_set_time_from_dashboard = 'true'           # Read the date and the time from dashboard. Useful if the raspberry pi doesn't have internet connection in the car.
control_pi_by_rns_e_buttons = 'true'                # Use rns-e buttons to control the raspberry pi. Note: You'll need to have "pynput" installed. You can install pynput with these commands: "pip3 install pynput" and "sudo pip3 install pynput".
reversecamera_by_reversegear = 'false'              # Use a hdmi input connected to the raspberry pi as reversecamera. Example: HDMI to CSI-2 Adapter Board.
reversecamera_turn_off_delay = '5'                  # Delay to turn off the reversecamera in seconds. Useful in parking situations.
send_values_to_dashboard = 'true'    #
send_oap_api_mediadata_to_dashboard = 'true'
clear_fis_if_media_is_paused = 'true'               # Show blank 1st and 2nd line fis/dis if media is paused. If this is set to 'false' the media will still show/scroll.
toggle_values_by_rnse_longpress = 'true'            # This will replace the normal rns-e up / rns-e down longpress to toggle values for 1st and 2nd line dis/fis. See: toggle_fis1 and toggle_fis2 below.
shutdown_by_ignition_off = 'false'                  # Shutdown the raspberry pi, if the ignition went off.
shutdown_by_pulling_key = 'false'                   # Shutdown the raspberry pi, if the they key got pulled.
shutdown_delay = '5'                                # Shutdown delay in seconds. Used for "shutdown_by_ignition_off" and "shutdown_by_pulling_key".

# 0 = blank line, 1 = title, 2 = artist, 3 = album, 4 = song position, 5 = song duration, 6 = speed, 7 = rpm, 8 = coolant, 9 = cpu/temp
toggle_fis1 = 1  # 1st line dis/fis
toggle_fis2 = 4  # 2nd line dis/fis

#####################################################


# Declare variables
FIS1 = '265'  # standard can id for first line dis/fis if no carmodel is detected
FIS2 = '267'  # standard can id for second line dis/fis if no carmodel is detected
speed = ''
rpm = ''
coolant = ''
playing = ''
position = ''
source = ''
title = ''
artist = ''
album = ''
duration = ''
global begin1
global eind1
begin1 = -1
eind1 = 7
global begin2
global eind2
begin2 = -1
eind2 = 7
pause_fis1 = False
pause_fis2 = False


logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-9s) %(message)s', )


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# install python-can if the module was not found.
try:
    import can
except ModuleNotFoundError:
    eprint('python-can is not installed - installing now (internet connection required')
    os.system('pip3 install python-can')
    os.system('sudo pip3 install python-can')
    eprint('python-can successfully installed - restarting script')
    os.execv(sys.executable, ['python3'] + sys.argv)

# install psutil if the module was not found. Needed to show raspberry pi cpu usage in %
if send_values_to_dashboard == 'true':
    try:
        import psutil
    except ModuleNotFoundError:
        eprint('psutil is not installed - installing now (internet connection required')
        os.system('pip3 install psutil')
        os.system('sudo pip3 install psutil')
        eprint('psutil successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)

# install pynput if the module was not found
if control_pi_by_rns_e_buttons == 'true':
    try:
        from pynput.keyboard import Key, Controller
    except ModuleNotFoundError:
        eprint('pynput is not installed - installing now (internet connection required')
        os.system('pip3 install pynput')
        os.system('sudo pip3 install pynput')
        eprint('pynput successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)
    keyboard = Controller()

# install picamera if the module was not found and deactivate camera functions if there is an error importing picamera - script doesn't crash then
if reversecamera_by_reversegear == 'true':
    try:
        from picamera import PiCamera
    except ModuleNotFoundError as e:
        eprint('picamera ist not installed - installing now (internet connection required')
        os.system('pip3 install picamera')
        os.system('sudo pip3 install picamera')
        eprint('picamera successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)
    except ImportError as e:
        reversecamera_by_reversegear = 'false'
        pass
    try:
        camera = PiCamera()
    except Exception as e:
        # eprint("camera is not connected or has problems - disabling all reversecamera features")
        reversecamera_by_reversegear = 'false'  # deactivate reversecamera features if the camera is not working
        pass

# try to import oap api if user has activated this feature
if send_oap_api_mediadata_to_dashboard == 'true':
    try:
        import common.Api_pb2 as oap_api
        from common.Client import Client, ClientEventHandler
    except ImportError as e:  # disable oap api features if import didn't worked
        show_music_title_in_fis = 'false'
        eprint('import from oap api failed - disabling oap api features')
        pass

# from oap api "MediaData.py" to read media metadata (title, artist, album, position, duration)
class read_song_infos_from_oap_api(ClientEventHandler):

    def on_hello_response(self, client, message):
        print(
            "received hello response, result: {}, oap version: {}.{}, api version: {}.{}"
            .format(message.result, message.oap_version.major,
                    message.oap_version.minor, message.api_version.major,
                    message.api_version.minor))

        set_status_subscriptions = oap_api.SetStatusSubscriptions()
        set_status_subscriptions.subscriptions.append(
            oap_api.SetStatusSubscriptions.Subscription.MEDIA)
        client.send(oap_api.MESSAGE_SET_STATUS_SUBSCRIPTIONS, 0,
                    set_status_subscriptions.SerializeToString())

    def on_media_status(self, client, message):
        global playing
        global position
        global source
        playing = message.is_playing
        position = message.position_label
        source = message.source
        # print(playing)
        # print(source)
        # print(position)

    def on_media_metadata(self, client, message):
        global title
        global artist
        global album
        global duration
        title = message.title
        artist = message.artist
        album = message.album
        duration = message.duration_label
        # print(title)
        # print(artist)
        # print(album)
        # print(duration)


def main():
    print('In Main')
    client = Client("media data example")
    event_handler = read_song_infos_from_oap_api()
    client.set_event_handler(event_handler)
    client.connect('127.0.0.1', 44405)
    active = True
    while active:
        try:
            active = client.wait_for_message()
        except KeyboardInterrupt:
            break
    client.disconnect()

# read on canbus and react to defined messages
def read_on_canbus():
    can_interface = 'can0'
    bus = can.interface.Bus(can_interface, bustype='socketcan')
    message = bus.recv()

    # eprint('In Dumpcan')
    try:
        tmset = 0
        carmodel = ''
        car_model_set = 0
        tv_mode_active = 1
        mfsw_detected = 0
        press_mfsw = 0
        up = 0
        down = 0
        select = 0
        back = 0
        nextbtn = 0
        prev = 0
        setup = 0  
        gear = 0
        global toggle_fis1
        global toggle_fis2
        global speed
        global rpm
        global coolant

        global begin1
        global eind1
        global pause_fis1
        global begin2
        global eind2
        global pause_fis2


        regel2 = ''
        label2 = ''
        for message in bus:
            canid = str(hex(message.arbitration_id).lstrip('0x').upper())
            msg = binascii.hexlify(message.data).decode('ascii').upper()

            # print('In read_from_canbus')

# read ignition message, or pulling key message to shut down the raspberry pi
            if canid == '271' or canid == '2C3':
                if shutdown_by_ignition_off == 'true' or shutdown_by_pulling_key == 'true':
                    if msg[0:2] == '11' and shutdown_by_ignition_off == 'true':
                        # eprint("ignition off message detected - system will shutdown in", shutdown_delay, "seconds")
                        sleep(int(shutdown_delay))  # defined delay to shutdown the pi
                        # eprint("system is shutting down now")
                        os.system('sudo shutdown -h now')
                    elif msg[0:2] == '10' and shutdown_by_pulling_key == 'true':
                        # eprint("pulling key message detected - system will shutdown in", shutdown_delay, "seconds")
                        sleep(int(shutdown_delay))  # defined delay to shutdown the pi
                        # eprint("system is shutting down now")
                        os.system('sudo shutdown -h now')

# read reverse gear message
            if canid == '351':
                global reversecamera_by_reversegear
                if reversecamera_by_reversegear == 'true':  # read reverse gear message and start reversecamera
                    if msg[0:2] == '00' and gear == 1:
                        gear = 0
                        #eprint("forward gear engaged - stopping reverse camera with", reversecamera_turn_off_delay, "seconds delay")
                        sleep(int(reversecamera_turn_off_delay))  # turn camera off with 5 seconds delay
                        try:
                            camera.stop_preview()
                        except Exception:
                            reversecamera_by_reversegear = 'false'  # deactivate reversecamera features if the camera is not working
                    elif msg[0:2] == '02' and gear == 0:
                        gear = 1
                        #eprint("reverse gear engaged - starting reverse camera")
                        try:
                            camera.start_preview()
                        except Exception:
                            reversecamera_by_reversegear = 'false'  # deactivate reversecamera features if the camera is not working
                    print(reversecamera_by_reversegear)

# read speed
                if toggle_fis1 == 6 or toggle_fis2 == 6:
                    msg = re.sub('[\\s+]', '', msg)
                    speed1 = msg[2:4]
                    speed2 = msg[4:6]
                    speed = '%s%s' % (speed2, speed1)
                    speed = int(speed, 16)
                    speed /= 200
                    speed = round(speed)
                    speed = str(speed)

# read rpm
            if canid == '353' or canid == '35B':
                if toggle_fis1 == 7 or toggle_fis2 == 7:
                    msg = re.sub('[\\s+]', '', msg)
                    rpm1 = msg[2:4]
                    rpm2 = msg[4:6]
                    rpm = '%s%s' % (rpm2, rpm1)
                    rpm = int(rpm, 16)
                    rpm /= 4
                    rpm = round(rpm)
                    rpm = str(rpm)

# read coolant temperature
                if toggle_fis1 == 8 or toggle_fis2 == 8:
                    msg = re.sub('[\\s+]', '', msg)
                    coolant = msg[6:8]
                    coolant = int(coolant, 16)
                    coolant = (coolant * 0.75) - 48
                    coolant = round(coolant)
                    coolant = str(coolant)

# read RNS-E button presses to control Raspberry Pi/OpenAuto Pro
            if canid == '461':
                if control_pi_by_rns_e_buttons == 'true':  # read can messages from rns-e button presses
                    if msg == '373001004001':
                        keyboard.press('1')
                        keyboard.release('1')
                        # eprint('RNS-E: wheel button scrolled LEFT - Keyboard: "1" - OpenAuto: "Scroll left"')

                    elif msg == '373001002001':
                        keyboard.press('2')
                        keyboard.release('2')
                        # eprint('RNS-E: wheel button scrolled RIGHT - Keyboard: "2" -  OpenAuto: "Scroll right"')

                    elif msg == '373001400000':  # RNS-E: button UP pressed
                        up += 1
                    elif msg == '373004400000' and up > 0:  # RNS-E: button UP released
                        if up <= 4:
                            keyboard.press(Key.up)
                            keyboard.release(Key.up)
                            # eprint('RNS-E: button up shortpress - Keyboard: "UP arrow" - OpenAuto: "Navigate up"')
                            up = 0
                        elif up > 4:
                            if toggle_values_by_rnse_longpress == 'true':
                                pause_fis1 = True
                                clear_fis1 = f'cansend can0 {FIS1}#{"6565656565656565"}'
                                os.system(clear_fis1)
                                toggle_fis1 += 1
                                if toggle_fis1 == 0:
                                    name = 'CLEAR'
                                elif toggle_fis1 == 1:
                                    name = 'TITLE'
                                elif toggle_fis1 == 2:
                                    name = 'ARTIST'
                                elif toggle_fis1 == 3:
                                    name = 'ALBUM'
                                elif toggle_fis1 == 4:
                                    name = 'POSITION'
                                elif toggle_fis1 == 5:
                                    name = 'DURATION'
                                elif toggle_fis1 == 6:
                                    name = 'SPEED'
                                elif toggle_fis1 == 7:
                                    name = 'RPM'
                                elif toggle_fis1 == 8:
                                    name = 'COOLANT'
                                elif toggle_fis1 == 9:
                                    name = 'CPU/TEMP'
                                elif toggle_fis1 == 10:
                                    name = 'CLEAR'
                                    toggle_fis1 = 0
                                name = name.encode().hex().upper()
                                name = convert_to_audi_ascii(name)
                                name = fill_up_with_spaces_align_center(name)
                                name = f'cansend can0 {FIS1}#{name}'
                                os.system(name)
                                begin1 = -1
                                eind1 = 7
                                sleep(2)
                                pause_fis1 = False
                            else:
                                keyboard.press('P')
                                keyboard.release('P')
                                # eprint('RNS-E: button up - Keyboard: "P" -  OpenAuto: "Answer call/Phone menu"')
                            up = 0

                    elif msg == '373001800000':  # RNS-E: button DOWN pressed
                        down += 1
                    elif msg == '373004800000' and down > 0:  # RNS-E: button DOWN released
                        if down <= 4:
                            keyboard.press(Key.down)
                            keyboard.release(Key.down)
                            # eprint('RNS-E: button down shortpress - Keyboard: "DOWN arrow" -  OpenAuto: "Navigate Down"')
                            down = 0
                        elif down > 4:  # just react if function is enabled by user
                            if toggle_values_by_rnse_longpress == 'true':
                                pause_fis2 = True
                                clear_fis2 = f'cansend can0 {FIS2}#{"6565656565656565"}'
                                os.system(clear_fis2)
                                toggle_fis2 += 1
                                if toggle_fis2 == 0:
                                    name2 = 'CLEAR'
                                elif toggle_fis2 == 1:
                                    name2 = 'TITLE'
                                elif toggle_fis2 == 2:
                                    name2 = 'ARTIST'
                                elif toggle_fis2 == 3:
                                    name2 = 'ALBUM'
                                elif toggle_fis2 == 4:
                                    name2 = 'POSITION'
                                elif toggle_fis2 == 5:
                                    name2 = 'DURATION'
                                elif toggle_fis2 == 6:
                                    name2 = 'SPEED'
                                elif toggle_fis2 == 7:
                                    name2 = 'RPM'
                                elif toggle_fis2 == 8:
                                    name2 = 'COOLANT'
                                elif toggle_fis2 == 9:
                                    name2 = 'CPU/TEMP'
                                elif toggle_fis2 == 10:
                                    name2 = 'CLEAR'
                                    toggle_fis2 = 0
                                name2 = name2.encode().hex().upper()
                                name2 = convert_to_audi_ascii(name2)
                                name2 = fill_up_with_spaces_align_center(name2)
                                name2 = f'cansend can0 {FIS2}#{name2}'
                                print(f'{name2}')
                                os.system(name2)
                                begin2 = -1
                                eind2 = 7
                                sleep(2)
                                pause_fis2 = False
                            else:
                                keyboard.press(Key.f2)
                                keyboard.release(Key.f2)
                                # eprint('RNS-E: button up longpress - Keyboard: "F2" - OpenAuto: "Toggle Android Auto night mode"')
                            down = 0

                    elif msg == '373001001000':  # RNS-E: wheel pressed
                        select += 1
                    elif msg == '373004001000' and select > 0:  # RNS-E: wheel released
                        if select <= 4:
                            keyboard.press(Key.enter)
                            keyboard.release(Key.enter)
                            # eprint('RNS-E: wheel shortpress - Keyboard: "ENTER" on keyboard-  OpenAuto: "Select"')
                            select = 0
                        elif select > 4:
                            keyboard.press('B')
                            keyboard.release('B')
                            # eprint('RNS-E: wheel longpress - Keyboard: "B" -  OpenAuto: "Toggle play/pause"')
                            select = 0

                    elif msg == '373001000200':  # RNS-E: return button pressed
                        back += 1
                    elif msg == '373004000200' and back > 0:  # RNS-E: return button released
                        if back <= 4:
                            keyboard.press(Key.esc)
                            keyboard.release(Key.esc)
                            # eprint('RNS-E return button shortpress - Keyboard "ESC" -  OpenAuto: "Back"')
                            back = 0
                        elif back > 4:
                            keyboard.press('O')
                            keyboard.release('O')
                            # eprint('RNS-E: return button longpress - Keyboard: "O" -  OpenAuto: "End phone call"')
                            back = 0

                    elif msg == '373001020000':  # RNS-E: next track button pressed
                        nextbtn += 1
                    elif msg == '373004020000' and nextbtn > 0:  # RNS-E: next track button released
                        if nextbtn <= 4:
                            keyboard.press('N')
                            keyboard.release('N')
                            # eprint('RNS-E: next track shortpress - Keyboard: "N" -  OpenAuto: "Next track"')
                            nextbtn = 0
                        elif nextbtn > 4:
                            keyboard.press(Key.ctrl)
                            keyboard.press(Key.f3)
                            keyboard.release(Key.ctrl)
                            keyboard.release(Key.f3)
                            # eprint('RNS-E: next track longpress - Keyboard: "CTRL+F3" - OpenAuto: "Toggle application"')
                            nextbtn = 0

                    elif msg == '373001010000':  # RNS-E: previous track button pressed
                        prev += 1
                    elif msg == '373004010000' and prev > 0:  # RNS-E: previous track button released
                        if prev <= 4:
                            keyboard.press('V')
                            keyboard.release('V')
                            # eprint('RNS-E: previous track button shortpress - Keyboard: "V" -  OpenAuto: "Previous track"')
                            prev = 0
                        elif prev > 4:
                            keyboard.press(Key.f12)
                            keyboard.release(Key.f12)
                            # eprint('RNS-E: previous track longpress - Keyboard: "F12" - OpenAuto: "Bring OpenAuto Pro to front"')
                            prev = 0

                    elif msg == '373001000100':  # RNS-E: setup button pressed
                        setup += 1
                    elif msg == '373004000100' and setup > 0:  # RNS-E: setup button released
                        if setup <= 6:
                            keyboard.press('M')
                            keyboard.release('M')
                            # eprint('RNS-E: setup button shortpress - Keyboard: "M" -  OpenAuto: "Voice command"')
                            setup = 0
                        elif setup > 6:
                            # eprint("RNS-E: setup button longpress - shutting down raspberry pi")
                            os.system('sudo shutdown -h now')
                            setup = 0


# read mfsw button presses if mfsw ist detected and rns-e tv input is active
            if canid == '5C3':
                if mfsw_detected == 0:
                    mfsw_detected = 1
                    eprint('mfsw detected')
                # read message 3900 or 3A00 on can id 5C3 to detect if a mfsw is installed.
                elif mfsw_detected == 1 and tv_mode_active == 1:
                    if (carmodel == '8E' and msg == '3904') or (
                            carmodel == '8P' and msg == '390B') or (
                            carmodel == '8J' and msg == '390B'):
                        keyboard.press('1')
                        keyboard.release('1')
                        # eprint("MFSW " + str(carmodel) + ": scan wheel up - Keyboard: 1 - OpenAuto scroll left")
                        press_mfsw = 0
                    elif (carmodel == '8E' and msg == '3905') or (
                            carmodel == '8P' and msg == '390C') or (
                            carmodel == '8J' and msg == '390C'):
                        keyboard.press('2')
                        keyboard.release('2')
                        # eprint("MFSW " + str(carmodel) + ": scan wheel down - Keyboard: 2 - OpenAuto: Scroll right")
                        press_mfsw = 0
                    elif (carmodel == '8E' and msg == '3908') or (
                            carmodel == '8P' and msg == '3908') or (
                            carmodel == '8J' and msg == '3908'):
                        press_mfsw += 1
                    elif (msg == '3900' or msg == '3A00') and press_mfsw > 0:
                        if press_mfsw == 1:
                            keyboard.press(Key.enter)
                            keyboard.release(Key.enter)
                            # eprint("MFSW " + str(carmodel) + ": scan wheel shortpress - Keyboard: ENTER - OpenAuto: Select")
                            press_mfsw = 0
                        elif press_mfsw >= 2:
                            keyboard.press(Key.esc)
                            keyboard.release(Key.esc)
                            # eprint("MFSW " + str(carmodel) + ": scan wheel longpress - Keyboard: ESC - OpenAuto: Back")
                            press_mfsw = 0
                    elif msg == '3900' and press_mfsw == 0:
                        nextbtn = 0
                        prev = 0



# read time from dis (driver information system) and set the time on raspberry pi.
            if canid == '623':
                if read_and_set_time_from_dashboard == 'true':  # read date and time from dis and set on raspberry pi
                    if tmset == 0:
                        msg = re.sub('[\\s+]', '', msg)
                        date = 'sudo date %s%s%s%s%s.%s' % (
                            msg[10:12], msg[8:10], msg[2:4], msg[4:6], msg[12:16], msg[6:8])
                        os.system(date)
                        eprint('Date and time set on raspberry pi')
                        tmset = 1




# read carmodel (8E - Audi A4 / 8P - Audi A3) and caryear - precondition to use different can ids
            if canid == '65F':
                if msg[0:2] == '01':
                    if car_model_set == 0:
                        msg = re.sub('[\\s+]', '', msg)
                        carmodel = msg[8:12]
                        carmodelyear = msg[14:16]
                        carmodel = bytes.fromhex(carmodel).decode()
                        carmodelyear = bytes.fromhex(carmodelyear).decode()
                        carmodelyear = str(int(carmodelyear, 16) + 2000)
                        car_model_set = 1
                        eprint('car model and carmodel year was successfully read from canbus')
                        eprint("car model:", carmodel)
                        eprint("car model year:", carmodelyear)
                        global FIS1
                        global FIS2
                        if carmodel[0:2] == '8E':
                            FIS1 = '265'
                            FIS2 = '267'
                        elif carmodel[0:2] in ('8I', '8J', '8L', '8P'):
                            FIS1 = '667'
                            FIS2 = '66B'
                        elif carmodel[0:2] == '42':
                            FIS1 = '265'
                            FIS2 = '267'

# check if rns-e tv input is active
            if canid == '661':
                if msg == '8101123700000000' or msg == '8301123700000000':
                    if tv_mode_active == 0:
                        keyboard.press('X')  # play media, if rns-e ist (back) on tv mode
                        keyboard.release('X')
                        # eprint('rns-e is (back) in tv mode - play media - Keyboard: "X" - OpenAuto: "play"')
                        tv_mode_active = 1
                else:
                    if tv_mode_active == 1:
                        keyboard.press('C')  # pause media, if rns-e left tv mode
                        keyboard.release('C')
                        # eprint('rns-e is not in tv mode (anymore) - pause media - Keyboard: "C" - OpenAuto: "pause"')
                        tv_mode_active = 0

    except Exception as e:
        eprint("error in function read_from_canbus:", str(e))

# if the script gets closed by keyboard interrupt close connection to picamera
    except KeyboardInterrupt as e:
        if reversecamera_by_reversegear == 'true':
            camera.stop_preview()
            camera.close()
        eprint("Script killed by KeyboardInterrupt!")
        exit(1)


# send message to activate tv input source on rns-e
def send_tv_input_activation_message():
    while True:
        # print('In Sendcan')
        # Send message to activate RNS-E tv input
        # eprint('activate rns-e true')
        os.system("cansend can0 602#09123000000000")  # Working in Audi A4 B6 (8E) 2002 - RNS-E (3R0 035 192)
        # os.system("cansend can0 602#81123000000000") #In other forums the message was 81 and not 09. Maybe needed for older RNS-E with CD/TV Button?
        # eprint("activate rns-e tv input message sent")
        sleep(0.5)  # send


# send values to dashboard every 0.5 seconds
def send_values_to_dashboard():
    global begin1
    global eind1
    global begin2
    global eind2
    global playing
    global source
    global speed
    global rpm
    global coolant
    global pause_fis1
    global pause_fis2

    while True:

# clear dis/fis 1st or 2nd line if you just want to show no value there
        if toggle_fis1 == 0:
            if pause_fis1 == False:
                clear_fis1 = f'cansend can0 {FIS1}#{"6565656565656565"}'
                os.system(clear_fis1)
        if toggle_fis2 == 0:
            if pause_fis2 == False:
                clear_fis2 = f'cansend can0 {FIS2}#{"6565656565656565"}'
                os.system(clear_fis2)

# only send oap api mediadata (title, artist, album, position, durdation) to dis/fis if user has activated this feature
        if send_oap_api_mediadata_to_dashboard == 'true':
# send oap api media mediadata to dis/fis
            if toggle_fis1 in (1, 2, 3, 4, 5):
                if source in (1, 3, 4):
                    if playing == True:
                        if pause_fis1 == False:
                            if position == '00:00':
                                begin1 = -1
                                eind1 = 7
                            if toggle_fis1 == 1:
                                regel1 = (f"{title}")
                            elif toggle_fis1 == 2:
                                regel1 = (f"{artist}")
                            elif toggle_fis1 == 3:
                                regel1 = (f"{album}")
                            elif toggle_fis1 == 4:
                                regel1 = (f"{position}")
                            elif toggle_fis1 == 5:
                                regel1 = (f"{duration}")
                            regel1 = regel1.encode('ISO-8859-1', 'ignore')
                            lengte1 = len(regel1)
                            begin1 += 1
                            eind1 += 1
                            if eind1 > lengte1:
                                begin1 = 0
                                eind1 = 8
                            printregel1 = regel1[begin1:eind1]
                            printregel1 = printregel1.hex().upper()
                            printregel1 = convert_to_audi_ascii(printregel1)
                            if len(printregel1) < 16:
                                printregel1 = fill_up_with_spaces_align_center(printregel1)
                            printregel1 = f"cansend can0 {FIS1}#{printregel1} &"
                            os.system(printregel1)

# if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                    elif playing == False:
                        if clear_fis_if_media_is_paused == 'true':
                            pause_media1 = ''
                            pause_media1 = pause_media1.encode().hex().upper()
                            pause_media1 = fill_up_with_spaces_align_center(pause_media1)
                            pause_media1 = convert_to_audi_ascii(pause_media1)
                            pause_media1 = f"cansend can0 {FIS1}#{pause_media1} &"
                            os.system(pause_media1)
# show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                elif source == 2:
                    if pause_fis1 == False:
                        carplay_1 = 'CARPLAY'
                        carplay_1 = carplay_1.encode().hex().upper()
                        carplay_1 = fill_up_with_spaces_align_center(carplay_1)
                        carplay_1 = convert_to_audi_ascii(carplay_1)
                        carplay_1 = f"cansend can0 {FIS1}#{carplay_1} &"

# send oap api media mediadata to dis/fis
            if toggle_fis2 in (1, 2, 3, 4, 5):
                if source in (1, 3, 4):
                    if playing == True:
                        if pause_fis2 == False:
                            if position == '00:00':
                                begin2 = -1
                                eind2 = 7
                            if toggle_fis2 == 1:
                                regel2 = (f"{title}")
                            elif toggle_fis2 == 2:
                                regel2 = (f"{artist}")
                            elif toggle_fis2 == 3:
                                regel2 = (f"{album}")
                            elif toggle_fis2 == 4:
                                regel2 = (f"{position}")
                            elif toggle_fis2 == 5:
                                regel2 = (f"{duration}")
                            regel2 = regel2.encode('ISO-8859-1', 'ignore')
                            lengte2 = len(regel2)
                            begin2 += 1
                            eind2 += 1
                            if eind2 > lengte2:
                                begin2 = 0
                                eind2 = 8
                            printregel2 = regel2[begin2:eind2]
                            printregel2 = printregel2.hex().upper()
                            printregel2 = convert_to_audi_ascii(printregel2)
                            if len(printregel2) < 16:
                                printregel2 = fill_up_with_spaces_align_center(printregel2)
                            printregel2 = f"cansend can0 {FIS2}#{printregel2} &"
                            os.system(printregel2)

# if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                    elif playing == False:  # if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                        if clear_fis_if_media_is_paused == 'true':
                            pause_media2 = ''
                            pause_media2 = pause_media2.encode().hex().upper()
                            pause_media2 = fill_up_with_spaces_align_center(pause_media2)
                            pause_media2 = convert_to_audi_ascii(pause_media2)
                            pause_media2 = f"cansend can0 {FIS2}#{pause_media2} &"
                            os.system(pause_media2)

# show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                elif source == 2:  # show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                    if pause_fis2 == False:
                        carplay_2 = 'CARPLAY'
                        carplay_2 = carplay_2.encode().hex().upper()
                        carplay_2 = fill_up_with_spaces_align_center(carplay_2)
                        carplay_2 = convert_to_audi_ascii(carplay_2)
                        carplay_2 = f"cansend can0 {FIS2}#{carplay_2} &"
                        os.system(carplay_2)
# show text " DISABLED" in dis/fis if user has disabled the feature send_oap_api_mediadata_to_dashboard and toggle_fis1 or toggle_fis2 is 1,2,3,4,5
        elif send_oap_api_mediadata_to_dashboard == 'false':
            if toggle_fis1 in (1, 2, 3, 4, 5):
                disabled_1 = 'DISABLED'
                disabled_1 = disabled_1.encode().hex().upper()
                disabled_1 = fill_up_with_spaces_align_center(disabled_1)
                disabled_1 = convert_to_audi_ascii(disabled_1)
                disabled_1 = f"cansend can0 {FIS1}#{disabled_1} &"
                os.system(disabled_1)

            if toggle_fis2 in (1, 2, 3, 4, 5):
                disabled_2 = 'DISABLED'
                disabled_2 = disabled_2.encode().hex().upper()
                disabled_2 = fill_up_with_spaces_align_center(disabled_2)
                disabled_2 = convert_to_audi_ascii(disabled_2)
                disabled_2 = f"cansend can0 {FIS1}#{disabled_2} &"
                os.system(disabled_2)


# only send values (speed, rpm, coolant, pi cpu usage and temp) to dis/fis if user has activated this feature
        if send_values_to_dashboard == 'true':
# send speed to dis/fis
            if toggle_fis1 == 6:
                if pause_fis1 == False:
                    regel_speed = f'{speed} KM/H'  # example: "120 KM/H"
                    regel_speed = regel_speed.encode().hex().upper()
                    regel_speed = fill_up_with_spaces_align_right(regel_speed)
                    regel_speed = convert_to_audi_ascii(regel_speed)
                    regel_speed = f'cansend can0 {FIS1}#{regel_speed}'
                    os.system(regel_speed)
            if toggle_fis2 == 6:
                if pause_fis2 == False:
                    regel_speed = f'{speed} KM/H'  # example: "120 KM/H"
                    regel_speed = regel_speed.encode().hex().upper()
                    regel_speed = fill_up_with_spaces_align_right(regel_speed)
                    regel_speed = convert_to_audi_ascii(regel_speed)
                    regel_speed = f'cansend can0 {FIS2}#{regel_speed}'
                    os.system(regel_speed)

# send rpm to dis/fis
            if toggle_fis1 == 7:
                if pause_fis1 == False:
                    regel_rpm = f'{rpm} RPM'  # example: "2500 RPM"
                    regel_rpm = regel_rpm.encode().hex().upper()
                    regel_rpm = fill_up_with_spaces_align_right(regel_rpm)
                    regel_rpm = convert_to_audi_ascii(regel_rpm)
                    regel_rpm = f'cansend can0 {FIS1}#{regel_rpm}'
                os.system(regel_rpm)
            if toggle_fis2 == 7:
                if pause_fis2 == False:
                    regel_rpm = f'{rpm} RPM'  # example: "2500 RPM"
                    regel_rpm = regel_rpm.encode().hex().upper()
                    regel_rpm = fill_up_with_spaces_align_right(regel_rpm)
                    regel_rpm = convert_to_audi_ascii(regel_rpm)
                    regel_rpm = f'cansend can0 {FIS2}#{regel_rpm}'
                    os.system(regel_rpm)

# send coolant temp to dis/fis
            if toggle_fis1 == 8:
                if pause_fis1 == False:
                    regel_coolant = f'{coolant} °C W'  # example: "  95°C W"
                    regel_coolant = regel_coolant.encode().hex().upper()
                    regel_coolant = fill_up_with_spaces_align_right(regel_coolant)
                    regel_coolant = convert_to_audi_ascii(regel_coolant)
                    regel_coolant = f'cansend can0 {FIS1}#{regel_coolant}'
                    os.system(regel_coolant)
            if toggle_fis2 == 8:
                if pause_fis2 == False:
                    regel_coolant = f'{coolant} °C W'  # example: "  95°C W"
                    regel_coolant = regel_coolant.encode().hex().upper()
                    regel_coolant = fill_up_with_spaces_align_right(regel_coolant)
                    regel_coolant = convert_to_audi_ascii(regel_coolant)
                    regel_coolant = f'cansend can0 {FIS2}#{regel_coolant}'
                    os.system(regel_coolant)

# send raspberry pi cpu temp to fis
            if toggle_fis1 == 9:
                if pause_fis1 == False:
                    cpu = round(psutil.cpu_percent())
                    if cpu == '100':  # prevent cpu usage to be three digits
                        cpu = '99'
                    cpu = str(cpu).zfill(2)
                    cpu = cpu.encode().hex().upper()
                    regel_cpu_temp = (get_cpu_temp())
                    regel_cpu_temp = str(regel_cpu_temp)
                    regel_cpu_temp = f'{cpu}% {regel_cpu_temp}°C'  # example: "25% 38°C"
                    regel_cpu_temp = regel_cpu_temp.encode().hex().upper()
                    regel_cpu_temp = fill_up_with_spaces_align_right(regel_cpu_temp)
                    regel_cpu_temp = convert_to_audi_ascii(regel_cpu_temp)
                    regel_cpu_temp = f'cansend can0 {FIS1}#{regel_cpu_temp}'
                    os.system(regel_cpu_temp)
            if toggle_fis2 == 9:
                if pause_fis2 == False:
                    cpu = round(psutil.cpu_percent())
                    if cpu == '100':  # prevent cpu usage to be three digits
                        cpu = '99'
                    cpu = str(cpu).zfill(2)
                    cpu = cpu.encode().hex().upper()
                    regel_cpu_temp = (get_cpu_temp())
                    regel_cpu_temp = str(regel_cpu_temp)
                    regel_cpu_temp = f'{cpu}% {regel_cpu_temp}°C'  # example: "25% 38°C"
                    regel_cpu_temp = regel_cpu_temp.encode().hex().upper()
                    regel_cpu_temp = fill_up_with_spaces_align_right(regel_cpu_temp)
                    regel_cpu_temp = convert_to_audi_ascii(regel_cpu_temp)
                    regel_cpu_temp = f'cansend can0 {FIS2}#{regel_cpu_temp}'
                    os.system(regel_cpu_temp)


        sleep(0.5)  # just send to dis/fis every 0.5 seconds. Needed for scrolling speed if values are bigger than 8 characters.


# send hands free message to avoid flickering from dashboard 1st and 2nd line
def send_hands_free_activation_message():
    while True:
        # print('In sendcan3')
        os.system('cansend can0 665#0300')
        sleep(1)

# read cpu temperature
def get_cpu_temp():
    """
    Obtains the current value of the CPU temperature.
    :returns: Current value of the CPU temperature if successful, zero value otherwise.
    :rtype: float
    """
    # Initialize the result.
    result = 0.0
    # The first line in this file holds the CPU temperature as an integer times 1000.
    # Read the first line and remove the newline character at the end of the string.
    if os.path.isfile('/sys/class/thermal/thermal_zone0/temp'):
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            line = f.readline().strip()
        # Test if the string is an integer as expected.
        if line.isdigit():
            # Convert the string with the CPU temperature to a float in degrees Celsius.
            result = round(float(line) / 1000)
    # Give the result back to the caller.
    return result

# convert hex text to audi ascii
def convert_to_audi_ascii(content=''):
    bytex0, byte0x, bytex1, byte1x, bytex2, byte2x, bytex3, byte3x, bytex4, byte4x, bytex5, byte5x, bytex6, byte6x, bytex7, byte7x = content[0:1], content[1:2], content[2:3], content[3:4], content[4:5], content[5:6], content[6:7], content[7:8], content[8:9], content[9:10], content[10:11], content[11:12], content[12:13], content[13:14], content[14:15], content[15:16]

    if bytex0 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex0 = '0'
    elif bytex0 == '7' and byte0x == '0':  # hex 70 = "p" = 17 audi ascii
        bytex0 = '1'
    elif bytex0 == 'B' and byte0x == '0':  # hex B0 = "Â°" = BB audi ascii
        bytex0 = 'B'
        byte0x = 'B'
    elif bytex0 == 'E' and byte0x == '4':  # german umlaut "ä"
        bytex0 = '9'
        byte0x = '1'
    elif bytex0 == 'F' and byte0x == '6':  # german umlaut "ö"
        bytex0 = '9'
        byte0x = '7'
    elif bytex0 == 'F' and byte0x == 'C':  # german umlaut "ü"
        bytex0 = '9'
        byte0x = '9'
    elif bytex0 == 'C' and byte0x == '4':  # german umlaut "Ä"
        bytex0 = '5'
        byte0x = 'F'
    elif bytex0 == 'D' and byte0x == '6':  # german umlaut "Ö"
        bytex0 = '6'
        byte0x = '0'
    elif bytex0 == 'D' and byte0x == 'C':  # german umlaut "Ü"
        bytex0 = '6'
        byte0x = '1'
    elif bytex1 == 'D' and byte1x == 'F':  # german umlaut "ß"
        bytex1 = '8'
        byte1x = 'D'
    elif bytex0 == '5' and byte0x == 'F':  # symbol "_"
        bytex0 = '6'
        byte0x = '6'

    if bytex1 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex1 = '0'
    elif bytex1 == '7' and byte1x == '0':
        bytex1 = '1'
    elif bytex1 == 'B' and byte1x == '0':
        bytex1 = 'B'
        byte1x = 'B'
    elif bytex1 == 'E' and byte1x == '4':
        bytex1 = '9'
        byte1x = '1'
    elif bytex1 == 'F' and byte1x == '6':
        bytex1 = '9'
        byte1x = '7'
    elif bytex1 == 'F' and byte1x == 'C':
        bytex1 = '9'
        byte1x = '9'
    elif bytex1 == 'C' and byte1x == '4':
        bytex1 = '5'
        byte1x = 'F'
    elif bytex1 == 'D' and byte1x == '6':
        bytex1 = '6'
        byte1x = '0'
    elif bytex1 == 'D' and byte1x == 'C':
        bytex1 = '6'
        byte1x = '1'
    elif bytex1 == 'D' and byte1x == 'F':
        bytex1 = '8'
        byte1x = 'D'
    elif bytex1 == '5' and byte1x == 'F':
        bytex1 = '6'
        byte1x = '6'

    if bytex2 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex2 = '0'
    elif bytex2 == '7' and byte2x == '0':
        bytex2 = '1'
    elif bytex2 == 'B' and byte2x == '0':
        bytex2 = 'B'
        byte2x = 'B'
    elif bytex2 == 'E' and byte2x == '4':
        bytex2 = '9'
        byte2x = '1'
    elif bytex2 == 'F' and byte2x == '6':
        bytex2 = '9'
        byte2x = '7'
    elif bytex2 == 'F' and byte2x == 'C':
        bytex2 = '9'
        byte2x = '9'
    elif bytex2 == 'C' and byte2x == '4':
        bytex2 = '5'
        byte2x = 'F'
    elif bytex2 == 'D' and byte2x == '6':
        bytex2 = '6'
        byte2x = '0'
    elif bytex2 == 'D' and byte2x == 'C':
        bytex2 = '6'
        byte2x = '1'
    elif bytex2 == 'D' and byte2x == 'F':
        bytex2 = '8'
        byte2x = 'D'
    elif bytex2 == '5' and byte2x == 'F':
        bytex2 = '6'
        byte2x = '6'

    if bytex3 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex3 = '0'
    elif bytex3 == '7' and byte3x == '0':
        bytex3 = '1'
    elif bytex3 == 'B' and byte3x == '0':
        bytex3 = 'B'
        byte3x = 'B'
    elif bytex3 == 'E' and byte3x == '4':
        bytex3 = '9'
        byte3x = '1'
    elif bytex3 == 'F' and byte3x == '6':
        bytex3 = '9'
        byte3x = '7'
    elif bytex3 == 'F' and byte3x == 'C':
        bytex3 = '9'
        byte3x = '9'
    elif bytex3 == 'C' and byte3x == '4':
        bytex3 = '5'
        byte3x = 'F'
    elif bytex3 == 'D' and byte3x == '6':
        bytex3 = '6'
        byte3x = '0'
    elif bytex3 == 'D' and byte3x == 'C':
        bytex3 = '6'
        byte3x = '1'
    elif bytex3 == 'D' and byte3x == 'F':
        bytex3 = '8'
        byte3x = 'D'
    elif bytex3 == '5' and byte3x == 'F':
        bytex3 = '6'
        byte3x = '6'

    if bytex4 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex4 = '0'
    elif bytex4 == '7' and byte4x == '0':
        bytex4 = '1'
    elif bytex4 == 'B' and byte4x == '0':
        bytex4 = 'B'
        byte4x = 'B'
    elif bytex4 == 'E' and byte4x == '4':
        bytex4 = '9'
        byte4x = '1'
    elif bytex4 == 'F' and byte4x == '6':
        bytex4 = '9'
        byte4x = '7'
    elif bytex4 == 'F' and byte4x == 'C':
        bytex4 = '9'
        byte4x = '9'
    elif bytex4 == 'C' and byte4x == '4':
        bytex4 = '5'
        byte4x = 'F'
    elif bytex4 == 'D' and byte4x == '6':
        bytex4 = '6'
        byte4x = '0'
    elif bytex4 == 'D' and byte4x == 'C':
        bytex4 = '6'
        byte4x = '1'
    elif bytex4 == 'D' and byte4x == 'F':
        bytex4 = '8'
        byte4x = 'D'
    elif bytex4 == '5' and byte4x == 'F':
        bytex4 = '6'
        byte4x = '6'

    if bytex5 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex5 = '0'
    elif bytex5 == '7' and byte5x == '0':
        bytex5 = '1'
    elif bytex5 == 'B' and byte5x == '0':
        bytex5 = 'B'
        byte5x = 'B'
    elif bytex5 == 'E' and byte5x == '4':
        bytex5 = '9'
        byte5x = '1'
    elif bytex5 == 'F' and byte5x == '6':
        bytex5 = '9'
        byte5x = '7'
    elif bytex5 == 'F' and byte5x == 'C':
        bytex5 = '9'
        byte5x = '9'
    elif bytex5 == 'C' and byte5x == '4':
        bytex5 = '5'
        byte5x = 'F'
    elif bytex5 == 'D' and byte5x == '6':
        bytex5 = '6'
        byte5x = '0'
    elif bytex5 == 'D' and byte5x == 'C':
        bytex5 = '6'
        byte5x = '1'
    elif bytex5 == 'D' and byte5x == 'F':
        bytex5 = '8'
        byte5x = 'D'
    elif bytex5 == '5' and byte5x == 'F':
        bytex5 = '6'
        byte5x = '6'

    if bytex6 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex6 = '0'
    elif bytex6 == '7' and byte6x == '0':
        bytex6 = '1'
    elif bytex6 == 'B' and byte6x == '0':
        bytex6 = 'B'
        byte6x = 'B'
    elif bytex6 == 'E' and byte6x == '4':
        bytex6 = '9'
        byte6x = '1'
    elif bytex6 == 'F' and byte6x == '6':
        bytex6 = '9'
        byte6x = '7'
    elif bytex6 == 'F' and byte6x == 'C':
        bytex6 = '9'
        byte6x = '9'
    elif bytex6 == 'C' and byte6x == '4':
        bytex6 = '5'
        byte6x = 'F'
    elif bytex6 == 'D' and byte6x == '6':
        bytex6 = '6'
        byte6x = '0'
    elif bytex6 == 'D' and byte6x == 'C':
        bytex6 = '6'
        byte6x = '1'
    elif bytex6 == 'D' and byte6x == 'F':
        bytex6 = '8'
        byte6x = 'D'
    elif bytex6 == '5' and byte6x == 'F':
        bytex6 = '6'
        byte6x = '6'

    if bytex7 == '6':  # a-o in hex 6x = a-o in audi ascii 0x
        bytex7 = '0'
    elif bytex7 == '7' and byte7x == '0':
        bytex7 = '1'
    elif bytex7 == 'B' and byte7x == '0':
        bytex7 = 'B'
        byte7x = 'B'
    elif bytex7 == 'E' and byte7x == '4':
        bytex7 = '9'
        byte7x = '1'
    elif bytex7 == 'F' and byte7x == '6':
        bytex7 = '9'
        byte7x = '7'
    elif bytex7 == 'F' and byte7x == 'C':
        bytex7 = '9'
        byte7x = '9'
    elif bytex7 == 'C' and byte7x == '4':
        bytex7 = '5'
        byte7x = 'F'
    elif bytex7 == 'D' and byte7x == '6':
        bytex7 = '6'
        byte7x = '0'
    elif bytex7 == 'D' and byte7x == 'C':
        bytex7 = '6'
        byte7x = '1'
    elif bytex7 == 'D' and byte7x == 'F':
        bytex7 = '8'
        byte7x = 'D'
    elif bytex7 == '5' and byte7x == 'F':
        bytex7 = '6'
        byte7x = '6'
    content = f'{bytex0}{byte0x}{bytex1}{byte1x}{bytex2}{byte2x}{bytex3}{byte3x}{bytex4}{byte4x}{bytex5}{byte5x}{bytex6}{byte6x}{bytex7}{byte7x}'
    return content

# fill up content with spaces if the content has less than 8 digits. Filled up with hex 20 means the content in dis/fis will be aligned centered
def fill_up_with_spaces_align_center(content=''):  # content centered
    lengte = 0
    lengte = len(content)
    # print(lengte)
    if lengte == 0:
        content = (f'2020202020202020{content}')
    elif lengte == 2:
        content = (f'20202020202020{content}')
    elif lengte == 4:
        content = (f'202020202020{content}')
    elif lengte == 6:
        content = (f'2020202020{content}')
    elif lengte == 8:
        content = (f'20202020{content}')
    elif lengte == 10:
        content = (f'202020{content}')
    elif lengte == 12:
        content = (f'2020{content}')
    elif lengte == 14:
        content = (f'20{content}')
    elif lengte == 16:
        content = content
    # print(content)
    return content

# fill up content with spaces if the content has less than 8 digits. Filled up with hex 65 means the content in dis/fis will be aligned right
def fill_up_with_spaces_align_right(content=''):  # content right aligned
    lengte = 0
    lengte = len(content)
    # print(lengte)
    if lengte == 0:
        content = (f'6565656565656565{content}')
    elif lengte == 2:
        content = (f'65656565656565{content}')
    elif lengte == 4:
        content = (f'656565656565{content}')
    elif lengte == 6:
        content = (f'6565656565{content}')
    elif lengte == 8:
        content = (f'65656565{content}')
    elif lengte == 10:
        content = (f'656565{content}')
    elif lengte == 12:
        content = (f'6565{content}')
    elif lengte == 14:
        content = (f'65{content}')
    elif lengte == 16:
        content = content
    # print(content)
    return content


# Declare threads
t1 = Thread(target=read_on_canbus)
t2 = Thread(target=send_tv_input_activation_message)
t3 = Thread(target=read_song_infos_from_oap_api)
t4 = Thread(target=send_values_to_dashboard)
t5 = Thread(target=send_hands_free_activation_message)
t6 = Thread(target=get_cpu_temp)

# Start/call threads
if __name__ == '__main__':
    t1.start()
    if activate_rnse_tv_input == 'true':
        t2.start()
    if send_values_to_dashboard == 'true':
        t6.start()
    if send_values_to_dashboard == 'true' or send_oap_api_mediadata_to_dashboard == 'true':
        t4.start()
        t5.start()
    if send_oap_api_mediadata_to_dashboard == 'true':
        t3.start()
        sleep(5)
        main()