from __future__ import print_function
import os
import sys
import binascii
import re
import can
from time import sleep
from threading import Thread

#####################################################

#  set here, what you want to have active
#  PLEASE ONLY USE 'true' or 'false'

#  MFSW (multi function steering wheel) will autodetect if it is installed

activate_rnse_tv_input = 'false'
read_and_set_time_from_dis = 'true'
control_pi_by_rns_e_buttons = 'true'
reversecamera_by_reversegear = 'false'
shutdown_by_ignition_off = 'false'
shutdown_by_pulling_key = 'false'

reversecamera_turn_off_delay = '5'  # in seconds
shutdown_delay = '5'  # in seconds

#####################################################

can_interface = 'can0'
bus = can.interface.Bus(can_interface, bustype='socketcan')
message = bus.recv()


def eprint(*args, **kwargs):
    """

    :param args:
    :param kwargs:
    """
    print(*args, file=sys.stderr, **kwargs)


eprint('script starting')

# install pynput if the module was not found
try:
    from pynput.keyboard import Key, Controller
except ModuleNotFoundError:
    eprint('pynput is not installed - please connect the pi to the internet and install pynput with "pip3 install pynput" and "sudo pip3 install pynput"')
keyboard = Controller()

# deactivate camera functions if there is an error importing picamera - script doesn't crash then
if reversecamera_by_reversegear == 'true':
    try:
        from picamera import PiCamera
    except ModuleNotFoundError as e:
        eprint('picamera ist not installed - is not installed - please connect the pi to the internet and install picamera with "pip3 install picamera" and "sudo pip3 install picamera"')
    except ImportError as e:
        reversecamera_by_reversegear = 'false'
        pass
    try:
        camera = PiCamera()
    except Exception as e:
        eprint("camera is not connected or has problems - disabling all reversecamera features")
        reversecamera_by_reversegear = 'false'  # deactivate reversecamera features if the camera is not working
        pass


