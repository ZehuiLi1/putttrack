# nRF54L15 Tag mechanical envelope for the research ball

## Source and reproducibility

Nordic published `nrf54l15_tag_v1.0.step` with the nRF54L15 Tag enclosure
article. The local file inspected on 2026-09-02 has:

- size: `5,169,968` bytes;
- SHA-256: `77a874066e029b6f094a1b5a472dbac75be0d82262060d064a5613a86dc91636`;
- STEP header timestamp: `2026-08-03T13:13:39`;
- units: millimetres;
- assembly root: `PCB`, with 70 named component instances.

Source:
[Nordic nRF54L15 Tag STEP model](https://devzone.nordicsemi.com/cfs-file/__key/communityserver-blogs-components-weblogfiles/00-00-00-00-04/nrf54l15_5F00_tag_5F00_v1.0.step).

The vendor model is not copied into this repository because its redistribution
terms have not been established. Reproduce the measurement from a separately
downloaded copy with an external CadQuery environment:

```bash
python tools/inspect_tag_step.py /path/to/nrf54l15_tag_v1.0.step
```

## Measured model envelope

The STEP coordinate origin is on the component-side PCB surface (`z = 0`).
These are axis-aligned model bounds, not hand-measured board claims.

| Region | X (mm) | Y (mm) | Z (mm) | Size (mm) |
|---|---:|---:|---:|---:|
| Complete populated assembly | -16.600 to 16.500 | -16.500 to 16.500 | -5.981 to 2.500 | 33.100 × 33.000 × 8.481 |
| PCB (`Board`) | -16.500 to 16.500 | -16.500 to 16.500 | -0.811 to 0.000 | 33.000 × 33.000 × 0.811 |
| Reset switch (`SW1`) | -6.100 to -2.900 | -2.838 to 1.737 | 0.000 to 2.500 | 3.200 × 4.575 × 2.500 |
| Edge/debug connector (`P1`) | -16.600 to -10.830 | -3.375 to 3.375 | -3.911 to 1.189 | 5.770 × 6.750 × 5.100 |
| Battery-holder model (`Bat1`) | -8.000 to 8.000 | -15.700 to 15.850 | -5.981 to -0.801 | 16.000 × 31.550 × 5.180 |
| Cell model (`Free-Models`) | -10.000 to 10.000 | -10.000 to 10.000 | -5.111 to -1.911 | 20.000 × 20.000 × 3.200 |
| 2.4 GHz antenna `A1` | 6.604 to 10.196 | 10.854 to 13.746 | 0.000 to 1.202 | 3.592 × 2.892 × 1.202 |
| 2.4 GHz antenna `A2` | 6.604 to 10.196 | -13.746 to -10.854 | 0.000 to 1.202 | 3.592 × 2.892 × 1.202 |

The model therefore fits inside a conservative cylindrical keep-in envelope of
`34.0 mm diameter × 9.2 mm height` after allowing approximately 0.45 mm radial
and 0.36 mm axial clearance per side. That envelope is a starting point for a
removable carrier, not a production tolerance. Verify the printed carrier
against the physical board before closing the ball.

## First research-ball CAD constraints

Use the existing two-half ball only as a research enclosure. The first revision
should optimize repeatability and recoverability, not final balance or impact
survival:

1. Place the PCB approximately in the ball's equatorial plane and center the
   complete `34.0 × 9.2 mm` keep-in envelope, not only the 33 mm board outline.
2. Locate the board from its perimeter with three or four broad polymer seats.
   Do not clamp the switch, connector, battery clip, sensors or antennas.
3. Retain the cell independently so it cannot chatter against the PCB during
   rolling or a gentle strike. Loose cell motion invalidates the IMU label.
4. Keep both `A1`/`A2` regions free of screws, metal ballast and dense conductive
   material. Use polymer near their coordinates and leave room for RF testing.
5. Keep a removable cap or split that allows cell replacement, reset access and
   board recovery. Normal logging and firmware updates use BLE; DAPLink must not
   remain attached during rotation or impact.
6. Add visible X/Y orientation marks and a unique core revision to the outer
   shell. Record total mass and a simple roll-down balance check for every
   mechanical revision.
7. Start with low-speed roller tests and gentle hand rolls. Putter impact begins
   only after the carrier has no detectable internal movement and the two shell
   halves cannot separate inside the roller guard.

A nominal 42.67 mm ball with a 2.0 mm shell has a 38.67 mm inner diameter. At
the Tag's 16.55 mm radial envelope, the spherical cavity still provides about
20.0 mm total axial space, so the 9.2 mm carrier keep-in is geometrically
feasible. The remaining space is valuable for compliant retention and balance;
it is not permission to let the assembly move.

## Not yet established

- Physical-print tolerances and the actual downloaded model-to-board fit.
- Complete assembly mass and centre-of-mass offset.
- RF loss through the chosen filament, infill and battery orientation.
- Survival under a normal or strong putter strike.
- NFC loop geometry and matching inside the final enclosure.
- Whether BMI270 clipping at `±16 g` and `±2000 dps` loses information needed by
  the product.

These are measured gates for the removable research core, not values to infer
from the STEP file.
