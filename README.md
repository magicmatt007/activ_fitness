[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/magicmatt007/activ_fitness?color=41BDF5&style=for-the-badge)
![Integration Usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&style=for-the-badge&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.activ_fitness.total)

# Activ Fitness Integration for Home Assistant

Note: You need to have an active membership to use this component.

This component lets you see the when your favorite courses in your favorite fitness locations are scheduled. You can also book these courses.

It provides also information about your studio check-ins.

## Features


### Senors

### Front End:
![My Image](img/screenshot.png)


Using Home Assitant's `tile` card you can have a very compact UI for displaying the upcoming courses. By clicking on the circles, you can book / unbook a course. Please give it a couple of seconds to execute the booking and update the UI.

``` YAML
type: vertical-stack
title: 'Upcoming courses:'
cards:
  - type: tile
    entity: binary_sensor.activ_fitness_course_0_booked
    icon_tap_action:
      action: call-service
      service: activ_fitness.toggle_booking
      data: {}
      target:
        entity_id: binary_sensor.activ_fitness_course_0_booked
    color: green
  - type: tile
    entity: binary_sensor.activ_fitness_course_1_booked
    icon_tap_action:
      action: call-service
      service: activ_fitness.toggle_booking
      data: {}
      target:
        entity_id: binary_sensor.activ_fitness_course_1_booked
    color: green
  - type: tile
    entity: binary_sensor.activ_fitness_course_2_booked
    icon_tap_action:
      action: call-service
      service: activ_fitness.toggle_booking
      data: {}
      target:
        entity_id: binary_sensor.activ_fitness_course_2_booked
    color: green
  - type: tile
    entity: binary_sensor.activ_fitness_course_3_booked
    icon_tap_action:
      action: call-service
      service: activ_fitness.toggle_booking
      data: {}
      target:
        entity_id: binary_sensor.activ_fitness_course_3_booked
    color: green
  - type: tile
    entity: binary_sensor.activ_fitness_course_4_booked
    icon_tap_action:
      action: call-service
      service: activ_fitness.toggle_booking
      data: {}
      target:
        entity_id: binary_sensor.activ_fitness_course_4_booked
    color: green


```

## Usage

Lovelace example: TODO


## Installation
### Option 1 (Recommended)

Use HACS. This ensures, you receive notifications about newer versions.

### Option 2

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `activ_fitness`.
4. Download _all_ the files from the `custom_components/activ_fitness/` directory (folder) in this repository, including the subdirectories.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Settings" -> "Devices & services", click "Add integration" and search for "Activ Fitness"

Using your HA configuration directory (folder) as a starting point you should now also something similar to this (Note: _Not all actual files are listed here_):

```text
custom_components/activ_fitness/translations/en.json
custom_components/activ_fitness/activ_fitness/api_class.py
custom_components/activ_fitness/__init__.py
custom_components/activ_fitness/binary_sensor.py
custom_components/activ_fitness/button.py
custom_components/activ_fitness/config_flow.py
custom_components/activ_fitness/const.py
custom_components/activ_fitness/manifest.json
custom_components/activ_fitness/sensor.py
```

## Configuration is done in the UI

1. Enter the login (email and password) of your Activ Fitness account. It is the Migros login you also use in the Activ Fitness app.
2. Select the studios (centers) you are interested in.
3. Select the courses you want to follow. If you select none, all courses of the selected studios are shown.

The integration updates every 15 minutes. It stores your login and the sessions it needs in Home Assistant's configuration, so it does not have to log in again with your password every time.

Tested with Home Assistant 2026.9.

<!---->

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

![license-shield]

***

[license-shield]: https://img.shields.io/github/license/magicmatt007/activ_fitness.svg?style=for-the-badge
