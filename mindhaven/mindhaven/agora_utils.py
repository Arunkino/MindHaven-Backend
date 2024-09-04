from agora_token_builder import RtcTokenBuilder
import time
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def generate_agora_token(channel_name, uid):
    logger.info("genarating agora token")
    appId = settings.AGORA_APP_ID
    appCertificate = settings.AGORA_APP_CERTIFICATE
    expirationTimeInSeconds = 3600
    currentTimestamp = int(time.time())
    privilegeExpiredTs = currentTimestamp + expirationTimeInSeconds

    logger.info(f"appId: {appId}, appCertificate: {appCertificate}, channel_name: {channel_name}, uid: {uid}, privilegeExpiredTs: {privilegeExpiredTs}")

    return RtcTokenBuilder.buildTokenWithUid(appId, appCertificate, channel_name, uid, 1, privilegeExpiredTs)