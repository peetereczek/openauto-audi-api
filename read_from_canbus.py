# -*- coding: ISO-8859-1 -*-
from __future__ import print_function
import os
import sys
import binascii
import re
import logging
import threading
from time import sleep
from threading import Thread
from builtins import str
import time

#####################################################

#  Set here, what you want to use
#  PLEASE ONLY USE True or False

#  MFSW (multi function steering wheel) will autodetect if it's installed

activate_rnse_tv_input = True               # If you don't have a multimedia interface, you can send the activation message for rns-e tv input with raspberry pi. Note: You'll need fbas or rgbs video pinned into 32 pin rns-e plug.
read_and_set_time_from_dashboard = True     # Read the date and the time from dashboard. Useful if the raspberry pi doesn't have internet connection in the car.
control_pi_by_rns_e_buttons = True          # Use rns-e buttons to control the raspberry pi. Note: You'll need to have "pynput" installed. You can install pynput with these commands: "pip3 install pynput" and "sudo pip3 install pynput".
change_dark_mode_by_car_light = True             # read cars light state on/off to change openauto and android auto day/night mode
send_values_to_dashboard = True             # Send speed, rpm, coolant, pi cpu usage and temp to dashboard
send_oap_api_mediadata_to_dashboard = True  # Send oap api mediadata (title, artist, album, position, duration) to dashboard
clear_fis_if_media_is_paused = True         # Show blank 1st and 2nd line fis/dis if media is paused. If this is set to False the media will still show/scroll.
toggle_values_by_rnse_longpress = True      # This will replace the normal rns-e up / rns-e down longpress to toggle values for 1st and 2nd line dis/fis. See: toggle_fis1 and toggle_fis2 below.
reversecamera_by_reversegear = False        # Use a hdmi input connected to the raspberry pi as reversecamera. Example: HDMI to CSI-2 Adapter Board.
reversecamera_turn_off_delay = 5            # Delay to turn off the reversecamera in seconds. Useful in parking situations.
shutdown_by_ignition_off = False            # Shutdown the raspberry pi, if the ignition went off.
shutdown_by_pulling_key = False             # Shutdown the raspberry pi, if the they key got pulled.
shutdown_delay = 5                          # Shutdown delay in seconds. Used for "shutdown_by_ignition_off" and "shutdown_by_pulling_key".

# Speed measure 0-100 km/h etc.
lower_speed = 0                             # speed to start acceleration measurement (example: 0 km/h)
upper_speed = 100                           # speed to stop acceleration measurement (ecample: 100 km/h)

# Select here what you want to show in dashboard
toggle_fis1 = 1                             # 1st line dis/fis
toggle_fis2 = 4                             # 2nd line dis/fis
# 0 = blank line, 1 = title, 2 = artist, 3 = album, 4 = song position, 5 = song duration, 6 = speed, 7 = rpm, 8 = coolant, 9 = cpu/temp

#####################################################
#  set can interface
can_interface = 'can0'
#####################################################

# Declare variables
FIS1 = '265'  # standard can id for first line dis/fis if no carmodel is detected
FIS2 = '267'  # standard can id for second line dis/fis if no carmodel is detected
speed = 0
rpm = ''
coolant = ''
playing = ''
position = ''
source = ''
title = ''
artist = ''
album = ''
duration = ''
begin1 = -1
eind1 = 7
begin2 = -1
eind2 = 7
pause_fis1 = False
pause_fis2 = False
#global light_status
light_status = None
light_set = False


logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-9s) %(message)s', )

# install python-can if the module was not found.
try:
    import can
except ModuleNotFoundError:
    print('python-can is not installed - installing now (internet connection required')
    os.system('pip3 install python-can')
    os.system('sudo pip3 install python-can')
    print('python-can successfully installed - restarting script')
    os.execv(sys.executable, ['python3'] + sys.argv)

