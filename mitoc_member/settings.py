import os


MEMBERSHIP_SECRET_KEY = os.getenv('MEMBERSHIP_SECRET_KEY',
                                  'secret shared with mitoc-trips')
