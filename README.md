# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                         |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|--------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                          |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                      |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py               |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py                |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py                |      101 |       11 |       16 |        4 |     87% |165-169, 245-253, 286-299, 329-340 |
| src/api/routes/health.py                     |       24 |        0 |        2 |        0 |    100% |           |
| src/api/routes/items.py                      |      118 |        4 |        6 |        2 |     95% |219, 239, 274, 328 |
| src/api/routes/shares.py                     |       49 |        5 |        6 |        3 |     85% |85, 90-92, 131 |
| src/api/routes/tags.py                       |       27 |        0 |        2 |        0 |    100% |           |
| src/api/routes/vaults.py                     |       86 |        0 |        2 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py             |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/collection\_service.py      |      153 |       27 |       36 |        6 |     81% |283, 307, 404, 410, 424, 522, 595-633, 663-696 |
| src/api/services/item\_service.py            |      369 |       54 |      116 |       14 |     86% |394, 411-422, 442-443, 457-478, 519-524, 531-536, 544-549, 707-708, 713-714, 716-717, 857, 949-955, 961-\>977, 969-974, 991-996, 1009-1033, 1054-1059, 1076, 1086-1088, 1165, 1168-\>1171, 1172-\>1175 |
| src/api/services/share\_service.py           |       94 |        8 |       22 |        4 |     90% |170, 188, 202-203, 249, 330-335 |
| src/api/services/vault\_deletion\_service.py |      117 |        3 |       44 |        4 |     96% |135-\>144, 169, 177, 205 |
| src/api/services/vault\_service.py           |      203 |        6 |       58 |        4 |     96% |354-\>358, 631-636, 638-639, 647-651 |
| src/entrypoint/\_\_init\_\_.py               |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                        |        4 |        4 |        0 |        0 |      0% |       3-8 |
| src/entrypoint/container.py                  |        5 |        5 |        0 |        0 |      0% |      3-10 |
| src/environment/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py         |       90 |        6 |        6 |        1 |     93% |112-118, 235, 333 |
| src/shared/\_\_init\_\_.py                   |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/\_codegen\_base.py                |        3 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                           |       28 |        1 |        8 |        1 |     94% |        70 |
| src/shared/exceptions.py                     |       39 |        0 |        0 |        0 |    100% |           |
| src/shared/logger.py                         |        7 |        0 |        0 |        0 |    100% |           |
| src/shared/models.py                         |      294 |       12 |       14 |        3 |     94% |126-128, 140, 376, 379-384, 409 |
| src/shared/oidc.py                           |       34 |        4 |        2 |        0 |     89% | 29, 35-37 |
| src/shared/repository.py                     |      214 |       44 |       38 |        5 |     81% |62-67, 98-99, 137-142, 215-220, 248-250, 254-259, 320-325, 366-371, 418-423, 453-458, 498-507, 537-542, 649-653, 691-695, 736-737, 765-767 |
| src/shared/util.py                           |       12 |        3 |        4 |        0 |     69% |     42-44 |
| **TOTAL**                                    | **2074** |  **197** |  **382** |   **51** | **89%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/layertwo/cortex/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/layertwo/cortex/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Flayertwo%2Fcortex%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.