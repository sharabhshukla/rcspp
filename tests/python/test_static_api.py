#  Copyright (c) 2025 Laboratory for Combinatorial Optimization in Real-time Environment.
#  All rights reserved.
"""The public Python API is written out, not built at import time.

An IDE or a type checker reads the source, so it only sees a name that the source declares.
These tests fail when the extension gains a class, a function or a graph method that
``rcspp.graph`` or ``rcspp.resource`` does not declare by name.
"""

import ast
import inspect
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../python/src")))

import rcspp  # noqa: E402
from rcspp import _core  # noqa: E402
from rcspp import graph as graph_module  # noqa: E402
from rcspp import resource as resource_module  # noqa: E402
from rcspp._resource_types import ALL  # noqa: E402
from rcspp.graph import BucketAlgorithmParams, ResourceGraph  # noqa: E402
from rcspp.resource import (  # noqa: E402
    AdditionExtensionFunction,
    MinMaxFeasibilityFunction,
    SizeFeasibilityFunction,
    SubsetDominanceFunction,
    TrivialCostFunction,
    UnionExtensionFunction,
    ValueCostFunction,
    ValueDominanceFunction,
)


def _public(obj) -> set[str]:
    return {name for name in dir(obj) if not name.startswith("_")}


def _cpp_resource_graph_classes() -> list[type]:
    return [
        getattr(_core.graph, name)
        for name in dir(_core.graph)
        if name.startswith("_") and name.endswith("_resource_graph")
    ]


def _names_bound_in_source(module) -> set[str]:
    """The names a module's source binds at top level: what a static reader sees."""
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_graph_module_names_every_public_name_of_the_extension():
    # ResourceGraph is the Python class, patched into the extension module on import, and
    # BucketAlgorithmParams is wrapped by the Python class of the same name.
    expected = _public(_core.graph) - {"ResourceGraph", "BucketAlgorithmParams"}
    in_source = _names_bound_in_source(graph_module)
    assert expected - in_source == set()
    assert expected - set(graph_module.__all__) == set()
    for name in expected:
        assert getattr(graph_module, name) is getattr(_core.graph, name)


def test_resource_module_names_every_public_name_of_the_extension():
    expected = _public(_core.resource)
    in_source = _names_bound_in_source(resource_module)
    assert expected - in_source == set()
    assert expected - set(resource_module.__all__) == set()
    for name in expected:
        assert getattr(resource_module, name) is getattr(_core.resource, name)


def test_all_lists_only_names_that_exist():
    for module in (graph_module, resource_module, rcspp):
        missing = [name for name in module.__all__ if not hasattr(module, name)]
        assert missing == []


def test_resource_graph_declares_every_public_method_of_the_cpp_graphs():
    """A method reached only through ``__getattr__`` has no signature in an IDE."""
    declared = set(vars(ResourceGraph))
    classes = _cpp_resource_graph_classes()
    assert classes
    undeclared = {name for cls in classes for name in _public(cls) if name not in declared}
    assert undeclared == set()


def test_resource_graph_declares_one_add_resource_method_per_resource_type():
    for resource_type in ALL:
        method = vars(ResourceGraph).get(f"add_{resource_type}_resource")
        assert inspect.isfunction(method), resource_type
        assert method.__doc__
        assert list(inspect.signature(method).parameters) == [
            "self",
            "extension_function",
            "feasibility_function",
            "cost_function",
            "dominance_function",
        ]


def test_every_public_method_of_resource_graph_is_annotated_and_documented():
    for name, member in vars(ResourceGraph).items():
        if name.startswith("_") or not inspect.isfunction(member):
            continue
        assert member.__doc__, name
        signature = inspect.signature(member)
        assert signature.return_annotation is not inspect.Signature.empty, name
        for parameter in list(signature.parameters.values())[1:]:
            assert parameter.annotation is not inspect.Parameter.empty, (name, parameter.name)


def test_bucket_algorithm_params_declares_the_fields_it_forwards():
    """The wrapper forwards attributes at run time; its class body declares them for IDEs."""
    tree = ast.parse(inspect.getsource(graph_module))
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BucketAlgorithmParams"
    )
    declared: set[str] = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            declared.add(node.target.id)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            declared.add(node.name)
    assert _public(_core.graph.BucketAlgorithmParams) - declared == set()
    # And each one is forwarded.
    params = BucketAlgorithmParams()
    for name in _public(_core.graph.BucketAlgorithmParams):
        getattr(params, name)


