# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(putttrack_tag)

target_sources(app PRIVATE src/main.c)
target_sources_ifdef(CONFIG_PUTTTRACK_MOTION_DEMO_V0 app PRIVATE src/motion_demo_v0.c)

target_sources_ifdef(CONFIG_PUTTTRACK_STROKE_PICKUP_V1 app PRIVATE src/stroke_pickup_v1.c)
