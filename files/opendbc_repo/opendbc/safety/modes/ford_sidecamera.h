#pragma once

// Stationary development tests only. No 0x3EE display-state injection.
// Gear and foot-brake eligibility are checked in the controller. Firmware independently checks fresh
// validated standstill/speed reports and inactive driving controls.
#define FORD_CAM_VIEW 0x3E2U
#define FORD_CAM_BUTTON 0x192U
#define FORD_CAM_TRAILER 0x443U
#define FORD_CAM_LENGTH 0x227U

static bool ford_cam_length_started = false;
static bool ford_cam_length_active = false;
static uint32_t ford_cam_length_start_ts = 0U;
static uint32_t ford_cam_length_last_ts = 0U;
static unsigned int ford_cam_length_frames = 0U;

static bool ford_cam_stop_seen = false;
static bool ford_cam_speed_seen = false;
static bool ford_cam_stalk_seen = false;
static bool ford_cam_stopped = false;
static bool ford_cam_zero_speed = false;
static uint8_t ford_cam_stalk = 0U;
static uint32_t ford_cam_stop_ts = 0U;
static uint32_t ford_cam_speed_ts = 0U;
static uint32_t ford_cam_stalk_ts = 0U;
static unsigned int ford_cam_requests = 0U;
static bool ford_cam_request_seen = false;
static uint32_t ford_cam_request_ts = 0U;
static unsigned int ford_cam_button_presses = 0U;
static bool ford_cam_button_active = false;
static uint32_t ford_cam_button_ts = 0U;
static bool ford_cam_trailer_started = false;
static bool ford_cam_trailer_active = false;
static uint32_t ford_cam_trailer_start_ts = 0U;
static uint32_t ford_cam_trailer_last_ts = 0U;
static unsigned int ford_cam_trailer_frames = 0U;
static bool ford_cam_auto_payload = false;

static void ford_cam_reset(void) {
  ford_cam_length_started = false;
  ford_cam_length_active = false;
  ford_cam_length_start_ts = 0U;
  ford_cam_length_last_ts = 0U;
  ford_cam_length_frames = 0U;
  ford_cam_auto_payload = false;
  ford_cam_stop_seen = false;
  ford_cam_speed_seen = false;
  ford_cam_stalk_seen = false;
  ford_cam_stopped = false;
  ford_cam_zero_speed = false;
  ford_cam_stalk = 0U;
  ford_cam_stop_ts = 0U;
  ford_cam_speed_ts = 0U;
  ford_cam_stalk_ts = 0U;
  ford_cam_requests = 0U;
  ford_cam_request_seen = false;
  ford_cam_request_ts = 0U;
  ford_cam_button_presses = 0U;
  ford_cam_button_active = false;
  ford_cam_button_ts = 0U;
  ford_cam_trailer_started = false;
  ford_cam_trailer_active = false;
  ford_cam_trailer_start_ts = 0U;
  ford_cam_trailer_last_ts = 0U;
  ford_cam_trailer_frames = 0U;
}

// Called from the existing Ford RX hook, after the original integrity checks.
static void ford_cam_rx(const CANPacket_t *msg) {
  if ((msg->bus == FORD_MAIN_BUS) && (GET_LEN(msg) == 8U)) {
    const uint32_t now = microsecond_timer_get();
    if (msg->addr == FORD_DesiredTorqBrk) {
      ford_cam_stop_seen = true;
      ford_cam_stop_ts = now;
      ford_cam_stopped = ((msg->data[3] >> 3) & 3U) == 1U;
      if (!ford_cam_stopped) {
        ford_cam_trailer_active = false;
      }
    }
    if (msg->addr == FORD_BrakeSysFeatures) {
      ford_cam_speed_seen = true;
      ford_cam_speed_ts = now;
      ford_cam_zero_speed = (msg->data[0] == 0U) && (msg->data[1] == 0U);
      if (!ford_cam_zero_speed) {
        ford_cam_trailer_active = false;
      }
    }
    if (msg->addr == FORD_Steering_Data_FD1) {
      ford_cam_stalk_seen = true;
      ford_cam_stalk_ts = now;
      ford_cam_stalk = (msg->data[0] >> 4) & 3U;
      if (ford_cam_length_active && ((uint32_t)(now - ford_cam_length_last_ts) >= 1200000U)) {
        ford_cam_length_active = false;
      }
      // Expired leases must release the internal active flag as well as
      // forwarding; a lost cleanup must not permanently consume the burst.
      if (ford_cam_trailer_active && ((uint32_t)(now - ford_cam_trailer_last_ts) >= 1200000U)) {
        ford_cam_trailer_active = false;
      }
      if ((ford_cam_stalk == 0U) && !ford_cam_length_active &&
          ((uint32_t)(now - ford_cam_length_last_ts) >= 2000000U)) {
        ford_cam_length_started = false;
        ford_cam_length_frames = 0U;
      }
      // A new automatic burst requires a genuine neutral stalk after cleanup,
      // and at least two seconds since the last connected frame.
      if (ford_cam_auto_payload && (ford_cam_stalk == 0U) && !ford_cam_trailer_active &&
          ((uint32_t)(now - ford_cam_trailer_last_ts) >= 2000000U)) {
        ford_cam_trailer_started = false;
        ford_cam_trailer_frames = 0U;
        ford_cam_auto_payload = false;
      }
    }
  }
}

