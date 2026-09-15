"""
Contract enforcement - defines violation errors for illegal state mutations.
"""


class ContractViolationError(Exception):
    """Raised when a state transition violates the execution contract."""
    pass
