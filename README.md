# APSyncCloud
A web service written in Python to support automatic and secure uploading of Ardupilot logs via rsync. This project is the server-side implementation of the workflow outlined here: https://github.com/ArduPilot/companion/issues/21 . The client / vehicle-side of this project can be found here: https://github.com/SamuelDudley/APSyncWeb . Example code utlising the service can be found here: https://github.com/SamuelDudley/APSyncWeb/blob/df_sync_wip/APSyncFramework/utils/requests_utils.py#L51

## Workflow

#### One time registration with datalog server + setup of the companion computer
##### _user steps:_
1. Enter the address of the datalog server or leave the default on the companion computer web UI
2. Enter your email and on the companion computer web UI
2. On the companion computer web UI a button is pushed to 'register'
3. In the received email a confirmation link is clicked
##### _all steps:_
- On the companion computer web UI the user enters the address of the datalog server e.g. `apsync.cloud` and their email
- On the companion computer a button is pushed to 'register' with the server
 - A ssh key pair is generated automatically
 - When the register button is pushed the `/register` endpoint of the server is POST'ed to over HTTPS with data containing the email and companion computer public key
 - An email is sent to the user from the server asking them to confirm via clicking on a link in the email
 - Once the link is confirmed, the server associates that public key + email with a particular companion computer (the same email can have many public keys and hence many vehicles associated with it)
 - The companion computer detects the user has confirmed the email via a challenge REST request and receives a generic username, unique vehicle id, and port number for the server __TODO__
 - The configuration file on the companion computer is automatically updated and saved for future use __TODO__

#### Normal operation
_The companion computer wants to rsync a log_
##### _user steps:_
N/A
##### _all steps:_
- Data is POST'ed over HTTPS from the companion computer, to the datalog server at the `/upload` endpoint. The data in the POST only contains the public key fingerprint of the vehicle 
- The datalog server responds with a time stamped directory name and a valid time period to begin syncing
- The datalog server creates the time stamped directory for that user + vehicle ID by looking up the public key that shares a fingerprint with one just POST'ed
- The time stamped directory now exists on the datalog server, and we can begin to rsync to it using the ssh pre-shared keys
- The datalog server accepts the connection from that particular ssh key and rsync's the datalog
- Once the rsync is complete, the companion computer creates a local archive folder using the name provided by the datalog server. The local copy of the datalog is then moved to this folder. __TODO__
 - If a log upload has not started when the valid time period expires the empty directory is cleaned up on the datalog server

#### Accessing the logs on the datalog server - __Not yet implemented__
_When a user wants to retrieve logs that have been rsync'd with the datalog server_
##### _user steps via 'normal' access :_
1. Navigate to website
2. Login
##### _user steps via  companion computer access :_
1. Open the correct screen in the companion computer web UI
##### _all steps:_
 - Users navigate to datalog server web front end and login using the email address and ssh public key string (a bit painful?)
  -  Perhaps there is an option to login with a linked google / github / ardupilot.org account to simplify things?
 - User is provided with a list of registered vehicles and can browse the associated logs
 - There could be further functions to download / perform analysis on the logs
 - The web UI on the companion computer is also capable of connecting via a REST backend to display a list of sync'd logs for the associated email address (all vehicles) and ssh public key combo
