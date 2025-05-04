try:
    # Hack to work around greenlet not compiling in GitHub Actions for
    # Python 3.14.
    import playwright

    pytest_plugins = "tdom.fixtures"
except ImportError:
    pass
