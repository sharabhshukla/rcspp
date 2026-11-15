#  Copyright (c) 2025 Laboratory for Combinatorial Optimization in Real-time Environment.
#  All rights reserved.
"""Resource-constrained shortest-path graph abstraction.

Provides the Python-side :class:`ResourceGraph` factory and the
:class:`BucketAlgorithmParams` helper.  The heavy lifting is done by a
generated C++ extension (``rcspp._core.graph``); this module handles lazy
construction, resource registration, buffered node/arc insertion, and
NetworkX integration.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeAlias

import networkx as nx

from . import _core as _ext

# The public names of the C++ graph module. They are listed by name, not copied in a loop, so
# that an IDE or a type checker sees them; tests/python/test_static_api.py fails when the
# extension gains a public name that is missing here.
from ._core.graph import (
    Algorithm,
    AlgorithmParams,
    AlgorithmStatus,
    Arc,
    BidirectionalStats,
)
from ._core.graph import BucketAlgorithmParams as _CppBucketAlgorithmParams
from ._core.graph import (
    Column,
    Graph,
    Node,
    Row,
    SearchDirection,
    Solution,
    SolveResult,
    check_interrupted,
)
from ._core.resource import (
    CostFunction_bitset,
    CostFunction_int,
    CostFunction_int_set,
    CostFunction_real,
    CostFunction_real_set,
    DominanceFunction_bitset,
    DominanceFunction_int,
    DominanceFunction_int_set,
    DominanceFunction_real,
    DominanceFunction_real_set,
    ExtensionFunction_bitset,
    ExtensionFunction_int,
    ExtensionFunction_int_set,
    ExtensionFunction_real,
    ExtensionFunction_real_set,
    FeasibilityFunction_bitset,
    FeasibilityFunction_int,
    FeasibilityFunction_int_set,
    FeasibilityFunction_real,
    FeasibilityFunction_real_set,
)
from ._resource_types import ALL, canonical
from .resource import (
    AnyResourceFunction,
    CostFunction,
    DominanceFunction,
    ExtensionFunction,
    FeasibilityFunction,
    _GenericFunctionDescriptor,
)

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

__all__ = [
    "ALGORITHMS",
    "Algorithm",
    "AlgorithmName",
    "AlgorithmParams",
    "AlgorithmStatus",
    "AnyArc",
    "AnyNode",
    "Arc",
    "BidirectionalStats",
    "BucketAlgorithmParams",
    "Column",
    "DirectionName",
    "Graph",
    "Node",
    "ResourceConsumption",
    "ResourceGraph",
    "ResourceValue",
    "Row",
    "RowLike",
    "SearchDirection",
    "Solution",
    "SolveResult",
    "check_interrupted",
]

# ── Argument types ────────────────────────────────────────────────────────────

#: An algorithm, by name. ``solve`` also takes the :class:`Algorithm` itself.
AlgorithmName: TypeAlias = Literal[
    "simple", "pushing", "pulling", "greedy", "tabu", "astar", "bidirectional"
]

#: A search direction, by name. ``solve`` also takes the :class:`SearchDirection` itself.
DirectionName: TypeAlias = Literal["forward", "backward", "bidirectional"]

#: A row of an arc: a :class:`Row`, or its ``(index, coefficient)``.
RowLike: TypeAlias = Row | tuple[int, float]

#: What one resource consumes on an arc: a number for ``real`` and ``int`` resources, a set for
#: the container ones, or a tuple that initialises a resource of several components.
ResourceValue: TypeAlias = float | set[int] | set[float] | tuple[Any, ...]

#: What an arc consumes: one :data:`ResourceValue` per registered resource, in the order of the
#: ``add_<type>_resource`` calls. A graph with a single resource also takes the bare value.
ResourceConsumption: TypeAlias = tuple[ResourceValue, ...] | float | set[int] | set[float]


class AnyNode(Protocol):
    """A node of a :class:`ResourceGraph`, whichever resource types the graph holds.

    The C++ node class depends on the graph's resource types (:class:`Node` with a single
    ``real`` resource). All of them have these members.
    """

    @property
    def id(self) -> int:
        """The node's id."""

    @property
    def source(self) -> bool:
        """Whether a path may start here."""

    @property
    def sink(self) -> bool:
        """Whether a path may end here."""


class AnyArc(Protocol):
    """An arc of a :class:`ResourceGraph`, whichever resource types the graph holds.

    The C++ arc class depends on the graph's resource types (:class:`Arc` with a single
    ``real`` resource). All of them have these members.
    """

    @property
    def id(self) -> int:
        """The arc's id."""

    @property
    def cost(self) -> float:
        """The arc's base cost, which ``update_reduced_costs`` never changes."""

    @property
    def rows(self) -> list[Row]:
        """The arc's coefficients in the master problem's constraints."""

    def origin(self) -> AnyNode:
        """The node the arc leaves."""

    def destination(self) -> AnyNode:
        """The node the arc enters."""


# String → Algorithm enum mapping
_ALGORITHM_MAP: dict[str, Callable[[], Algorithm]] = {
    "simple": lambda: _ext.graph.Algorithm.Simple,
    "pushing": lambda: _ext.graph.Algorithm.Pushing,
    "pulling": lambda: _ext.graph.Algorithm.Pulling,
    "greedy": lambda: _ext.graph.Algorithm.Greedy,
    "tabu": lambda: _ext.graph.Algorithm.Tabu,
    "astar": lambda: _ext.graph.Algorithm.AStar,
    "bidirectional": lambda: _ext.graph.Algorithm.Bidirectional,
}

# Kept for backward compatibility
ALGORITHMS = tuple(_ALGORITHM_MAP)

# String → SearchDirection mapping
_DIRECTIONS: dict[str, Callable[[], SearchDirection]] = {
    "forward": lambda: _ext.graph.SearchDirection.Forward,
    "backward": lambda: _ext.graph.SearchDirection.Backward,
    "bidirectional": lambda: _ext.graph.SearchDirection.Bidirectional,
}


def _search_direction(direction: SearchDirection | str) -> SearchDirection:
    """The ``SearchDirection`` that *direction* names, a string or the enum itself."""
    if isinstance(direction, str):
        factory = _DIRECTIONS.get(direction)
        if factory is None:
            raise ValueError(
                f"Unknown direction {direction!r}. Choose from: {', '.join(_DIRECTIONS)}"
            )
        return factory()
    return direction


# Canonical resource type names exposed through add_<type>_resource methods.
_ALL_RESOURCE_TYPES = ALL

# ── Type-signature → C++ class-name lookup table ─────────────────────────────
# Built by scanning _ext.graph for _*_resource_graph classes and parsing their
# names back to canonical Python-type tuples.  Adding a new combination to
# graph.cpp automatically makes it available here — no Python changes needed.

# Sorted longest-first so the greedy parser never confuses "real" with "real_set".
_TYPE_NAMES: list[str] = sorted(ALL, key=len, reverse=True)


