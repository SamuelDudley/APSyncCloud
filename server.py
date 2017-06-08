import tornado.ioloop
import tornado.web
import os, json, base64
import uuid, subprocess, binascii
import errno
import time
from datetime import datetime

import threading
from Queue import Queue

from mail import send_email
from cmds import cd, mkdir_p, generate_key_fingerprint
from cmds import block_directory_creation, give_dir_permissions

import sqlite3 as lite

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
db_file = os.path.join(APP_ROOT, 'data', 'database.db')
config_file = (os.path.join(APP_ROOT, 'conf', 'WebConfigServer.json'))
with open(config_file, 'r') as fid:
    config = json.load(fid)
    
class MainHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.xsrf_token
        
    def get(self):
        self.write(json.dumps({'msg':'welcome to apsync.cloud!'}))

class RegisterHandler(tornado.web.RequestHandler):  
    def post(self):
        verify_hash = base64.urlsafe_b64encode(str(uuid.uuid4())+str(uuid.uuid4()))
        arg_dict =  { k: self.get_argument(k) for k in self.request.arguments }
        email = arg_dict.get('email', None)
        if not email:
            self.write(json.dumps({'msg':'email is required!'}))
        email = email.strip()
        encoded_email = base64.urlsafe_b64encode(email.strip().lower())
        
        encoded_public_key = arg_dict.get('public_key', None) # this is sent from the CC
        if not encoded_public_key:
            self.write(json.dumps({'msg':'public key is required!'}))
        encoded_public_key = encoded_public_key.strip()
        decoded_public_key = base64.b64decode(encoded_public_key)
        # generate a fingerprint for the public key
        filepath = "/home/{0}/tmp/".format(config['worker'])
        mkdir_p(filepath)
        filename = os.path.join(filepath, "{0}.pub".format(verify_hash))
        with open(filename, "w") as fid:
            fid.write(decoded_public_key)
        public_key_fingerprint = generate_key_fingerprint(filename)
        os.remove(filename)
        if not public_key_fingerprint:
            self.write(json.dumps({'msg':'public key fingerprint failed'}))
        
        user_id = encoded_email # if one does not exist... (look for previously confirmed public keys for this email
        
        # user exists and public key exists # existing user with existing vehicle
        # user exists and public key does not # new vehicle_id for existing user
        # user does not exist and key does not exist # new user and vehicle_id
        # user does not exist but key exits # this is an issue as we require unique public keys...
        
        verify_url = "{0}/verify?hash={1}".format(config['webserver_address'],verify_hash)
        sql = "SELECT * FROM Users WHERE PublicKey=?"
        
        con = lite.connect(db_file)
        with con:
            cur = con.cursor()
            cur.execute(sql, [(decoded_public_key)])
            res = cur.fetchone()
            
        if res is not None:
            if len(res) >= 1:
                # the public key already exists in the DB...
                # check the user id...
                if res[2] == user_id and res[6]: # user exists and is authenticated
                    # send them a message
                    self.write(json.dumps({'msg':'Already verified! Service ready to use with exisiting credentials'}))
                elif res[2] == user_id and not res[6]: # user exists and is NOT authenticated
                    # check to see if AuthenticatedTime has passed
                    if time.time()>= res[7]+int(config['verification_timeout']):
                        # send a new email for the user to click on
                        
                        con = lite.connect(db_file)
                        with con:
                            # update the AuthenticatedTime
                            task = (int(time.time()), decoded_public_key)
                            sql = ''' UPDATE Users
                                  SET AuthenticatedTime = ?
                                  WHERE PublicKey = ?'''
                            cur = con.cursor()
                            cur.execute(sql, task)
                            con.commit()
                            # update the AuthenticatedHash
                            task = (verify_hash, decoded_public_key)
                            sql = ''' UPDATE Users
                                  SET AuthenticatedHash = ?
                                  WHERE PublicKey = ?'''
                            cur = con.cursor()
                            cur.execute(sql, task)
                            con.commit()
                        
                        # send a new email
                        self.write(json.dumps({'msg':'Thanks for the credentials, please verify them by clicking on the link sent to your supplied email address'}))
                        send_email( config['email_user'],  config['email_password'], email, "Confirm account with apsync.cloud", verify_url)
                    
                    else: #AuthenticatedTime has NOT passed
                        self.write(json.dumps({'msg':'Please verify your credentials using the link previously sent to your supplied email address'}))
                else:
                    # can get here if the user has alredy tried to use a diffrent email with the =
                    # same public key
                    print(res)
                    self.write(json.dumps({'msg':'An error occured when processing your request'}))
        else:
            # the public key is new...
            # create a row in the user database to hold the new key
            vehicle_id = str(uuid.uuid4())  
            rows = [(decoded_public_key, public_key_fingerprint, # PublicKey, PublicKeyFingerprint
                     user_id, email,
                     base64.urlsafe_b64encode(str(uuid.uuid4())), # vehicle id
                     verify_hash,
                     0, # is NOT authenticated
                     int(time.time()),
                     '' # ArchiveFolder
                     )]
            con = lite.connect(db_file)
            with con:
                cur = con.cursor()
                cur.executemany('INSERT INTO Users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', rows)
                con.commit()
            send_email( config['email_user'],  config['email_password'], email, "Confirm account with apsync.cloud", verify_url)
            self.write(json.dumps({'msg':'Thanks for the credentials, please verify them by clicking on the link sent to your supplied email address'}))

