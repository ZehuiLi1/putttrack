# Ball IMU State Recognition — Research and Implementation Direction

**Status:** evidence-gated research direction  
**Applies to:** Nordic nRF54L15 Tag research ball, instrumented ball prototype, later custom Smart Ball EVT  
**Architecture authority:** [`../ARCHITECTURE_CONSTITUTION.md`](../ARCHITECTURE_CONSTITUTION.md)  
**Experiment authority:** [`../EXPERIMENT_PLAN.md`](../EXPERIMENT_PLAN.md)

## 1. Decision

PuttTrack should **not** choose a final ball-state classifier before collecting real IMU data from a mechanically representative ball.

The correct sequence is:

```text
Nordic Tag sensor/logger bring-up
        ->
instrumented research-ball prototype
        ->
raw labelled IMU dataset
        ->
rule/FSM baseline
        ->
feature + Random Forest baseline
        ->
small temporal model only where it adds measurable value
        ->
freeze production sensor ranges / sampling / mechanics
        ->
custom Ball PCB + production classifier
```

This does **not** mean waiting for the final production ball before doing any work. The first ball only needs to be a safe, repeatable **research instrument** that puts the sensors inside a ball-like mechanical structure and preserves raw data.

A bare Nordic Tag is useful for firmware, timestamp, FIFO, BLE/UART and sensor bring-up, but it is not sufficient evidence for final thresholds or model training. Potting, enclosure stiffness, PCB mounting, centre of mass and shell contact can materially change impact and rolling waveforms.

## 2. Recommended architecture

The preferred architecture is hybrid and hierarchical rather than one opaque multi-class neural network:

```text
ADXL367 low-power motion wake
        ->
BMI270 active FIFO capture
        ->
pre-processing / orientation-invariant magnitudes
        ->
fast event detectors
  impact / free-fall / stationary
        +
window features
        ->
small classifier for ambiguous windows
        ->
temporal FSM + hysteresis + refractory periods
        ->
generic BallPhysicalState + confidence
        ->
Venue evidence fusion
        ->
SHOT_CONFIRMED / CUP_CONFIRMED / gameplay event
```

The ball may infer generic physical states such as:

- `STATIONARY`
- `IMPACT`
- `ROLLING`
- `SLOWING` / `SETTLING`
- `PICKED_UP` / `CARRIED`
- `FREE_FALL` / `DROP`
- `COLLISION`

It must not directly own score, player identity, hole-specific rules or final gameplay truth.

## 3. Algorithm recommendation

### V0 — rules + FSM first

Start with deterministic signal processing and a temporal state machine.

Useful orientation-invariant signals:

```text
A = sqrt(ax^2 + ay^2 + az^2)
W = sqrt(gx^2 + gy^2 + gz^2)
jerk ~= dA/dt
HF_energy = energy(high-pass(A))
```

Candidate rules:

- `STATIONARY`: low acceleration variance + low gyro RMS for a sustained dwell;
- `IMPACT`: short high jerk / high-frequency acceleration event with debounce and refractory period;
- `ROLLING`: sustained rotational activity after an impact/motion transition;
- `SLOWING`: rotational/activity envelope trends downward over time;
- `FREE_FALL`: acceleration magnitude approaches zero for a short valid interval;
- `DROP`: `FREE_FALL -> IMPACT -> settling` sequence;
- `PICKED_UP`: stationary-to-motion transition with sustained gravity-vector/orientation change and no normal rolling signature;
- `COLLISION`: impact interpreted using pre/post state and context, not peak amplitude alone.

The exact thresholds are **not design constants yet**. They must come from the measured distributions.

### V1 — handcrafted features + Random Forest

If V0 leaves ambiguous classes, use time-window features and a compact tree classifier before deep learning.

Recommended first ML baseline:

- Random Forest;
- optionally linear/RBF SVM for comparison;
- train on features extracted with TSFEL/own feature code;
- deploy only after reducing to a small, explainable feature set.

Useful features include:

- mean / standard deviation / variance / RMS;
- max / min / peak-to-peak;
- jerk peak and RMS;
- high-pass energy;
- zero-crossing / sign-change counts where useful;
- gyro RMS and decay slope;
- spectral energy / dominant frequency;
- gravity-vector change;
- duration and preceding/following state.

