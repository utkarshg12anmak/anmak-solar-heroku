# storage_backends.py

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class MediaStorage(S3Boto3Storage):
    """
    Store all FileField/ImageField uploads in S3.
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN
    default_acl = None
    file_overwrite = False
    location = ""           # don’t prepend any extra folder—`upload_to` is enough
