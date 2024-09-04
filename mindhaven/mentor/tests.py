from django.test import TestCase

from celery import shared_task
import logging

logger = logging.getLogger(__name__)

# Create your tests here.
@shared_task
def test_task():
    logger.info("This is a test task")
    return "Test task completed"