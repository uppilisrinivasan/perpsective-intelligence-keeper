"""Error types. Every user-facing error is a LaminaError carrying a line and a column."""


class LaminaError(Exception):
    """Base class for all lamina errors."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"{self.message} (line {self.line}, column {self.column})"


class ParseError(LaminaError):
    """The text is not valid lamina syntax."""


class IncludeError(LaminaError):
    """An include directive cannot be resolved."""


class InterpolationError(LaminaError):
    """A ${NAME} reference cannot be expanded."""