def _parse_rg_class(attr: str) -> tuple[str, ...] | None:
    """Parse a _*_resource_graph attribute name into a canonical Python-type tuple.

    Returns None when the name contains a C++ type not in the Python registry
    """
    suffix = "_resource_graph"
    if not (attr.startswith("_") and attr.endswith(suffix)):
        return None
    inner = attr[1 : -len(suffix)]
    py_types: list[str] = []
    while inner:
        for name in _TYPE_NAMES:
            if inner == name:
                py_types.append(name)
                inner = ""
                break
            if inner.startswith(name + "_"):
                py_types.append(name)
                inner = inner[len(name) + 1 :]
                break
        else:
            return None
    return canonical(*py_types) if py_types else None


_RG_CLASS: dict[tuple[str, ...], str] = {}

_py_type_set = set(ALL)
for _attr in dir(_ext.graph):
    _types = _parse_rg_class(_attr)
    if _types is not None and all(t in _py_type_set for t in _types):
        _RG_CLASS[_types] = _attr


class ResourceGraph:
    """Factory that defers C++ ResourceGraph instantiation until the first graph
    operation, picking the right template from the resources added via
    :meth:`add_real_resource` / :meth:`add_int_resource` / etc.

    Nodes and arcs added via :meth:`add_node` / :meth:`add_arc` are buffered in
    Python and sent to C++ in one batch when the graph is first used (solve,
    get_node, get_arc, …) or when :meth:`update` is called explicitly.  This
    eliminates per-call Python→C++ overhead and allows the C++ hash-maps to be
    pre-allocated with a single ``reserve`` call.
    """

    def __init__(self) -> None:
        """Initialise an empty ResourceGraph.

        Register the resources first, then add nodes and arcs, or import a NetworkX graph
        with :meth:`from_networkx`.
        """
        # (canonical_type, ext, feas, cost, dom)
        self._pending: list[tuple[str, Any, Any, Any, Any]] = []
        self._refs: list[Any] = []  # keep Python wrappers alive against GC
        # The actual C++ object, created lazily. Its class depends on the registered resource
        # types, so it is not known statically.
        self._graph: Any = None
        # Set after _ensure_graph():
        #   _graph_canonical    – full slot tuple of the chosen C++ class (canonical order)
        #   _registered_order   – types in the order the user called add_<type>_resource()
        self._graph_canonical: tuple[str, ...] = ()
        self._registered_order: tuple[str, ...] = ()
        self._full_registration_order: list[str] = []  # per-instance, incl. duplicates
        # Buffers for deferred node/arc insertion
        self._node_buffer: list[tuple[int, bool, bool]] = []  # list of (id, source, sink)
        # list of (raw_consumption, origin, dest, cost, rows)
        self._arc_buffer: list[tuple[Any, int, int, float, list[Row]]] = []
        # list of (arc_id, row_index, coeff) triples
        self._rows_buffer: list[Any] = []
        self._reserve_hint: tuple[int, int] = (
            0,
            0,
        )  # (n_nodes, n_arcs) hint from reserve()
        self._next_arc_id: int = 0  # mirrors C++ next_arc_id_; returned by add_arc

    # ── Resource registration ─────────────────────────────────────────────────

    @staticmethod
    def _resolve(
        fn: _GenericFunctionDescriptor | AnyResourceFunction, canonical_type: str
    ) -> AnyResourceFunction:
        """Instantiate a typed C++ function object if *fn* is a generic descriptor."""
        if isinstance(fn, _GenericFunctionDescriptor):
            return fn.create(canonical_type)
        return fn

    def _add_resource(
        self,
        canonical_type: str,
        extension_function: _GenericFunctionDescriptor | AnyResourceFunction,
        feasibility_function: _GenericFunctionDescriptor | AnyResourceFunction,
        cost_function: _GenericFunctionDescriptor | AnyResourceFunction,
        dominance_function: _GenericFunctionDescriptor | AnyResourceFunction,
    ) -> None:
        """Register a resource of *canonical_type*; the ``add_<type>_resource`` methods call it."""
        if self._graph is not None:
            raise RuntimeError(
                f"Cannot call add_{canonical_type}_resource after the graph has been "
                "initialized (i.e. after the first solve / update / get_node call). "
                "Add all resources before using the graph."
            )
        if len(self._pending) == 0 and canonical_type != "real":
            raise ValueError(
                f"The first registered resource must be a cost resource ('real'), "
                f"got {canonical_type!r}. Register a real resource before any other type."
            )
        ext = self._resolve(extension_function, canonical_type)
        feas = self._resolve(feasibility_function, canonical_type)
        cost = self._resolve(cost_function, canonical_type)
        dom = self._resolve(dominance_function, canonical_type)
        self._pending.append((canonical_type, ext, feas, cost, dom))

    def add_real_resource(
        self,
        extension_function: ExtensionFunction | ExtensionFunction_real,
        feasibility_function: FeasibilityFunction | FeasibilityFunction_real,
        cost_function: CostFunction | CostFunction_real,
        dominance_function: DominanceFunction | DominanceFunction_real,
    ) -> None:
        """Register a real-valued resource (a C++ ``RealResource``, a ``float`` on each arc).

        Resources are numbered in the order they are registered, and each arc gives one
        consumption per resource in that order. The first resource registered must be a real
        one: it carries the cost. Register every resource before the graph is first used
        (``solve``, ``update``, ``get_node``, ...).

        Args:
            extension_function: How an arc changes the resource
                (e.g. ``AdditionExtensionFunction()``).
            feasibility_function: Which values are allowed
                (e.g. ``MinMaxFeasibilityFunction(0, 50)``).
            cost_function: What the resource adds to the objective
                (e.g. ``ValueCostFunction()``).
            dominance_function: When a label makes another redundant
                (e.g. ``ValueDominanceFunction()``).

        Raises:
            RuntimeError: If the graph has already been used.
        """
        self._add_resource(
            "real", extension_function, feasibility_function, cost_function, dominance_function
        )

    def add_int_resource(
        self,
        extension_function: ExtensionFunction | ExtensionFunction_int,
        feasibility_function: FeasibilityFunction | FeasibilityFunction_int,
        cost_function: CostFunction | CostFunction_int,
        dominance_function: DominanceFunction | DominanceFunction_int,
    ) -> None:
        """Register an integer resource (a C++ ``IntResource``, an ``int`` on each arc).

        Resources are numbered in the order they are registered, and each arc gives one
        consumption per resource in that order. Register every resource
        before the graph is first used (``solve``, ``update``, ``get_node``, ...).

        Args:
            extension_function: How an arc changes the resource
                (e.g. ``AdditionExtensionFunction()``).
            feasibility_function: Which values are allowed
                (e.g. ``MinMaxFeasibilityFunction(0, 50)``).
            cost_function: What the resource adds to the objective
                (e.g. ``ValueCostFunction()``).
            dominance_function: When a label makes another redundant
                (e.g. ``ValueDominanceFunction()``).

        Raises:
            RuntimeError: If the graph has already been used.
            ValueError: If no real resource has been registered yet.
        """
        self._add_resource(
            "int", extension_function, feasibility_function, cost_function, dominance_function
        )

    def add_real_set_resource(
        self,
        extension_function: ExtensionFunction | ExtensionFunction_real_set,
        feasibility_function: FeasibilityFunction | FeasibilityFunction_real_set,
        cost_function: CostFunction | CostFunction_real_set,
        dominance_function: DominanceFunction | DominanceFunction_real_set,
    ) -> None:
        """Register a resource that is a set of reals (a ``set[float]`` on each arc).

        Resources are numbered in the order they are registered, and each arc gives one
        consumption per resource in that order. Register every resource
        before the graph is first used (``solve``, ``update``, ``get_node``, ...).

        Args:
            extension_function: How an arc changes the resource
                (e.g. ``UnionExtensionFunction()``).
            feasibility_function: Which values are allowed
                (e.g. ``SizeFeasibilityFunction(0, 5)``).
            cost_function: What the resource adds to the objective
                (e.g. ``TrivialCostFunction()``).
            dominance_function: When a label makes another redundant
                (e.g. ``SubsetDominanceFunction()``).

        Raises:
            RuntimeError: If the graph has already been used.
            ValueError: If no real resource has been registered yet.
        """
        self._add_resource(
            "real_set", extension_function, feasibility_function, cost_function, dominance_function
        )

    def add_int_set_resource(
        self,
        extension_function: ExtensionFunction | ExtensionFunction_int_set,
        feasibility_function: FeasibilityFunction | FeasibilityFunction_int_set,
        cost_function: CostFunction | CostFunction_int_set,
        dominance_function: DominanceFunction | DominanceFunction_int_set,
    ) -> None:
        """Register a resource that is a set of integers (a ``set[int]`` on each arc).

        Resources are numbered in the order they are registered, and each arc gives one
        consumption per resource in that order. Register every resource
        before the graph is first used (``solve``, ``update``, ``get_node``, ...).

        Args:
            extension_function: How an arc changes the resource
                (e.g. ``UnionExtensionFunction()``).
            feasibility_function: Which values are allowed
                (e.g. ``SizeFeasibilityFunction(0, 5)``).
            cost_function: What the resource adds to the objective
                (e.g. ``TrivialCostFunction()``).
            dominance_function: When a label makes another redundant
                (e.g. ``SubsetDominanceFunction()``).

        Raises:
            RuntimeError: If the graph has already been used.
            ValueError: If no real resource has been registered yet.
        """
        self._add_resource(
            "int_set", extension_function, feasibility_function, cost_function, dominance_function
        )

    def add_bitset_resource(
        self,
        extension_function: ExtensionFunction | ExtensionFunction_bitset,
        feasibility_function: FeasibilityFunction | FeasibilityFunction_bitset,
        cost_function: CostFunction | CostFunction_bitset,
        dominance_function: DominanceFunction | DominanceFunction_bitset,
    ) -> None:
        """Register a resource that is a set of small non-negative integers, stored as a bitset
        (a ``set[int]`` on each arc).

        Resources are numbered in the order they are registered, and each arc gives one
        consumption per resource in that order. Register every resource
        before the graph is first used (``solve``, ``update``, ``get_node``, ...).

        Args:
            extension_function: How an arc changes the resource
                (e.g. ``UnionExtensionFunction()``).
            feasibility_function: Which values are allowed
                (e.g. ``SizeFeasibilityFunction(0, 5)``).
            cost_function: What the resource adds to the objective
                (e.g. ``TrivialCostFunction()``).
            dominance_function: When a label makes another redundant
                (e.g. ``SubsetDominanceFunction()``).

        Raises:
            RuntimeError: If the graph has already been used.
            ValueError: If no real resource has been registered yet.
        """
        self._add_resource(
            "bitset", extension_function, feasibility_function, cost_function, dominance_function
        )

    # ── Lazy construction ─────────────────────────────────────────────────────

    def _ensure_graph(self) -> None:
        if self._graph is not None:
            return

        # Preserve registration order (first occurrence of each type in _pending).
        reg_order: list[str] = []
        seen_set: set[str] = set()
        for r in self._pending:
            if r[0] not in seen_set:
                reg_order.append(r[0])
                seen_set.add(r[0])

        full_reg_order = [r[0] for r in self._pending]

        # The first registered resource must be a real-valued cost resource.
        if not full_reg_order:
            raise ValueError("At least one resource must be registered before using the graph.")
        if full_reg_order[0] != "real":  # pragma: no cover
            raise ValueError(
                f"The first registered resource must be a real resource for the cost, "
                f"got {full_reg_order[0]!r}. Register a real resource before any other type."
            )

        requested = frozenset(reg_order)
        types = canonical(*requested)

        cls_name = _RG_CLASS.get(types)
        selected_combo = types

        if cls_name is None:
            # Find the smallest C++ class that is a superset of the requested types.
            candidates = sorted(
                ((combo, cls) for combo, cls in _RG_CLASS.items() if requested <= frozenset(combo)),
                key=lambda x: len(x[0]),
            )
            if not candidates:  # pragma: no cover
                raise ValueError(
                    f"No C++ ResourceGraph is bound for resource combination {types!r}. "
                    f"Available combinations: {sorted(_RG_CLASS)}"
                )
            selected_combo, cls_name = candidates[0]

        self._graph_canonical = selected_combo
        self._registered_order = tuple(reg_order)
        self._full_registration_order = full_reg_order

        self._graph = getattr(_ext.graph, cls_name)()
        for r_type, ext, feas, cost, dom in self._pending:
            getattr(self._graph, f"add_{r_type}_resource")(ext, feas, cost, dom)
            self._refs.extend([ext, feas, cost, dom])
        self._pending.clear()

    def _flush(self) -> None:
        """Flush buffered nodes and arcs to C++, creating the graph if needed.

        Calls ``reserve`` once with the total expected counts so the C++ hash-maps
        are allocated in a single shot instead of rehashing on every insert.
        """
        self._ensure_graph()
        if not self._node_buffer and not self._arc_buffer and not self._rows_buffer:
            return
        n_nodes = max(
            self._reserve_hint[0],
            self._graph.number_of_nodes() + len(self._node_buffer),
        )
        n_arcs = max(self._reserve_hint[1], self._graph.number_of_arcs() + len(self._arc_buffer))
        self._graph.reserve(n_nodes, n_arcs)
        self._reserve_hint = (0, 0)
        if self._node_buffer:
            self._graph._add_nodes_bulk(self._node_buffer)
            self._node_buffer.clear()
        if self._arc_buffer:
            consumptions, origins, dests, costs, all_rows = [], [], [], [], []
            for raw_cons, origin_id, dest_id, cost, rows in self._arc_buffer:
                consumptions.append(self._normalize_consumption(raw_cons))
                origins.append(origin_id)
                dests.append(dest_id)
                costs.append(cost)
                all_rows.append(rows)
            self._arc_buffer.clear()
            try:
                self._graph._add_arcs_bulk(consumptions, origins, dests, costs, all_rows)
            except Exception:
                # C++ checks the whole batch before adding any arc, so a refused arc adds none
                # of them. Drop the batch, and the rows buffered for its arcs, and hand out ids
                # from where C++ stands again, so later arcs keep matching their C++ ids.
                self._next_arc_id = self._graph.next_arc_id()
                self._rows_buffer = [
                    row for row in self._rows_buffer if int(row[0]) < self._next_arc_id
                ]
                raise
        if self._rows_buffer:
            import numpy as np

            arr = np.array(self._rows_buffer, dtype=np.float64)
            self._graph._add_rows_bulk(arr)
            self._rows_buffer.clear()

    # ── Normalisation helper ──────────────────────────────────────────────────

    def _normalize_consumption(self, consumption: Any) -> tuple[list[Any], ...]:
        """Normalise a resource-consumption argument into canonical-ordered per-type
        lists.

        Returns a tuple with one list per canonical C++ slot, ready to pass to C++.
        Reordering is always applied.

        **Flat style** — one element per registered *instance* in the exact order
        ``add_<type>_resource`` was called (duplicates included).  A tuple value is
        passed as-is (multi-component initialiser); any other value is wrapped in a
        1-tuple::

            (1, 5.0, (3, 5), {4})
            # add_int / add_real / add_int / add_set were called in that order
            # → ([(1,), (3,5)], [(5.0,)], [({4},)]) after canonical reordering
        """
        if not isinstance(consumption, tuple):
            consumption = (consumption,)
        if len(consumption) != len(self._full_registration_order):
            raise ValueError(
                f"Expected {len(self._full_registration_order)} resource components in "
                f"consumption, got {len(consumption)}. The number of components must "
                f"match the number of registered resources (including duplicates) and "
                f"their order must match the order in which add_<type>_resource() was "
                f"called."
            )
        result: list[list[Any]] = [[] for _ in self._graph_canonical]
        for i, item in enumerate(consumption):
            rt = self._full_registration_order[i]
            slot = self._graph_canonical.index(rt)
            result[slot].append(item if isinstance(item, tuple) else (item,))
        return tuple(result)

    @staticmethod
    def _normalize_rows(rows: tuple[int, float] | Iterable[RowLike] | None) -> list[Row]:
        """Normalise rows to a list of Row objects.

        Args:
            rows: None, a single ``(index, coeff)`` tuple, a list of such tuples,
                  or a list of :class:`Row` objects (passed through unchanged).

        Returns:
            A list of :class:`Row` objects.
        """
        if rows is None:
            return []
        if isinstance(rows, tuple) and len(rows) == 2:
            return [Row(int(rows[0]), float(rows[1]))]  # type: ignore[arg-type]
        result: list[Row] = []
        for r in rows:
            if isinstance(r, tuple):
                result.append(Row(int(r[0]), float(r[1])))
            else:
                result.append(r)
        return result

    # ── Graph mutation (buffered) ─────────────────────────────────────────────

    def add_node(self, node_id: int, source: bool = False, sink: bool = False) -> None:
        """Buffer a node for insertion.

        The node is not sent to C++ immediately; call :meth:`update` or any read
        operation to flush the buffer.
        """
        self._node_buffer.append((int(node_id), bool(source), bool(sink)))

    def add_arc(
        self,
        resource_consumption: ResourceConsumption,
        origin_node_id: int,
        destination_node_id: int,
        cost: float = 0.0,
        rows: tuple[int, float] | Iterable[RowLike] | None = None,
    ) -> int:
        """Buffer an arc for insertion, and return its id.

        Args:
            resource_consumption: What the arc consumes: one value per registered resource,
                in the order of the ``add_<type>_resource`` calls.
            origin_node_id: The node the arc leaves.
            destination_node_id: The node the arc enters.
            cost: The arc's base cost.
            rows: The arc's coefficients in the master problem: ``(index, coefficient)``
                tuples or :class:`Row` objects.

        The arc is not sent to C++ immediately; call :meth:`update` or any read
        operation to flush the buffer.  Arc resource normalization happens at flush
        time so resources must be registered before :meth:`update` is called.

        An arc into a source or out of a sink is refused when the buffer is flushed,
        with a ``ValueError``: a path starts at a source and ends at a sink, so no path
        could use it. The flush then adds none of the buffered arcs: they are dropped,
        with the rows buffered for them, and the next ``add_arc`` returns the id C++ would
        assign, so ids keep matching after the error.
        """
        normalized_rows = self._normalize_rows(rows)
        arc_id = self._next_arc_id
        self._next_arc_id += 1
        self._arc_buffer.append(
            (
                resource_consumption,
                int(origin_node_id),
                int(destination_node_id),
                float(cost),
                normalized_rows,
            )
        )
        return arc_id

    def remove_arcs(self, arc_ids: Sequence[int] | npt.NDArray[np.integer[Any]]) -> list[int]:
        """Remove a batch of arcs by id.

        Args:
            arc_ids: list of arc ids **or** a 1-D numpy integer array.

        Returns:
            List of ids that were actually removed (ids not found in the graph
            are silently skipped).
        """
        self._flush()
        if hasattr(arc_ids, "tolist"):
            arc_ids = arc_ids.tolist()
        removed: list[int] = self._graph.remove_arcs(arc_ids)
        return removed

    def restore_arcs(self, arc_ids: Sequence[int] | npt.NDArray[np.integer[Any]]) -> list[int]:
        """Restore a batch of previously removed arcs by id.

        Args:
            arc_ids: list of arc ids **or** a 1-D numpy integer array.

        Returns:
            List of ids that were actually restored (ids not in the removed-arc
            pool are silently skipped).
        """
        self._flush()
        if hasattr(arc_ids, "tolist"):
            arc_ids = arc_ids.tolist()
        restored: list[int] = self._graph.restore_arcs(arc_ids)
        return restored

    def update(self) -> None:
        """Flush all buffered nodes and arcs to the C++ graph.

        Call this explicitly after bulk insertions if you need the graph to be
        up-to-date before inspecting it (e.g. ``get_node``, ``get_arc``, …).
        All read operations flush the buffer automatically, so this call is
        optional but can be useful for explicit control.
        """
        self._flush()

    def reserve(self, n_nodes: int, n_arcs: int) -> None:
        """Pre-allocate capacity for *n_nodes* nodes and *n_arcs* arcs.

        When called before the graph has been flushed, the hint is stored and applied at
        flush time so the C++ hash-maps are allocated in one shot. When called after the
        graph is already populated, the reservation is forwarded to C++ immediately.
        """
        if self._graph is not None:
            self._graph.reserve(n_nodes, n_arcs)
        else:
            self._reserve_hint = (
                max(self._reserve_hint[0], n_nodes),
                max(self._reserve_hint[1], n_arcs),
            )

    # ── Graph read operations (flush first) ───────────────────────────────────

    def get_node(self, node_id: int) -> AnyNode | None:
        """Return the node with the given ID, flushing pending buffers first.

        Args:
            node_id: Integer node identifier.

        Returns:
            The C++ node object for *node_id*, or ``None`` if there is none.
        """
        self._flush()
        node: AnyNode | None = self._graph.get_node(node_id)
        return node

    def get_arc(self, arc_id: int) -> AnyArc | None:
        """Return the arc with the given ID, flushing pending buffers first.

        Args:
            arc_id: Integer arc identifier.

        Returns:
            The C++ arc object for *arc_id*, or ``None`` if there is none or it
            is removed.
        """
        self._flush()
        arc: AnyArc | None = self._graph.get_arc(arc_id)
        return arc

    def get_arcs(self, origin_node_id: int, destination_node_id: int) -> list[AnyArc]:
        """Return the arcs from *origin_node_id* to *destination_node_id*."""
        self._flush()
        arcs: list[AnyArc] = self._graph.get_arcs(origin_node_id, destination_node_id)
        return arcs

    def update_arc(
        self, arc: AnyArc, resource_consumption: ResourceConsumption, cost: float | None = None
    ) -> None:
        """Update an arc's resource consumption in place.

        Flushes all pending buffers before modifying the arc so the C++ object
        is fully built.  The *resource_consumption* argument follows the same
        flat-style convention as :meth:`add_arc`.

        Args:
            arc: The arc to update, as :meth:`get_arc` returns it.
            resource_consumption: New resource consumption values, in the same
                order as the original :meth:`add_arc` call.
            cost: The arc's new base cost. ``None`` (the default) keeps the cost it has.
        """
        self._flush()
        norm_res_cons = self._normalize_consumption(resource_consumption)
        self._graph.update_arc(arc, norm_res_cons, cost)

    def add_rows_to_arc(self, arc_id: int, rows: tuple[int, float] | Iterable[RowLike]) -> None:
        """Buffer rows to be appended to arc *arc_id*; applied at next flush/solve.

        Args:
            arc_id: Target arc ID.
            rows: Single ``(index, coeff)`` tuple, a list of such tuples, or a
                  list of :class:`Row` objects.
        """
        arc_id = int(arc_id)
        row_list: Iterable[RowLike]
        if isinstance(rows, tuple) and len(rows) == 2:
            row_list = [rows]  # type: ignore[list-item]
        else:
            row_list = rows  # type: ignore[assignment]
        for r in row_list:
            if isinstance(r, tuple):
                self._rows_buffer.append((arc_id, int(r[0]), float(r[1])))
            else:
                self._rows_buffer.append((arc_id, int(r.index), float(r.coefficient)))

    def add_rows(
        self, data: Iterable[tuple[int, int, float]] | npt.NDArray[np.floating[Any]]
    ) -> None:
        """Buffer rows for multiple arcs at once; applied at next flush/solve.

        Args:
            data: Either a list of ``(arc_id, row_index, coeff)`` tuples or a
                  2-D numpy array with shape ``(N, 3)`` and columns
                  ``[arc_id, row_index, coeff]``.
        """
        if hasattr(data, "tolist"):
            self._rows_buffer.extend(data.tolist())
        else:
            self._rows_buffer.extend(data)

    def clone(self, include_rows: bool = True, clone_removed_arcs: bool = False) -> ResourceGraph:
        """Return a deep clone of this ResourceGraph with stable arc IDs.

        Flushes all pending buffers before cloning so the clone reflects the
        complete current state.  The returned graph has an independent
        remove/restore state and its own resource factory copy.

        Args:
            include_rows: Copy arc rows into the clone (set *False* for a
                topology-only clone to be populated via :meth:`add_rows`).
            clone_removed_arcs: Also clone arcs currently removed from the
                graph (they will be re-removed in the clone).

        Returns:
            A new :class:`ResourceGraph` wrapping the cloned C++ object.
        """
        self._flush()
        cpp_clone = self._graph.clone(include_rows, clone_removed_arcs)
        cloned = ResourceGraph.__new__(ResourceGraph)
        cloned._pending = []
        cloned._refs = list(self._refs)
        cloned._graph = cpp_clone
        cloned._graph_canonical = self._graph_canonical
        cloned._registered_order = self._registered_order
        cloned._full_registration_order = list(self._full_registration_order)
        cloned._node_buffer = []
        cloned._arc_buffer = []
        cloned._rows_buffer = []
        cloned._reserve_hint = (0, 0)
        cloned._next_arc_id = cpp_clone.next_arc_id()
        return cloned

    def clone_topology(self) -> ResourceGraph:
        """Clone topology only (arc rows are empty in the clone).

        Use :meth:`add_rows` or :meth:`add_rows_to_arc` to populate rows per
        (demand, time) slice after cloning.

        Returns:
            A new :class:`ResourceGraph` with no rows on arcs.
        """
        return self.clone(include_rows=False)

    def sort_nodes(self, comp: Callable[[AnyNode, AnyNode], bool] | None = None) -> None:
        """Sort graph nodes in place.

        Args:
            comp: Optional callable ``(node1, node2) -> bool`` returning True when
                *node1* should come before *node2*.  When omitted, nodes are sorted
                by ascending ``node.id``.
        """
        self._flush()
        if comp is None:
            self._graph.sort_nodes()
        else:
            self._graph.sort_nodes(comp)

    # ── Algorithm dispatch ────────────────────────────────────────────────────

    def solve(
        self,
        algorithm: Algorithm | AlgorithmName = "simple",
        upper_bound: float = math.inf,
        params: AlgorithmParams | BucketAlgorithmParams | None = None,
        preprocess: bool = True,
        cost_index: int = 0,
        direction: SearchDirection | DirectionName | None = None,
    ) -> SolveResult:
        """Solve the RCSPP.

        Args:
            algorithm: ``Algorithm.Simple`` (default), ``Algorithm.Pushing``,
                ``Algorithm.Pulling``, ``Algorithm.Greedy``, ``Algorithm.AStar``,
                ``Algorithm.Bidirectional``, or the equivalent strings
                ``'simple'``, ``'pushing'``, ``'pulling'``, ``'greedy'``,
                ``'astar'``, ``'bidirectional'``.

                ``'bidirectional'`` is ``'simple'`` with
                ``direction='bidirectional'``: it searches forward from the
                sources and backward from the sinks, and joins the two halves in
                the middle. Set ``params.critical_resource_index`` (the clock)
                and ``params.half_way_point`` (where the halves meet; with 0, the
                default, the solve is correct but slower than a forward one).
                Every resource must support backward extension, or the model
                checks raise ``RuntimeError`` before the search starts. See
                :doc:`the algorithms guide </advanced/algorithms>`.
            upper_bound: Prune paths with cost ≥ this value.
            params: :class:`AlgorithmParams` (defaults to ``AlgorithmParams()``).
            preprocess: Run preprocessing before solving.
            cost_index: Index within the cost resource type (the first ``real``
                or ``int`` slot in canonical order that the user registered).
                Defaults to 0.
            direction: ``'forward'``, ``'backward'`` or ``'bidirectional'`` (or a
                ``SearchDirection``). Only ``'simple'`` searches backward or
                bidirectionally; the other algorithms raise ``ValueError``.
                ``None`` (the default) uses ``params.direction`` (forward unless
                set), or ``'bidirectional'`` when ``algorithm='bidirectional'``;
                that algorithm raises ``ValueError`` with any other direction.
                The direction applies to this call only: ``params.direction`` is
                left unchanged. A backward or bidirectional solve runs the model
                checks first and raises ``RuntimeError`` on a model that fails
                them (see :meth:`check_model`).

        Returns:
            :class:`SolveResult` with a ``solutions`` list and an
            ``AlgorithmStatus`` indicating why the solver stopped.

            A ``complete`` status alone does not prove the answer optimal: if
            memory pressure dropped labels, only the labels that were kept were
            all processed. Check ``result.memory_pressure_triggered`` -- see
            :doc:`the algorithms guide </advanced/algorithms>`.
        """
        if cost_index < 0:
            raise ValueError(f"cost_index must be non-negative, got {cost_index}")
        check_interrupted()
        self._flush()
        cpp_params: AlgorithmParams
        if params is None:
            cpp_params = AlgorithmParams()
        elif isinstance(params, BucketAlgorithmParams):
            cpp_params = params._to_cpp(self._full_registration_order)
        else:
            cpp_params = params
        if isinstance(algorithm, str):
            factory = _ALGORITHM_MAP.get(algorithm)
            if factory is None:
                raise ValueError(
                    f"Unknown algorithm {algorithm!r}. Choose from: {', '.join(ALGORITHMS)}"
                )
            algorithm = factory()
        is_bidirectional_alias = algorithm == Algorithm.Bidirectional
        if direction is None:
            chosen = (
                SearchDirection.Bidirectional if is_bidirectional_alias else cpp_params.direction
            )
        else:
            chosen = _search_direction(direction)
        if is_bidirectional_alias and chosen != SearchDirection.Bidirectional:
            raise ValueError(
                "algorithm='bidirectional' searches bidirectionally; for another direction, "
                "use algorithm='simple' with that direction"
            )
        # Set for this call only: the caller's params keep their own direction.
        previous = cpp_params.direction
        cpp_params.direction = chosen
        try:
            result: SolveResult = self._graph.solve(
                algorithm, upper_bound, cpp_params, preprocess, cost_index
            )
            return result
        finally:
            cpp_params.direction = previous

    def check_model(
        self, direction: SearchDirection | DirectionName = "bidirectional"
    ) -> list[str]:
        """Run the model checks a search in *direction* needs, without solving.

        A forward search needs no checks. A backward search checks that every
        resource can be extended backward consistently with its forward
        definition; a bidirectional search also checks that forward and backward
        labels can be joined. A solve in that direction runs the same checks
        first and raises ``RuntimeError`` listing every problem.

        Args:
            direction: ``'forward'``, ``'backward'`` or ``'bidirectional'`` (the
                default), or a ``SearchDirection``.

        Returns:
            One string per problem; empty when the model is ready for that search.
        """
        self._flush()
        return list(self._graph.check_model(_search_direction(direction)))

    # ── Dual-based reduced-cost update ───────────────────────────────────────

    def update_reduced_costs(
        self,
        duals: Mapping[int, float] | Sequence[float] | npt.NDArray[np.floating[Any]],
        cost_index: int = 0,
    ) -> None:
        """Recompute arc extender costs from dual values without rebuilding the graph.

        For each arc, computes::

            reduced_cost = arc.cost - sum(row.coefficient * duals[row.index]
                                          for row in arc.rows)

        and writes ``reduced_cost`` to extender resource slot *cost_index*.
        ``arc.cost`` (base cost) is never modified, so repeated calls with
        different duals are correct across iterations.

        Args:
            duals: ``dict`` mapping row-index → dual value, **or** a ``list``
                   (or any sequence) where ``duals[i]`` is the dual for row *i*.
                   An empty dict is silently ignored.
            cost_index: Resource slot to update (default 0).
        """
        if cost_index < 0:
            raise ValueError(f"cost_index must be non-negative, got {cost_index}")
        self._flush()
        # The pybind binding only registers update_reduced_costs on graph
        # specialisations that include RealResource (see graph_impl.hpp). Without
        # this guard, int-only graphs raise a cryptic AttributeError referencing
        # the internal _core type name. Surface the real requirement instead.
        if not hasattr(self._graph, "update_reduced_costs"):  # pragma: no cover
            raise TypeError(
                "update_reduced_costs requires a graph with a RealResource cost "
                "slot; this graph has none."
            )

        if isinstance(duals, dict):
            if not duals:
                return  # honor the docstring: empty dict ⇒ leave reduced costs unchanged
            import numpy as np

            max_idx = max(duals.keys())
            duals_arr = np.zeros(max_idx + 1, dtype=np.float64)
            for k, v in duals.items():
                duals_arr[k] = v
        else:
            import numpy as np

            # ascontiguousarray is a no-op when duals is already a C-contiguous
            # float64 ndarray (the common hot-path case), avoiding tolist() overhead.
            duals_arr = np.ascontiguousarray(duals, dtype=np.float64)
        self._graph.update_reduced_costs(duals_arr, cost_index)

    # ── Reads and arc removal, forwarded to the C++ graph (flush first) ───────

    def number_of_nodes(self) -> int:
        """Return the number of nodes, buffered ones included."""
        self._flush()
        count: int = self._graph.number_of_nodes()
        return count

    def number_of_arcs(self) -> int:
        """Return the number of arcs in the graph, buffered ones included, removed ones not."""
        self._flush()
        count: int = self._graph.number_of_arcs()
        return count

    def node_ids(self) -> list[int]:
        """Return the ids of the nodes."""
        self._flush()
        ids: list[int] = self._graph.node_ids()
        return ids

    def source_node_ids(self) -> list[int]:
        """Return the ids of the source nodes."""
        self._flush()
        ids: list[int] = self._graph.source_node_ids()
        return ids

    def sink_node_ids(self) -> list[int]:
        """Return the ids of the sink nodes."""
        self._flush()
        ids: list[int] = self._graph.sink_node_ids()
        return ids

    def arc_ids(self) -> list[int]:
        """Return the ids of the arcs in the graph; removed arcs are not listed."""
        self._flush()
        ids: list[int] = self._graph.arc_ids()
        return ids

    def removed_arc_ids(self) -> list[int]:
        """Return the ids of the removed arcs, which :meth:`restore_arcs` can bring back."""
        self._flush()
        ids: list[int] = self._graph.removed_arc_ids()
        return ids

    def next_arc_id(self) -> int:
        """Return the id the next :meth:`add_arc` will be given."""
        self._flush()
        arc_id: int = self._graph.next_arc_id()
        return arc_id

    def is_source(self, node_id: int) -> bool:
        """Return whether *node_id* is a source."""
        self._flush()
        answer: bool = self._graph.is_source(node_id)
        return answer

    def is_sink(self, node_id: int) -> bool:
        """Return whether *node_id* is a sink."""
        self._flush()
        answer: bool = self._graph.is_sink(node_id)
        return answer

    def is_connected(self, origin_node_id: int, destination_node_id: int) -> bool:
        """Return whether *destination_node_id* can be reached from *origin_node_id*."""
        self._flush()
        answer: bool = self._graph.is_connected(origin_node_id, destination_node_id)
        return answer

    def get_removed_arc(self, arc_id: int) -> AnyArc | None:
        """Return the removed arc with this id, or ``None`` if no removed arc has it."""
        self._flush()
        arc: AnyArc | None = self._graph.get_removed_arc(arc_id)
        return arc

    def remove_arc(self, arc: int | AnyArc) -> bool:
        """Remove one arc, given by id or as an arc object; :meth:`restore_arc` brings it back.

        Returns:
            Whether an arc was removed.
        """
        self._flush()
        removed: bool = self._graph.remove_arc(arc)
        return removed

    def restore_arc(self, arc: int | AnyArc) -> bool:
        """Restore one removed arc, given by id or as an arc object.

        Returns:
            Whether an arc was restored.
        """
        self._flush()
        restored: bool = self._graph.restore_arc(arc)
        return restored

    def force_arc(self, arc: int | AnyArc) -> list[int]:
        """Make every path through the arc's endpoints use this arc.

        Removes all other arcs out of the arc's origin and all other arcs into its
        destination.

        Returns:
            The ids of the removed arcs, to pass to :meth:`restore_arcs`.
        """
        self._flush()
        removed: list[int] = self._graph.force_arc(arc)
        return removed

    def remove_arcs_if(self, pred: Callable[[AnyArc], bool]) -> list[int]:
        """Remove every arc for which *pred* returns true.

        Returns:
            The ids of the removed arcs.
        """
        self._flush()
        removed: list[int] = self._graph.remove_arcs_if(pred)
        return removed

    def restore_arcs_if(self, pred: Callable[[AnyArc], bool]) -> list[int]:
        """Restore every removed arc for which *pred* returns true.

        Returns:
            The ids of the restored arcs.
        """
        self._flush()
        restored: list[int] = self._graph.restore_arcs_if(pred)
        return restored

    def remove_infeasible_arcs(self) -> None:
        """Remove the arcs the feasibility preprocessor finds no feasible path can use."""
        self._flush()
        self._graph.remove_infeasible_arcs()

    # ── String representation ─────────────────────────────────────────────────

    def to_string(self, print_arcs: bool = False) -> str:
        """Return a human-readable string representation of the graph.

        Args:
            print_arcs: Include arc details in the output (default ``False``).

        Returns:
            Multi-line string describing the graph, or an empty string when the
            graph has not been initialised yet.
        """
        if self._graph is None and not self._node_buffer and not self._arc_buffer:
            return ""
        self._flush()
        text: str = self._graph.to_string(print_arcs)
        return text

    def __str__(self) -> str:
        """Return a human-readable string representation of the graph."""
        return self.to_string()

    def __repr__(self) -> str:
        """Return a one-line summary of the graph, without flushing the buffers.

        A repr must not fail: flushing could raise, for example when a buffered arc is
        refused, so this reads the counts as they stand.
        """
        nodes = arcs = 0
        if self._graph is not None:
            nodes = self._graph.number_of_nodes()
            arcs = self._graph.number_of_arcs()
        resources = self._registered_order or tuple(r[0] for r in self._pending)
        return (
            f"<ResourceGraph: {nodes} nodes, {arcs} arcs, "
            f"{len(self._node_buffer)} nodes and {len(self._arc_buffer)} arcs buffered, "
            f"resources={list(resources)}>"
        )

    # ── Transparent delegation for everything else ────────────────────────────

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attribute lookups to the underlying C++ graph.

        A last resort: every method of the C++ graph that users are meant to call is declared
        above, with its signature, and tests/python/test_static_api.py fails when the C++ graph
        gains a public method that is not. Called only when normal attribute lookup fails.
        Flushes pending buffers so the C++ object is up-to-date before the attribute is read.

        Args:
            name: Attribute name to look up on the C++ graph.

        Returns:
            The attribute value from the C++ graph object.
        """
        # Called only when normal lookup fails — flushes the buffer and forwards
        # to the C++ graph.
        self._flush()
        return getattr(self._graph, name)

    # ── NetworkX integration ──────────────────────────────────────────────────

    def from_networkx(self, nx_graph: nx.DiGraph[Any]) -> None:
        """Populate the graph from a NetworkX DiGraph.

        Nodes and arcs are buffered and flushed to C++ in a single batch.
        At least one node must be marked ``source=True`` and one ``sink=True``.
        When resources have already been registered, every edge must carry a
        ``'resource'`` attribute.

        Args:
            nx_graph: Directed NetworkX graph.  Each node may have ``source``
                and ``sink`` boolean attributes.  Each edge must have a
                ``'resource'`` attribute (tuple of consumption values) and may
                have a ``'cost'`` float and a ``'rows'`` list.

        Raises:
            ValueError: If no source or sink node is found, or if a required
                ``'resource'`` edge attribute is missing.
        """
        # ── Structural validation ─────────────────────────────────────────────
        source_nodes = [n for n, d in nx_graph.nodes(data=True) if d.get("source") is True]
        sink_nodes = [n for n, d in nx_graph.nodes(data=True) if d.get("sink") is True]
        if not source_nodes:
            raise ValueError(
                "NetworkX graph has no source node. "
                "Set source=True on at least one node:\n"
                "  G.nodes[node_id]['source'] = True\n"
                "  or G.add_node(node_id, source=True)"
            )
        if not sink_nodes:
            raise ValueError(
                "NetworkX graph has no sink node. "
                "Set sink=True on at least one node:\n"
                "  G.nodes[node_id]['sink'] = True\n"
                "  or G.add_node(node_id, sink=True)"
            )

        # ── Arc resource validation ───────────────────────────────────────────
        # If resources have been registered every arc must carry a 'resource' tuple;
        # otherwise the C++ binding would be called with the wrong argument types.
        resources_registered = bool(self._pending) or (self._graph is not None)
        if resources_registered:
            missing = [(u, v) for u, v, d in nx_graph.edges(data=True) if "resource" not in d]
            if missing:
                n_res = len(self._pending) or len(self._full_registration_order)
                pairs = ", ".join(f"({u} → {v})" for u, v in missing[:5])
                if len(missing) > 5:
                    pairs += f" … ({len(missing) - 5} more)"
                raise ValueError(
                    f"{len(missing)} arc(s) are missing a 'resource' attribute, "
                    f"but {n_res} resource(s) are registered: {pairs}.\n"
                    f"Provide resource consumption for every arc:\n"
                    f"  G.add_edge(u, v, resource=(val1, val2, ...))"
                )

        # ── Buffer nodes and arcs — flushed as one batch when graph is used ───
        for node_id, data in nx_graph.nodes(data=True):
            source = data.get("source", False) is True
            sink = data.get("sink", False) is True
            self.add_node(int(node_id), source, sink)

        for u, v, data in nx_graph.edges(data=True):
            if "resource" not in data:
                raise ValueError(
                    f"Arc ({u} → {v}) is missing 'resource' attribute. Provide resource "
                    f"consumption for every arc:\n  G.add_edge(u, v, resource=(val1, val2, ...))"
                )

            resource_init = tuple(data["resource"])
            cost = data.get("cost", 0.0)
            rows = data.get("rows", [])
            self.add_arc(resource_init, int(u), int(v), cost, rows)

        # Update the graph once everything is buffered
        self.update()


# Patch the C++ submodule so `from rcspp._core.graph import ResourceGraph` resolves correctly
_ext.graph.ResourceGraph = ResourceGraph

# ── BucketAlgorithmParams Python wrapper ─────────────────────────────────────
# _CppBucketAlgorithmParams, imported above, is the raw C++ class the wrapper instantiates.


class BucketAlgorithmParams:
    """AlgorithmParams variant using a bucket-partitioned label container.

    Pass ``bucket_resource_pos`` and/or ``sort_resource_pos`` to identify
    resources by their registration order (0 = first ``add_<type>_resource()``
    call, 1 = second, etc.).  Python resolves the position to the correct C++
    resource type and within-type index at solve time.

    When a position is not given (``None``), the corresponding C++ field
    (``bucket_resource_type`` / ``sort_resource_index``) is used as-is,
    preserving backward compatibility with code that sets those fields directly.

    Args:
        bucket_width: Width of each bucket along the bucket resource axis.
        bucket_resource_pos: Registration-order position of the resource used
            to partition labels into buckets.  ``None`` (default) keeps the
            C++ default (empty ``bucket_resource_type`` → cost resource).
        sort_resource_pos: Registration-order position of the resource used to
            sort labels within each bucket.  Must be a numerical resource
            (``real`` or ``int``).  ``None`` (default) keeps the C++ default
            (``sort_resource_index=0``).
        **kwargs: Additional :class:`AlgorithmParams` fields
            (e.g. ``max_solutions``, ``timeout_s``, ``max_memory_gb``).
    """

    def __init__(
        self,
        bucket_width: int = 100,
        bucket_resource_pos: int | None = None,
        sort_resource_pos: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Create BucketAlgorithmParams with optional resource-position hints.

        Args:
            bucket_width: Width of each bucket partition along the bucket
                resource axis.
            bucket_resource_pos: Zero-based registration-order index of the
                resource used to partition labels into buckets.  ``None``
                keeps the C++ default.
            sort_resource_pos: Zero-based registration-order index of the
                numerical resource used to sort labels within each bucket.
                ``None`` keeps the C++ default.
            **kwargs: Additional :class:`AlgorithmParams` fields forwarded
                directly to the C++ object (e.g. ``max_solutions``,
                ``timeout_s``, ``max_memory_gb``).
        """
        self._bucket_resource_pos = (
            None if bucket_resource_pos is None else int(bucket_resource_pos)
        )
        self._sort_resource_pos = None if sort_resource_pos is None else int(sort_resource_pos)
        self._cpp = _CppBucketAlgorithmParams()
        self._cpp.bucket_width = int(bucket_width)
        for k, v in kwargs.items():
            setattr(self._cpp, k, v)

    # The fields of the C++ params object, which __getattr__ and __setattr__ forward to. Declared
    # for IDEs and type checkers only; tests/python/test_static_api.py keeps the list in step
    # with the extension.
    if TYPE_CHECKING:
        bucket_resource_index: int
        bucket_resource_type: str
        bucket_width: int
        critical_resource_index: int
        direction: SearchDirection
        half_way_point: float
        join_after_early_stop: bool
        limit_to_available_ram: bool
        limit_to_total_ram: bool
        max_extended_labels_per_node: int
        max_iterations: int
        max_memory_gb: float
        max_phases: int
        max_solutions: int
        memory_check_interval: int
        memory_limit_fraction: float
        memory_pressure_fraction: float
        memory_pressure_max_labels_per_node: int
        prune_by_upper_bound: bool
        release_after_solve: bool
        return_dominated_solutions: bool
        seed: int
        sort_resource_index: int
        tabu_exempt_node_ids: set[int]
        tabu_random_noise: bool
        tabu_tenure: int
        timeout_s: float
        tolerance: float

        def check(self) -> None:
            """Validate the parameters; raises on an inconsistent combination."""

        def could_be_non_optimal(self) -> bool:
            """Return whether these parameters can stop a solve before it proves optimality."""

    def __getattr__(self, name: str) -> Any:
        """Forward public attribute reads to the underlying C++ params object.

        Args:
            name: Attribute name.

        Returns:
            The attribute value from the C++ ``BucketAlgorithmParams``.

        Raises:
            AttributeError: For private names (starting with ``_``).
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._cpp, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Forward public attribute writes to the underlying C++ params object.

        Private names (starting with ``_``) are stored on the Python instance
        via the default ``object.__setattr__`` mechanism.

        Args:
            name: Attribute name.
            value: Value to assign.
        """
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            setattr(self._cpp, name, value)

    def _to_cpp(self, full_registration_order: list[str]) -> _CppBucketAlgorithmParams:
        """Resolve resource positions and return the underlying C++ params object.

        Args:
            full_registration_order: Per-instance list of canonical resource type
                names in the order ``add_<type>_resource()`` was called
                (from :attr:`ResourceGraph._full_registration_order`).

        Returns:
            The configured C++ ``BucketAlgorithmParams`` ready for ``solve()``.
        """
        reg = full_registration_order
        n = len(reg)

        def resolve(pos: int, label: str) -> tuple[str, int]:
            if pos < 0 or pos >= n:
                raise ValueError(
                    f"{label}={pos} out of range; graph has {n} registered "
                    f"resource(s) (valid: 0–{n - 1})."
                )
            t = reg[pos]
            idx = sum(1 for r in reg[:pos] if r == t)
            return t, idx

        if self._bucket_resource_pos is not None:
            bucket_type, bucket_idx = resolve(self._bucket_resource_pos, "bucket_resource_pos")
            self._cpp.bucket_resource_type = bucket_type
            self._cpp.bucket_resource_index = bucket_idx

        if self._sort_resource_pos is not None:
            _, sort_idx = resolve(self._sort_resource_pos, "sort_resource_pos")
            self._cpp.sort_resource_index = sort_idx

        return self._cpp
