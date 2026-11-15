#  Copyright (c) 2025 Laboratory for Combinatorial Optimization in Real-time Environment.
#  All rights reserved.
"""Generic resource-function descriptors for the Python RCSPP API.

Each descriptor class is a lightweight, type-agnostic wrapper that defers
instantiation of the underlying typed C++ object until the resource type is
known (i.e. when ``add_xxx_resource`` is called on a ``ResourceGraph``).
C++ classes are registered as ``FunctionName_<resource_type>``
(e.g. ``ValueCostFunction_real``, ``UnionExtensionFunction_real_set``).
"""

from collections.abc import Iterable, Mapping
from typing import Any, TypeAlias

from . import _core as _ext

# The typed C++ classes, one per function and resource type. They are listed by name, not copied
# in a loop, so that an IDE or a type checker sees them; tests/python/test_static_api.py fails
# when the extension gains a class that is missing here.
from ._core.resource import (
    AdditionExtensionFunction_int,
    AdditionExtensionFunction_real,
    CapacityExtensionFunction_int,
    CapacityExtensionFunction_real,
    CostFunction_bitset,
    CostFunction_int,
    CostFunction_int_set,
    CostFunction_real,
    CostFunction_real_set,
    DifferenceExtensionFunction_bitset,
    DifferenceExtensionFunction_int_set,
    DifferenceExtensionFunction_real_set,
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
    IntersectionExtensionFunction_bitset,
    IntersectionExtensionFunction_int_set,
    IntersectionExtensionFunction_real_set,
    IntersectionFeasibilityFunction_bitset,
    IntersectionFeasibilityFunction_int_set,
    IntersectionFeasibilityFunction_real_set,
    MinMaxFeasibilityFunction_int,
    MinMaxFeasibilityFunction_real,
    NgPathExtensionFunction_bitset,
    NgPathExtensionFunction_int_set,
    NgPathExtensionFunction_real_set,
    SizeFeasibilityFunction_bitset,
    SizeFeasibilityFunction_int_set,
    SizeFeasibilityFunction_real_set,
    SubsetDominanceFunction_bitset,
    SubsetDominanceFunction_int_set,
    SubsetDominanceFunction_real_set,
    SupersetDominanceFunction_bitset,
    SupersetDominanceFunction_int_set,
    SupersetDominanceFunction_real_set,
    TimeWindowExtensionFunction_int,
    TimeWindowExtensionFunction_real,
    TimeWindowFeasibilityFunction_int,
    TimeWindowFeasibilityFunction_real,
    TrivialCostFunction_bitset,
    TrivialCostFunction_int,
    TrivialCostFunction_int_set,
    TrivialCostFunction_real,
    TrivialCostFunction_real_set,
    TrivialFeasibilityFunction_bitset,
    TrivialFeasibilityFunction_int,
    TrivialFeasibilityFunction_int_set,
    TrivialFeasibilityFunction_real,
    TrivialFeasibilityFunction_real_set,
    UnionExtensionFunction_bitset,
    UnionExtensionFunction_int_set,
    UnionExtensionFunction_real_set,
    ValueCostFunction_int,
    ValueCostFunction_real,
    ValueDominanceFunction_int,
    ValueDominanceFunction_real,
)

