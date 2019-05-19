from prometheus_client import start_http_server, Summary, Gauge
import random
import time

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

# Decorate function with metric.
@REQUEST_TIME.time()
def process_request(t):
    """A dummy function that takes some time."""
    time.sleep(t)


from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, func, select
engine = create_engine('sqlite:///db.sqlite3', echo=True)
meta = MetaData()

users = Table(
    'users', meta, 
    Column('uuid', String), 
    Column('email', String), 
    Column('name', String), 
)
ciphers = Table(
    'ciphers', meta, 
    Column('uuid', String), 
    Column('user_uuid', String), 
)
folders = Table(
    'folders', meta, 
    Column('uuid', String), 
    Column('user_uuid', String), 
    Column('name', String), 
)
folders_ciphers = Table(
    'folders_ciphers', meta, 
    Column('cipher_uuid', String), 
    Column('folder_uuid', String), 
)
conn = engine.connect()

num_users = Gauge('users', 'Number of users')
def export_users():
    s = select(
        [func.count()]
    ).select_from(users)
    count = conn.scalar(s)
    num_users.set(count)


num_passwords = Gauge('passwords', 'Number of passwords')
def export_passwords():
    s = select(
        [func.count()]
    ).select_from(ciphers)
    count = conn.scalar(s)
    num_passwords.set(count)


num_passwords_by_user = Gauge('passwords_by_user', 'Number of passwords by user', ['user_uuid', 'username', 'email'])
def export_passwords_by_users():
    s = select(
        [users.c.name, users.c.email, users.c.uuid, func.count()]
    ).select_from(
        ciphers.join(users, users.c.uuid == ciphers.c.user_uuid)
    ).group_by(users.c.email)
    result = conn.execute(s)

    for row in result:
        name = row[0]
        email = row[1]
        uuid = row[2]
        count = row[3]
        num_passwords_by_user.labels(username=name, email=email, user_uuid=uuid).set(count)


num_folders = Gauge('folders', 'Number of folders')
def export_folders():
    s = select(
        [func.count()]
    ).select_from(folders)
    count = conn.scalar(s)
    num_folders.set(count)

num_passwords_by_folder = Gauge('passwords_by_folder', 'Number of passwords by folders', ['folder_uuid'])
def export_passwords_by_folder():
    s = select(
        [folders.c.uuid, func.count()]
    ).select_from(
        folders.join(folders_ciphers, folders.c.uuid == folders_ciphers.c.folder_uuid)
    ).group_by(folders.c.uuid)
    result = conn.execute(s)

    for row in result:
        uuid = row[0]
        count = row[1]
        num_passwords_by_folder.labels(folder_uuid=uuid).set(count)



def update_readings():
    export_users()
    export_passwords()
    export_passwords_by_users()
    export_passwords_by_folder()
    export_folders()

update_readings()



if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8000)
    # Generate some requests.
    while True:
        process_request(random.random())
