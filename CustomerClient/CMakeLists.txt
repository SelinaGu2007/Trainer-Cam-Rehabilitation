set(CUSTOMER_CLIENT_SOURCES
    ../common/appconfig.cpp
    ../common/applogger.cpp
    ClientStuff.cpp
    analyse.cpp
    login.cpp
    main.cpp
    mainwindow.cpp
    recordconfiguation.cpp
    ClientStuff.h
    analyse.h
    login.h
    mainwindow.h
    recordconfiguation.h
    analyse.ui
    login.ui
    mainwindow.ui
    recordconfiguation.ui
    resources.qrc
)

add_executable(CustomerClient WIN32 ${CUSTOMER_CLIENT_SOURCES})

target_include_directories(CustomerClient PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../common
)

target_link_libraries(CustomerClient PRIVATE
    Qt${QT_VERSION_MAJOR}::Core
    Qt${QT_VERSION_MAJOR}::Gui
    Qt${QT_VERSION_MAJOR}::Network
    Qt${QT_VERSION_MAJOR}::Widgets
)

if(WIN32)
    target_link_libraries(CustomerClient PRIVATE user32)
endif()