# install psutil if the module was not found. Needed to show raspberry pi cpu usage in %
if send_values_to_dashboard == True:
    try:
        import psutil
    except ModuleNotFoundError:
        print('psutil is not installed - installing now (internet connection required')
        os.system('pip3 install psutil')
        os.system('sudo pip3 install psutil')
        print('psutil successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)

# install pynput if the module was not found
if control_pi_by_rns_e_buttons == True:
    try:
        from pynput.keyboard import Key, Controller
    except ModuleNotFoundError:
        print('pynput is not installed - installing now (internet connection required')
        os.system('pip3 install pynput')
        os.system('sudo pip3 install pynput')
        print('pynput successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)
    keyboard = Controller()

# install picamera if the module was not found and deactivate camera functions if there is an error importing picamera - script doesn't crash then
if reversecamera_by_reversegear == True:
    try:
        from picamera import PiCamera
    except ModuleNotFoundError as e:
        print('picamera ist not installed - installing now (internet connection required')
        os.system('pip3 install picamera')
        os.system('sudo pip3 install picamera')
        print('picamera successfully installed - restarting script')
        os.execv(sys.executable, ['python3'] + sys.argv)
    except ImportError as e:
        reversecamera_by_reversegear = False
        pass
    try:
        camera = PiCamera()
    except Exception as e:
        # print("camera is not connected or has problems - disabling all reversecamera features")
        reversecamera_by_reversegear = False  # deactivate reversecamera features if the camera is not working
        pass

try:
    import unidecode
except ModuleNotFoundError as e:
    print('unidecode ist not installed - installing now (internet connection required')
    os.system('pip3 install unidecode')
    os.system('sudo pip3 install unidecode')
    print('unidecode successfully installed - restarting script')
    os.execv(sys.executable, ['python3'] + sys.argv)

try:
    import codecs
except ModuleNotFoundError as e:
    print('codecs ist not installed - installing now (internet connection required')
    os.system('pip3 install codecs')
    os.system('sudo pip3 install codecs')
    print('codecs successfully installed - restarting script')
    os.execv(sys.executable, ['python3'] + sys.argv)

# try to import oap api if user has activated this feature
if send_oap_api_mediadata_to_dashboard == True or change_dark_mode_by_car_light == True:
    try:
        import common.Api_pb2 as oap_api
        from common.Client import Client, ClientEventHandler
    # download oap api files from github if the import failes
    except ModuleNotFoundError as e:
        path = os.getcwd()
        set_permissions = f"sudo chmod -R 774 {path}"
        os.system(set_permissions)
        os.system("wget http://github.com/bluewave-studio/openauto-pro-api/archive/master.zip")
        os.system("unzip master.zip")
        path1 = f"mv {path}/openauto-pro-api-main/api_examples/python/common {path}/"
        os.system(path1)
        os.system("rm -r openauto-pro-api-main")
        os.system("rm master.zip")
        print()
        print('oap api files successfully installed - restarting script')
        print()
        os.execv(sys.executable, ['python3'] + sys.argv)
    except ImportError as e:  # disable oap api features if import didn't worked
        show_music_title_in_fis = False
        print('import from oap api failed - disabling oap api features')
        pass




def unidecode_fallback(e):
    part = e.object[e.start:e.end]
    replacement = str(unidecode.unidecode(part) or '?')
    return (replacement, e.start + len(part))

codecs.register_error('unidecode_fallback', unidecode_fallback)



# read on canbus and react to defined messages
def read_on_canbus():
    bus = can.interface.Bus(can_interface, bustype='socketcan')
    message = bus.recv()

    # print('read_on_canbus')
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

        start_time = None
        end_time = None
        elapsed_time = 0

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
        global light_status
        light_status = 0
        regel2 = ''
        label2 = ''
        for message in bus:
            canid = str(hex(message.arbitration_id).lstrip('0x').upper())
            msg = binascii.hexlify(message.data).decode('ascii').upper()

            # print('In read_from_canbus')

            # read time from dis (driver information system) and set the time on raspberry pi.
            if canid == '623':
                if read_and_set_time_from_dashboard == True:  # read date and time from dis and set on raspberry pi
                    if tmset == 0:
                        msg = re.sub('[\\s+]', '', msg)
                        date = 'sudo date %s%s%s%s%s.%s' % (
                            msg[10:12], msg[8:10], msg[2:4], msg[4:6], msg[12:16], msg[6:8])
                        os.system(date)
                        print('Date and time set on raspberry pi')
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
                        print('car model and carmodel year was successfully read from canbus')
                        print("car model:", carmodel)
                        print("car model year:", carmodelyear)
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
                        print('FIS1 =', FIS1)
                        print('FIS2 =', FIS2)

            # read reverse gear message
            if canid == '351':
                global reversecamera_by_reversegear
                if reversecamera_by_reversegear == True:  # read reverse gear message and start reversecamera
                    if msg[0:2] == '00' and gear == 1:
                        gear = 0
                        print("forward gear engaged - stopping reverse camera with", reversecamera_turn_off_delay,
                               "seconds delay")
                        sleep(int(reversecamera_turn_off_delay))  # turn camera off with 5 seconds delay
                        try:
                            camera.stop_preview()
                        except Exception:
                            reversecamera_by_reversegear = False  # deactivate reversecamera features if the camera is not working
                    elif msg[0:2] == '02' and gear == 0:
                        gear = 1
                        print("reverse gear engaged - starting reverse camera")
                        try:
                            camera.start_preview()
                        except Exception:
                            reversecamera_by_reversegear = False  # deactivate reversecamera features if the camera is not working
                            print('problems while starting reversecamera detected - disabling reversecamera feature')

                # read speed
                if toggle_fis1 == 6 or toggle_fis2 == 6 or toggle_fis1 == 10 or toggle_fis2 == 10:
                    msg = re.sub('[\\s+]', '', msg)
                    speed1 = msg[2:4]
                    speed2 = msg[4:6]
                    speed = '%s%s' % (speed2, speed1)
                    speed = int(speed, 16)
                    speed /= 200
                    speed = round(speed)
                    speed = str(speed)
                    if toggle_fis1 == 10:  #make value to integer to use this in 0-100 km/h measure
                        speed = int(speed)
                    if toggle_fis2 == 10:
                        speed = int(speed)

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
                if control_pi_by_rns_e_buttons == True:  # read can messages from rns-e button presses
                    if msg == '373001004001':
                        keyboard.press('1')
                        keyboard.release('1')
                        # print('RNS-E: wheel button scrolled LEFT - Keyboard: "1" - OpenAuto: "Scroll left"')

                    elif msg == '373001002001':
                        keyboard.press('2')
                        keyboard.release('2')
                        # print('RNS-E: wheel button scrolled RIGHT - Keyboard: "2" -  OpenAuto: "Scroll right"')

                    elif msg == '373001400000':  # RNS-E: button UP pressed
                        up += 1
                    elif msg == '373004400000' and up > 0:  # RNS-E: button UP released
                        if up <= 4:
                            keyboard.press(Key.up)
                            keyboard.release(Key.up)
                            # print('RNS-E: button up shortpress - Keyboard: "UP arrow" - OpenAuto: "Navigate up"')
                            up = 0
                        elif up > 4:
                            if toggle_values_by_rnse_longpress == True:
                                pause_fis1 = True
                                clear_fis1 = f'cansend {can_interface} {FIS1}#{"6565656565656565"}'
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
                                    name = f'{lower_speed}-{upper_speed}'
                                elif toggle_fis1 == 11:
                                    name = 'CLEAR'
                                    toggle_fis1 = 0
                                name = name.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                                name = convert_to_audi_ascii(name)
                                name = fill_up_with_spaces_align_center(name)
                                name = f'cansend {can_interface} {FIS1}#{name}'
                                os.system(name)
                                begin1 = -1
                                eind1 = 7
                                sleep(2)
                                os.system(clear_fis1)
                                pause_fis1 = False

                            else:
                                keyboard.press('P')
                                keyboard.release('P')
                                # print('RNS-E: button up longpress - Keyboard: "P" -  OpenAuto: "Answer call/Phone menu"')
                            up = 0

                    elif msg == '373001800000':  # RNS-E: button DOWN pressed
                        down += 1
                    elif msg == '373004800000' and down > 0:  # RNS-E: button DOWN released
                        if down <= 4:
                            keyboard.press(Key.down)
                            keyboard.release(Key.down)
                            # print('RNS-E: button down shortpress - Keyboard: "DOWN arrow" -  OpenAuto: "Navigate Down"')
                            down = 0
                        elif down > 4:  # just react if function is enabled by user
                            if toggle_values_by_rnse_longpress == True:
                                pause_fis2 = True
                                clear_fis2 = f'cansend {can_interface} {FIS2}#{"6565656565656565"}'
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
                                    name2 = f'{lower_speed}-{upper_speed}'
                                elif toggle_fis2 == 11:
                                    name2 = 'CLEAR'
                                    toggle_fis2 = 0

                                name2 = name2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                                name2 = convert_to_audi_ascii(name2)
                                name2 = fill_up_with_spaces_align_center(name2)
                                name2 = f'cansend {can_interface} {FIS2}#{name2}'
                                os.system(name2)
                                begin2 = -1
                                eind2 = 7
                                sleep(2)
                                pause_fis2 = False
                            else:
                                keyboard.press(Key.f2)
                                keyboard.release(Key.f2)
                                # print('RNS-E: button down longpress - Keyboard: "F2" - OpenAuto: "Toggle Android Auto night mode"')
                            down = 0

                    elif msg == '373001001000':  # RNS-E: wheel pressed
                        select += 1
                    elif msg == '373004001000' and select > 0:  # RNS-E: wheel released
                        if select <= 4:
                            keyboard.press(Key.enter)
                            keyboard.release(Key.enter)
                            # print('RNS-E: wheel shortpress - Keyboard: "ENTER" on keyboard-  OpenAuto: "Select"')
                            select = 0
                        elif select > 4:
                            keyboard.press('B')
                            keyboard.release('B')
                            # print('RNS-E: wheel longpress - Keyboard: "B" -  OpenAuto: "Toggle play/pause"')
                            select = 0

                    elif msg == '373001000200':  # RNS-E: return button pressed
                        back += 1
                    elif msg == '373004000200' and back > 0:  # RNS-E: return button released
                        if back <= 4:
                            keyboard.press(Key.esc)
                            keyboard.release(Key.esc)
                            # print('RNS-E return button shortpress - Keyboard "ESC" -  OpenAuto: "Back"')
                            back = 0
                        elif back > 4:
                            keyboard.press('O')
                            keyboard.release('O')
                            # print('RNS-E: return button longpress - Keyboard: "O" -  OpenAuto: "End phone call"')
                            back = 0

                    elif msg == '373001020000':  # RNS-E: next track button pressed
                        nextbtn += 1
                    elif msg == '373004020000' and nextbtn > 0:  # RNS-E: next track button released
                        if nextbtn <= 4:
                            keyboard.press('N')
                            keyboard.release('N')
                            # print('RNS-E: next track shortpress - Keyboard: "N" -  OpenAuto: "Next track"')
                            nextbtn = 0
                        elif nextbtn > 4:
                            keyboard.press(Key.ctrl)
                            keyboard.press(Key.f3)
                            keyboard.release(Key.ctrl)
                            keyboard.release(Key.f3)
                            # print('RNS-E: next track longpress - Keyboard: "CTRL+F3" - OpenAuto: "Toggle application"')
                            nextbtn = 0

                    elif msg == '373001010000':  # RNS-E: previous track button pressed
                        prev += 1
                    elif msg == '373004010000' and prev > 0:  # RNS-E: previous track button released
                        if prev <= 4:
                            keyboard.press('V')
                            keyboard.release('V')
                            # print('RNS-E: previous track button shortpress - Keyboard: "V" -  OpenAuto: "Previous track"')
                            prev = 0
                        elif prev > 4:
                            keyboard.press(Key.f12)
                            keyboard.release(Key.f12)
                            # print('RNS-E: previous track longpress - Keyboard: "F12" - OpenAuto: "Bring OpenAuto Pro to front"')
                            prev = 0

                    elif msg == '373001000100':  # RNS-E: setup button pressed
                        setup += 1
                    elif msg == '373004000100' and setup > 0:  # RNS-E: setup button released
                        if setup <= 6:
                            keyboard.press('M')
                            keyboard.release('M')
                            # print('RNS-E: setup button shortpress - Keyboard: "M" -  OpenAuto: "Voice command"')
                            setup = 0
                        elif setup > 6:
                            # print("RNS-E: setup button longpress - shutting down raspberry pi")
                            os.system('sudo shutdown -h now')
                            setup = 0

            # read mfsw button presses if mfsw ist detected and rns-e tv input is active
            if canid == '5C3':
                if mfsw_detected == 0:
                    mfsw_detected = 1
                    print('mfsw detected')
                # read message 3900 or 3A00 on can id 5C3 to detect if a mfsw is installed.
                elif mfsw_detected == 1 and tv_mode_active == 1:
                    if (carmodel == '8E' and msg == '3904') or (
                            carmodel == '8P' and msg == '390B') or (
                            carmodel == '8J' and msg == '390B'):
                        keyboard.press('1')
                        keyboard.release('1')
                        # print("MFSW " + str(carmodel) + ": scan wheel up - Keyboard: 1 - OpenAuto scroll left")
                        press_mfsw = 0
                    elif (carmodel == '8E' and msg == '3905') or (
                            carmodel == '8P' and msg == '390C') or (
                            carmodel == '8J' and msg == '390C'):
                        keyboard.press('2')
                        keyboard.release('2')
                        # print("MFSW " + str(carmodel) + ": scan wheel down - Keyboard: 2 - OpenAuto: Scroll right")
                        press_mfsw = 0
                    elif (carmodel == '8E' and msg == '3908') or (
                            carmodel == '8P' and msg == '3908') or (
                            carmodel == '8J' and msg == '3908'):
                        press_mfsw += 1
                    elif (msg == '3900' or msg == '3A00') and press_mfsw > 0:
                        if press_mfsw == 1:
                            keyboard.press(Key.enter)
                            keyboard.release(Key.enter)
                            # print("MFSW " + str(carmodel) + ": scan wheel shortpress - Keyboard: ENTER - OpenAuto: Select")
                            press_mfsw = 0
                        elif press_mfsw >= 2:
                            keyboard.press(Key.esc)
                            keyboard.release(Key.esc)
                            # print("MFSW " + str(carmodel) + ": scan wheel longpress - Keyboard: ESC - OpenAuto: Back")
                            press_mfsw = 0
                    elif msg == '3900' and press_mfsw == 0:
                        nextbtn = 0
                        prev = 0

            # check if the car light is turned on - toggle day/night mode
            if canid == '635':
                light = ''
                light = re.sub('[\\s+]', '', msg)
                light = msg[2:4]
                light = int(light, 16)
                if light > 0 and light_status == 0:
                    light_status = 1
                    print('Light is turned on')
                elif light <= 0 and light_status == 1:
                    light_status = 0
                    print('Light is turned off')
            # check if rns-e tv input is active
            if canid == '661':
                if msg == '8101123700000000' or msg == '8301123700000000':
                    if tv_mode_active == 0:
                        keyboard.press('X')  # play media, if rns-e ist (back) on tv mode
                        keyboard.release('X')
                        # print('rns-e is (back) in tv mode - play media - Keyboard: "X" - OpenAuto: "play"')
                        tv_mode_active = 1
                else:
                    if tv_mode_active == 1:
                        keyboard.press('C')  # pause media, if rns-e left tv mode
                        keyboard.release('C')
                        # print('rns-e is not in tv mode (anymore) - pause media - Keyboard: "C" - OpenAuto: "pause"')
                        tv_mode_active = 0

            # read ignition message, or pulling key message to shut down the raspberry pi
            if canid == '271' or canid == '2C3':
                if shutdown_by_ignition_off == True or shutdown_by_pulling_key == True:
                    if msg[0:2] == '11' and shutdown_by_ignition_off == True:
                        print("ignition off message detected - system will shutdown in", shutdown_delay, "seconds")
                        sleep(int(shutdown_delay))  # defined delay to shutdown the pi
                        print("system is shutting down now")
                        os.system('sudo shutdown -h now')
                    elif msg[0:2] == '10' and shutdown_by_pulling_key == True:
                        print("pulling key message detected - system will shutdown in", shutdown_delay, "seconds")
                        sleep(int(shutdown_delay))  # defined delay to shutdown the pi
                        print("system is shutting down now")
                        os.system('sudo shutdown -h now')


    except Exception as e:
        print("error in function read_from_canbus:", str(e))

    # if the script gets closed by keyboard interrupt close connection to picamera
    except KeyboardInterrupt as e:
        if reversecamera_by_reversegear == True:
            camera.stop_preview()
            camera.close()
        print("Script killed by KeyboardInterrupt!")
        exit(1)

# from oap api "MediaData.py" to read media metadata (title, artist, album, position, duration)
if send_oap_api_mediadata_to_dashboard == True or change_dark_mode_by_car_light == True:

    class EventHandler(ClientEventHandler):

        def __init__(self):
            self._timer = None

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

            if change_dark_mode_by_car_light == True:
                self.toggle_day_night(client)

        if change_dark_mode_by_car_light == True:
            def toggle_day_night(self, client):
                global light_set

                if light_status == 1 and light_set == False:  #define day or night
                    self._day = True
                elif light_status == 0 and light_set == False:  #define day or night
                    self._day = False
    # just react on changes if light turned from off to on and dont send every time to the api
                if (light_status == 1 and self._day == False) or (light_status == 1 and light_set == False):
                    self._day = True
                    set_day_night = oap_api.SetDayNight()
                    set_day_night.android_auto_night_mode = self._day
                    set_day_night.oap_night_mode = self._day
                    client.send(oap_api.MESSAGE_SET_DAY_NIGHT, 0,
                                set_day_night.SerializeToString())
                    light_set = True
                    print("Light turned on - turn dark mode on")

    # just react on changes if light turned from on to off and dont send every time to the api
                elif light_status == 0 and self._day == True or (light_status == 0 and light_set == False):
                    self._day = False
                    set_day_night = oap_api.SetDayNight()
                    set_day_night.android_auto_night_mode = self._day
                    set_day_night.oap_night_mode = self._day
                    client.send(oap_api.MESSAGE_SET_DAY_NIGHT, 0,
                                set_day_night.SerializeToString())
                    light_set = True
                    print("Light turned off - turn dark mode off")

                self._timer = threading.Timer(3, self.toggle_day_night, [client])
                self._timer.start()

            def get_timer(self):
                return self._timer

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
        event_handler = EventHandler()
        client.set_event_handler(event_handler)
        client.connect('127.0.0.1', 44405)
        active = True
        while active:
            try:
                active = client.wait_for_message()
            except KeyboardInterrupt:
                break
        client.disconnect()

# send message to activate tv input source on rns-e
def send_tv_input_activation_message():
    while True:
        # print('send_tv_input_activation_message')
        # Send message to activate RNS-E tv input
        # print('activate rns-e true')
        regel_tv = f'cansend {can_interface} 602#09123000000000'  # Working in Audi A4 B6 (8E) 2002 - RNS-E (3R0 035 192)
        #regel_tv = f'cansend {can_interface} 602#81123000000000' #In other forums the message was 81 and not 09. Maybe needed for older RNS-E with CD/TV Button?
        os.system(regel_tv)
        #print("activate rns-e tv input message sent")
        sleep(0.5)


# send values to dashboard every 0.5 seconds
def send_to_dashboard():
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
    global send_values_to_dashboard
    global send_oap_api_mediadata_to_dashboard
    global toggle_fis1
    global toggle_fis2
    # repeat function
    while True:
        # just send if there is not toggle from rne-e longpress
        if pause_fis1 == False:
            # only send oap api mediadata (title, artist, album, position, durdation) to dis/fis if user has activated this feature
            if send_oap_api_mediadata_to_dashboard == True:
                # clear dis/fis 1st or 2nd line if you just want to show no value there
                if toggle_fis1 == 0:
                    clear_fis1 = f'cansend {can_interface} {FIS1}#{"6565656565656565"}'
                    os.system(clear_fis1)
                # send oap api media mediadata to dis/fis
                if toggle_fis1 in (1, 2, 3, 4, 5):
                    if source in (1, 3, 4):
                        if (playing == True) or (playing == False and clear_fis_if_media_is_paused == False):
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
                            regel1 = regel1.encode('iso-8859-1', errors='unidecode_fallback')
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
                            printregel1 = f'cansend {can_interface} {FIS1}#{printregel1}'
                            os.system(printregel1)
                        # if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                        elif playing == False:
                            if clear_fis_if_media_is_paused == True:
                                pause_media1 = ''
                                pause_media1 = pause_media1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                                pause_media1 = fill_up_with_spaces_align_center(pause_media1)
                                pause_media1 = convert_to_audi_ascii(pause_media1)
                                pause_media1 = f'cansend {can_interface} {FIS1}#{pause_media1}'
                                os.system(pause_media1)
                                begin1 = -1
                                eind1 = 7
                    # show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                    elif source == 2:
                        carplay_1 = 'CARPLAY'
                        carplay_1 = carplay_1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                        carplay_1 = convert_to_audi_ascii(carplay_1)
                        carplay_1 = fill_up_with_spaces_align_center(carplay_1)
                        carplay_1 = f'cansend {can_interface} {FIS1}#{carplay_1}'
                        os.system(carplay_1)

            # show text " DISABLED" in dis/fis if user has disabled the feature send_oap_api_mediadata_to_dashboard and toggle_fis1 or toggle_fis2 is 1,2,3,4,5
            elif send_oap_api_mediadata_to_dashboard == False:
                if toggle_fis1 in (1, 2, 3, 4, 5):
                    disabled_1 = 'DISABLED'
                    disabled_1 = disabled_1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    disabled_1 = convert_to_audi_ascii(disabled_1)
                    disabled_1 = fill_up_with_spaces_align_center(disabled_1)
                    disabled_1 = f'cansend {can_interface} {FIS1}#{disabled_1}'
                    os.system(disabled_1)

            if send_values_to_dashboard == True:
                # send speed to dis/fis
                if toggle_fis1 == 6:
                    regel_speed = f'{speed} KM/H'  # example: "120 KM/H"
                    regel_speed = regel_speed.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_speed = convert_to_audi_ascii(regel_speed)  #
                    regel_speed = fill_up_with_spaces_align_right(regel_speed)
                    regel_speed = f'cansend {can_interface} {FIS1}#{regel_speed}'
                    os.system(regel_speed)
                # send rpm to dis/fis
                if toggle_fis1 == 7:
                    regel_rpm = f'{rpm} RPM'  # example: "2500 RPM"
                    regel_rpm = regel_rpm.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_rpm = convert_to_audi_ascii(regel_rpm)
                    regel_rpm = fill_up_with_spaces_align_right(regel_rpm)
                    regel_rpm = f'cansend {can_interface} {FIS1}#{regel_rpm}'
                    os.system(regel_rpm)
                # send coolant temp to dis/fis
                if toggle_fis1 == 8:
                    regel_coolant = f'{coolant}�C W'  # example: "  95�C W"
                    regel_coolant = regel_coolant.encode('iso-8859-1', errors='unidecode_fallback')
                    regel_coolant = regel_coolant.hex().upper()
                    # regel_coolant = regel_coolant.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_coolant = convert_to_audi_ascii(regel_coolant)
                    regel_coolant = fill_up_with_spaces_align_right(regel_coolant)
                    regel_coolant = f'cansend {can_interface} {FIS1}#{regel_coolant}'
                    os.system(regel_coolant)
                # send raspberry pi cpu temp to fis
                if toggle_fis1 == 9:
                    cpu = round(psutil.cpu_percent())
                    if cpu == '100':  # prevent cpu usage to be three digits
                        cpu = '99'
                    cpu = str(cpu).zfill(2)
                    regel_cpu_temp = (get_cpu_temp())
                    regel_cpu_temp = str(regel_cpu_temp)
                    regel_cpu_temp = f'{cpu}% {regel_cpu_temp}�C'  # example: "25% 38�C"
                    regel_cpu_temp = regel_cpu_temp.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_cpu_temp = convert_to_audi_ascii(regel_cpu_temp)
                    regel_cpu_temp = fill_up_with_spaces_align_right(regel_cpu_temp)
                    regel_cpu_temp = f'cansend {can_interface} {FIS1}#{regel_cpu_temp}'
                    os.system(regel_cpu_temp)
            #  if user has disabled, show "DISABLED" in dis/fis
            elif send_values_to_dashboard == False:
                if toggle_fis1 in (6, 7, 8, 9):
                    disabled_1 = 'DISABLED'
                    disabled_1 = disabled_1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    disabled_1 = convert_to_audi_ascii(disabled_1)
                    disabled_1 = fill_up_with_spaces_align_center(disabled_1)
                    disabled_1 = f'cansend {can_interface} {FIS1}#{disabled_1}'
                    os.system(disabled_1)
                # just send if there is not toggle from rne-e longpress
        if pause_fis2 == False:
            if send_oap_api_mediadata_to_dashboard == True:
                if toggle_fis2 == 0:
                    clear_fis2 = f'cansend {can_interface} {FIS2}#{"6565656565656565"}'
                    os.system(clear_fis2)
                # send oap api media mediadata to dis/fis
                if toggle_fis2 in (1, 2, 3, 4, 5):
                    if source in (1, 3, 4):
                        if (playing == True) or (playing == False and clear_fis_if_media_is_paused == False):
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
                            regel2 = regel2.encode('iso-8859-1', errors='unidecode_fallback')
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
                            printregel2 = f'cansend {can_interface} {FIS2}#{printregel2}'
                            os.system(printregel2)
                        # if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                        elif playing == False:  # if media is paused clear fis. Remove this whole elif if you still want to show (and scroll) media metadata
                            if clear_fis_if_media_is_paused == True:
                                pause_media2 = ''
                                pause_media2 = pause_media2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                                pause_media2 = convert_to_audi_ascii(pause_media2)
                                pause_media2 = fill_up_with_spaces_align_center(pause_media2)
                                pause_media2 = f'cansend {can_interface} {FIS2}#{pause_media2}'
                                os.system(pause_media2)
                                begin1 = -1
                                eind1 = 7
                    # show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                    elif source == 2:  # show text " CARPLAY" in dis/fis to source 2 = Apple Carplay. Note: carlinkit usb dongle doesn't provide any data (title, artist etc.)
                        carplay_2 = 'CARPLAY'
                        carplay_2 = carplay_2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                        carplay_2 = convert_to_audi_ascii(carplay_2)
                        carplay_2 = fill_up_with_spaces_align_center(carplay_2)
                        carplay_2 = f'cansend {can_interface} {FIS2}#{carplay_2}'
                        os.system(carplay_2)
            # show text " DISABLED" in dis/fis if user has disabled the feature send_oap_api_mediadata_to_dashboard and toggle_fis1 or toggle_fis2 is 1,2,3,4,5
            elif send_values_to_dashboard == False:
                if toggle_fis2 in (1, 2, 3, 4, 5):
                    disabled_2 = 'DISABLED'
                    disabled_2 = disabled_2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    disabled_2 = convert_to_audi_ascii(disabled_2)
                    disabled_2 = fill_up_with_spaces_align_center(disabled_2)
                    disabled_2 = f'cansend {can_interface} {FIS2}#{disabled_2}'
                    os.system(disabled_2)

            if send_values_to_dashboard == True:
                # send speed to dis/fis
                if toggle_fis2 == 6:
                    regel_speed = f'{speed} KM/H'  # example: "120 KM/H"
                    regel_speed = regel_speed.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_speed = convert_to_audi_ascii(regel_speed)
                    regel_speed = fill_up_with_spaces_align_right(regel_speed)
                    regel_speed = f'cansend {can_interface} {FIS2}#{regel_speed}'
                    os.system(regel_speed)
                # send rpm to dis/fis
                if toggle_fis2 == 7:
                    regel_rpm = f'{rpm} RPM'  # example: "2500 RPM"
                    regel_rpm = regel_rpm.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_rpm = convert_to_audi_ascii(regel_rpm)
                    regel_rpm = fill_up_with_spaces_align_right(regel_rpm)
                    regel_rpm = f'cansend {can_interface} {FIS2}#{regel_rpm}'
                    os.system(regel_rpm)
                # send coolant temp to dis/fis
                if toggle_fis2 == 8:
                    regel_coolant = f'{coolant}�C W'  # example: "  95�C W"
                    regel_coolant = regel_coolant.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_coolant = convert_to_audi_ascii(regel_coolant)
                    regel_coolant = fill_up_with_spaces_align_right(regel_coolant)
                    regel_coolant = f'cansend {can_interface} {FIS2}#{regel_coolant}'
                    os.system(regel_coolant)
                # send raspberry pi cpu temp to fis
                if toggle_fis2 == 9:
                    cpu = round(psutil.cpu_percent())
                    if cpu == '100':  # prevent cpu usage to be three digits
                        cpu = '99'
                    cpu = str(cpu).zfill(2)
                    regel_cpu_temp = (get_cpu_temp())
                    regel_cpu_temp = str(regel_cpu_temp)
                    regel_cpu_temp = f'{cpu}% {regel_cpu_temp}�C'  # example: "25% 38�C"
                    regel_cpu_temp = regel_cpu_temp.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    regel_cpu_temp = convert_to_audi_ascii(regel_cpu_temp)
                    regel_cpu_temp = fill_up_with_spaces_align_right(regel_cpu_temp)
                    regel_cpu_temp = f'cansend {can_interface} {FIS2}#{regel_cpu_temp}'
                    os.system(regel_cpu_temp)
            # show text " DISABLED" in dis/fis if user has disabled the feature send_oap_api_mediadata_to_dashboard and toggle_fis1 or toggle_fis2 is 1,2,3,4,5
            elif send_values_to_dashboard == False:
                if toggle_fis2 in (6, 7, 8, 9):
                    disabled_2 = 'DISABLED'
                    disabled_2 = disabled_2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    disabled_2 = convert_to_audi_ascii(disabled_2)
                    disabled_2 = fill_up_with_spaces_align_center(disabled_2)
                    disabled_2 = f'cansend {can_interface} {FIS2}#{disabled_2}'
                    os.system(disabled_2)
        # just send to dis/fis every 0.5 seconds. Needed for scrolling speed if values are bigger than 8 characters.
        sleep(0.5)

# send hands free message to avoid flickering from dashboard 1st and 2nd line
def send_hands_free_activation_message():
    while True:
        # print('In sendcan3')
        regel_hands_free = f'cansend {can_interface} 665#0300'
        os.system(regel_hands_free)
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

# convert hex to audi ascii
def convert_to_audi_ascii(content=''):
    hex_to_audi_ascii = {
        '61': '01', '62': '02', '63': '03', '64': '04', '65': '05',
        '66': '06', '67': '07', '68': '08', '69': '09', '6A': '0A',
        '6B': '0B', '6C': '0C', '6D': '0D', '6E': '0E', '6F': '0F',
        '70': '10', 'B0': 'BB', 'E4': '91', 'F6': '97', 'FC': '99',
        'C4': '5F', 'D6': '60', 'DC': '61', 'DF': '8D', '5F': '66',
        'A3': 'AA', 'A7': 'BF', 'A9': 'A2', 'B1': 'B4', 'B5': 'B8',
        'B9': 'B1', 'BA': 'BB', 'C8': '83', 'E8': '83', 'C9': '82',
        'E9': '82', '20': '65'
    }

    result = ''
    for i in range(0, len(content), 2):
        pair = content[i:i+2]
        result += hex_to_audi_ascii.get(pair, pair)
    return result

# fill up content with spaces if the content has less than 8 digits. Filled up with hex 20 means the content in dis/fis will be aligned centered
def fill_up_with_spaces_align_center(content=''):
    lengte = len(content)
    if lengte < 16:
        content = (f'2020202020202020'[:16-lengte] + content)
    return content

# fill up content with spaces if the content has less than 8 digits. Filled up with hex 65 means the content in dis/fis will be aligned right
def fill_up_with_spaces_align_right(content=''):  # content right aligned
    lengte = len(content)
    if lengte < 16:
        content = (f'6565656565656565'[:16-lengte] + content)
    return content


def measure_speed():
    start_time = None
    elapsed_time = 0
    measure_done = 0

    while True:

        if speed > lower_speed:
            # Starte die Messung, falls sie noch nicht gestartet wurde
            if start_time is None:
                start_time = time.time()
            if measure_done == 0:
                #print("{:.1f}".format(time.time() - start_time))
                if toggle_fis1 == 10:
                    print_measure1 = "{:.1f}".format(time.time() - start_time)
                    print_measure1 = "{0} s".format(str(print_measure1))
                    print_measure1 = print_measure1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    print_measure1 = fill_up_with_spaces_align_center(print_measure1)
                    print_measure1 = f'cansend {can_interface} {FIS1}#{print_measure1}'
                    os.system(print_measure1)
                if toggle_fis2 == 10:
                    print_measure2 = "{:.1f}".format(time.time() - start_time)
                    print_measure2 = "{0} s".format(str(print_measure2))
                    print_measure2 = print_measure2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    print_measure2 = fill_up_with_spaces_align_center(print_measure2)
                    print_measure2 = f'cansend {can_interface} {FIS2}#{print_measure2}'
                    os.system(print_measure2)

            # Wenn die Geschwindigkeit 100 km/h erreicht hat, breche die Messung ab und gib die gemessene Zeit aus
            if speed >= upper_speed and measure_done == 0:
                measure_done = 1
                elapsed_time = time.time() - start_time
                elapsed_time_formatted = "{:.1f}".format(elapsed_time)
                print("Die Zeit von",lower_speed,"-",upper_speed,"km/h zu beschleunigen betrug {} Sekunden.".format(elapsed_time_formatted))
                #print(elapsed_time_formatted,"s")
                start_time = None
                elapsed_time = 0
            if measure_done == 1:
                if toggle_fis1 == 10:
                    print_measure_result1 = elapsed_time_formatted
                    print_measure_result1 = "{0} s".format(str(print_measure_result1))
                    print_measure_result1 = print_measure_result1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    print_measure_result1 = fill_up_with_spaces_align_center(print_measure_result1)
                    print_measure_result1 = f'cansend {can_interface} {FIS1}#{print_measure_result1}'
                    os.system(print_measure_result1)
                if toggle_fis2 == 10:
                    print_measure_result2 = elapsed_time_formatted
                    print_measure_result2 = "{0} s".format(str(print_measure_result2))
                    print_measure_result2 = print_measure_result2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                    print_measure_result2 = fill_up_with_spaces_align_center(print_measure_result2)
                    print_measure_result2 = f'cansend {can_interface} {FIS2}#{print_measure_result2}'
                    os.system(print_measure_result2)
                sleep(0.5)
            sleep(0.1)


        else:
        #elif speed <= lower_speed:
            # Setze die gemessene Zeit zur�ck, wenn die Geschwindigkeit wieder 0 km/h erreicht
            start_time = None
            elapsed_time = 0
            measure_done = 0

            if toggle_fis1 == 10:
                measure_reset1 = '0.0 s'
                measure_reset1 = measure_reset1.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                measure_reset1 = fill_up_with_spaces_align_center(measure_reset1)
                measure_reset1 = f'cansend {can_interface} {FIS1}#{measure_reset1}'
                os.system(measure_reset1)
            if toggle_fis2 == 10:
                measure_reset2 = '0.0 s'
                measure_reset2 = measure_reset2.encode('iso-8859-1', errors='unidecode_fallback').hex().upper()
                measure_reset2 = fill_up_with_spaces_align_center(measure_reset2)
                measure_reset2 = f'cansend {can_interface} {FIS2}#{measure_reset2}'
                os.system(measure_reset2)
            sleep(0.5)

# Declare threads
t1 = Thread(target=read_on_canbus)
if activate_rnse_tv_input == True:
    t2 = Thread(target=send_tv_input_activation_message)
if send_oap_api_mediadata_to_dashboard == True or change_dark_mode_by_car_light == True:
    t3 = Thread(target=EventHandler)
if send_values_to_dashboard == True or send_oap_api_mediadata_to_dashboard == True:
    t4 = Thread(target=send_to_dashboard)
    t5 = Thread(target=send_hands_free_activation_message)
if send_values_to_dashboard == True:
    t6 = Thread(target=get_cpu_temp)
t7 = Thread(target=main)
t8 = Thread(target=measure_speed)

# Start/call threads
if __name__ == '__main__':
    t1.start()
    if activate_rnse_tv_input == True:
        t2.start()
    if send_values_to_dashboard == True:
        t6.start()
    if send_values_to_dashboard == True or send_oap_api_mediadata_to_dashboard == True:
        t4.start()
        t5.start()
    if send_oap_api_mediadata_to_dashboard == True or change_dark_mode_by_car_light == True:
        #sleep(5)
        t3.start()
        t7.start()
    t8.start()
