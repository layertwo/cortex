# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                            |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py                  |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py                  |      101 |       11 |       16 |        4 |     87% |165-169, 245-253, 286-299, 329-340 |
| src/api/routes/items.py                        |      126 |        4 |        6 |        2 |     95% |219, 239, 274, 328 |
| src/api/routes/shares.py                       |       49 |        5 |        6 |        3 |     85% |85, 90-92, 131 |
| src/api/routes/tags.py                         |       27 |        0 |        2 |        0 |    100% |           |
| src/api/routes/vaults.py                       |       86 |        0 |        6 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py               |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/collection\_service.py        |      153 |       27 |       36 |        6 |     81% |283, 307, 404, 410, 424, 522, 595-633, 663-696 |
| src/api/services/item\_service.py              |      367 |       55 |      116 |       13 |     86% |397, 414-425, 445-446, 460-481, 522-527, 534-539, 549-554, 712-713, 718-719, 721-722, 790-791, 950-956, 962-\>978, 970-975, 992-997, 1010-1034, 1055-1060, 1077, 1087-1089, 1166, 1169-\>1172, 1173-\>1176 |
| src/api/services/rotation\_abandon\_service.py |       36 |        0 |        8 |        0 |    100% |           |
| src/api/services/share\_service.py             |       93 |        8 |       22 |        4 |     90% |169, 187, 201-202, 249, 330-335 |
| src/api/services/vault\_deletion\_service.py   |      117 |        3 |       44 |        4 |     96% |135-\>144, 169, 177, 205 |
| src/api/services/vault\_service.py             |      240 |        2 |       74 |        1 |     99% |   611-615 |
| src/entrypoint/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                          |        4 |        4 |        0 |        0 |      0% |       3-8 |
| src/entrypoint/container.py                    |        5 |        5 |        0 |        0 |      0% |      3-10 |
| src/environment/\_\_init\_\_.py                |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py           |       96 |        6 |        6 |        1 |     93% |112-118, 245, 342 |
| src/shared/\_\_init\_\_.py                     |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/\_codegen\_base.py                  |        3 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                             |       28 |        8 |       10 |        0 |     63% |     68-78 |
| src/shared/exceptions.py                       |       39 |        0 |        0 |        0 |    100% |           |
| src/shared/logger.py                           |        7 |        0 |        0 |        0 |    100% |           |
| src/shared/models.py                           |      293 |       12 |       14 |        3 |     94% |126-128, 140, 376, 379-384, 409 |
| src/shared/repository.py                       |      218 |       47 |       38 |        5 |     80% |56-61, 92-93, 131-136, 209-214, 230-239, 267-269, 273-278, 339-344, 385-390, 437-442, 472-477, 517-526, 556-561, 668-672, 710-714, 755-756, 784-786 |
| src/shared/util.py                             |       12 |        3 |        4 |        0 |     69% |     42-44 |
| **TOTAL**                                      | **2103** |  **200** |  **408** |   **46** | **90%** |           |


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