def read_from_canbus(gear):
    """

    :param gear:
    """
    try:
        var = 1
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
        for message in bus:
            if var == 1:
                canid = str(hex(message.arbitration_id).lstrip('0x').upper())
                msg = binascii.hexlify(message.data).decode('ascii').upper()

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

                # read time from dis (driver information system) and set the time on raspberry pi.
                elif canid == '623':
                    if read_and_set_time_from_dis == 'true':  # read date and time from dis and set on raspberry pi
                        if tmset == 0:
                            msg = re.sub('[\\s+]', '', msg)
                            date = 'sudo date %s%s%s%s%s.%s' % (
                                msg[10:12], msg[8:10], msg[2:4], msg[4:6], msg[12:16], msg[6:8])
                            os.system(date)
                            eprint('Date and time set on raspberry pi')
                            tmset = 1

                elif canid == '661':
                    if msg == '8101123700000000' or msg == '8301123700000000':
                        if tv_mode_active == 0:
                            keyboard.press('X')  # play media, if rns-e ist (back) on tv mode
                            keyboard.release('X')
                            eprint('rns-e is (back) in tv mode - play media - Keyboard: "X" - OpenAuto: "play"')
                            tv_mode_active = 1
                    else:
                        if tv_mode_active == 1:
                            keyboard.press('C')  # pause media, if rns-e left tv mode
                            keyboard.release('C')
                            eprint(
                                'rns-e is not in tv mode (anymore) - pause media - Keyboard: "C" - OpenAuto: "pause"')
                            tv_mode_active = 0

                # read mfsw button presses if mfsw ist detected and rns-e tv input is active
                elif canid == '5C3':
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
                            eprint("MFSW " + str(
                                carmodel) + ": scan wheel up - Keyboard: 1 - OpenAuto scroll left")
                            press_mfsw = 0

                        elif (carmodel == '8E' and msg == '3905') or (
                                carmodel == '8P' and msg == '390C') or (
                                carmodel == '8J' and msg == '390C'):
                            keyboard.press('2')
                            keyboard.release('2')
                            eprint("MFSW " + str(
                                carmodel) + ": scan wheel down - Keyboard: 2 - OpenAuto: Scroll right")
                            press_mfsw = 0

                        elif (carmodel == '8E' and msg == '3908') or (
                                carmodel == '8P' and msg == '3908') or (
                                carmodel == '8J' and msg == '3908'):
                            press_mfsw += 1
                        elif (msg == '3900' or msg == '3A00') and press_mfsw > 0:
                            if press_mfsw == 1:
                                keyboard.press(Key.enter)
                                keyboard.release(Key.enter)
                                eprint("MFSW " + str(
                                    carmodel) + ": scan wheel shortpress - Keyboard: ENTER - OpenAuto: Select")
                                press_mfsw = 0
                            elif press_mfsw >= 2:
                                keyboard.press(Key.esc)
                                keyboard.release(Key.esc)
                                eprint("MFSW " + str(
                                    carmodel) + ": scan wheel longpress - Keyboard: ESC - OpenAuto: Back")
                                press_mfsw = 0
                        elif msg == '3900' and press_mfsw == 0:
                            nextbtn = 0
                            prev = 0


                # read reverse gear message to activate the reverse camera
                elif canid == '351':
                    if reversecamera_by_reversegear == 'true':  # read reverse gear message and start reversecamera
                        if msg[0:2] == '00' and gear == 1:
                            gear = 0
                            eprint("forward gear engaged - stopping reverse camera with", reversecamera_turn_off_delay,
                                   "seconds delay")
                            sleep(int(reversecamera_turn_off_delay))  # turn camera off with 5 seconds delay
                            camera.stop_preview()
                        elif msg[0:2] == '02' and gear == 0:
                            gear = 1
                            eprint("reverse gear engaged - starting reverse camera")
                            camera.start_preview()

                # read RNS-E button presses to control Raspberry Pi/OpenAuto Pro
                elif canid == '461':
                    if control_pi_by_rns_e_buttons == 'true':  # read can messages from rns-e button presses
                        if msg == '373001004001':
                            keyboard.press('1')
                            keyboard.release('1')
                            eprint('RNS-E: wheel button scrolled LEFT - Keyboard: "1" - OpenAuto: "Scroll left"')

                        elif msg == '373001002001':
                            keyboard.press('2')
                            keyboard.release('2')
                            eprint('RNS-E: wheel button scrolled RIGHT - Keyboard: "2" -  OpenAuto: "Scroll right"')

                        elif msg == '373001400000':  #RNS-E: button UP pressed
                            up += 1
                        elif msg == '373004400000' and up > 0:  #RNS-E: button UP released
                            if up <= 4:
                                keyboard.press(Key.up)
                                keyboard.release(Key.up)
                                eprint('RNS-E: button up shortpress - Keyboard: "UP arrow" - OpenAuto: "Navigate up"')
                                up = 0
                            elif up > 4:
                                keyboard.press('P')
                                keyboard.release('P')
                                eprint('RNS-E: button up - Keyboard: "P" -  OpenAuto: "Answer call/Phone menu"')
                                up = 0

                        elif msg == '373001800000':  # RNS-E: button DOWN pressed
                            down += 1
                        elif msg == '373004800000' and down > 0:  # RNS-E: button DOWN released
                            if down <= 4:
                                keyboard.press(Key.down)
                                keyboard.release(Key.down)
                                eprint(
                                    'RNS-E: button down shortpress - Keyboard: "DOWN arrow" -  OpenAuto: "Navigate Down"')
                                down = 0
                            elif down > 4: # just react if function is enabled by user
                                keyboard.press(Key.f2)
                                keyboard.release(Key.f2)
                                eprint(
                                    'RNS-E: button up longpress - Keyboard: "F2" - OpenAuto: "Toggle Android Auto night mode"')
                                down = 0
                            
                        elif msg == '373001001000':  # RNS-E: wheel pressed
                            select += 1
                        elif msg == '373004001000' and select > 0:  # RNS-E: wheel released
                            if select <= 4:
                                keyboard.press(Key.enter)
                                keyboard.release(Key.enter)
                                eprint('RNS-E: wheel shortpress - Keyboard: "ENTER" on keyboard-  OpenAuto: "Select"')
                                select = 0
                            elif select > 4:
                                keyboard.press('B')
                                keyboard.release('B')
                                eprint('RNS-E: wheel longpress - Keyboard: "B" -  OpenAuto: "Toggle play/pause"')
                                select = 0

                        elif msg == '373001000200':  # RNS-E: return button pressed
                            back += 1
                        elif msg == '373004000200' and back > 0:  # RNS-E: return button released
                            if back <= 4:
                                keyboard.press(Key.esc)
                                keyboard.release(Key.esc)
                                eprint('RNS-E return button shortpress - Keyboard "ESC" -  OpenAuto: "Back"')
                                back = 0
                            elif back > 4:
                                keyboard.press('O')
                                keyboard.release('O')
                                eprint('RNS-E: return button longpress - Keyboard: "O" -  OpenAuto: "End phone call"')
                                back = 0


                        elif msg == '373001020000':  # RNS-E: next track button pressed
                            nextbtn += 1
                        elif msg == '373004020000' and nextbtn > 0:  # RNS-E: next track button released
                            if nextbtn <= 4:
                                keyboard.press('N')
                                keyboard.release('N')
                                eprint('RNS-E: next track shortpress - Keyboard: "N" -  OpenAuto: "Next track"')
                                nextbtn = 0
                            elif nextbtn > 4:
                                keyboard.press(Key.ctrl)
                                keyboard.press(Key.f3)
                                keyboard.release(Key.ctrl)
                                keyboard.release(Key.f3)
                                eprint(
                                    'RNS-E: next track longpress - Keyboard: "CTRL+F3" - OpenAuto: "Toggle application"')
                                nextbtn = 0

                        elif msg == '373001010000':  # RNS-E: previous track button pressed
                            prev += 1
                        elif msg == '373004010000' and prev > 0: # RNS-E: previous track button released
                            if prev <= 4:
                                keyboard.press('V')
                                keyboard.release('V')
                                eprint(
                                    'RNS-E: previous track button shortpress - Keyboard: "V" -  OpenAuto: "Previous track"')
                                prev = 0
                            elif prev > 4:
                                keyboard.press(Key.f12)
                                keyboard.release(Key.f12)
                                eprint(
                                    'RNS-E: previous track longpress - Keyboard: "F12" - OpenAuto: "Bring OpenAuto Pro to front"')
                                prev = 0

                        elif msg == '373001000100':  # RNS-E: setup button pressed
                            setup += 1
                        elif msg == '373004000100' and setup > 0:  # RNS-E: setup button released
                            if setup <= 6:
                                keyboard.press('M')
                                keyboard.release('M')
                                eprint('RNS-E: setup button shortpress - Keyboard: "M" -  OpenAuto: "Voice command"')
                                setup = 0
                            elif setup > 6:
                                eprint("RNS-E: setup button longpress - shutting down raspberry pi")
                                os.system('sudo shutdown -h now')
                                setup = 0


                # read ignition message, or pulling key message to shut down the raspberry pi
                elif canid == '271':
                    if shutdown_by_ignition_off == 'true' or shutdown_by_pulling_key == 'true':
                        if msg[0:2] == '11' and shutdown_by_ignition_off == 'true':
                            eprint("ignition off message detected - system will shutdown in", shutdown_delay, "seconds")
                            sleep(
                                int(shutdown_delay))  # defined delay to shutdown the pi
                            eprint("system is shutting down now")
                            os.system('sudo shutdown -h now')
                        elif msg[0:2] == '10' and shutdown_by_pulling_key == 'true':
                            eprint("pulling key message detected - system will shutdown in", shutdown_delay, "seconds")
                            sleep(
                                int(shutdown_delay))  # defined delay to shutdown the pi
                            eprint("system is shutting down now")
                            os.system('sudo shutdown -h now')


    except Exception as e:
        eprint("error in function read_from_canbus:", str(e))

    except KeyboardInterrupt as e:
        if reversecamera_by_reversegear == 'true':
            camera.stop_preview()
            camera.close()
        eprint("Script killed by KeyboardInterrupt!")
        exit(1)

gear = 0


def sendcan():
    if activate_rnse_tv_input == 'true':  # Send message to activate RNS-E tv input
        os.system("cansend can0 602#09123000000000") # Working in Audi A4 B6 (8E) 2002 - RNS-E (3R0 035 192)
        #os.system("cansend can0 602#81123000000000") #In other forums the message was 81 and not 09. Maybe needed for older RNS-E with CD/TV Button?
        eprint("activate rns-e tv input message sent")
        sleep(0.5)
    sendcan()


if __name__ == '__main__':
    Thread(target=sendcan).start()
    Thread(target = read_from_canbus(gear)).start()
from __future__ import print_function
