"""AWS credential checks and SSO guidance.

Adapted from ~/workspace/s3-taggings/src/credentials.py.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError, UnauthorizedSSOTokenError

from .aws_profiles import profile_is_sso


def sso_login_command(profile: str) -> str:
    if profile == "default":
        return "aws sso login"
    return f"aws sso login --profile {profile}"


def validate_profile(profile: str) -> tuple[bool, str]:
    session = boto3.Session(profile_name=profile)
    try:
        identity = session.client("sts").get_caller_identity()
        return True, f"Account {identity['Account']} ({identity.get('Arn', '')})"
    except UnauthorizedSSOTokenError:
        if profile_is_sso(profile):
            return False, (
                f"SSO session expired for profile '{profile}'. "
                f"Run: {sso_login_command(profile)}"
            )
        return False, f"Profile '{profile}' credentials invalid or expired"
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "ClientError")
        return False, f"Profile '{profile}' failed ({code}): {error}"
    except BotoCoreError as error:
        return False, f"Profile '{profile}' failed: {error}"
