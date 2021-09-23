from . import tests

if __name__ == '__main__':
    for test in tests:
        print(f"Running {test.__name__}...    " + "OK !" if not test() else "FAIL !")
