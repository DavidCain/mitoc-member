class InvalidAffiliation(ValueError):
    """The affiliation supplied is not recognized in our system."""


class IncorrectPayment(ValueError):
    """The payment value does not match what the affiliation type demands."""
