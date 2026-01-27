# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                 |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                  |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/auth.py               |       86 |       24 |        0 |        0 |     72% |128-133, 176-194, 246-264 |
| src/api/routes/base\_route.py        |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py        |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/items.py              |      284 |      132 |       36 |        0 |     50% |66-75, 95-96, 102-103, 115-117, 154-164, 186-187, 193-194, 206-208, 245-253, 259-260, 272-273, 279-280, 286-287, 293-294, 306-308, 377-491, 558-630, 716-759, 826-884 |
| src/api/routes/recovery.py           |       59 |       12 |        0 |        0 |     80% |95-102, 167-172 |
| src/api/routes/shares.py             |       22 |        0 |        0 |        0 |    100% |           |
| src/api/routes/tags.py               |       10 |        0 |        0 |        0 |    100% |           |
| src/api/routes/vaults.py             |       53 |        9 |        0 |        0 |     83% |96-101, 158-162 |
| src/api/services/\_\_init\_\_.py     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py      |       27 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py    |       84 |       11 |       18 |        6 |     83% |99, 128, 164, 199, 223-227, 231-235, 249-254 |
| src/api/services/item\_service.py    |      234 |       18 |       66 |        3 |     93% |319-320, 376-384, 423-424, 434-435, 449-450, 810-816, 822->837, 830-831, 915-920 |
| src/api/services/vault\_service.py   |       71 |        0 |       16 |        1 |     99% |  162->166 |
| src/entrypoint/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py      |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py |       27 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py           |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                   |       60 |        5 |       18 |        2 |     91% |60-64, 84-85, 223, 256->exit |
| src/shared/errors.py                 |       81 |        0 |        8 |        0 |    100% |           |
| src/shared/models.py                 |      315 |        9 |       14 |        3 |     95% |57, 126-128, 134-141, 373, 381 |
| src/shared/repository.py             |      176 |       17 |       30 |        4 |     90% |166->169, 182-186, 246, 321-326, 358-363, 403-413, 615-616, 644-646 |
| **TOTAL**                            | **1643** |  **237** |  **208** |   **19** | **84%** |           |


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