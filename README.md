# OctoPrint Anywhere

OctoPrint Anywhere extends your control beyond the local network.

* Get webcam feed on your smart phone (Only when you are checking. There is no network traffic when the page is open in background).
* Get real-time feed on temperatures and print job.
* Pause or cancel print job.
* Display the IP address of your OctoPrint on your phone.
* Check status of all your 3D printers on the same page at a glance.
* Many more to come...

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
