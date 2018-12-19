# CodeGen

Python C++ code generation tool using libclang that integrates into qmake. Currently, it provides an enum reflection system that allows you to convert enum constant values to/from string. It could be extended with more features in the future.

# Requirements

Running CodeGen requires:
* LLVM 6.0.1 installation; currently must be installed to `C:\Program Files\LLVM` on Windows
* Python 3.x
* Python packages `clang` and `mako` (install via pip)

# Usage

In a qmake project:
* Set CODEGEN_OUT_PATH to the cpp file you would like codegen to output to.
* Set CODEGEN_SRC_PATH to the root folder containing your source files (which will normally be $$PWD).
* Include codegen.pri in your .pro file. The include must be at the bottom of the file, after the SOURCES, HEADERS, and INCLUDEPATH variables are fully initialized.

Include <codegen/EnumReflection.h> to use enum reflection features in your C++ code.
