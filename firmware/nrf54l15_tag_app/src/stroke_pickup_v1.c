/* SPDX-License-Identifier: Apache-2.0 */
#include "stroke_pickup_v1.h"
#include <math.h>
#include <string.h>
#include <limits.h>
_Static_assert(sizeof(struct spv1_context) <= 4096U, "shadow engine RAM limit");
#define GRAVITY 9.80665f
static float norm3(const float v[3]) { return sqrtf(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]); }
static float clamp(float x, float lo, float hi) { return fminf(hi,fmaxf(lo,x)); }
static uint32_t milli(float x) { return (uint32_t)(clamp(x,0.0f,100000.0f)*1000.0f+0.5f); }
static void inc(struct spv1_context *c, uint32_t *p) {
    if (*p < UINT32_MAX) (*p)++;
    else { c->current_quality |= SP_COUNTER_OVERFLOW; c->count_incomplete=true; }
}
static void rotate_up(float up[3], const float gyro[3], float dt) {
    float n=norm3(gyro); if (n<1e-8f) return;
    float k[3]={gyro[0]/n,gyro[1]/n,gyro[2]/n};
    float co=cosf(n*dt), si=-sinf(n*dt);
    float dot=k[0]*up[0]+k[1]*up[1]+k[2]*up[2];
    float cross[3]={k[1]*up[2]-k[2]*up[1],k[2]*up[0]-k[0]*up[2],k[0]*up[1]-k[1]*up[0]};
    for (int i=0;i<3;i++) up[i]=up[i]*co+cross[i]*si+k[i]*dot*(1.0f-co);
}
/* tr(M^2)/tr(M)^2 lies in [1/3,1]. Unlike signed mean it retains axial
 * concentration under reversal. It is not a principal eigenvalue estimate.
 * It is a measured/censored statistic when any axis is near its rail. */
