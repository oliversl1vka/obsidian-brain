import re


def sanitize_git_error_message(error: object) -> str:
    """Redact credentials from git/HTTP error messages before logging or returning them."""
    message = str(error)
    message = re.sub(r"(x-access-token:)[^@/\s]+@", r"\1***@", message)
    message = re.sub(r"(https?://[^:/@\s]+:)[^@/\s]+@", r"\1***@", message)
    return message
