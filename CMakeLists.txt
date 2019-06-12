cmake_minimum_required(VERSION 3.12)
include(CMakePackageConfigHelpers)
if (POLICY CMP0077)
    cmake_policy(SET CMP0077 NEW)
endif()

project(codegen VERSION 0.1.0)

find_package(Python3 COMPONENTS Interpreter REQUIRED)

add_library(codegen INTERFACE)
target_compile_definitions(
    codegen
    INTERFACE
        WITH_CODEGEN
)
target_include_directories(
    codegen
    INTERFACE
        # Add source include files to target's interface include directories for projects using add_subdirectory()
        $<BUILD_INTERFACE:${codegen_SOURCE_DIR}/include>
)

set(setup_command_args "")
list(APPEND setup_command_args
    "${Python3_EXECUTABLE}" "${codegen_SOURCE_DIR}/setup.py" "sdist" "-d" "${codegen_BINARY_DIR}/dist"
)
set(package_file_name "codegen-${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}.${PROJECT_VERSION_PATCH}.tar.gz")
set(package_file "${codegen_BINARY_DIR}/dist/${package_file_name}")

add_custom_target(
    codegen_sdist
    ALL
    COMMAND
        ${setup_command_args}
    WORKING_DIRECTORY
        "${codegen_SOURCE_DIR}"
)
add_dependencies(codegen codegen_sdist)

#
# If we're told to, make install targets
#
option(CODEGEN_GENERATE_INSTALL_TARGETS "Make codegen install targets" ON)

if (CODEGEN_GENERATE_INSTALL_TARGETS)

    # Install the CMake Module
    install(
        DIRECTORY "${codegen_SOURCE_DIR}/cmake"
        DESTINATION "share"
    )

    # Install the python package
    install(
        FILES "${package_file}"
        DESTINATION "share/codegen/"
    )

    # Install the project headers
    install(
        DIRECTORY "${codegen_SOURCE_DIR}/include/codegen"
        DESTINATION include
    )


    set(version_config_file "${codegen_BINARY_DIR}/codegenConfigVersion.cmake")
    set(config_file "${codegen_BINARY_DIR}/codegenConfig.cmake")
    set(config_install_dir "lib/cmake/codegen")


    # Associate target with export
    install(
        TARGETS codegen
        EXPORT codegenTargets
        INCLUDES DESTINATION include  # Added to INTERFACE_INCLUDE_DIRECTORIES
    )

    # Install the target config files
    install(
        EXPORT codegenTargets
        NAMESPACE "codegen::"
        DESTINATION "${config_install_dir}"
    )

    # Generate version config file
    write_basic_package_version_file(
        "${version_config_file}"
        COMPATIBILITY SameMajorVersion
    )

    # Generate config file
    configure_package_config_file(
        "Config.cmake.in"
        "${config_file}"
        INSTALL_DESTINATION "lib/cmake/codegen"
    )

    # Install the config files
    install(
        FILES "${config_file}" "${version_config_file}"
        DESTINATION ${config_install_dir}
    )

endif()

#
# If we're told to, build the python package at configure time
#
if (CODEGEN_BUILD_PACKAGE_DURING_CONFIGURE)
    message(STATUS "Building CodeGen Package")
    execute_process(
        COMMAND
            ${setup_command_args}
        WORKING_DIRECTORY
            "${codegen_SOURCE_DIR}"
        RESULT_VARIABLE setup_result
    )
    if (NOT setup_result EQUAL 0)
        message(FATAL_ERROR "Failed to setup CodeGen package during configure time")
    endif()

    # Copy the built package to a place we can easily find it from parent projects
    file(COPY "${package_file}" DESTINATION "${codegen_BINARY_DIR}")
    file(RENAME "${codegen_BINARY_DIR}/${package_file_name}" "${codegen_BINARY_DIR}/codegen.tar.gz")
    set(CODEGEN_PACKAGE "${codegen_BINARY_DIR}/codegen.tar.gz" CACHE FILEPATH "")
endif()

# Include module functions for the parent project as well
include(cmake/Modules/codegen.cmake)
