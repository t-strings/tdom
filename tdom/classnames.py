def classnames(*args: object) -> str:
    """
    Construct a space-separated class string from various inputs.

    Accepts strings, lists/tuples of strings, and dicts mapping class names to
    boolean values. Ignores None and False values.

    Examples:
        classnames("btn", "btn-primary") -> "btn btn-primary"
        classnames("btn", {"btn-primary": True, "disabled": False}) -> "btn btn-primary"
        classnames(["btn", "btn-primary"], {"disabled": True}) -> "btn btn-primary disabled"
        classnames("btn", None, False, "active") -> "btn active"

    Args:
        *args: Variable length argument list containing strings, lists/tuples,
               or dicts.

    Returns:
        A single string with class names separated by spaces.
    """
    classes: list[str] = []
    # Use a queue to process arguments iteratively, preserving order.
    queue = list(args)

    while queue:
        arg = queue.pop(0)

        if not arg:  # Handles None, False, empty strings/lists/dicts
            continue

        if isinstance(arg, str):
            classes.append(arg)
        elif isinstance(arg, dict):
            for key, value in arg.items():
                if value:
                    classes.append(key)
        elif isinstance(arg, (list, tuple)):
            # Add items to the front of the queue to process them next, in order.
            queue[0:0] = arg
        elif isinstance(arg, bool):
            pass  # Explicitly ignore booleans not in a dict
        else:
            raise ValueError(f"Invalid class argument type: {type(arg).__name__}")

    # Filter out empty strings and join the result.
    return " ".join(stripped for c in classes if (stripped := c.strip()))
