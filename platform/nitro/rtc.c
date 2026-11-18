/* Synchronous ARM9 clock requests. The PXI reply can run on the IRQ
 * thread before the send returns. Each caller owns its completion word. */
struct RTCDate;
struct RTCTime;
typedef void (*RTCCallback)(int result, void *argument);

extern int RTC_GetDateAsync(struct RTCDate *, RTCCallback, void *);
extern int RTC_GetTimeAsync(struct RTCTime *, RTCCallback, void *);
extern int RTC_GetDateTimeAsync(struct RTCDate *, struct RTCTime *, RTCCallback, void *);
extern void PXIi_HandlerRecvFifoNotEmpty(void);

static void complete(int result, void *argument)
{
    __atomic_store_n((int *)argument, result, __ATOMIC_RELEASE);
}

static int wait_for_reply(int send_result, int *completion)
{
    if (send_result != 0)
        return send_result;
    int result;
    while ((result = __atomic_load_n(completion, __ATOMIC_ACQUIRE)) < 0)
        PXIi_HandlerRecvFifoNotEmpty();
    return result;
}

int RTC_GetDate(struct RTCDate *date)
{
    int completion = -1;
    return wait_for_reply(RTC_GetDateAsync(date, complete, &completion), &completion);
}

int RTC_GetTime(struct RTCTime *time)
{
    int completion = -1;
    return wait_for_reply(RTC_GetTimeAsync(time, complete, &completion), &completion);
}

int RTC_GetDateTime(struct RTCDate *date, struct RTCTime *time)
{
    int completion = -1;
    return wait_for_reply(RTC_GetDateTimeAsync(date, time, complete, &completion), &completion);
}
