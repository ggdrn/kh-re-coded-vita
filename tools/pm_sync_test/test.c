#include <assert.h>
#include "nitro/pm_sync_view.h"
#include "nitro/deferred_queue.h"
extern u32 PM_SetBackLight(PMLCDTarget, PMBackLightSwitch);
extern u32 PMi_SetLED(PMLEDStatus);
extern void PMi_DummyCallback(u32,void *);
static Deferred *volatile queue;
static Deferred replies[2], unrelated;
static unsigned received, submits, waits, command, send_result;
static void dma(void *a,void *b,void *c) {assert(0);}
static void reply(void *a,void *b,void *c) {
    assert((unsigned long)c==received++);
    if (!c) {
        Deferred *next=kh_take_completion(&queue,reply);
        assert(next==&replies[1]);next->fn(next->a,next->b,next->c);
    } else { PMi_DummyCallback(23,b); }
}
u32 PM_SendUtilityCommandAsync(u32 cmd,u32 value,u32 reserved,PMCallback cb,void *arg) {
    ++submits;assert(!value && !reserved && cb==PMi_DummyCallback && cmd==command);
    if(send_result)return send_result;
    replies[1]=(Deferred){reply,0,arg,(void *)1,0};
    unrelated=(Deferred){dma,0,0,0,&replies[1]};
    replies[0]=(Deferred){reply,0,arg,0,&unrelated};
    queue=&replies[0];received=0;return 0;
}
void PMi_WaitBusy(void) {
    ++waits;Deferred *node=kh_take_completion(&queue,reply);
    assert(node==&replies[0]);node->fn(node->a,node->b,node->c);
    assert(received==2 && !kh_take_completion(&queue,reply));
    assert(kh_take_completion(&queue,0)==&unrelated && !queue);
}
int main(void) {
    command=8;assert(PM_SetBackLight(PM_LCD_ALL,PM_BACKLIGHT_ON)==23);
    command=3;assert(PMi_SetLED(PM_LED_BLINK_LOW)==23);
    send_result=17;assert(PMi_SetLED(PM_LED_BLINK_LOW)==17);
    assert(PMi_SetLED(PM_LED_NONE)==0xffff);
    assert(submits==3 && waits==2);
}
