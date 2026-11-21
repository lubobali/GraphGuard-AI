"""The alert key can only send email from the one address to the one address (S6.1).

Proven against REAL AWS once `.secrets/alerts-aws.env` and `alerts-mail.env` exist
(docs/runbooks/scorer-down.md); skips elsewhere (CI). Every call here is either refused
by IAM or, for the one allowed shape, never made: no email is sent by this test.
"""

import pytest

from graphguard.config import REPO_ROOT
from graphguard.ops import alert

SECRETS = REPO_ROOT / ".secrets"
KEY, MAIL = SECRETS / "alerts-aws.env", SECRETS / "alerts-mail.env"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (KEY.exists() and MAIL.exists()), reason="alert key not set"),
]


def _code(call):
    from botocore.exceptions import ClientError

    try:
        call()
    except ClientError as e:
        return e.response["Error"]["Code"]
    return "OK"


@pytest.fixture(scope="module")
def ses():
    return alert.ses_client()


def _send(ses, sender, to):
    email = alert.Email("down", "[GraphGuard][TEST] must be refused", "never delivered")
    return lambda: alert.send(ses, email, sender=sender, to=to)


def test_sending_from_another_address_is_refused(ses):
    _, to = alert.addresses()
    assert _code(_send(ses, "someone-else@example.org", to)) == "AccessDeniedException"


def test_sending_to_another_address_is_refused(ses):
    sender, _ = alert.addresses()
    assert _code(_send(ses, sender, "someone-else@example.org")) == "AccessDeniedException"


def test_reading_ses_settings_is_refused(ses):
    assert _code(lambda: ses.list_email_identities()) == "AccessDeniedException"
    assert _code(lambda: ses.get_account()) == "AccessDeniedException"


def test_the_key_reaches_nothing_else():
    import boto3

    env = alert._env_file(KEY)
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )
    assert _code(lambda: s3.list_buckets()) == "AccessDenied"