Random Forest is the preferred first ML benchmark because it provides feature importance, works well with modest datasets and can be converted to embedded C if the model remains small.

### V2 — tiny 1D-CNN / TCN only for residual ambiguity

Use a quantised temporal neural model only if held-out data shows a real gain, especially for difficult distinctions such as:

- putter strike vs wall/ball collision;
- pickup/carry vs unusual rolling/handling;
- complex cup/drop/bounce sequences.

Prefer tiny 1D-CNN or TCN over LSTM as the first temporal neural baseline because convolutional models are generally simpler to quantise and schedule on a Cortex-M-class MCU.

Do not use a Transformer or an end-to-end model that directly produces score for Production V1.

## 4. Sensor-range and sampling gates

The nRF54L15 Tag is an excellent research platform because it combines nRF54L15, ADXL367 and BMI270, but the final Smart Ball sensor choice remains evidence-gated.

### Initial research configuration

Start with:

- low-power motion wake on ADXL367;
- BMI270 accel/gyro active capture around **400 Hz** for general state work;
- raise accelerometer capture toward **1–1.6 kHz** around impact experiments where practical;
- use FIFO and preserve pre/post-trigger samples;
- keep raw `ax, ay, az, gx, gy, gz` in addition to any derived state.

### Critical saturation checks

BMI270 acceleration range is limited to `±16 g` and gyro to `±2000 dps`. Both limits must be treated as experimental questions, not assumed adequate.

For a 42.7 mm-diameter ball in pure rolling:

```text
omega = v / r
```

At approximately `1 m/s`, angular rate is already about `2680 dps`, above the BMI270 gyro full-scale range. A normal faster putt can therefore clip the gyro even when the state is still easy to classify qualitatively.

Likewise, a rigidly mounted IMU can see putter-impact acceleration well above `16 g`.

Therefore the first dataset must record clipping/saturation counts explicitly.

If impact clipping prevents reliable discrimination, evaluate a separate high-g accelerometer such as an ADXL372-class `±200 g` device during EVT. Do **not** add it to the production BOM merely because high-g events are possible; add it only if the measured data shows that the existing sensors lose information needed by the product.

## 5. Research-ball requirement

Before collecting the canonical motion dataset, build an instrumented research ball with:

- the sensor board/core rigidly and repeatably located;
- documented ball mass and centre-of-mass offset;
- fixed sensor coordinate frame;
- no loose battery or PCB motion;
- an enclosure that can survive the intended weak-to-normal putting tests;
- a way to recover logs and identify each run;
- visible external orientation marks for experiments.

The first research ball does **not** need final RF tuning, production potting, final battery life or tournament-conforming balance. It only needs to be mechanically repeatable enough that labelled motion data is meaningful.

A second mechanically different ball/core is valuable later to test whether the classifier generalises across units rather than learning one enclosure's vibration signature.

## 6. Canonical dataset

Minimum labelled episodes:

1. stationary;
2. weak putter strike;
3. normal putter strike;
4. strong putter strike;
5. straight roll;
6. slow roll / settling;
7. wall collision;
8. ball-ball collision;
9. pickup;
10. carry;
11. hand roll / deliberate manipulation;
12. drop;
13. bounce;
14. cup drop / bounce / rest;
15. remove ball from cup;
16. ramp ascent / rollback where relevant.

Start with roughly **100–200 episodes per important class**, using multiple orientations, speeds, operators and surfaces. Increase the difficult/confused classes after the first confusion matrix rather than collecting all classes equally forever.

Use independent video ground truth for dynamic/ambiguous sequences. A low/oblique calibrated camera is sufficient; a tall overhead camera is not required.

Canonical raw schema:

```text
t_us,ax,ay,az,gx,gy,gz,label,event_id,ball_id,session_id
```

Also retain:

- sensor range / ODR configuration;
- clipping flags/counts;
- firmware commit;
- ball mechanical revision;
- battery state where practical;
- operator and surface;
- synchronized video/CS reference IDs.

Train/test splits must be separated by **session and preferably ball**, not by randomly splitting adjacent windows from the same episode.

## 7. Evaluation

Do not optimise only overall classification accuracy.

Primary product metrics:

