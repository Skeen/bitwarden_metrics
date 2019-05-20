from prometheus_client import start_http_server, Gauge, Counter
from prometheus_client import make_wsgi_app
from wsgiref.simple_server import make_server
import time
metrics_prefix = 'bitwarden_rs_database_'
update_interval = 10

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
    Column('organization_uuid', String), 
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
attachments = Table(
    'attachments', meta, 
    Column('id', String), 
    Column('cipher_uuid', String), 
    Column('file_name', String), 
    Column('file_size', Integer),
)
# TODO: file_size histogram
devices = Table(
    'devices', meta, 
    Column('uuid', String), 
    Column('user_uuid', String), 
    Column('name', String), 
    Column('type', Integer),
)
invitations = Table(
    'invitations', meta, 
    Column('email', String), 
)
organizations = Table(
    'organizations', meta, 
    Column('uuid', String), 
    Column('name', String), 
    Column('billing_email', String), 
)
users_organizations = Table(
    'users_organizations', meta, 
    Column('uuid', String), 
    Column('user_uuid', String), 
    Column('org_uuid', String), 
)

conn = engine.connect()

metrics = {
    'users': {
        'description': 'Number of users',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(users),
    },
    'passwords': {
        'description': 'Number of passwords',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(ciphers),
    },
    'passwords_by_user': {
        'description': 'Number of passwords by user',
        'labels': ['user_uuid', 'username', 'email'],
        'scalar': False,
        'query': select(
            [users.c.uuid, users.c.name, users.c.email, func.count()]
        ).select_from(
            ciphers.join(users, users.c.uuid == ciphers.c.user_uuid)
        ).group_by(users.c.uuid)
    },
    'folders': {
        'description': 'Number of folders',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(folders)
    },
    'passwords_by_folder': {
        'description': 'Number of passwords by folder',
        'labels': ['folder_uuid'],
        'scalar': False,
        'query': select(
            [folders.c.uuid, func.count()]
        ).select_from(
            folders.join(folders_ciphers, folders.c.uuid == folders_ciphers.c.folder_uuid)
        ).group_by(folders.c.uuid)
    },
    'attachments': {
        'description': 'Number of attachments',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(attachments)
    },
    'devices': {
        'description': 'Number of devices',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(devices)
    },
    'devices_by_user': {
        'description': 'Number of devices by user',
        'labels': ['user_uuid', 'username', 'email'],
        'scalar': False,
        'query': select(
            [users.c.uuid, users.c.name, users.c.email, func.count()]
        ).select_from(
            devices.join(users, users.c.uuid == devices.c.user_uuid)
        ).group_by(users.c.uuid)
    },
    'devices_by_devicename': {
        'description': 'Number of devices by devicename',
        'labels': ['devicename'],
        'scalar': False,
        'query': select(
            [devices.c.name, func.count()]
        ).select_from(
            devices
        ).group_by(devices.c.name)
    },
    'invitations': {
        'description': 'Number of invitations',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(invitations)
    },
    'organizations': {
        'description': 'Number of organizations',
        'labels': [],
        'scalar': True,
        'query': select(
            [func.count()]
        ).select_from(organizations)
    },
    'users_by_organization': {
        'description': 'Number of users by organization',
        'labels': ['org_uuid', 'name', 'billing_email'],
        'scalar': False,
        'query': select(
            [organizations.c.uuid, organizations.c.name, organizations.c.billing_email, func.count()]
        ).select_from(
            organizations.join(users_organizations, organizations.c.uuid == users_organizations.c.org_uuid)
        ).group_by(organizations.c.uuid)
    },
    'attachments_by_organization': {
        'description': 'Number of attachments by organization',
        'labels': ['org_uuid', 'name', 'billing_email'],
        'scalar': False,
        'query': select(
            [organizations.c.uuid, organizations.c.name, organizations.c.billing_email, func.count()]
        ).select_from(
            attachments.join(
                ciphers, attachments.c.cipher_uuid == ciphers.c.uuid
            ).join(
                organizations, ciphers.c.organization_uuid == organizations.c.uuid
            )
        ).group_by(organizations.c.uuid)
    },
    'attachments_by_user': {
        'description': 'Number of attachments by user',
        'labels': ['user_uuid', 'username', 'email'],
        'scalar': False,
        'query': select(
            [users.c.uuid, users.c.name, users.c.email, func.count()]
        ).select_from(
            attachments.join(
                ciphers, attachments.c.cipher_uuid == ciphers.c.uuid
            ).join(
                users, ciphers.c.user_uuid == users.c.uuid
            )
        ).group_by(users.c.uuid)
    },
    'duplicate_organizations_by_name': {
        'description': 'Number of duplicate organizations by name',
        'labels': ['name'],
        'scalar': False,
        'query': select(
            [organizations.c.name, func.count()]
        ).select_from(
            organizations
        ).group_by(
            organizations.c.name
        ).having(
            func.count() > 1
        )
    },
    'duplicate_organizations_by_email': {
        'description': 'Number of duplicate organizations by email',
        'labels': ['email'],
        'scalar': False,
        'query': select(
            [organizations.c.billing_email, func.count()]
        ).select_from(
            organizations
        ).group_by(
            organizations.c.billing_email
        ).having(
            func.count() > 1
        )
    },
}

guages = {}

for (metric_name, dic) in metrics.iteritems():
    guages[metric_name] = Gauge(
        metrics_prefix + metric_name,
        dic['description'],
        dic['labels'],
    )

def export_metrics():
    for (metric_name, dic) in metrics.iteritems():
        if dic['scalar']:
            count = conn.scalar(dic['query'])
            guages[metric_name].set(count)
        else:
            result = conn.execute(dic['query'])
            for row in result:
                count = row[-1]
                guages[metric_name].labels(*row[:-1]).set(count)


readings_count = Counter(metrics_prefix + 'readings_count', 'Number of updates of readings')
readings_update = Gauge(metrics_prefix + 'readings_update', 'Time for last update of readings')
def update_readings():
    # Update readings
    export_metrics()
    # Set update time and count
    readings_update.set(time.time())
    readings_count.inc()


request_count = Counter(metrics_prefix + 'request_count', 'Number of requests handled')
if __name__ == '__main__':
    # Start up the server to expose the metrics.
    app = make_wsgi_app()
    httpd = make_server('0.0.0.0', 8173, app)
    print "Starting HTTPD on 0.0.0.0:8173"
    last = time.time()
    update_readings()
    while True:
        # Handle one request
        httpd.handle_request()
        request_count.inc()
        now = time.time()
        # Only update every 'update_interval' seconds
        if now - last > update_interval:
            update_readings()
            last = time.time()
