# Define CODEGEN_OUT_FILE and then include this file in a qmake project
CodegenTarget.name = Codegen
CodegenTarget.input = SOURCES
CodegenTarget.output = $$CODEGEN_OUT_PATH
CodegenTarget.variable_out = SOURCES
CodegenTarget.commands = python $$PWD/codegen.py -pwd $$PWD -cmdinput -o $$CODEGEN_OUT_PATH -sourcefiles $$SOURCES -include $$INCLUDEPATH
CodegenTarget.CONFIG += target_predeps combine
QMAKE_EXTRA_COMPILERS += CodegenTarget