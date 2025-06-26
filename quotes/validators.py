# quotes/validators.py
from django.core.exceptions import ValidationError

def FileSizeValidator(value):
    """
    Validate that the uploaded file is no larger than 100 MB.
    """
    limit_mb = 100
    if value.size > limit_mb * 1024 * 1024:
        raise ValidationError(f"File too large. Maximum file size is {limit_mb} MB.")