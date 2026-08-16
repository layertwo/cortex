# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                    |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py           |      101 |       23 |       16 |        6 |     74% |45, 112-127, 156-170, 197-209, 237-245, 278-291, 321-332 |
| src/api/routes/items.py                 |      120 |        4 |        6 |        2 |     95% |199, 219, 254, 314 |
| src/api/routes/shares.py                |       49 |        5 |        6 |        3 |     85% |85, 90-92, 131 |
| src/api/routes/tags.py                  |       27 |        0 |        2 |        0 |    100% |           |
| src/api/routes/vaults.py                |       47 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/collection\_service.py |      142 |       27 |       30 |        6 |     80% |246, 302, 400, 406, 420, 518, 591-629, 659-692 |
| src/api/services/item\_service.py       |      370 |       56 |      118 |       14 |     85% |387, 404-415, 435-436, 450-471, 512-517, 524-529, 539-544, 702-703, 708-709, 711-712, 771, 788-789, 948-954, 960-\>976, 968-973, 990-995, 1008-1032, 1053-1058, 1077, 1094-1096, 1173, 1176-\>1179, 1180-\>1183 |
| src/api/services/share\_service.py      |       93 |        8 |       22 |        4 |     90% |169, 187, 201-202, 249, 330-335 |
| src/api/services/vault\_service.py      |      108 |       11 |       28 |        4 |     86% |164-\>168, 281-\>284, 354-362, 388-392 |
| src/entrypoint/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                   |        4 |        4 |        0 |        0 |      0% |       3-8 |
| src/entrypoint/container.py             |        5 |        5 |        0 |        0 |      0% |      3-10 |
| src/environment/\_\_init\_\_.py         |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py    |       88 |        6 |        6 |        1 |     93% |107-113, 218, 309 |
| src/shared/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/\_codegen\_base.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                      |       28 |        8 |       10 |        0 |     63% |     68-78 |
| src/shared/exceptions.py                |       39 |        0 |        0 |        0 |    100% |           |
| src/shared/logger.py                    |        7 |        0 |        0 |        0 |    100% |           |
| src/shared/models.py                    |      293 |       12 |       14 |        3 |     94% |126-128, 140, 376, 379-384, 409 |
| src/shared/repository.py                |      208 |       50 |       36 |        5 |     77% |56-61, 92-93, 131-136, 209-214, 230-239, 267-269, 273-278, 339-344, 391-396, 426-431, 471-480, 510-515, 537-546, 597-602, 622-626, 664-668, 709-710, 738-740 |
| src/shared/util.py                      |       10 |        3 |        4 |        0 |     64% |     37-39 |
| **TOTAL**                               | **1745** |  **222** |  **298** |   **48** | **86%** |           |


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