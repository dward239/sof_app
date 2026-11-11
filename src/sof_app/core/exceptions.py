class SofError(Exception):
    """Base class for SOF errors."""

class UnitMismatchError(SofError):
    pass

class SchemaError(SofError):
    pass

class NuclideNotFoundError(SofError):
    pass
class CountsUnitDetectedError(SofError):
    """Raised when counts units (cpm/cps/counts) are detected in samples."""
    pass
