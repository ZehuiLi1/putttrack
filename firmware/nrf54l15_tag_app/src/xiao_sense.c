/* SPDX-License-Identifier: Apache-2.0
 * LSM6DS3TR-C board backend. Register values follow the ST LSM6DS3TR-C datasheet.
 * No Zephyr LSM6DSL driver instance owns this sensor: all accesses are serialized.
 */
#include "xiao_sense.h"
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/regulator.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/kernel.h>
#include <math.h>

static const struct i2c_dt_spec imu = I2C_DT_SPEC_GET(DT_ALIAS(imu0));
static const struct gpio_dt_spec irq = GPIO_DT_SPEC_GET(DT_ALIAS(imu0), irq_gpios);
static const struct device *const power = DEVICE_DT_GET(DT_NODELABEL(pdm_imu_pwr));
static struct gpio_callback irq_cb;
static bool initialized, callback_added, powered, idle;
static void (*wake_notify)(void);
K_MUTEX_DEFINE(imu_lock);
static int write_checked(uint8_t reg, uint8_t value)
{
	uint8_t readback;
	int rc = i2c_reg_write_byte_dt(&imu, reg, value);
	if (!rc) {
		rc = i2c_reg_read_byte_dt(&imu, reg, &readback);
	}
	return rc ? rc : readback == value ? 0 : -EIO;
}
static void wake_work_fn(struct k_work *work)
{
	ARG_UNUSED(work);
	uint8_t source = 0;
	void (*notify)(void) = NULL;
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = i2c_reg_read_byte_dt(&imu, 0x1b, &source);
	if (!rc && (source & BIT(3))) {
		notify = wake_notify;
	}
	k_mutex_unlock(&imu_lock);
	if (notify) {
		notify();
	}
}
K_WORK_DEFINE(wake_work, wake_work_fn);
static void wake_irq(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	ARG_UNUSED(pins);
	k_work_submit(&wake_work);
}
bool pt_xiao_ready(void)
{
	return initialized;
}
int pt_xiao_wake_disable(void)
{
	k_mutex_lock(&imu_lock, K_FOREVER);
	wake_notify = NULL;
	int rc = gpio_pin_interrupt_configure_dt(&irq, GPIO_INT_DISABLE);
	if (!rc && powered) {
		rc = write_checked(0x5e, 0);
	}
	k_mutex_unlock(&imu_lock);
	return rc;
}
int pt_xiao_active(void)
{
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = write_checked(0x5e, 0); /* INT1 route off */
	if (!rc) {
		rc = write_checked(0x58, 0); /* motion interrupts off */
	}
	if (!rc) {
		rc = write_checked(0x10, 0x44); /* accel 104 Hz, +/-16g */
	}
	if (!rc) {
		rc = write_checked(0x11, 0x4c); /* gyro 104 Hz, +/-2000dps */
	}
	if (!rc) {
		rc = write_checked(0x15, 0); /* accel high performance */
	}
	if (!rc) {
		rc = write_checked(0x16, 0); /* gyro high performance */
	}
	if (!rc) {
		idle = false;
	}
	k_mutex_unlock(&imu_lock);
	if (!rc) {
		k_msleep(80); /* gyro restart and fresh sample settling */
	}
	return rc;
}
int pt_xiao_idle(void)
{
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = write_checked(0x11, 0); /* gyro power down */
	if (!rc) {
		rc = write_checked(0x10, 0x20); /* accel 26 Hz, +/-2g */
	}
	if (!rc) {
		rc = write_checked(0x15, 0x10); /* accel low power */
	}
	if (!rc) {
		idle = true;
	}
	k_mutex_unlock(&imu_lock);
	return rc;
}
int pt_xiao_wake_enable(void (*notify)(void))
{
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = write_checked(0x58, 0x81); /* basic interrupts, latched, slope filter */
	if (!rc) {
		rc = write_checked(0x5b, 2); /* 2*(2g/64) = 62.5mg threshold */
	}
	if (!rc) {
		rc = write_checked(0x5c, 0x20); /* one ODR duration */
	}
	k_mutex_unlock(&imu_lock);
	if (rc) {
		return rc;
	}
	k_msleep(160);
	k_mutex_lock(&imu_lock, K_FOREVER);
	uint8_t source;
	rc = i2c_reg_read_byte_dt(&imu, 0x1b, &source); /* clear latched wake */
	if (!rc) {
		rc = gpio_pin_interrupt_configure_dt(&irq, GPIO_INT_EDGE_TO_ACTIVE);
	}
	if (!rc) {
		wake_notify = notify;
		rc = write_checked(0x5e, 0x20);
	}
	if (rc) {
		wake_notify = NULL;
	}
	k_mutex_unlock(&imu_lock);
	if (!rc && gpio_pin_get_dt(&irq) > 0) {
		k_work_submit(&wake_work);
	}
	return rc;
}
int pt_xiao_init(void)
{
	initialized = false;
	if (!device_is_ready(power) || !i2c_is_ready_dt(&imu) || !gpio_is_ready_dt(&irq)) {
		return -ENODEV;
	}
	(void)pt_xiao_wake_disable();
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = 0;
	if (powered) {
		rc = regulator_disable(power);
		if (!rc) {
			powered = false;
		}
	}
	if (!rc) {
		k_msleep(100);
		rc = regulator_enable(power);
		if (!rc) {
			powered = true;
		}
	}
	k_msleep(100);
	uint8_t id = 0;
	if (!rc) {
		rc = i2c_reg_read_byte_dt(&imu, 0x0f, &id);
	}
	if (!rc && id != 0x6a) {
		rc = -ENODEV;
	}
	if (!rc) {
		rc = i2c_reg_write_byte_dt(&imu, 0x12, 1); /* software reset */
	}
	if (!rc) {
		for (int n = 0; n < 20; n++) {
			k_msleep(5);
			rc = i2c_reg_read_byte_dt(&imu, 0x12, &id);
			if (rc || !(id & 1)) {
				break;
			}
		}
		if (!rc && (id & 1)) {
			rc = -ETIMEDOUT;
		}
	}
	if (!rc) {
		rc = write_checked(0x12, 0x44); /* BDU + auto increment */
	}
	if (!rc) {
		rc = gpio_pin_configure_dt(&irq, GPIO_INPUT);
	}
	if (!rc && !callback_added) {
		gpio_init_callback(&irq_cb, wake_irq, BIT(irq.pin));
		rc = gpio_add_callback(irq.port, &irq_cb);
		if (!rc) {
			callback_added = true;
		}
	}
	k_mutex_unlock(&imu_lock);
	if (!rc) {
		rc = pt_xiao_active();
	}
	initialized = rc == 0;
	return rc;
}
static void value_from_micro(int64_t micro, struct sensor_value *value)
{
	value->val1 = micro / 1000000;
	value->val2 = micro % 1000000;
}
int pt_xiao_sample(struct sensor_value accel[3], struct sensor_value gyro[3])
{
	if (!initialized) {
		return -ENODEV;
	}
	uint8_t data[12];
	k_mutex_lock(&imu_lock, K_FOREVER);
	int rc = i2c_burst_read_dt(&imu, 0x22, data, sizeof(data));
	if (!rc) {
		for (int i = 0; i < 3; i++) {
			int16_t g = (int16_t)sys_get_le16(data + i * 2),
				a = (int16_t)sys_get_le16(data + 6 + i * 2);
			/* 0.488mg/LSB (16g), 0.061mg/LSB (2g), 70mdps/LSB (2000dps). */
			value_from_micro(llround((double)a * (idle ? 598.20565 : 4785.6452)),
					 &accel[i]);
			value_from_micro(idle ? 0 : llround((double)g * 1221.730476396), &gyro[i]);
		}
	}
	k_mutex_unlock(&imu_lock);
	return rc;
}
