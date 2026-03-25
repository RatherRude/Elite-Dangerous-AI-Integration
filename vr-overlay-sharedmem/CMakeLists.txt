cmake_minimum_required(VERSION 3.15)
project(CovasVROverlay)

set(CMAKE_CXX_STANDARD 17)

# OpenVR SDK path
set(OPENVR_SDK "${CMAKE_SOURCE_DIR}/openvr")

# Add executable
add_executable(CovasVROverlay
    src/main.cpp
)

# Include directories
target_include_directories(CovasVROverlay PRIVATE
    ${OPENVR_SDK}/headers
)

# Link libraries
target_link_libraries(CovasVROverlay PRIVATE
    ${OPENVR_SDK}/lib/win64/openvr_api.lib
    d3d11.lib
    dxgi.lib
)

# Copy OpenVR DLL to output
add_custom_command(TARGET CovasVROverlay POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${OPENVR_SDK}/bin/win64/openvr_api.dll"
    $<TARGET_FILE_DIR:CovasVROverlay>
)