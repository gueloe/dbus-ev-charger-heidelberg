# dbus-ev-charger-heidelberg

⚠️ Work in progress!!!! ⚠️

This repo integrates a Heidelberg Charge Control  Wallbox into a Victron Venus OS device (e.g. Cerbo GX). The integration
is using the Victron evcharger model (com.victronenergy.evcharger) and is basically mimic a Victron wallbox.
Therefore switching between 1-phase and 3-phase charging is not supported, since it is not supported by Victrons wallbox.

It is possible to see the current charging status (not connected, connected, rfid missing, charging etc.) and you can control the maximum charging current (Settings->Max charging current).
As charge mode you can select between manual and automatic (scheduled is not implemented right now). Manual mode is basically the normal charging mode where you can control the charging current and start/stop the charging process.
In automatic mode pv excess mode is selected. So this option is only available if pv excess mode is available at the WARP charger. If the wallbox is a WARP Charger Pro wallbox also the energy measurements are shown.

## Setup
install pip:

opkg update

opkg install python3-pip

then install pip3:

pip3 install minimalmodbus


Copy the files to the data folder `/data/` e.g. `/data/dbus-ev-charger-heidelberg`.
Afterwards modify the `config.ini` file such that it points to your heidelberg charger.
After that call the install.sh script. 



## Discussions on Tinkerunity (forum)


## Credit
This project is based on the dbus-warp-charger integration repo: https://github.com/vikt0rm/dbus-goecharger
