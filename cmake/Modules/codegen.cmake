cmake_minimum_required(VERSION 3.12)

function(add_codegen_targets
    source_files
    generated_files_var
    input_root
    output_root
    include_directories
)
    #
    # Find our python interpreter, and set up some python related variables.
    #
    find_package(PythonInterp 3.6 REQUIRED)
    set(venv_path "${CMAKE_CURRENT_BINARY_DIR}/codegen_venv")
    set(venv_dummy "${CMAKE_CURRENT_BINARY_DIR}/codegen_venv_dummy")
    set(package_dummy "${CMAKE_CURRENT_BINARY_DIR}/codegen_package_dummy")

    set(missing_requirements FALSE)

    #
    # Find libclang.
    #
    find_library(CLANG_LIBRARY NAMES clang libclang REQUIRED)
    if ("${CLANG_LIBRARY}" STREQUAL "CLANG_LIBRARY-NOTFOUND")
        message(SEND_ERROR "libclang not found")
        set(missing_requirements TRUE)
    endif()

    #
    # Find the codegen python package file
    #
    if ("${CODEGEN_PACKAGE}" STREQUAL "")
        foreach (prefix ${CMAKE_PREFIX_PATH})
            set(codegen_package_candidate "${prefix}/share/codegen/codegen-0.1.0.tar.gz")
            if (EXISTS "${codegen_package_candidate}")
                set(CODEGEN_PACKAGE "${codegen_package_candidate}")
                break()
            endif()
        endforeach()
        if ("${CODEGEN_PACKAGE}" STREQUAL "")
            set(CODEGEN_PACKAGE "CODEGEN_PACKAGE-NOTFOUND" CACHE FILEPATH)
        endif()
    endif()
    if ("${CODEGEN_PACKAGE}" STREQUAL "CODEGEN_PACKAGE-NOTFOUND")
        message(SEND_ERROR "codegen package not found")
        set(missing_requirements TRUE)
    endif()

    if (missing_requirements)
        message(FATAL_ERROR "Missing requirements")
    endif()

    #
    # Get name of python executable. We gotta add a '.exe' prefix if we're on windows, obviously.
    #
    if (WIN32)
        set(sep ";")
        set(python_executable_name "python.exe")
    else()
        set(sep ":")
        set(python_executable_name "python")
    endif()

    #
    # Determine the path of the virtual env python wrapper. It's different on Windows.
    #
    set(venv_python_executable_path "bin/${python_executable_name}")
    if (NOT EXISTS "${venv_python_executable_path}" AND WIN32)
        set(venv_python_executable_path "Scripts/${python_executable_name}")
    endif()

    #
    # Setup the virtual env for the codegen tool to use if it hasn't been set up.
    #
    if (NOT EXISTS "${venv_dummy}")
        message(STATUS "Creating virtual env at ${venv_path}")
        execute_process(
            COMMAND "${PYTHON_EXECUTABLE}" -m ensurepip
            RESULT_VARIABLE update_venv_result
            OUTPUT_VARIABLE update_venv_output
            ERROR_VARIABLE  update_venv_error
        )
        if (NOT update_venv_result EQUAL 0)
            # ensurepip module failed not installed. Check if pip is installed, and cause an error if it's not installed.
            execute_process(
                COMMAND "${PYTHON_EXECUTABLE}" -m pip --version
                RESULT_VARIABLE pip_version_result
            )
            if (NOT pip_version_result EQUAL 0)
                message(FATAL_ERROR "Failed to run ensurepip module, and pip is not installed. Please install pip manually.")
            endif()
        endif()

        execute_process(
            COMMAND "${PYTHON_EXECUTABLE}" -m pip install virtualenv
            RESULT_VARIABLE update_venv_result
            OUTPUT_VARIABLE update_venv_output
            ERROR_VARIABLE  update_venv_error
        )
        if (NOT update_venv_result EQUAL 0)
            message(FATAL_ERROR "Failed to install virtualenv with pip: result: ${update_venv_result}. stderr:\n${update_venv_error}")
        endif()

        execute_process(
            COMMAND "${PYTHON_EXECUTABLE}" -m virtualenv "${venv_path}"
            RESULT_VARIABLE update_venv_result
            OUTPUT_VARIABLE update_venv_output
            ERROR_VARIABLE  update_venv_error
        )
        if (NOT update_venv_result EQUAL 0)
            message(FATAL_ERROR "Cannot update codegen tool venv: result: ${update_venv_result}. stderr:\n${update_venv_error}")
        endif()

        #
        # Install the codegen package with pip
        #
        execute_process(
            COMMAND
                "${venv_path}/${venv_python_executable_path}" "-m" "pip"
                "install" "${CODEGEN_PACKAGE}"
            RESULT_VARIABLE pip_result
            ERROR_VARIABLE pip_error
        )
        if (NOT pip_result EQUAL 0)
            message(FATAL_ERROR "Failed to install codegen packages into codegen virtualenv. result: ${pip_result}. stderr:\n${pip_error}")
        endif()
        file(TOUCH "${package_dummy}")

        #
        # Create the dummy file to signify that we have successfully created the venv.
        #
        file(TOUCH "${venv_dummy}")
    endif()

    #
    # Add build-time target to update the codegen package if it's touched.
    #
    add_custom_command(
        OUTPUT
            "${package_dummy}"
        COMMAND
            "${venv_path}/${venv_python_executable_path}" "-m" "pip"
            "install" "${CODEGEN_PACKAGE}"
        COMMAND
            "${CMAKE_COMMAND}" "-E" "touch" "${package_dummy}"
        DEPENDS
            "${CODEGEN_PACKAGE}"
    )

    set(include_directories_arguments "")
    foreach(include_directory include_directories)
        list(APPEND include_directories_arguments "-I")
        list(APPEND include_directories_arguments "${include_directory}")
    endforeach()

    message(STATUS "Updating codegen targets")

    #
    # Set up targets for all files which will be generated by the codegen tool.
    #
    set(all_output_files "")
    foreach(current_source_file ${source_files})
        #
        # Determine which files are generated by this source file at configure time
        #
        execute_process(
            COMMAND
                "${venv_path}/${venv_python_executable_path}" "-m" "codegen"
                "get_output_files"
                "${current_source_file}"
                ${include_directories_arguments}
                "--libclangpath" "${CLANG_LIBRARY}"
                "--source-root" "${input_root}"
                "--output-root" "${output_root}"
            OUTPUT_VARIABLE current_output_files
            ERROR_VARIABLE tool_error
            RESULT_VARIABLE tool_result
        )
        if (NOT tool_result EQUAL 0)
            message(SEND_ERROR "Error running codegen tool. result: ${tool_result}. stderr:\n${tool_error}")
            continue()
        endif()

        #
        # Set up a build target for the outputs given to us by the above commands.
        #
        string(STRIP "${current_output_files}" current_output_files)
        list(LENGTH current_output_files current_output_files_len)
        if ("${current_output_files_len}" EQUAL 0)
            continue()
        endif()

        foreach(current_output_file ${current_output_files})
            list(APPEND all_output_files "${current_output_file}")
        endforeach()
        
        add_custom_command(
            OUTPUT "${current_output_files}"
            COMMAND
                "${venv_path}/${venv_python_executable_path}" "-m" "codegen"
                "generate"
                "${current_source_file}"
                ${include_directories_arguments}
                "--libclangpath" "${CLANG_LIBRARY}"
                "--source-root" "${input_root}"
                "--output-root" "${output_root}"
            DEPENDS "${current_source_file}" "${package_dummy}"
        )

    endforeach()

    #
    # "Return" a list of all files that will be generated during build time.
    #
    set("${generated_files_var}" "${all_output_files}" PARENT_SCOPE)

endfunction()
