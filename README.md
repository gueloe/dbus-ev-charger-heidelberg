# dbus-ev-charger-heidelberg

⚠️ Work in progress!!!! ⚠️

This repo integrates a Heidelberg Charge Control  Wallbox into a Victron Venus OS device (e.g. Cerbo GX).
The integration is using the Victron evcharger model (com.victronenergy.evcharger)
and is basically mimic a Victron wallbox.


It is possible to see the current charging status (not connected, connected, charging etc.) and you can control 
the charging current.
As charge mode you can select between manual and automatic (scheduled is not implemented right now).
Manual mode is basically the normal charging mode where you can control the charging current and start/stop the charging process.
Automatic mode is implemented in a node-red flow.
It sets the "W/XX/evcharger/YY/SetCurrent" Value over MQTT. XX=VRM Portal ID  YY=DEVICE INSTANCE
Automatic is used for Charge on Solar.
The flow uses akt. PV POWER, BAT POWER, GRID POWER, BAT SOC and the number of used Phases for controlling the EV POWER.

### Software

To provide the software on your Venus OS, execute there these commands:

````
wget https://github.com/gueloe/dbus-ev-charger-heidelberg/archive/refs/heads/main.zip
unzip main.zip "dbus-ev-charger-heidelberg-main/*" -d /data
rm main.zip
mv /data/dbus--ev-charger-heidelberg-main/ /data/dbus-ev-charger-heidelberg/
````


Afterwards modify the `config.ini` file such that it points to your heidelberg charger.
After that call the install.sh script. 

## Configuration

You have to edit `config.ini`. Please note the comments there as explanation!


| Config value        | Explanation   |
|-------------------- | ------------- |
| Logging | set loglevel for `/var/log/dbus-d0-smartmeter/current`. Possible values among others are `DEBUG`, `INFO`, `WARING` |
| SignOfLiveLog | if >0, interval in minutes to give stats |
| Deviceinstance | device instance of dbus evcharger |
| Position | Position 0: ac out, 1: ac in |
| Devicename within [ModbusRTU]-Section | provides the correct name listed within /dev/serial/by-id/. |
| DebugModbus within [ModbusRTU]-Section | 0=OFF 1=On Shows Information of ModbusCalls |
 



With the scripts in this repo it should be easy possible to install, uninstall, restart a service that connects the Heidelberg Wallbox to the VenusOS and GX devices from Victron. 



## Inspiration
This project is my first on GitHub and with the Victron Venus OS, so I took some ideas and approaches from the following projects - many thanks for sharing the knowledge:
- https://github.com/schollex/dbus-d0-smartmeter
- https://github.com/Louisvdw/dbus-serialbattery
- https://github.com/vikt0rm/dbus-goecharger
- https://github.com/JuWorkshop/dbus-evsecharger
- https://github.com/victronenergy/dbus-modbus-client

## How it works
- plug the vehicle
- if you set ev to Manual Mode, you can choose the Current over the vrm settings.
- in automode it is possible to use differrent parameters 
    - PV POWER to Start charging
    - MAX EV energy to charge
    - MX GRID ENERGY USED (STOPS IF PV < MIN EV POWER and BAT is EMPTY and MAX_GRID_ENERGY is used)

to set the maximum EV POWER. 
In normal auto mode, the flow tries to adjust the EV POWER, so that the current PV surplus is charged

    
### My setup
- Heidelberg Energy Control Wallbox
  - 3-Phase installation (normal for Germany)
  - Connected to RASP PI4 over RS485 Adapter
- Victron Energy RASP PI4 Venus OS - Firmware v3.53
  - IR Sensor (USB)
  - DIY AKKU 16 KW/h (TTL-USB), MP2 5000 (MK3), HUAWEI PV INVERTER (MODBUS TCP) 


### Details / Process
As mentioned above the script is inspired by @schollex dbus-d0-smartmeter implementation for using serial connections without the usage of 
etc/udev/rules.d/serial-starter.rules and ignore approach.
@vikt0rm and @JuWorkshop for ev handling, @victronenergy for modbus handling and @Louisvdw for dbus handling

So what is the script doing:
- Running as a service
- connecting to DBus of the Venus OS com.victronenergy.ev and to Heidelberg Energy Controll Wallbox over USB-RS485 Adapter.
- The service uses minimalmodbus for communication to the wallbox (Easy-to-use Modbus RTU and Modbus ASCII implementation for Python - https://pypi.org/project/minimalmodbus/)

- Info to heidelberg modbus https://www.amperfied.de/wp-content/uploads/2023/03/20220809_AMP-Erweiterte-ModBus-Registerbeschreibung.pdf