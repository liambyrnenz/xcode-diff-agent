from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    url: str
    source_type: str
    version: str | None = None


# Release notes are available as .md; extend this list (or discover from the docs index).
SOURCES: list[Source] = [
    Source("https://developer.apple.com/documentation/xcode-release-notes/xcode-26-release-notes.md",
           "xcode_release_notes", "26.0"),
    # Source("https://developer.apple.com/xcode/system-requirements/", "system_requirements"),
    # Apple Developer news RSS, OS release notes, swift-evolution proposals / CHANGELOG.md ...
]