# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                 |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                  |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/auth.py               |       85 |       20 |        2 |        1 |     76% |118, 125-130, 175, 182-187, 248-253 |
| src/api/routes/base\_route.py        |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py        |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/items.py              |       58 |        0 |        0 |        0 |    100% |           |
| src/api/routes/recovery.py           |       62 |       14 |        4 |        2 |     76% |86, 100-107, 151, 163-168 |
| src/api/routes/shares.py             |       22 |        0 |        0 |        0 |    100% |           |
| src/api/routes/tags.py               |       10 |        0 |        0 |        0 |    100% |           |
| src/api/routes/vaults.py             |       16 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py      |       20 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py    |       84 |       11 |       18 |        6 |     83% |99, 128, 164, 199, 223-227, 231-235, 249-254 |
| src/entrypoint/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py      |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py |       19 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py           |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                   |       56 |        5 |       16 |        1 |     92% |60-64, 84-85, 223 |
| src/shared/errors.py                 |       81 |        0 |        8 |        0 |    100% |           |
| src/shared/models.py                 |      204 |        0 |        2 |        0 |    100% |           |
| src/shared/repository.py             |      145 |        4 |       22 |        1 |     97% |187, 508-510 |
| **TOTAL**                            |  **916** |   **54** |   **74** |   **11** | **93%** |           |


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