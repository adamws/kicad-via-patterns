# ![icon](resources/icon.png) KiCad Via Patterns

|         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---     | ---                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| CI/CD   | [![CircleCI](https://circleci.com/gh/adamws/kicad-via-patterns.svg?style=shield)](https://circleci.com/gh/adamws/kicad-via-patterns/tree/master) [![Coverage Status](https://coveralls.io/repos/github/adamws/kicad-via-patterns/badge.svg)](https://coveralls.io/github/adamws/kicad-via-patterns)
| Package | [![KiCad Repository](https://img.shields.io/badge/KiCad-Plugin%20Repository-blue)](https://gitlab.com/kicad/addons/metadata/-/tree/main/packages/com.github.adamws.kicad-via-patterns) ![KiCad v7](https://img.shields.io/badge/kicad-v7-green) ![KiCad v8](https://img.shields.io/badge/kicad-v8-green) [![PyPI - Version](https://img.shields.io/pypi/v/kicad-via-patterns.svg)](https://pypi.org/project/kicad-via-patterns)                                                                                                                                                                                    |
| Meta    | [![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch) [![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![code style - Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy) [![License - MIT](https://img.shields.io/badge/license-MIT-9400d3.svg)](https://spdx.org/licenses/) |

-----

Add vias using various patterns

## Key Features

Arranges vias in pattern with respect to clearance rules and trace width.
Following table shows images of supported patterns with clearance outlines enabled.

<table>
  <tr>
    <td align="center"><b>Pattern</b></td>
    <th align="center"><b>Example</b></th>
  </tr>
  <tr>
    <td align="center" style="vertical-align: middle;">Perpendicular</td>
    <td align="center"><img src="resources/perpendicular.png" width="80%"/></td>
  </tr>
  <tr>
    <td align="center" style="vertical-align: middle;">Diagonal</td>
    <td align="center"><img src="resources/diagonal.png" width="80%"/></td>
  </tr>
  <tr>
    <td align="center" style="vertical-align: middle;">Stagger</td>
    <td align="center"><img src="resources/stagger.png" width="80%"/></td>
  </tr>
</table>

## Installation

To install release version of this plugin, use KiCad's `Plugin and Content Manager`
and select `Via Patterns` from official plugin repository.

![pcm-image](resources/pcm.png)

Latest `master` build is automatically uploaded to unofficial PCM compatible
[repository](https://adamws.github.io/kicad-via-patterns/) hosted on GitHub pages.
To use it, add `https://adamws.github.io/kicad-via-patterns/repository.json`
to PCM repository list.

## How to use

1. Select via.
2. Click plugin icon to open dialog window.

    ![gui](resources/gui.png)

   Select pattern type and size. Set track width. Click OK.
3. Adjust pattern orientation with rotation buttons in new pop-up dialog.

    ![gui-rotate](resources/gui-rotate.png)

4. Pattern will start at position of selected via and will use it as an template (i.e. added vias will have same properties except net).
    - Pattern elements will be automatically selected to ease reposition or rotation/flip.
5. Update nets of created vias and continue routing.

## License

This project is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
