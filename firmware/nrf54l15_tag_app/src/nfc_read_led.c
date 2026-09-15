#include <errno.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include "nfc_read_led.h"

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
static struct k_work pulse_work;
static struct k_work_delayable off_work;
static atomic_t ready;
static atomic_t pending;
static atomic_t error;
static atomic_t pulses;
static int64_t last_pulse = -1000;

static void turn_off(struct k_work *work)
{
	ARG_UNUSED(work);
	atomic_set(&error, gpio_pin_set_dt(&led, 0));
	atomic_clear(&pending);
}

static void pulse(struct k_work *work)
{
	ARG_UNUSED(work);
	const int64_t now = k_uptime_get();
	if (!atomic_get(&ready) || now - last_pulse < 1000) {
		atomic_clear(&pending);
		return;
	}
	int rc = gpio_pin_set_dt(&led, 1);
	atomic_set(&error, rc);
	if (rc) {
		atomic_clear(&pending);
		return;
	}
	last_pulse = now;
	atomic_inc(&pulses);
	(void)k_work_reschedule(&off_work, K_MSEC(150));
}

void nfc_read_led_init(void)
{
	k_work_init(&pulse_work, pulse);
	k_work_init_delayable(&off_work, turn_off);
	int rc = gpio_is_ready_dt(&led) ? gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE) : -ENODEV;
	atomic_set(&error, rc);
	atomic_set(&ready, rc == 0);
}

void nfc_read_led_notify(void)
{
	/* NFCT callback only queues work: no delays or GPIO transactions in IRQ. */
	if (atomic_get(&ready) && atomic_cas(&pending, 0, 1)) {
		(void)k_work_submit(&pulse_work);
	}
}

void nfc_read_led_stop(void)
{
	/* Called from the same system workqueue before System OFF. */
	atomic_clear(&ready);
	(void)k_work_cancel(&pulse_work);
	(void)k_work_cancel_delayable(&off_work);
	if (gpio_is_ready_dt(&led)) {
		atomic_set(&error, gpio_pin_set_dt(&led, 0));
	}
	atomic_clear(&pending);
}

int nfc_read_led_error(void) { return atomic_get(&error); }
unsigned int nfc_read_led_pulses(void) { return (unsigned int)atomic_get(&pulses); }
