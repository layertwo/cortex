# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                 |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                  |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/auth.py               |       86 |       27 |        0 |        0 |     69% |115-133, 176-194, 246-264 |
| src/api/routes/base\_route.py        |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py        |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/items.py              |      135 |       37 |        0 |        0 |     73% |62-71, 78-79, 91-92, 98-99, 111-113, 150-160, 169-170, 182-183, 189-190, 202-204, 241-249, 255-256, 268-269, 275-276, 282-283, 289-290, 302-304 |
| src/api/routes/recovery.py           |       59 |       15 |        0 |        0 |     75% |95-102, 154-172 |
| src/api/routes/shares.py             |       22 |        0 |        0 |        0 |    100% |           |
| src/api/routes/tags.py               |       10 |        0 |        0 |        0 |    100% |           |
| src/api/routes/vaults.py             |       53 |       12 |        0 |        0 |     77% |83-101, 158-162 |
| src/api/services/\_\_init\_\_.py     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py      |       27 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py    |       84 |       11 |       18 |        6 |     83% |99, 128, 164, 199, 223-227, 231-235, 249-254 |
| src/api/services/item\_service.py    |      118 |       10 |       30 |        1 |     93% |317-318, 374-382, 421-422, 432-433, 447-448 |
| src/api/services/vault\_service.py   |       71 |        0 |       16 |        1 |     99% |  162->166 |
| src/entrypoint/\_\_init\_\_.py       |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py      |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py |       27 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py           |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                   |       56 |        5 |       16 |        1 |     92% |60-64, 84-85, 223 |
| src/shared/errors.py                 |       81 |        0 |        8 |        0 |    100% |           |
| src/shared/models.py                 |      269 |        5 |       10 |        3 |     97% |57, 292, 298-300 |
| src/shared/repository.py             |      171 |       15 |       26 |        3 |     91% |166->169, 182-186, 244, 316-321, 353-358, 398-408, 634-636 |
| **TOTAL**                            | **1323** |  **137** |  **126** |   **15** | **90%** |           |


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