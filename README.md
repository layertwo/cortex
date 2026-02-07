# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                    |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/auth.py                  |       68 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py           |      144 |       39 |       16 |        4 |     68% |114-160, 197-231, 265-281, 321-335, 373-390, 432-449 |
| src/api/routes/items.py                 |      157 |       21 |       30 |        9 |     80% |153-155, 214, 218, 227, 255-279, 293, 342, 344, 346, 348 |
| src/api/routes/recovery.py              |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/shares.py                |       55 |        5 |        4 |        2 |     88% |49-51, 94, 141 |
| src/api/routes/tags.py                  |       42 |        0 |       16 |        0 |    100% |           |
| src/api/routes/vaults.py                |       40 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py         |       20 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py       |       85 |        0 |       18 |        0 |    100% |           |
| src/api/services/collection\_service.py |      142 |       27 |       30 |        6 |     80% |254, 311, 409, 415, 431, 533, 607-646, 676-710 |
| src/api/services/item\_service.py       |      287 |       48 |       82 |       10 |     84% |326-337, 357-358, 372-396, 434-439, 446-451, 461-466, 662-666, 760-766, 772->788, 780-785, 802-807, 820-846, 867-872, 891, 908-910, 987, 990->993, 994->997 |
| src/api/services/share\_service.py      |      108 |       13 |       22 |        5 |     86% |72-73, 197, 215, 229-230, 275, 336-341, 357-362 |
| src/api/services/vault\_service.py      |       72 |        0 |       16 |        1 |     99% |  167->171 |
| src/entrypoint/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                   |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py         |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py    |       35 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                      |       20 |        2 |        4 |        0 |     92% |     59-63 |
| src/shared/models.py                    |      312 |        6 |       14 |        3 |     97% |126-128, 140, 376, 384 |
| src/shared/repository.py                |      201 |       57 |       36 |        5 |     73% |55-60, 91-94, 132-137, 181-195, 210-215, 231-240, 268-270, 274-279, 340-345, 394-399, 431-436, 476-486, 519-524, 549-559, 576-581, 601-605, 643-647, 688-689, 717-719 |
| src/shared/util.py                      |       10 |        2 |        4 |        2 |     71% |    21, 39 |
| **TOTAL**                               | **1852** |  **220** |  **294** |   **47** | **86%** |           |


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