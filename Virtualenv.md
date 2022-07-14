# Python **virtualenv** Setup

How to run and test this code in a python virtualenv:

```shell
# install or update virtualenv:
pip install --upgrade virtualenv
# create a new virtualenv:
python -m venv venv
# activate the virtualenv:
venv\Scripts\activate.bat
# update pip within the virtualenv:
python -m pip install --upgrade pip
# install or update tools within the virtualenv:
pip install --upgrade wheel setuptools poetry autopep8 mypy
# next line only if you want to use jupyter notebooks:
pip install --upgrade jupyter jupyterlab
# install dependencies:
pip install --upgrade -r requirements.txt
# develop and test your code
python main.py
# ......
# deactivate the virtualenv:
deactivate.bat
```

---

> Last updated: 12.07.2022
