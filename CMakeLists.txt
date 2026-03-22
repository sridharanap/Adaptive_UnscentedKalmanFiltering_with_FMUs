cmake_minimum_required(VERSION 3.17)

set(MODEL_NAMES
        BatteryModel
        )

project(CppFmuSdk)

set(FMI_VERSION 2 CACHE STRING "FMI Version")
set_property(CACHE FMI_VERSION PROPERTY STRINGS 2 3)

if (MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)

    # Minimum supported MSVC version is 1800 = Visual Studio 12.0/2013
    # See also https://cmake.org/cmake/help/latest/variable/MSVC_VERSION.html
    if (MSVC_VERSION VERSION_LESS 1800)
        message(SEND_ERROR "MSVC_VERSION ${MSVC_VERSION} is not a supported Visual Studio compiler version. Please use Visual Studio 2013 or any later version.")
    endif ()
endif ()

# hide internal functions
if (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fvisibility=hidden")
endif ()

if (${FMI_VERSION} GREATER 2)
    if (WIN32)
        set(FMI_PLATFORM windows)
    elseif (APPLE)
        set(FMI_PLATFORM darwin)
    else ()
        set(FMI_PLATFORM linux)
    endif ()

    if ("${CMAKE_SIZEOF_VOID_P}" STREQUAL "8")
        set(FMI_PLATFORM x86_64-${FMI_PLATFORM})
    else ()
        set(FMI_PLATFORM x86-${FMI_PLATFORM})
    endif ()
else ()
    if (WIN32)
        set(FMI_PLATFORM win)
    elseif (APPLE)
        set(FMI_PLATFORM darwin)
    else ()
        set(FMI_PLATFORM linux)
    endif ()

    if ("${CMAKE_SIZEOF_VOID_P}" STREQUAL "8")
        set(FMI_PLATFORM ${FMI_PLATFORM}64)
    else ()
        set(FMI_PLATFORM ${FMI_PLATFORM}32)
    endif ()
endif ()

MESSAGE("FMI_PLATFORM: " ${FMI_PLATFORM})

foreach (MODEL_NAME ${MODEL_NAMES})

    set(TARGET_NAME ${MODEL_NAME})

    SET(HEADERS
            ${MODEL_NAME}/config.h
            include/cosimulation.h
            include/model.h
            )

    if (${FMI_VERSION} EQUAL 2)
        SET(HEADERS
                ${HEADERS}
                include/fmi2Functions.h
                include/fmi2FunctionTypes.h
                include/fmi2TypesPlatform.h
                )
    elseif (${FMI_VERSION} EQUAL 3)
        SET(HEADERS
                ${HEADERS}
                include/fmi3Functions.h
                include/fmi3FunctionTypes.h
                include/fmi3PlatformTypes.h
                )
    endif ()

    SET(SOURCES
            ${MODEL_NAME}/model.c
            src/fmi${FMI_VERSION}Functions.c
            src/cosimulation.c
            )

    add_library(${TARGET_NAME} SHARED
            ${HEADERS}
            ${SOURCES}
            "${MODEL_NAME}/FMI${FMI_VERSION}${FMI_TYPE}.xml"
            )

    file(MAKE_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/fmus)

    target_compile_definitions(${TARGET_NAME} PRIVATE
            FMI_VERSION=${FMI_VERSION}
            DISABLE_PREFIX
            )

    if (MSVC)
        target_compile_options(${TARGET_NAME} PRIVATE /W4 /WX)
    else ()
        target_compile_options(${TARGET_NAME} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif ()

    if (CMAKE_C_COMPILER_ID STREQUAL "GNU")
        target_link_options(${TARGET_NAME} PRIVATE "-static-libgcc")
    endif ()

    if (CMAKE_C_COMPILER_ID STREQUAL "Intel")
        target_link_options(${TARGET_NAME} PRIVATE "-static-intel" "-static-libgcc")
    endif ()

    if (${FMI_VERSION} EQUAL 1 AND "${FMI_TYPE}" STREQUAL CS)
        target_compile_definitions(${TARGET_NAME} PRIVATE FMI_COSIMULATION)
    endif ()

    target_include_directories(${TARGET_NAME} PRIVATE
            include
            ${MODEL_NAME}
            )

    set(FMU_BUILD_DIR temp/${MODEL_NAME})

    set_target_properties(${TARGET_NAME} PROPERTIES
            RUNTIME_OUTPUT_DIRECTORY "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            RUNTIME_OUTPUT_DIRECTORY_DEBUG "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            RUNTIME_OUTPUT_DIRECTORY_RELEASE "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            LIBRARY_OUTPUT_DIRECTORY "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            LIBRARY_OUTPUT_DIRECTORY_DEBUG "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            LIBRARY_OUTPUT_DIRECTORY_RELEASE "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            ARCHIVE_OUTPUT_DIRECTORY "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            ARCHIVE_OUTPUT_DIRECTORY_DEBUG "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}"
            )

    set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "")
    set_target_properties(${TARGET_NAME} PROPERTIES OUTPUT_NAME ${MODEL_NAME})

    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/lib)

    # modelDescription.xml
    add_custom_command(TARGET ${TARGET_NAME} POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy
            "${CMAKE_CURRENT_SOURCE_DIR}/${MODEL_NAME}/FMI${FMI_VERSION}${FMI_TYPE}.xml"
            "${FMU_BUILD_DIR}/modelDescription.xml"
            )

    set(ARCHIVE_FILES "modelDescription.xml" "binaries")

    if (EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${MODEL_NAME}/resources")
        add_custom_command(TARGET ${TARGET_NAME} POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy_directory
                "${CMAKE_CURRENT_SOURCE_DIR}/${MODEL_NAME}/resources"
                "${FMU_BUILD_DIR}/resources/"
                )
        set(ARCHIVE_FILES ${ARCHIVE_FILES} "resources")
    endif ()

    # delete unintended files from binaries (Release configuration only)
    if (MSVC)
        add_custom_command(TARGET ${TARGET_NAME} POST_BUILD COMMAND if $<CONFIG:Release> neq 0 (
                ${CMAKE_COMMAND} -E rm -f
                "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}/${MODEL_NAME}.exp"
                "${FMU_BUILD_DIR}/binaries/${FMI_PLATFORM}/${MODEL_NAME}.lib"
                )
                )
    endif ()

    # create ZIP archive
    add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E tar "cfv" ${CMAKE_CURRENT_BINARY_DIR}/fmus/${MODEL_NAME}.fmu --format=zip
            ${ARCHIVE_FILES}
            WORKING_DIRECTORY ${FMU_BUILD_DIR} COMMENT "Creating ZIP archive"
            )

    install(FILES ${CMAKE_CURRENT_BINARY_DIR}/fmus/${MODEL_NAME}.fmu DESTINATION ${CMAKE_INSTALL_PREFIX})

endforeach (MODEL_NAME)
