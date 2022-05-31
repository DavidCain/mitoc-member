![CI](https://github.com/DavidCain/mitoc-member/workflows/CI/badge.svg?branch=master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Coverage Status](https://coveralls.io/repos/github/DavidCain/mitoc-member/badge.svg)](https://coveralls.io/github/DavidCain/mitoc-member)

# DISCONTINUED
This library was a temporary solution that served us well for 4 years.
The approach was always flawed in some key ways, but it worked well enough.

In short, we made this repository initially as a proof of concept, but kept
it around while other work was done to provide public API endpoints which
could replace the direct database access.

# Mistakes made
We have replaced this repository with an AWS-native solution.
Many of the mistakes and assumptions inherent in this repository
have been addressed (and surely, some new mistakes made).

The new solution is not yet open-sourced, but we've detailed the failures of
this design (and how we've addressed them) below.

## Direct access to a managed schema
The Flask service would write rows directly to a MySQL database, where that
database was managed by a totally separate Django application. A few times over
the years, normal changes to the Django application would break this application,
and we would only notice when processing a new waiver or membership failed.

As a result, the developers of the Django application have just been careful
not to modify certain models, which is a frustrating constraint (that's doubly
frustrating since we made no efforts to verify schema expectations).

We opted to use direct SQL, since it was fast & simple to do, and required
no modification of the Django-based gear database. We always planned to drop
direct SQL once sufficient API endpoints were authored that could be used instead.

**The fix:** We instead invoke some new API endpoints:
- `https://mitoc-gear.mit.edu/api-auth/v1/waiver/`
- `https://mitoc-gear.mit.edu/api-auth/v1/membership/`

## Authentication logic separated from the code
Each of the two routes served by this Flask service have incredibly important
verification logic (namely - mutual TLS for DocuSign, and an IP address
allowlist for CyberSource). These configurations lived in a totally separate
Ansible repository.

(At the very least, CyberSource signature verification lived directly in the
code, but we've never had the ability to enable that feature)

**The fix:** We configure authentication logic directly in the Pulumi
repository that controls our new AWS-based design.

## Idempotency & race conditions
These endpoints could very easily record the same waiver or membership twice.
We made efforts to first query for an existing row with matching timestamps and
metadata, but that approach is not resilient against writes occurring after the
initial read. We never made use of database transactions, or uniqueness constraints
at the database level itself (again, because this repository doesn't actually
manage the underlying schema).

**The fix:** We can configure uniqueness constraints (and enforce idempotency)
directly in the new API endpoints served by the gear database.

## Unable to handle service outages
The most glaring problem with this service was its utter inability to handle
service outages or failures. If this Flask service was down (a very rare
occurrence), then CyberSource and DocuSign would at least dutifully retry their
POST calls until eventually getting a response (or giving up). No other retry
logic existed, though.

If a waiver or membership notification was "missed," then the backstop was for
a human to manually check a shared email account (which received emails
duplicating the callbacks' payloads), and enter information by hand. We had to
do this many, many times over the years.

If the gear database itself was down (e.g. for routine maintenance), the
endpoints had no way to queue the work up for a future attempt. The only
solution was to manually enter information by hand.

**The fix:** We leverage AWS's SQS to add the ability to retry.

We break up waiver & membership processing into several steps:

1. Once notified, verify the caller's identity, and parse the payload.
2. Put valid payloads into a queue for processing.
3. Eagerly remove payloads from the queue, attempting to notify the gear and
   trips APIs, retrying (with an exponential backoff) in the event of API outages.
4. Save failures to a deadletter queue (so they can be retried later, or
   manually addressed - but without needing to log into a shared email account)

## No independent architecture
For convenience, we served this application on the same EC2 instance which serves
https://mitoc-trips.mit.edu/. This meant that any time the trips service was
down (or simply overloaded), we also lost the ability to process waivers or
membership.

We used a totally separate NGINX configuration, and a different supervisord
configuration, but it was still running in the same virtual machine.

**The fix:** We now run our services in totally independent architecture.


----------

*Previous README archived below for posterity*:

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
https://mitoc.mit.edu/#join

## Installation

### Poetry
This project uses [`poetry`][poetry]. Make sure [`poetry` is installed!][poetry_installation]

```bash
make run
```

## Running unit tests & linters
```bash
make check
```


[poetry]: https://github.com/sdispater/poetry
[poetry_installation]: https://github.com/sdispater/poetry#installation
