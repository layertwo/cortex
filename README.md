# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                 |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                  |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/auth.py               |       76 |       18 |        0 |        0 |     76% |114-119, 162-167, 219-224 |
| src/api/routes/base\_route.py        |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py        |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/items.py              |       58 |        0 |        0 |        0 |    100% |           |
| src/api/routes/recovery.py           |       55 |       12 |        0 |        0 |     78% |94-101, 153-158 |
| src/api/routes/shares.py             |       22 |        0 |        0 |        0 |    100% |           |
| src/api/routes/tags.py               |       10 |        0 |        0 |        0 |    100% |           |
| src/api/routes/vaults.py             |       49 |        9 |        0 |        0 |     82% |82-87, 144-148 |
| src/api/services/\_\_init\_\_.py     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py      |       27 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py    |       84 |       11 |       18 |        6 |     83% |99, 128, 164, 199, 223-227, 231-235, 249-254 |
| src/api/services/vault\_service.py   |       71 |        0 |       16 |        1 |     99% |  162->166 |
| src/entrypoint/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py      |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py |       23 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py           |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                   |       56 |        5 |       16 |        1 |     92% |60-64, 84-85, 223 |
| src/shared/errors.py                 |       81 |        0 |        8 |        0 |    100% |           |
| src/shared/models.py                 |      221 |        4 |        8 |        2 |     97% |244, 250-252 |
| src/shared/repository.py             |      138 |       13 |       18 |        1 |     91% |186, 258-263, 295-300, 340-350, 499-501 |
| **TOTAL**                            | **1025** |   **72** |   **86** |   **11** | **93%** |           |


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