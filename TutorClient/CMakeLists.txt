set(TUTOR_CLIENT_SOURCES
    ../common/appconfig.cpp
    ../common/applogger.cpp
    login.cpp
    main.cpp
    mainwindow.cpp
    record.cpp
    serverstuff.cpp
    login.h
    mainwindow.h
    record.h
    serverstuff.h
    login.ui
    mainwindow.ui
    record.ui
)

add_executable(TutorClient WIN32 ${TUTOR_CLIENT_SOURCES})

target_include_directories(TutorClient PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../common
)

target_link_libraries(TutorClient PRIVATE
    Qt${QT_VERSION_MAJOR}::Core
    Qt${QT_VERSION_MAJOR}::Gui
    Qt${QT_VERSION_MAJOR}::Network
    Qt${QT_VERSION_MAJOR}::Widgets
)

if(WIN32)
    target_link_libraries(TutorClient PRIVATE user32)
endif()
