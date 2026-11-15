#  Copyright (c) 2025 Laboratory for Combinatorial Optimization in Real-time Environment.
#  All rights reserved.


from collections.abc import Iterable


class Path:
    def __init__(self, path_id: int, cost: float, visited_nodes: Iterable[int]) -> None:
        self.id = path_id
        self.cost = cost
        self.visited_nodes = list(visited_nodes)