__all__ = [
    # Generic descriptors: the resource type is chosen by the add_<type>_resource call.
    "AdditionExtensionFunction",
    "CapacityExtensionFunction",
    "DifferenceExtensionFunction",
    "IntersectionExtensionFunction",
    "IntersectionFeasibilityFunction",
    "MinMaxFeasibilityFunction",
    "NgPathExtensionFunction",
    "SizeFeasibilityFunction",
    "SubsetDominanceFunction",
    "SupersetDominanceFunction",
    "TimeWindowExtensionFunction",
    "TimeWindowFeasibilityFunction",
    "TrivialCostFunction",
    "TrivialFeasibilityFunction",
    "UnionExtensionFunction",
    "ValueCostFunction",
    "ValueDominanceFunction",
    # The base of each role's generic descriptors.
    "CostFunction",
    "DominanceFunction",
    "ExtensionFunction",
    "FeasibilityFunction",
    # What a generic descriptor creates, for annotations.
    "AnyCostFunction",
    "AnyDominanceFunction",
    "AnyExtensionFunction",
    "AnyFeasibilityFunction",
    "AnyResourceFunction",
    # Typed C++ classes.
    "AdditionExtensionFunction_int",
    "AdditionExtensionFunction_real",
    "CapacityExtensionFunction_int",
    "CapacityExtensionFunction_real",
    "CostFunction_bitset",
    "CostFunction_int",
    "CostFunction_int_set",
    "CostFunction_real",
    "CostFunction_real_set",
    "DifferenceExtensionFunction_bitset",
    "DifferenceExtensionFunction_int_set",
    "DifferenceExtensionFunction_real_set",
    "DominanceFunction_bitset",
    "DominanceFunction_int",
    "DominanceFunction_int_set",
    "DominanceFunction_real",
    "DominanceFunction_real_set",
    "ExtensionFunction_bitset",
    "ExtensionFunction_int",
    "ExtensionFunction_int_set",
    "ExtensionFunction_real",
    "ExtensionFunction_real_set",
    "FeasibilityFunction_bitset",
    "FeasibilityFunction_int",
    "FeasibilityFunction_int_set",
    "FeasibilityFunction_real",
    "FeasibilityFunction_real_set",
    "IntersectionExtensionFunction_bitset",
    "IntersectionExtensionFunction_int_set",
    "IntersectionExtensionFunction_real_set",
    "IntersectionFeasibilityFunction_bitset",
    "IntersectionFeasibilityFunction_int_set",
    "IntersectionFeasibilityFunction_real_set",
    "MinMaxFeasibilityFunction_int",
    "MinMaxFeasibilityFunction_real",
    "NgPathExtensionFunction_bitset",
    "NgPathExtensionFunction_int_set",
    "NgPathExtensionFunction_real_set",
    "SizeFeasibilityFunction_bitset",
    "SizeFeasibilityFunction_int_set",
    "SizeFeasibilityFunction_real_set",
    "SubsetDominanceFunction_bitset",
    "SubsetDominanceFunction_int_set",
    "SubsetDominanceFunction_real_set",
    "SupersetDominanceFunction_bitset",
    "SupersetDominanceFunction_int_set",
    "SupersetDominanceFunction_real_set",
    "TimeWindowExtensionFunction_int",
    "TimeWindowExtensionFunction_real",
    "TimeWindowFeasibilityFunction_int",
    "TimeWindowFeasibilityFunction_real",
    "TrivialCostFunction_bitset",
    "TrivialCostFunction_int",
    "TrivialCostFunction_int_set",
    "TrivialCostFunction_real",
    "TrivialCostFunction_real_set",
    "TrivialFeasibilityFunction_bitset",
    "TrivialFeasibilityFunction_int",
    "TrivialFeasibilityFunction_int_set",
    "TrivialFeasibilityFunction_real",
    "TrivialFeasibilityFunction_real_set",
    "UnionExtensionFunction_bitset",
    "UnionExtensionFunction_int_set",
    "UnionExtensionFunction_real_set",
    "ValueCostFunction_int",
    "ValueCostFunction_real",
    "ValueDominanceFunction_int",
    "ValueDominanceFunction_real",
]

# ── The four roles, over every resource type ──────────────────────────────────
# Each typed class derives from the base of its role and resource type
# (ValueCostFunction_real from CostFunction_real, ...).

AnyExtensionFunction: TypeAlias = (
    ExtensionFunction_real
    | ExtensionFunction_int
    | ExtensionFunction_real_set
    | ExtensionFunction_int_set
    | ExtensionFunction_bitset
)
AnyFeasibilityFunction: TypeAlias = (
    FeasibilityFunction_real
    | FeasibilityFunction_int
    | FeasibilityFunction_real_set
    | FeasibilityFunction_int_set
    | FeasibilityFunction_bitset
)
AnyCostFunction: TypeAlias = (
    CostFunction_real
    | CostFunction_int
    | CostFunction_real_set
    | CostFunction_int_set
    | CostFunction_bitset
)
AnyDominanceFunction: TypeAlias = (
    DominanceFunction_real
    | DominanceFunction_int
    | DominanceFunction_real_set
    | DominanceFunction_int_set
    | DominanceFunction_bitset
)
AnyResourceFunction: TypeAlias = (
    AnyExtensionFunction | AnyFeasibilityFunction | AnyCostFunction | AnyDominanceFunction
)

# ── Generic resource-function descriptors ─────────────────────────────────────
# These are resolved to the correct typed C++ object when add_xxx_resource is
# called on a ResourceGraph. Naming convention: C++ classes are registered as
# FunctionName_<resource_type> (e.g. ValueCostFunction_real, UnionExtensionFunction_real_set).


