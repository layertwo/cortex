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
| src/api/routes/items.py                 |      161 |       22 |       32 |       10 |     79% |46, 170-172, 231, 235, 244, 272-296, 310, 359, 361, 363, 365 |
| src/api/routes/recovery.py              |       46 |        0 |        0 |        0 |    100% |           |
| src/api/routes/shares.py                |       22 |        0 |        0 |        0 |    100% |           |
| src/api/routes/tags.py                  |       10 |        0 |        0 |        0 |    100% |           |
| src/api/routes/vaults.py                |       40 |        0 |        0 |        0 |    100% |           |
| src/api/services/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/api/services/api\_router.py         |       20 |        0 |        2 |        0 |    100% |           |
| src/api/services/auth\_service.py       |       84 |        0 |       18 |        0 |    100% |           |
| src/api/services/collection\_service.py |      146 |       26 |       28 |        5 |     81% |254, 311, 409, 432, 548, 622-661, 691-725 |
| src/api/services/item\_service.py       |      224 |       43 |       58 |        5 |     82% |307-318, 338-339, 353-377, 415-420, 427-432, 442-447, 643-647, 741-747, 753->769, 761-766, 783-788, 797-822, 842-847 |
| src/api/services/vault\_service.py      |       71 |        0 |       16 |        1 |     99% |  165->169 |
| src/entrypoint/\_\_init\_\_.py          |        0 |        0 |        0 |        0 |    100% |           |
| src/entrypoint/api.py                   |        5 |        0 |        0 |        0 |    100% |           |
| src/environment/\_\_init\_\_.py         |        0 |        0 |        0 |        0 |    100% |           |
| src/environment/service\_provider.py    |       31 |        0 |        0 |        0 |    100% |           |
| src/shared/\_\_init\_\_.py              |        0 |        0 |        0 |        0 |    100% |           |
| src/shared/auth.py                      |       20 |        2 |        4 |        0 |     92% |     59-63 |
| src/shared/models.py                    |      315 |        6 |       14 |        3 |     97% |126-128, 140, 375, 383 |
| src/shared/repository.py                |      180 |       48 |       32 |        4 |     75% |55-60, 91-94, 132-137, 181-195, 210-215, 276-281, 330-335, 367-372, 412-422, 455-460, 485-495, 512-517, 537-541, 579-583, 624-625, 653-655 |
| **TOTAL**                               | **1590** |  **186** |  **220** |   **32** | **87%** |           |


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