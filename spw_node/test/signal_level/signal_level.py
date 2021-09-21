from . import a

signal_level_tests = [
    a.test_6_3_2_a
]

if __name__ == '__main__':
    for test in signal_level_tests:
        print(f"Running {test.__name__}...    " + "OK !" if not test() else "FAIL !")