class _GenericFunctionDescriptor:
    """Base marker for generic (type-unspecialized) resource function descriptors.

    Subclasses implement ``create`` to instantiate the appropriate typed C++
    object once the concrete resource type is known.
    """

    def create(self, resource_type: str) -> AnyResourceFunction:
        """Instantiate the typed C++ function object for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError


# ── One base per role ─────────────────────────────────────────────────────────
# add_<type>_resource takes one function of each role, in this order. The bases let a type
# checker refuse, say, a feasibility function passed where the extension function goes.


class ExtensionFunction(_GenericFunctionDescriptor):
    """Base of the generic extension functions: how an arc changes the resource."""

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate the typed C++ extension function for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError


class FeasibilityFunction(_GenericFunctionDescriptor):
    """Base of the generic feasibility functions: whether a resource value is allowed."""

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate the typed C++ feasibility function for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError


class CostFunction(_GenericFunctionDescriptor):
    """Base of the generic cost functions: what the resource adds to the objective."""

    def create(self, resource_type: str) -> AnyCostFunction:
        """Instantiate the typed C++ cost function for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError


class DominanceFunction(_GenericFunctionDescriptor):
    """Base of the generic dominance functions: when one label makes another redundant."""

    def create(self, resource_type: str) -> AnyDominanceFunction:
        """Instantiate the typed C++ dominance function for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError


def _get_fn(fn_name: str, resource_type: str) -> Any:
    """Look up a typed C++ class by name and resource type.

    Args:
        fn_name: Base name of the C++ class (e.g. ``"ValueCostFunction"``).
        resource_type: Resource type suffix (e.g. ``"real"``, ``"int_set"``).

    Returns:
        The C++ class registered as ``{fn_name}_{resource_type}``.

    Raises:
        TypeError: If no matching class is found in the C++ extension module.
    """
    cls = getattr(_ext.resource, f"{fn_name}_{resource_type}", None)
    if cls is None:
        raise TypeError(f"{fn_name} is not available for resource type '{resource_type}'")
    return cls


# ── Numerical + container: trivial ───────────────────────────────────────────


class TrivialFeasibilityFunction(FeasibilityFunction):
    """Feasibility function that always returns feasible.

    Applicable to both numerical and container resource types.
    """

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate a TrivialFeasibilityFunction for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Returns:
            A typed C++ TrivialFeasibilityFunction instance.
        """
        return _get_fn("TrivialFeasibilityFunction", resource_type)()


class TrivialCostFunction(CostFunction):
    """Cost function that always returns zero cost.

    Applicable to both numerical and container resource types.
    """

    def create(self, resource_type: str) -> AnyCostFunction:
        """Instantiate a TrivialCostFunction for *resource_type*.

        Args:
            resource_type: Resource type string (e.g. ``"real"``, ``"int_set"``).

        Returns:
            A typed C++ TrivialCostFunction instance.
        """
        return _get_fn("TrivialCostFunction", resource_type)()


# ── Numerical only ────────────────────────────────────────────────────────────


class AdditionExtensionFunction(ExtensionFunction):
    """Extension function that adds the arc consumption to the resource value.

    Applicable to numerical resource types only.
    """

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate an AdditionExtensionFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ AdditionExtensionFunction instance.
        """
        return _get_fn("AdditionExtensionFunction", resource_type)()


class ValueCostFunction(CostFunction):
    """Cost function that uses the resource value directly as cost.

    Applicable to numerical resource types only.
    """

    def create(self, resource_type: str) -> AnyCostFunction:
        """Instantiate a ValueCostFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ ValueCostFunction instance.
        """
        return _get_fn("ValueCostFunction", resource_type)()


class ValueDominanceFunction(DominanceFunction):
    """Dominance function that compares resource values directly.

    A label dominates another if its resource value is less than or equal to the
    other's. Applicable to numerical resource types only.
    """

    def create(self, resource_type: str) -> AnyDominanceFunction:
        """Instantiate a ValueDominanceFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ ValueDominanceFunction instance.
        """
        return _get_fn("ValueDominanceFunction", resource_type)()


class MinMaxFeasibilityFunction(FeasibilityFunction):
    """Feasibility function that enforces a [min, max] bound on a resource value.

    A label is feasible when its resource value lies within the closed interval
    ``[min_value, max_value]``. Applicable to numerical resource types only.
    """

    def __init__(self, min_value: float, max_value: float) -> None:
        """Initialize the feasibility bounds.

        Args:
            min_value: Lower bound (inclusive) on the resource value.
            max_value: Upper bound (inclusive) on the resource value.
        """
        self.min_value = min_value
        self.max_value = max_value

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate a MinMaxFeasibilityFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ MinMaxFeasibilityFunction instance.
        """
        return _get_fn("MinMaxFeasibilityFunction", resource_type)(self.min_value, self.max_value)


