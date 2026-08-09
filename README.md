# L2 Motion Bed — Home Assistant custom integration

Direct local Bluetooth control for the Leon's L2 Motion / HHC D345 adjustable bed.

## Install on Home Assistant OS / Supervised

[![Open your Home Assistant instance and add the L2 Motion app repository](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FFranklin-C%2Fl2-motion-home-assistant)

1. Tap the button above and open the link in your Home Assistant instance.
2. Confirm **Add repository**.
3. Open **Settings → Apps**, select **L2 Motion Integration Installer**, and install it.
4. Start the installer once and check its log for `Installation complete`.
5. Restart Home Assistant.
6. Tap the setup button below.

[![Open your Home Assistant instance and start setting up L2 Motion Bed](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=l2_motion)

The installer app only copies `custom_components/l2_motion` into `/config` and then exits. It does not remain running. Container and Core installations should use the manual installation below.

## What it adds

- Home / Flat (`$O`)
- Memory 1 and Memory 2
- Head, feet, and extra Up/Down buttons (0.5-second adjustments)
- Under-bed light and massage buttons
- `l2_motion.move` action for precise timed movement
- `l2_motion.run_profile` action that homes the bed before replaying a saved position
- Compatibility with Home Assistant Bluetooth adapters and ESPHome Bluetooth proxies

## Manual installation

1. Extract this ZIP.
2. Copy the `l2_motion` folder from `custom_components` into Home Assistant's `/config/custom_components/` folder.
3. The final path must be `/config/custom_components/l2_motion/manifest.json`.
4. Restart Home Assistant completely.
5. Open **Settings → Devices & services → Add integration**.
6. Search for **L2 Motion Bed** and select the detected bed.

Close the L2 Motion phone app before setup. The app and Home Assistant cannot reliably control the same Bluetooth connection simultaneously.

If the integration says the bed was not found, Home Assistant does not have enough Bluetooth coverage near the bed. Add an ESPHome Bluetooth proxy near it.

## Test a precise movement

In **Developer tools → Actions**, choose `l2_motion.move`:

```yaml
action: l2_motion.move
data:
  section: head
  direction: up
  duration: 1.0
```

The D345 does not have a separate Stop command. Motion stops when Home Assistant stops sending the repeated command. Durations are therefore intentionally capped at 30 seconds.

## Mobile dashboard

Copy [`examples/dashboard.yaml`](examples/dashboard.yaml), then in a Home Assistant dashboard choose **Edit dashboard → Add card → Manual** and paste the YAML. Tap movement buttons for 0.5 seconds of movement or hold them for a two-second adjustment.

## Create a voice-controllable saved position

First use the web controller to determine the Head, Feet, and Extra timing. Then create a Home Assistant script like this:

```yaml
alias: Bed Reading Position
icon: mdi:bed
sequence:
  - action: l2_motion.run_profile
    data:
      home_wait: 18
      head: 4.2
      feet: 1.5
      extra: 0
mode: single
```

`run_profile` always sends Home/Flat first, waits for the bed to finish, and then replays the timings. Change `home_wait` if your bed needs longer than 18 seconds to flatten.

To expose the script to Google Home, expose the resulting script entity through Home Assistant Cloud's Google Assistant settings. A natural alias such as **Bed Reading Position** lets you say, “Hey Google, turn on Bed Reading Position.”

## Home/Flat accuracy

For this D345 profile, Home/Flat is a single `$O` write. It must not be held or repeated. Motor movement is different: `$K/$L/$M/$N/$P/$Q` is repeated every 100 ms and stops when transmission ends. This integration follows that behavior.

## Safety

Test with short durations first and keep the physical remote nearby. Bluetooth loss stops additional movement writes, but the built-in Home and Memory commands can continue travelling to their controller-defined positions.
