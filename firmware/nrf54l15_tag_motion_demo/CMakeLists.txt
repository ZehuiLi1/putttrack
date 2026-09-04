# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# Reuse the physically proven Tag configuration, then apply only the demo image
# version override. This avoids a second drifting copy of the baseline config.
set(CONF_FILE
  "${CMAKE_CURRENT_LIST_DIR}/../nrf54l15_tag_app/prj.conf;${CMAKE_CURRENT_LIST_DIR}/motion_demo.conf"
)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf54l15_tag_motion_demo)

# Reuse the baseline source without editing it. At configure time make one build-
# local copy whose human-readable firmware version is bumped to 0.1.18 so OTA
# and captured provenance cannot be confused with the physically confirmed
# 0.1.17 image.
set(BASELINE_MAIN "${CMAKE_CURRENT_LIST_DIR}/../nrf54l15_tag_app/src/main.c")
file(READ "${BASELINE_MAIN}" BASELINE_MAIN_TEXT)
string(REPLACE
  "#define PUTTTRACK_FIRMWARE_VERSION \"0.1.17\""
  "#define PUTTTRACK_FIRMWARE_VERSION \"0.1.18\""
  DEMO_BASELINE_MAIN_TEXT
  "${BASELINE_MAIN_TEXT}"
)
if(DEMO_BASELINE_MAIN_TEXT STREQUAL BASELINE_MAIN_TEXT)
  message(FATAL_ERROR "baseline firmware version patch point changed; review motion demo integration")
endif()
set(DEMO_BASELINE_MAIN "${CMAKE_CURRENT_BINARY_DIR}/putttrack_tag_app_motion_demo.c")
file(WRITE "${DEMO_BASELINE_MAIN}" "${DEMO_BASELINE_MAIN_TEXT}")

target_sources(app PRIVATE
  src/main.c
  src/motion_engine.c
)

target_include_directories(app PRIVATE src)
target_compile_definitions(app PRIVATE
  PT_BASELINE_MAIN_SOURCE=\"${DEMO_BASELINE_MAIN}\"
)
