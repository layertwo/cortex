# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                             |    Stmts |     Miss |   Branch |   BrPart |  Cover |   Missing |
|--------------------------------- | -------: | -------: | -------: | -------: | -----: | --------: |
| src/api/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |   100% |           |
| src/api/handler.py               |        2 |        0 |        0 |        0 |   100% |           |
| src/api/routes/\_\_init\_\_.py   |        0 |        0 |        0 |        0 |   100% |           |
| src/api/services/\_\_init\_\_.py |        0 |        0 |        0 |        0 |   100% |           |
| src/shared/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |   100% |           |
| src/shared/auth.py               |       56 |       56 |       16 |        0 |     0% |    10-225 |
| src/shared/errors.py             |       81 |       81 |        8 |        0 |     0% |    10-239 |
| src/shared/models.py             |      204 |      204 |        2 |        0 |     0% |    10-445 |
| src/shared/repository.py         |      145 |      145 |       22 |        0 |     0% |    10-510 |
| **TOTAL**                        |  **488** |  **486** |   **48** |    **0** | **1%** |           |


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