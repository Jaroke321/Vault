class Route:
    """One node in the command routing tree.

    `handler` is the callable to invoke when dispatch stops at this node
    (called with whatever tokens remain as `options`). `children` maps the
    next token to a child `Route`, for commands that route deeper. `usage`
    is the usage text shown in tab-completion metadata.
    """

    def __init__(self, handler=None, usage: str | None = None, children: dict | None = None):
        self.handler = handler
        self.usage = usage
        self.children = children if children is not None else {}

    @staticmethod
    def walk(routes: dict[str, "Route"], tokens: list[str]):
        """Descend through `routes` while the next token matches a child, then
        stop at the deepest match. Returns (route, remaining_tokens), or
        (None, None) if the first token matches nothing."""

        if not tokens or tokens[0] not in routes:
            return None, None

        route = routes[tokens[0]]
        remaining = tokens[1:]
        while remaining and remaining[0] in route.children:
            route = route.children[remaining[0]]
            remaining = remaining[1:]

        return route, remaining