static bool ford_cam_stationary(void) {
  const uint32_t now = microsecond_timer_get();
  return ford_cam_stop_seen && ford_cam_speed_seen && ford_cam_stalk_seen &&
    ((uint32_t)(now - ford_cam_stop_ts) < 200000U) &&
    ((uint32_t)(now - ford_cam_speed_ts) < 200000U) &&
    ((uint32_t)(now - ford_cam_stalk_ts) < 300000U) &&
    ford_cam_stopped && ford_cam_zero_speed && !vehicle_moving &&
    !controls_allowed && !controls_allowed_lateral && !safety_rx_checks_invalid &&
    (ford_cam_stalk != 3U);
}

static bool ford_cam_tx(const CANPacket_t *msg) {
  const uint32_t now = microsecond_timer_get();
  bool allowed = false;
  if (ford_cam_stationary() && (GET_LEN(msg) == 8U)) {
    if ((msg->addr == FORD_CAM_LENGTH) && (msg->bus == FORD_CAM_BUS)) {
      // Python requires a fresh exact genuine baseline. No new mandatory RX
      // check is added to the vehicle's stock safety configuration.
      const uint8_t baseline[8] = {0U, 0U, 0xFCU, 0U, 0x80U, 0U, 0xFCU, 0x40U};
      bool matching = true;
      for (unsigned int i = 0U; i < 8U; i++) {
        if (i == 6U) {
          matching = matching && ((msg->data[i] & 1U) == 0U);
        } else {
          matching = matching && (msg->data[i] == baseline[i]);
        }
      }
      const uint8_t length = msg->data[6] >> 1;
      if (matching && (length == 9U)) {
        const bool signal = (ford_cam_stalk == 1U) || (ford_cam_stalk == 2U);
        const bool window = !ford_cam_length_started ||
          ((uint32_t)(now - ford_cam_length_start_ts) < 10000000U);
        const bool rate = !ford_cam_length_started ||
          ((uint32_t)(now - ford_cam_length_last_ts) >= 900000U);
        allowed = signal && window && rate && (ford_cam_length_frames < 10U);
        if (allowed) {
          if (!ford_cam_length_started) { ford_cam_length_start_ts = now; }
          ford_cam_length_started = true;
          ford_cam_length_active = true;
          ford_cam_length_last_ts = now;
          ford_cam_length_frames++;
        }
      } else if (matching && (length == 126U)) {
        allowed = ford_cam_length_active;
        if (allowed) { ford_cam_length_active = false; }
      }
    }
    if ((msg->addr == FORD_CAM_VIEW) && (msg->bus == FORD_MAIN_BUS)) {
      const uint8_t value = msg->data[1];
      const bool known_view = (value == 0x2FU) || (value == 0x30U) ||
        (value == 0x07U) || (value == 0x2CU) || (value == 0x0BU) || (value == 0x26U);
      const bool exact = (msg->data[0] == 0U) && known_view &&
        (msg->data[2] == 8U) && (msg->data[3] == 0x1BU) &&
        (msg->data[4] == 0x81U) && (msg->data[5] == 0x50U) &&
        (msg->data[6] == 0U) && (msg->data[7] == 0U);
      const bool rate_ok = !ford_cam_request_seen || ((uint32_t)(now - ford_cam_request_ts) >= 250000U);
      allowed = exact && rate_ok && (ford_cam_requests < 8U);
      if (allowed) {
        ford_cam_request_seen = true;
        ford_cam_request_ts = now;
        ford_cam_requests++;
      }
    }
    if ((msg->addr == FORD_CAM_BUTTON) && (msg->bus == FORD_MAIN_BUS)) {
      const bool exact = (msg->data[0] == 0U) && (msg->data[1] <= 1U) &&
        (msg->data[2] == 0U) && (msg->data[3] == 0U) && (msg->data[4] == 0U) &&
        (msg->data[5] == 0U) && (msg->data[6] == 0U) && (msg->data[7] == 0U);
      if (exact && (msg->data[1] == 1U)) {
        allowed = !ford_cam_button_active && (ford_cam_button_presses < 2U) &&
          ((ford_cam_button_presses == 0U) || ((uint32_t)(now - ford_cam_button_ts) >= 2000000U));
        if (allowed) {
          ford_cam_button_active = true;
          ford_cam_button_ts = now;
          ford_cam_button_presses++;
        }
      } else if (exact && (msg->data[1] == 0U)) {
        allowed = ford_cam_button_active && ((uint32_t)(now - ford_cam_button_ts) <= 750000U);
        if (allowed) {
          ford_cam_button_active = false;
        }
      }
    }
    // Optional, explicitly selected fallback. Only the captured no-trailer
    // baseline, with the lamp-connection bit (80) or captured connected/normal-
    // charge status (84), on the camera bus. No lamp-flash variants are allowed.
    if ((msg->addr == FORD_CAM_TRAILER) && (msg->bus == FORD_CAM_BUS)) {
      const bool old_exact = ((msg->data[0] == 0U) || (msg->data[0] == 0x80U) || (msg->data[0] == 0x84U)) &&
        (msg->data[1] == 0U) && (msg->data[2] == 0x10U) &&
        (msg->data[3] == 0xFFU) && (msg->data[4] == 0xFEU) &&
        (msg->data[5] == 0U) && (msg->data[6] == 0U) && (msg->data[7] == 0U);
      const bool current_exact = ((msg->data[0] == 0U) || (msg->data[0] == 0x80U)) &&
        (msg->data[1] == 0U) && ((msg->data[2] == 0U) || (msg->data[2] == 0x10U)) &&
        (msg->data[3] == 0xFFU) && (msg->data[4] == 0xFCU) &&
        (msg->data[5] == 0U) && (msg->data[6] == 0U) && (msg->data[7] == 0U);
      const bool exact = old_exact || current_exact;
      if (exact && ((msg->data[0] == 0x80U) || (msg->data[0] == 0x84U))) {
        const bool within_window = !ford_cam_trailer_started ||
          ((uint32_t)(now - ford_cam_trailer_start_ts) < 10000000U);
        const bool rate_ok = !ford_cam_trailer_started ||
          ((uint32_t)(now - ford_cam_trailer_last_ts) >= 900000U);
        allowed = within_window && rate_ok && (ford_cam_trailer_frames < 10U);
        if (allowed) {
          if (!ford_cam_trailer_started) {
            ford_cam_trailer_start_ts = now;
          }
          ford_cam_auto_payload = current_exact;
          ford_cam_trailer_started = true;
          ford_cam_trailer_active = true;
          ford_cam_trailer_last_ts = now;
          ford_cam_trailer_frames++;
        }
      } else if (exact && (msg->data[0] == 0U)) {
        allowed = ford_cam_trailer_active;
        if (allowed) {
          ford_cam_trailer_active = false;
        }
      }
    }
  }
  return allowed;
}

static bool ford_cam_fwd(int bus_num, int addr) {
  const uint32_t now = microsecond_timer_get();
  // Stop competing real/modified status only on the main->camera path.
  // If the sender stops, normal forwarding resumes within 1.2 seconds.
  const bool lease = ford_cam_trailer_active && ford_cam_stationary() &&
    ((uint32_t)(now - ford_cam_trailer_last_ts) < 1200000U) &&
    ((uint32_t)(now - ford_cam_trailer_start_ts) < 10000000U);
  const bool length_lease = ford_cam_length_active && ford_cam_stationary() &&
    ((uint32_t)(now - ford_cam_length_last_ts) < 1200000U) &&
    ((uint32_t)(now - ford_cam_length_start_ts) < 10000000U);
  return (bus_num == (int)FORD_MAIN_BUS) &&
    (((addr == (int)FORD_CAM_TRAILER) && lease) ||
     ((addr == (int)FORD_CAM_LENGTH) && length_lease));
}
