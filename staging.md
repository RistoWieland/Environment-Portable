

sudo nano /etc/ssh/sshd_config
- change: #Port 22
- to: Port 1971
sudo service ssh restart

# only if wire 1 sensores are connected
sudo raspi-config
sudo nano /boot/config.txt
dtoverlay=w1-gpio

# enable I2C when I2C sensors are connected

sudo apt update
sudo apt upgrade

sudo reboot

git clone https://github.com/RistoWieland/Environment-Portable.git

mkdir Config


# db server
sudo nano /etc/postgresql/13/main/postgresql.conf 
replace: #listen_addresses = 'localhost'
with: listen_addresses = '*'


sudo nano /etc/postgresql/13/main/pg_hba.conf 
# TYPE  DATABASE	USER	ADDRESS   	METHOD
host    all     	all     0.0.0.0/0       md5

sudo systemctl restart postgresql 