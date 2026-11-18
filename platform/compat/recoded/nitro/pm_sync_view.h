#ifndef KH_PM_SYNC_VIEW_H
#define KH_PM_SYNC_VIEW_H
#include "nitro/types.h"
typedef void (*PMCallback)(u32 result, void *argument);
typedef enum PMLCDTarget {
    PM_LCD_TOP = 0,
    PM_LCD_BOTTOM = 1,
    PM_LCD_ALL = 2
} PMLCDTarget;
typedef enum PMBackLightSwitch {
    PM_BACKLIGHT_OFF = 0,
    PM_BACKLIGHT_ON = 1
} PMBackLightSwitch;
typedef enum PMLEDStatus {
    PM_LED_NONE = 0,
    PM_LED_ON = 1,
    PM_LED_BLINK_LOW = 2,
    PM_LED_BLINK_HIGH = 3
} PMLEDStatus;
#define PM_SUCCESS 0
#endif