static float axial(const struct spv1_window *w) {
    const float *m=w->moment;
    float tr=m[0]+m[1]+m[2]; if (tr<1e-10f) return 0.0f;
    return clamp((m[0]*m[0]+m[1]*m[1]+m[2]*m[2]+2.0f*(m[3]*m[3]+m[4]*m[4]+m[5]*m[5]))/(tr*tr),0,1);
}
static void emit(struct spv1_context *c,uint32_t type,uint32_t reason,uint32_t quality,
                 uint64_t onset,uint32_t seq,const struct spv1_window *w) {
    if (c->latest_id==UINT32_MAX) { c->current_quality|=SP_COUNTER_OVERFLOW;c->count_incomplete=true;return; }
    struct spv1_event e={0}; e.id=++c->latest_id;e.type=type;e.reason=reason;e.quality=quality;
    e.onset_us=onset;e.onset_seq=seq;e.end_seq=c->source_sequence;e.decision_us=c->source_us;
    if(w && w->samples) {
        e.impulse_milli=w->up_valid?(int32_t)milli(w->impulse):-1;
        e.gyro_mean_milli=(int32_t)milli(w->gyro_sum/(float)w->samples);
        e.direction_milli=milli(w->gyro_sum>1e-8f?clamp(norm3(w->gyro_vector)/w->gyro_sum,0,1):0);
        e.axial_milli=milli(axial(w));e.impact_milli=milli(w->impact_max);
        e.clip_permille=1000U*w->clip_samples/w->samples;
    } else { e.impulse_milli=-1; }
    c->events[(e.id-1U)%SPV1_EVENT_CAPACITY]=e;
    if(c->event_count<SPV1_EVENT_CAPACITY)c->event_count++;else inc(c,&c->overwritten);
}
void spv1_init(struct spv1_context *c) { memset(c,0,sizeof(*c));c->gravity=GRAVITY;c->state=SP_BOOTSTRAP; }
void spv1_invalidate(struct spv1_context *c) {
    /* Never silently reset audit counters after an idle/recovery transition. */
    c->have_previous=false;c->armed=false;c->window.active=false;
    c->quiet_samples=0;c->state=SP_BOOTSTRAP;c->count_incomplete=true;
    memset(c->quiet_accel_sum,0,sizeof(c->quiet_accel_sum));inc(c,&c->generation);
}
void spv1_new_trial(struct spv1_context *c) {
    uint32_t next=c->generation; if(next<UINT32_MAX)next++;
    spv1_init(c);c->generation=next;
    if(next==UINT32_MAX){c->current_quality|=SP_COUNTER_OVERFLOW;c->count_incomplete=true;}
}
static void begin(struct spv1_context *c) {
    struct spv1_window *w=&c->window;memset(w,0,sizeof(*w));
    w->active=true;w->up_valid=true;w->start_us=c->source_us;w->start_seq=c->source_sequence;
    for(int i=0;i<3;i++)w->up[i]=c->quiet_accel_sum[i]/(float)c->quiet_samples;
    w->gravity=norm3(w->up);
    if(w->gravity<8.0f||w->gravity>12.0f) {w->up_valid=false;w->quality|=SP_NO_BASELINE;}
    else for(int i=0;i<3;i++)w->up[i]/=w->gravity;
    c->armed=false;c->state=SP_MOVING;
}
static void finish(struct spv1_context *c) {
    struct spv1_window *w=&c->window;
    float gm=w->samples?w->gyro_sum/(float)w->samples:0;
    float direction=w->gyro_sum>1e-8f?norm3(w->gyro_vector)/w->gyro_sum:0;
    bool impact=w->impact_max>=SPV1_CONTACT_DELTA_MPS2;
    bool rotation=gm>=SPV1_STROKE_MEAN_GYRO_MIN_RADS && direction>=SPV1_STROKE_DIRECTION_MIN;
    float pickup_score=(w->up_valid && w->impulse>SPV1_PICKUP_POSITIVE_IMPULSE_MIN_MPS?2.0f:0.0f)
          +(gm<SPV1_PICKUP_MEAN_GYRO_MAX_RADS?1.0f:0.0f)+(direction<0.75f?0.5f:0.0f);
    bool pickup=w->up_valid && !(w->quality&(SP_ACCEL_RAIL|SP_GYRO_RAIL)) && pickup_score>SPV1_PICKUP_SCORE_MIN;
    uint32_t reason=(impact?SP_HAS_EARLY_TRANSIENT:0U)|(rotation?SP_HAS_ROTATION:0U)|(pickup?SP_HAS_LIFT_SCORE:0U);
    uint32_t quality=w->quality;
    if(w->samples<40U||w->active_samples<6U) {quality|=SP_WINDOW;pickup=false;rotation=false;}
    if(pickup) {
        inc(c,&c->pickup_candidates);c->held_hint=true;
        emit(c,SP_PICKUP_SUSPECTED,reason|SP_HELD_UNRESOLVED,quality,w->start_us,w->start_seq,w);
    } else if(impact && (rotation || w->stroke_pending) && !c->held_hint && !(quality & SP_WINDOW)) {
        inc(c,&c->stroke_candidates);
        emit(c,SP_STROKE_LIKE,reason|SP_NEEDS_CONTACT_SOURCE,quality,w->start_us,w->start_seq,w);
    } else {
        inc(c,&c->unknown_onsets);c->count_incomplete=true;
        if(c->held_hint){reason|=SP_HELD_UNRESOLVED;quality|=SP_HELD_CONTEXT;}
        emit(c,SP_ONSET_UNRESOLVED,reason|SP_WEAK_OR_UNSUPPORTED,quality,w->start_us,w->start_seq,w);
    }
    c->state=rotation?SP_ROTATION:SP_MOVING;w->active=false;
}
void spv1_push(struct spv1_context *c,const struct spv1_sample *s) {
    float a[3],g[3];for(int i=0;i<3;i++){a[i]=s->accel_micro[i]*1e-6f;g[i]=s->gyro_micro[i]*1e-6f;}
    uint32_t fault=(!s->valid||s->sensor_errors)?SP_SENSOR:0U;
    uint64_t dt_us=0;float dt=0;
    if(c->have_previous){
        if(s->sequence!=(uint32_t)(c->source_sequence+1U))fault|=SP_SEQUENCE;
        if(s->time_us<=c->source_us)fault|=SP_TIME;
        else {dt_us=s->time_us-c->source_us;if(dt_us<SPV1_MINIMUM_DT_US||dt_us>SPV1_MAXIMUM_DT_US)fault|=SP_TIME;}
        dt=(float)dt_us*1e-6f;
    }
    float delta[3];for(int i=0;i<3;i++)delta[i]=a[i]-c->previous_accel[i];
    float da=c->have_previous?norm3(delta):0.0f;
    c->source_us=s->time_us;c->source_sequence=s->sequence;c->current_quality=0;
    for(int i=0;i<3;i++){
        if(fabsf(a[i])>=SPV1_ACCEL_NEAR_RAIL_MPS2)c->current_quality|=SP_ACCEL_RAIL;
        if(fabsf(g[i])>=SPV1_GYRO_NEAR_RAIL_RADS)c->current_quality|=SP_GYRO_RAIL;
    }
    if(fault){
        c->current_quality|=fault;inc(c,&c->quality_breaks);c->count_incomplete=true;
        emit(c,SP_QUALITY_BREAK,SP_INTERRUPTED,c->current_quality,s->time_us,s->sequence,NULL);
        c->window.active=false;c->armed=false;c->quiet_samples=0;c->state=SP_DEGRADED;
        memset(c->quiet_accel_sum,0,sizeof(c->quiet_accel_sum));
        /* Invalid samples cannot establish any new window. */
        goto done;
    }
    float an=norm3(a),gn=norm3(g);
    /* A stationary sensor may have a repeatable norm offset from 1g.
     * Compare local variation, not a narrow hard-coded gravity error. */
    bool quiet=an>=SPV1_BASELINE_ACCEL_NORM_MIN_MPS2 && an<=SPV1_BASELINE_ACCEL_NORM_MAX_MPS2 &&
        gn<=SPV1_QUIET_GYRO_RADS && (c->quiet_samples==0U ||
        fabsf(an-c->quiet_norm_mean)<=SPV1_QUIET_ACCEL_DEVIATION_MPS2);
    bool active=fabsf(an-c->gravity)>=SPV1_ONSET_ACCEL_DEVIATION_MPS2 || gn>=SPV1_ONSET_GYRO_RADS;
    if(c->armed && !c->window.active && active)begin(c);
    if(quiet){
        if(c->quiet_samples==0U)c->quiet_start_us=s->time_us;
        /* bounded running baseline, no growing accumulator in long idle */
        if(c->quiet_samples<1000U){for(int i=0;i<3;i++)c->quiet_accel_sum[i]+=a[i];c->quiet_samples++;
            c->quiet_norm_mean+=(an-c->quiet_norm_mean)/(float)c->quiet_samples;}
        if(c->quiet_samples>=40U && s->time_us-c->quiet_start_us>=SPV1_QUIET_DWELL_US && !c->window.active){
            c->armed=true;c->state=SP_QUIET;
            float base[3];for(int i=0;i<3;i++)base[i]=c->quiet_accel_sum[i]/(float)c->quiet_samples;
            float bn=norm3(base);if(bn>=8.0f&&bn<=12.0f)c->gravity=bn;
        }
    }else if(!c->armed||active){c->quiet_samples=0;memset(c->quiet_accel_sum,0,sizeof(c->quiet_accel_sum));}
    if(c->window.active){
        struct spv1_window *w=&c->window;uint64_t elapsed=s->time_us-w->start_us;
        w->quality|=c->current_quality;
        if(c->current_quality&(SP_ACCEL_RAIL|SP_GYRO_RAIL))w->up_valid=false;
        if(w->samples && w->up_valid)rotate_up(w->up,c->previous_gyro,dt);
        w->samples++;w->active_samples+=active?1U:0U;w->gyro_sum+=gn;
        for(int i=0;i<3;i++)w->gyro_vector[i]+=g[i];
        w->moment[0]+=g[0]*g[0];w->moment[1]+=g[1]*g[1];w->moment[2]+=g[2]*g[2];
        w->moment[3]+=g[0]*g[1];w->moment[4]+=g[0]*g[2];w->moment[5]+=g[1]*g[2];
        if(c->current_quality&SP_GYRO_RAIL)w->clip_samples++;
        if(elapsed<=SPV1_EARLY_IMPACT_WINDOW_US)w->impact_max=fmaxf(w->impact_max,da);
        if(elapsed<=SPV1_IMPULSE_WINDOW_US && w->up_valid && w->samples>1U){
            float az=a[0]*w->up[0]+a[1]*w->up[1]+a[2]*w->up[2]-w->gravity;
            w->impulse+=fmaxf(0.0f,az)*dt;
        }
        if(!w->stroke_checked && elapsed>=SPV1_STROKE_DECISION_WINDOW_US){
            w->stroke_checked=true;
            float early_gm=w->gyro_sum/(float)w->samples;
            float early_direction=w->gyro_sum>1e-8f?norm3(w->gyro_vector)/w->gyro_sum:0;
            if(w->samples>=8U && w->active_samples>=6U &&
               w->impact_max>=SPV1_CONTACT_DELTA_MPS2 &&
               early_gm>=SPV1_STROKE_MEAN_GYRO_MIN_RADS &&
               early_direction>=SPV1_STROKE_DIRECTION_MIN && !c->held_hint){
                w->stroke_pending=true;
                emit(c,SP_STROKE_PENDING,SP_HAS_EARLY_TRANSIENT|SP_HAS_ROTATION|SP_NEEDS_CONTACT_SOURCE,
                     w->quality,w->start_us,w->start_seq,w);
            }
        }
        if(da>=SPV1_CONTACT_DELTA_MPS2){
            if(elapsed>SPV1_STROKE_DECISION_WINDOW_US &&
               (c->last_contact_us==0U||s->time_us-c->last_contact_us>SPV1_CONTACT_MERGE_US)){
                inc(c,&c->ambiguous_contacts);c->count_incomplete=true;
                emit(c,SP_CONTACT_MOVING,SP_FROM_MOVING|SP_NEEDS_CONTACT_SOURCE,
                     c->current_quality,s->time_us,s->sequence,NULL);
            }
            c->last_contact_us=s->time_us;
        }
        if(elapsed>=SPV1_DECISION_WINDOW_US)finish(c);
    }else if(active && !c->armed){
        /* No semantic veto: a later contact can be a collision OR second stroke.
         * It is never silently treated as zero additional strokes. */
        if(da>=SPV1_CONTACT_DELTA_MPS2){
            if(c->last_contact_us==0U||s->time_us-c->last_contact_us>SPV1_CONTACT_MERGE_US){
                inc(c,&c->ambiguous_contacts);c->count_incomplete=true;
                emit(c,SP_CONTACT_MOVING,SP_FROM_MOVING|SP_NEEDS_CONTACT_SOURCE,c->current_quality,s->time_us,s->sequence,NULL);
            }
            c->last_contact_us=s->time_us;
        }
        /* Recover descriptive activity without waiting for a future stop. */
        c->state=gn>=SPV1_STROKE_MEAN_GYRO_MIN_RADS?SP_ROTATION:SP_MOVING;
    }
done:
    for(int i=0;i<3;i++){c->previous_accel[i]=a[i];c->previous_gyro[i]=g[i];}
    c->have_previous=true;
}
size_t spv1_events(const struct spv1_context *c,struct spv1_event *out,size_t capacity){
    size_t n=c->event_count;if(n>capacity)n=capacity;
    uint32_t start=c->latest_id-(uint32_t)n+1U;
    for(size_t i=0;i<n;i++)out[i]=c->events[(start+(uint32_t)i-1U)%SPV1_EVENT_CAPACITY];
    return n;
}
const char *spv1_event_name(uint32_t t){
    switch(t){case SP_STROKE_PENDING:return "STROKE_PENDING_NOT_COUNTED";case SP_STROKE_LIKE:return "STROKE_LIKE_CANDIDATE";case SP_PICKUP_SUSPECTED:return "PICKUP_SUSPECTED";
    case SP_CONTACT_MOVING:return "MOTION_TRANSIENT_UNRESOLVED";case SP_QUALITY_BREAK:return "QUALITY_BREAK";
    default:return "ONSET_UNRESOLVED";}
}
