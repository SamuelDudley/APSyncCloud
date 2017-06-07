# Script to create or upgrade the SQLite DB

import sqlite3 as lite
import sys
import os

def get_data_filepath():
    return os.path.dirname(os.path.abspath(__file__))

def get_db_filename():
    return os.path.join('database.db')

data_dir = get_data_filepath()
if not os.path.exists(data_dir):
    print('Creating data directory: {0}'.format(data_dir))
    os.makedirs(data_dir)

db_path = os.path.join(data_dir, get_db_filename())
print('Creating DB: {0}'.format(db_path))
con = lite.connect(db_path)
with con:
    cur = con.cursor()

    # User table (contains verified user information)
    cur.execute("PRAGMA table_info('Users')")
    columns = cur.fetchall()

    if len(columns) == 0:
        cur.execute("CREATE TABLE Users("
                "PublicKey TEXT, "
                "PublicKeyFingerprint TEXT, "
                "Id TEXT, "
                "Email TEXT, "
                "Vehicle TEXT, "
                "AuthenticatedHash TEXT, "
                "IsAuthenticated INT, "
                "AuthenticatedTime INT, "
                "ArchiveFolder TEXT, "
                "CONSTRAINT Id_PK PRIMARY KEY (PublicKey))")
    
con.close()
print('Done!')

