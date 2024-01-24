import pytest


@pytest.fixture(scope="session", autouse=True)
def configure_test():
    print("configure_test()")
