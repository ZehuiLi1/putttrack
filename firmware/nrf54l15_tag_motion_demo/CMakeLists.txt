# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

# Reuse the proven Tag application's Kconfig selection. The demo is additive and
# does not fork the raw telemetry/power/NFC configuration.
set(CONF_FILE ${CMAKE_CURRENT_LIST_DIR}/../nrf54l15_tag_app/prj.conf)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf54l15_tag_motion_demo)

target_sources(app PRIVATE
  src/main.c
  src/motion_engine.c
)

target_include_directories(app PRIVATE src)
