from celery import Celery
import os

def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        broker=os.getenv("CELERY_BROKER_URL"),
        backend=os.getenv("CELERY_RESULT_BACKEND")
    )
    celery.conf.update(
        broker_use_ssl={'ssl_cert_reqs': os.getenv('SSL_CERT_REQS', 'CERT_NONE')},
        result_backend_use_ssl={'ssl_cert_reqs': os.getenv('SSL_CERT_REQS', 'CERT_NONE')}
    )
    return celery

celery = make_celery()