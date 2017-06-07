#!/bin/bash
# rsync -ahHzv --progress /home/uas/Dropbox/git/APSyncServer apsync-worker@apsync.cloud:~
# ssh apsync-worker@apsync.cloud
# sudo nano /lib/systemd/system/dflogger_server.service
# systemctl daemon-reload
# service dflogger_server restart
# systemctl status dflogger_server.service 
# cat /var/log/syslog

if [[ $USER != "apsync-worker" ]]; then 
	echo "This script must be run as apsync-worker!" 
	exit 1
fi 

cd /home/apsync-worker/APSyncServer
chown -R apsync-worker:apsync-worker ./ # only allow apsync-worker to have access to these files
chmod -R go-rwx ./ # only allow apsync-worker to have access to these files
# allow server to excecute
chmod u+x server.py
cd data
rm *.db*
chmod u+x make_db.py
python make_db.py

# move into the apsync home dir
cd /home/apsync/
rm  -r dflogger
mkdir dflogger

rm  -r users
mkdir users

rm  -r .ssh
mkdir .ssh
chown apsync-worker:apsync .ssh
touch .ssh/authorized_keys
chown apsync-worker:apsync .ssh/authorized_keys
chmod 0640 .ssh/authorized_keys # apsync-worker read+write, apsync read only

chown apsync-worker:apsync ./
chmod 0750 ./ #apsync-worker read+write+ex, apsync read+ex

echo "Now run python server.py"
# upload folder chmod 0770 #apsync-worker read+write+ex, apsync read+write+ex
