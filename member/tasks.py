import random

from celery import shared_task


def increasing_retry(num_retries):
    """ Returning an increasing countdown (in seconds).

    Includes randomness to avoid the Thundering Herd Problem.

    With 8 retries, tasks will be attempted again in approximately:
      - 1 second
      - 5 seconds
      - 15 seconds
      - 30 seconds
      - 1 minute
      - 5 minutes
      - 15 minutes
      - 1 hour
      - 5 hours
    """
    return int(random.uniform(3, 5) ** num_retries)


@shared_task(bind=True, max_retries=8)
def update_membership(verified_payload):
    """ Accepts a signed & verified payload & updates the membership.

    This will also handle creating the user if needed.

    This is kept as an idempotent, repeatable task in case the trips API
    experiences some outage, or the gear database is inacccessible.
    """
