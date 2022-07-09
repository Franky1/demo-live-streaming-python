# Python **virtualenv** Setup

```shell
pip install --upgrade virtualenv
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install --upgrade wheel setuptools poetry autopep8
pip install --upgrade jupyter jupyterlab
pip install --upgrade -r requirements.txt
# develop and test your code
# ......
deactivate.bat
```

---

> Last updated: 09.07.2022
