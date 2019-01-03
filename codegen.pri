# Define CODEGEN_DIR, CODEGEN_OUT_PATH and CODEGEN_SRC_PATH, then include this file in a qmake project
# The include must be at the bottom of the file (after SOURCES, HEADERS, and INCLUDEPATH are all fully initialized)
Codegen.name = Codegen
Codegen.input = SOURCES
Codegen.output = $$CODEGEN_OUT_PATH
Codegen.variable_out = SOURCES
Codegen.commands = python3 $$CODEGEN_DIR/codegen.py -pwd $$CODEGEN_SRC_PATH -cmdinput -include $$INCLUDEPATH -sourcefiles $$SOURCES $$HEADERS -o $$CODEGEN_OUT_PATH
Codegen.CONFIG += target_predeps combine
QMAKE_EXTRA_COMPILERS += Codegen
DEFINES += WITH_CODEGEN
