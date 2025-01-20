# dbus-ev-charger-heidelberg
Integrate Heidelberg Enegy Controll Wallbox into Victron Venus OS

Purpose
This script supports reading EV charger values from Heidelberg Enegy Controll Wallbox over Modbus RTU. Writing values is supported for "Charging current"

## Introduction and motivation


This project/script will catch the received data and supply it as external ev Charger to Venus OS.


> **Attention:**
> This project is corrently not well documented. Thus, you should have advanced Venus OS and Linux experience.

## Preparation

### Hardware

You need

 
### Software

To provide the software on your Venus OS, execute there these commands:

````
wget https://github.com/gueloe/dbus-ev-charger-heidelberg/archive/refs/heads/main.zip
unzip main.zip "dbus-ev-charger-heidelberg-main/*" -d /data
rm main.zip
mv /data/dbus-ev-charger-heidelberg-main/ /data/dbus-ev-charger-heidelberg/
````
## Configuration

You have to edit `config.ini`. Please note the comments there as explanation!


| Config value        | Explanation   |
|-------------------- | ------------- |
| Logging | set loglevel for `/var/log/dbus-d0-smartmeter/current`. Possible values among others are `DEBUG`, `INFO`, `WARING` |
| SignOfLiveLog | if >0, interval in minutes to give stats (= number of received correct SML-data) |
| CustomName | user-friendly name for the gridmeter within the Venus web-GUI |
| TimeoutInterval | if no valid data is received within this millisencods-interval, the DBUS-service-property Connected will be set to 0 |
| ExitOnTimeout | if set to `1` instead of `0`, the script will terminate itself which erases service from DBUS. This is indicated as "not connected" within the web-GUI |
| ExitAfterHours | if >0. the script will terminate itself after these hours |
| ChangeSmartmeter | if set to `1` instead of `0`, DBUS-property com.victronenergy.settings/Settings/CGwacs/RunWithoutGridMeter respectivly the web-GUI-setting Settings > ESS > Grid Metering is changed. If { no } grid metering can be done, property is set to `1` { `0` } respectivly GUI to `Inverter/Charger` { `External meter` }. Without this, e.g. if grid metering is stall, ESS would work on old power-assumptions. If set to `External meter` and the battery is fully charged, Victron OS would stop MPPT from producing power. With setup `Inverter/Charger`, MPPT is still producing power which is completly fed in to AC by Multiplus. |
| PostRawdata | if set to `1` instead of `0`, SML-rawdata is post to DBUS-gridmeter-property `/rawdata` |
| Regex | Here is the magic. See Debugging-section below. |
| ReadInterval within [USB]-Section | millisecond-interval the script reads data from TTY. This should be obviously <1000. Otherwise, the TTY-buffer would fill up resulting in outdated data |
| Devicename within [USB]-Section | provides the correct name listed within /dev/serial/by-id/. This TTY is only used when the scipt is manually started without command-line-arguments. |

You have to set the `DEV`-variable within `service/run` to your USB-TTY-adapter. E.g. for me, it's `DEV='/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0'`. Because `service/run` will identify the corresponding /dev/ttyUSB-device, stop the serial-starter for this TTY and start the script with this TTY as command-line-argument.
 
## Usage

I refer to https://github.com/henne49/dbus-opendtu#usage

Additionally as my script handles with a serial-device, special preparation is necessary. For details, see https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus#3-installing-a-driver

First, I took the ``etc/udev/rules.d/serial-starter.rules`` and ``ignore`` approach. But this file is on a RO-mountpoint. You have to remount as RW to edit the file. This modification also gets lost during a firmware update. Therefore I switch to this implementation...

You do not have to modify serial-starter.rules beause `service/run` stops the corresponding `serial-starter`-process. This frees the TTY from `serial-starter` so that my script can correctly read from TTY.

## Starting and Debugging

If you have good luck, just run `install.sh` and the charger appears within the Venus-GUI.

`/var/log/dbus-ev-charger-heidelberg/current` will look like this:

[...]
````
You'll get stats every `SignOfLiveLog` minutes - see the 15 min interval of the last log lines above.

If you see something like this

````

````


Otherwise, you shoud set `Logging=Debug`. After modifying `config.ini` you have to execute `restart.sh` to apply. Then, the log could look like this (some parts are truncated):

````

[...]
````


