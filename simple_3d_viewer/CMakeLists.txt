# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

add_executable(simple_3d_viewer main.cpp)

find_package(OpenCV 4 REQUIRED)

target_include_directories(simple_3d_viewer PRIVATE
    ../sample_helper_includes
    ${OpenCV_INCLUDE_DIRS}
)

# Dependencies of this library
target_link_libraries(simple_3d_viewer PRIVATE 
    k4a
    k4abt
    k4arecord
    window_controller_3d::window_controller_3d
    glfw::glfw
    ${OpenCV_LIBS}
    )