class VerifyHandler(tornado.web.RequestHandler):      
    def get(self):
        verified = None
        res = None
        try:
            verify_hash = self.get_argument('hash')
        except:
            verified = False
        
        if verified is None:
            # check to see if the hash is in our database
            sql = "SELECT * FROM Users WHERE AuthenticatedHash=?"
            con = lite.connect(db_file)
            with con:
                cur = con.cursor()
                cur.execute(sql, [(verify_hash)])
                res = cur.fetchone()
            if res is not None:
                if len(res) >= 1:
                    # we found a match to the hash
                    # check to see if the hash has been authenticated
                    if res[6]: # is already authenticated
                        verified = False
                    else:
                        # is NOT authenticated
                        # lets take care of that...
                        con = lite.connect(db_file)
                        with con:
                            task = (1, verify_hash)
                            sql = ''' UPDATE Users
                                      SET IsAuthenticated = ?
                                      WHERE AuthenticatedHash = ?'''
                            cur = con.cursor()
                            cur.execute(sql, task)
                            con.commit()
                        
                        # add ssh public key to authorized_keys with command
                        command = 'command="rsync --server -vlHogDtprze.iLsfxC . /home/apsync/users/{0}/{1}/upload/",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding {2}'.format(res[2], res[4], res[0])
                        filepath = "/home/{0}/.ssh/".format(config['user'])
                        mkdir_p(filepath)
                        filename = os.path.join(filepath, "authorized_keys")
                        with open(filename, "a+") as fid: # file is created if it does not exist
                            fid.write("{0}\n".format(command))
                        
                        # create the dflogger dirs
                        mkdir_p('/home/apsync/users/{0}/{1}/'.format(res[2], res[4]))
                        mkdir_p('/home/apsync/dflogger/{0}/{1}/'.format(res[2], res[4]))
                        # note that the apsync user has no permissions in these dirs
                        # the user is now all set up!
                        verified = True
            else:
                # there was no match to the hash in the DB
                verified = False
            
        if not verified:
            self.write(json.dumps({'verify':False, 'msg':'Verification failed! Perhaps the verification time has expired, has already been used or the URL was wrongly entered.'}))
        else:
            self.write(json.dumps({'verify':True, 'msg':'Credentials verified! Service ready to use :)', 'user_id':res[2], 'vehicle_id':res[4]}))
    
    def post(self):
        # TODO: check for registration timeout and re send email
        res = None
        arg_dict =  { k: self.get_argument(k) for k in self.request.arguments }
        public_key_fingerprint = arg_dict.get('public_key_fingerprint', None)
        if not public_key_fingerprint:
            print('failed to get public_key_fingerprint')
            raise tornado.web.HTTPError(401) #401 Unauthorized

        decoded_public_key_fingerprint = base64.b64decode(public_key_fingerprint)
        # check fingerprint against DB, if an entry exists
        print('got: {0}'.format(public_key_fingerprint))
        
        sql = "SELECT * FROM Users WHERE PublicKeyFingerprint=?"
        con = lite.connect(db_file)
        with con:
            cur = con.cursor()
            cur.execute(sql, [(decoded_public_key_fingerprint)])
            res = cur.fetchone()
            
        if res is not None:
            if len(res) >= 1:
                if not res[6]: # user is not authenticated
                    print("user is not authenticated")
                    self.write(json.dumps({'verify':False, 'msg':'Credentials need to be verified! Please verify them by clicking on the link sent to your email address'}))
                else:
                    self.write(json.dumps({'verify':True, 'msg':'Credentials have been verified! Service ready to use :)', 'user_id':res[2], 'vehicle_id':res[4]}))
            else:
                self.write(json.dumps({'verify':False, 'msg':'An error occured when processing your request'}))        
        else:           
            raise tornado.web.HTTPError(401) #401 Unauthorized
    
