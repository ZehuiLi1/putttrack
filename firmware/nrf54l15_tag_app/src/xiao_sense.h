/* SPDX-License-Identifier: Apache-2.0 */
#pragma once
#include <zephyr/drivers/sensor.h>
int pt_xiao_init(void);
int pt_xiao_active(void);
int pt_xiao_idle(void);
int pt_xiao_sample(struct sensor_value accel[3], struct sensor_value gyro[3]);
int pt_xiao_wake_enable(void (*notify)(void));
int pt_xiao_wake_disable(void);
bool pt_xiao_ready(void);
