---
title: Installation
---

# Installation

## Python (recommended)

```bash
pip install rcspp
```

This installs a pre-built wheel, so no compiler is needed, for CPython 3.11 to 3.14 (and the
free-threaded 3.14t) on Linux x86_64 and aarch64 (glibc ≥ 2.28), macOS 11 or later (arm64 and
x86_64) and Windows x86_64. On any other platform `pip` builds from the source distribution,
which needs the prerequisites below.

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
cmake -B build -DCMAKE_BUILD_TYPE=Release -DUSE_PYTHON=ON
cmake --build build
```

Or build and install the Python package in one step:

```bash
pip install .
```

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