class UploadHandler(tornado.web.RequestHandler):
    def initialize(self, queue):
        self.queue = queue
        
    def post(self):
        res = None
        arg_dict =  { k: self.get_argument(k) for k in self.request.arguments }
        public_key_fingerprint = arg_dict.get('public_key_fingerprint', None)
        if not public_key_fingerprint:
            print('failed to get public_key_fingerprint')
            raise tornado.web.HTTPError(401) #401 Unauthorized

        decoded_public_key_fingerprint = base64.b64decode(public_key_fingerprint)
        # check fingerprint against DB, if an entry exists
        print('got: {0}'.format(public_key_fingerprint))
        
        sql = "SELECT * FROM Users WHERE PublicKeyFingerprint=?"
        con = lite.connect(db_file)
        with con:
            cur = con.cursor()
            cur.execute(sql, [(decoded_public_key_fingerprint)])
            res = cur.fetchone()
            
        if res is not None:
            if len(res) >= 1:
                if not res[6]: # user is not authenticated
                    print("user is not authenticated")
                    raise tornado.web.HTTPError(401) #401 Unauthorized
                # Check to see if archive folder is valid and still active, if so send name of ArchiveFolder
                if ((res[8] != '') and (res[7]+int(config['upload_timeout']) > time.time())):
                    self.write( json.dumps({'archive_folder':res[8], 'valid_time':int((res[7]+int(config['upload_timeout']))-time.time())}))
                if ((res[8] == '') or (res[7]+int(config['upload_timeout']) <= time.time())):
                    # we need a new archive folder...
                    upload_base = '/home/apsync/users/{0}/{1}/'.format(res[2], res[4])
                    upload_path = '/home/apsync/users/{0}/{1}/upload'.format(res[2], res[4])
                    archive_folder = 'dataflash-{0}-{1}'.format(res[4], datetime.utcnow().strftime('%Y%m%d%H%M%S'))
                    archive_path = '/home/apsync/dflogger/{0}/{1}/{2}'.format(res[2], res[4], archive_folder)
                    mkdir_p(upload_base) # should already exist
                    mkdir_p(archive_path) # should already exist
                    
                    if res[8] != '':
                        # try to remove existing symlink (if its still there)
                        try:
                            if os.path.islink(upload_path):
                                os.unlink(upload_path)
                        except Exception as e:
                            print e
                    
                    with cd(archive_path):
                        block_directory_creation()
                    give_dir_permissions(archive_path)
                    # make a symlink called 'upload' and point it to the archive dir
                    os.symlink(archive_path, upload_path)
                    
                    auth_time = int(time.time())
                    queue.put_nowait({'valid_time':int(config['upload_timeout'])+auth_time, 'upload_path':upload_path, 'archive_path':archive_path, 'decoded_public_key_fingerprint':decoded_public_key_fingerprint})
                    con = lite.connect(db_file)
                    with con:
                        # update the AuthenticatedTime
                        task = (auth_time, decoded_public_key_fingerprint)
                        sql = ''' UPDATE Users
                              SET AuthenticatedTime = ?
                              WHERE PublicKeyFingerprint = ?'''
                        cur = con.cursor()
                        cur.execute(sql, task)
                        con.commit()
                        # update the ArchiveFolder
                        task = (archive_folder, decoded_public_key_fingerprint)
                        sql = ''' UPDATE Users
                          SET ArchiveFolder = ?
                          WHERE PublicKeyFingerprint = ?'''
                        cur = con.cursor()
                        cur.execute(sql, task)
                        con.commit()
                        
                    self.write( json.dumps({'archive_folder':archive_folder, 'valid_time':int((auth_time+int(config['upload_timeout']))-time.time())}))
                    # TODO: setup an external thread to stat the archive dir and watch for a connection from this public key
                    # when a file is added, remove the sym link (rsync will continue). Then set AuthenticatedTime to one second in the past
        else:
            print('No DB entry')       
            raise tornado.web.HTTPError(401) #401 Unauthorized
        
