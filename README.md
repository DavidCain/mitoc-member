![CI](https://github.com/DavidCain/mitoc-member/workflows/CI/badge.svg?branch=master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Coverage Status](https://coveralls.io/repos/github/DavidCain/mitoc-member/badge.svg)](https://coveralls.io/github/DavidCain/mitoc-member)

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
