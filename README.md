# DUSTWAVE 〰️

**Closed-loop, AI-adapted ultrasonic vibration for waterless dust removal from solar panels, glass and equipment.**

## The problem
Dust cuts solar-panel output and makes glass facades and industrial equipment need frequent cleaning, which today uses water, chemicals and manual labour.

## The idea
Instead of one fixed vibration, DUSTWAVE **measures the surface, then keeps adapting the vibration pattern from the cleaning result**:

1. **Camera** photographs the dusty surface and scores it (`dust_analysis.py`).
2. **Frequency sweep**: the ESP32 sweeps the transducer and reads a vibration sensor; the software finds the surface's resonance (`find_resonance`).
3. **Adaptive controller** proposes frequency and duty for the next burst (`AdaptiveController`), always clamped to safety limits.
4. **Camera checks the result**; the dust-score drop is fed back as the reward, and the next pattern is adjusted.
5. Repeat until the dust score stops improving.

## What works today (honest status)

| Part | Status |
|---|---|
| Dust score + before/after efficiency from photos | Works; relative score, needs same camera position and lighting |
| Resonance finder from sweep CSV | Works; tested on simulated data |
| Adaptive controller | Works in simulation, with unit tests |
| Streamlit app | All four tabs run without errors in an offline test harness; please also run it once on your machine |
| ESP32 sweep/burst sketch | Compiles in a syntax check; **not yet tested on real hardware** |
| Real cleaning proof | **Not yet.** Needs bench photos from a real transducer test |

In the simulator, 25 adaptive cycles removed on average about 82% of the simulated dust versus about 35% for a fixed guessed frequency (10 random seeds; results vary a lot per seed). **This is a model, not experimental evidence.**

## Run it
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
python tests/test_core.py     # run the tests
```

## Hardware (bench prototype)
- ESP32, small 40 kHz piezo transducer or disc, logic-level MOSFET or piezo driver, vibration sensor (analog), ARM switch.
- Wiring and serial commands are at the top of `hardware/esp32_dustwave.ino`. Never drive a transducer straight from a GPIO pin. Output only runs while the ARM switch is held, duty is capped at 30% and bursts at 200 ms.
- Serial output of the sweep (`freq_hz,response`) can be saved as a CSV and loaded in the app's *Frequency sweep* tab.

## Next steps
1. Bench test on a small glass or panel sample with fine dust; log before/after photos.
2. Replace the pixel-contrast score with a model trained on your own labelled photos.
3. Scale up: multiple transducers and a dust-collection path (suction or edge channel).

## Limits
Ultrasonic energy in air attenuates quickly and sticky or humid dust resists vibration, so performance will depend on the dust, the surface and the mounting. Do not expose people or animals to ultrasonic output.

## Structure
```
app.py  dust_analysis.py  wave_optimizer.py  simulator.py
hardware/esp32_dustwave.ino   data/sample_sweep.csv   tests/test_core.py
```
