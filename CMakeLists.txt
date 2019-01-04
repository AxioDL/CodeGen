cmake_minimum_required(VERSION 3.12)
include(CMakePackageConfigHelpers)

project(codegen VERSION 0.1.0)

find_package(PythonInterp 3.6 REQUIRED)

add_library(codegen INTERFACE)
target_compile_definitions(
    codegen
    INTERFACE
        WITH_CODEGEN
)

add_custom_target(
    codegen_sdist
    ALL
    COMMAND
        "${PYTHON_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/setup.py" "sdist" "-d" "${PROJECT_BINARY_DIR}/dist"
    WORKING_DIRECTORY
        "${PROJECT_SOURCE_DIR}"
)
add_dependencies(codegen codegen_sdist)

# Install the CMake Module
install(
    DIRECTORY "${PROJECT_SOURCE_DIR}/cmake"
    DESTINATION "share"
)

# Install the python package
install(
    FILES "${PROJECT_BINARY_DIR}/dist/codegen-${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}.${PROJECT_VERSION_PATCH}.tar.gz"
    DESTINATION "share/codegen/"
)

# Install the project headers
install(
    DIRECTORY "${PROJECT_SOURCE_DIR}/include/codegen"
    DESTINATION "include/codegen"
)


set(version_config_file "${PROJECT_BINARY_DIR}/codegenConfigVersion.cmake")
set(config_file "${PROJECT_BINARY_DIR}/codegenConfig.cmake")
set(config_install_dir "lib/cmake/codegen")


# Associate target with export
install(
    TARGETS codegen
    EXPORT codegenTargets
    INCLUDES DESTINATION "include/codegen"
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
