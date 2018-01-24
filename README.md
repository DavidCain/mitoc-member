# About
This repository contains endpoints for when a MITOC member creates or renews a
membership. In order to be a member of the club, one must pay annual dues and sign
a waiver. This repository processes both events, and creates an account in
MITOC's membership system.

Once an account is created, members may participate in MITOC's many official
trips, rent gear from the office, and more.

Membership payments are handled through CyberSource, with a callback posted
over HTTPS after every transaction. Similarly, our waivers are administered by
DocuSign - when a Power Form waiver (i.e. a self-service document) completes,
our API is notified.


## Becoming a member
Membership payments and waiver completions are initiated at:
http://mitoc.mit.edu/#join

## Installation

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
FLASK_APP=autoapp.py flask run
```

## Running unit tests
```bash
python3 -m venv test_env
source test_env/bin/activate
pip install -r requirements-dev.txt
FLASK_APP=autoapp.py flask test
```
