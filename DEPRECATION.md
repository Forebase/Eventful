# Deprecation policy

Before 1.0, public API removals warn for at least one minor release when practical
and are recorded in the changelog. A symbol documented as experimental may change
faster, but the change must still be documented. Patch releases do not knowingly
remove public APIs. Security fixes may override the notice period when retaining an
API would leave users exposed.
