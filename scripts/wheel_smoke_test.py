"""Smoke test of an installed rcspp wheel: the quickstart of the docs, with its output asserted,
and one reduced-cost update.

cibuildwheel runs it against every wheel it builds (``test-command`` in ``pyproject.toml``), in
an environment that has the wheel and nothing of the source tree. Run it by hand the same way::

    pip install rcspp
    python scripts/wheel_smoke_test.py

Keep it in step with ``docs/python/quickstart.md``.
"""

import sys

import rcspp
from rcspp.graph import ResourceGraph
from rcspp.resource import (
    AdditionExtensionFunction,
    MinMaxFeasibilityFunction,
    ValueCostFunction,
    ValueDominanceFunction,
)


def main() -> int:
    """Solve the quickstart graph, check its answer, then price it once with a dual."""
    rg = ResourceGraph()

    # One real resource: distance, must stay ≤ 50
    rg.add_real_resource(
        AdditionExtensionFunction(),
        MinMaxFeasibilityFunction(0.0, 50.0),
        ValueCostFunction(),
        ValueDominanceFunction(),
    )

    rg.add_node(0, source=True)
    rg.add_node(1)
    rg.add_node(2)
    rg.add_node(3, sink=True)

    rg.add_arc((10.0,), 0, 1, cost=10.0)
    rg.add_arc((15.0,), 1, 3, cost=15.0)
    rg.add_arc((20.0,), 0, 2, cost=20.0)
    rg.add_arc((10.0,), 2, 3, cost=10.0)

    result = rg.solve()
    cost = result.solutions[0].cost
    path = list(result.solutions[0].path_node_ids)
    status = result.status_string()
    print(cost)
    print(path)
    print(status)

    # One column generation step: a row on arc 0 -> 1 with dual 4 makes that arc cost 6, so the
    # path costs 21. (The distance is also the cost here and must stay >= 0, hence a small dual.)
    # This needs numpy, which the wheel must bring in as a dependency.
    rg.add_rows_to_arc(0, (0, 1.0))
    rg.update_reduced_costs([4.0])
    reduced_cost = rg.solve().solutions[0].cost
    print(reduced_cost)

    problems = []
    if reduced_cost != 21.0:
        problems.append(f"reduced cost is {reduced_cost!r}, expected 21.0")
    if cost != 25.0:
        problems.append(f"cost is {cost!r}, expected 25.0")
    if path != [0, 1, 3]:
        problems.append(f"path is {path!r}, expected [0, 1, 3]")
    if status != "complete":
        problems.append(f"status is {status!r}, expected 'complete'")
    for problem in problems:
        print(f"wheel smoke test failed ({rcspp.__file__}): {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
