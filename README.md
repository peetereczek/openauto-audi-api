# openauto-audi-api
### **Description**
BlueWave Studio [OpenAuto Pro](https://bluewavestudio.io/) API bridge development for AUDI cars to use CAN bus communication over RaspberryPi PiCAN2 interface.
<br />
Project dedicated to develop and support additional OpenAuto features over exposed APIs
<br />
### **Tested cars**
Audi A3 8P FL 2012
<br />
### **Installation**
1. Install dependent Python packages:
```
sudo pip install pynput
sudo pip3 install pynput
sudo pip install picamera
sudo pip3 install picamera
sudo pip install python-can
sudo pip3 install python-can
```
2. Download the script to you Pi with OpenAuto
3. Move the script to a folder you want. Example:
```
/home/pi/scripts/
```
4. Give the script permissions to run/execute. Example:
```
sudo chmod +x /home/pi/scripts/read_from_canbus.py
```
5. Edit the upper section in the script to activate the features you want to use. Avaliable options:
 - read date and time from dis/fis and set it on Raspberry Pi. Recommended, if Raspberry Pi has no internet connection in the car.
 - read reverse gear message from canbus to activate reversecamer. Reversecamera must be connected to Raspberry Pi, not to RNS-E or av-input modules for RNS-E.
 - read longpress down left rns-e button near wheel to activate reversecamera manualy.
 - control rns-e by reading rns-e button presses. This works on the whole system and not only on openauto pro gui. Im using that in kodi to navigate too (see kodi keymap editor).
 - read ignition off message to shutdown the raspberry pi. Should be only relevant if you have permanent power to raspberry pi.
 - read pulling key message to shutdown the raspberry pi. Should be only relevant if you have permanent power to raspberry pi.
 - if reversecamera is on by gear detection, and forward gear gets detected, turn the camera off with delay. Better for parking situations :-)
 - set delay for turning the raspberry pi off after ignition got detected as off
6. Add script as part of OpenAuto services. Edit file '/home/pi/.openauto/config/openauto_applications.ini'
```
[Application_<x>]
Name=CAN bus scripts
Path=/usr/bin/python3 /home/pi/scripts/read_from_canbus.py
IconPath=/home/pi/.openauto/icons/rnse_button.svg
Arguments=
Autostart=true
```
### **Exclusion**
In case of API support, suggestions or any other queries related to core API, please visit OpenAuto API [project](https://github.com/bluewave-studio/openauto-pro-api) or [community forum](https://www.bluewavestudio.io/community/).
### **Credits**
@noobychris for pushing thinks forward
