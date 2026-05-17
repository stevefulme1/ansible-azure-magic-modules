"""Shared utility functions for the Azure Magic Modules generator."""


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Example: ``address_prefixes`` -> ``AddressPrefixes``
    """
    return "".join(word.capitalize() for word in name.split("_"))
