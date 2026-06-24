"""Dependency requirement parsing and pin validation."""

from __future__ import annotations

from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import NormalizedName, canonicalize_name


@dataclass(frozen=True)
class DependencyPin:
    """Parsed information for a selected tox dependency."""

    requirement: str
    version: str | None
    is_exact: bool


def find_dependency_pin(dep_lines: list[str], package_name: str) -> DependencyPin | None:
    """Find and classify the requested dependency in tox ``deps`` lines."""

    canonical_package = canonicalize_name(package_name)
    for line in dep_lines:
        try:
            requirement = Requirement(line)
        except InvalidRequirement:
            continue

        if canonicalize_name(requirement.name) != canonical_package:
            continue

        return _classify_pin(line, requirement)

    return None


def _classify_pin(original_line: str, requirement: Requirement) -> DependencyPin:
    specifiers = list(requirement.specifier)
    if len(specifiers) != 1:
        return DependencyPin(requirement=original_line, version=None, is_exact=False)

    specifier = specifiers[0]
    if specifier.operator != "==" or "*" in specifier.version:
        return DependencyPin(requirement=original_line, version=None, is_exact=False)

    return DependencyPin(requirement=original_line, version=specifier.version, is_exact=True)


def canonical_package_name(package_name: str) -> NormalizedName:
    """Return the normalized package name used for matching."""

    return canonicalize_name(package_name)
