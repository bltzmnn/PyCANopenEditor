# `eds/` — Sample EDS / XDD files

This directory bundles a curated set of public CANopen **Electronic Data Sheet
(EDS)** and **XML Device Description (XDD)** files used by the test suite to
exercise the parser, exporter and view-model code paths.

All files are sourced from public open-source repositories (see per-file
provenance below). They are **not** committed as customer-specific data and
they contain no internal references.

## Quick start

```bash
# Run the full test suite against the bundled samples (auto-defaults to eds/)
pytest tests/

# Point at your own directory of EDS files
PYCANOPEN_TEST_EDS_DIR=/path/to/your/eds pytest tests/
```

The test suite automatically uses this `eds/` directory when
`PYCANOPEN_TEST_EDS_DIR` is not set, so no manual configuration is needed.

## File inventory

| File | Format | Source | Profile / Device |
|---|---|---|---|
| `canopen_sample.eds` | EDS | [canopen-python/canopen](https://github.com/canopen-python/canopen) | test fixture |
| `canopen_datatypes.eds` | EDS | [canopen-python/canopen](https://github.com/canopen-python/canopen) | test fixture (datatypes) |
| `canopen_e35.eds` | EDS | [canopen-python/canopen](https://github.com/canopen-python/canopen) | generic E35 industrial sensor |
| `canopennode_ds301_profile.eds` | EDS | [CANopenNode/CANopenNode](https://github.com/CANopenNode/CANopenNode) | CiA 301 (DS301 standard profile) |
| `canopennode_basic_device.eds` | EDS | [CANopenNode/CANopenSocket](https://github.com/CANopenNode/CANopenSocket) | basic socket device |
| `canopennode_basic_device.xdd` | XDD | [CANopenNode/CANopenSocket](https://github.com/CANopenNode/CANopenSocket) | basic socket device (XDD variant) |
| `dm_motor_slave.eds` | EDS | [dmBots/dm_canopen](https://github.com/dmBots/dm_canopen) | DM-series motor driver (slave) |
| `dm4310_master.xdd` | XDD | [dmBots/dm_canopen](https://github.com/dmBots/dm_canopen) | DM4310 master (XDD) |
| `dm4310_slave.xdd` | XDD | [dmBots/dm_canopen](https://github.com/dmBots/dm_canopen) | DM4310 slave (XDD) |
| `cia_301_profile.eds` | EDS | [grafoteka/kacanopen](https://github.com/grafoteka/kacanopen) | CiA 301 — generic communication profile |
| `cia_401_io.eds` | EDS | [grafoteka/kacanopen](https://github.com/grafoteka/kacanopen) | CiA 401 — generic I/O modules |
| `cia_402_profile.eds` | EDS | [grafoteka/kacanopen](https://github.com/grafoteka/kacanopen) | CiA 402 — drives and motion control |
| `cia_406_encoder.eds` | EDS | [grafoteka/kacanopen](https://github.com/grafoteka/kacanopen) | CiA 406 — rotary / linear encoders |
| `faulhaber_605_3150_55.eds` | EDS | [KITmedical/kacanopen](https://github.com/KITmedical/kacanopen_old) | Faulhaber MCLM motor |
| `faulhaber_605_3150_68b.eds` | EDS | [KITmedical/kacanopen](https://github.com/KITmedical/kacanopen_old) | Faulhaber MCDC motor |
| `faulhaber_605_3150_71a.eds` | EDS | [KITmedical/kacanopen](https://github.com/KITmedical/kacanopen_old) | Faulhaber Sinus2 motor |
| `systec_iox1.eds` | EDS | [KITmedical/kacanopen](https://github.com/KITmedical/kacanopen_old) | Systec sysWORXX IO-X1 (16DI/8DO) |
| `minimal_project.xdd` | XDD | [CANopenNode/CANopenEditor](https://github.com/CANopenNode/CANopenEditor) | minimal test device (XDD v1.1) |

Total: **14 EDS + 4 XDD = 18 files**.

## Coverage

* **Communication profile** (CiA 301, DS301) — 2 files
* **I/O module profile** (CiA 401) — 1 file
* **Drives / motion control profile** (CiA 402) — 1 file
* **Encoder profile** (CiA 406) — 1 file
* **Test fixtures** (Python canopen test suite) — 2 files
* **Generic industrial sensor** (E35) — 1 file
* **Servo / stepper motors** (Faulhaber ×3, DM-driver) — 4 files
* **Discrete I/O** (Systec) — 1 file
* **XDD XML variants** for the same basic / motor data — 3 files
* **XDD test device** (CANopenEditor minimal project) — 1 file

## Source projects

| Project | License | Notes |
|---|---|---|
| [canopen-python/canopen](https://github.com/canopen-python/canopen) | MIT | Python CANopen library + reference test EDS files |
| [CANopenNode/CANopenNode](https://github.com/CANopenNode/CANopenNode) | Apache-2.0 | Reference implementation of the CANopen stack; ships the canonical DS301 profile |
| [CANopenNode/CANopenSocket](https://github.com/CANopenNode/CANopenSocket) | Apache-2.0 | Linux/BSD socket integration; provides the `basicDevice` example |
| [dmBots/dm_canopen](https://github.com/dmBots/dm_canopen) | — | DM motor driver firmware project |
| [grafoteka/kacanopen](https://github.com/grafoteka/kacanopen) | — | Fork of KaCanOpen with the full CiA profile library |
| [KITmedical/kacanopen_old](https://github.com/KITmedical/kacanopen_old) | BSD / LGPL | Robotics stack bundled with vendor EDS samples (Faulhaber, Systec) |
| [CANopenNode/CANopenEditor](https://github.com/CANopenNode/CANopenEditor) | GPL | C# CANopen editor; provides the minimal XDD test device |

EDS files are technical documentation under their respective vendors'
copyright and are included here for **testing and interoperability purposes
only**, consistent with fair-use of device description files in open-source
CANopen tooling.

## Refreshing the samples

If you need to refresh a file from its upstream source, use the raw URL
recorded in the table above. The download itself is straightforward:

```bash
curl -sSL -o faulhaber_605_3150_55.eds \
  https://gh-proxy.com/https://raw.githubusercontent.com/KITmedical/kacanopen_old/master/eds/Faulhaber/605.3150.55-D-EK-2-60.eds
```

If you have no direct connectivity to GitHub, replace the host with a public
mirror such as `gh-proxy.com`, `ghproxy.com`, etc.
