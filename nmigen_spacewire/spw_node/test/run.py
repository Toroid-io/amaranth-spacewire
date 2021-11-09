from .signal_level import tests as signal_level_tests

if __name__ == '__main__':
    print("Running Singal Level test suite...")
    for test in signal_level_tests:
        print(f"Running {test.__name__}...    " + "OK !" if not test() else "FAIL !")