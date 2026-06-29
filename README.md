# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                    |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py           |      101 |       23 |       16 |        6 |     74% |45, 113-129, 158-174, 201-214, 242-251, 284-298, 328-340 |
| src/api/routes/items.py                 |      120 |        4 |        6 |        2 |     95% |202, 222, 257, 319 |
| src/api/routes/shares.py                |       49 |        5 |        6 |        3 |     85% |86, 91-93, 132 |
| src/api/routes/tags.py                  |       27 |        0 |        2 |        0 |    100% |           |
| src/api/routes/vaults.py                |       29 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/collection\_service.py |      142 |       27 |       30 |        6 |     80% |251, 308, 408, 414, 430, 530, 604-643, 673-707 |
| src/api/services/item\_service.py       |      364 |       56 |      114 |       15 |     85% |390, 407-418, 438-439, 453-477, 519-524, 531-536, 546-551, 707-\>710, 711-712, 717-718, 720-721, 774, 791-792, 955-961, 967-\>983, 975-980, 997-1002, 1015-1041, 1062-1067, 1086, 1103-1105, 1182, 1185-\>1188, 1189-\>1192 |
| src/api/services/share\_service.py      |       93 |        8 |       22 |        4 |     90% |170, 188, 202-203, 250, 332-337 |
| src/api/services/vault\_service.py      |       72 |        0 |       16 |        1 |     99% | 164-\>168 |
| src/entrypoint/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                   |        4 |        4 |        0 |        0 |      0% |       3-8 |
| src/entrypoint/container.py             |        5 |        5 |        0 |        0 |      0% |      3-10 |
| src/environment/\_\_init\_\_.py         |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py    |       88 |        6 |        6 |        1 |     93% |102-108, 213, 296 |
| src/shared/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/\_codegen\_base.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                      |       27 |        8 |       10 |        0 |     62% |     67-77 |
| src/shared/exceptions.py                |       34 |        0 |        0 |        0 |    100% |           |
| src/shared/logger.py                    |        7 |        0 |        0 |        0 |    100% |           |
| src/shared/models.py                    |      293 |       12 |       14 |        3 |     94% |126-128, 140, 376, 379-384, 409 |
| src/shared/repository.py                |      208 |       50 |       36 |        5 |     77% |56-61, 92-93, 131-136, 209-214, 230-239, 267-269, 273-278, 339-344, 393-398, 430-435, 475-485, 518-523, 548-558, 610-615, 635-639, 677-681, 722-723, 751-753 |
| src/shared/util.py                      |       10 |        3 |        4 |        0 |     64% |     37-39 |
| **TOTAL**                               | **1679** |  **211** |  **282** |   **46** | **86%** |           |


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