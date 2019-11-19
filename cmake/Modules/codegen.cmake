cmake_minimum_required(VERSION 3.12)

function(add_codegen_targets
    source_files
    generated_files_var
    input_root
    output_root
    include_directories
)
    set(cache_path "${CMAKE_CURRENT_BINARY_DIR}/codegen_cache")

    #
    # Find our python interpreter, and set up some python related variables.
    #
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
    set(venv_path "${CMAKE_CURRENT_BINARY_DIR}/codegen_venv")
    set(venv_dummy "${CMAKE_CURRENT_BINARY_DIR}/codegen_venv_dummy")
    set(package_dummy "${CMAKE_CURRENT_BINARY_DIR}/codegen_package_dummy")

    set(missing_requirements FALSE)

    #
    # Find libclang.
    #
    if (WIN32)
        set(CMAKE_FIND_LIBRARY_SUFFIXES .dll)
        find_library(CLANG_LIBRARY NAMES clang libclang PATHS "$ENV{ProgramW6432}/LLVM/bin"
                     NO_SYSTEM_ENVIRONMENT_PATH REQUIRED)
    elseif (APPLE)
        execute_process(COMMAND xcrun -find clang
                        OUTPUT_VARIABLE CLANG_BIN_PATH OUTPUT_STRIP_TRAILING_WHITESPACE)
        get_filename_component(CLANG_BIN_DIR "${CLANG_BIN_PATH}" DIRECTORY)
        find_library(CLANG_LIBRARY NAMES clang libclang HINTS "${CLANG_BIN_DIR}/../lib" REQUIRED)
    else()
        find_library(CLANG_LIBRARY NAMES clang libclang PATHS /usr/lib/llvm-6.0/lib REQUIRED)
    endif()
    if (NOT CLANG_LIBRARY)
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
            set(CODEGEN_PACKAGE "CODEGEN_PACKAGE-NOTFOUND" CACHE FILEPATH "")
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

    #
    # TODO: Instead of just skipping over venv creation if a directory exists, we should ensure the venv is valid and
    # the codegen package is up to date.
    #

    if (NOT EXISTS "${venv_dummy}")
        message(STATUS "Creating virtual env at ${venv_path}")
        execute_process(
            COMMAND "${Python3_EXECUTABLE}" -m ensurepip
            RESULT_VARIABLE update_venv_result
        )
        if (NOT update_venv_result EQUAL 0)
            # ensurepip module failed not installed. Check if pip is installed, and cause an error if it's not installed.
            execute_process(
                COMMAND "${Python3_EXECUTABLE}" -m pip --version
                RESULT_VARIABLE pip_version_result
            )
            if (NOT pip_version_result EQUAL 0)
                message(FATAL_ERROR "Failed to run ensurepip module, and pip is not installed. Please install pip manually.")
            endif()
        endif()

        execute_process(
            COMMAND "${Python3_EXECUTABLE}" -m pip install --user virtualenv
            RESULT_VARIABLE update_venv_result
        )
        if (NOT update_venv_result EQUAL 0)
            message(FATAL_ERROR "Failed to install virtualenv with pip: result: ${update_venv_result}.")
        endif()

        execute_process(
            COMMAND "${Python3_EXECUTABLE}" -m virtualenv "${venv_path}"
            RESULT_VARIABLE update_venv_result
        )
        if (NOT update_venv_result EQUAL 0)
            message(FATAL_ERROR "Cannot update codegen tool venv: result: ${update_venv_result}.")
        endif()

        #
        # Install the codegen package with pip
        #
        execute_process(
            COMMAND
                "${venv_path}/${venv_python_executable_path}" -m pip
                install "${CODEGEN_PACKAGE}"
            RESULT_VARIABLE pip_result
        )
        if (NOT pip_result EQUAL 0)
            message(FATAL_ERROR "Failed to install codegen packages into codegen virtualenv. result: ${pip_result}.")
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
            "${venv_path}/${venv_python_executable_path}" -m pip
            install "${CODEGEN_PACKAGE}"
        COMMAND
            "${CMAKE_COMMAND}" "-E" "touch" "${package_dummy}"
        DEPENDS
            "${CODEGEN_PACKAGE}"
    )

    set(include_directories_arguments "")
    foreach(include_directory ${include_directories})
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
        file(RELATIVE_PATH source_file_relative "${input_root}" "${current_source_file}")
        set(cached_source_outputs_filename "${cache_path}/${source_file_relative}.outputs")
        set(cached_outputs_are_ok false)

        if (EXISTS "${cached_source_outputs_filename}")
            # Get the timestamp of the cache file and the source file
            file(TIMESTAMP "${cached_source_outputs_filename}" cached_outputs_timestamp "%s")
            file(TIMESTAMP "${current_source_file}" source_file_timestamp "%s")
            if (cached_outputs_timestamp GREATER source_file_timestamp)
                # Cache hit
                file(READ "${cached_source_outputs_filename}" current_output_files)
                set(cached_outputs_are_ok true)
            endif()
        endif()

        if (NOT "${cached_outputs_are_ok}")
            execute_process(
                COMMAND
                    "${venv_path}/${venv_python_executable_path}" "-m" "codegen"
                    "get_output_files"
                    "${current_source_file}"
                    ${include_directories_arguments}
                    "--libclangpath" "${CLANG_LIBRARY}"
                    "--source-root" "${input_root}"
                    "--output-root" "${output_root}"
                    "--cache-path" "${cache_path}"
                OUTPUT_VARIABLE current_output_files
                RESULT_VARIABLE tool_result
            )
            if (NOT tool_result EQUAL 0)
                message(SEND_ERROR "Error running codegen tool. result: ${tool_result}.")
                continue()
            endif()
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

#
# gather_include_directories recursively builds a list of include directories
# across all dependencies.
#

function(_gather_include_directories_impl target_name)
    get_target_property(target_dependencies ${target_name} INTERFACE_LINK_LIBRARIES)
    foreach(dep ${target_dependencies})
        if(TARGET ${dep})
            get_target_property(dep_includes ${dep} INTERFACE_INCLUDE_DIRECTORIES)
            list(APPEND target_includes ${dep_includes})
            _gather_include_directories_impl(${dep})
        endif()
    endforeach()
    set(target_includes ${target_includes} PARENT_SCOPE)
endfunction()

function(gather_include_directories var target_name)
    get_target_property(target_includes ${target_name} INTERFACE_INCLUDE_DIRECTORIES)
    _gather_include_directories_impl(${target_name})
    list(REMOVE_DUPLICATES target_includes)
    set(${var} ${target_includes} PARENT_SCOPE)
endfunction()
