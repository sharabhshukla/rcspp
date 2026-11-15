#  Copyright (c) 2025 Laboratory for Combinatorial Optimization in Real-time Environment.
#  All rights reserved.


class MPSolution:
    def __init__(
        self,
        value_by_var_id: dict[int, float] | None = None,
        dual_by_var_id: dict[int, float] | None = None,
        cost: float = 0.0,
    ) -> None:
        self.value_by_var_id: dict[int, float] = (
            value_by_var_id if value_by_var_id is not None else {}
        )
        self.dual_by_var_id: dict[int, float] = dual_by_var_id if dual_by_var_id is not None else {}
        self.cost: float = cost

    def __repr__(self) -> str:
        return (
            f"MPSolution(cost={self.cost}, "
            f"value_by_var_id={self.value_by_var_id}, "
            f"dual_by_var_id={self.dual_by_var_id})"
        )