class Application(tornado.web.Application):
    def __init__(self, queue):
        handlers = [
            (r"/", MainHandler),
            (r"/register", RegisterHandler),
            (r"/verify", VerifyHandler),
            (r"/upload", UploadHandler, dict(queue=queue)),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
#             template_path=os.path.join(os.path.dirname(__file__), "templates"),
#             static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            debug= int(config['webserver_debug']),
            autoreload=int(config['webserver_autoreload']),
        )
        super(Application, self).__init__(handlers, **settings)


def upload_watcher_deployer(queue):
    while True:
        while not queue.empty():
            obj = queue.get_nowait()
            datalog_stat = os.stat(obj['archive_path'])
            obj['mtime'] = datalog_stat.st_mtime
            threading.Thread(target=upload_watcher,args=(obj.copy(),)).start()
        time.sleep(0.2)

def upload_watcher(data):
        while time.time() <= data['valid_time']:
            if data['mtime'] != os.stat(data['archive_path']).st_mtime:
                print('CHANGE!')
                if os.path.islink(data['upload_path']):
                    os.unlink(data['upload_path'])
                    
                auth_time = int(time.time()-(int(config['upload_timeout'])+1))
                con = lite.connect(db_file)
                # update the AuthenticatedTime
                task = (auth_time, data['decoded_public_key_fingerprint'])
                sql = ''' UPDATE Users
                      SET AuthenticatedTime = ?
                      WHERE PublicKeyFingerprint = ?'''
                with con:
                    cur = con.cursor()
                    cur.execute(sql, task)
                    con.commit()
                return
            
            time.sleep(0.2)
        
        print('TIMEOUT!')
        if os.path.islink(data['upload_path']):
            os.unlink(data['upload_path'])
        os.rmdir(data['archive_path'])

if __name__ == "__main__":
    queue = Queue()
    application = Application(queue)
    server = tornado.httpserver.HTTPServer(application)
    port = int(config['webserver_port'])
    server.listen(port, address='127.0.0.1')
    
    upload_watcher_deployer_thread = threading.Thread(target=upload_watcher_deployer,args=(queue,))
    upload_watcher_deployer_thread.daemon = True
    upload_watcher_deployer_thread.start()
    
    print("Starting Tornado on port {0}".format(port))
    tornado.ioloop.IOLoop.current().start()