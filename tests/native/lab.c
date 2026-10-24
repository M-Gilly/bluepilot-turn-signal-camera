#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
static uint32_t lab_clock = 1000000U;
uint32_t microsecond_timer_get(void) { return lab_clock; }
#include "opendbc/safety/can.h"
#include "opendbc/safety/safety.h"
static CANPacket_t packet(int addr, int bus, int length, const unsigned char *data) {
  CANPacket_t p = {0};
  p.addr = (unsigned int)addr;
  p.bus = (unsigned char)bus;
  for (unsigned int i=0U;i<16U;i++) {
    if (dlc_to_len[i] == length) { p.data_len_code = i; break; }
  }
  if ((length >= 0) && (length <= 64)) { memcpy(p.data, data, (size_t)length); }
  return p;
}
void lab_time(uint32_t t) { lab_clock=t; }
void lab_flags(int allowed, int lateral, int moving, int invalid) {
 controls_allowed=allowed!=0; controls_allowed_lateral=lateral!=0;
 vehicle_moving=moving!=0; safety_rx_checks_invalid=invalid!=0;
}
int lab_init(int param, int sp) {
 current_safety_param_sp=(uint16_t)sp;
 int r=set_safety_hooks(SAFETY_FORD,(uint16_t)param);
 lab_flags(0,0,0,0);return r;
}
int lab_rx(int addr, int bus, int len, const unsigned char *data) {
 CANPacket_t p=packet(addr,bus,len,data);return safety_rx_hook(&p);
}
int lab_tx(int addr, int bus, int len, const unsigned char *data) {
 CANPacket_t p=packet(addr,bus,len,data);return safety_tx_hook(&p);
}
int lab_fwd(int bus, int addr) { return safety_fwd_hook(bus,addr); }
