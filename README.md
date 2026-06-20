# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/layertwo/cortex/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                    |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/\_\_init\_\_.py                     |        0 |        0 |        0 |        0 |    100% |           |
| src/api/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/api/routes/base\_route.py           |        3 |        0 |        0 |        0 |    100% |           |
| src/api/routes/collections.py           |      108 |       29 |       20 |        6 |     68% |101-138, 172-202, 239-247, 284-293, 334-343, 383-395 |
| src/api/routes/items.py                 |      126 |       17 |       26 |        8 |     78% |181, 206-230, 242, 276, 294, 296, 298, 300 |
| src/api/routes/shares.py                |       49 |        5 |        6 |        3 |     85% |86, 91-93, 138 |
| src/api/routes/tags.py                  |       31 |        0 |       10 |        0 |    100% |           |
| src/api/routes/vaults.py                |       30 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/collection\_service.py |      142 |       27 |       30 |        6 |     80% |251, 308, 406, 412, 428, 530, 604-643, 673-707 |
| src/api/services/item\_service.py       |      285 |       46 |       82 |        9 |     84% |321-332, 352-353, 367-391, 429-434, 441-446, 456-461, 755-761, 767-\>783, 775-780, 797-802, 815-841, 862-867, 886, 903-905, 982, 985-\>988, 989-\>992 |
| src/api/services/share\_service.py      |       93 |        8 |       22 |        4 |     90% |164, 182, 196-197, 242, 324-329 |
| src/api/services/vault\_service.py      |       72 |        0 |       16 |        1 |     99% | 164-\>168 |
| src/entrypoint/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                   |        4 |        4 |        0 |        0 |      0% |       3-8 |
| src/entrypoint/container.py             |        5 |        5 |        0 |        0 |      0% |      3-10 |
| src/environment/\_\_init\_\_.py         |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py    |       88 |        6 |        6 |        1 |     93% |100-106, 211, 292 |
| src/shared/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                      |       27 |        8 |       10 |        0 |     62% |     67-77 |
| src/shared/exceptions.py                |       34 |        0 |        0 |        0 |    100% |           |
| src/shared/logger.py                    |        7 |        0 |        0 |        0 |    100% |           |
| src/shared/models.py                    |      293 |        6 |       14 |        3 |     96% |126-128, 140, 376, 384 |
| src/shared/repository.py                |      201 |       57 |       36 |        5 |     73% |56-61, 92-93, 131-136, 180-194, 209-214, 230-239, 267-269, 273-278, 339-344, 393-398, 430-435, 475-485, 518-523, 548-558, 575-580, 600-604, 642-646, 687-688, 716-718 |
| src/shared/util.py                      |       10 |        2 |        4 |        2 |     71% |    21, 39 |
| **TOTAL**                               | **1608** |  **220** |  **282** |   **48** | **84%** |           |


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