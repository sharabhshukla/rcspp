---
title: Installation
---

# Installation

## Python (recommended)

```bash
pip install rcspp
```

This installs pre-built wheels for Linux, macOS, and Windows (Python 3.11+).

## C++ library

### Prerequisites

- **CMake ≥ 3.26**
- **C++23 compiler** — Clang 21+ or GCC 13+

### Build from source

```bash
git clone --recursive https://github.com/lab-core/rcspp.git
cd rcspp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

To also build the Python bindings:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DRCSPP_BUILD_PYTHON=ON
cmake --build build
pip install python/
```

### Working on the Python package

An editable install builds the extension once and reads the Python sources from the
repository, so an edit to `python/src/rcspp/*.py` takes effect without reinstalling:

```bash
pip install -e .
```

An IDE or a type checker that uses this environment resolves `rcspp` to `python/src/rcspp`,
with the signatures and docstrings of the whole API. After a change to the C++ code or to the
bindings, run the command again.

### Include in your CMake project

```cmake
find_package(rcspp REQUIRED)
target_link_libraries(my_target PRIVATE rcspp::rcspp)
```

Or via FetchContent:

```cmake
include(FetchContent)
FetchContent_Declare(
    rcspp
    GIT_REPOSITORY https://github.com/lab-core/rcspp.git
    GIT_TAG        main
)
FetchContent_MakeAvailable(rcspp)
target_link_libraries(my_target PRIVATE rcspp::rcspp)
```
