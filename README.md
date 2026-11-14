# RCSPP

**RCSPP (Resource Constrained Shortest Path Problem)** is a C++ library
(built as a shared library: DLL on Windows, .so on Linux, .dylib on macOS)
for solving resource-constrained shortest path problems, with optional Python
bindings (via [pybind11]). Moreover, the project includes an optional VRP
column generation example (using Gurobi) to illustrate how to use the library.

---

## Installing the Python package

```sh
pip install rcspp
```

This installs a pre-built wheel, so no compiler is needed, for CPython 3.11 to 3.14
(and the free-threaded 3.14t) on:

- Linux x86_64 and aarch64 (glibc >= 2.28: `manylinux_2_28`)
- macOS 11 or later, arm64 and x86_64
- Windows x86_64

On the free-threaded build the extension does not declare itself safe without the GIL,
so the interpreter turns the GIL back on when `rcspp` is imported.

On any other platform `pip` builds from the source distribution, which needs the
prerequisites below (CMake and a C++23 compiler).

A first model:

```python
from rcspp.graph import ResourceGraph
from rcspp.resource import (
    AdditionExtensionFunction,
    MinMaxFeasibilityFunction,
    ValueCostFunction,
    ValueDominanceFunction,
)

rg = ResourceGraph()

# One real resource: distance, must stay <= 50
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

# add_arc(resource_consumption_tuple, origin, dest, cost)
rg.add_arc((10.0,), 0, 1, cost=10.0)
rg.add_arc((15.0,), 1, 3, cost=15.0)
rg.add_arc((20.0,), 0, 2, cost=20.0)
rg.add_arc((10.0,), 2, 3, cost=10.0)

result = rg.solve()
print(result.solutions[0].cost)           # 25.0
print(result.solutions[0].path_node_ids)  # [0, 1, 3]
```

The rest of this file is about building from source.

---

## Prerequisites

### RCSPP library

- **CMake >= 3.26**
- **C++ compiler** with C++23 support (e.g., Clang 21.1.0, or a compatible compiler;
  the Linux wheels are built with GCC 14)

### Python bindings

- **Python >= 3.11** (for Python bindings and pre-commit hooks)
- **Git** (to have pybind11 as a submodule)
- **[pybind11]** (as a submodule – auto-included when you follow instructions below)

To build and install the Python package from a clone, with the same prerequisites:

```sh
pip install .
```

### VRP

- **Gurobi >= 12.03**

---

## Getting the Source Code

For the C++ library and the VRP example, clone the RCSPP repository as follows:

```sh
git clone https://github.com/lab-core/rcspp.git
cd rcspp
```

If you plan to use the optional Python bindings, you must also clone the
repository with submodules to ensure pybind11 is present (as a submodule
under `extern/pybind11`):

```sh
git clone --recursive https://github.com/lab-core/rcspp.git
cd rcspp
```

If you already cloned without `--recursive` and now want to enable Python
bindings, run:  

```sh
git submodule update --init --recursive
```

---

## Getting the instances

To download the instances that can be used with the VRP example, use the
following command:

```sh
git lfs pull
```

---

## Building RCSPP

### Building the C++ library

To compile the library only:

```sh
mkdir build
cd build
cmake ..
cmake --build .
```

### Building the Python bindings

To compile the Python bindings, use the CMake option `USE_PYTHON=ON` (set to `OFF`
by default):

```sh
cmake -DUSE_PYTHON=ON ..
cmake --build .
```

### Building the VRP example

To compile the VRP example, use the CMake option `USE_VRP=ON` (set to `OFF`
by default):

```sh
cmake -DUSE_VRP=ON ..
cmake --build .
```

Note that these options can be combined:

```sh
cmake -DUSE_PYTHON=ON -DUSE_VRP=ON ..
cmake --build .
```

---

## Pre-commit and hooks

### Prerequisites for pre-commit

- **Git**
- **Python >= 3.11**
- **Node.js** (Required for `markdownlint-cli` (Markdown formatting))
- **C++ tools**
  - **clang-format** (for formatting C/C++ code)
  - **clang-tidy** (for C++ linting)
  - **cppcheck** (for static analysis)
  - **cpplint** (for C++ style checks)
  > On many systems, these can be installed via your package manager:
  > - Ubuntu:  
  >   `sudo apt-get install clang-format clang-tidy cppcheck cpplint`
  > - macOS (with Homebrew):  
  >   `brew install clang-format clang-tidy cppcheck cpplint`
  > - Windows:  
  >   Provided via [LLVM releases](https://releases.llvm.org/) or
 via [Chocolatey](https://chocolatey.org/).

### Installation

1. **Install pre-commit** (ensure you have Python >= 3.11):

   ```sh
   pip install pre-commit
   ```

2. **Install all hooks from [.pre-commit-config.yaml]** (to ensure hooks
run on every commit):

   ```sh
   pre-commit install --hook-type pre-commit
   ```

3. **[Optional] Update hooks** (to keep hooks up to date):

   ```sh
   pre-commit autoupdate
   ```

4. **[Optional] Run all hooks manually on all files:**

   ```sh
   pre-commit run --all-files
   ```

---

[pybind11]: https://github.com/pybind/pybind11
