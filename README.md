# OctoPrint Anywhere

Remote monitoring and control of your 3D printers. ANYWHERE. ON YOUR PHONE. No more port forwarding or VPN.

OctoPrint Anywhere streams the webcam feed, bed/nozzle temperature, and other critical status from your 3D printer to your phone via the cloud. Now you don't have to be on the same WiFi network as the OctoPrint to monitor and control your 3D printer.

## Highlights of OctoPrint Anywhere

* Webcam feed on your phone. Extremely low latency (usually <3s).
* Real-time feed on temperatures and status of active print. Pause or cancel the active print.
* Bandwidth-efficiency. Streams data only when you are watching. Data transmission immediately stops when browser tab goes to background.
* Sharing realtime webcam feed with your friends with an encrypted link!
* Access to your timelapses anywhere so that you can show them off! Sharing them too!
* Remote control of X/Y/Z movement.
* Seeing the IP address of your OctoPrint.
* Check status of all your 3D printers on the same page at a glance.
* Many more to come...

## Screenshots

<p align="center">
  <img width="460" height="300" src="https://github.com/kennethjiang/OctoPrint-Anywhere/blob/master/jpgs1/02.jpg?raw=true" />
</p>

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/kennethjiang/OctoPrint-Anywhere/archive/master.zip

After install, go to:

    https://www.getanywhere.io/pub

Any time you wish to see and control your Octoprint from outside your local network.

## Contribute

1. Clone OctoPrint-Anywhere

```bash
git clone https://github.com/kennethjiang/OctoPrint-Anywhere.git
```

2. Launch a Vagrant VM. This step will take about 10 minutes or longer.

```
cd OctoPrint-Anywhere
vargrant up
```

3. Log into the Vagrant VM

```
vagrant ssh
```

4. Start OctoPrint with OctoPrint Anywhere pre-installed as develop mode. These commands need to run in the Vagrant VM.

```
cd /vagrant
./start.sh
```

5. On your laptop, go to http://192.168.134.30:5000/ to access the OctoPrint running on the Vagrant VM.
