sudo apt update
sudo apt upgrade

sudo nano /etc/ssh/sshd_config
- change: #Port 22
- to: Port 1971
sudo service ssh restart

sudo raspi-config

sudo nano /boot/config.txt
dtoverlay=w1-gpio

sudo reboot

git clone https://github.com/RistoWieland/Environment-Portable.git

mkdir Config
