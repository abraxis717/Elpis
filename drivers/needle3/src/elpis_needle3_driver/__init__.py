"""Needle3 native isolated-driver wheel entry point."""

from .provider import Needle3Provider


def factory(context):
    return Needle3Provider(context)


__all__ = [
    "Needle3Provider",
    "factory",
]