- stroke/impact precision, recall and F1;
- missed-stroke rate;
- false strokes per player-hour / per labelled non-stroke episode;
- event timestamp error;
- state confusion matrix;
- pickup/drop/collision confusion;
- latency;
- CPU/RAM/flash cost;
- active energy per event;
- clipping/saturation rate;
- robustness across balls, orientations, surfaces and operators.

Architecture candidate target remains:

- stroke recall `>= 99%`;
- false-stroke rate `<= 0.1%` of labelled non-stroke episodes;

but these are verification targets, not current measured performance.

## 8. What IMU may and may not decide

IMU is expected to be strong for:

- stationary vs active;
- impact timing;
- free-fall/drop sequences;
- broad rolling/settling context;
- pickup/carry evidence after temporal modelling.

IMU alone is least trustworthy for authoritative semantic distinctions such as:

- putter strike vs another-ball/wall collision in every geometry;
- whether a ball entered the correct cup;
- whether a feature/route should score;
- whether a movement is a valid stroke under a particular hole rule.

Those should remain evidence-fusion decisions using spatial/channel-sounding context and physical tee/cup/feature sensors where appropriate.

## 9. First implementation references

Priority references from the 2026-08 research pass:

1. Nordic Trackaball / nRF54L15 public case study  
   <https://www.nordicsemi.com/Nordic-news/2025/08/Puttshack-Trackaball-uses-Nordic-nRF54L15-SoC-and-nPM2100-PMIC>
2. Nordic nRF54L15 Tag platform  
   <https://devzone.nordicsemi.com/nordic/nordic-blog/b/blog/posts/introducing-the-nrf54l15-tag-tiny-dual-antenna-prototyping-platform>
3. Nordic Edge AI Data Forwarder  
   <https://nrfconnectdocs.nordicsemi.com/addons/addon-edge-ai/latest/samples/data_forwarder/README.html>
4. Nordic Edge AI workflow  
   <https://nrfconnectdocs.nordicsemi.com/addons/addon-edge-ai/latest/quick_start/nrf_edgeai.html>
5. Bosch BMI270 Sensor API  
   <https://github.com/boschsensortec/BMI270_SensorAPI>
6. ARM CMSIS-DSP  
   <https://github.com/ARM-software/CMSIS-DSP>
7. TensorFlow Lite Micro  
   <https://github.com/tensorflow/tflite-micro>
8. TSFEL time-series feature extraction  
   <https://github.com/fraunhoferportugal/tsfel>
9. `micromlgen` tree/SVM-to-C reference  
   <https://github.com/eloquentarduino/micromlgen>
10. Punchihewa et al., IMU impact detection, Sensors 2021  
    <https://www.mdpi.com/1424-8220/21/9/3002>
11. Shieh et al., embedded Smart Ball IMU study, Sensors 2020  
    <https://pmc.ncbi.nlm.nih.gov/articles/PMC7571218/>
12. World Golf Systems / Puttshack Australian patent family reference  
    <https://patents.google.com/patent/AU2013250910B2/en>

The patent material is useful prior-art and architecture evidence, not a freedom-to-operate opinion. Production authority should continue to avoid hole-specific movement signatures unless a later claims-based legal review supports that direction.

## 10. Immediate execution order

When the Nordic Tag / research-ball hardware is available:

1. verify raw BMI270 accel/gyro streaming, FIFO, timestamps and dropped-sample detection;
2. measure stationary noise and bias in several orientations;
3. perform gentle impact/roll tests and quantify accel/gyro clipping;
4. build/fix the mechanically repeatable research-ball core;
5. repeat the same tests inside the ball and compare with bare-board signals;
6. synchronize video ground truth;
7. collect the first labelled dataset;
8. implement the V0 rule/FSM baseline;
9. produce confusion matrix and false-stroke analysis;
10. only then train RF and, if justified, a tiny 1D-CNN/TCN;
11. use those results to decide whether BMI270 alone is sufficient or a high-g / higher-rate sensor is needed;
12. freeze the final ball sensor/BOM only after the evidence exists.

## Bottom line

**Build the research ball first, not the final product ball. Collect raw data before choosing the final algorithm.**

The likely production solution is not “AI everywhere”; it is expected to be a low-power wake path + high-rate event capture + simple deterministic event detectors + temporal FSM, with a small ML classifier only for classes that remain ambiguous on held-out real-ball data.
