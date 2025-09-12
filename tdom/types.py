# Centralized shared types for tdom
# Python 3.12+ type statement per project guidelines

# NOTE: Keep this file lightweight and free of runtime dependencies.

# A rendering-time context passed down through html() processing and components.
# Components may treat this as read-only shared data.
# None means no context was provided.
# Use as: `def Comp(*children: Node, *, context: Context = None): ...`

type Context = dict[str, object] | None