# ── The declared methods do what the delegation did ───────────────────────────


def _diamond() -> ResourceGraph:
    """0 -> 1 -> 3 (cost 25) and 0 -> 2 -> 3 (cost 30); nothing is flushed yet."""
    rg = ResourceGraph()
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
    return rg


def test_counts_and_ids_flush_the_buffers_first():
    assert _diamond().number_of_nodes() == 4
    assert _diamond().number_of_arcs() == 4
    assert sorted(_diamond().node_ids()) == [0, 1, 2, 3]
    assert sorted(_diamond().arc_ids()) == [0, 1, 2, 3]
    assert _diamond().source_node_ids() == [0]
    assert _diamond().sink_node_ids() == [3]
    assert _diamond().removed_arc_ids() == []
    assert _diamond().next_arc_id() == 4


def test_node_questions():
    rg = _diamond()
    assert rg.is_source(0) and not rg.is_source(3)
    assert rg.is_sink(3) and not rg.is_sink(0)
    assert rg.is_connected(0, 3)


def test_remove_and_restore_one_arc_by_id_and_by_object():
    rg = _diamond()
    assert rg.remove_arc(0) is True
    assert rg.removed_arc_ids() == [0]
    assert rg.get_arc(0) is None
    removed = rg.get_removed_arc(0)
    assert removed is not None and removed.id == 0
    # preprocess=False: this test is about the two methods, not about what preprocessing
    # removes while an arc is out.
    assert rg.solve(preprocess=False).solutions[0].cost == 30.0
    assert rg.restore_arc(removed) is True
    assert rg.solve(preprocess=False).solutions[0].cost == 25.0

    arc = rg.get_arc(2)
    assert arc is not None
    assert rg.remove_arc(arc) is True
    assert rg.restore_arc(2) is True
    assert rg.removed_arc_ids() == []


def test_force_arc_removes_the_other_arcs_at_its_endpoints():
    rg = _diamond()
    removed = rg.force_arc(2)  # 0 -> 2: the other arc out of 0 is arc 0
    assert removed == [0]
    assert rg.solve().solutions[0].path_node_ids == [0, 2, 3]
    assert sorted(rg.restore_arcs(removed)) == [0]


def test_remove_and_restore_arcs_by_predicate():
    rg = _diamond()
    assert rg.remove_arcs_if(lambda arc: arc.cost >= 20.0) == [2]
    assert rg.restore_arcs_if(lambda arc: arc.id == 2) == [2]
    assert rg.number_of_arcs() == 4


def test_remove_infeasible_arcs_keeps_the_optimum():
    rg = _diamond()
    rg.remove_infeasible_arcs()
    assert rg.solve().solutions[0].cost == 25.0


def test_update_arc_takes_the_cost_by_position_or_keyword():
    rg = _diamond()
    arc = rg.get_arc(0)
    assert arc is not None
    rg.update_arc(arc, (12.0,), 12.0)
    assert arc.cost == 12.0
    rg.update_arc(arc, (11.0,), cost=11.0)
    assert arc.cost == 11.0
    rg.update_arc(arc, (10.0,))
    assert arc.cost == 11.0


def test_the_container_add_resource_methods_register_their_type():
    for method in ("add_real_set_resource", "add_int_set_resource", "add_bitset_resource"):
        rg = ResourceGraph()
        rg.add_real_resource(
            AdditionExtensionFunction(),
            MinMaxFeasibilityFunction(0.0, 50.0),
            ValueCostFunction(),
            ValueDominanceFunction(),
        )
        getattr(rg, method)(
            UnionExtensionFunction(),
            SizeFeasibilityFunction(0, 5),
            TrivialCostFunction(),
            SubsetDominanceFunction(),
        )
        rg.add_node(0, source=True)
        rg.add_node(1, sink=True)
        rg.add_arc((1.0, {1}), 0, 1, cost=1.0)
        assert rg.solve().solutions[0].cost == 1.0


def test_getattr_still_reaches_what_the_class_does_not_declare():
    rg = _diamond()
    assert callable(rg._add_nodes_bulk)