class TimeWindowExtensionFunction(ExtensionFunction):
    """Extension function that advances the resource to the earliest feasible time.

    At each node the resource value is extended by the arc consumption and then clamped
    to the node's time-window lower bound (i.e. waiting is allowed). Applicable to
    numerical resource types only.
    """

    def __init__(
        self,
        tw_by_node: Mapping[int, tuple[float, float]],
        default_max_value: float | None = None,
    ) -> None:
        """Initialize the time-window extension function.

        Args:
            tw_by_node: Mapping from node identifier to ``(earliest, latest)``
                time-window tuples.
            default_max_value: Fallback upper bound used for nodes not present
                in *tw_by_node*. When ``None`` the C++ default is applied.
        """
        self.tw_by_node = tw_by_node
        self.default_max_value = default_max_value

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate a TimeWindowExtensionFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ TimeWindowExtensionFunction instance.
        """
        fn = _get_fn("TimeWindowExtensionFunction", resource_type)
        if self.default_max_value is None:
            return fn(dict(self.tw_by_node))
        return fn(dict(self.tw_by_node), self.default_max_value)


class CapacityExtensionFunction(ExtensionFunction):
    """A capacity: a load summed along the path that must stay within a cap.

    It also supports backward search. Forward, it adds each arc's load, like
    :class:`AdditionExtensionFunction`. Backward, a label starts at the cap and subtracts
    each load, so it holds how much load the rest of the path, back to the source, may
    still use. This lets it be used in a backward or bidirectional solve, and as the
    bidirectional clock. Only signed types (``"real"``, ``"int"``) are supported, since the
    backward step subtracts.

    Pair it with ``MinMaxFeasibilityFunction(0, capacity)`` using the same capacity: a
    backward or bidirectional solve refuses a cap that differs from the feasibility
    function's maximum. :func:`rcspp.presets.add_capacity_resource` registers the pair.
    """

    def __init__(self, capacity: float) -> None:
        """Initialize the capacity extension function.

        Args:
            capacity: The upper bound at every node.
        """
        self.capacity = capacity

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate a CapacityExtensionFunction for *resource_type*.

        Args:
            resource_type: Signed numerical resource type string (``"real"`` or ``"int"``).

        Returns:
            A typed C++ CapacityExtensionFunction instance.

        Raises:
            TypeError: If *resource_type* is not one of the signed numerical types.
        """
        fn = _get_fn("CapacityExtensionFunction", resource_type)
        return fn(self.capacity)


class TimeWindowFeasibilityFunction(FeasibilityFunction):
    """Feasibility function that checks whether a resource value lies within a time
    window.

    A label is feasible at a node when its resource value does not exceed the node's
    latest time. Applicable to numerical resource types only.
    """

    def __init__(
        self,
        tw_by_node: Mapping[int, tuple[float, float]],
        default_max_value: float | None = None,
    ) -> None:
        """Initialize the time-window feasibility function.

        Args:
            tw_by_node: Mapping from node identifier to ``(earliest, latest)``
                time-window tuples.
            default_max_value: Fallback upper bound used for nodes not present
                in *tw_by_node*. When ``None`` the C++ default is applied.
        """
        self.tw_by_node = tw_by_node
        self.default_max_value = default_max_value

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate a TimeWindowFeasibilityFunction for *resource_type*.

        Args:
            resource_type: Numerical resource type string (e.g. ``"real"``,
                ``"int"``).

        Returns:
            A typed C++ TimeWindowFeasibilityFunction instance.
        """
        fn = _get_fn("TimeWindowFeasibilityFunction", resource_type)
        if self.default_max_value is None:
            return fn(dict(self.tw_by_node))
        return fn(dict(self.tw_by_node), self.default_max_value)


# ── Container only ────────────────────────────────────────────────────────────


class UnionExtensionFunction(ExtensionFunction):
    """Extension function that unions the arc consumption set into the resource.

    Applicable to container resource types only.
    """

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate a UnionExtensionFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ UnionExtensionFunction instance.
        """
        return _get_fn("UnionExtensionFunction", resource_type)()


