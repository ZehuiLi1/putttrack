/* SPDX-License-Identifier: Apache-2.0 */
#include "stroke_pickup_v1.h"
#include <stdio.h>
#include <inttypes.h>
int main(void){
    struct spv1_context c;spv1_init(&c);char line[512];uint32_t n=0;
    while(fgets(line,sizeof(line),stdin)){
        struct spv1_sample s={0};unsigned valid;unsigned long long t;char extra;
        int got=sscanf(line,"%" SCNu32 ",%llu,%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%" SCNd32 ",%u,%" SCNu32 " %c",
            &s.sequence,&t,&s.accel_micro[0],&s.accel_micro[1],&s.accel_micro[2],&s.gyro_micro[0],&s.gyro_micro[1],&s.gyro_micro[2],&valid,&s.sensor_errors,&extra);
        if(got!=10||valid>1U){fprintf(stderr,"invalid input line %u\n",n+1U);return 2;}
        s.time_us=(uint64_t)t;s.valid=valid!=0;uint32_t before=c.latest_id;
        spv1_push(&c,&s);n++;
        for(uint32_t event_id=before+1U; event_id<=c.latest_id && event_id>0U; event_id++){
            const struct spv1_event *e=&c.events[(event_id-1U)%SPV1_EVENT_CAPACITY];
            printf("{\"kind\":\"event\",\"id\":%u,\"type\":%u,\"name\":\"%s\",\"reason\":%u,\"quality\":%u,\"onset_seq\":%u,\"end_seq\":%u,\"onset_us\":%" PRIu64 ",\"decision_us\":%" PRIu64 ",\"impulse_milli\":%d,\"gyro_mean_milli\":%d,\"direction_milli\":%u,\"axial_milli\":%u,\"impact_milli\":%u,\"clip_permille\":%u}\n",
            e->id,e->type,spv1_event_name(e->type),e->reason,e->quality,e->onset_seq,e->end_seq,e->onset_us,e->decision_us,e->impulse_milli,e->gyro_mean_milli,e->direction_milli,e->axial_milli,e->impact_milli,e->clip_permille);
        }
    }
    if(ferror(stdin))return 3;
    printf("{\"kind\":\"summary\",\"samples\":%u,\"stroke_candidates\":%u,\"pickup_candidates\":%u,\"ambiguous_contacts\":%u,\"unknown_onsets\":%u,\"quality_breaks\":%u,\"state\":%u,\"held_hint\":%s,\"count_incomplete\":%s,\"context_bytes\":%zu,\"config_sha256\":\"%s\",\"authority\":false}\n",
    n,c.stroke_candidates,c.pickup_candidates,c.ambiguous_contacts,c.unknown_onsets,c.quality_breaks,(unsigned)c.state,c.held_hint?"true":"false",c.count_incomplete?"true":"false",sizeof(c),SPV1_CONFIG_SHA256);
    return 0;
}
