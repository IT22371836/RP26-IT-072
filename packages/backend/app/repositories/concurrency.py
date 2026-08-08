class ProfileConcurrencyError(Exception):
    """The profile changed after the client version was read."""