class IntersectionExtensionFunction(ExtensionFunction):
    """Extension function that intersects the resource with the arc consumption set.

    Applicable to container resource types only.
    """

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate an IntersectionExtensionFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ IntersectionExtensionFunction instance.
        """
        return _get_fn("IntersectionExtensionFunction", resource_type)()


class DifferenceExtensionFunction(ExtensionFunction):
    """Extension function that removes the arc consumption set from the resource.

    Applicable to container resource types only.
    """

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate a DifferenceExtensionFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ DifferenceExtensionFunction instance.
        """
        return _get_fn("DifferenceExtensionFunction", resource_type)()


class SubsetDominanceFunction(DominanceFunction):
    """Dominance function based on set inclusion.

    A label dominates another if its resource set is a subset of the other's. Applicable
    to container resource types only.
    """

    def create(self, resource_type: str) -> AnyDominanceFunction:
        """Instantiate a SubsetDominanceFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ SubsetDominanceFunction instance.
        """
        return _get_fn("SubsetDominanceFunction", resource_type)()


class SupersetDominanceFunction(DominanceFunction):
    """Dominance function based on superset containment.

    A label dominates another if its resource set is a superset of the other's.
    Applicable to container resource types only.
    """

    def create(self, resource_type: str) -> AnyDominanceFunction:
        """Instantiate a SupersetDominanceFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ SupersetDominanceFunction instance.
        """
        return _get_fn("SupersetDominanceFunction", resource_type)()


class SizeFeasibilityFunction(FeasibilityFunction):
    """Feasibility function that enforces a cardinality bound on a container resource.

    A label is feasible when the size of its resource set lies within the
    closed interval ``[min_size, max_size]``. Applicable to container resource
    types only.
    """

    def __init__(self, min_size: int, max_size: int) -> None:
        """Initialize the size feasibility bounds.

        Args:
            min_size: Minimum required cardinality of the resource set.
            max_size: Maximum allowed cardinality of the resource set.
        """
        self.min_size = min_size
        self.max_size = max_size

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate a SizeFeasibilityFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ SizeFeasibilityFunction instance.
        """
        return _get_fn("SizeFeasibilityFunction", resource_type)(self.min_size, self.max_size)


class NgPathExtensionFunction(ExtensionFunction):
    """Extension function of the ng-path memory.

    Along an arc, adds the node the label leaves to its set, then keeps only the members
    of the arrival node's neighbourhood. The node comes from the arc's endpoints, not
    its value, so the same formula works backward. Applicable to container resource
    types only.
    """

    def __init__(self, neighborhoods: Mapping[int, Iterable[int]]) -> None:
        """Initialize the ng-neighbourhoods.

        Args:
            neighborhoods: ``{node_id: ng-neighbourhood}``. A node absent from the map forgets
                the whole memory on arrival.
        """
        self.neighborhoods: dict[int, set[int]] = {
            node: set(members) for node, members in neighborhoods.items()
        }

    def create(self, resource_type: str) -> AnyExtensionFunction:
        """Instantiate an NgPathExtensionFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ NgPathExtensionFunction instance.
        """
        return _get_fn("NgPathExtensionFunction", resource_type)(self.neighborhoods)


class IntersectionFeasibilityFunction(FeasibilityFunction):
    """Feasibility function testing the resource set against per-node values.

    With ``forbidden=True`` (the default), a label is infeasible at a node when its set meets the
    node's values; with ``forbidden=False``, when it does not. Applicable to container resource
    types only.
    """

    def __init__(self, values_by_node: Mapping[int, Iterable[int]], forbidden: bool = True) -> None:
        """Initialize the per-node values.

        Args:
            values_by_node: ``{node_id: values}``; a node absent from the map is not tested.
            forbidden: Whether the values are forbidden (``True``) or required (``False``).
        """
        self.values_by_node: dict[int, set[int]] = {
            node: set(values) for node, values in values_by_node.items()
        }
        self.forbidden = forbidden

    def create(self, resource_type: str) -> AnyFeasibilityFunction:
        """Instantiate an IntersectionFeasibilityFunction for *resource_type*.

        Args:
            resource_type: Container resource type string
                (e.g. ``"real_set"``, ``"int_set"``, ``"bitset"``).

        Returns:
            A typed C++ IntersectionFeasibilityFunction instance.
        """
        return _get_fn("IntersectionFeasibilityFunction", resource_type)(
            self.values_by_node, self.forbidden
        )
